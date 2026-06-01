#!/usr/bin/env python3
"""Standalone entry point for HedgeFollow insider activity scraping."""

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

from browser.scrapers.hedgefollow_insiders import HedgeFollowInsiderScraper


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Scrape HedgeFollow insider buys and sells.")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in headless mode.",
    )
    args = parser.parse_args(argv)

    with HedgeFollowInsiderScraper(headless=args.headless) as scraper:
        manifest = scraper.run()

    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
