from __future__ import annotations

from pathlib import Path

from browser.base import BrowserAutomation, SCRAPED_DIR
from tools.dashboard_freshness import (
    AASTOCKS_HIGH_URL,
    AASTOCKS_LOW_URL,
    now_hkt_iso,
    parse_aastocks_high_low_pages,
    write_json,
)


class AAStocksScraper(BrowserAutomation):
    SERVICE_NAME = "aastocks"
    USE_CHROME_PROFILE = False

    def __init__(self, **kwargs):
        kwargs.setdefault("slow_mo", 50)
        super().__init__(**kwargs)
        self.output_dir = SCRAPED_DIR / "hk_breadth"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def is_logged_in(self) -> bool:
        return True

    def login(self) -> None:
        return None

    def fetch_html(self, url: str) -> str:
        self.page.goto(url, wait_until="domcontentloaded")
        self.page.wait_for_timeout(2500)
        return self.page.content()

    def capture_latest(self, output_path: Path | None = None) -> dict:
        output = output_path or (self.output_dir / "latest.json")
        captured_at = now_hkt_iso()
        high_html = self.fetch_html(AASTOCKS_HIGH_URL)
        low_html = self.fetch_html(AASTOCKS_LOW_URL)
        payload = parse_aastocks_high_low_pages(
            high_html=high_html,
            low_html=low_html,
            captured_at=captured_at,
        )
        write_json(output, payload)
        return payload
