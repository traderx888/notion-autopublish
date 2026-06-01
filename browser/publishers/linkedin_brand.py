"""LinkedIn brand publisher -- API for original posts, browser for comments.

Original posts reuse the existing publish_linkedin() from publish.py.
Comments use BrowserAutomation to navigate to post URLs and post comments.
"""

from __future__ import annotations

import json
import os
import random
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
HKT = timezone(timedelta(hours=8))


def publish_post(text: str, dry_run: bool = False) -> bool:
    """Publish an original LinkedIn post via API."""
    if dry_run:
        print(f"  [DRY-RUN] LinkedIn post ({len(text)} chars):")
        print(f"  {text[:300]}...")
        return True

    from publish import publish_linkedin
    publish_linkedin(text)
    return True


class LinkedInCommenter:
    """Browser-based LinkedIn comment poster using BrowserAutomation."""

    def __init__(self, headless: bool = False):
        from browser.base import BrowserAutomation

        class _LinkedInBrowser(BrowserAutomation):
            SERVICE_NAME = "linkedin_brand"
            USE_CHROME_PROFILE = True

            def is_logged_in(self) -> bool:
                self.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
                self.page.wait_for_timeout(3000)
                # Check for feed presence (logged in) vs login form
                return self.page.locator(".feed-shared-update-v2").count() > 0

            def login(self):
                self.page.goto("https://www.linkedin.com/login")
                self.wait_for_user(
                    "Please log in to LinkedIn in the browser, then press Enter."
                )

        self._browser = _LinkedInBrowser(headless=headless)

    def __enter__(self):
        self._browser.start()
        self._browser.ensure_logged_in()
        return self

    def __exit__(self, *args):
        self._browser.__exit__(*args)

    def post_comment(self, post_url: str, text: str, dry_run: bool = False) -> bool:
        """Navigate to a LinkedIn post and leave a comment."""
        if dry_run:
            print(f"  [DRY-RUN] LinkedIn comment on {post_url}:")
            print(f"  {text[:200]}...")
            return True

        page = self._browser.page
        page.goto(post_url, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # Click the comment button to open comment box
        comment_btn = page.locator("button.comment-button, [aria-label*='Comment']").first
        if comment_btn.count() == 0:
            print(f"  Could not find comment button on {post_url}")
            self._browser.screenshot("linkedin_no_comment_btn")
            return False

        comment_btn.click()
        page.wait_for_timeout(1500)

        # Find and fill the comment input
        comment_box = page.locator(
            ".ql-editor[data-placeholder], "
            "[role='textbox'][aria-label*='comment'], "
            ".comments-comment-texteditor .ql-editor"
        ).first

        if comment_box.count() == 0:
            print(f"  Could not find comment input on {post_url}")
            self._browser.screenshot("linkedin_no_comment_input")
            return False

        # Type with human-like delays
        comment_box.click()
        page.wait_for_timeout(500)
        for char in text:
            comment_box.type(char, delay=random.randint(30, 80))
            if random.random() < 0.05:
                page.wait_for_timeout(random.randint(200, 500))

        page.wait_for_timeout(1000)

        # Submit
        submit_btn = page.locator(
            "button.comments-comment-box__submit-button, "
            "button[aria-label*='Post comment']"
        ).first
        if submit_btn.count() == 0:
            print(f"  Could not find submit button")
            self._browser.screenshot("linkedin_no_submit")
            return False

        submit_btn.click()
        page.wait_for_timeout(3000)
        print(f"  LinkedIn comment posted on {post_url}")
        return True


def log_activity(action: str, details: dict | None = None):
    """Log LinkedIn brand activity."""
    log_dir = PROJECT_ROOT / "outputs" / "brand"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "brand_activity.log"

    entry = {
        "timestamp": datetime.now(HKT).isoformat(),
        "platform": "linkedin",
        "action": action,
        **(details or {}),
    }

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
