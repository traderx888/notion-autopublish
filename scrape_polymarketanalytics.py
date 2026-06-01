#!/usr/bin/env python3
"""Standalone entry point for Polymarket Analytics public scraping."""

from __future__ import annotations

import io
import json
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
        except Exception:
            pass

from browser.scrapers.polymarketanalytics import PolymarketAnalyticsScraper
from browser.scrapers.polymarketanalytics import DEFAULT_ACTIVITY_PAGE_SIZE, DEFAULT_ACTIVITY_PAGES


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Scrape Polymarket Analytics traders and activity.")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode.")
    parser.add_argument("--force-leaderboard", action="store_true", help="Force a fresh leaderboard fetch.")
    parser.add_argument(
        "--activity-pages",
        type=int,
        default=DEFAULT_ACTIVITY_PAGES,
        help="How many activity pages to fetch.",
    )
    parser.add_argument(
        "--activity-page-size",
        type=int,
        default=DEFAULT_ACTIVITY_PAGE_SIZE,
        help="Rows per activity page.",
    )
    args = parser.parse_args(argv)

    with PolymarketAnalyticsScraper(headless=args.headless) as scraper:
        manifest = scraper.run(
            force_leaderboard=args.force_leaderboard,
            activity_pages=args.activity_pages,
            activity_page_size=args.activity_page_size,
        )

    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
