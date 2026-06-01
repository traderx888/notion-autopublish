"""
HedgeFollow insider activity scraper.

Captures the public Largest Insider Buys and Largest Insider Sells tables,
normalizes the rendered 1-week rows, and emits JSON plus a reusable dashboard
HTML section snippet.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from browser.base import BrowserAutomation, SCRAPED_DIR

OUTPUT_DIR = SCRAPED_DIR / "hedgefollow_insiders"
BUY_PAGE_URL = "https://hedgefollow.com/largest-insider-buys.php"
SELL_PAGE_URL = "https://hedgefollow.com/largest-insider-sells.php"
ROW_WAIT_SELECTOR = "table#insider_1W tbody tr"

_BOT_CHECK_SIGNALS = [
    "just a moment",
    "checking your browser",
    "performing security verification",
    "verify you are human",
    "attention required",
]


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _normalize_money_spacing(text: str) -> str:
    text = _normalize_whitespace(text)
    return re.sub(r"\$\s+", "$", text)


def parse_money_text(text: str) -> float | None:
    match = re.search(r"\$?\s*([\d,.]+)\s*([KMB])?\b", text or "", re.IGNORECASE)
    if not match:
        return None
    value = float(match.group(1).replace(",", ""))
    suffix = (match.group(2) or "").lower()
    multiplier = {"": 1.0, "k": 1_000.0, "m": 1_000_000.0, "b": 1_000_000_000.0}[suffix]
    return value * multiplier


def _extract_range_bounds(text: str) -> tuple[str, str]:
    amounts = [
        _normalize_money_spacing(match.group(0))
        for match in re.finditer(r"\$\s*[\d,.]+", text or "")
    ]
    if len(amounts) >= 2:
        return amounts[0], amounts[-1]
    if len(amounts) == 1:
        return amounts[0], amounts[0]
    return "", ""


def _extract_primary_insider(summary: str) -> str:
    summary = _normalize_whitespace(summary)
    match = re.match(r"(.+?)\s+-\s+\$", summary)
    return match.group(1).strip() if match else summary


def _looks_like_symbol(symbol: str) -> bool:
    cleaned = _normalize_whitespace(symbol)
    return bool(re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,8}", cleaned))


def normalize_table_rows(raw_rows: list[dict[str, Any]], source_page: str) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for raw_row in raw_rows:
        cells = [_normalize_whitespace(cell) for cell in raw_row.get("cells", []) if _normalize_whitespace(cell)]
        if len(cells) < 5:
            continue
        symbol = cells[0]
        if not _looks_like_symbol(symbol):
            continue

        trade_value_text = _normalize_money_spacing(cells[2])
        range_low, range_high = _extract_range_bounds(cells[3])
        insider_summary = _normalize_whitespace(cells[4])

        normalized.append(
            {
                "rank": len(normalized) + 1,
                "symbol": symbol,
                "company_name": cells[1],
                "trade_value_text": trade_value_text,
                "trade_value_numeric": parse_money_text(trade_value_text),
                "range_low": range_low,
                "range_high": range_high,
                "primary_insider": _extract_primary_insider(insider_summary),
                "insider_summary": insider_summary,
                "stock_url": raw_row.get("stock_url", ""),
                "source_page": source_page,
            }
        )
    return normalized


def _format_human_timestamp(iso_text: str) -> str:
    try:
        return datetime.fromisoformat(iso_text).strftime("%b %d, %Y %H:%M %Z").strip()
    except ValueError:
        return iso_text


def _render_table_rows(rows: list[dict[str, Any]], row_limit: int) -> str:
    if not rows:
        return '<tr><td colspan="4" style="color:var(--muted);">No insider rows captured.</td></tr>'

    rendered_rows: list[str] = []
    for row in rows[:row_limit]:
        stock_label = escape(row["symbol"])
        stock_url = row.get("stock_url") or row.get("source_page") or "#"
        company_name = escape(row["company_name"])
        trade_value = escape(row["trade_value_text"])
        primary_insider = escape(row["primary_insider"])
        insider_summary = escape(row["insider_summary"])
        rendered_rows.append(
            "<tr>"
            f'<td><a href="{escape(stock_url)}" target="_blank" rel="noreferrer">{stock_label}</a></td>'
            f"<td>{company_name}</td>"
            f'<td class="val">{trade_value}</td>'
            f'<td title="{insider_summary}">{primary_insider}</td>'
            "</tr>"
        )
    return "".join(rendered_rows)


def render_dashboard_section(manifest: dict[str, Any], row_limit: int = 5) -> str:
    generated_at = _format_human_timestamp(manifest.get("generated_at", ""))
    largest_buys = manifest.get("largest_buys_1w", [])
    largest_sells = manifest.get("largest_sells_1w", [])
    buy_page = manifest.get("buy_page", BUY_PAGE_URL)
    sell_page = manifest.get("sell_page", SELL_PAGE_URL)

    return f"""
<!-- HEDGEFOLLOW INSIDERS -->
<div class="section-title">Insider Flow</div>
<div class="grid">
  <div class="card">
    <div class="card-header">
      <div class="card-icon" style="background:rgba(63,185,80,0.2);color:var(--green);">IB</div>
      <div>
        <div class="card-title">Largest Insider Buys</div>
        <div class="card-subtitle">HedgeFollow public tracker &middot; 1-week aggregate &middot; latest capture {escape(generated_at)}</div>
      </div>
    </div>
    <table>
      <tr><th>Stock</th><th>Company</th><th>Value 1W</th><th>Lead Insider</th></tr>
      {_render_table_rows(largest_buys, row_limit)}
    </table>
    <div style="margin-top:10px;font-size:12px;color:var(--muted);">
      <strong>Source:</strong> <a href="{escape(buy_page)}" target="_blank" rel="noreferrer">HedgeFollow Largest Insider Buys</a>
    </div>
  </div>

  <div class="card">
    <div class="card-header">
      <div class="card-icon" style="background:rgba(248,81,73,0.2);color:var(--red);">IS</div>
      <div>
        <div class="card-title">Largest Insider Sells</div>
        <div class="card-subtitle">HedgeFollow public tracker &middot; 1-week aggregate &middot; latest capture {escape(generated_at)}</div>
      </div>
    </div>
    <table>
      <tr><th>Stock</th><th>Company</th><th>Value 1W</th><th>Lead Insider</th></tr>
      {_render_table_rows(largest_sells, row_limit)}
    </table>
    <div style="margin-top:10px;font-size:12px;color:var(--muted);">
      <strong>Source:</strong> <a href="{escape(sell_page)}" target="_blank" rel="noreferrer">HedgeFollow Largest Insider Sells</a>
    </div>
  </div>
</div>
""".strip()


def write_run_artifacts(manifest: dict[str, Any], output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    latest_path = output_dir / "hedgefollow_insiders_latest.json"
    buys_path = output_dir / "largest_insider_buys.json"
    sells_path = output_dir / "largest_insider_sells.json"
    section_path = output_dir / "insider_dashboard_section.html"

    latest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    buys_path.write_text(
        json.dumps(manifest.get("largest_buys_1w", []), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    sells_path.write_text(
        json.dumps(manifest.get("largest_sells_1w", []), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    section_path.write_text(render_dashboard_section(manifest), encoding="utf-8")
    return manifest


class HedgeFollowInsiderScraper(BrowserAutomation):
    """Public Playwright scraper for HedgeFollow insider tables."""

    SERVICE_NAME = "hedgefollow_insiders"
    USE_CHROME_PROFILE = False

    def __init__(self, headless: bool = True, slow_mo: int = 100, use_chrome: bool | None = None):
        super().__init__(headless=headless, slow_mo=slow_mo, use_chrome=use_chrome)
        self.output_dir = OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def start(self):
        """Prefer the Chrome channel to reduce bot friction on public pages."""
        from playwright.sync_api import sync_playwright

        self.playwright = sync_playwright().start()
        launch_kwargs = dict(
            user_data_dir=str(self.session_dir),
            headless=self.headless,
            slow_mo=self.slow_mo,
            viewport={"width": 1600, "height": 1200},
            locale="en-US",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        try:
            self.context = self.playwright.chromium.launch_persistent_context(
                channel="chrome",
                **launch_kwargs,
            )
        except Exception:
            self.context = self.playwright.chromium.launch_persistent_context(**launch_kwargs)

        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        self.page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => false});"
        )
        return self.page

    def is_logged_in(self) -> bool:
        return True

    def login(self):
        return None

    def _body_text(self) -> str:
        try:
            return self.page.inner_text("body")
        except Exception:
            return ""

    def _is_bot_check_page(self) -> bool:
        lowered = self._body_text().lower()
        return any(signal in lowered for signal in _BOT_CHECK_SIGNALS)

    def _navigate(self, url: str) -> None:
        self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
        self.page.wait_for_timeout(4000)
        self.page.wait_for_function(
            "() => document.querySelectorAll('table#insider_1W tbody tr').length >= 10",
            timeout=25000,
        )

    def _extract_table_rows(self) -> list[dict[str, Any]]:
        return self.page.evaluate(
            """
            () => {
              const rows = Array.from(document.querySelectorAll('table#insider_1W tbody tr'));
              return rows.map((row) => {
                const visibleCells = Array.from(row.querySelectorAll('td')).filter((cell) => {
                  const style = window.getComputedStyle(cell);
                  return style.display !== 'none' && style.visibility !== 'hidden' && cell.offsetParent !== null;
                });
                const stockLink = row.querySelector("a[href*='/stocks/']");
                return {
                  cells: visibleCells.map((cell) => cell.innerText.replace(/\\s+/g, ' ').trim()),
                  stock_url: stockLink ? stockLink.href : '',
                };
              });
            }
            """
        )

    def scrape_table(self, source_page: str) -> list[dict[str, Any]]:
        self._navigate(source_page)
        if self._is_bot_check_page():
            raise RuntimeError(f"HedgeFollow bot check blocked page load for {source_page}")
        return normalize_table_rows(self._extract_table_rows(), source_page=source_page)

    def run(self) -> dict[str, Any]:
        largest_buys = self.scrape_table(BUY_PAGE_URL)
        largest_sells = self.scrape_table(SELL_PAGE_URL)

        manifest = {
            "generated_at": _now_iso(),
            "source": "HedgeFollow",
            "window": "1W",
            "buy_page": BUY_PAGE_URL,
            "sell_page": SELL_PAGE_URL,
            "largest_buys_1w": largest_buys,
            "largest_sells_1w": largest_sells,
        }
        write_run_artifacts(manifest, output_dir=self.output_dir)
        return manifest
