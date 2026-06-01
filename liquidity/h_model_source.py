from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

from liquidity.notion_capital_wars_source import (
    DEFAULT_PARENT_PAGE_ID,
    capture_latest_notion_capital_wars,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FALLBACK_ARTICLE_PATH = PROJECT_ROOT / "scraped_data" / "substack_authors" / "capital-wars.json"
_PNG_PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Z0ioAAAAASUVORK5CYII="
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_raw_dir() -> Path:
    raw_dir = Path(os.getenv("LIQUIDITY_RAW_DIR", "scraped_data/liquidity")).expanduser()
    if not raw_dir.is_absolute():
        raw_dir = (PROJECT_ROOT / raw_dir).resolve()
    raw_dir.mkdir(parents=True, exist_ok=True)
    return raw_dir


def _env_file_candidates() -> list[Path]:
    candidates: list[Path] = []
    for env_name in ("H_MODEL_SHARED_ENV_FILE", "FUNDMAN_JARVIS_ENV_FILE"):
        value = os.getenv(env_name, "").strip()
        if value:
            candidates.append(Path(value).expanduser())
    candidates.append(PROJECT_ROOT / ".env")
    candidates.append(PROJECT_ROOT.parent / "fundman-jarvis" / ".env")
    return candidates


def _env_value(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value

    for env_path in _env_file_candidates():
        if not env_path.exists():
            continue
        values = dotenv_values(env_path)
        for name in names:
            value = str(values.get(name) or "").strip()
            if value:
                return value
    return ""


def _resolve_notion_output_dir() -> Path:
    output_dir = Path(_env_value("H_MODEL_NOTION_OUTPUT_DIR") or "scraped_data/notion").expanduser()
    if not output_dir.is_absolute():
        output_dir = (PROJECT_ROOT / output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _write_placeholder_screenshot(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(_PNG_PIXEL)


def _load_fallback_article() -> dict | None:
    if not FALLBACK_ARTICLE_PATH.exists():
        return None
    try:
        return json.loads(FALLBACK_ARTICLE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def capture_latest_h_model(
    author_url: str,
    limit: int = 3,
    headless: bool = True,
) -> dict:
    raw_dir = _resolve_raw_dir()
    raw_path = raw_dir / "h_model_latest_raw.json"
    screenshot_path = raw_dir / "h_model_latest_screenshot.png"
    payload = {
        "author_url": author_url,
        "captured_at": _now_iso(),
        "articles": [],
        "available": False,
        "capture_status": "missing",
        "screenshot_path": str(screenshot_path),
    }
    source_mode = os.getenv("H_MODEL_SOURCE", "notion").strip().lower()
    if source_mode not in {"notion", "auto", "substack"}:
        source_mode = "notion"
    payload["source_mode"] = source_mode

    notion_error = None
    if source_mode in {"notion", "auto"}:
        token = _env_value("H_MODEL_NOTION_TOKEN", "NOTION_TOKEN")
        parent_page_id = _env_value("H_MODEL_NOTION_PARENT_PAGE_ID") or DEFAULT_PARENT_PAGE_ID
        if token:
            try:
                notion_payload = capture_latest_notion_capital_wars(
                    token=token,
                    parent_page_id=parent_page_id,
                    output_dir=_resolve_notion_output_dir(),
                )
                if notion_payload.get("available"):
                    _write_placeholder_screenshot(screenshot_path)
                    payload.update(notion_payload)
                    payload["author_url"] = author_url
                    payload["screenshot_path"] = str(screenshot_path)
                    raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                    return payload
                notion_error = notion_payload.get("capture_status", "notion_missing")
            except Exception as exc:
                notion_error = str(exc)
        else:
            notion_error = "missing NOTION_TOKEN"
        if notion_error:
            payload["notion_error"] = notion_error

    try:
        from scrape_substack_author import SubstackAuthorReader

        with SubstackAuthorReader(headless=headless) as reader:
            articles = reader.read_author_page(author_url, limit=limit)
            if getattr(reader, "page", None) is not None:
                reader.page.screenshot(str(screenshot_path))
            if not articles:
                raise RuntimeError("No H-model articles captured")
            payload.update({"articles": articles, "available": True, "capture_status": "ok"})
            if notion_error:
                payload["capture_status"] = "substack_after_notion_error"
    except Exception as exc:
        fallback = _load_fallback_article()
        _write_placeholder_screenshot(screenshot_path)
        if fallback:
            payload.update(
                {
                    "articles": [fallback],
                    "available": True,
                    "capture_status": "fallback_existing",
                    "error": str(exc),
                }
            )
        else:
            payload.update({"error": str(exc)})

    raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def load_latest_h_model_article(raw_dir: str | Path) -> dict | None:
    raw_path = Path(raw_dir) / "h_model_latest_raw.json"
    if not raw_path.exists():
        return None
    return json.loads(raw_path.read_text(encoding="utf-8"))
