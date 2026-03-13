"""
Notion integration token grabber.

Navigates to notion.so/my-integrations, finds or creates an integration,
and extracts the internal token (ntn_...) into .env.
"""

import os
import re
from browser.base import BrowserAutomation
from browser.env_manager import update_env_value


class NotionTokenGrabber(BrowserAutomation):
    SERVICE_NAME = "notion"
    INTEGRATIONS_URL = "https://www.notion.so/my-integrations"

    def is_logged_in(self) -> bool:
        self.page.goto(self.INTEGRATIONS_URL, wait_until="networkidle")
        self.page.wait_for_timeout(3000)
        return "my-integrations" in self.page.url

    def login(self):
        self.page.goto("https://www.notion.so/login", wait_until="networkidle")
        self.page.wait_for_timeout(2000)

        email = os.getenv("NOTION_EMAIL", "")
        if email:
            email_input = self.page.locator('input[type="email"]')
            if email_input.count() > 0:
                email_input.fill(email)
                continue_btn = self.page.locator('text=Continue with email')
                if continue_btn.count() > 0:
                    continue_btn.click()

        self.wait_for_user(
            "Complete Notion login in the browser (email link, Google SSO, or password)."
        )

    def find_or_create_integration(self) -> str | None:
        """Find existing integration or guide user to create one, then extract token."""
        self.page.goto(self.INTEGRATIONS_URL, wait_until="networkidle")
        self.page.wait_for_timeout(3000)

        # Look for existing integration named 'autopublish'
        integration_link = self.page.locator('text=autopublish').first
        if integration_link.count() > 0:
            integration_link.click()
            self.page.wait_for_timeout(2000)
        else:
            new_btn = self.page.locator('text=New integration')
            if new_btn.count() > 0:
                new_btn.click()
                self.wait_for_user(
                    "Create a new integration named 'autopublish', then click Submit."
                )
            else:
                self.wait_for_user(
                    "Navigate to your integration in the browser."
                )

        # Try to reveal and extract the token
        show_btn = self.page.locator('text=Show').first
        if show_btn.count() > 0:
            show_btn.click()
            self.page.wait_for_timeout(1000)

        # Look for ntn_ token in input fields
        token_input = self.page.locator('input[value^="ntn_"]').first
        if token_input.count() > 0:
            return token_input.get_attribute("value")

        # Fallback: search visible text for ntn_ pattern
        all_text = self.page.locator('//*[contains(text(), "ntn_")]').first
        if all_text.count() > 0:
            text = all_text.inner_text()
            match = re.search(r'(ntn_\w+)', text)
            if match:
                return match.group(1)

        return None

    def run(self):
        """Login -> find/create integration -> save token to .env."""
        print(f"\n{'='*50}")
        print(f"  Notion Token Grabber")
        print(f"{'='*50}\n")

        self.ensure_logged_in()
        token = self.find_or_create_integration()

        if token:
            update_env_value("NOTION_TOKEN", token)
            print(f"\n  Notion token saved: {token[:15]}...")
        else:
            print("\n  Could not extract the token automatically.")
            self.wait_for_user(
                "Copy the token from the browser and paste it into .env manually."
            )
