"""
DeepVue Dashboard Scraper

Captures screenshots and extracts key data from DeepVue dashboards:
- Market Overview (breadth, stage analysis, sectors)
- PreOpen (pre-market movers, bubble charts)

Uses persistent Playwright session — login once, reuse cookies.

First run (interactive):
    python scrape_deepvue.py

Headless (after login session established):
    python scrape_deepvue.py --headless
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from browser.base import BrowserAutomation, SCRAPED_DIR


class DeepVueScraper(BrowserAutomation):
    SERVICE_NAME = "deepvue"
    USE_CHROME_PROFILE = False

    DASHBOARD_URL = "https://app.deepvue.com/dashboard"
    MARKET_OVERVIEW_TAB = "Market overview11"
    PREOPEN_TAB = "PreOpen"

    def __init__(self, **kwargs):
        # Wider viewport for dashboard panels
        kwargs.setdefault("slow_mo", 200)
        super().__init__(**kwargs)
        self.output_dir = SCRAPED_DIR / "deepvue"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def start(self):
        """Override to use wider viewport for dashboards."""
        if self.USE_CHROME_PROFILE:
            from browser.base import is_chrome_running, copy_chrome_session
            if is_chrome_running():
                print("\n" + "=" * 60)
                print("  Chrome is currently running.")
                print("  Please CLOSE ALL Chrome windows first,")
                print("  then press Enter to continue.")
                print("=" * 60)
                input("  Press ENTER when Chrome is closed >>> ")
                print()
            print("  Copying Chrome session data...")
            copy_chrome_session(self.session_dir)

        from playwright.sync_api import sync_playwright
        self.playwright = sync_playwright().start()
        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.session_dir),
            headless=self.headless,
            slow_mo=self.slow_mo,
            viewport={"width": 2560, "height": 940},
            locale="en-US",
            args=["--disable-blink-features=AutomationControlled"],
        )
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        return self.page

    def is_logged_in(self) -> bool:
        """Check if DeepVue session is valid."""
        self.page.goto(self.DASHBOARD_URL, wait_until="domcontentloaded")
        self.page.wait_for_timeout(5000)
        url = self.page.url.lower()
        # If redirected to login page, not authenticated
        if "login" in url or "sign-in" in url or "auth" in url:
            return False
        # Check if dashboard content loaded
        try:
            # Look for dashboard navigation or content elements
            has_content = self.page.locator("text=Market Overview").count() > 0
            return has_content
        except Exception:
            return False

    def login(self):
        """
        DeepVue uses code-based login (email → verification code).
        Must be done interactively the first time.
        """
        self.page.goto("https://app.deepvue.com", wait_until="domcontentloaded")
        self.page.wait_for_timeout(3000)
        self.wait_for_user(
            "Please log in to DeepVue in the browser:\n"
            "  1. Enter your email\n"
            "  2. Check email for login code\n"
            "  3. Enter the code\n"
            "  4. Wait until the dashboard loads\n"
            "  Press Enter here when you see the dashboard."
        )

    def _wait_for_dashboard_load(self, timeout: int = 15000):
        """Wait for dashboard panels to render."""
        try:
            self.page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            # networkidle can timeout on SPA dashboards with persistent connections
            pass
        self.page.wait_for_timeout(timeout)

    def _switch_tab(self, tab_name: str):
        """Click a top-level dashboard tab."""
        try:
            tab = self.page.locator(f"text={tab_name}").first
            if tab.is_visible():
                tab.click()
                self.page.wait_for_timeout(3000)
                self._wait_for_dashboard_load(timeout=10000)
                return True
        except Exception:
            pass
        return False

    def _close_sidebar(self):
        """Close the left sidebar/dropdown if open, so screenshots are clean."""
        try:
            # Click on the main content area to dismiss any open menus
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(500)
            # Click the main dashboard area to ensure focus moves away from sidebar
            main = self.page.locator("main, .dashboard-content, [class*='content']").first
            if main.is_visible():
                main.click(position={"x": 500, "y": 400})
                self.page.wait_for_timeout(500)
        except Exception:
            pass

    def _scroll_panel(self, selector: str, scroll_top: int = 99999):
        """Scroll an internal panel to the given scroll position."""
        try:
            self.page.evaluate(f"""() => {{
                const el = document.querySelector('{selector}');
                if (el) el.scrollTop = {scroll_top};
            }}""")
            self.page.wait_for_timeout(500)
        except Exception:
            pass

    def _detect_market_overview_panel_bounds(self, width: int, height: int) -> tuple[int, int, int]:
        """
        Detect x-boundaries for (left | stage | right) layout.
        Falls back to 40/20/40 if panel headers are not detectable.
        """
        default_left = int(round(width * 0.40))
        default_center = int(round(width * 0.60))
        default_top = int(round(height * 0.05))
        left_end = default_left
        center_end = default_center
        top_trim = default_top

        try:
            stage_box = self.page.locator("text=Stage Analysis").first.bounding_box()
        except Exception:
            stage_box = None
        try:
            user_box = self.page.locator("text=User Panel").first.bounding_box()
        except Exception:
            user_box = None

        if stage_box and user_box:
            cand_left = int(stage_box.get("x", left_end))
            cand_center = int(user_box.get("x", center_end))
            cand_top = int(min(stage_box.get("y", top_trim), user_box.get("y", top_trim)))

            # Guard against matching hidden/off-target text nodes.
            min_left = int(width * 0.25)
            min_center_width = int(width * 0.10)
            min_right = int(width * 0.25)
            if (
                cand_left >= min_left
                and (cand_center - cand_left) >= min_center_width
                and (width - cand_center) >= min_right
            ):
                left_end = cand_left
                center_end = cand_center
                top_trim = cand_top
            else:
                left_end = default_left
                center_end = default_center
                top_trim = default_top

        left_end = max(1, min(left_end, width - 2))
        center_end = max(left_end + 1, min(center_end, width - 1))
        top_trim = max(0, min(top_trim, height - 1))
        return left_end, center_end, top_trim

    def _build_market_overview_panel_screenshots(
        self,
        full_screenshot_path: Path,
        ts: str,
    ) -> list[str]:
        """Create 3 DeepVue-style panel images from the full market overview screenshot."""
        try:
            from PIL import Image
        except Exception as e:
            print(f"  Panel split skipped (Pillow missing): {e}")
            return []

        panel_paths: list[str] = []
        try:
            with Image.open(full_screenshot_path) as img:
                width, height = img.size
                left_end, center_end, top_trim = self._detect_market_overview_panel_bounds(width, height)

                crops = [
                    ("left", (0, 0, left_end, height)),
                    ("stage", (left_end, top_trim, center_end, height)),
                    ("right", (center_end, top_trim, width, height)),
                ]

                for idx, (name, box) in enumerate(crops, start=1):
                    panel_path = self.output_dir / f"market_overview_panel{idx}_{name}_{ts}.png"
                    panel = img.crop(box)
                    panel.save(panel_path)
                    panel_paths.append(str(panel_path))
        except Exception as e:
            print(f"  Panel split error: {e}")
            return []

        return panel_paths

    def capture_market_overview(self) -> dict:
        """
        Capture Market Overview dashboard — single wide screenshot (2560x940)
        matching the user's ultrawide display so all panels fit.
        """
        print("[DeepVue] Capturing Market Overview...")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        result = {
            "dashboard": "market_overview",
            "timestamp": datetime.now().isoformat(),
            "screenshots": [],
            "screenshot": None,
            "full_screenshot": None,
            "breadth": {},
            "stages": {},
        }

        # Navigate to Market Overview tab
        self.page.goto(self.DASHBOARD_URL, wait_until="domcontentloaded")
        self._wait_for_dashboard_load()

        # Try to click Market Overview tab
        self._switch_tab(self.MARKET_OVERVIEW_TAB)

        # Close sidebar/dropdowns for clean screenshot
        self._close_sidebar()

        # Single wide screenshot — all panels fit at 2560x940
        screenshot_path = self.output_dir / f"market_overview_{ts}.png"
        self.page.screenshot(path=str(screenshot_path), full_page=False)
        result["screenshot"] = str(screenshot_path)
        result["full_screenshot"] = str(screenshot_path)
        print(f"  Full screenshot: {screenshot_path}")

        panel_paths = self._build_market_overview_panel_screenshots(screenshot_path, ts)
        if panel_paths:
            result["screenshots"] = panel_paths
            for panel_path in panel_paths:
                print(f"  Panel screenshot: {panel_path}")
        else:
            result["screenshots"] = [str(screenshot_path)]

        # Extract breadth metrics from DOM
        try:
            result["breadth"] = self._extract_breadth_data()
        except Exception as e:
            print(f"  Breadth extraction error: {e}")

        # Extract stage analysis
        try:
            result["stages"] = self._extract_stage_data()
        except Exception as e:
            print(f"  Stage extraction error: {e}")

        # Save data to JSON
        data_path = self.output_dir / "market_overview.json"
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"  Data saved: {data_path}")

        return result

    def capture_preopen(self) -> dict:
        """
        Capture PreOpen dashboard:
        - Full screenshot
        - Extract top movers from scanner table
        """
        print("[DeepVue] Capturing PreOpen...")
        result = {
            "dashboard": "preopen",
            "timestamp": datetime.now().isoformat(),
            "screenshot": None,
            "movers": [],
        }

        # Navigate and switch to PreOpen tab
        self.page.goto(self.DASHBOARD_URL, wait_until="domcontentloaded")
        self._wait_for_dashboard_load()
        self._switch_tab(self.PREOPEN_TAB)

        # Close sidebar for clean screenshot
        self._close_sidebar()

        # Take screenshot
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = self.output_dir / f"preopen_{ts}.png"
        self.page.screenshot(path=str(screenshot_path), full_page=False)
        result["screenshot"] = str(screenshot_path)
        print(f"  Screenshot: {screenshot_path}")

        # Extract top movers from table
        try:
            result["movers"] = self._extract_preopen_movers()
        except Exception as e:
            print(f"  Movers extraction error: {e}")

        # Save data
        data_path = self.output_dir / "preopen.json"
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"  Data saved: {data_path}")

        return result

    def _extract_breadth_data(self) -> dict:
        """Extract Market Breadth panel data from the DOM."""
        breadth = {}

        # Get all text content from the page for parsing
        body_text = self.page.inner_text("body")

        # Parse breadth metrics using regex patterns
        patterns = {
            "new_highs_vs_lows_pct": r"New Highs vs New Lows\s+(\d+)%",
            "advance_decline_pct": r"Advance vs Decline\s+(\d+)%",
            "up_from_open_pct": r"Up from Open vs Down from Open\s+(\d+)%",
            "up_volume_pct": r"Up on Volume vs Down on Volume\s+(\d+)%",
            "up_4pct_pct": r"Up 4% vs Down 4%\s+(\d+)%",
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, body_text)
            if match:
                breadth[key] = int(match.group(1))

        # Try to extract raw counts
        count_patterns = {
            "highs_count": r"(\d+)\s*Highs",
            "lows_count": r"(\d+)\s*Lows",
            "advance_count": r"(\d+)\s*Advance",
            "decline_count": r"(\d+)\s*Decline",
        }
        for key, pattern in count_patterns.items():
            match = re.search(pattern, body_text)
            if match:
                breadth[key] = int(match.group(1))

        if breadth:
            print(f"  Breadth: {breadth}")

        return breadth

    def _extract_stage_data(self) -> dict:
        """Extract Stage Analysis data including S2A (Stage 2 Advance)."""
        stages = {}
        body_text = self.page.inner_text("body")

        # Try the dot-separator format first: "86 · 1%", "630 · 11%"
        # Look for S1/S2A/S2/S3/S4 labels followed by count · pct%
        for label, key in [("S1", "stage_1"), ("S2A", "stage_2a"),
                           ("S2", "stage_2"), ("S3", "stage_3"), ("S4", "stage_4")]:
            # Match: "S2A\n630 · 11%" or "S2A 630 · 11%" or "S1 86 · 1%"
            pattern = rf"(?<!\w){label}(?!\w)[\s\n]+(\d[\d,]*)\s*[·.]\s*(\d+)%"
            match = re.search(pattern, body_text)
            if match:
                count = int(match.group(1).replace(",", ""))
                pct = int(match.group(2))
                stages[key] = {"count": count, "pct": pct}

        # Fallback: "Stage 1  83  1%" format (no dot separator)
        if not stages:
            stage_pattern = r"Stage\s*(\d)\s+(\d[\d,]*)\s+(\d+)%"
            for match in re.finditer(stage_pattern, body_text):
                stage_num = int(match.group(1))
                count = int(match.group(2).replace(",", ""))
                pct = int(match.group(3))
                stages[f"stage_{stage_num}"] = {"count": count, "pct": pct}

        if stages:
            print(f"  Stages: {stages}")

        return stages

    def _extract_preopen_movers(self) -> list:
        """Extract top movers from PreOpen scanner table."""
        movers = []

        try:
            # Look for the Universe table rows
            rows = self.page.locator("table tbody tr").all()
            for row in rows[:15]:  # Top 15 movers
                try:
                    cells = row.locator("td").all()
                    if len(cells) < 5:
                        continue

                    # Extract visible text from cells
                    symbol = cells[0].inner_text().strip() if cells[0] else ""
                    # Clean up symbol text (remove icons etc)
                    symbol = re.sub(r'[^\w\s.-]', '', symbol).strip().split()[0] if symbol else ""

                    if not symbol or len(symbol) > 6:
                        continue

                    mover = {"symbol": symbol}

                    # Try to get numeric values from subsequent cells
                    for i, cell in enumerate(cells[1:7], 1):
                        try:
                            val = cell.inner_text().strip()
                            if val:
                                mover[f"col_{i}"] = val
                        except Exception:
                            pass

                    movers.append(mover)
                except Exception:
                    continue

        except Exception as e:
            print(f"  Table extraction error: {e}")

        if movers:
            print(f"  Found {len(movers)} movers")

        return movers

    def run(self, dashboards: list[str] | None = None):
        """
        Capture specified dashboards (default: both).

        Args:
            dashboards: List of dashboard names to capture.
                Options: "market_overview", "preopen"
        """
        if dashboards is None:
            dashboards = ["market_overview", "preopen"]

        self.ensure_logged_in()
        results = {}

        if "market_overview" in dashboards:
            results["market_overview"] = self.capture_market_overview()

        if "preopen" in dashboards:
            results["preopen"] = self.capture_preopen()

        return results
