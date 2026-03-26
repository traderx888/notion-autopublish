"""
CLI: trigger fundamental research via NotebookLM for a given stock/sector signal.

Usage examples:
  # Manual one-shot:
  python scrape_fundamental_research.py \
      --ticker NVDA --sector semiconductors \
      --trigger-source DEEPVUE --trigger-signal momentum_breakout \
      --notebook-id <NLM_NOTEBOOK_ID> \
      --youtube https://www.youtube.com/watch?v=abc \
      --youtube https://www.youtube.com/watch?v=def

  # From a signal JSON file (for automated triggers from SMM/DeepVue):
  python scrape_fundamental_research.py --signal-file path/to/signal.json --notebook-id <ID>

Output: scraped_data/notebooklm/{ticker_lower}_fundamental.md
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from ciovacco.notebooklm_sync import canonicalize_source_url
from fundamental_research.notebooklm_research import (
    resolve_research_config,
    sync_fundamental_research,
)

OUTPUT_DIR = Path("scraped_data/notebooklm")


def load_signal_from_file(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    data["ticker"] = data.get("ticker", "").upper()
    data["youtube_urls"] = [canonicalize_source_url(u) for u in data.get("youtube_urls", [])]
    return data


def build_signal_from_args(
    *,
    ticker: str,
    sector: str,
    trigger_source: str,
    trigger_signal: str,
    youtube_urls: list[str],
) -> dict:
    return {
        "ticker": ticker.upper(),
        "sector": sector,
        "trigger_source": trigger_source,
        "trigger_signal": trigger_signal,
        "youtube_urls": [canonicalize_source_url(u) for u in youtube_urls],
    }


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run fundamental research via NotebookLM")
    p.add_argument("--signal-file", help="Path to JSON signal file (alternative to manual flags)")
    p.add_argument("--ticker", help="Stock ticker, e.g. NVDA")
    p.add_argument("--sector", default="", help="Sector label, e.g. semiconductors")
    p.add_argument("--trigger-source", default="MANUAL", help="e.g. SMM_GOLDEN_EP, DEEPVUE, MANUAL")
    p.add_argument("--trigger-signal", default="ad_hoc", help="Signal description")
    p.add_argument("--youtube", dest="youtube_urls", action="append", default=[],
                   metavar="URL", help="YouTube URL to add (repeat for multiple)")
    p.add_argument("--notebook-id", help="NotebookLM notebook ID (or set FUNDAMENTAL_NOTEBOOKLM_NOTEBOOK_ID_{TICKER})")
    p.add_argument("--notebooklm-storage", help="Path to notebooklm auth storage_state.json")
    return p.parse_args()


async def _main():
    args = _parse_args()

    if args.signal_file:
        signal = load_signal_from_file(args.signal_file)
    elif args.ticker:
        signal = build_signal_from_args(
            ticker=args.ticker,
            sector=args.sector,
            trigger_source=args.trigger_source,
            trigger_signal=args.trigger_signal,
            youtube_urls=args.youtube_urls,
        )
    else:
        print("ERROR: Provide --ticker or --signal-file.", file=sys.stderr)
        sys.exit(1)

    env = dict(os.environ)
    cfg = resolve_research_config(
        notebook_id=args.notebook_id,
        storage_path=args.notebooklm_storage,
        env=env,
        ticker=signal["ticker"],
    )

    print(f"[fundamental-research] Syncing {signal['ticker']} ({signal['sector']}) "
          f"triggered by {signal['trigger_source']}: {signal['trigger_signal']}")
    print(f"[fundamental-research] YouTube sources: {signal['youtube_urls']}")

    result = await sync_fundamental_research(
        signal,
        notebook_id=cfg["notebook_id"],
        storage_path=cfg["storage_path"],
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"{signal['ticker'].lower()}_fundamental.md"
    out_path.write_text(result["rendered_md"], encoding="utf-8")
    print(f"[fundamental-research] Saved → {out_path}")

    if result.get("sources_added"):
        print(f"[fundamental-research] New sources added: {result['sources_added']}")
    else:
        print("[fundamental-research] No new sources (all URLs already in notebook)")

    return result


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(_main())
