"""XiaoHongShu content discovery -- find relevant notes to comment on.

Uses BrowserAutomation to search XiaoHongShu for finance/tech notes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

from browser.base import BrowserAutomation

HKT = timezone(timedelta(hours=8))


@dataclass
class DiscoveryResult:
    url: str
    title: str
    author: str
    content_snippet: str
    engagement: dict
    relevance_score: float
    platform: str
    discovered_at: str


def _score_relevance(text: str, config: dict) -> float:
    """Score how relevant a note is to brand topics."""
    bk = config.get("brand_keywords", {})
    keywords = (
        bk.get("target_associations_zh", []) +
        bk.get("target_associations_en", []) +
        [t.replace("_", " ") for t in config["topics"]["primary"]]
    )
    text_lower = text.lower()
    matches = sum(1 for kw in keywords if kw.lower() in text_lower)
    return min(matches / 4.0, 1.0)


class XiaoHongShuDiscovery(BrowserAutomation):
    """Discover relevant XiaoHongShu notes via search."""

    SERVICE_NAME = "xiaohongshu"
    USE_CHROME_PROFILE = False

    def is_logged_in(self) -> bool:
        self.page.goto("https://www.xiaohongshu.com/explore", wait_until="domcontentloaded")
        self.page.wait_for_timeout(3000)
        login_btn = self.page.locator("[class*='login-btn'], .login-container")
        return login_btn.count() == 0

    def login(self):
        self.page.goto("https://www.xiaohongshu.com")
        self.wait_for_user("Please scan the QR code to log in, then press Enter.")

    def discover(self, config: dict, limit: int = 10,
                 query: str | None = None) -> list[DiscoveryResult]:
        """Search XiaoHongShu for relevant notes."""
        bk = config.get("brand_keywords", {})
        queries = [query] if query else bk.get("target_associations_zh", [])[:5]

        results = []
        seen_urls = set()
        page = self.page

        for q in queries:
            encoded = q.replace(" ", "%20")
            page.goto(
                f"https://www.xiaohongshu.com/search_result?keyword={encoded}",
                wait_until="domcontentloaded",
            )
            page.wait_for_timeout(3000)

            # Extract note cards
            cards = page.locator("[class*='note-item'], [class*='search-result-card']").all()

            for card in cards[:5]:
                try:
                    link = card.locator("a").first
                    url = link.get_attribute("href") or ""
                    if not url.startswith("http"):
                        url = f"https://www.xiaohongshu.com{url}"
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    title_el = card.locator("[class*='title'], [class*='desc']").first
                    title = title_el.inner_text()[:100] if title_el.count() > 0 else ""

                    author_el = card.locator("[class*='author'], [class*='name']").first
                    author = author_el.inner_text()[:50] if author_el.count() > 0 else "Unknown"

                    score = _score_relevance(title + " " + q, config)
                    if score < 0.2:
                        continue

                    results.append(DiscoveryResult(
                        url=url,
                        title=title,
                        author=author.strip(),
                        content_snippet=title,
                        engagement={},
                        relevance_score=round(score, 2),
                        platform="xiaohongshu",
                        discovered_at=datetime.now(HKT).isoformat(),
                    ))
                except Exception:
                    continue

            if len(results) >= limit:
                break

        results.sort(key=lambda r: r.relevance_score, reverse=True)
        return results[:limit]
