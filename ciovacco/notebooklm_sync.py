from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Iterable
from urllib.parse import parse_qs, urlparse

from notebooklm import NotebookLMClient


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_notebooklm_sync_config(
    *,
    notebook_id: str | None = None,
    storage_path: str | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, str | None]:
    env_map = env or {}
    resolved_notebook_id = (notebook_id or env_map.get("CIOVACCO_NOTEBOOKLM_NOTEBOOK_ID", "")).strip()
    if not resolved_notebook_id:
        raise ValueError(
            "Missing NotebookLM notebook ID. Pass --notebook-id or set CIOVACCO_NOTEBOOKLM_NOTEBOOK_ID."
        )
    resolved_storage = (
        storage_path
        or env_map.get("NOTEBOOKLM_STORAGE_PATH", "")
        or env_map.get("CIOVACCO_NOTEBOOKLM_STORAGE", "")
    ).strip() or None
    return {
        "notebook_id": resolved_notebook_id,
        "storage_path": resolved_storage,
    }


def _extract_youtube_video_id(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if "youtu.be" in host:
        return parsed.path.strip("/").split("/")[0]
    query_video_id = parse_qs(parsed.query).get("v", [])
    if query_video_id:
        return query_video_id[0]
    return ""


def canonicalize_source_url(url: str | None) -> str:
    if not url:
        return ""
    video_id = _extract_youtube_video_id(url)
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    return url.strip()


def find_source_by_url(sources: Iterable[Any], url: str) -> Any | None:
    canonical_url = canonicalize_source_url(url)
    for source in sources:
        source_url = canonicalize_source_url(getattr(source, "url", None))
        if source_url and source_url == canonical_url:
            return source
    return None


def build_ciovacco_notebooklm_questions(artifact: dict) -> dict[str, str]:
    latest_video = artifact.get("latest_video", {})
    analysis = artifact.get("analysis", {})
    ratio_names = ", ".join(
        signal.get("ratio", "")
        for signal in analysis.get("ratio_signals", [])
        if signal.get("ratio")
    )
    core_conclusion = analysis.get("core_conclusion", "")
    situation = analysis.get("situation", "")
    title = latest_video.get("title", "")
    video_id = latest_video.get("id", "")

    return {
        "core_thesis": (
            f'Using the full notebook history and the newest Ciovacco video "{title}", '
            f"state the core thesis this week. Start from this base case: {core_conclusion} "
            "and explain whether the notebook's historical record supports or weakens that view."
        ),
        "what_changed": (
            f"For the newest Ciovacco video {video_id}, what changed versus prior notebook entries? "
            f"Focus on what is materially different in stance, risk framing, and market situation. Current situation: {situation}"
        ),
        "ratio_logic": (
            f"Explain the current trading logic and invalidation levels for these ratios: {ratio_names}. "
            "Use past notebook history to distinguish between recurring themes and this week's fresh signal."
        ),
        "action_items": (
            "Based on the notebook's full historical memory plus the newest video, list the practical actions, "
            "watchpoints, and invalidation levels we should care about now."
        ),
    }


def _serialize_source(source: Any, *, source_added: bool) -> dict[str, Any]:
    kind = getattr(source, "kind", None)
    if hasattr(kind, "value"):
        kind = kind.value
    return {
        "id": getattr(source, "id", ""),
        "title": getattr(source, "title", None),
        "url": getattr(source, "url", None),
        "kind": kind,
        "status": getattr(source, "status", None),
        "source_added": source_added,
    }


async def _default_client_factory(storage_path: str | None):
    return await NotebookLMClient.from_storage(path=storage_path)


async def sync_ciovacco_notebooklm(
    artifact: dict,
    *,
    notebook_id: str,
    storage_path: str | None = None,
    client_factory: Callable[[str | None], Awaitable[Any]] | None = None,
) -> dict[str, Any]:
    latest_video = artifact.get("latest_video", {})
    video_url = latest_video.get("url", "")
    questions = build_ciovacco_notebooklm_questions(artifact)
    build_client = client_factory or _default_client_factory
    client = await build_client(storage_path)

    async with client as active_client:
        notebook = await active_client.notebooks.get(notebook_id)
        summary = await active_client.notebooks.get_summary(notebook_id)
        existing_sources = await active_client.sources.list(notebook_id)
        source = find_source_by_url(existing_sources, video_url)
        source_added = False
        if source is None:
            source = await active_client.sources.add_url(notebook_id, video_url, wait=False)
            source = await active_client.sources.wait_until_ready(notebook_id, source.id)
            source_added = True

        answers: dict[str, dict[str, str]] = {}
        for key, question in questions.items():
            result = await active_client.chat.ask(notebook_id, question)
            answers[key] = {
                "question": question,
                "answer": result.answer,
                "conversation_id": result.conversation_id,
            }

    return {
        "synced_at": _now_iso(),
        "notebook_id": notebook_id,
        "notebook_title": getattr(notebook, "title", ""),
        "video_id": latest_video.get("id", ""),
        "video_url": video_url,
        "summary": summary,
        "source": _serialize_source(source, source_added=source_added),
        "questions": answers,
    }
