from __future__ import annotations

import csv
import io
import json
import re
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from zoneinfo import ZoneInfo


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRAPED_DATA_DIR = REPO_ROOT / "scraped_data"
OUTPUT_DIR = REPO_ROOT / "output"
HKT = ZoneInfo("Asia/Hong_Kong")

SMM_SOURCE_URL = (
    "https://docs.google.com/spreadsheets/d/1O6OhS7ciA8zwfycBfGPbP2fWJnR0pn2UUvFZVDP9jpE/"
    "pub?gid=1082103394&output=csv"
)
AASTOCKS_HIGH_URL = "https://www.aastocks.com/en/stocks/market/high-low-stocks.aspx?catg=1&period=3&t=1"
AASTOCKS_LOW_URL = "https://www.aastocks.com/en/stocks/market/high-low-stocks.aspx?catg=1&period=3&t=2"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def now_hkt_iso() -> str:
    return datetime.now(HKT).isoformat()


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=HKT)
    return dt.astimezone(HKT)


def format_market_date(value: str | None) -> str:
    if not value:
        return "N/A"
    return date.fromisoformat(value).strftime("%b %d, %Y")


def format_hkt_timestamp(value: str | None) -> str:
    dt = parse_iso_datetime(value)
    if dt is None:
        return "N/A"
    return dt.strftime("%b %d, %Y %H:%M HKT")


def js_single_quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def safe_float(value: Any) -> float | None:
    if value in (None, "", "N/A", "No Profit"):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").replace("%", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def safe_int(value: Any) -> int | None:
    number = safe_float(value)
    if number is None:
        return None
    return int(round(number))


def pct(count: int | None, total: int | None) -> float | None:
    if count is None or total in (None, 0):
        return None
    return round((count / total) * 100.0, 1)


def business_days_between(start: date, end: date) -> int:
    if start >= end:
        return 0
    days = 0
    current = start
    while current < end:
        current += timedelta(days=1)
        if current.weekday() < 5:
            days += 1
    return days


def evaluate_source_status(
    market_date: str | None,
    last_attempt_ok: bool,
    now_iso: str | None = None,
) -> str:
    if not last_attempt_ok:
        return "error"
    if not market_date:
        return "stale"
    current = parse_iso_datetime(now_iso) or datetime.now(HKT)
    # Strict same-HKT-day rule: only the current HKT calendar day counts as fresh.
    # Anything captured on a previous day (even yesterday) is stale, so Telegram/CIO
    # consumers never read across-day artifacts.
    return "fresh" if date.fromisoformat(market_date) == current.date() else "stale"


def _signal_badges(score: float | None, tone: str) -> tuple[str, str]:
    if score is None:
        return "N/A", "badge-caution"
    if score >= 65:
        return "GREEN", "badge-bullish"
    if score <= 35:
        return "RED", "badge-bearish"
    if tone == "caution":
        return "AMBER", "badge-caution"
    return "YELLOW", "badge-neutral"


def parse_smm_csv(csv_text: str, captured_at: str | None = None) -> dict[str, Any]:
    rows = list(csv.reader(io.StringIO(csv_text)))
    data_rows = [row for row in rows if row and row[0] and re.match(r"^\d{1,2}/\d{1,2}/\d{4}$", row[0].strip())]
    if not data_rows:
        raise ValueError("SMM CSV did not contain any dated rows")

    latest = data_rows[0]
    previous = data_rows[1] if len(data_rows) > 1 else None
    fifth_prior = data_rows[5] if len(data_rows) > 5 else None

    market_date = datetime.strptime(latest[0].strip(), "%m/%d/%Y").date().isoformat()
    universe = safe_int(latest[13])
    spx_close = safe_float(latest[15])
    prev_spx = safe_float(previous[15]) if previous else None
    fifth_spx = safe_float(fifth_prior[15]) if fifth_prior else None

    spx_change_1d = None
    if spx_close and prev_spx:
        spx_change_1d = round(((spx_close / prev_spx) - 1.0) * 100.0, 2)
    spx_change_5d = None
    if spx_close and fifth_spx:
        spx_change_5d = round(((spx_close / fifth_spx) - 1.0) * 100.0, 2)

    metrics = {
        "universeCount": universe,
        "up4Count": safe_int(latest[1]),
        "down4Count": safe_int(latest[2]),
        "ratio5d": safe_float(latest[3]),
        "ratio10d": safe_float(latest[4]),
        "qtrUp25Count": safe_int(latest[5]),
        "qtrDown25Count": safe_int(latest[6]),
        "monthUp25Count": safe_int(latest[7]),
        "monthDown25Count": safe_int(latest[8]),
        "monthUp50Count": safe_int(latest[9]),
        "monthDown50Count": safe_int(latest[10]),
        "up13In34dCount": safe_int(latest[11]),
        "down13In34dCount": safe_int(latest[12]),
        "ma40Pct": safe_float(latest[14]),
        "spxClose": spx_close,
        "spxChange1dPct": spx_change_1d,
        "spxChange5dPct": spx_change_5d,
    }
    metrics["up4Pct"] = pct(metrics["up4Count"], universe)
    metrics["down4Pct"] = pct(metrics["down4Count"], universe)
    metrics["qtrUp25Pct"] = pct(metrics["qtrUp25Count"], universe)
    metrics["qtrDown25Pct"] = pct(metrics["qtrDown25Count"], universe)
    metrics["monthUp25Pct"] = pct(metrics["monthUp25Count"], universe)
    metrics["monthDown25Pct"] = pct(metrics["monthDown25Count"], universe)
    metrics["up13In34dPct"] = pct(metrics["up13In34dCount"], universe)
    metrics["down13In34dPct"] = pct(metrics["down13In34dCount"], universe)

    score = 50.0
    if metrics["ma40Pct"] is not None:
        score += (metrics["ma40Pct"] - 25.0) * 0.7
    if metrics["ratio5d"] is not None:
        score += (metrics["ratio5d"] - 1.0) * 18.0
    if metrics["ratio10d"] is not None:
        score += (metrics["ratio10d"] - 1.0) * 14.0
    if metrics["qtrDown25Pct"] is not None and metrics["qtrUp25Pct"] is not None:
        score -= max(0.0, metrics["qtrDown25Pct"] - metrics["qtrUp25Pct"]) * 0.45
    score = round(clamp(score, 0.0, 100.0), 1)

    if metrics["ma40Pct"] is not None and metrics["ma40Pct"] < 20:
        signal_label = "OVERSOLD REBOUND WATCH"
        signal_tone = "neutral"
    elif metrics["ratio10d"] is not None and metrics["ratio10d"] < 0.8:
        signal_label = "BEARISH PARTICIPATION"
        signal_tone = "bearish"
    elif metrics["ratio10d"] is not None and metrics["ratio10d"] > 1.05 and (metrics["ma40Pct"] or 0) > 35:
        signal_label = "BULLISH PARTICIPATION"
        signal_tone = "bullish"
    else:
        signal_label = "NEUTRAL BREADTH"
        signal_tone = "neutral"

    thesis = (
        f"Public SMM sheet last closed on {format_market_date(market_date)} with MA40 at "
        f"{metrics['ma40Pct']:.2f}% and 10-day ratio at {metrics['ratio10d']:.2f}. "
        f"Quarter breadth shows {metrics['qtrDown25Count']:,} stocks down 25%+ versus "
        f"{metrics['qtrUp25Count']:,} up 25%+, so participation is still fragile."
    )

    return {
        "sourceName": "SMM Google Sheet",
        "capturedAt": captured_at or now_hkt_iso(),
        "marketDate": market_date,
        "score": score,
        "signalLabel": signal_label,
        "signalTone": signal_tone,
        "metrics": metrics,
        "thesis": thesis,
    }


def normalize_deepvue_payload(payload: dict[str, Any]) -> dict[str, Any]:
    captured_at = payload.get("timestamp") or now_hkt_iso()
    captured_dt = parse_iso_datetime(captured_at)
    market_date = (captured_dt or datetime.now(HKT)).date().isoformat()

    breadth = payload.get("breadth") or {}
    stages = payload.get("stages") or {}

    metrics = {
        "advanceCount": safe_int(breadth.get("advance_count")),
        "declineCount": safe_int(breadth.get("decline_count")),
        "advanceDeclinePct": safe_int(breadth.get("advance_decline_pct")),
        "highsCount": safe_int(breadth.get("highs_count")),
        "lowsCount": safe_int(breadth.get("lows_count")),
        "newHighsVsLowsPct": safe_int(breadth.get("new_highs_vs_lows_pct")),
        "upFromOpenPct": safe_int(breadth.get("up_from_open_pct")),
        "upVolumePct": safe_int(breadth.get("up_volume_pct")),
        "up4Pct": safe_int(breadth.get("up_4pct_pct")),
        "stage1Count": safe_int((stages.get("stage_1") or {}).get("count")),
        "stage1Pct": safe_int((stages.get("stage_1") or {}).get("pct")),
        "stage2Count": safe_int((stages.get("stage_2") or {}).get("count")),
        "stage2Pct": safe_int((stages.get("stage_2") or {}).get("pct")),
        "stage3Count": safe_int((stages.get("stage_3") or {}).get("count")),
        "stage3Pct": safe_int((stages.get("stage_3") or {}).get("pct")),
        "stage4Count": safe_int((stages.get("stage_4") or {}).get("count")),
        "stage4Pct": safe_int((stages.get("stage_4") or {}).get("pct")),
    }

    score = 50.0
    score += ((metrics["advanceDeclinePct"] or 50) - 50) * 0.6
    score += ((metrics["newHighsVsLowsPct"] or 50) - 50) * 0.25
    score += ((metrics["stage2Pct"] or 0) - (metrics["stage4Pct"] or 0)) * 0.45
    score = round(clamp(score, 0.0, 100.0), 1)

    if (metrics["stage4Pct"] or 0) >= 50 or score <= 35:
        signal_label = "BROAD DOWNTREND"
        signal_tone = "bearish"
    elif (metrics["stage2Pct"] or 0) > (metrics["stage4Pct"] or 0) and (metrics["advanceDeclinePct"] or 0) > 55:
        signal_label = "BREADTH IMPROVING"
        signal_tone = "bullish"
    else:
        signal_label = "MIXED STRUCTURE"
        signal_tone = "neutral"

    thesis = (
        f"Stage 4 accounts for {metrics['stage4Pct']}% of the universe against "
        f"{metrics['stage2Pct']}% in Stage 2, while only {metrics['advanceDeclinePct']}% "
        f"of stocks are advancing. DeepVue still reads as structurally weak."
    )

    return {
        "sourceName": "DeepVue Market Overview",
        "capturedAt": captured_at,
        "marketDate": market_date,
        "score": score,
        "signalLabel": signal_label,
        "signalTone": signal_tone,
        "metrics": metrics,
        "thesis": thesis,
    }


def _extract_aastocks_last_update(html: str) -> str | None:
    meta_match = re.search(r'<meta name="aa-update" content="([^"]+)"', html)
    if meta_match:
        raw = meta_match.group(1).strip()
        return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=HKT).isoformat()
    text_match = re.search(r"Last Update:\s*([0-9/]{10}\s+[0-9:]{5})", html)
    if text_match:
        raw = text_match.group(1).strip()
        return datetime.strptime(raw, "%Y/%m/%d %H:%M").replace(tzinfo=HKT).isoformat()
    return None


def _count_aastocks_rows(html: str) -> int:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#tblTS2.HIGHLOWSTOCKS")
    if table is None:
        raise ValueError("AASTOCKS high/low table #tblTS2.HIGHLOWSTOCKS was not found")
    return len(table.select("tbody tr"))


def parse_aastocks_high_low_pages(
    high_html: str,
    low_html: str,
    captured_at: str | None = None,
) -> dict[str, Any]:
    captured = captured_at or _extract_aastocks_last_update(high_html) or now_hkt_iso()
    captured_dt = parse_iso_datetime(captured)
    market_date = (captured_dt or datetime.now(HKT)).date().isoformat()

    new_highs = _count_aastocks_rows(high_html)
    new_lows = _count_aastocks_rows(low_html)
    ratio = round(new_highs / new_lows, 2) if new_lows else None

    thesis = (
        f"AASTOCKS refreshed highs/lows on {format_market_date(market_date)} with "
        f"{new_highs} stocks at 52-week highs and {new_lows} at 52-week lows. "
        "Moving-average breadth is unavailable in the current scraper and is shown as N/A."
    )

    return {
        "sourceName": "AASTOCKS",
        "capturedAt": captured,
        "marketDate": market_date,
        "score": None,
        "signalLabel": "PARTIAL DATA",
        "signalTone": "caution",
        "metrics": {
            "sourceName": "AASTOCKS",
            "liquidStockCount": None,
            "pctAbove20Ma": None,
            "pctAbove50Ma": None,
            "pctAbove200Ma": None,
            "advancePct": None,
            "declinePct": None,
            "advanceDeclineRatio": None,
            "newHighs52w": new_highs,
            "newLows52w": new_lows,
            "highLowRatio": ratio,
            "up20In63dPct": None,
            "strongUpPct": None,
            "strongDownPct": None,
        },
        "thesis": thesis,
    }


def unavailable_source(name: str, message: str) -> dict[str, Any]:
    return {
        "sourceName": name,
        "capturedAt": None,
        "marketDate": None,
        "score": None,
        "signalLabel": "UNAVAILABLE",
        "signalTone": "caution",
        "metrics": {},
        "thesis": message,
        "lastError": message,
    }


def _coerce_source_payload(source_key: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        if source_key == "smm":
            return unavailable_source("SMM Google Sheet", "SMM snapshot has not been generated yet.")
        if source_key == "deepvue":
            return unavailable_source("DeepVue Market Overview", "DeepVue artifact has not been captured yet.")
        return unavailable_source("AASTOCKS", "HK breadth artifact has not been captured yet.")

    if source_key == "deepvue" and "metrics" not in payload:
        return normalize_deepvue_payload(payload)
    if source_key == "smm" and "metrics" not in payload:
        raise ValueError("SMM payload is missing normalized metrics")
    if source_key == "hkBreadth" and "metrics" not in payload:
        raise ValueError("HK breadth payload is missing normalized metrics")
    return payload


def build_market_breadth_snapshot(
    smm_payload: dict[str, Any] | None,
    deepvue_payload: dict[str, Any] | None,
    hk_payload: dict[str, Any] | None,
    refresh_status: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    refresh_sources = (refresh_status or {}).get("sources", {})
    snapshot = {"generatedAt": generated_at or now_hkt_iso(), "sources": {}}

    for source_key, raw_payload in (
        ("smm", smm_payload),
        ("deepvue", deepvue_payload),
        ("hkBreadth", hk_payload),
    ):
        payload = _coerce_source_payload(source_key, raw_payload)
        refresh_meta = refresh_sources.get(source_key, {})
        last_attempt_ok = refresh_meta.get("ok", True)
        payload["status"] = evaluate_source_status(
            payload.get("marketDate"),
            last_attempt_ok=last_attempt_ok,
            now_iso=snapshot["generatedAt"],
        )
        if refresh_meta.get("lastAttemptAt"):
            payload["lastAttemptAt"] = refresh_meta["lastAttemptAt"]
        if refresh_meta.get("error"):
            payload["lastError"] = refresh_meta["error"]
        snapshot["sources"][source_key] = payload

    return snapshot


def _format_count_pct(count: int | None, percentage: float | None) -> str:
    if count is None:
        return "N/A"
    if percentage is None:
        return f"{count:,}"
    return f"{count:,} ({percentage:.1f}%)"


def _format_float(value: float | None, decimals: int = 2, suffix: str = "") -> str:
    if value is None:
        return "N/A"
    return f"{value:.{decimals}f}{suffix}"


def _status_badge(status: str) -> tuple[str, str]:
    if status == "fresh":
        return "FRESH", "badge-info"
    if status == "stale":
        return "STALE", "badge-caution"
    return "ERROR", "badge-bearish"


def _market_badge(source: dict[str, Any]) -> tuple[str, str]:
    return _signal_badges(source.get("score"), source.get("signalTone", "neutral"))


def _score_ring(source: dict[str, Any]) -> str:
    score = source.get("score")
    tone = source.get("signalTone", "neutral")
    color = {
        "bullish": "var(--green)",
        "bearish": "var(--red)",
        "caution": "var(--orange)",
        "neutral": "var(--yellow)",
    }.get(tone, "var(--accent)")
    score_text = "--" if score is None else f"{score:.1f}"
    compact = "width:60px; height:60px; font-size:18px;" if score is None else ""
    return (
        f'<div class="score-ring" style="border: 3px solid {color}; color: {color}; {compact}">{score_text}</div>'
    )


def _date_line(source: dict[str, Any], extra: str | None = None) -> str:
    parts = [format_market_date(source.get("marketDate"))]
    if extra:
        parts.append(extra)
    captured_dt = parse_iso_datetime(source.get("capturedAt"))
    captured_text = "N/A" if captured_dt is None else captured_dt.strftime("%H:%M HKT")
    parts.append(f"captured {captured_text}")
    return " &bull; ".join(parts)


def _render_meter(label: str, value_text: str, width_pct: float | None, color_class: str) -> str:
    width = 0 if width_pct is None else clamp(width_pct, 0, 100)
    return (
        '<div class="breadth-gauge">'
        f'<div class="breadth-stat"><span class="label">{escape(label)}</span><span class="value">{escape(value_text)}</span></div>'
        f'<div class="meter"><div class="meter-fill {color_class}" style="width:{width:.1f}%"></div></div>'
        "</div>"
    )


def _render_smm_card(source: dict[str, Any]) -> str:
    freshness_label, freshness_class = _status_badge(source["status"])
    signal_label, signal_class = _market_badge(source)
    metrics = source["metrics"]
    universe = metrics.get("universeCount")
    extra = f"{universe:,} stocks" if universe else None
    return f"""
  <div class="card">
    <div class="card-header">
      {_score_ring(source)}
      <div>
        <div class="card-title"><a href="smm.html" style="color:var(--text);text-decoration:none;">US Market Monitor (SMM)</a></div>
        <div style="font-size:12px;color:var(--muted);">{_date_line(source, extra)}</div>
      </div>
      <div style="margin-left:auto;text-align:right;">
        <span class="badge {freshness_class}">{freshness_label}</span>
        <span class="badge {signal_class}">{escape(signal_label)}</span>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
      <div>
        <div style="font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">SMM Primary</div>
        {_render_meter("Daily Up ≥4%", _format_count_pct(metrics.get("up4Count"), metrics.get("up4Pct")), metrics.get("up4Pct"), "meter-green")}
        {_render_meter("Daily Down ≥4%", _format_count_pct(metrics.get("down4Count"), metrics.get("down4Pct")), metrics.get("down4Pct"), "meter-red")}
        {_render_meter("5-Day Ratio", _format_float(metrics.get("ratio5d")), (metrics.get("ratio5d") or 0) * 50, "meter-yellow")}
        {_render_meter("10-Day Ratio", _format_float(metrics.get("ratio10d")), (metrics.get("ratio10d") or 0) * 50, "meter-yellow")}
        {_render_meter("Qtr Up ≥25%", _format_count_pct(metrics.get("qtrUp25Count"), metrics.get("qtrUp25Pct")), metrics.get("qtrUp25Pct"), "meter-green")}
        {_render_meter("Qtr Down ≥25%", _format_count_pct(metrics.get("qtrDown25Count"), metrics.get("qtrDown25Pct")), metrics.get("qtrDown25Pct"), "meter-red")}
      </div>
      <div>
        <div style="font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">SMM Secondary</div>
        {_render_meter("MA40 (% > 40MA)", _format_float(metrics.get("ma40Pct"), suffix="%"), metrics.get("ma40Pct"), "meter-blue")}
        {_render_meter("34d Up ≥13%", _format_count_pct(metrics.get("up13In34dCount"), metrics.get("up13In34dPct")), metrics.get("up13In34dPct"), "meter-green")}
        {_render_meter("34d Down ≥13%", _format_count_pct(metrics.get("down13In34dCount"), metrics.get("down13In34dPct")), metrics.get("down13In34dPct"), "meter-red")}
        {_render_meter("Month Up ≥25%", _format_count_pct(metrics.get("monthUp25Count"), metrics.get("monthUp25Pct")), metrics.get("monthUp25Pct"), "meter-green")}
        {_render_meter("Month Down ≥25%", _format_count_pct(metrics.get("monthDown25Count"), metrics.get("monthDown25Pct")), metrics.get("monthDown25Pct"), "meter-red")}
        <div class="breadth-gauge">
          <div class="breadth-stat"><span class="label">S&amp;P 500</span><span class="value">{_format_float(metrics.get("spxClose"))}</span></div>
          <div class="breadth-stat"><span class="label">SPX 1D</span><span class="value">{_format_float(metrics.get("spxChange1dPct"), suffix="%")}</span></div>
          <div class="breadth-stat"><span class="label">SPX 5D</span><span class="value">{_format_float(metrics.get("spxChange5dPct"), suffix="%")}</span></div>
        </div>
      </div>
    </div>
    <div class="thesis" style="margin-top:12px;"><strong>SMM:</strong> {escape(source["thesis"])}</div>
  </div>
""".strip()


def _render_deepvue_card(source: dict[str, Any]) -> str:
    freshness_label, freshness_class = _status_badge(source["status"])
    signal_label, signal_class = _market_badge(source)
    metrics = source["metrics"]
    advance_decline = (
        f"{metrics.get('advanceCount'):,} / {metrics.get('declineCount'):,} ({metrics.get('advanceDeclinePct')}%)"
    )
    highs_lows = f"{metrics.get('highsCount'):,} / {metrics.get('lowsCount'):,} ({metrics.get('newHighsVsLowsPct')}%)"
    return f"""
  <div class="card">
    <div class="card-header">
      <div class="card-icon" style="background:rgba(248,81,73,0.2);color:var(--red);">DV</div>
      <div>
        <div class="card-title">DV US Market</div>
        <div style="font-size:12px;color:var(--muted);">{_date_line(source)}</div>
      </div>
      <div style="margin-left:auto;text-align:right;">
        <span class="badge {freshness_class}">{freshness_label}</span>
        <span class="badge {signal_class}">{escape(signal_label)}</span>
      </div>
    </div>
    <div class="card-subtitle">Stage Analysis &amp; Breadth Overview</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
      <div>
        <div style="font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">Breadth Indicators</div>
        {_render_meter("Advance / Decline", advance_decline, metrics.get("advanceDeclinePct"), "meter-red")}
        {_render_meter("New Highs vs Lows", highs_lows, metrics.get("newHighsVsLowsPct"), "meter-red")}
        {_render_meter("Up from Open", _format_float(metrics.get("upFromOpenPct"), decimals=0, suffix="%"), metrics.get("upFromOpenPct"), "meter-red")}
        {_render_meter("Up Volume", _format_float(metrics.get("upVolumePct"), decimals=0, suffix="%"), metrics.get("upVolumePct"), "meter-red")}
        {_render_meter("Up ≥4%", _format_float(metrics.get("up4Pct"), decimals=0, suffix="%"), metrics.get("up4Pct"), "meter-red")}
      </div>
      <div>
        <div style="font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">Weinstein Stage Distribution</div>
        {_render_meter("Stage 1 (Base)", f"{metrics.get('stage1Count'):,} ({metrics.get('stage1Pct')}%)", metrics.get("stage1Pct"), "meter-blue")}
        {_render_meter("Stage 2 (Uptrend)", f"{metrics.get('stage2Count'):,} ({metrics.get('stage2Pct')}%)", metrics.get("stage2Pct"), "meter-green")}
        {_render_meter("Stage 3 (Top)", f"{metrics.get('stage3Count'):,} ({metrics.get('stage3Pct')}%)", metrics.get("stage3Pct"), "meter-yellow")}
        {_render_meter("Stage 4 (Decline)", f"{metrics.get('stage4Count'):,} ({metrics.get('stage4Pct')}%)", metrics.get("stage4Pct"), "meter-red")}
      </div>
    </div>
    <div class="thesis" style="margin-top:12px;"><strong>DV:</strong> {escape(source["thesis"])}</div>
  </div>
""".strip()


def _render_hk_card(source: dict[str, Any]) -> str:
    freshness_label, freshness_class = _status_badge(source["status"])
    signal_label, signal_class = _market_badge(source)
    metrics = source["metrics"]

    def _na_pct(value: float | None) -> str:
        return "N/A" if value is None else f"{value:.1f}%"

    adv_decl = "N/A"
    if metrics.get("advancePct") is not None and metrics.get("declinePct") is not None and metrics.get("advanceDeclineRatio") is not None:
        adv_decl = (
            f"{metrics['advancePct']:.1f}% / {metrics['declinePct']:.1f}% "
            f"({metrics['advanceDeclineRatio']:.2f}x)"
        )
    high_low = "N/A"
    if metrics.get("newHighs52w") is not None and metrics.get("newLows52w") is not None:
        ratio = metrics.get("highLowRatio")
        ratio_text = "N/A" if ratio is None else f"{ratio:.2f}x"
        high_low = f"{metrics['newHighs52w']} / {metrics['newLows52w']} ({ratio_text})"

    error_html = ""
    if source.get("lastError"):
        error_html = (
            f'<div style="font-size:11px;color:var(--orange);margin-top:6px;">Latest issue: '
            f'{escape(source["lastError"])}</div>'
        )

    return f"""
  <div class="card">
    <div class="card-header">
      {_score_ring(source)}
      <div>
        <div class="card-title">Hong Kong Breadth</div>
        <div style="font-size:12px;color:var(--muted);">{_date_line(source, 'AASTOCKS')}</div>
      </div>
      <div style="margin-left:auto;text-align:right;">
        <span class="badge {freshness_class}">{freshness_label}</span>
        <span class="badge {signal_class}">{escape(signal_label)}</span>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
      <div>
        <div style="font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">Moving Average Participation</div>
        {_render_meter("% Above 20MA", _na_pct(metrics.get("pctAbove20Ma")), metrics.get("pctAbove20Ma"), "meter-red")}
        {_render_meter("% Above 50MA", _na_pct(metrics.get("pctAbove50Ma")), metrics.get("pctAbove50Ma"), "meter-yellow")}
        {_render_meter("% Above 200MA", _na_pct(metrics.get("pctAbove200Ma")), metrics.get("pctAbove200Ma"), "meter-blue")}
      </div>
      <div>
        <div style="font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">Internals</div>
        {_render_meter("Advance / Decline", adv_decl, metrics.get("advancePct"), "meter-green")}
        <div class="breadth-gauge"><div class="breadth-stat"><span class="label">New 52W Highs / Lows</span><span class="value">{escape(high_low)}</span></div></div>
        {_render_meter("Up ≥20% in 63d", _na_pct(metrics.get("up20In63dPct")), metrics.get("up20In63dPct"), "meter-green")}
        <div class="breadth-gauge">
          <div class="breadth-stat"><span class="label">Strong Up (≥4%/day)</span><span class="value">{escape(_na_pct(metrics.get('strongUpPct')))}</span></div>
          <div class="breadth-stat"><span class="label">Strong Down</span><span class="value">{escape(_na_pct(metrics.get('strongDownPct')))}</span></div>
        </div>
      </div>
    </div>
    {error_html}
    <div class="thesis" style="margin-top:12px;"><strong>HK:</strong> {escape(source["thesis"])}</div>
  </div>
""".strip()


def build_breadth_section(snapshot: dict[str, Any]) -> str:
    generated_text = format_hkt_timestamp(snapshot["generatedAt"])
    return f"""
<!-- MARKET BREADTH -->
<div class="section-title" data-i18n="sec_breadth">Market Breadth</div>
<div class="grid">
  <div class="card card-full" style="padding:14px 18px;">
    <div style="font-size:12px;color:var(--muted);">
      <strong>Freshness note:</strong> Market Breadth auto-refreshes on schedule. This build used source artifacts generated at {generated_text}. Other dashboard sections may reflect manual updates in this phase.
    </div>
  </div>
  {_render_smm_card(snapshot["sources"]["smm"])}
  {_render_deepvue_card(snapshot["sources"]["deepvue"])}
  {_render_hk_card(snapshot["sources"]["hkBreadth"])}
</div>
""".strip()


def render_dashboard_html(template_html: str, snapshot: dict[str, Any]) -> str:
    generated_text = format_hkt_timestamp(snapshot["generatedAt"])
    subtitle_html = "All Sources &mdash; Market Breadth auto-refreshed; other sections remain manually curated"
    timestamp_html = (
        f"{generated_text} &bull; Market Breadth auto-refreshes on schedule &bull; "
        "Other sections may reflect manual updates"
    )
    footer_html = (
        "Generated by notion-autopublish scrapers &bull; Market Breadth auto-refreshed from source artifacts on "
        f"{generated_text} &bull; Other dashboard sections may reflect manual updates"
    )

    rendered = re.sub(
        r"<!-- MARKET BREADTH -->.*?<!-- MACRO & LIQUIDITY -->",
        build_breadth_section(snapshot) + "\n\n<!-- MACRO & LIQUIDITY -->",
        template_html,
        flags=re.S,
    )
    rendered = re.sub(
        r'(<div class="subtitle" data-i18n="subtitle">).*?(</div>)',
        rf"\1{subtitle_html}\2",
        rendered,
        count=1,
        flags=re.S,
    )
    rendered = re.sub(
        r'(<div class="timestamp" data-i18n="timestamp">).*?(</div>)',
        rf"\1{timestamp_html}\2",
        rendered,
        count=1,
        flags=re.S,
    )
    rendered = re.sub(
        r'(<div class="footer" data-i18n="footer">\s*).*?(\s*</div>)',
        rf"\1{footer_html}\2",
        rendered,
        count=1,
        flags=re.S,
    )

    replacements = {
        "subtitle": "All Sources - Market Breadth auto-refreshed; other sections remain manually curated",
        "timestamp": f"{generated_text} - Market Breadth auto-refreshes on schedule - Other sections may reflect manual updates",
        "footer": f"Generated by notion-autopublish scrapers - Market Breadth auto-refreshed from source artifacts on {generated_text} - Other dashboard sections may reflect manual updates",
    }
    for _ in range(2):
        for key, value in replacements.items():
            rendered = re.sub(
                rf"({key}:\s*')([^']*)(')",
                lambda match: match.group(1) + js_single_quote(value) + match.group(3),
                rendered,
                count=1,
            )

    return rendered


def _render_smm_card(source: dict[str, Any]) -> str:
    freshness_label, freshness_class = _status_badge(source["status"])
    signal_label, signal_class = _market_badge(source)
    metrics = source["metrics"]
    universe = metrics.get("universeCount")
    extra = f"{universe:,} stocks" if universe else None
    error_html = ""
    if source.get("lastError"):
        error_html = (
            f'<div style="font-size:11px;color:var(--orange);margin-top:6px;">Latest issue: '
            f'{escape(source["lastError"])}</div>'
        )
    return f"""
  <div class="card">
    <div class="card-header">
      {_score_ring(source)}
      <div>
        <div class="card-title"><a href="smm.html" style="color:var(--text);text-decoration:none;">US Market Monitor (SMM)</a></div>
        <div style="font-size:12px;color:var(--muted);">{_date_line(source, extra)}</div>
      </div>
      <div style="margin-left:auto;text-align:right;">
        <span class="badge {freshness_class}">{freshness_label}</span>
        <span class="badge {signal_class}">{escape(signal_label)}</span>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
      <div>
        <div style="font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">SMM Primary</div>
        {_render_meter("Daily Up >=4%", _format_count_pct(metrics.get("up4Count"), metrics.get("up4Pct")), metrics.get("up4Pct"), "meter-green")}
        {_render_meter("Daily Down >=4%", _format_count_pct(metrics.get("down4Count"), metrics.get("down4Pct")), metrics.get("down4Pct"), "meter-red")}
        {_render_meter("5-Day Ratio", _format_float(metrics.get("ratio5d")), (metrics.get("ratio5d") or 0) * 50, "meter-yellow")}
        {_render_meter("10-Day Ratio", _format_float(metrics.get("ratio10d")), (metrics.get("ratio10d") or 0) * 50, "meter-yellow")}
        {_render_meter("Qtr Up >=25%", _format_count_pct(metrics.get("qtrUp25Count"), metrics.get("qtrUp25Pct")), metrics.get("qtrUp25Pct"), "meter-green")}
        {_render_meter("Qtr Down >=25%", _format_count_pct(metrics.get("qtrDown25Count"), metrics.get("qtrDown25Pct")), metrics.get("qtrDown25Pct"), "meter-red")}
      </div>
      <div>
        <div style="font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">SMM Secondary</div>
        {_render_meter("MA40 (% > 40MA)", _format_float(metrics.get("ma40Pct"), suffix="%"), metrics.get("ma40Pct"), "meter-blue")}
        {_render_meter("34d Up >=13%", _format_count_pct(metrics.get("up13In34dCount"), metrics.get("up13In34dPct")), metrics.get("up13In34dPct"), "meter-green")}
        {_render_meter("34d Down >=13%", _format_count_pct(metrics.get("down13In34dCount"), metrics.get("down13In34dPct")), metrics.get("down13In34dPct"), "meter-red")}
        {_render_meter("Month Up >=25%", _format_count_pct(metrics.get("monthUp25Count"), metrics.get("monthUp25Pct")), metrics.get("monthUp25Pct"), "meter-green")}
        {_render_meter("Month Down >=25%", _format_count_pct(metrics.get("monthDown25Count"), metrics.get("monthDown25Pct")), metrics.get("monthDown25Pct"), "meter-red")}
        <div class="breadth-gauge">
          <div class="breadth-stat"><span class="label">S&amp;P 500</span><span class="value">{_format_float(metrics.get("spxClose"))}</span></div>
          <div class="breadth-stat"><span class="label">SPX 1D</span><span class="value">{_format_float(metrics.get("spxChange1dPct"), suffix="%")}</span></div>
          <div class="breadth-stat"><span class="label">SPX 5D</span><span class="value">{_format_float(metrics.get("spxChange5dPct"), suffix="%")}</span></div>
        </div>
      </div>
    </div>
    {error_html}
    <div class="thesis" style="margin-top:12px;"><strong>SMM:</strong> {escape(source["thesis"])}</div>
  </div>
""".strip()


def _render_deepvue_card(source: dict[str, Any]) -> str:
    freshness_label, freshness_class = _status_badge(source["status"])
    signal_label, signal_class = _market_badge(source)
    metrics = source["metrics"]
    advance_count = metrics.get("advanceCount")
    decline_count = metrics.get("declineCount")
    highs_count = metrics.get("highsCount")
    lows_count = metrics.get("lowsCount")
    advance_pct = metrics.get("advanceDeclinePct")
    highs_lows_pct = metrics.get("newHighsVsLowsPct")
    advance_decline = "N/A"
    if advance_count is not None and decline_count is not None and advance_pct is not None:
        advance_decline = f"{advance_count:,} / {decline_count:,} ({advance_pct}%)"
    highs_lows = "N/A"
    if highs_count is not None and lows_count is not None and highs_lows_pct is not None:
        highs_lows = f"{highs_count:,} / {lows_count:,} ({highs_lows_pct}%)"
    error_html = ""
    if source.get("lastError"):
        error_html = (
            f'<div style="font-size:11px;color:var(--orange);margin-top:6px;">Latest issue: '
            f'{escape(source["lastError"])}</div>'
        )
    return f"""
  <div class="card">
    <div class="card-header">
      <div class="card-icon" style="background:rgba(248,81,73,0.2);color:var(--red);">DV</div>
      <div>
        <div class="card-title">DV US Market</div>
        <div style="font-size:12px;color:var(--muted);">{_date_line(source)}</div>
      </div>
      <div style="margin-left:auto;text-align:right;">
        <span class="badge {freshness_class}">{freshness_label}</span>
        <span class="badge {signal_class}">{escape(signal_label)}</span>
      </div>
    </div>
    <div class="card-subtitle">Stage Analysis &amp; Breadth Overview</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
      <div>
        <div style="font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">Breadth Indicators</div>
        {_render_meter("Advance / Decline", advance_decline, metrics.get("advanceDeclinePct"), "meter-red")}
        {_render_meter("New Highs vs Lows", highs_lows, metrics.get("newHighsVsLowsPct"), "meter-red")}
        {_render_meter("Up from Open", _format_float(metrics.get("upFromOpenPct"), decimals=0, suffix="%"), metrics.get("upFromOpenPct"), "meter-red")}
        {_render_meter("Up Volume", _format_float(metrics.get("upVolumePct"), decimals=0, suffix="%"), metrics.get("upVolumePct"), "meter-red")}
        {_render_meter("Up >=4%", _format_float(metrics.get("up4Pct"), decimals=0, suffix="%"), metrics.get("up4Pct"), "meter-red")}
      </div>
      <div>
        <div style="font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">Weinstein Stage Distribution</div>
        {_render_meter("Stage 1 (Base)", _format_count_pct(metrics.get("stage1Count"), metrics.get("stage1Pct")), metrics.get("stage1Pct"), "meter-blue")}
        {_render_meter("Stage 2 (Uptrend)", _format_count_pct(metrics.get("stage2Count"), metrics.get("stage2Pct")), metrics.get("stage2Pct"), "meter-green")}
        {_render_meter("Stage 3 (Top)", _format_count_pct(metrics.get("stage3Count"), metrics.get("stage3Pct")), metrics.get("stage3Pct"), "meter-yellow")}
        {_render_meter("Stage 4 (Decline)", _format_count_pct(metrics.get("stage4Count"), metrics.get("stage4Pct")), metrics.get("stage4Pct"), "meter-red")}
      </div>
    </div>
    {error_html}
    <div class="thesis" style="margin-top:12px;"><strong>DV:</strong> {escape(source["thesis"])}</div>
  </div>
""".strip()


def _render_hk_card(source: dict[str, Any]) -> str:
    freshness_label, freshness_class = _status_badge(source["status"])
    signal_label, signal_class = _market_badge(source)
    metrics = source["metrics"]

    def _na_pct(value: float | None) -> str:
        return "N/A" if value is None else f"{value:.1f}%"

    adv_decl = "N/A"
    if metrics.get("advancePct") is not None and metrics.get("declinePct") is not None and metrics.get("advanceDeclineRatio") is not None:
        adv_decl = (
            f"{metrics['advancePct']:.1f}% / {metrics['declinePct']:.1f}% "
            f"({metrics['advanceDeclineRatio']:.2f}x)"
        )
    high_low = "N/A"
    if metrics.get("newHighs52w") is not None and metrics.get("newLows52w") is not None:
        ratio = metrics.get("highLowRatio")
        ratio_text = "N/A" if ratio is None else f"{ratio:.2f}x"
        high_low = f"{metrics['newHighs52w']} / {metrics['newLows52w']} ({ratio_text})"

    error_html = ""
    if source.get("lastError"):
        error_html = (
            f'<div style="font-size:11px;color:var(--orange);margin-top:6px;">Latest issue: '
            f'{escape(source["lastError"])}</div>'
        )

    return f"""
  <div class="card">
    <div class="card-header">
      {_score_ring(source)}
      <div>
        <div class="card-title">Hong Kong Breadth</div>
        <div style="font-size:12px;color:var(--muted);">{_date_line(source, 'AASTOCKS')}</div>
      </div>
      <div style="margin-left:auto;text-align:right;">
        <span class="badge {freshness_class}">{freshness_label}</span>
        <span class="badge {signal_class}">{escape(signal_label)}</span>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
      <div>
        <div style="font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">Moving Average Participation</div>
        {_render_meter("% Above 20MA", _na_pct(metrics.get("pctAbove20Ma")), metrics.get("pctAbove20Ma"), "meter-red")}
        {_render_meter("% Above 50MA", _na_pct(metrics.get("pctAbove50Ma")), metrics.get("pctAbove50Ma"), "meter-yellow")}
        {_render_meter("% Above 200MA", _na_pct(metrics.get("pctAbove200Ma")), metrics.get("pctAbove200Ma"), "meter-blue")}
      </div>
      <div>
        <div style="font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">Internals</div>
        {_render_meter("Advance / Decline", adv_decl, metrics.get("advancePct"), "meter-green")}
        <div class="breadth-gauge"><div class="breadth-stat"><span class="label">New 52W Highs / Lows</span><span class="value">{escape(high_low)}</span></div></div>
        {_render_meter("Up >=20% in 63d", _na_pct(metrics.get("up20In63dPct")), metrics.get("up20In63dPct"), "meter-green")}
        <div class="breadth-gauge">
          <div class="breadth-stat"><span class="label">Strong Up (>=4%/day)</span><span class="value">{escape(_na_pct(metrics.get('strongUpPct')))}</span></div>
          <div class="breadth-stat"><span class="label">Strong Down</span><span class="value">{escape(_na_pct(metrics.get('strongDownPct')))}</span></div>
        </div>
      </div>
    </div>
    {error_html}
    <div class="thesis" style="margin-top:12px;"><strong>HK:</strong> {escape(source["thesis"])}</div>
  </div>
""".strip()


def render_dashboard_html(template_html: str, snapshot: dict[str, Any]) -> str:
    generated_text = format_hkt_timestamp(snapshot["generatedAt"])
    title_html = f"External Intelligence Dashboard - {generated_text}"
    subtitle_html = "All Sources &mdash; Market Breadth auto-refreshed; other sections remain manually curated"
    timestamp_html = (
        f"{generated_text} &bull; Market Breadth auto-refreshes on schedule &bull; "
        "Other sections may reflect manual updates"
    )
    footer_html = (
        "Generated by notion-autopublish scrapers &bull; Market Breadth auto-refreshed from source artifacts on "
        f"{generated_text} &bull; Other dashboard sections may reflect manual updates"
    )

    rendered = re.sub(
        r"<!-- MARKET BREADTH -->.*?<!-- MACRO & LIQUIDITY -->",
        build_breadth_section(snapshot) + "\n\n<!-- MACRO & LIQUIDITY -->",
        template_html,
        flags=re.S,
    )
    rendered = re.sub(
        r"(<title>).*?(</title>)",
        rf"\1{title_html}\2",
        rendered,
        count=1,
        flags=re.S,
    )
    rendered = re.sub(
        r'(<div class="subtitle" data-i18n="subtitle">).*?(</div>)',
        rf"\1{subtitle_html}\2",
        rendered,
        count=1,
        flags=re.S,
    )
    rendered = re.sub(
        r'(<div class="timestamp" data-i18n="timestamp">).*?(</div>)',
        rf"\1{timestamp_html}\2",
        rendered,
        count=1,
        flags=re.S,
    )
    rendered = re.sub(
        r'(<div class="footer" data-i18n="footer">\s*).*?(\s*</div>)',
        rf"\1{footer_html}\2",
        rendered,
        count=1,
        flags=re.S,
    )

    replacements = {
        "subtitle": "All Sources - Market Breadth auto-refreshed; other sections remain manually curated",
        "timestamp": f"{generated_text} - Market Breadth auto-refreshes on schedule - Other sections may reflect manual updates",
        "footer": f"Generated by notion-autopublish scrapers - Market Breadth auto-refreshed from source artifacts on {generated_text} - Other dashboard sections may reflect manual updates",
    }
    for _ in range(2):
        for key, value in replacements.items():
            rendered = re.sub(
                rf"({key}:\s*')([^']*)(')",
                lambda match: match.group(1) + js_single_quote(value) + match.group(3),
                rendered,
                count=1,
            )

    return rendered


def render_dashboard_html(template_html: str, snapshot: dict[str, Any]) -> str:
    generated_text = format_hkt_timestamp(snapshot["generatedAt"])
    title_html = f"External Intelligence Dashboard - {generated_text}"
    subtitle_html = "All Sources &mdash; Market Breadth auto-refreshed; other sections remain manually curated"
    timestamp_html = (
        f"{generated_text} &bull; Market Breadth auto-refreshes on schedule &bull; "
        "Other sections may reflect manual updates"
    )
    footer_html = (
        "Generated by notion-autopublish scrapers &bull; Market Breadth auto-refreshed from source artifacts on "
        f"{generated_text} &bull; Other dashboard sections may reflect manual updates"
    )

    rendered = re.sub(
        r"<!-- MARKET BREADTH -->.*?<!-- MACRO & LIQUIDITY -->",
        lambda _match: build_breadth_section(snapshot) + "\n\n<!-- MACRO & LIQUIDITY -->",
        template_html,
        flags=re.S,
    )
    rendered = re.sub(
        r"(<title>).*?(</title>)",
        lambda match: match.group(1) + title_html + match.group(2),
        rendered,
        count=1,
        flags=re.S,
    )
    rendered = re.sub(
        r'(<div class="subtitle" data-i18n="subtitle">).*?(</div>)',
        lambda match: match.group(1) + subtitle_html + match.group(2),
        rendered,
        count=1,
        flags=re.S,
    )
    rendered = re.sub(
        r'(<div class="timestamp" data-i18n="timestamp">).*?(</div>)',
        lambda match: match.group(1) + timestamp_html + match.group(2),
        rendered,
        count=1,
        flags=re.S,
    )
    rendered = re.sub(
        r'(<div class="footer" data-i18n="footer">\s*).*?(\s*</div>)',
        lambda match: match.group(1) + footer_html + match.group(2),
        rendered,
        count=1,
        flags=re.S,
    )

    replacements = {
        "subtitle": "All Sources - Market Breadth auto-refreshed; other sections remain manually curated",
        "timestamp": f"{generated_text} - Market Breadth auto-refreshes on schedule - Other sections may reflect manual updates",
        "footer": f"Generated by notion-autopublish scrapers - Market Breadth auto-refreshed from source artifacts on {generated_text} - Other dashboard sections may reflect manual updates",
    }
    for _ in range(2):
        for key, value in replacements.items():
            rendered = re.sub(
                rf"({key}:\s*')([^']*)(')",
                lambda match: match.group(1) + js_single_quote(value) + match.group(3),
                rendered,
                count=1,
            )

    return rendered
