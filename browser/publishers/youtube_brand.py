"""YouTube brand comment poster using BrowserAutomation.

Posts comments on relevant YouTube videos using persistent Google login.
Includes human-like typing delays and rate limiting.
"""

from __future__ import annotations

import json
import random
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from browser.base import BrowserAutomation

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
HKT = timezone(timedelta(hours=8))


class YouTubeBrandPublisher(BrowserAutomation):
    """Post comments on YouTube videos for brand building."""

    SERVICE_NAME = "youtube_brand"
    USE_CHROME_PROFILE = True  # Google SSO

    def is_logged_in(self) -> bool:
        self.page.goto("https://www.youtube.com", wait_until="domcontentloaded")
        self.page.wait_for_timeout(3000)
        # Logged-in users have an avatar button
        avatar = self.page.locator("button#avatar-btn, img.yt-spec-avatar-shape__button")
        return avatar.count() > 0

    def login(self):
        self.page.goto("https://accounts.google.com/signin")
        self.wait_for_user(
            "Please log in to your Google account in the browser, then press Enter."
        )
        # Navigate to YouTube to verify
        self.page.goto("https://www.youtube.com")
        self.page.wait_for_timeout(3000)

    def post_comment(self, video_url: str, text: str, dry_run: bool = False) -> bool:
        """Navigate to a YouTube video and post a comment."""
        if dry_run:
            print(f"  [DRY-RUN] YouTube comment on {video_url}:")
            print(f"  {text[:200]}...")
            return True

        page = self.page
        page.goto(video_url, wait_until="domcontentloaded")
        page.wait_for_timeout(4000)

        # Dismiss cookie consent if present
        consent_btn = page.locator("button[aria-label*='Accept'], tp-yt-paper-button:has-text('Accept all')")
        if consent_btn.count() > 0:
            consent_btn.first.click()
            page.wait_for_timeout(2000)

        # Scroll down to load comments section
        page.evaluate("window.scrollBy(0, 600)")
        page.wait_for_timeout(3000)

        # Click on the comment input placeholder to activate it
        comment_placeholder = page.locator(
            "#simplebox-placeholder, "
            "ytd-comment-simplebox-renderer #placeholder-area, "
            "[placeholder='Add a comment...']"
        ).first

        if comment_placeholder.count() == 0:
            print(f"  Could not find comment box on {video_url}")
            self.screenshot("yt_no_comment_box")
            return False

        comment_placeholder.click()
        page.wait_for_timeout(2000)

        # Find the active comment input
        comment_input = page.locator(
            "#contenteditable-root, "
            "div#contenteditable-root[contenteditable='true'], "
            "ytd-comment-simplebox-renderer #contenteditable-root"
        ).first

        if comment_input.count() == 0:
            print(f"  Could not find active comment input")
            self.screenshot("yt_no_input")
            return False

        comment_input.click()
        page.wait_for_timeout(500)

        # Type with human-like delays
        for char in text:
            comment_input.type(char, delay=random.randint(30, 90))
            if random.random() < 0.03:
                page.wait_for_timeout(random.randint(300, 800))

        page.wait_for_timeout(1500)

        # Click submit button
        submit_btn = page.locator(
            "#submit-button, "
            "ytd-comment-simplebox-renderer #submit-button, "
            "tp-yt-paper-button#submit-button"
        ).first

        if submit_btn.count() == 0:
            print(f"  Could not find submit button")
            self.screenshot("yt_no_submit")
            return False

        submit_btn.click()
        page.wait_for_timeout(3000)
        print(f"  YouTube comment posted on {video_url}")
        return True

    def post_self_reply(self, video_url: str, original_comment_text: str,
                        reply_text: str, dry_run: bool = False) -> bool:
        """Reply to your own comment on a video (self-reply for added depth)."""
        if dry_run:
            print(f"  [DRY-RUN] YouTube self-reply on {video_url}:")
            print(f"  Original: {original_comment_text[:80]}...")
            print(f"  Reply: {reply_text[:200]}...")
            return True

        page = self.page
        page.goto(video_url, wait_until="domcontentloaded")
        page.wait_for_timeout(4000)

        # Scroll to comments
        page.evaluate("window.scrollBy(0, 600)")
        page.wait_for_timeout(3000)

        # Sort by newest to find our comment
        sort_btn = page.locator("#sort-menu tp-yt-paper-button, button[aria-label*='Sort']").first
        if sort_btn.count() > 0:
            sort_btn.click()
            page.wait_for_timeout(1000)
            newest = page.locator("tp-yt-paper-item:has-text('Newest first'), a:has-text('Newest first')").first
            if newest.count() > 0:
                newest.click()
                page.wait_for_timeout(3000)

        # Find our comment and click reply
        comments = page.locator("ytd-comment-thread-renderer").all()
        for comment_el in comments[:10]:
            content = comment_el.locator("#content-text").first
            if content.count() > 0 and original_comment_text[:50] in (content.inner_text() or ""):
                reply_btn = comment_el.locator(
                    "#reply-button-end button, "
                    "button[aria-label*='Reply']"
                ).first
                if reply_btn.count() > 0:
                    reply_btn.click()
                    page.wait_for_timeout(2000)

                    reply_input = comment_el.locator(
                        "#contenteditable-root[contenteditable='true']"
                    ).first
                    if reply_input.count() > 0:
                        reply_input.click()
                        for char in reply_text:
                            reply_input.type(char, delay=random.randint(30, 90))
                        page.wait_for_timeout(1000)

                        submit = comment_el.locator("#submit-button").first
                        if submit.count() > 0:
                            submit.click()
                            page.wait_for_timeout(3000)
                            print(f"  YouTube self-reply posted")
                            return True

        print(f"  Could not find original comment to reply to")
        return False


def log_activity(action: str, details: dict | None = None):
    """Log YouTube brand activity."""
    log_dir = PROJECT_ROOT / "outputs" / "brand"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "brand_activity.log"

    entry = {
        "timestamp": datetime.now(HKT).isoformat(),
        "platform": "youtube",
        "action": action,
        **(details or {}),
    }

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
