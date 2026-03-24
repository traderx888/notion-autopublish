from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Iterable

from notebooklm import NotebookLMClient

# Re-use URL helpers from ciovacco module (don't duplicate)
from ciovacco.notebooklm_sync import canonicalize_source_url, find_source_by_url


_SECTION_TITLES = {
    "earnings_change": "Earnings Change",
    "management_tone": "Management Tone",
    "thesis_validity": "Thesis Validity",
    "key_risks": "Key Risks",
}

_QUESTION_ORDER = ["earnings_change", "management_tone", "thesis_validity", "key_risks"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_research_config(
    *,
    notebook_id: str | None = None,
    storage_path: str | None = None,
    env: dict[str, str] | None = None,
    ticker: str | None = None,
) -> dict[str, str | None]:
    env_map = env or {}
    # Ticker-specific env var first, then generic fallback
    ticker_key = f"FUNDAMENTAL_NOTEBOOKLM_NOTEBOOK_ID_{(ticker or '').upper()}"
    resolved_nb = (
        notebook_id
        or env_map.get(ticker_key, "")
        or env_map.get("FUNDAMENTAL_NOTEBOOKLM_NOTEBOOK_ID", "")
    ).strip()
    if not resolved_nb:
        raise ValueError(
            f"Missing NotebookLM notebook ID. Pass --notebook-id or set {ticker_key}."
        )
    resolved_storage = (
        storage_path
        or env_map.get("NOTEBOOKLM_STORAGE_PATH", "")
        or env_map.get("FUNDAMENTAL_NOTEBOOKLM_STORAGE", "")
    ).strip() or None
    return {"notebook_id": resolved_nb, "storage_path": resolved_storage}


def build_fundamental_questions(signal: dict) -> dict[str, str]:
    ticker = signal.get("ticker", "").upper()
    sector = signal.get("sector", "")
    trigger_signal = signal.get("trigger_signal", "")

    return {
        "earnings_change": (
            f"For {ticker} ({sector}), what changed in the most recently added sources "
            f"versus historical notebook entries? Focus on: earnings beats/misses, revenue/margin guidance "
            f"revisions, and any surprise vs consensus. The trigger signal was: {trigger_signal}. "
            "Use notebook history to quantify the delta, not just describe the current state."
        ),
        "management_tone": (
            f"Analyse the management tone shift for {ticker} across the notebook sources. "
            "Look for: hedging language increases or decreases, capital allocation changes (buybacks, capex), "
            "confidence signals in forward guidance, and any notable changes in how leadership frames risk."
        ),
        "thesis_validity": (
            f"Based on all notebook sources for {ticker} in the {sector} sector, is the current bull thesis "
            f"intact, impaired, or strengthened after the '{trigger_signal}' signal? "
            "State the single strongest supporting evidence and the single biggest threat. "
            "End with: INTACT / IMPAIRED / STRENGTHENED."
        ),
        "key_risks": (
            f"List the actionable risk watchpoints and invalidation levels for {ticker} from the combined "
            "notebook sources. For each risk: (1) what is the catalyst, (2) what price/data level invalidates "
            "the thesis, (3) what timeframe. Rank by probability × impact."
        ),
    }


def render_research_markdown(
    *,
    signal: dict,
    answers: dict[str, dict[str, str]],
    notebook_id: str,
    notebook_title: str,
    synced_at: str,
) -> str:
    ticker = signal.get("ticker", "")
    sector = signal.get("sector", "")
    trigger_source = signal.get("trigger_source", "")
    trigger_signal = signal.get("trigger_signal", "")
    youtube_urls = signal.get("youtube_urls", [])

    url_lines = "\n".join(f"  - {u}" for u in youtube_urls) if youtube_urls else "  []"

    frontmatter = (
        "---\n"
        f"ticker: {ticker}\n"
        f"sector: {sector}\n"
        f"trigger_source: {trigger_source}\n"
        f"trigger_signal: {trigger_signal}\n"
        f"notebook_id: {notebook_id}\n"
        f"notebook_title: {notebook_title}\n"
        f"synced_at: {synced_at}\n"
        f"youtube_urls:\n{url_lines}\n"
        "---\n"
    )

    body_parts = [f"# Fundamental Research: {ticker}\n"]
    body_parts.append(f"**Sector:** {sector}  \n**Triggered by:** {trigger_source} — {trigger_signal}  \n**Synced:** {synced_at}\n")

    for key in _QUESTION_ORDER:
        if key not in answers:
            continue
        title = _SECTION_TITLES.get(key, key.replace("_", " ").title())
        answer_text = answers[key].get("answer", "")
        body_parts.append(f"\n## {title}\n\n{answer_text}\n")

    return frontmatter + "\n".join(body_parts)


async def _default_client_factory(storage_path: str | None):
    return await NotebookLMClient.from_storage(path=storage_path)


async def sync_fundamental_research(
    signal: dict,
    *,
    notebook_id: str,
    storage_path: str | None = None,
    client_factory: Callable[[str | None], Awaitable[Any]] | None = None,
) -> dict[str, Any]:
    """
    Core async function: adds YouTube URLs to a NLM notebook, asks structured
    fundamental questions, and returns a result dict including rendered_md.

    signal keys: ticker, sector, trigger_source, trigger_signal, youtube_urls (list)
    """
    youtube_urls: list[str] = signal.get("youtube_urls", [])
    questions = build_fundamental_questions(signal)
    build_client = client_factory or _default_client_factory
    client = await build_client(storage_path)

    async with client as active_client:
        notebook = await active_client.notebooks.get(notebook_id)
        summary = await active_client.notebooks.get_summary(notebook_id)
        existing_sources = await active_client.sources.list(notebook_id)

        sources_added = []
        for url in youtube_urls:
            source = find_source_by_url(existing_sources, url)
            if source is None:
                source = await active_client.sources.add_url(notebook_id, url, wait=False)
                source = await active_client.sources.wait_until_ready(notebook_id, source.id)
                sources_added.append(url)

        answers: dict[str, dict[str, str]] = {}
        for key, question in questions.items():
            result = await active_client.chat.ask(notebook_id, question)
            answers[key] = {
                "question": question,
                "answer": result.answer,
                "conversation_id": result.conversation_id,
            }

    synced_at = _now_iso()
    rendered_md = render_research_markdown(
        signal=signal,
        answers=answers,
        notebook_id=notebook_id,
        notebook_title=getattr(notebook, "title", ""),
        synced_at=synced_at,
    )

    return {
        "synced_at": synced_at,
        "ticker": signal.get("ticker", ""),
        "notebook_id": notebook_id,
        "notebook_title": getattr(notebook, "title", ""),
        "summary": summary,
        "sources_added": sources_added,
        "answers": answers,
        "rendered_md": rendered_md,
    }
