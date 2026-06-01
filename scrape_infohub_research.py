"""CLI entry point for the Info Hub research bridge.

Usage:
    # Dry run — print resolved targets + planned profile specs only.
    python scrape_infohub_research.py --from-signals --dry-run

    # Real run, all kinds.
    python scrape_infohub_research.py --from-signals --max-per-kind 5 --days 3

    # Narrow scope.
    python scrape_infohub_research.py --from-signals --only-kinds ticker,macro_keyword

The bridge talks to Info Hub via subprocess, using its bundled venv. Set
``INFOHUB_DIR`` or pass ``--infohub-dir`` to override the auto-discovery
order (env var → sibling repo → C:/Users/User/Documents/Info Hub).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Force UTF-8 stdout on Windows so non-ASCII titles don't crash cp950.
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).parent.resolve()
DEFAULT_SCRAPED = REPO_ROOT / "scraped_data"
DEFAULT_OUTPUTS = REPO_ROOT / "outputs"
DEFAULT_OUTPUT_DIR = DEFAULT_SCRAPED / "infohub"
DEFAULT_FUNDMAN = REPO_ROOT.parent / "fundman-jarvis" / "data"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Info Hub research bridge")
    p.add_argument("--from-signals", action="store_true",
                   help="Auto-collect targets from screening files")
    p.add_argument("--scraped-dir", default=str(DEFAULT_SCRAPED))
    p.add_argument("--outputs-dir", default=str(DEFAULT_OUTPUTS))
    p.add_argument("--fundman-data-dir", default=str(DEFAULT_FUNDMAN),
                   help="Path to fundman-jarvis/data (for SMM signals)")
    p.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR),
                   help="Where to write per-target *_news.json files")
    p.add_argument("--infohub-dir", default=None,
                   help="Override Info Hub install path (else INFOHUB_DIR / sibling / hardcoded)")
    p.add_argument("--max-per-kind", type=int, default=5)
    p.add_argument("--days", type=int, default=3)
    p.add_argument("--max-items-per-source", type=int, default=5)
    p.add_argument("--only-kinds", default=None,
                   help="Comma list: ticker,sector,macro_keyword,event_topic")
    p.add_argument("--dry-run", action="store_true",
                   help="Resolve targets and print profile specs without calling Info Hub")
    p.add_argument("--health-check", action="store_true",
                   help="Probe the Info Hub CLI and exit")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main() -> int:
    args = _parse_args()
    _setup_logging(args.verbose)

    scraped_dir = Path(args.scraped_dir)
    outputs_dir = Path(args.outputs_dir)
    fundman_dir = Path(args.fundman_data_dir)
    output_dir = Path(args.output_dir)
    only_kinds = (
        [k.strip() for k in args.only_kinds.split(",") if k.strip()]
        if args.only_kinds else None
    )

    # Always import lazily so --dry-run can work without an Info Hub install.
    from infohub_research.targets import collect_all_targets, filter_kinds
    from infohub_research.profile_builder import build_profile_spec

    targets = collect_all_targets(
        scraped_dir=scraped_dir,
        fundman_data_dir=fundman_dir if fundman_dir.exists() else None,
        outputs_dir=outputs_dir,
        max_per_kind=args.max_per_kind,
    )
    targets = filter_kinds(targets, only_kinds)

    if not targets:
        print("No screening targets found. Check scraped_data/ + fundman-jarvis/data.")
        return 0

    if args.dry_run:
        preview = []
        for t in targets:
            spec = build_profile_spec(t)
            preview.append({
                "slug": t.slug,
                "kind": t.kind,
                "source": t.source,
                "keywords": t.keywords,
                "profile": {
                    "domain": spec["domain"],
                    "theme": spec["theme"],
                    "focus": spec["focus"],
                    "queries": spec["queries"],
                    "sources": spec["sources"],
                    "priority": spec["priority"],
                },
            })
        print(json.dumps(preview, indent=2, ensure_ascii=False))
        print(f"\n{len(targets)} target(s) would be researched.")
        return 0

    # Real run requires the Info Hub install.
    from infohub_research.bridge import InfoHubClient, InfoHubError
    from infohub_research.research import run_pipeline

    try:
        client = InfoHubClient(infohub_dir=args.infohub_dir)
    except InfoHubError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.health_check:
        ok = client.health_check()
        print(json.dumps({
            "infohub_root": str(client.root),
            "infohub_python": str(client.python),
            "healthy": ok,
        }, indent=2))
        return 0 if ok else 1

    if not client.health_check():
        print("ERROR: Info Hub CLI health check failed", file=sys.stderr)
        return 3

    summary = run_pipeline(
        scraped_dir=scraped_dir,
        fundman_data_dir=fundman_dir if fundman_dir.exists() else None,
        outputs_dir=outputs_dir,
        output_dir=output_dir,
        client=client,
        max_per_kind=args.max_per_kind,
        days=args.days,
        max_items_per_source=args.max_items_per_source,
        only_kinds=only_kinds,
        targets=targets,
    )

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    ok = sum(1 for r in summary.get("results", []) if r.get("total_items", 0) > 0)
    print(
        f"\nDone. {len(summary.get('results', []))} target(s) processed, "
        f"{ok} with items. {len(summary.get('errors', []))} error(s)."
    )
    return 0 if not summary.get("errors") else 1


if __name__ == "__main__":
    raise SystemExit(main())
