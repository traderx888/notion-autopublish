"""
Patreon creator token grabber.

Navigates to Patreon's client registration page,
finds the Creator's Access Token, and saves it to .env.
"""

import os
from browser.base import BrowserAutomation
from browser.env_manager import update_env_value


class PatreonTokenGrabber(BrowserAutomation):
    SERVICE_NAME = "patreon"
    CLIENTS_URL = "https://www.patreon.com/portal/registration/register-clients"

    def is_logged_in(self) -> bool:
        self.page.goto(self.CLIENTS_URL, wait_until="networkidle")
        self.page.wait_for_timeout(3000)
        return "/portal/" in self.page.url or "register-clients" in self.page.url

    def login(self):
        self.page.goto("https://www.patreon.com/login", wait_until="networkidle")
        self.page.wait_for_timeout(2000)

        email = os.getenv("PATREON_EMAIL", "")
        password = os.getenv("PATREON_PASSWORD", "")

        if email and password:
            email_input = self.page.locator('input[name="email"]').first
            if email_input.count() > 0:
                email_input.fill(email)
            pwd_input = self.page.locator('input[name="password"]').first
            if pwd_input.count() > 0:
                pwd_input.fill(password)
                submit = self.page.locator('button[type="submit"]').first
                if submit.count() > 0:
                    submit.click()

            self.page.wait_for_timeout(3000)

            # Check for 2FA
            twofa = self.page.locator('input[name="code"]')
            if twofa.count() > 0:
                self.wait_for_user("Enter your Patreon 2FA code in the browser.")
        else:
            self.wait_for_user(
                "Log in to Patreon in the browser.\n"
                "  Tip: Set PATREON_EMAIL and PATREON_PASSWORD in .env for auto-fill."
            )

    def extract_token(self) -> str | None:
        """Extract Creator's Access Token from client registration page."""
        self.page.goto(self.CLIENTS_URL, wait_until="networkidle")
        self.page.wait_for_timeout(3000)

        # Click on existing client if available
        client_links = self.page.locator('a[href*="/portal/registration/register-clients/"]')
        if client_links.count() > 0:
            client_links.first.click()
            self.page.wait_for_timeout(2000)

        # Look for "Creator's Access Token" and extract its value
        token_label = self.page.locator("text=Creator's Access Token").first
        if token_label.count() > 0:
            parent = token_label.locator("..")
            token_el = parent.locator("input, code, span").first
            if token_el.count() > 0:
                tag = token_el.evaluate("el => el.tagName")
                if tag == "INPUT":
                    token = token_el.input_value()
                else:
                    token = token_el.inner_text()
                if token and len(token) > 10:
                    return token.strip()

        return None

    def run(self):
        """Login -> extract token -> save to .env."""
        print(f"\n{'='*50}")
        print(f"  Patreon Token Grabber")
        print(f"{'='*50}\n")

        self.ensure_logged_in()
        token = self.extract_token()

        if token:
            update_env_value("PATREON_ACCESS_TOKEN", token)
            print(f"\n  Patreon token saved: {token[:15]}...")
        else:
            print("\n  Could not extract token automatically.")
            self.wait_for_user(
                "Copy the Creator's Access Token from the browser into .env manually."
            )
