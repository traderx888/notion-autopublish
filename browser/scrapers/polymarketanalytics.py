"""
Public Polymarket Analytics scraper.

Uses the public website plus its public JSON endpoints to build three artifacts:
  - leaderboard_latest.json
  - activity_latest.json
  - trader_signals_latest.json
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from browser.base import BrowserAutomation, SCRAPED_DIR

OUTPUT_DIR = SCRAPED_DIR / "polymarketanalytics"
TRADERS_PAGE_URL = "https://polymarketanalytics.com/traders"
ACTIVITY_PAGE_URL = "https://polymarketanalytics.com/activity"
LEADERBOARD_API_URL = "https://polymarketanalytics.com/api/traders-tag-performance"
ACTIVITY_API_URL = "https://polymarketanalytics.com/api/activity-trades"
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}
TRACKED_TRADER_LIMIT = 25
MIN_TRACKED_WIN_RATE_PCT = 60.0
MIN_TRACKED_ACTIVE_POSITIONS = 5
MIN_TRACKED_TOTAL_POSITIONS = 5
MIN_TRACKED_PNL = 1_000_000.0
LEADERBOARD_CACHE_MAX_AGE = timedelta(hours=24)
ACTIVITY_CACHE_MAX_AGE = timedelta(minutes=90)
DEFAULT_ACTIVITY_PAGES = 20
DEFAULT_ACTIVITY_PAGE_SIZE = 100
MIN_ACTIVITY_PAGES = 5
TARGET_TRACKED_ACTIVITY_HITS = 5
RECENT_TRADE_WINDOW = timedelta(hours=24)


def _now() -> datetime:
    return datetime.now(timezone.utc).astimezone()


def _now_iso() -> str:
    return _now().isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _round_money(value: Any) -> float:
    return round(_safe_float(value, 0.0), 2)


def _short_wallet(wallet: str) -> str:
    text = str(wallet or "").strip()
    if len(text) <= 12:
        return text
    return f"{text[:6]}...{text[-4:]}"


def _display_name(handle: str, wallet: str) -> str:
    cleaned = str(handle or "").strip()
    return cleaned or _short_wallet(wallet)


def _parse_trade_time(text: Any) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    dt = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _parse_iso_datetime(text: Any) -> datetime | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _status_age_minutes(generated_at: str) -> float | None:
    dt = _parse_iso_datetime(generated_at)
    if dt is None:
        return None
    return round((_now() - dt).total_seconds() / 60.0, 1)


def _status_payload(
    *,
    status: str,
    generated_at: str,
    row_count: int,
    used_cache: bool,
    error: str = "",
    stale_after: timedelta | None = None,
) -> dict[str, Any]:
    age_minutes = _status_age_minutes(generated_at)
    stale = False
    if age_minutes is not None and stale_after is not None:
        stale = age_minutes > stale_after.total_seconds() / 60.0
    return {
        "status": status,
        "generated_at": generated_at,
        "row_count": int(row_count),
        "used_cache": bool(used_cache),
        "stale": stale,
        "age_minutes": age_minutes,
        "error": str(error or ""),
    }


def normalize_leaderboard_rows(raw_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in raw_rows or []:
        wallet = str(raw.get("trader", "") or "").strip()
        if not wallet:
            continue
        handle = str(raw.get("trader_name", "") or "").strip()
        rows.append(
            {
                "rank": _safe_int(raw.get("rank"), len(rows) + 1),
                "wallet": wallet,
                "handle": handle,
                "display_name": _display_name(handle, wallet),
                "total_pnl": _round_money(raw.get("overall_gain")),
                "win_rate_pct": round(_safe_float(raw.get("win_rate"), 0.0) * 100.0, 1),
                "active_positions": _safe_int(raw.get("active_positions")),
                "current_value": _round_money(raw.get("total_current_value")),
                "total_positions": _safe_int(raw.get("total_positions")),
                "total_wins": _round_money(raw.get("win_amount")),
                "total_losses": _round_money(raw.get("loss_amount")),
                "trader_tags": str(raw.get("trader_tags", "") or "").strip(),
            }
        )
    rows.sort(key=lambda row: (row["rank"], -row["total_pnl"]))
    return rows


def normalize_activity_rows(raw_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in raw_rows or []:
        wallet = str(raw.get("trader_id", "") or "").strip()
        if not wallet:
            continue
        handle = str(raw.get("trader_name", "") or "").strip()
        rows.append(
            {
                "trade_at": _parse_trade_time(raw.get("trade_dttm")),
                "trader_wallet": wallet,
                "handle": handle,
                "display_name": _display_name(handle, wallet),
                "side": str(raw.get("side", "") or "").strip().lower(),
                "shares": round(_safe_float(raw.get("amount"), 0.0), 6),
                "price": round(_safe_float(raw.get("price"), 0.0), 6),
                "value": _round_money(raw.get("value")),
                "event_id": str(raw.get("event_id", "") or "").strip(),
                "market_title": str(raw.get("market_title", "") or "").strip(),
                "market_subtitle": str(raw.get("market_subtitle", "") or "").strip(),
                "outcome": str(raw.get("outcome", "") or "").strip(),
                "trader_tags": str(raw.get("trader_tags", "") or "").strip(),
            }
        )
    rows.sort(key=lambda row: row.get("trade_at", ""), reverse=True)
    return rows


def select_tracked_traders(leaderboard_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def _qualifies(row: dict[str, Any]) -> bool:
        win_rate_pct = float(row.get("win_rate_pct", 0.0))
        active_positions = int(row.get("active_positions", 0) or 0)
        total_positions = int(row.get("total_positions", 0) or 0)
        total_pnl = float(row.get("total_pnl", 0.0) or 0.0)
        if win_rate_pct < MIN_TRACKED_WIN_RATE_PCT:
            return False
        if active_positions >= MIN_TRACKED_ACTIVE_POSITIONS:
            return True
        return total_pnl >= MIN_TRACKED_PNL and total_positions >= MIN_TRACKED_TOTAL_POSITIONS

    eligible = [
        dict(row)
        for row in leaderboard_rows
        if _qualifies(row)
    ]
    eligible.sort(key=lambda row: (-float(row.get("total_pnl", 0.0)), int(row.get("rank", 999999))))
    return eligible[:TRACKED_TRADER_LIMIT]


def build_trader_signals_manifest(
    *,
    leaderboard_rows: list[dict[str, Any]],
    activity_rows: list[dict[str, Any]],
    tracked_activity_rows: list[dict[str, Any]] | None = None,
    leaderboard_status: dict[str, Any],
    activity_status: dict[str, Any],
    tracked_activity_status: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated = generated_at or _now_iso()
    generated_dt = _parse_iso_datetime(generated) or _now()
    recent_cutoff = generated_dt - RECENT_TRADE_WINDOW
    tracked_traders = select_tracked_traders(leaderboard_rows)
    tracked_wallets = {str(row.get("wallet", "")).lower() for row in tracked_traders}
    recent_trades = [
        dict(row)
        for row in activity_rows
        if str(row.get("trader_wallet", "")).lower() in tracked_wallets
        and (_parse_iso_datetime(row.get("trade_at")) or generated_dt) >= recent_cutoff
    ]
    if tracked_activity_rows:
        seen_trade_keys = {
            (
                str(row.get("trade_at", "") or "").strip(),
                str(row.get("trader_wallet", "") or "").strip().lower(),
                str(row.get("event_id", "") or "").strip(),
                str(row.get("outcome", "") or "").strip(),
                str(row.get("side", "") or "").strip().lower(),
            )
            for row in recent_trades
        }
        for row in tracked_activity_rows:
            trade_dt = _parse_iso_datetime(row.get("trade_at")) or generated_dt
            if trade_dt < recent_cutoff:
                continue
            trade_key = (
                str(row.get("trade_at", "") or "").strip(),
                str(row.get("trader_wallet", "") or "").strip().lower(),
                str(row.get("event_id", "") or "").strip(),
                str(row.get("outcome", "") or "").strip(),
                str(row.get("side", "") or "").strip().lower(),
            )
            if trade_key in seen_trade_keys:
                continue
            recent_trades.append(dict(row))
            seen_trade_keys.add(trade_key)
        recent_trades.sort(key=lambda row: row.get("trade_at", ""), reverse=True)

    overall_status = "ok"
    if str(leaderboard_status.get("status", "")) not in {"fresh", "cached", "ok"}:
        overall_status = "degraded"
    if str(activity_status.get("status", "")) not in {"fresh", "cached", "ok"}:
        overall_status = "degraded"
    if tracked_activity_status and str(tracked_activity_status.get("status", "")) not in {"fresh", "cached", "ok", "partial"}:
        overall_status = "degraded"
    if leaderboard_status.get("stale") or activity_status.get("stale"):
        overall_status = "stale"

    return {
        "generated_at": generated,
        "as_of": generated,
        "leaderboard_latest": leaderboard_rows,
        "activity_latest": activity_rows,
        "tracked_traders": tracked_traders,
        "recent_trades": recent_trades,
        "source_status": {
            "status": overall_status,
            "tracked_trader_count": len(tracked_traders),
            "recent_trade_count": len(recent_trades),
            "leaderboard": leaderboard_status,
            "activity": activity_status,
            "tracked_activity": tracked_activity_status or {},
        },
    }


def write_run_artifacts(manifest: dict[str, Any], output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "leaderboard_latest.json").write_text(
        json.dumps(manifest.get("leaderboard_latest", []), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (output_dir / "activity_latest.json").write_text(
        json.dumps(manifest.get("activity_latest", []), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (output_dir / "trader_signals_latest.json").write_text(
        json.dumps(
            {
                "generated_at": manifest.get("generated_at"),
                "as_of": manifest.get("as_of"),
                "tracked_traders": manifest.get("tracked_traders", []),
                "recent_trades": manifest.get("recent_trades", []),
                "source_status": manifest.get("source_status", {}),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return manifest


class PolymarketAnalyticsScraper(BrowserAutomation):
    SERVICE_NAME = "polymarketanalytics"
    USE_CHROME_PROFILE = False

    def __init__(self, headless: bool = True, slow_mo: int = 50, use_chrome: bool | None = None):
        super().__init__(headless=headless, slow_mo=slow_mo, use_chrome=use_chrome)
        self.output_dir = OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def is_logged_in(self) -> bool:
        return True

    def login(self):
        return None

    def _navigate(self, url: str, selector: str) -> None:
        self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
        self.page.wait_for_selector(selector, timeout=30000)

    def _fetch_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        response = requests.get(url, params=params, headers=HTTP_HEADERS, timeout=30)
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}

    def _read_cached_rows(self, filename: str) -> tuple[list[dict[str, Any]], str]:
        path = self.output_dir / filename
        if not path.exists():
            return [], ""
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return [], ""
        if isinstance(payload, list):
            return payload, _now_iso()
        if isinstance(payload, dict):
            return payload.get("data", []), str(payload.get("generated_at", "") or "")
        return [], ""

    def fetch_leaderboard(self, *, force: bool = False, limit: int = 200) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        cache_path = self.output_dir / "leaderboard_latest.json"
        if not force and cache_path.exists():
            cache_generated = datetime.fromtimestamp(cache_path.stat().st_mtime, tz=timezone.utc).astimezone().isoformat()
            if _status_age_minutes(cache_generated) is not None and _status_age_minutes(cache_generated) <= LEADERBOARD_CACHE_MAX_AGE.total_seconds() / 60.0:
                cached_rows = json.loads(cache_path.read_text(encoding="utf-8"))
                return cached_rows, _status_payload(
                    status="cached",
                    generated_at=cache_generated,
                    row_count=len(cached_rows),
                    used_cache=True,
                    stale_after=LEADERBOARD_CACHE_MAX_AGE,
                )

        try:
            payload = self._fetch_json(
                LEADERBOARD_API_URL,
                {
                    "tag": "Overall",
                    "sortDirection": "ASC",
                    "limit": limit,
                    "offset": 0,
                    "sortColumn": "rank",
                    "minPnL": 0,
                    "maxPnL": 0,
                    "minActivePositions": 0,
                    "maxActivePositions": 0,
                    "minWinAmount": 0,
                    "maxWinAmount": 0,
                    "minLossAmount": 0,
                    "maxLossAmount": 0,
                    "minWinRate": 0,
                    "maxWinRate": 0,
                    "minCurrentValue": 0,
                    "maxCurrentValue": 0,
                    "minTotalPositions": 0,
                    "maxTotalPositions": 0,
                },
            )
            rows = normalize_leaderboard_rows(payload.get("data", []))
            generated_at = _now_iso()
            return rows, _status_payload(
                status="fresh",
                generated_at=generated_at,
                row_count=len(rows),
                used_cache=False,
                stale_after=LEADERBOARD_CACHE_MAX_AGE,
            )
        except Exception as exc:
            if cache_path.exists():
                cached_rows = json.loads(cache_path.read_text(encoding="utf-8"))
                cache_generated = datetime.fromtimestamp(cache_path.stat().st_mtime, tz=timezone.utc).astimezone().isoformat()
                return cached_rows, _status_payload(
                    status="cached",
                    generated_at=cache_generated,
                    row_count=len(cached_rows),
                    used_cache=True,
                    error=str(exc),
                    stale_after=LEADERBOARD_CACHE_MAX_AGE,
                )
            return [], _status_payload(
                status="error",
                generated_at=_now_iso(),
                row_count=0,
                used_cache=False,
                error=str(exc),
                stale_after=LEADERBOARD_CACHE_MAX_AGE,
            )

    def fetch_activity(
        self,
        *,
        pages: int = DEFAULT_ACTIVITY_PAGES,
        page_size: int = DEFAULT_ACTIVITY_PAGE_SIZE,
        tracked_wallets: set[str] | None = None,
        target_tracked_hits: int = TARGET_TRACKED_ACTIVITY_HITS,
        min_pages: int = MIN_ACTIVITY_PAGES,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        cache_path = self.output_dir / "activity_latest.json"
        collected: list[dict[str, Any]] = []
        try:
            normalized_tracked_wallets = {str(wallet).strip().lower() for wallet in (tracked_wallets or set()) if str(wallet).strip()}
            tracked_hits = 0
            page_limit = max(1, int(pages))
            page_size_value = max(1, int(page_size))
            min_page_count = max(1, int(min_pages))
            target_hits = max(1, int(target_tracked_hits))

            for page_index in range(page_limit):
                payload = self._fetch_json(
                    ACTIVITY_API_URL,
                    {
                        "min_value": 0,
                        "max_value": 1000000,
                        "sortBy": "trade_dttm",
                        "sortDesc": "true",
                        "limit": page_size_value,
                        "offset": page_index * page_size_value,
                    },
                )
                batch = payload.get("data", [])
                if not isinstance(batch, list) or not batch:
                    break
                collected.extend(batch)
                if normalized_tracked_wallets:
                    tracked_hits += sum(
                        1
                        for row in batch
                        if str(row.get("trader_id", "")).strip().lower() in normalized_tracked_wallets
                    )
                if len(batch) < page_size_value:
                    break
                if (
                    normalized_tracked_wallets
                    and page_index + 1 >= min_page_count
                    and tracked_hits >= target_hits
                ):
                    break
            rows = normalize_activity_rows(collected)
            generated_at = _now_iso()
            return rows, _status_payload(
                status="fresh",
                generated_at=generated_at,
                row_count=len(rows),
                used_cache=False,
                stale_after=ACTIVITY_CACHE_MAX_AGE,
            )
        except Exception as exc:
            if collected:
                rows = normalize_activity_rows(collected)
                return rows, _status_payload(
                    status="partial",
                    generated_at=_now_iso(),
                    row_count=len(rows),
                    used_cache=False,
                    error=str(exc),
                    stale_after=ACTIVITY_CACHE_MAX_AGE,
                )
            if cache_path.exists():
                cached_rows = json.loads(cache_path.read_text(encoding="utf-8"))
                cache_generated = datetime.fromtimestamp(cache_path.stat().st_mtime, tz=timezone.utc).astimezone().isoformat()
                return cached_rows, _status_payload(
                    status="cached",
                    generated_at=cache_generated,
                    row_count=len(cached_rows),
                    used_cache=True,
                    error=str(exc),
                    stale_after=ACTIVITY_CACHE_MAX_AGE,
                )
            return [], _status_payload(
                status="error",
                generated_at=_now_iso(),
                row_count=0,
                used_cache=False,
                error=str(exc),
                stale_after=ACTIVITY_CACHE_MAX_AGE,
            )

    def fetch_tracked_trader_activity(
        self,
        *,
        tracked_traders: list[dict[str, Any]],
        per_trader_limit: int = 5,
        max_traders: int = 10,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        try:
            for trader in tracked_traders[: max(1, int(max_traders))]:
                wallet = str(trader.get("wallet", "") or "").strip()
                if not wallet:
                    continue
                payload = self._fetch_json(
                    ACTIVITY_API_URL,
                    {
                        "trader_id": wallet,
                        "limit": max(1, int(per_trader_limit)),
                        "offset": 0,
                        "sortBy": "trade_dttm",
                        "sortDesc": "true",
                        "min_value": 0,
                        "max_value": 1000000,
                    },
                )
                batch = payload.get("data", [])
                if not isinstance(batch, list) or not batch:
                    continue
                collected.extend(batch)
            rows = normalize_activity_rows(collected)
            return rows, _status_payload(
                status="fresh",
                generated_at=_now_iso(),
                row_count=len(rows),
                used_cache=False,
                stale_after=ACTIVITY_CACHE_MAX_AGE,
            )
        except Exception as exc:
            if collected:
                rows = normalize_activity_rows(collected)
                return rows, _status_payload(
                    status="partial",
                    generated_at=_now_iso(),
                    row_count=len(rows),
                    used_cache=False,
                    error=str(exc),
                    stale_after=ACTIVITY_CACHE_MAX_AGE,
                )
            return [], _status_payload(
                status="error",
                generated_at=_now_iso(),
                row_count=0,
                used_cache=False,
                error=str(exc),
                stale_after=ACTIVITY_CACHE_MAX_AGE,
            )

    def run(
        self,
        *,
        force_leaderboard: bool = False,
        activity_pages: int = DEFAULT_ACTIVITY_PAGES,
        activity_page_size: int = DEFAULT_ACTIVITY_PAGE_SIZE,
    ) -> dict[str, Any]:
        leaderboard_rows, leaderboard_status = self.fetch_leaderboard(force=force_leaderboard)
        tracked_traders = select_tracked_traders(leaderboard_rows)
        tracked_wallets = {str(row.get("wallet", "")).strip().lower() for row in tracked_traders}
        activity_rows, activity_status = self.fetch_activity(
            pages=activity_pages,
            page_size=activity_page_size,
            tracked_wallets=tracked_wallets,
        )
        tracked_activity_rows, tracked_activity_status = self.fetch_tracked_trader_activity(
            tracked_traders=tracked_traders,
        )
        manifest = build_trader_signals_manifest(
            leaderboard_rows=leaderboard_rows,
            activity_rows=activity_rows,
            tracked_activity_rows=tracked_activity_rows,
            leaderboard_status=leaderboard_status,
            activity_status=activity_status,
            tracked_activity_status=tracked_activity_status,
            generated_at=_now_iso(),
        )
        write_run_artifacts(manifest, output_dir=self.output_dir)
        return manifest
