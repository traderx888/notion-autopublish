"""
LuxAlgo trading alerts/signals scraper.

Logs in to LuxAlgo premium dashboard and extracts
trading alerts and signals data.
"""

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from browser.base import BrowserAutomation, SCRAPED_DIR


class LuxAlgoScraper(BrowserAutomation):
    SERVICE_NAME = "luxalgo"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.output_dir = SCRAPED_DIR / "luxalgo"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def is_logged_in(self) -> bool:
        self.page.goto("https://www.luxalgo.com/account/", wait_until="networkidle")
        self.page.wait_for_timeout(3000)
        return "account" in self.page.url and "login" not in self.page.url

    def login(self):
        self.page.goto("https://www.luxalgo.com/account/", wait_until="networkidle")
        self.page.wait_for_timeout(2000)

        email = os.getenv("LUXALGO_EMAIL", "")
        password = os.getenv("LUXALGO_PASSWORD", "")

        if email and password:
            email_input = self.page.locator(
                'input[type="email"], input[name="email"], input[name="username"]'
            ).first
            if email_input.count() > 0:
                email_input.fill(email)

            pwd_input = self.page.locator('input[type="password"]').first
            if pwd_input.count() > 0:
                pwd_input.fill(password)

            submit = self.page.locator(
                'button[type="submit"], input[type="submit"]'
            ).first
            if submit.count() > 0:
                submit.click()

            self.page.wait_for_timeout(3000)
        else:
            self.wait_for_user(
                "Log in to LuxAlgo in the browser.\n"
                "  Tip: Set LUXALGO_EMAIL and LUXALGO_PASSWORD in .env."
            )

    def scrape_alerts(self) -> list[dict]:
        """
        Scrape trading alerts/signals from the dashboard.
        Tries multiple page patterns and extraction strategies.
        """
        # Try known dashboard/signals pages
        candidate_urls = [
            "https://www.luxalgo.com/account/",
            "https://www.luxalgo.com/dashboard/",
            "https://www.luxalgo.com/signals/",
            "https://www.luxalgo.com/alerts/",
        ]

        dashboard_found = False
        for url in candidate_urls:
            self.page.goto(url, wait_until="networkidle")
            self.page.wait_for_timeout(2000)
            # Check if the page exists (not 404)
            if "404" not in self.page.title().lower() and self.page.url == url:
                dashboard_found = True
                break

        if not dashboard_found:
            self.wait_for_user(
                "Navigate to the LuxAlgo alerts/signals page in the browser."
            )

        self.page.wait_for_timeout(2000)
        alerts = []

        # Strategy 1: Table rows
        rows = self.page.locator(
            'table tbody tr, [class*="alert-row"], [class*="signal-item"]'
        )
        for i in range(rows.count()):
            row = rows.nth(i)
            cells = row.locator('td, [class*="cell"]')
            if cells.count() >= 2:
                alert_data = {}
                for j in range(cells.count()):
                    alert_data[f"col_{j}"] = cells.nth(j).inner_text().strip()
                alerts.append(alert_data)

        # Strategy 2: Card-style layout
        if not alerts:
            cards = self.page.locator(
                '[class*="card"], [class*="alert"], [class*="signal"]'
            )
            for i in range(cards.count()):
                card_text = cards.nth(i).inner_text().strip()
                if card_text and len(card_text) > 10:
                    alerts.append({"raw_text": card_text})

        # Strategy 3: Full page text as last resort
        if not alerts:
            print("    Could not find structured alerts. Extracting full page text.")
            main_el = self.page.locator('main, [role="main"], .content').first
            if main_el.count() > 0:
                body_text = main_el.inner_text()
            else:
                body_text = self.page.locator("body").inner_text()
            alerts.append({"raw_text": body_text})

        return alerts

    def run(self, limit: int = 10):
        print(f"\n{'='*50}")
        print(f"  LuxAlgo Scraper")
        print(f"{'='*50}\n")

        self.ensure_logged_in()
        alerts = self.scrape_alerts()
        print(f"  Extracted {len(alerts)} alert entries\n")

        hkt = timezone(timedelta(hours=8))
        output = {
            "source": "luxalgo",
            "scraped_at": datetime.now(hkt).isoformat(),
            "page_url": self.page.url,
            "alerts": alerts,
        }

        date = datetime.now().strftime("%Y-%m-%d")
        filepath = self.output_dir / f"{date}_alerts.json"
        filepath.write_text(
            json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  Saved: {filepath}")
