"""
Unified CLI entry point for all browser automation.

Usage:
    python -m browser grab notion
    python -m browser grab patreon
    python -m browser scrape substack [--limit 10] [--headless]
    python -m browser scrape seekingalpha
    python -m browser scrape luxalgo
    python -m browser scrape all
"""

import argparse
import sys
from dotenv import load_dotenv

load_dotenv()


def main():
    parser = argparse.ArgumentParser(
        prog="browser",
        description="Browser automation tools for notion-autopublish",
    )
    subparsers = parser.add_subparsers(dest="command")

    # grab command
    grab_parser = subparsers.add_parser("grab", help="Grab API tokens via browser")
    grab_parser.add_argument(
        "service",
        choices=["notion", "patreon"],
        help="Which service token to grab",
    )

    # scrape command
    scrape_parser = subparsers.add_parser("scrape", help="Scrape content via browser")
    scrape_parser.add_argument(
        "service",
        choices=["substack", "seekingalpha", "luxalgo", "all"],
        help="Which service to scrape",
    )
    scrape_parser.add_argument(
        "--limit", type=int, default=10,
        help="Maximum articles to scrape (default: 10)",
    )
    scrape_parser.add_argument(
        "--headless", action="store_true",
        help="Run in headless mode (not recommended)",
    )
    scrape_parser.add_argument(
        "--chrome", action="store_true",
        help="Use your real Chrome profile (keeps existing logins like Google SSO)",
    )

    args = parser.parse_args()

    if args.command == "grab":
        run_grabber(args)
    elif args.command == "scrape":
        run_scraper(args)
    else:
        parser.print_help()
        sys.exit(1)


def run_grabber(args):
    if args.service == "notion":
        from browser.grabbers.notion_token import NotionTokenGrabber
        with NotionTokenGrabber() as grabber:
            grabber.run()
    elif args.service == "patreon":
        from browser.grabbers.patreon_token import PatreonTokenGrabber
        with PatreonTokenGrabber() as grabber:
            grabber.run()


def run_scraper(args):
    services = ["substack", "seekingalpha", "luxalgo"] if args.service == "all" else [args.service]
    headless = getattr(args, "headless", False)
    limit = getattr(args, "limit", 10)
    use_chrome = getattr(args, "chrome", False)

    for service in services:
        if service == "substack":
            from browser.scrapers.substack import SubstackScraper
            with SubstackScraper(headless=headless, use_chrome=use_chrome) as scraper:
                scraper.run(limit=limit)
        elif service == "seekingalpha":
            from browser.scrapers.seekingalpha import SeekingAlphaScraper
            # SA defaults to Chrome profile (Google SSO); --chrome flag is additive
            with SeekingAlphaScraper(headless=headless) as scraper:
                scraper.run(limit=limit)
        elif service == "luxalgo":
            from browser.scrapers.luxalgo import LuxAlgoScraper
            with LuxAlgoScraper(headless=headless, use_chrome=use_chrome) as scraper:
                scraper.run(limit=limit)


if __name__ == "__main__":
    main()
