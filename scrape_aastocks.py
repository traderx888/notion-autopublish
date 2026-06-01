#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from browser.scrapers.aastocks import AAStocksScraper


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape AASTOCKS high/low breadth pages.")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in headless mode.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output path for the normalized HK breadth JSON artifact.",
    )
    args = parser.parse_args()

    with AAStocksScraper(headless=args.headless) as scraper:
        payload = scraper.capture_latest(output_path=args.output)

    metrics = payload["metrics"]
    print(
        "AASTOCKS breadth refreshed:",
        payload["marketDate"],
        f"newHighs={metrics.get('newHighs52w')}",
        f"newLows={metrics.get('newLows52w')}",
        f"ratio={metrics.get('highLowRatio')}",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
