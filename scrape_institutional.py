"""
Standalone entry point for institutional insights scraping.

Usage:
    python scrape_institutional.py                           # All 3 sites
    python scrape_institutional.py --site goldmansachs       # Just GS
    python scrape_institutional.py --site morganstanley --limit 3
    python scrape_institutional.py --headless                # Stealth headless
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

from browser.scrapers.institutional import InstitutionalInsightsScraper, INSTITUTIONAL_SITES


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape institutional research insights")
    parser.add_argument(
        "--site", action="append",
        choices=list(INSTITUTIONAL_SITES.keys()),
        help="Specific site(s) to scrape (default: all)",
    )
    parser.add_argument(
        "--limit", type=int, default=5,
        help="Maximum articles per site (default: 5)",
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="Run in stealth headless mode (falls back to headed if blocked)",
    )
    args = parser.parse_args()

    site_keys = args.site or None

    with InstitutionalInsightsScraper(headless=args.headless) as scraper:
        manifest = scraper.run(site_keys=site_keys, limit=args.limit)

    print(f"\nResult: {json.dumps(manifest, indent=2, ensure_ascii=False)}")
