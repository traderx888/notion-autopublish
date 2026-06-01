"""XiaoHongShu (RED) brand publisher using BrowserAutomation.

Posts notes and comments on XiaoHongShu for brand building.
Login via QR code (manual first time, persistent session after).
Content is Traditional Chinese only.
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


class XiaoHongShuPublisher(BrowserAutomation):
    """Post notes and comments on XiaoHongShu."""

    SERVICE_NAME = "xiaohongshu"
    USE_CHROME_PROFILE = False  # QR code login, own session

    def is_logged_in(self) -> bool:
        self.page.goto("https://www.xiaohongshu.com/explore", wait_until="domcontentloaded")
        self.page.wait_for_timeout(3000)
        # Check for logged-in user avatar/profile link
        avatar = self.page.locator(".user-avatar, .side-bar .user, [class*='login-btn']")
        # If login button is present, we're NOT logged in
        login_btn = self.page.locator("[class*='login-btn'], .login-container")
        if login_btn.count() > 0:
            return False
        return avatar.count() > 0

    def login(self):
        self.page.goto("https://www.xiaohongshu.com")
        self.page.wait_for_timeout(2000)
        # Try to trigger login dialog
        login_btn = self.page.locator("[class*='login-btn'], .login-container, button:has-text('Log in')").first
        if login_btn.count() > 0:
            login_btn.click()
            self.page.wait_for_timeout(2000)

        self.wait_for_user(
            "Please scan the QR code to log in to XiaoHongShu, then press Enter."
        )

    def create_post(self, title: str, content: str,
                    hashtags: list[str] | None = None,
                    dry_run: bool = False) -> bool:
        """Create a new XiaoHongShu note (text post)."""
        if dry_run:
            tag_str = " ".join(hashtags or [])
            print(f"  [DRY-RUN] XiaoHongShu post:")
            print(f"  Title: {title}")
            print(f"  Content ({len(content)} chars): {content[:200]}...")
            if tag_str:
                print(f"  Tags: {tag_str}")
            return True

        page = self.page

        # Navigate to creator center
        page.goto("https://creator.xiaohongshu.com/publish/publish", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # Click on "text" tab if available (vs image/video)
        text_tab = page.locator("[class*='text'], button:has-text('Text'), [data-type='text']").first
        if text_tab.count() > 0:
            text_tab.click()
            page.wait_for_timeout(1500)

        # Fill title
        title_input = page.locator(
            "input[placeholder*='title'], "
            "input[placeholder*='Title'], "
            "[class*='title'] input, "
            "[class*='title'] textarea"
        ).first
        if title_input.count() > 0:
            title_input.click()
            title_input.fill(title)
            page.wait_for_timeout(500)

        # Fill content
        content_input = page.locator(
            "[contenteditable='true'], "
            "textarea[placeholder*='content'], "
            "[class*='editor'] [contenteditable], "
            ".ql-editor"
        ).first
        if content_input.count() > 0:
            content_input.click()
            page.wait_for_timeout(500)

            # Add hashtags inline
            full_text = content
            if hashtags:
                full_text += "\n\n" + " ".join(hashtags)

            # Type with human-like speed
            for char in full_text:
                content_input.type(char, delay=random.randint(20, 60))

            page.wait_for_timeout(1000)

        # Click publish
        publish_btn = page.locator(
            "button:has-text('Publish'), "
            "button:has-text('publish'), "
            "[class*='publish'] button, "
            "button[class*='submit']"
        ).first
        if publish_btn.count() > 0:
            publish_btn.click()
            page.wait_for_timeout(5000)
            print(f"  XiaoHongShu post published: {title[:50]}")
            return True

        print(f"  Could not find publish button")
        self.screenshot("xhs_no_publish")
        return False

    def post_comment(self, note_url: str, text: str, dry_run: bool = False) -> bool:
        """Navigate to a XiaoHongShu note and post a comment."""
        if dry_run:
            print(f"  [DRY-RUN] XiaoHongShu comment on {note_url}:")
            print(f"  {text[:200]}...")
            return True

        page = self.page
        page.goto(note_url, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # Find comment input
        comment_input = page.locator(
            "[contenteditable='true'][class*='comment'], "
            "textarea[placeholder*='comment'], "
            "input[placeholder*='comment'], "
            "[class*='comment-input'] [contenteditable], "
            "[class*='comment'] textarea"
        ).first

        if comment_input.count() == 0:
            # Try clicking a "write comment" area first
            comment_area = page.locator(
                "[class*='comment-placeholder'], "
                "[class*='input-box'], "
                "div:has-text('Write a comment')"
            ).first
            if comment_area.count() > 0:
                comment_area.click()
                page.wait_for_timeout(1500)
                comment_input = page.locator("[contenteditable='true']").last

        if comment_input.count() == 0:
            print(f"  Could not find comment input on {note_url}")
            self.screenshot("xhs_no_comment")
            return False

        comment_input.click()
        page.wait_for_timeout(500)

        # Type with human-like delays
        for char in text:
            comment_input.type(char, delay=random.randint(30, 80))

        page.wait_for_timeout(1000)

        # Submit
        submit_btn = page.locator(
            "button:has-text('Send'), "
            "button:has-text('Post'), "
            "[class*='comment'] button[class*='submit'], "
            "button[class*='send']"
        ).first
        if submit_btn.count() > 0:
            submit_btn.click()
            page.wait_for_timeout(3000)
            print(f"  XiaoHongShu comment posted")
            return True

        # Try pressing Enter as fallback
        comment_input.press("Enter")
        page.wait_for_timeout(3000)
        print(f"  XiaoHongShu comment posted (via Enter)")
        return True


def log_activity(action: str, details: dict | None = None):
    """Log XiaoHongShu brand activity."""
    log_dir = PROJECT_ROOT / "outputs" / "brand"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "brand_activity.log"

    entry = {
        "timestamp": datetime.now(HKT).isoformat(),
        "platform": "xiaohongshu",
        "action": action,
        **(details or {}),
    }

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
