"""
MacroMicro browser-session scraper.

Uses a persistent Playwright session because direct HTTP access is blocked by
Cloudflare and some chart payloads only materialize inside the rendered page.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

from browser.base import BrowserAutomation, SCRAPED_DIR

TARGET_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "macromicro_targets.json"
BUILTIN_TARGET_SPECS: List[Dict[str, Any]] = [
    {
        "key": "sentiment-combinations",
        "name": "Sentiment Combinations",
        "url": "https://www.macromicro.me/charts/99984/Sentiment-Combinations",
        "page_type": "chart",
        "analysis_domains": ["sentiment", "positioning"],
        "enabled": True,
    },
    {
        "key": "fear-and-greed",
        "name": "Fear And Greed",
        "url": "https://www.macromicro.me/cross-country-database/fear-and-greed",
        "page_type": "cross-country",
        "analysis_domains": ["sentiment", "cross_sectional"],
        "enabled": True,
    },
    {
        "key": "global-recession-rate",
        "name": "MM Global Economic Recession Rate",
        "url": "https://www.macromicro.me/charts/7898/mm-global-economic-recession-rate",
        "page_type": "chart",
        "analysis_domains": ["macro_cycle", "recession"],
        "enabled": True,
    },
]


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def is_security_verification_page(text: str) -> bool:
    lowered = (text or "").strip().lower()
    return "performing security verification" in lowered or "verifying..." in lowered


def overlay_present_values(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in extra.items():
        if value in (None, "") and key in merged:
            continue
        merged[key] = value
    return merged


def _extract_first_int(text: str) -> Optional[int]:
    match = re.search(r"(\d[\d,]*)", text or "")
    if not match:
        return None
    return int(match.group(1).replace(",", ""))


def normalize_industry_overview_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    industries: List[Dict[str, Any]] = []
    for item in payload.get("industries") or []:
        name = str(item.get("name") or "").strip()
        data_count_text = str(item.get("data_count_text") or item.get("count_text") or "").strip()
        if not name:
            continue
        industries.append(
            {
                "name": name,
                "data_count_text": data_count_text,
                "data_count": _extract_first_int(data_count_text),
            }
        )

    featured_charts: List[Dict[str, Any]] = []
    for item in payload.get("featured_charts") or []:
        title = str(item.get("title") or "").strip()
        summary = str(item.get("summary") or "").strip()
        category = str(item.get("category") or "").strip()
        combined = " ".join(part for part in [title, summary, category] if part)
        if not combined:
            continue
        featured_charts.append(
            {
                "category": category or None,
                "title": title or None,
                "summary": summary or None,
                "locked": bool(
                    item.get("locked")
                    or "立即訂閱" in combined
                    or "立即註冊登入" in combined
                    or "MM Max 訂閱專屬" in combined
                    or "PrimePRO" in combined
                ),
            }
        )

    return {
        "hero_title": str(payload.get("hero_title") or "").strip() or None,
        "hero_summary": str(payload.get("hero_summary") or "").strip() or None,
        "industry_count": len(industries),
        "industries": industries,
        "featured_chart_count": len(featured_charts),
        "featured_charts": featured_charts,
        "featured_chart_titles": [item["title"] for item in featured_charts if item.get("title")],
        "chart_count_text": str(payload.get("chart_count_text") or "").strip() or None,
        "chart_count": _extract_first_int(str(payload.get("chart_count_text") or "")),
        "industry_chain": [str(item).strip() for item in (payload.get("industry_chain") or []) if str(item).strip()],
    }


def normalize_industry_report_list_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    def _is_report_detail_url(href: str) -> bool:
        if not href or "/subscribe?next=" in href:
            return False
        path = urlparse(href).path.rstrip("/")
        if "/mails/" in path and not path.endswith("/monthly_report"):
            return True
        if "/industry-report/" in path and not path.endswith("/industry-report"):
            return True
        return False

    reports: List[Dict[str, Any]] = []
    raw_reports = list(payload.get("reports") or [])
    raw_reports.extend(payload.get("report_links") or [])
    seen: set[tuple[str, str]] = set()
    for item in raw_reports:
        title = str(item.get("title") or "").strip()
        href = str(item.get("href") or "").strip()
        if not title:
            continue
        dedupe_key = (title, href)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        locked = bool(item.get("locked") or "/subscribe?next=" in href)
        detail_url = href if href and not locked and _is_report_detail_url(href) else None
        reports.append(
            {
                "title": title,
                "date": str(item.get("date") or "").strip() or None,
                "status": str(item.get("status") or "").strip() or None,
                "href": href or None,
                "locked": locked,
                "detail_url": detail_url,
                "category": str(item.get("category") or "").strip() or None,
                "sector": str(item.get("sector") or "").strip() or None,
                "summary": str(item.get("summary") or "").strip() or None,
                "author": str(item.get("author") or "").strip() or None,
            }
        )

    return {
        "page_title": str(payload.get("page_title") or "").strip() or None,
        "cta_title": str(payload.get("cta_title") or "").strip() or None,
        "cta_summary": str(payload.get("cta_summary") or "").strip() or None,
        "report_count": len(reports),
        "reports": reports,
        "accessible_report_count": sum(1 for item in reports if item.get("detail_url")),
        "locked_report_count": sum(1 for item in reports if item.get("locked")),
    }


def _clean_text_list(items: Iterable[Any], max_items: int = 12) -> List[str]:
    cleaned: List[str] = []
    seen = set()
    for item in items or []:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
        if len(cleaned) >= max_items:
            break
    return cleaned


def normalize_industry_report_detail_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    related_reports: List[Dict[str, Optional[str]]] = []
    seen_related = set()
    for item in payload.get("related_reports") or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        href = str(item.get("href") or "").strip()
        if not title or not href:
            continue
        key = (title, href)
        if key in seen_related:
            continue
        seen_related.add(key)
        related_reports.append({"title": title, "href": href})

    return {
        "detail_url": str(payload.get("detail_url") or payload.get("url") or "").strip() or None,
        "title": str(payload.get("title") or "").strip() or None,
        "page_title": str(payload.get("page_title") or "").strip() or None,
        "author": str(payload.get("author") or "").strip() or None,
        "published_date": str(payload.get("published_date") or payload.get("date") or "").strip() or None,
        "sector": str(payload.get("sector") or "").strip() or None,
        "report_type": str(payload.get("report_type") or payload.get("category") or "").strip() or None,
        "summary_points": _clean_text_list(payload.get("summary_points") or [], max_items=8),
        "question_headings": _clean_text_list(payload.get("question_headings") or [], max_items=10),
        "section_headings": _clean_text_list(payload.get("section_headings") or [], max_items=10),
        "answer_previews": _clean_text_list(payload.get("answer_previews") or [], max_items=6),
        "related_reports": related_reports,
    }


_INDUSTRY_REPORT_LANGUAGE_LABELS = {
    "繁體中文",
    "简体中文",
    "簡體中文",
    "english",
    "日本語",
    "한국어",
}

_INDUSTRY_REPORT_NOISE_EXACT = {
    "收藏",
    "通知中心",
    "獨家產業報告",
    "MM獨家報告",
    "Isaiah 產業報告",
    "Isaiah產業報告",
    "搜尋",
    "搜尋...",
}


def _is_industry_report_language_label(text: str) -> bool:
    return (text or "").strip().lower() in _INDUSTRY_REPORT_LANGUAGE_LABELS


def _is_industry_report_noise(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return True
    if stripped in _INDUSTRY_REPORT_NOISE_EXACT or _is_industry_report_language_label(stripped):
        return True
    lowered = stripped.lower()
    return (
        lowered.startswith("macro")
        or lowered.startswith("search")
        or lowered.startswith("登入")
        or lowered.startswith("login")
    )


def _is_industry_report_question(text: str) -> bool:
    stripped = (text or "").strip()
    return bool(
        stripped
        and (
            re.match(r"^Q\d+[:：]?", stripped)
            or stripped in {"為什麼重要", "What it means", "Why it matters"}
        )
    )


def _is_industry_report_answer_label(text: str) -> bool:
    return bool(re.match(r"^A\d+[:：]?$", (text or "").strip()))


def _filter_industry_related_reports(
    detail_url: str, related_reports: Iterable[Dict[str, Any]]
) -> List[Dict[str, str]]:
    filtered: List[Dict[str, str]] = []
    seen = set()
    for item in related_reports or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        href = str(item.get("href") or "").strip()
        if not title or not href or _is_industry_report_language_label(title):
            continue
        parsed = urlparse(href)
        path = parsed.path.rstrip("/")
        if parsed.netloc and not parsed.netloc.endswith("macromicro.me"):
            continue
        if "/industry-report/" not in path or path == urlparse(detail_url).path.rstrip("/"):
            continue
        key = (title, href)
        if key in seen:
            continue
        seen.add(key)
        filtered.append({"title": title, "href": href})
    return filtered


def parse_industry_report_detail_content(
    *,
    detail_url: str,
    page_title: str,
    title: str,
    body_lines: Iterable[str],
    headings: Iterable[str],
    related_reports: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    cleaned_lines = _clean_text_list(body_lines, max_items=400)
    cleaned_headings = _clean_text_list(headings, max_items=20)

    date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    author = next((line for line in cleaned_lines[:16] if "Research" in line or "研究" in line), "")
    published_date = next((line for line in cleaned_lines[:20] if date_pattern.match(line)), "")

    metadata_anchor = 0
    if published_date and published_date in cleaned_lines:
        metadata_anchor = cleaned_lines.index(published_date) + 1
    elif author and author in cleaned_lines:
        metadata_anchor = cleaned_lines.index(author) + 1
    elif title and title in cleaned_lines:
        metadata_anchor = cleaned_lines.index(title) + 1

    metadata_candidates: List[str] = []
    for line in cleaned_lines[metadata_anchor:metadata_anchor + 10]:
        if line in {title, author, published_date, page_title} or _is_industry_report_noise(line):
            continue
        if _is_industry_report_question(line) or _is_industry_report_answer_label(line):
            break
        metadata_candidates.append(line)
        if len(metadata_candidates) >= 2:
            break

    sector = metadata_candidates[0] if metadata_candidates else ""
    report_type = metadata_candidates[1] if len(metadata_candidates) > 1 else ""

    summary_points: List[str] = []
    for line in cleaned_lines:
        if line in {title, author, published_date, sector, report_type, page_title}:
            continue
        if _is_industry_report_noise(line) or _is_industry_report_question(line) or _is_industry_report_answer_label(line):
            if _is_industry_report_question(line):
                break
            continue
        if len(line) >= 12:
            summary_points.append(line)
        if len(summary_points) >= 6:
            break

    question_headings = [heading for heading in cleaned_headings if _is_industry_report_question(heading)]
    section_headings = [
        heading
        for heading in cleaned_headings
        if heading != title and not _is_industry_report_noise(heading)
    ][:10]

    answer_previews: List[str] = []
    capture_answers = False
    for line in cleaned_lines:
        if _is_industry_report_question(line):
            capture_answers = True
            continue
        if not capture_answers:
            continue
        if (
            line in {title, author, published_date, sector, report_type, page_title}
            or _is_industry_report_noise(line)
            or line in cleaned_headings
            or _is_industry_report_answer_label(line)
        ):
            continue
        if len(line) >= 24:
            answer_previews.append(line)
        if len(answer_previews) >= 4:
            break

    return normalize_industry_report_detail_payload(
        {
            "detail_url": detail_url,
            "title": title,
            "page_title": page_title,
            "author": author,
            "published_date": published_date,
            "sector": sector,
            "report_type": report_type,
            "summary_points": summary_points,
            "question_headings": question_headings,
            "section_headings": section_headings,
            "answer_previews": answer_previews,
            "related_reports": _filter_industry_related_reports(detail_url, related_reports),
        }
    )


def build_industry_report_research_snapshot(payload: Dict[str, Any], max_reports: int = 5) -> Dict[str, Any]:
    detail_rows = [
        normalize_industry_report_detail_payload(item)
        for item in (payload.get("report_details") or [])
        if isinstance(item, dict)
    ]
    detail_rows = [row for row in detail_rows if row.get("title")]

    latest_reports = []
    focus_sectors: List[str] = []
    report_types: List[str] = []
    key_points: List[str] = []

    for row in detail_rows[:max_reports]:
        report_points = row.get("summary_points") or row.get("answer_previews") or []
        latest_reports.append(
            {
                "title": row.get("title"),
                "detail_url": row.get("detail_url"),
                "published_date": row.get("published_date"),
                "sector": row.get("sector"),
                "report_type": row.get("report_type"),
                "summary_points": report_points[:3],
            }
        )
        if row.get("sector") and row["sector"] not in focus_sectors:
            focus_sectors.append(row["sector"])
        if row.get("report_type") and row["report_type"] not in report_types:
            report_types.append(row["report_type"])
        for point in report_points:
            if point not in key_points:
                key_points.append(point)

    return {
        "available": bool(latest_reports),
        "report_count": len(detail_rows),
        "focus_sectors": focus_sectors[:8],
        "report_types": report_types[:8],
        "latest_reports": latest_reports,
        "key_points": key_points[:12],
    }


def normalize_target_key_from_url(url: str) -> str:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        return "macromicro"
    if len(parts) >= 2 and parts[0] in {"charts", "cross-country-database"}:
        return parts[-1].lower()
    return re.sub(r"[^a-z0-9]+", "-", parts[-1].lower()).strip("-") or "macromicro"


def _normalize_target_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    url = str(spec["url"])
    page_type = str(spec.get("page_type") or ("cross-country" if "/cross-country-database/" in url else "chart"))
    return {
        "key": str(spec.get("key") or normalize_target_key_from_url(url)),
        "name": str(spec.get("name") or spec.get("key") or normalize_target_key_from_url(url)),
        "url": url,
        "page_type": page_type,
        "analysis_domains": [str(item) for item in spec.get("analysis_domains", [])],
        "enabled": bool(spec.get("enabled", True)),
    }


def load_target_registry(config_path: Path = TARGET_CONFIG_PATH) -> Dict[str, Dict[str, Any]]:
    specs = BUILTIN_TARGET_SPECS
    try:
        if config_path.exists():
            payload = json.loads(config_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and isinstance(payload.get("targets"), list):
                specs = payload["targets"]
    except Exception:
        specs = BUILTIN_TARGET_SPECS

    registry: Dict[str, Dict[str, Any]] = {}
    for raw_spec in specs:
        spec = _normalize_target_spec(raw_spec)
        if not spec["enabled"]:
            continue
        registry[spec["key"]] = spec
    return registry


DEFAULT_TARGETS = load_target_registry()
TARGET_NETWORK_HINTS: Dict[str, List[str]] = {
    "global-recession-rate": [
        "7898",
        "global-economic-recession-rate",
        "mm-global-economic-recession-rate",
    ],
    "fear-and-greed": [
        "fear-and-greed",
    ],
}
COOKIE_FETCH_TARGETS: Dict[str, Dict[str, Any]] = {
    "fear-and-greed": {
        "endpoints": [
            {"role": "stats", "url": "https://www.macromicro.me/cross-country-database/stats/104"},
            {"role": "series", "url": "https://www.macromicro.me/api/cross-country-database/series/104"},
        ],
    },
    "global-recession-rate": {
        "endpoints": [
            {"role": "view", "url": "https://www.macromicro.me/api/view/chart/7898"},
            {"role": "data", "url": "https://www.macromicro.me/charts/data/7898"},
        ],
    },
}


def _extract_json_assignment(text: str, variable_name: str) -> Dict[str, Any]:
    match = re.search(
        rf"let\s+{re.escape(variable_name)}\s*=\s*(\{{.*?\}})\s*;",
        text,
        re.DOTALL,
    )
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}


def _extract_int_assignment(text: str, variable_name: str) -> Optional[int]:
    match = re.search(rf"let\s+{re.escape(variable_name)}\s*=\s*(\d+)\s*;", text)
    if not match:
        return None
    return int(match.group(1))


def _stringify_json_fragment(payload: Any, limit: int = 4000) -> str:
    try:
        text = json.dumps(payload, ensure_ascii=False)
    except Exception:
        text = str(payload)
    return text[:limit].lower()


def should_retry_headed_from_payload(payload: Dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get("error") == "security_verification_incomplete":
        return True
    title = str(payload.get("title") or "").strip().lower()
    return title == "just a moment..."


def _network_match_score(target_key: str, capture: Dict[str, Any]) -> int:
    hints = TARGET_NETWORK_HINTS.get(target_key, [target_key.replace("_", "-")])
    url = str(capture.get("url") or "").lower()
    haystacks = [
        url,
        _stringify_json_fragment(capture.get("payload")),
    ]
    score = 0
    for hint in hints:
        hint_lower = hint.lower()
        if any(hint_lower in haystack for haystack in haystacks):
            score += 3
    payload = capture.get("payload")
    if "/charts/data/" in url:
        score += 5
    elif "/api/view/chart/" in url:
        score += 1
    if "/api/cross-country-database/series/" in url:
        score += 5
    elif "/cross-country-database/stats/" in url:
        score += 1
    if isinstance(payload, dict):
        if isinstance(payload.get("chart"), dict):
            score += 2
        if isinstance(payload.get("series"), list):
            score += 1
        if isinstance(payload.get("data"), list):
            score += 1
        if isinstance(payload.get("data"), dict):
            score += 1
            for value in payload["data"].values():
                if isinstance(value, dict) and isinstance(value.get("series"), list):
                    score += 4
                    break
    elif isinstance(payload, list):
        score += 1
    return score


def select_preferred_network_capture(
    target_key: str,
    captures: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    best_capture: Optional[Dict[str, Any]] = None
    best_score = -1
    for capture in captures:
        payload = capture.get("payload")
        if not isinstance(payload, (dict, list)):
            continue
        score = _network_match_score(target_key, capture)
        if score > best_score:
            best_capture = capture
            best_score = score
    return best_capture


def _normalize_series_points(raw_points: Any) -> List[List[Any]]:
    normalized: List[List[Any]] = []
    if not isinstance(raw_points, list):
        return normalized
    while (
        len(raw_points) == 1
        and isinstance(raw_points[0], list)
        and raw_points[0]
        and isinstance(raw_points[0][0], (list, tuple))
        and len(raw_points[0][0]) >= 2
    ):
        raw_points = raw_points[0]
    for item in raw_points:
        if isinstance(item, dict):
            timestamp = (
                item.get("date")
                or item.get("datetime")
                or item.get("timestamp")
                or item.get("time")
                or item.get("x")
            )
            value = item.get("value")
            if value is None:
                value = item.get("y")
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            timestamp, value = item[0], item[1]
        else:
            continue
        if timestamp is None or value is None:
            continue
        normalized.append([timestamp, value])
    return normalized


def _extract_chart_network_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    chart_meta = payload.get("chart") if isinstance(payload.get("chart"), dict) else {}
    settings = chart_meta.get("settings") if isinstance(chart_meta.get("settings"), dict) else {}

    raw_series = payload.get("series")
    if not isinstance(raw_series, list):
        raw_series = []
    if not raw_series and isinstance(payload.get("data"), list):
        raw_series = [{"name": chart_meta.get("name"), "data": payload.get("data")}]
    if not raw_series and isinstance(payload.get("data"), dict):
        for value in payload["data"].values():
            if not isinstance(value, dict):
                continue
            info = value.get("info") if isinstance(value.get("info"), dict) else {}
            series_points = value.get("series")
            if not isinstance(series_points, list):
                continue
            if not chart_meta:
                chart_meta = {
                    "id": info.get("id"),
                    "slug": info.get("slug"),
                    "name": info.get("name") or info.get("name_en") or info.get("name_tc") or info.get("name_sc"),
                    "description": info.get("description") or info.get("description_en") or info.get("description_tc") or info.get("description_sc"),
                }
                settings = info.get("settings") if isinstance(info.get("settings"), dict) else {}
            raw_series.append(
                {
                    "name": info.get("name") or info.get("name_en") or info.get("name_tc") or chart_meta.get("name"),
                    "data": series_points,
                }
            )

    normalized_series: List[Dict[str, Any]] = []
    series_last_rows: List[List[List[Any]]] = []
    for series in raw_series:
        if not isinstance(series, dict):
            continue
        points = _normalize_series_points(
            series.get("data") or series.get("points") or series.get("values") or []
        )
        if not points:
            continue
        normalized_series.append({"name": series.get("name") or chart_meta.get("name"), "data": points})
        series_last_rows.append(points[-3:])

    return {
        "chart_id": chart_meta.get("id"),
        "title": chart_meta.get("name"),
        "slug": chart_meta.get("slug"),
        "description": chart_meta.get("description"),
        "value_decimals": settings.get("valueDecimals"),
        "series_last_rows": series_last_rows,
        "highcharts_series": serialize_highcharts_series(normalized_series),
        "raw_chart": chart_meta,
    }


def _build_cross_country_metadata_map(captures: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    metadata: Dict[str, Dict[str, Any]] = {}
    for capture in captures:
        payload = capture.get("payload")
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            continue
        for row in payload["data"]:
            if not isinstance(row, dict):
                continue
            stat_id = row.get("stat_id") or row.get("id")
            if stat_id is None:
                continue
            metadata[str(stat_id)] = {
                "code": row.get("country") or row.get("code"),
                "name": row.get("name_en") or row.get("name") or row.get("title"),
                "country_name": row.get("country_name"),
            }
    return metadata


def _extract_cross_country_rows(
    payload: Any,
    metadata_map: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        for key in ("data", "items", "rows", "list", "ranking"):
            if isinstance(payload.get(key), list):
                rows = payload.get(key)
                break
        else:
            data_dict = payload.get("data")
            if isinstance(data_dict, dict):
                synthesized_rows = []
                for value in data_dict.values():
                    if not isinstance(value, dict):
                        continue
                    info = value.get("info") if isinstance(value.get("info"), dict) else {}
                    series = value.get("series") if isinstance(value.get("series"), list) else []
                    if not info or not series:
                        continue
                    stat_id = info.get("id")
                    metadata = (metadata_map or {}).get(str(stat_id))
                    last_point = series[-1] if isinstance(series[-1], (list, tuple)) and len(series[-1]) >= 2 else None
                    prev_point = series[-2] if len(series) >= 2 and isinstance(series[-2], (list, tuple)) and len(series[-2]) >= 2 else None
                    if not last_point:
                        continue
                    change = None
                    if prev_point:
                        try:
                            change = last_point[1] - prev_point[1]
                        except Exception:
                            change = None
                    synthesized_rows.append(
                        {
                            "code": info.get("country") or (metadata or {}).get("code"),
                            "name": (
                                info.get("name")
                                or info.get("name_en")
                                or info.get("name_tc")
                                or info.get("name_sc")
                                or (metadata or {}).get("name")
                            ),
                            "country_name": (metadata or {}).get("country_name"),
                            "value": last_point[1],
                            "date": last_point[0],
                            "change": change,
                            "stat_id": stat_id,
                        }
                    )
                rows = synthesized_rows
            else:
                table = payload.get("table")
                if isinstance(table, dict) and isinstance(table.get("rows"), list):
                    rows = table.get("rows")
                else:
                    rows = []
    else:
        rows = []

    normalized: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized_row = {
            "code": row.get("code") or row.get("country_code") or row.get("symbol"),
            "name": row.get("name") or row.get("country") or row.get("label") or row.get("title"),
            "value": row.get("value") if row.get("value") is not None else row.get("score"),
            "rank": row.get("rank"),
            "change": row.get("change") if row.get("change") is not None else row.get("delta"),
            "date": row.get("date"),
            "stat_id": row.get("stat_id"),
            "country_name": row.get("country_name"),
        }
        if normalized_row["name"] is None and normalized_row["code"] is None:
            continue
        if normalized_row["value"] is None and normalized_row["rank"] is None:
            continue
        normalized.append(normalized_row)
    return normalized


def _format_cross_country_card_text(row: Dict[str, Any]) -> str:
    parts = []
    if row.get("value") is not None:
        parts.append(f"value: {row['value']}")
    if row.get("country_name") is not None:
        parts.append(f"country: {row['country_name']}")
    if row.get("date") is not None:
        parts.append(f"date: {row['date']}")
    if row.get("rank") is not None:
        parts.append(f"rank: {row['rank']}")
    if row.get("change") is not None:
        parts.append(f"change: {row['change']}")
    return " | ".join(parts) if parts else "captured"


def _extract_cross_country_network_payload(
    payload: Any,
    metadata_map: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    rows = _extract_cross_country_rows(payload, metadata_map=metadata_map)
    cards = [
        {
            "title": str(row.get("name") or row.get("code") or "row"),
            "text": _format_cross_country_card_text(row),
        }
        for row in rows[:8]
    ]
    return {
        "network_rows": rows,
        "cards": cards,
    }


def extract_target_network_payload(
    target_key: str,
    page_type: str,
    captures: List[Dict[str, Any]],
) -> Dict[str, Any]:
    selected = select_preferred_network_capture(target_key, captures)
    if not selected:
        return {}

    payload = selected.get("payload")
    if page_type == "chart" and isinstance(payload, dict):
        extracted = _extract_chart_network_payload(payload)
    elif page_type == "cross-country":
        extracted = _extract_cross_country_network_payload(
            payload,
            metadata_map=_build_cross_country_metadata_map(captures),
        )
    else:
        extracted = {}

    if not extracted:
        return {}

    extracted["network_capture"] = {
        "selected_url": selected.get("url"),
        "content_type": selected.get("content_type"),
        "matched_response_count": len(captures),
    }
    return extracted


def extract_chart_bootstrap(text: str) -> Dict[str, Any]:
    chart = _extract_json_assignment(text, "chart")
    settings = chart.get("settings") or {}
    last_rows_raw = chart.get("series_last_rows")
    last_rows: List[Any] = []
    if isinstance(last_rows_raw, str) and last_rows_raw:
        try:
            last_rows = json.loads(last_rows_raw)
        except json.JSONDecodeError:
            last_rows = []

    return {
        "chart_id": chart.get("id"),
        "title": chart.get("name"),
        "slug": chart.get("slug"),
        "description": chart.get("description"),
        "value_decimals": settings.get("valueDecimals"),
        "series_last_rows": last_rows,
        "raw_chart": chart,
    }


def extract_cross_country_bootstrap(text: str, page_title: Optional[str] = None) -> Dict[str, Any]:
    areas = _extract_json_assignment(text, "stat_area")
    normalized_areas: Dict[str, Dict[str, Any]] = {}
    for key, value in areas.items():
        countries = []
        for item in value.get("list", []):
            if isinstance(item, dict):
                countries.append(
                    {
                        "code": item.get("code"),
                        "name": item.get("name"),
                    }
                )
        normalized_areas[key] = {
            "name": value.get("name"),
            "countries": countries,
        }

    return {
        "title": page_title,
        "national_id": _extract_int_assignment(text, "national_id"),
        "areas": normalized_areas,
    }


def serialize_highcharts_series(raw_series: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = []
    for series in raw_series:
        data = series.get("data") or []
        points = []
        for item in data:
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            points.append(
                {
                    "timestamp": item[0],
                    "value": item[1],
                }
            )
        normalized.append(
            {
                "name": series.get("name"),
                "points": len(points),
                "first_points": points[:3],
                "last_points": points[-3:] if points else [],
            }
        )
    return normalized


def write_run_artifacts(
    results: Dict[str, Dict[str, Any]],
    output_dir: Path,
    generated_at: Optional[str] = None,
) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    for target_key, payload in results.items():
        path = output_dir / f"{target_key}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest = {
        "generated_at": generated_at or _now_iso(),
        "target_count": len(results),
        "success_count": sum(1 for payload in results.values() if payload.get("success")),
        "targets": results,
    }
    latest_path = output_dir / "macromicro_latest.json"
    latest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def summarize_network_capture(capture: Dict[str, Any]) -> Dict[str, Any]:
    payload = capture.get("payload")
    if isinstance(payload, dict):
        payload_type = "dict"
        top_level_keys = [str(key) for key in list(payload.keys())[:12]]
    elif isinstance(payload, list):
        payload_type = "list"
        top_level_keys = []
    else:
        payload_type = type(payload).__name__
        top_level_keys = []

    return {
        "url": capture.get("url"),
        "content_type": capture.get("content_type"),
        "payload_type": payload_type,
        "top_level_keys": top_level_keys,
        "payload_preview": _stringify_json_fragment(payload, limit=1200),
    }


def build_network_record_payload(
    *,
    target_key: str,
    spec: Dict[str, Any],
    captures: List[Dict[str, Any]],
    recorded_at: str,
    final_url: str,
    title: str,
    logged_in: bool,
    screenshot_path: Optional[str] = None,
) -> Dict[str, Any]:
    page_type = str(spec.get("page_type") or ("cross-country" if "/cross-country-database/" in spec["url"] else "chart"))
    selected = select_preferred_network_capture(target_key, captures)
    extracted_payload = extract_target_network_payload(target_key, page_type, captures)
    authenticated = logged_in or bool(selected)

    payload = {
        "target_key": target_key,
        "target_name": spec.get("name", target_key),
        "url": spec["url"],
        "page_type": page_type,
        "recorded_at": recorded_at,
        "final_url": final_url,
        "title": title,
        "logged_in": authenticated,
        "screenshot": screenshot_path,
        "capture_count": len(captures),
        "selected_endpoint": selected.get("url") if selected else None,
        "selected_content_type": selected.get("content_type") if selected else None,
        "candidate_endpoints": [summarize_network_capture(capture) for capture in captures],
        "extracted_payload": extracted_payload,
        "raw_captures": captures,
        "success": bool(selected),
    }
    if not selected:
        payload["error"] = "no_matching_network_capture"
    return payload


def build_cookie_fetch_payload(
    *,
    target_key: str,
    spec: Dict[str, Any],
    captures: List[Dict[str, Any]],
    fetched_at: str,
) -> Dict[str, Any]:
    page_type = str(spec.get("page_type") or ("cross-country" if "/cross-country-database/" in spec["url"] else "chart"))
    extracted_payload = extract_target_network_payload(target_key, page_type, captures)
    network_capture = extracted_payload.get("network_capture") if isinstance(extracted_payload, dict) else {}
    selected_endpoint = network_capture.get("selected_url") if isinstance(network_capture, dict) else None
    selected_content_type = network_capture.get("content_type") if isinstance(network_capture, dict) else None
    if page_type == "chart":
        has_structured_data = bool(extracted_payload.get("highcharts_series") or extracted_payload.get("series_last_rows") or extracted_payload.get("raw_chart"))
    else:
        has_structured_data = bool(extracted_payload.get("network_rows"))

    payload: Dict[str, Any] = {
        "target_key": target_key,
        "target_name": spec.get("name", target_key),
        "url": spec["url"],
        "final_url": spec["url"],
        "page_type": page_type,
        "scraped_at": fetched_at,
        "logged_in": bool(selected_endpoint),
        "success": bool(selected_endpoint) and has_structured_data,
        "title": None,
        "fetch_mode": "cookie_api",
        "selected_endpoint": selected_endpoint,
        "selected_content_type": selected_content_type,
        "network_candidate_urls": [capture.get("url") for capture in captures],
    }
    payload = overlay_present_values(payload, extracted_payload)
    if not payload.get("title"):
        payload["title"] = spec.get("name", target_key)
    if not payload["success"]:
        payload["error"] = "cookie_fetch_parse_failed"
    return payload


def write_network_recording_artifacts(
    results: Dict[str, Dict[str, Any]],
    output_dir: Path,
    generated_at: Optional[str] = None,
) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_results: Dict[str, Dict[str, Any]] = {}

    for target_key, payload in results.items():
        raw_captures = payload.get("raw_captures") or []
        summary_payload = dict(payload)
        summary_payload.pop("raw_captures", None)

        (output_dir / f"{target_key}_network_record.json").write_text(
            json.dumps(summary_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (output_dir / f"{target_key}_network_captures.json").write_text(
            json.dumps(raw_captures, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        summary_results[target_key] = summary_payload

    manifest = {
        "generated_at": generated_at or _now_iso(),
        "target_count": len(summary_results),
        "success_count": sum(1 for payload in summary_results.values() if payload.get("success")),
        "targets": summary_results,
    }
    latest_path = output_dir / "macromicro_network_recordings_latest.json"
    latest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


class MacroMicroScraper(BrowserAutomation):
    SERVICE_NAME = "macromicro"
    USE_CHROME_PROFILE = True
    HOME_URL = "https://www.macromicro.me/"
    LOGIN_URL = "https://www.macromicro.me/login"
    MAX_INDUSTRY_REPORT_DETAILS = 8

    def __init__(self, allow_manual_login: bool = True, **kwargs):
        kwargs.setdefault("slow_mo", 150)
        super().__init__(**kwargs)
        self.allow_manual_login = allow_manual_login
        self.output_dir = SCRAPED_DIR / "macromicro"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.network_recordings_dir = self.output_dir / "network_recordings"
        self.network_recordings_dir.mkdir(parents=True, exist_ok=True)

    def _has_saved_session_state(self) -> bool:
        default_dir = self.session_dir / "Default"
        cookie_candidates = (
            default_dir / "Network" / "Cookies",
            default_dir / "Cookies",
        )
        storage_markers = (
            default_dir / "Local Storage",
            default_dir / "Session Storage",
            default_dir / "Service Worker",
        )
        has_cookies = any(path.exists() for path in cookie_candidates)
        has_storage = any(path.exists() for path in storage_markers)
        return has_cookies and has_storage

    def start(self):
        """Prefer real Chrome channel for Cloudflare-heavy pages."""
        if self.USE_CHROME_PROFILE and not self._has_saved_session_state():
            from browser.base import copy_chrome_session, is_chrome_running

            if is_chrome_running():
                if self.headless:
                    raise RuntimeError(
                        "Chrome must be closed before headless MacroMicro scrape can copy the session."
                    )
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
        launch_kwargs = dict(
            user_data_dir=str(self.session_dir),
            headless=self.headless,
            slow_mo=self.slow_mo,
            viewport={"width": 1440, "height": 1000},
            locale="en-US",
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            self.context = self.playwright.chromium.launch_persistent_context(
                channel="chrome",
                **launch_kwargs,
            )
        except Exception:
            self.context = self.playwright.chromium.launch_persistent_context(**launch_kwargs)

        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        return self.page

    def is_logged_in(self) -> bool:
        self.page.goto(self.HOME_URL, wait_until="domcontentloaded")
        self.page.wait_for_timeout(3000)
        if not self._wait_for_security_verification_to_clear(timeout_seconds=20):
            return False
        return self._current_page_logged_in()

    def _wait_for_security_verification_to_clear(self, timeout_seconds: int = 20) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if not is_security_verification_page(self._body_text()):
                return True
            self.page.wait_for_timeout(2000)
        return not is_security_verification_page(self._body_text())

    def login(self):
        self.page.goto(self.LOGIN_URL, wait_until="domcontentloaded")
        self.page.wait_for_timeout(2000)
        self.wait_for_user(
            "Please log in to MacroMicro in the browser, then press Enter here "
            "after you can open paid charts normally."
        )

    def ensure_session(self):
        """Require a logged-in session for paid MacroMicro targets."""
        if self.headless:
            if not self.is_logged_in():
                raise RuntimeError(
                    "MacroMicro session missing; run non-headless with --login first."
                )
            return
        if self.allow_manual_login:
            self.ensure_logged_in()
            return
        if not self.is_logged_in():
            raise RuntimeError("MacroMicro session missing even in headed mode.")

    def _dismiss_cookie_banner(self):
        try:
            button = self.page.locator("button:has-text('我同意')").first
            if button.count() and button.is_visible():
                button.click()
                self.page.wait_for_timeout(500)
        except Exception:
            pass

    def _dismiss_overlays(self):
        self._dismiss_cookie_banner()
        for selector in (
            "button:has-text('X')",
            "button:has-text('確認')",
            "div[role='dialog'] button",
        ):
            try:
                button = self.page.locator(selector).first
                if button.count() and button.is_visible():
                    button.click()
                    self.page.wait_for_timeout(300)
            except Exception:
                continue

    def _current_page_logged_in(self) -> bool:
        try:
            if is_security_verification_page(self._body_text()):
                return False
            for selector in (
                "a[href*='/logout']",
                "a[href*='/user/settings']",
                "a[href*='/user/mcoins']",
                "a[href*='/user/mm-benefits']",
            ):
                if self.page.locator(selector).count() > 0:
                    return True
            return self.page.locator("a[href*='/login']").count() == 0
        except Exception:
            return False

    def _body_text(self) -> str:
        try:
            return self.page.locator("body").inner_text(timeout=2000)
        except Exception:
            return ""

    def _goto_target_url(self, url: str, attempts: int = 3) -> None:
        last_error: Optional[Exception] = None
        for attempt in range(1, attempts + 1):
            try:
                self.page.goto(url, wait_until="domcontentloaded")
                return
            except Exception as exc:
                last_error = exc
                message = str(exc).lower()
                if "interrupted by another navigation" not in message or attempt == attempts:
                    raise
                self.page.wait_for_timeout(1500)
        if last_error:
            raise last_error

    def _wait_for_target_ready(self, page_type: str, timeout_seconds: int = 45):
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            self._dismiss_overlays()
            body_text = self._body_text()
            if is_security_verification_page(body_text):
                self.page.wait_for_timeout(2000)
                continue

            try:
                if page_type == "chart":
                    if self.page.locator("main h1").count() > 0:
                        if self._extract_highcharts_series():
                            return
                        html = self.page.content()
                        if extract_chart_bootstrap(html).get("chart_id"):
                            return
                else:
                    if self.page.locator("main h1").count() > 0:
                        return
            except Exception:
                pass

            self.page.wait_for_timeout(1500)

    def _extract_highcharts_series(self) -> List[Dict[str, Any]]:
        try:
            raw_series = self.page.evaluate(
                """() => {
                    if (!window.Highcharts || !Array.isArray(window.Highcharts.charts)) {
                        return [];
                    }
                    return window.Highcharts.charts
                        .filter(Boolean)
                        .flatMap((chart) => (chart.series || []).map((series) => ({
                            name: series.name,
                            data: Array.isArray(series.options?.data) ? series.options.data : [],
                        })));
                }"""
            )
        except Exception:
            return []
        return serialize_highcharts_series(raw_series or [])

    def _extract_chart_latest_data(self) -> List[Dict[str, Any]]:
        try:
            return self.page.evaluate(
                """() => {
                    const rows = [];
                    const items = Array.from(document.querySelectorAll('main li'));
                    for (const item of items) {
                        const text = item.innerText.trim();
                        if (text && text.includes('前值')) {
                            rows.push({ text });
                        }
                    }
                    return rows.slice(0, 8);
                }"""
            )
        except Exception:
            return []

    def _extract_cross_country_cards(self) -> List[Dict[str, Any]]:
        try:
            return self.page.evaluate(
                """() => {
                    const cards = [];
                    const headings = Array.from(document.querySelectorAll('main h3, main h4, main h6'));
                    for (const heading of headings) {
                        const container = heading.closest('div');
                        const text = container ? container.innerText.trim() : heading.innerText.trim();
                        if (text && text.includes('看更多')) {
                            cards.push({
                                title: heading.innerText.trim(),
                                text: text.slice(0, 400),
                            });
                        }
                    }
                    return cards.slice(0, 8);
                }"""
            )
        except Exception:
            return []

    def _extract_industry_overview_summary(self) -> Dict[str, Any]:
        try:
            raw_payload = self.page.evaluate(
                """() => {
                    const main = document.querySelector('main') || document.body;
                    const lines = main.innerText
                        .split('\\n')
                        .map((line) => line.trim())
                        .filter(Boolean);
                    const heroTitle = lines.find((line) => line === '產業決策平台') || (document.querySelector('main h1')?.innerText.trim() || '');
                    const heroIndex = heroTitle ? lines.indexOf(heroTitle) : -1;
                    let heroSummary = '';
                    for (let i = Math.max(heroIndex + 1, 0); i < lines.length; i += 1) {
                        const line = lines[i];
                        if (line === 'MM研究員推薦圖表' || /^\\d[\\d,]*\\s*條數據$/.test(line)) {
                            break;
                        }
                        if (line.length > heroSummary.length && !['取得權限', '立即訂閱', '立即註冊登入'].includes(line)) {
                            heroSummary = line;
                        }
                    }

                    const industries = [];
                    for (let i = Math.max(heroIndex + 1, 0); i < lines.length - 1; i += 1) {
                        if (lines[i] === 'MM研究員推薦圖表') {
                            break;
                        }
                        if (/^\\d[\\d,]*\\s*條數據$/.test(lines[i + 1])) {
                            industries.push({name: lines[i], data_count_text: lines[i + 1]});
                            i += 1;
                        }
                    }

                    const featuredStart = lines.indexOf('MM研究員推薦圖表');
                    const sectionEndCandidates = ['產業總覽產業鏈', '產業總覽關鍵圖表']
                        .map((marker) => lines.indexOf(marker))
                        .filter((index) => index > featuredStart);
                    const featuredEnd = sectionEndCandidates.length ? Math.min(...sectionEndCandidates) : lines.length;
                    const featuredLines = featuredStart >= 0 ? lines.slice(featuredStart + 1, featuredEnd) : [];
                    const chartCountText = featuredLines.find((line) => /總共有\\s*\\d+\\s*張圖表/.test(line)) || '';

                    const titleCandidates = featuredLines.filter((line) => {
                        if (line.length < 8 || line.length > 90) return false;
                        if (/^\\d/.test(line)) return false;
                        if (/(看更多|立即訂閱|立即註冊登入|Zoom|All|YTD|PrimePRO|免費成為 MM 會員)/.test(line)) return false;
                        if (['宏觀產業', '利潤觀測', '限定解鎖宏觀產業', '預覽', '圖表分類 (2)', 'MM研究員排序'].includes(line)) return false;
                        return /[-A-Za-z一-龥]/.test(line);
                    });
                    const summaryCandidates = featuredLines
                        .filter((line) => line.includes('看更多') || line.includes('MM Max 訂閱專屬') || line.includes('免費成為 MM 會員'))
                        .map((line) => line.replace(/\\s*看更多$/, '').trim());
                    const featuredCharts = [];
                    for (let i = 0; i < Math.min(titleCandidates.length, summaryCandidates.length, 8); i += 1) {
                        featuredCharts.push({
                            title: titleCandidates[i],
                            summary: summaryCandidates[i],
                            category: null,
                        });
                    }

                    let industryChain = [];
                    const chainStart = lines.indexOf('產業總覽產業鏈');
                    const chainAnchor = lines.findIndex((line) => line.includes('11 大行業板塊'));
                    const chainIndex = chainAnchor > chainStart ? chainAnchor : chainStart;
                    if (chainIndex >= 0) {
                        for (let i = chainIndex + 1; i < lines.length; i += 1) {
                            const line = lines[i];
                            if (line === '產業總覽關鍵圖表') {
                                break;
                            }
                            if (line.length <= 12 && !line.includes('點此') && !line.includes('查看') && !/^\\d/.test(line)) {
                                industryChain.push(line);
                            }
                        }
                    }

                    return {
                        hero_title: heroTitle,
                        hero_summary: heroSummary,
                        industries,
                        featured_charts: featuredCharts,
                        chart_count_text: chartCountText,
                        industry_chain: Array.from(new Set(industryChain)).slice(0, 20),
                    };
                }"""
            )
        except Exception:
            return {}
        return normalize_industry_overview_payload(raw_payload or {})

    def _extract_industry_report_list(self) -> Dict[str, Any]:
        try:
            raw_payload = self.page.evaluate(
                """() => {
                    const pageTitle = document.querySelector('main h1')?.innerText.trim() || 'MM獨家報告';
                    const bodyLines = (document.querySelector('main') || document.body).innerText
                        .split('\\n')
                        .map((line) => line.trim())
                        .filter(Boolean);
                    const ctaIndex = bodyLines.indexOf(pageTitle);
                    let ctaTitle = '';
                    let ctaSummary = '';
                    for (let i = Math.max(ctaIndex + 1, 0); i < Math.min(bodyLines.length, ctaIndex + 8); i += 1) {
                        const line = bodyLines[i];
                        if (!ctaTitle && !['會員檔案', '立即訂閱', '未讀'].includes(line)) {
                            ctaTitle = line;
                            continue;
                        }
                        if (ctaTitle && !ctaSummary && !['立即訂閱'].includes(line)) {
                            ctaSummary = line;
                            break;
                        }
                    }

                    const reports = Array.from(
                        new Map(
                            Array.from(document.querySelectorAll('a.mail-link, a[href*="/industry-report/"]'))
                                .filter((anchor) => {
                                    const href = anchor.href || '';
                                    const text = anchor.innerText.trim();
                                    if (!text) {
                                        return false;
                                    }
                                    if (anchor.classList.contains('mail-link')) {
                                        return true;
                                    }
                                    return (
                                        !href.includes('/industry-report?page=') &&
                                        !href.endsWith('/industry-report') &&
                                        !href.includes('/industry-report?')
                                    );
                                })
                                .map((anchor) => {
                                    let container = anchor.closest('article, li');
                                    if (!container) {
                                        let node = anchor.closest('div');
                                        while (node && node !== document.body) {
                                            const text = (node.innerText || '').trim();
                                            const detailLinkCount = node.querySelectorAll('a[href*="/industry-report/"]').length;
                                            if (text && text.length <= 1400 && detailLinkCount <= 2) {
                                                container = node;
                                                break;
                                            }
                                            node = node.parentElement;
                                        }
                                    }
                                    const lines = (container?.innerText || '')
                                        .split('\\n')
                                        .map((line) => line.trim())
                                        .filter(Boolean);
                                    const title = anchor.innerText.trim();
                                    const titleIndex = lines.findIndex((line) => line === title);
                                    const afterTitle = titleIndex >= 0
                                        ? lines.slice(titleIndex + 1)
                                        : lines.filter((line) => line !== title);
                                    const looksLikeDate = (line) =>
                                        /\\b\\d{1,2}\\s+[A-Za-z]{3}\\s+20\\d{2}\\b/.test(line || '') ||
                                        /\\b20\\d{2}-\\d{2}-\\d{2}\\b/.test(line || '');
                                    const date = afterTitle.find((line) => looksLikeDate(line)) || lines.find((line) => looksLikeDate(line)) || '';
                                    const author = afterTitle.find((line) => /Research/i.test(line)) || '';
                                    const status = container?.querySelector('.mail-status')?.innerText.trim() || '';
                                    const category = titleIndex > 0 ? lines[titleIndex - 1] : '';
                                    const sector = afterTitle.find((line) => line && line !== author && !looksLikeDate(line) && line !== '收藏') || '';
                                    const summary = afterTitle.find((line) =>
                                        line &&
                                        line !== sector &&
                                        line !== author &&
                                        !looksLikeDate(line) &&
                                        line !== '收藏'
                                    ) || '';
                                    return [anchor.href, {
                                        title,
                                        href: anchor.href,
                                        date,
                                        status,
                                        category,
                                        sector,
                                        summary,
                                        author,
                                        locked: anchor.classList.contains('pro-gate-link') || anchor.href.includes('/subscribe?next='),
                                    }];
                                })
                        ).values()
                    );

                    return {
                        page_title: pageTitle,
                        cta_title: ctaTitle,
                        cta_summary: ctaSummary,
                        reports,
                    };
                }"""
            )
        except Exception:
            return {}
        return normalize_industry_report_list_payload(raw_payload or {})

    def _extract_industry_report_detail(self, detail_url: str) -> Dict[str, Any]:
        title = ""
        try:
            title = self.page.locator("main h1").first.inner_text(timeout=1500).strip()
        except Exception:
            pass

        main_text = ""
        try:
            main_text = self.page.locator("main").first.inner_text(timeout=2000).strip()
        except Exception:
            main_text = ""
        source_text = main_text or self._body_text()
        body_lines = _clean_text_list(source_text.splitlines(), max_items=400)
        if not title and body_lines:
            title = body_lines[0]

        headings: List[str] = []
        try:
            heading_locator = self.page.locator("main h1, main h2, main h3, main h4")
            for idx in range(min(heading_locator.count(), 24)):
                text = heading_locator.nth(idx).inner_text(timeout=1000).strip()
                if text and text not in headings:
                    headings.append(text)
        except Exception:
            pass

        related_reports: List[Dict[str, str]] = []
        try:
            anchor_locator = self.page.locator("main a[href*='/industry-report/']")
            for idx in range(min(anchor_locator.count(), 40)):
                anchor = anchor_locator.nth(idx)
                href = str(anchor.get_attribute("href") or "").strip()
                if href.startswith("/"):
                    href = f"https://www.macromicro.me{href}"
                text = anchor.inner_text(timeout=1000).strip()
                if not href or not text or href == detail_url:
                    continue
                if "/industry-report?" in href or href.rstrip("/").endswith("/industry-report"):
                    continue
                related_reports.append({"title": text, "href": href})
        except Exception:
            pass

        page_title = ""
        try:
            page_title = self.page.title()
        except Exception:
            page_title = ""

        return parse_industry_report_detail_content(
            detail_url=detail_url,
            page_title=page_title,
            title=title,
            body_lines=body_lines,
            headings=headings,
            related_reports=related_reports,
        )

        date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        author = next((line for line in body_lines[:12] if "Research" in line), "")
        published_date = next((line for line in body_lines[:14] if date_pattern.match(line)), "")

        metadata_window = []
        if published_date and published_date in body_lines:
            start = body_lines.index(published_date) + 1
            metadata_window = body_lines[start:start + 6]
        else:
            metadata_window = body_lines[1:8]

        metadata_candidates = [
            line for line in metadata_window
            if line not in {title, author, published_date, "收藏", "獨家產業報告"}
        ]
        sector = metadata_candidates[0] if metadata_candidates else ""
        report_type = metadata_candidates[1] if len(metadata_candidates) > 1 else ""

        first_heading_idx = None
        for idx, line in enumerate(body_lines):
            if line.startswith("Q1") or line.startswith("為什麼重要") or line.startswith("What it means"):
                first_heading_idx = idx
                break
        summary_slice = body_lines[:first_heading_idx] if first_heading_idx is not None else body_lines[:16]
        summary_points = [
            line
            for line in summary_slice
            if line not in {title, author, published_date, sector, report_type, "收藏", "獨家產業報告"}
            and len(line) >= 18
        ][:6]

        question_headings = [heading for heading in headings if re.match(r"^Q\d+[:：]", heading)]
        answer_previews: List[str] = []
        body_heading_set = {title, author, published_date, sector, report_type, "收藏", "獨家產業報告"}
        for line in body_lines:
            if (
                line in body_heading_set
                or line in headings
                or line.startswith("A1")
                or line.startswith("A2")
                or line.startswith("A3")
                or line.startswith("A4")
                or line.startswith("A5")
            ):
                continue
            if len(line) >= 40:
                answer_previews.append(line)
            if len(answer_previews) >= 4:
                break

        return normalize_industry_report_detail_payload(
            {
                "detail_url": detail_url,
                "title": title,
                "page_title": self.page.title(),
                "author": author,
                "published_date": published_date,
                "sector": sector,
                "report_type": report_type,
                "summary_points": summary_points,
                "question_headings": question_headings,
                "section_headings": headings[1:12] if headings[:1] == [title] else headings[:12],
                "answer_previews": answer_previews,
                "related_reports": related_reports,
            }
        )

    def _follow_industry_report_details(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        detail_urls = []
        for item in payload.get("reports") or []:
            if not isinstance(item, dict):
                continue
            detail_url = str(item.get("detail_url") or "").strip()
            if detail_url:
                detail_urls.append(detail_url)
        detail_urls = list(dict.fromkeys(detail_urls))[: self.MAX_INDUSTRY_REPORT_DETAILS]
        if not detail_urls:
            payload["report_details"] = []
            payload["research_snapshot"] = build_industry_report_research_snapshot(payload, max_reports=5)
            return payload

        detail_rows: List[Dict[str, Any]] = []
        retry_headed = False
        for idx, detail_url in enumerate(detail_urls, start=1):
            detail_payload = self._capture_target(
                f"industry-report-detail-{idx}",
                {
                    "name": f"Industry Report Detail {idx}",
                    "url": detail_url,
                    "page_type": "industry-report-detail",
                },
            )
            if detail_payload.get("success"):
                detail_rows.append(detail_payload)
            elif self.headless and should_retry_headed_from_payload(detail_payload):
                retry_headed = True
                break

        payload["report_details"] = detail_rows
        payload["report_detail_count"] = len(detail_rows)
        payload["report_detail_retry_headed"] = retry_headed
        payload["research_snapshot"] = build_industry_report_research_snapshot(payload, max_reports=5)
        return payload

    def _capture_network_response(self, captures: List[Any], response) -> None:
        try:
            request = response.request
            if request.resource_type not in {"xhr", "fetch"}:
                return
            if response.status != 200:
                return

            url = str(response.url or "")
            if "macromicro.me" not in url:
                return

            content_type = str((response.headers or {}).get("content-type", ""))
            if "json" not in content_type.lower() and "/api/" not in url.lower():
                return

            captures.append(response)
        except Exception:
            return

    def _finalize_network_captures(self, responses: List[Any]) -> List[Dict[str, Any]]:
        captures: List[Dict[str, Any]] = []
        for response in responses:
            try:
                url = str(response.url or "")
                content_type = str((response.headers or {}).get("content-type", ""))
                text = response.text()
                if not text or len(text) > 500000:
                    continue
                if text[:1] not in "[{":
                    continue

                payload = json.loads(text)
                captures.append(
                    {
                        "url": url,
                        "content_type": content_type,
                        "payload": payload,
                    }
                )
            except Exception:
                continue
        return captures

    def _supports_cookie_fetch(self, target_key: str, spec: Dict[str, str]) -> bool:
        canonical = DEFAULT_TARGETS.get(target_key)
        if not canonical:
            return False
        return target_key in COOKIE_FETCH_TARGETS and spec.get("url") == canonical.get("url")

    def _fetch_json_with_session_cookie(self, url: str, referer: str) -> Dict[str, Any]:
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Referer": referer,
        }
        request_context = self.playwright.request.new_context(
            storage_state=self.context.storage_state(),
            extra_http_headers=headers,
        )
        try:
            response = request_context.get(url, fail_on_status_code=False)
            if response.status != 200:
                raise RuntimeError(f"cookie fetch failed for {url} (status={response.status})")
            content_type = str((response.headers or {}).get("content-type", ""))
            text = response.text()
            if not text or text[:1] not in "[{":
                raise RuntimeError(f"cookie fetch returned non-json payload for {url}")
            return {
                "url": url,
                "content_type": content_type,
                "payload": json.loads(text),
            }
        finally:
            request_context.dispose()

    def _fetch_target_via_cookie_api(self, target_key: str, spec: Dict[str, str]) -> Dict[str, Any]:
        endpoint_spec = COOKIE_FETCH_TARGETS.get(target_key)
        if not endpoint_spec:
            raise KeyError(f"Cookie fetch unsupported for target: {target_key}")

        captures = [
            self._fetch_json_with_session_cookie(endpoint["url"], referer=spec["url"])
            for endpoint in endpoint_spec["endpoints"]
        ]
        return build_cookie_fetch_payload(
            target_key=target_key,
            spec=spec,
            captures=captures,
            fetched_at=_now_iso(),
        )

    def _resolve_targets(
        self,
        target_keys: Optional[List[str]] = None,
        urls: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, str]]:
        selected: Dict[str, Dict[str, str]] = {}
        for key in target_keys or []:
            if key not in DEFAULT_TARGETS:
                raise KeyError(f"Unknown MacroMicro target: {key}")
            selected[key] = DEFAULT_TARGETS[key]
        for url in urls or []:
            key = normalize_target_key_from_url(url)
            selected[key] = {
                "name": key,
                "url": url,
                "page_type": "cross-country" if "/cross-country-database/" in url else "chart",
            }
        if not selected:
            selected = dict(DEFAULT_TARGETS)
        return selected

    def _capture_target(self, target_key: str, spec: Dict[str, str]) -> Dict[str, Any]:
        started_at = _now_iso()
        url = spec["url"]
        page_type = spec.get("page_type") or (
            "cross-country" if "/cross-country-database/" in url else "chart"
        )
        network_responses: List[Any] = []
        response_handler = lambda response: self._capture_network_response(network_responses, response)
        self.page.on("response", response_handler)
        try:
            self._goto_target_url(url)
            self._wait_for_target_ready(page_type=page_type)
            final_url = self.page.url
            html = self.page.content()
            title = self.page.title()
            self._dismiss_overlays()
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = self.output_dir / f"{target_key}_{ts}.png"
            self.page.screenshot(path=str(screenshot_path), full_page=True)
            body_text = self._body_text()
        finally:
            try:
                self.page.remove_listener("response", response_handler)
            except Exception:
                pass
        network_captures = self._finalize_network_captures(network_responses)

        network_extract = extract_target_network_payload(
            target_key=target_key,
            page_type=page_type,
            captures=network_captures,
        )

        payload: Dict[str, Any] = {
            "target_key": target_key,
            "target_name": spec.get("name", target_key),
            "url": url,
            "final_url": final_url,
            "page_type": page_type,
            "scraped_at": started_at,
            "logged_in": self._current_page_logged_in() and not is_security_verification_page(body_text),
            "screenshot": str(screenshot_path),
            "success": final_url != self.HOME_URL and not is_security_verification_page(body_text),
            "title": title,
        }

        if page_type == "chart":
            payload = overlay_present_values(payload, extract_chart_bootstrap(html))
            payload["highcharts_series"] = self._extract_highcharts_series()
            payload["latest_data"] = self._extract_chart_latest_data()
        elif page_type == "industry-overview":
            payload = overlay_present_values(payload, self._extract_industry_overview_summary())
        elif page_type == "industry-report-list":
            payload = overlay_present_values(payload, self._extract_industry_report_list())
            if payload.get("success") and payload.get("accessible_report_count"):
                payload = self._follow_industry_report_details(payload)
        elif page_type == "industry-report-detail":
            payload = overlay_present_values(payload, self._extract_industry_report_detail(url))
        else:
            payload = overlay_present_values(
                payload,
                extract_cross_country_bootstrap(html, page_title=title),
            )
            payload["cards"] = self._extract_cross_country_cards()

        payload = overlay_present_values(payload, network_extract)
        payload["network_candidate_urls"] = [capture.get("url") for capture in network_captures[:12]]
        if "network_capture" not in payload:
            payload["network_capture"] = {
                "selected_url": None,
                "content_type": None,
                "matched_response_count": len(network_captures),
            }

        if final_url == self.HOME_URL:
            payload["error"] = "redirected_to_home"
            payload["success"] = False
        elif is_security_verification_page(body_text) or (title or "").strip().lower() == "just a moment...":
            payload["error"] = "security_verification_incomplete"
            payload["success"] = False
        elif payload.get("report_detail_retry_headed"):
            payload["error"] = "security_verification_incomplete"
            payload["success"] = False

        return payload

    def _record_network_target(self, target_key: str, spec: Dict[str, str]) -> Dict[str, Any]:
        recorded_at = _now_iso()
        url = spec["url"]
        page_type = spec.get("page_type") or (
            "cross-country" if "/cross-country-database/" in url else "chart"
        )
        network_responses: List[Any] = []
        final_url = url
        title = ""
        response_handler = lambda response: self._capture_network_response(network_responses, response)
        self.page.on("response", response_handler)
        screenshot_path: Optional[Path] = None
        body_text = ""
        try:
            self._goto_target_url(url)
            self._wait_for_target_ready(page_type=page_type)
            self.wait_for_user(
                f"MacroMicro network recorder is active for {target_key}. "
                "Interact with the page, then press Enter here to save captured endpoints."
            )
            final_url = self.page.url
            title = self.page.title()
            body_text = self._body_text()
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = self.network_recordings_dir / f"{target_key}_{ts}.png"
            self.page.screenshot(path=str(screenshot_path), full_page=True)
        finally:
            try:
                self.page.remove_listener("response", response_handler)
            except Exception:
                pass
        network_captures = self._finalize_network_captures(network_responses)

        return build_network_record_payload(
            target_key=target_key,
            spec={"name": spec.get("name", target_key), "url": url, "page_type": page_type},
            captures=network_captures,
            recorded_at=recorded_at,
            final_url=final_url,
            title=title,
            logged_in=self._current_page_logged_in() and not is_security_verification_page(body_text),
            screenshot_path=str(screenshot_path) if screenshot_path else None,
        )

    def record_network(
        self,
        target_keys: Optional[List[str]] = None,
        urls: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        if self.headless:
            raise RuntimeError("MacroMicro manual network recorder must run in headed mode.")

        selected = self._resolve_targets(target_keys=target_keys, urls=urls)
        self.ensure_session()
        results = {key: self._record_network_target(key, spec) for key, spec in selected.items()}
        return write_network_recording_artifacts(results, output_dir=self.network_recordings_dir)

    def run(
        self,
        target_keys: Optional[List[str]] = None,
        urls: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        selected = self._resolve_targets(target_keys=target_keys, urls=urls)
        results: Dict[str, Dict[str, Any]] = {}
        for key, spec in selected.items():
            if self._supports_cookie_fetch(key, spec):
                try:
                    cookie_payload = self._fetch_target_via_cookie_api(key, spec)
                    if cookie_payload.get("success"):
                        results[key] = cookie_payload
                        continue
                except Exception:
                    pass
            capture_payload = self._capture_target(key, spec)
            if self.headless and should_retry_headed_from_payload(capture_payload):
                raise RuntimeError("MacroMicro session missing; run non-headless with --login first.")
            results[key] = capture_payload
        return write_run_artifacts(results, output_dir=self.output_dir)
