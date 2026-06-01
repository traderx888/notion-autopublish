"""CLI entry point for signal-triggered NotebookLM fundamental research.

Usage:
    # Explicit tickers
    python scrape_notebooklm_research.py --tickers XENE,SMCI --max-youtube 3

    # Auto-extract from signal files
    python scrape_notebooklm_research.py --from-signals --signals-dir ../fundman-jarvis/data

    # Dry run (show targets without calling NotebookLM)
    python scrape_notebooklm_research.py --from-signals --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Ensure utf-8 on Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SCRAPED_DIR = Path(__file__).parent / "scraped_data"
OUTPUT_DIR = SCRAPED_DIR / "notebooklm"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Signal-triggered NotebookLM fundamental research",
    )
    parser.add_argument(
        "--tickers",
        help="Comma-separated ticker list (e.g. XENE,SMCI,NVDA)",
    )
    parser.add_argument(
        "--from-signals",
        action="store_true",
        help="Auto-extract tickers from signal files",
    )
    parser.add_argument(
        "--signals-dir",
        default=str(Path(__file__).parent / ".." / "fundman-jarvis" / "data"),
        help="Path to fundman-jarvis data dir (default: ../fundman-jarvis/data)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(OUTPUT_DIR),
        help="Output directory (default: scraped_data/notebooklm)",
    )
    parser.add_argument(
        "--notebooklm-storage",
        default=None,
        help="Path to NotebookLM storage_state.json",
    )
    parser.add_argument(
        "--max-tickers",
        type=int,
        default=5,
        help="Max tickers to research (default: 5)",
    )
    parser.add_argument(
        "--max-youtube",
        type=int,
        default=3,
        help="Max YouTube sources per ticker (default: 3)",
    )
    parser.add_argument(
        "--no-deep-research",
        action="store_true",
        help="Skip NotebookLM deep research (YouTube sources only)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show targets without calling NotebookLM",
    )
    return parser.parse_args()


def _build_targets(args: argparse.Namespace) -> list[dict]:
    """Build research targets from CLI args."""
    if args.tickers:
        tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
        return [{"ticker": t, "source": "manual"} for t in tickers]

    if args.from_signals:
        from notebooklm_research.signals import collect_research_targets

        signals_dir = Path(args.signals_dir).resolve()
        return collect_research_targets(
            scraped_dir=SCRAPED_DIR,
            fundman_data_dir=signals_dir if signals_dir.exists() else None,
            max_targets=args.max_tickers,
        )

    print("Error: specify --tickers or --from-signals", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    args = _parse_args()
    targets = _build_targets(args)

    if not targets:
        print("No research targets found.")
        return

    # Limit to max_tickers
    targets = targets[: args.max_tickers]

    if args.dry_run:
        print(json.dumps(targets, indent=2, ensure_ascii=False))
        print(f"\n{len(targets)} target(s) would be researched.")
        return

    from notebooklm_research.research_sync import run_research_batch

    output_dir = Path(args.output_dir)

    # Optional Telegram callback
    on_complete = None
    try:
        from notebooklm_research.telegram_alert import send_research_alert_sync

        on_complete = send_research_alert_sync
    except ImportError:
        pass

    results = asyncio.run(
        run_research_batch(
            targets,
            storage_path=args.notebooklm_storage,
            output_dir=output_dir,
            max_youtube=args.max_youtube,
            deep_research=not args.no_deep_research,
            on_ticker_complete=on_complete,
        )
    )

    # Summary
    ok = [r for r in results if "error" not in r]
    fail = [r for r in results if "error" in r]
    print(f"\nResearch complete: {len(ok)} succeeded, {len(fail)} failed.")
    for r in ok:
        print(f"  {r['ticker']}: {len(r.get('youtube_sources', []))} sources, "
              f"{len(r.get('questions', {}))} questions answered")
    for r in fail:
        print(f"  {r['ticker']}: ERROR - {r['error']}")


if __name__ == "__main__":
    main()
