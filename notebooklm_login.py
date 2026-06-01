"""Workaround login script for notebooklm-py.

The official `notebooklm login` crashes on Windows due to a navigation
race condition in Playwright when Google redirects accounts.google.com.

This script does the same thing but avoids the problematic navigation:
1. Opens a browser to notebooklm.google.com
2. Waits for you to log in
3. Saves storage_state.json to ~/.notebooklm/

Usage:
    python notebooklm_login.py
    python notebooklm_login.py --browser msedge
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

NOTEBOOKLM_URL = "https://notebooklm.google.com/"
STORAGE_DIR = Path.home() / ".notebooklm"
STORAGE_PATH = STORAGE_DIR / "storage_state.json"
BROWSER_PROFILE = STORAGE_DIR / "browser_profile"


def main():
    parser = argparse.ArgumentParser(description="Login to NotebookLM (workaround)")
    parser.add_argument("--browser", default="chromium", choices=["chromium", "msedge", "chrome"],
                        help="Browser to use (default: chromium)")
    args = parser.parse_args()

    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    BROWSER_PROFILE.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright

    print("Opening browser for Google login...")
    print(f"Using profile: {BROWSER_PROFILE}")
    print()

    with sync_playwright() as p:
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--password-store=basic",
        ]

        browser_type = p.chromium
        channel = None
        if args.browser == "msedge":
            channel = "msedge"
        elif args.browser == "chrome":
            channel = "chrome"

        context = browser_type.launch_persistent_context(
            user_data_dir=str(BROWSER_PROFILE),
            headless=False,
            channel=channel,
            args=launch_args,
            ignore_default_args=["--enable-automation"],
        )

        page = context.pages[0] if context.pages else context.new_page()

        # Navigate directly to NotebookLM (Google will redirect to login if needed)
        page.goto(NOTEBOOKLM_URL, wait_until="domcontentloaded")

        print("Instructions:")
        print("  1. Log in to your Google account in the browser window")
        print("  2. Wait until you see the NotebookLM homepage")
        print("  3. Press ENTER here to save and close")
        print()
        input("[Press ENTER when logged in] ")

        # Verify we're on NotebookLM
        current_url = page.url
        if "notebooklm.google.com" not in current_url:
            print(f"Warning: Current URL is {current_url}")
            print("You may not be fully logged in.")
            answer = input("Save anyway? (y/n): ").strip().lower()
            if answer != "y":
                context.close()
                sys.exit(1)

        # Save storage state (cookies + localStorage)
        context.storage_state(path=str(STORAGE_PATH))
        context.close()

    print(f"\nAuth saved to: {STORAGE_PATH}")
    print("You can now run: python scrape_notebooklm_research.py --tickers NVDA --max-youtube 1")


if __name__ == "__main__":
    main()
