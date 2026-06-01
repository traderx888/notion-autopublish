from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
DEFAULT_PARENT_PAGE_ID = "15d3caa8a48780bf84ffcc796104a627"
TEXT_ARTIFACT_NAME = "michael_howell_capital_war_latest.txt"
JSON_ARTIFACT_NAME = "michael_howell_capital_war_latest.json"

MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def extract_notion_page_id(value: str) -> str:
    """Extract a 32-hex Notion page ID from a URL or raw ID."""
    cleaned = (value or "").strip().split("?", 1)[0].replace("-", "")
    match = re.search(r"([0-9a-fA-F]{32})$", cleaned)
    if not match:
        raise ValueError(f"Could not extract Notion page ID from {value!r}")
    return match.group(1).lower()


def _notion_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


def _get_children(
    block_id: str,
    *,
    token: str,
    session: Any,
    timeout: int,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    cursor = None
    while True:
        params: dict[str, Any] = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        url = f"{NOTION_API_BASE}/blocks/{block_id}/children"
        response = session.get(url, headers=_notion_headers(token), params=params, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        results.extend(payload.get("results", []))
        if not payload.get("has_more"):
            return results
        cursor = payload.get("next_cursor")
        if not cursor:
            return results


def _rich_text_plain(items: list[dict[str, Any]]) -> str:
    return "".join(item.get("plain_text", "") for item in items or [])


def _block_text_lines(block: dict[str, Any]) -> list[str]:
    block_type = block.get("type", "")
    data = block.get(block_type, {}) if block_type else {}
    text = _rich_text_plain(data.get("rich_text", []))

    if block_type in {"paragraph", "heading_1", "heading_2", "heading_3", "quote", "callout"}:
        return [text] if text else []
    if block_type == "bulleted_list_item":
        return [f"- {text}"] if text else []
    if block_type == "numbered_list_item":
        return [f"1. {text}"] if text else []
    if block_type == "to_do":
        checked = "x" if data.get("checked") else " "
        return [f"- [{checked}] {text}"] if text else []
    if block_type == "divider":
        return ["---"]
    if block_type == "table_row":
        cells = data.get("cells", [])
        return [" | ".join(_rich_text_plain(cell) for cell in cells)]
    if block_type == "image":
        image_type = data.get("type", "")
        url = data.get(image_type, {}).get("url", "")
        caption = _rich_text_plain(data.get("caption", []))
        if url:
            return [f"![{caption}]({url})"]
    return [text] if text else []


def _page_text(
    page_id: str,
    *,
    token: str,
    session: Any,
    timeout: int,
    depth: int = 0,
) -> str:
    lines: list[str] = []
    for block in _get_children(page_id, token=token, session=session, timeout=timeout):
        lines.extend(_block_text_lines(block))
        if block.get("has_children") and depth < 2:
            child_text = _page_text(
                block["id"],
                token=token,
                session=session,
                timeout=timeout,
                depth=depth + 1,
            )
            if child_text:
                lines.append(child_text)
    return "\n".join(line for line in lines if line is not None).strip()


def _clean_title(title: str) -> str:
    cleaned = re.sub(r"<br\s*/?>", " ", title or "", flags=re.IGNORECASE)
    cleaned = cleaned.replace("**", "").replace("__", "")
    return " ".join(cleaned.split())


def _is_gli_title(title: str) -> bool:
    lowered = _clean_title(title).lower()
    if "global liquidity watch" in lowered:
        return True
    if "global liquidity" in lowered and any(term in lowered for term in ("update", "latest data")):
        return True
    return False


def _year_from_short(value: int) -> int:
    return 2000 + value if value < 100 else value


def _date_from_title(title: str) -> datetime | None:
    cleaned = _clean_title(title)
    month_names = (
        r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sept?|September|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
    )

    match = re.search(
        rf"\b({month_names})\s+(\d{{1,2}}),?\s+(\d{{2,4}})\b",
        cleaned,
        re.IGNORECASE,
    )
    if match:
        return datetime(_year_from_short(int(match.group(3))), MONTHS[match.group(1).lower()], int(match.group(2)), tzinfo=timezone.utc)

    match = re.search(
        rf"\b(\d{{1,2}})\s*,\s*({month_names})\s*,?\s*(\d{{2,4}})\b",
        cleaned,
        re.IGNORECASE,
    )
    if match:
        return datetime(_year_from_short(int(match.group(3))), MONTHS[match.group(2).lower()], int(match.group(1)), tzinfo=timezone.utc)

    match = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", cleaned)
    if match:
        return datetime(_year_from_short(int(match.group(3))), int(match.group(2)), int(match.group(1)), tzinfo=timezone.utc)

    return None


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _page_url(page_id: str) -> str:
    return f"https://www.notion.so/{extract_notion_page_id(page_id)}"


def _format_text_artifact(article: dict[str, Any], captured_at: str, parent_page_id: str) -> str:
    return "\n".join(
        [
            f"TITLE: {article['title']}",
            f"URL: {article['url']}",
            f"PUBLISHED_AT: {article['date']}",
            f"CAPTURED_AT: {captured_at}",
            "SOURCE: notion",
            f"PARENT_PAGE_ID: {extract_notion_page_id(parent_page_id)}",
            f"ARTICLE_PAGE_ID: {extract_notion_page_id(article['page_id'])}",
            "",
            article.get("body_text", ""),
            "",
        ]
    )


def capture_latest_notion_capital_wars(
    *,
    token: str,
    parent_page_id: str = DEFAULT_PARENT_PAGE_ID,
    output_dir: str | Path = "scraped_data/notion",
    session: Any | None = None,
    now_iso: str | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    if not token:
        raise ValueError("Missing NOTION_TOKEN")

    parent_id = extract_notion_page_id(parent_page_id)
    client = session or requests.Session()
    captured_at = now_iso or _now_iso()
    out_dir = Path(output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    child_pages = []
    for block in _get_children(parent_id, token=token, session=client, timeout=timeout):
        if block.get("type") != "child_page":
            continue
        title = _clean_title(block.get("child_page", {}).get("title", ""))
        if not _is_gli_title(title):
            continue
        published = _date_from_title(title) or _parse_iso(block.get("last_edited_time"))
        child_pages.append(
            {
                "page_id": block["id"],
                "title": title,
                "published_at": published or datetime.min.replace(tzinfo=timezone.utc),
                "last_edited_time": block.get("last_edited_time", ""),
            }
        )

    if not child_pages:
        return {
            "available": False,
            "capture_status": "notion_missing",
            "captured_at": captured_at,
            "articles": [],
            "parent_page_id": parent_id,
        }

    child_pages.sort(key=lambda item: item["published_at"], reverse=True)
    chosen = child_pages[0]
    body_text = _page_text(chosen["page_id"], token=token, session=client, timeout=timeout)
    published_at = chosen["published_at"].isoformat()
    article = {
        "url": _page_url(chosen["page_id"]),
        "page_id": extract_notion_page_id(chosen["page_id"]),
        "title": chosen["title"],
        "date": published_at,
        "body_text": body_text,
    }

    text_path = out_dir / TEXT_ARTIFACT_NAME
    json_path = out_dir / JSON_ARTIFACT_NAME
    text_path.write_text(
        _format_text_artifact(article, captured_at, parent_id),
        encoding="utf-8",
    )

    sidecar = {
        "source": "notion",
        "parent_page_id": parent_id,
        "parent_page_url": _page_url(parent_id),
        "article_page_id": article["page_id"],
        "article_page_url": article["url"],
        "title": article["title"],
        "published_at": article["date"],
        "captured_at": captured_at,
        "body_text": article["body_text"],
        "text_artifact_path": str(text_path),
    }
    json_path.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "available": True,
        "capture_status": "notion_ok",
        "captured_at": captured_at,
        "articles": [article],
        "parent_page_id": parent_id,
        "text_artifact_path": str(text_path),
        "json_artifact_path": str(json_path),
    }
