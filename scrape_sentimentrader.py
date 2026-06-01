"""
Standalone entry point for SentimentTrader scraping.

Usage:
    python scrape_sentimentrader.py --explore          # Exploration mode (headed)
    python scrape_sentimentrader.py --explore --record  # + capture API calls
    python scrape_sentimentrader.py                     # Full scrape (incl. research reports)
    python scrape_sentimentrader.py --quick              # Quick scrape (skip research reports)
    python scrape_sentimentrader.py --headless           # Headless mode
"""

import io
import json
import sys

# Fix Windows console encoding for CJK/emoji characters
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

from browser.scrapers.sentimentrader import SentimentTraderScraper, EXPLORE_PAGES


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape SentimentTrader indicators")
    parser.add_argument(
        "--explore", action="store_true",
        help="Exploration mode: screenshot key pages and save HTML for selector mapping",
    )
    parser.add_argument(
        "--record", action="store_true",
        help="Record API/XHR calls during exploration (use with --explore)",
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="Run in headless mode (requires established session)",
    )
    parser.add_argument(
        "--quick", action="store_true",
        help="Quick mode: skip research report scraping (faster for daily runs)",
    )
    args = parser.parse_args()

    # Explore mode is always headed
    headless = args.headless and not args.explore

    with SentimentTraderScraper(headless=headless) as scraper:
        if args.explore:
            manifest = scraper.explore()

            # Optionally record API calls on each page
            if args.record:
                print("\n  Phase 3: Recording API/XHR calls...")
                for page_key, url in EXPLORE_PAGES.items():
                    scraper.record_network(url, page_key)

            print(f"\nExploration complete. Review screenshots in:")
            print(f"  scraped_data/sentimentrader/explore/")
            print(json.dumps(manifest, indent=2, ensure_ascii=False))
        else:
            result = scraper.run(quick=args.quick)
            print(f"\nResult: {json.dumps(result, indent=2, ensure_ascii=False)}")
