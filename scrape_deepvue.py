#!/usr/bin/env python3
"""
DeepVue Dashboard Scraper

Captures screenshots and extracts key data from DeepVue dashboards.

First run (interactive — login required):
    python scrape_deepvue.py

Headless (after session established):
    python scrape_deepvue.py --headless

Specific dashboard:
    python scrape_deepvue.py --dashboard market_overview
    python scrape_deepvue.py --dashboard preopen
    python scrape_deepvue.py --dashboard capscreen
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="Scrape DeepVue dashboards.")
    parser.add_argument(
        "--headless", action="store_true",
        help="Run in headless mode (requires existing session)",
    )
    parser.add_argument(
        "--dashboard", choices=["market_overview", "preopen", "capscreen", "all"],
        default="all",
        help="Which dashboard to capture (default: all)",
    )
    args = parser.parse_args()

    dashboards = None  # means "all"
    if args.dashboard != "all":
        dashboards = [args.dashboard]

    from browser.scrapers.deepvue import DeepVueScraper

    with DeepVueScraper(headless=args.headless) as scraper:
        results = scraper.run(dashboards=dashboards)

        for name, data in results.items():
            print(f"\n{'='*50}")
            print(f"  {name}")
            print(f"{'='*50}")
            if data.get("screenshot"):
                print(f"  Screenshot: {data['screenshot']}")
            if data.get("breadth"):
                print(f"  Breadth: {data['breadth']}")
            if data.get("stages"):
                print(f"  Stages: {data['stages']}")
            if data.get("movers"):
                print(f"  Top movers: {len(data['movers'])}")
                for m in data["movers"][:5]:
                    print(f"    {m}")
            if data.get("tickers"):
                print(f"  Tickers: {len(data['tickers'])}")
                for t in data["tickers"][:10]:
                    print(f"    {t}")

    print("\nDone!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
