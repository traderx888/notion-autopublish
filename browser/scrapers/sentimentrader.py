"""
SentimentTrader scraper.

Scrapes sentiment indicators from the subscriber dashboard at
users.sentimentrader.com — Smart/Dumb Money Confidence, Short-Term &
Intermediate-Term indicators, Sector Trend Scores, Correlated Indicators,
Highlighted Indicators, and Risk Summary charts.

All data lives on the main dashboard page (/users/).

Requires an active subscription. First run opens a headed browser
for manual login; session persists for subsequent headless runs.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from browser.base import BrowserAutomation, SCRAPED_DIR

OUTPUT_DIR = SCRAPED_DIR / "sentimentrader"
EXPLORE_DIR = OUTPUT_DIR / "explore"

BASE_URL = "https://users.sentimentrader.com"
DASHBOARD_URL = f"{BASE_URL}/users/"
CSV_URL = f"{BASE_URL}/users/get_barchart_data/all"

# Pages to explore during --explore mode.
EXPLORE_PAGES = {
    "dashboard": DASHBOARD_URL,
    "smart_dumb_money": f"{BASE_URL}/users/data/indicator/smart-money-dumb-money-confidence",
    "macro_model": f"{BASE_URL}/users/data/indicator/bear-market-probability-model",
    "breadth": f"{BASE_URL}/users/data/indicator/breadth-indicators",
    "trend": f"{BASE_URL}/users/data/indicator/trend-score",
    "optix_spy": f"{BASE_URL}/users/data/indicator/optix/SPY",
}

# Risk summary chart keys (CDN image-based)
RISK_CHARTS = [
    "model_risk_stocks_short",
    "model_risk_stocks_medium",
    "model_risk_bonds",
    "model_risk_oil",
    "model_risk_gold",
    "model_risk_ag",
]


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _safe_float(text: str) -> Optional[float]:
    """Parse a float from text, returning None on failure."""
    try:
        return float(text.strip())
    except (ValueError, AttributeError):
        return None


class SentimentTraderScraper(BrowserAutomation):
    """Scraper for SentimentTrader subscriber portal."""

    SERVICE_NAME = "sentimentrader"
    USE_CHROME_PROFILE = False

    def __init__(self, headless: bool = False, slow_mo: int = 150):
        super().__init__(headless=headless, slow_mo=slow_mo)

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def is_logged_in(self) -> bool:
        """Check if already logged in by visiting the dashboard."""
        try:
            self.page.goto(DASHBOARD_URL, wait_until="domcontentloaded", timeout=20000)
            self.page.wait_for_timeout(3000)
            url = self.page.url.lower()
            if "login" in url or "sign-in" in url or "signin" in url:
                return False
            body = self.page.inner_text("body").lower()
            if "log in" in body[:500] and "log out" not in body[:500]:
                return False
            return True
        except Exception:
            return False

    def login(self):
        """Navigate to login page and wait for manual credential entry."""
        self.page.goto(DASHBOARD_URL, wait_until="domcontentloaded", timeout=20000)
        self.page.wait_for_timeout(2000)
        self.wait_for_user(
            "Please log in to SentimentTrader in the browser window.\n"
            "  Complete any 2FA if prompted, then press Enter here."
        )
        if not self.is_logged_in():
            print("  WARNING: Login may not have succeeded. Continuing anyway...")

    # ------------------------------------------------------------------
    # Full scrape — extract all data from dashboard
    # ------------------------------------------------------------------

    def run(self, quick: bool = False) -> Dict[str, Any]:
        """
        Scrape all sentiment data from the dashboard page.

        Args:
            quick: If True, skip research reports (faster for daily runs).

        Returns structured data dict and saves to disk.
        """
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.ensure_logged_in()

        # Navigate to dashboard (may already be there from login check)
        if "users.sentimentrader.com/users" not in self.page.url:
            self.page.goto(DASHBOARD_URL, wait_until="domcontentloaded", timeout=30000)
            self.page.wait_for_timeout(4000)

        # Scroll to load lazy content
        for _ in range(5):
            self.page.evaluate("window.scrollBy(0, window.innerHeight)")
            self.page.wait_for_timeout(1000)
        self.page.evaluate("window.scrollTo(0, 0)")
        self.page.wait_for_timeout(500)

        print("\n  Extracting dashboard data...")

        result = {
            "scraped_at": _now_iso(),
            "data_as_of": self._extract_data_date(),
        }

        # 1. Smart Money / Dumb Money Confidence
        sm, dm = self._extract_smart_dumb_money()
        result["smart_money_confidence"] = sm
        result["dumb_money_confidence"] = dm
        print(f"    Smart Money: {sm}, Dumb Money: {dm}")

        # 2. Short-Term Indicators
        result["short_term"] = self._extract_short_term_indicators()
        print(f"    Short-Term: {result['short_term']}")

        # 3. Intermediate-Term Indicators
        result["intermediate_term"] = self._extract_intermediate_term_indicators()
        print(f"    Intermediate-Term: {result['intermediate_term']}")

        # 4. S&P 500 Sector Trend Scores
        result["sector_trend_scores"] = self._extract_sector_trend_scores()
        print(f"    Sector Trend Scores: {len(result['sector_trend_scores'])} sectors")

        # 5. Most Correlated Indicators
        result["correlated_indicators"] = self._extract_correlated_indicators()
        print(f"    Correlated Indicators: {len(result['correlated_indicators'])} entries")

        # 6. Highlighted Indicators
        result["highlighted_indicators"] = self._extract_highlighted_indicators()
        print(f"    Highlighted Indicators: {len(result['highlighted_indicators'])} entries")

        # 7. Risk Summary chart URLs
        result["risk_chart_urls"] = self._extract_risk_chart_urls()
        print(f"    Risk Charts: {len(result['risk_chart_urls'])} charts")

        # 8. Latest commentary headlines
        result["latest_commentary"] = self._extract_commentary()
        print(f"    Commentary: {len(result['latest_commentary'])} articles")

        # 9. Active Studies (summary + individual studies from dashboard tab)
        result["active_studies"] = self._extract_active_studies()
        summary = result["active_studies"].get("summary", {})
        studies = result["active_studies"].get("studies", [])
        print(f"    Active Studies: {summary} ({len(studies)} individual)")

        # 10. Phase Table (sentiment regime per asset)
        result["phase_table"] = self._extract_phase_table()
        total_assets = sum(len(v) for v in result["phase_table"].values())
        print(f"    Phase Table: {total_assets} assets across 4 phases")

        # 11. Download CSV data
        csv_data = self._download_csv()
        if csv_data:
            csv_path = OUTPUT_DIR / "indicator_summary.csv"
            csv_path.write_text(csv_data, encoding="utf-8")
            result["csv_path"] = str(csv_path)
            print(f"    CSV: {csv_path} ({len(csv_data)} chars)")

        # 12. Research reports (skip in quick mode)
        if not quick:
            result["research_reports"] = self._extract_research_reports()
            total_articles = sum(
                len(arts) for arts in result["research_reports"].values()
            )
            print(f"    Research Reports: {total_articles} articles")
        else:
            print("    Research Reports: skipped (--quick)")

        # Save JSON output
        json_path = OUTPUT_DIR / "sentimentrader_latest.json"
        json_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n  Output: {json_path}")

        # Save text summary
        self._save_text_summary(result)

        # Save dashboard screenshot
        self.page.evaluate("window.scrollTo(0, 0)")
        ss_path = OUTPUT_DIR / "dashboard_latest.png"
        self.page.screenshot(path=str(ss_path), full_page=True)
        print(f"  Screenshot: {ss_path}")

        return result

    # ------------------------------------------------------------------
    # Data extraction methods
    # ------------------------------------------------------------------

    def _extract_data_date(self) -> str:
        """Extract the 'Data current as of' date."""
        try:
            text = self.page.inner_text("body")
            m = re.search(r"Data current as of\s+(.+?)(?:\s*<|\n)", text)
            if m:
                return m.group(1).strip()
            # Fallback: look in HTML
            html = self.page.content()
            m = re.search(r"Data current as of\s*(.+?)</", html)
            if m:
                return m.group(1).strip()
        except Exception:
            pass
        return ""

    def _extract_smart_dumb_money(self) -> tuple:
        """Extract Smart Money and Dumb Money confidence values from JS vars."""
        try:
            sm = self.page.evaluate("typeof smart_last !== 'undefined' ? smart_last : null")
            dm = self.page.evaluate("typeof dumb_last !== 'undefined' ? dumb_last : null")
            if sm is not None and dm is not None:
                return round(float(sm), 2), round(float(dm), 2)
        except Exception:
            pass

        # Fallback: parse from page text
        try:
            text = self.page.inner_text("body")
            sm_match = re.search(r"Smart Money\s*\(Last\s*=\s*([\d.]+)\)", text)
            dm_match = re.search(r"Dumb Money\s*\(Last\s*=\s*([\d.]+)\)", text)
            sm = float(sm_match.group(1)) if sm_match else None
            dm = float(dm_match.group(1)) if dm_match else None
            return sm, dm
        except Exception:
            return None, None

    def _extract_short_term_indicators(self) -> Dict[str, Optional[float]]:
        """Extract Short-Term indicator values from SVG text elements."""
        indicators = {}
        names = ["Optix", "Volatility", "Options", "Oscillator", "TICK"]
        try:
            svg = self.page.locator("svg.short_indicators")
            if svg.count() > 0:
                texts = svg.locator("text.values").all_text_contents()
                # SVG has: [name1, name2, ..., value1, value2, ...]
                # Names come first, then values
                n = len(names)
                if len(texts) >= n * 2:
                    for i, name in enumerate(names):
                        val = _safe_float(texts[n + i])
                        indicators[name.lower()] = val
                    return indicators
        except Exception:
            pass

        # Fallback: regex on page text
        try:
            text = self.page.inner_text("body")
            section = re.search(
                r"Short-Term Indicators\s*(.*?)Intermediate-Term Indicators",
                text, re.DOTALL,
            )
            if section:
                chunk = section.group(1)
                for name in names:
                    m = re.search(rf"{name}\s+(\d+)", chunk)
                    if m:
                        indicators[name.lower()] = float(m.group(1))
        except Exception:
            pass
        return indicators

    def _extract_intermediate_term_indicators(self) -> Dict[str, Optional[float]]:
        """Extract Intermediate-Term indicator values from SVG text elements."""
        indicators = {}
        names = ["Optix", "Volatility", "Options", "Breadth", "Surveys",
                 "COT", "Hedging", "Cash", "Insiders", "Rydex"]
        try:
            svg = self.page.locator("svg.int_indicators")
            if svg.count() > 0:
                texts = svg.locator("text.values").all_text_contents()
                n = len(names)
                if len(texts) >= n * 2:
                    for i, name in enumerate(names):
                        val = _safe_float(texts[n + i])
                        indicators[name.lower()] = val
                    return indicators
        except Exception:
            pass

        # Fallback: regex
        try:
            text = self.page.inner_text("body")
            section = re.search(
                r"Intermediate-Term Indicators\s*(.*?)(?:Highlighted Indicators|$)",
                text, re.DOTALL,
            )
            if section:
                chunk = section.group(1)
                for name in names:
                    m = re.search(rf"{name}\s+(\d+)", chunk)
                    if m:
                        indicators[name.lower()] = float(m.group(1))
        except Exception:
            pass
        return indicators

    def _extract_sector_trend_scores(self) -> Dict[str, float]:
        """Extract sector trend scores from the dashboard table."""
        scores = {}
        try:
            table = self.page.locator("#dashboard_sector_list")
            if table.count() == 0:
                return scores
            rows = table.locator("tbody tr")
            for i in range(rows.count()):
                row = rows.nth(i)
                cells = row.locator("td")
                if cells.count() >= 2:
                    # Sector name is in an <a> tag inside the first cell
                    name = cells.nth(0).inner_text().strip()
                    val = _safe_float(cells.nth(1).inner_text())
                    if name and val is not None:
                        scores[name] = val
        except Exception as e:
            print(f"    Error extracting sector trend scores: {e}")
        return scores

    def _extract_correlated_indicators(self) -> List[Dict]:
        """Extract S&P 500 Most Correlated Indicators table."""
        indicators = []
        try:
            table = self.page.locator("#sp_last_3m")
            if table.count() == 0:
                return indicators
            rows = table.locator("tbody tr")
            for i in range(rows.count()):
                row = rows.nth(i)
                cells = row.locator("td")
                if cells.count() >= 3:
                    name = cells.nth(0).inner_text().strip()
                    value = _safe_float(cells.nth(1).inner_text())
                    correlation = _safe_float(cells.nth(2).inner_text())
                    indicators.append({
                        "name": name,
                        "value": value,
                        "correlation": correlation,
                    })
        except Exception as e:
            print(f"    Error extracting correlated indicators: {e}")
        return indicators

    def _extract_highlighted_indicators(self) -> List[Dict]:
        """Extract Highlighted Indicators table."""
        indicators = []
        try:
            table = self.page.locator("#recent_indicators_table")
            if table.count() == 0:
                return indicators
            rows = table.locator("tbody tr")
            for i in range(rows.count()):
                row = rows.nth(i)
                cells = row.locator("td")
                if cells.count() >= 4:
                    indicators.append({
                        "date": cells.nth(0).inner_text().strip(),
                        "research": cells.nth(1).inner_text().strip(),
                        "indicator": cells.nth(2).inner_text().strip(),
                        "last_value": _safe_float(cells.nth(3).inner_text()),
                    })
        except Exception as e:
            print(f"    Error extracting highlighted indicators: {e}")
        return indicators

    def _extract_risk_chart_urls(self) -> Dict[str, str]:
        """Extract Risk Summary chart image URLs from CDN."""
        charts = {}
        labels = {
            "model_risk_stocks_short": "stocks_short_term",
            "model_risk_stocks_medium": "stocks_medium_term",
            "model_risk_bonds": "bonds",
            "model_risk_oil": "crude_oil",
            "model_risk_gold": "gold",
            "model_risk_ag": "agriculture",
        }
        try:
            for chart_key, label in labels.items():
                img = self.page.locator(f'a[href*="{chart_key}"] img')
                if img.count() > 0:
                    src = img.first.get_attribute("src")
                    if src:
                        charts[label] = src
        except Exception as e:
            print(f"    Error extracting risk charts: {e}")
        return charts

    def _extract_commentary(self) -> List[Dict]:
        """Extract latest commentary headlines from the dashboard."""
        articles = []
        try:
            text = self.page.inner_text("body")
            # Commentary section: title + "Published: DATE" + summary
            pattern = re.compile(
                r"(.+?)\nPublished:\s*(\d{4}-\d{2}-\d{2}[^\n]*)\n\n\n(.+?)(?=\n.+?\nPublished:|\nSMART MONEY)",
                re.DOTALL,
            )
            # Find the commentary section
            start = text.find("Latest Commentary")
            if start < 0:
                return articles
            chunk = text[start:start + 5000]
            for m in pattern.finditer(chunk):
                title = m.group(1).strip()
                date = m.group(2).strip()
                summary = m.group(3).strip()
                if title and title != "Latest Commentary":
                    articles.append({
                        "title": title,
                        "date": date,
                        "summary": summary[:500],
                    })
        except Exception as e:
            print(f"    Error extracting commentary: {e}")
        return articles

    def _extract_active_studies(self) -> Dict[str, Any]:
        """Extract Active Studies summary and individual studies from dashboard tab."""
        result: Dict[str, Any] = {"summary": {}, "studies": []}

        try:
            # Click the Active Studies tab to make it visible
            tab_link = self.page.locator('a[href="#tab_active_studies"]')
            if tab_link.count() > 0:
                tab_link.first.click()
                self.page.wait_for_timeout(2000)

            # Extract summary table (Short/Medium/Long-Term × Bullish/Bearish)
            summary_table = self.page.locator("#tab_active_studies table.tg")
            if summary_table.count() > 0:
                rows = summary_table.locator("tbody tr")
                for i in range(rows.count()):
                    cells = rows.nth(i).locator("td")
                    if cells.count() >= 3:
                        timeframe = cells.nth(0).inner_text().strip().lower().replace("-", "_").replace(" ", "_")
                        bullish = _safe_float(cells.nth(1).inner_text())
                        bearish = _safe_float(cells.nth(2).inner_text())
                        if timeframe and bullish is not None:
                            result["summary"][timeframe] = {
                                "bullish": int(bullish),
                                "bearish": int(bearish) if bearish is not None else 0,
                            }

            # Extract individual studies from DataTable #example
            studies_table = self.page.locator("#tab_active_studies table#example")
            if studies_table.count() > 0:
                rows = studies_table.locator("tbody tr")
                for i in range(rows.count()):
                    row = rows.nth(i)
                    cells = row.locator("td")
                    if cells.count() >= 5:
                        # Forecast: check for up/down arrow icon classes
                        forecast_cell = cells.nth(3)
                        forecast_html = forecast_cell.inner_html()
                        if "fa-arrow-up" in forecast_html:
                            forecast = "bullish"
                        elif "fa-arrow-down" in forecast_html:
                            forecast = "bearish"
                        elif "fa-minus" in forecast_html:
                            forecast = "flat"
                        else:
                            forecast = forecast_cell.inner_text().strip()

                        result["studies"].append({
                            "date": cells.nth(0).inner_text().strip(),
                            "title": cells.nth(1).inner_text().strip(),
                            "market": cells.nth(2).inner_text().strip(),
                            "forecast": forecast,
                            "timeframe": cells.nth(4).inner_text().strip(),
                        })

        except Exception as e:
            print(f"    Error extracting active studies: {e}")

        return result

    def _extract_phase_table(self) -> Dict[str, List[Dict]]:
        """Extract Phase Table — sentiment regime per asset from dashboard tab."""
        phases: Dict[str, List[Dict]] = {
            "phase_1": [],  # Extremely Low Optimism
            "phase_2": [],  # Low but Rising
            "phase_3": [],  # High but Declining
            "phase_4": [],  # Extremely High Optimism
        }
        phase_keys = list(phases.keys())

        try:
            # Click Phase Table tab
            tab_link = self.page.locator('a[href="#phase_table_tab"]')
            if tab_link.count() > 0:
                tab_link.first.click()
                self.page.wait_for_timeout(2000)

            # Each phase is in a div.col-sm-3 inside #phase-table
            columns = self.page.locator("#phase-table .col-sm-3")
            for col_idx in range(min(columns.count(), 4)):
                col = columns.nth(col_idx)
                key = phase_keys[col_idx]
                rows = col.locator("table tbody tr")
                for i in range(rows.count()):
                    row = rows.nth(i)
                    cells = row.locator("td")
                    if cells.count() >= 2:
                        market = cells.nth(0).inner_text().strip()
                        optix = _safe_float(cells.nth(1).inner_text())
                        if market and market != "\xa0" and optix is not None:
                            phases[key].append({
                                "market": market,
                                "optix": optix,
                            })

        except Exception as e:
            print(f"    Error extracting phase table: {e}")

        return phases

    def _extract_research_reports(self, limit: int = 3) -> Dict[str, List[Dict]]:
        """
        Navigate to each research section and extract latest articles.
        Returns dict keyed by section name with article lists.
        """
        sections = {
            "sentimentedge": f"{BASE_URL}/users/sentimentedge/",
            "modeledge": f"{BASE_URL}/users/modeledge/",
            "kaeppelscorner": f"{BASE_URL}/users/kaeppelscorner/",
            "weekly": f"{BASE_URL}/users/weekly/",
        }
        all_reports: Dict[str, List[Dict]] = {}

        for section_key, listing_url in sections.items():
            articles: List[Dict] = []
            try:
                print(f"    [{section_key}] Navigating to listing...")
                self.page.goto(listing_url, wait_until="domcontentloaded", timeout=30000)
                self.page.wait_for_timeout(3000)

                # Find article links — typically <a> tags with /blog/ or article titles
                # Common patterns: .post-title a, h2 a, .entry-title a, article a
                link_selectors = [
                    "a[href*='/blog/']",
                    ".post-title a",
                    "h2.entry-title a",
                    ".article-title a",
                    "h3 a[href*='sentimentrader.com']",
                ]
                found_links = []
                seen_hrefs = set()
                for sel in link_selectors:
                    links = self.page.locator(sel)
                    for i in range(min(links.count(), limit * 3)):
                        try:
                            el = links.nth(i)
                            href = el.get_attribute("href") or ""
                            text = el.inner_text().strip()
                            if href and text and href not in seen_hrefs and len(text) > 10:
                                seen_hrefs.add(href)
                                if href.startswith("/"):
                                    href = BASE_URL + href
                                found_links.append((text, href))
                        except Exception:
                            continue
                    if len(found_links) >= limit:
                        break

                # Navigate to each article and extract body text
                for title, url in found_links[:limit]:
                    try:
                        self.page.goto(url, wait_until="domcontentloaded", timeout=20000)
                        self.page.wait_for_timeout(2000)

                        # Try common article body selectors
                        body_text = ""
                        for body_sel in [".post-content", "article", ".entry-content", ".blog-content"]:
                            el = self.page.locator(body_sel)
                            if el.count() > 0:
                                body_text = el.first.inner_text().strip()
                                break
                        if not body_text:
                            body_text = self.page.inner_text("body")[:3000]

                        # Extract date if present
                        date_str = ""
                        date_el = self.page.locator("time, .post-date, .entry-date, .published")
                        if date_el.count() > 0:
                            date_str = date_el.first.inner_text().strip()

                        articles.append({
                            "title": title,
                            "url": url,
                            "date": date_str,
                            "body": body_text[:3000],
                        })
                    except Exception as e:
                        print(f"      Error reading article '{title[:40]}': {e}")

            except Exception as e:
                print(f"    Error scraping {section_key}: {e}")

            all_reports[section_key] = articles

        # Save combined text file (institutional scraper format)
        self._save_research_text(all_reports)

        return all_reports

    def _save_research_text(self, reports: Dict[str, List[Dict]]) -> None:
        """Save research reports in combined text format."""
        lines = []
        for section, articles in reports.items():
            for art in articles:
                lines.append("=" * 62)
                lines.append(f"SECTION: {section.upper()}")
                lines.append(f"TITLE: {art['title']}")
                lines.append(f"DATE: {art.get('date', 'N/A')}")
                lines.append(f"URL: {art.get('url', 'N/A')}")
                lines.append("=" * 62)
                lines.append(art.get("body", "")[:3000])
                lines.append("")

        if lines:
            text_path = OUTPUT_DIR / "research_latest.txt"
            text_path.write_text("\n".join(lines), encoding="utf-8")
            json_path = OUTPUT_DIR / "research_latest.json"
            json_path.write_text(
                json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    def _download_csv(self) -> Optional[str]:
        """Download the indicator summary CSV."""
        try:
            # Use page.evaluate to fetch CSV via authenticated session
            csv_data = self.page.evaluate(f"""
                async () => {{
                    const resp = await fetch("{CSV_URL}");
                    if (resp.ok) return await resp.text();
                    return null;
                }}
            """)
            return csv_data
        except Exception as e:
            print(f"    Error downloading CSV: {e}")
            return None

    def _save_text_summary(self, data: Dict) -> None:
        """Save a human-readable text summary."""
        lines = []
        lines.append("=" * 60)
        lines.append("SENTIMENTRADER DASHBOARD SUMMARY")
        lines.append(f"Scraped: {data['scraped_at']}")
        lines.append(f"Data as of: {data.get('data_as_of', 'N/A')}")
        lines.append("=" * 60)
        lines.append("")

        # Smart/Dumb Money
        lines.append("SMART MONEY / DUMB MONEY CONFIDENCE")
        lines.append(f"  Smart Money: {data.get('smart_money_confidence', 'N/A')}")
        lines.append(f"  Dumb Money:  {data.get('dumb_money_confidence', 'N/A')}")
        sm = data.get("smart_money_confidence")
        dm = data.get("dumb_money_confidence")
        if sm and dm:
            spread = round(sm - dm, 2)
            lines.append(f"  Spread (SM - DM): {spread}")
            if spread > 0.3:
                lines.append("  Signal: BULLISH (Smart Money significantly more confident)")
            elif spread < -0.3:
                lines.append("  Signal: BEARISH (Dumb Money significantly more confident)")
            else:
                lines.append("  Signal: NEUTRAL")
        lines.append("")

        # Short-Term
        st = data.get("short_term", {})
        if st:
            lines.append("SHORT-TERM INDICATORS (0=Max Pessimism, 100=Max Optimism)")
            for k, v in st.items():
                lines.append(f"  {k.capitalize():12s}: {v}")
            lines.append("")

        # Intermediate-Term
        it = data.get("intermediate_term", {})
        if it:
            lines.append("INTERMEDIATE-TERM INDICATORS")
            for k, v in it.items():
                lines.append(f"  {k.capitalize():12s}: {v}")
            lines.append("")

        # Sector Trend Scores
        sectors = data.get("sector_trend_scores", {})
        if sectors:
            lines.append("S&P 500 SECTOR TREND SCORES")
            for sector, score in sorted(sectors.items(), key=lambda x: -x[1]):
                lines.append(f"  {sector:25s}: {score}")
            lines.append("")

        # Correlated Indicators
        corr = data.get("correlated_indicators", [])
        if corr:
            lines.append("MOST CORRELATED INDICATORS (Last 3 Months)")
            for ind in corr:
                lines.append(f"  {ind['name']:35s}  Value={ind['value']}  Corr={ind['correlation']}")
            lines.append("")

        # Highlighted Indicators
        highlighted = data.get("highlighted_indicators", [])
        if highlighted:
            lines.append("HIGHLIGHTED INDICATORS (Recent Research)")
            for ind in highlighted:
                lines.append(f"  [{ind['date']}] {ind['indicator']}: {ind['last_value']}")
                lines.append(f"    Research: {ind['research']}")
            lines.append("")

        # Active Studies
        active = data.get("active_studies", {})
        summary = active.get("summary", {})
        if summary:
            lines.append("ACTIVE STUDIES SUMMARY (stocks-only)")
            for tf, counts in summary.items():
                bull = counts.get("bullish", 0)
                bear = counts.get("bearish", 0)
                total = bull + bear
                ratio = round(bull / total, 2) if total > 0 else "N/A"
                lines.append(f"  {tf:15s}: {bull} Bullish / {bear} Bearish  (bull ratio: {ratio})")
            lines.append("")
        studies = active.get("studies", [])
        if studies:
            lines.append(f"ACTIVE STUDIES ({len(studies)} individual)")
            for s in studies[:20]:
                arrow = {"bullish": "UP", "bearish": "DOWN", "flat": "FLAT"}.get(s["forecast"], s["forecast"])
                lines.append(f"  [{s['date']}] {s['market']:6s} {arrow:5s} {s['timeframe']:12s} | {s['title']}")
            if len(studies) > 20:
                lines.append(f"  ... and {len(studies) - 20} more")
            lines.append("")

        # Phase Table
        phase_table = data.get("phase_table", {})
        phase_labels = {
            "phase_1": "Phase 1 (Extremely Low Optimism)",
            "phase_2": "Phase 2 (Low but Rising)",
            "phase_3": "Phase 3 (High but Declining)",
            "phase_4": "Phase 4 (Extremely High Optimism)",
        }
        has_phases = any(phase_table.get(k) for k in phase_labels)
        if has_phases:
            lines.append("PHASE TABLE (Sentiment Regimes)")
            for key, label in phase_labels.items():
                assets = phase_table.get(key, [])
                if assets:
                    lines.append(f"  {label}:")
                    for a in assets:
                        lines.append(f"    {a['market']:35s} Optix={a['optix']}")
            lines.append("")

        # Commentary
        commentary = data.get("latest_commentary", [])
        if commentary:
            lines.append("LATEST COMMENTARY")
            for art in commentary[:5]:
                lines.append(f"  [{art['date']}] {art['title']}")
                lines.append(f"    {art['summary'][:200]}")
            lines.append("")

        text_path = OUTPUT_DIR / "sentimentrader_latest.txt"
        text_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"  Text summary: {text_path}")

    # ------------------------------------------------------------------
    # Exploration mode (keep for future selector refinement)
    # ------------------------------------------------------------------

    def explore(self) -> Dict[str, Any]:
        """Navigate key pages, save screenshots + HTML for selector mapping."""
        EXPLORE_DIR.mkdir(parents=True, exist_ok=True)
        self.ensure_logged_in()

        manifest = {"explored_at": _now_iso(), "pages": {}}

        print("\n  Phase 1: Capturing dashboard and navigation...")
        self._explore_page("dashboard", EXPLORE_PAGES["dashboard"], manifest)

        nav_links = self._discover_nav_links()
        if nav_links:
            print(f"\n  Discovered {len(nav_links)} navigation links:")
            for label, url in nav_links[:20]:
                print(f"    {label}: {url}")
            links_path = EXPLORE_DIR / "discovered_nav_links.json"
            links_path.write_text(
                json.dumps(nav_links, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        print("\n  Phase 2: Exploring indicator pages...")
        for page_key, url in EXPLORE_PAGES.items():
            if page_key == "dashboard":
                continue
            self._explore_page(page_key, url, manifest)

        manifest_path = EXPLORE_DIR / "explore_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n  Exploration manifest: {manifest_path}")
        return manifest

    def _explore_page(self, page_key: str, url: str, manifest: Dict) -> None:
        """Navigate to a page, capture screenshot + HTML."""
        print(f"\n  [{page_key}] Navigating to: {url}")
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            self.page.wait_for_timeout(4000)
            for _ in range(3):
                self.page.evaluate("window.scrollBy(0, window.innerHeight)")
                self.page.wait_for_timeout(1500)
            self.page.evaluate("window.scrollTo(0, 0)")
            self.page.wait_for_timeout(500)

            ss_path = EXPLORE_DIR / f"{page_key}.png"
            self.page.screenshot(path=str(ss_path), full_page=True)
            print(f"    Screenshot: {ss_path}")

            html_path = EXPLORE_DIR / f"{page_key}.html"
            html = self.page.content()
            html_path.write_text(html, encoding="utf-8")
            print(f"    HTML: {html_path} ({len(html)} chars)")

            body_text = self.page.inner_text("body")
            text_path = EXPLORE_DIR / f"{page_key}.txt"
            text_path.write_text(body_text, encoding="utf-8")
            print(f"    Text: {text_path} ({len(body_text)} chars)")

            manifest["pages"][page_key] = {
                "target_url": url,
                "actual_url": self.page.url,
                "screenshot": str(ss_path),
                "html_path": str(html_path),
                "text_path": str(text_path),
                "html_size": len(html),
                "text_size": len(body_text),
            }
        except Exception as e:
            print(f"    ERROR: {e}")
            self.screenshot(f"explore_error_{page_key}")
            manifest["pages"][page_key] = {"target_url": url, "error": str(e)}

    def _discover_nav_links(self) -> List[tuple]:
        """Extract navigation links from the current page."""
        links = []
        try:
            anchors = self.page.locator("a[href]")
            count = anchors.count()
            seen = set()
            for i in range(count):
                try:
                    el = anchors.nth(i)
                    href = el.get_attribute("href") or ""
                    text = el.inner_text().strip()[:100]
                    if not href or href in seen or not text:
                        continue
                    if "sentimentrader.com" in href or href.startswith("/"):
                        if href.startswith("/"):
                            href = BASE_URL + href
                        seen.add(href)
                        links.append((text, href))
                except Exception:
                    continue
        except Exception:
            pass
        return links

    def record_network(self, url: str, page_key: str) -> List[Dict]:
        """Navigate to a page while recording XHR/fetch responses."""
        captured = []

        def on_response(response):
            try:
                req_url = response.url
                if any(pat in req_url for pat in ["/api/", "/data/", ".json", "graphql"]):
                    captured.append({
                        "url": req_url,
                        "status": response.status,
                        "content_type": response.headers.get("content-type", ""),
                    })
            except Exception:
                pass

        self.page.on("response", on_response)
        try:
            self.page.goto(url, wait_until="networkidle", timeout=30000)
            self.page.wait_for_timeout(3000)
        except Exception:
            pass
        self.page.remove_listener("response", on_response)

        if captured:
            api_path = EXPLORE_DIR / f"{page_key}_api_calls.json"
            api_path.write_text(
                json.dumps(captured, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"    Captured {len(captured)} API calls → {api_path}")
        return captured
