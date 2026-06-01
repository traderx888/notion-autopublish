"""Core async research sync via notebooklm-py.

Pattern follows ciovacco/notebooklm_sync.py — async client with
factory injection for testing.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable

from notebooklm import NotebookLMClient

from .briefing_prompt import build_briefing_prompt
from .notebook_manager import get_or_create_notebook, load_registry, save_registry
from .question_templates import select_question_set
from .youtube_discovery import (
    build_search_queries,
    filter_recent_videos,
    search_ticker_videos,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonicalize_youtube_url(url: str) -> str:
    """Normalise YouTube URL to canonical form for dedup."""
    from urllib.parse import parse_qs, urlparse

    parsed = urlparse(url)
    if "youtu.be" in parsed.netloc.lower():
        video_id = parsed.path.strip("/").split("/")[0]
    else:
        video_id = parse_qs(parsed.query).get("v", [""])[0]
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    return url.strip()


def _find_source_by_url(sources: Iterable[Any], url: str) -> Any | None:
    """Find an existing NotebookLM source matching a URL."""
    canonical = _canonicalize_youtube_url(url)
    for source in sources:
        source_url = getattr(source, "url", None) or ""
        if _canonicalize_youtube_url(source_url) == canonical:
            return source
    return None


async def _default_client_factory(storage_path: str | None):
    return await NotebookLMClient.from_storage(path=storage_path)


def _build_deep_research_queries(ticker: str, target: dict) -> list[str]:
    """Build deep research queries for NotebookLM's web research feature."""
    source = target.get("source", "")
    year = __import__("datetime").datetime.now().year

    queries = [
        f"{ticker} latest earnings analysis management commentary {year}",
        f"{ticker} industry outlook competitive landscape {year}",
    ]

    if source in ("semianalysis", "fomo"):
        queries.append(f"{ticker} supply chain capacity analysis research {year}")
    elif source == "stockbee_ep":
        grade = target.get("grade", "")
        queries.append(f"{ticker} stock catalyst growth drivers analyst upgrade {year}")
        if grade in ("SUPER_SWAN", "SWAN"):
            queries.append(f"{ticker} institutional buying insider activity {year}")
    else:
        queries.append(f"{ticker} fundamental analysis research report {year}")

    return queries


async def _run_deep_research(
    client: Any,
    notebook_id: str,
    queries: list[str],
    *,
    max_sources_per_query: int = 5,
) -> list[dict]:
    """Run NotebookLM's built-in deep research to discover and import web sources.

    Uses NotebookLM's research API to search the web for relevant articles,
    management interviews, industry analysis, research papers, etc.
    All processing happens on Google's side.

    The research API returns dicts (not objects):
    - start() → {"task_id": ..., "report_id": ..., ...} or None
    - poll()  → {"status": "completed"|"in_progress", "sources": [...], ...}
    - import_sources() expects list of dicts with "url" and "title" keys
    """
    imported_sources: list[dict] = []

    for query in queries:
        try:
            print(f"[NLM Research] Deep research: {query[:60]}...")
            task = await client.research.start(notebook_id, query, source="web")
            if task is None:
                print(f"[NLM Research]   Failed to start research for: {query[:40]}")
                continue
            task_id = task.get("task_id", "")

            # Poll for results (up to 90s per query)
            result = None
            for _ in range(18):
                await __import__("asyncio").sleep(5)
                try:
                    result = await client.research.poll(notebook_id)
                    status = result.get("status", "")
                    if status == "completed":
                        break
                except Exception:
                    continue

            if result is None or result.get("status") != "completed":
                print(f"[NLM Research]   Research timed out for: {query[:40]}")
                continue

            # Get discovered sources (list of dicts with url/title)
            discovered = result.get("sources", [])
            if not discovered:
                print(f"[NLM Research]   No sources found for: {query[:40]}")
                continue

            sources_to_import = discovered[:max_sources_per_query]
            print(f"[NLM Research]   Found {len(discovered)} sources, importing {len(sources_to_import)} one by one...")

            # Import sources one at a time to avoid RPC timeout
            for src in sources_to_import:
                try:
                    await client.research.import_sources(
                        notebook_id, task_id, [src],
                    )
                    imported_sources.append({
                        "title": src.get("title", ""),
                        "url": src.get("url", ""),
                        "type": "deep_research",
                        "query": query,
                    })
                    print(f"[NLM Research]     + {src.get('title', '')[:50]}")
                except Exception as exc:
                    print(f"[NLM Research]     x Failed: {src.get('title', '')[:30]} — {exc}")

        except Exception as exc:
            print(f"[NLM Research]   Deep research error: {exc}")

    return imported_sources


async def research_ticker(
    target: dict[str, Any],
    *,
    client: Any,
    registry: dict[str, str],
    registry_path: Path,
    output_dir: Path,
    max_youtube: int = 3,
    deep_research: bool = True,
    max_deep_research_queries: int = 3,
    cookies_file: Path | None = None,
) -> dict[str, Any]:
    """Run NotebookLM research for a single ticker.

    1. Get or create a per-ticker notebook
    2. Search YouTube for relevant videos and add as sources
    3. Run NotebookLM deep research to find web articles, interviews, papers
    4. Ask fundamental questions against all sources
    5. Save and return structured result
    """
    ticker = target["ticker"]
    notebook_id = await get_or_create_notebook(
        client, ticker, registry, registry_path,
    )

    # ── Step 1: YouTube discovery ─────────────────────────────
    queries = build_search_queries(ticker, context=target)
    videos = search_ticker_videos(
        ticker, queries, limit_per_query=2, cookies_file=cookies_file,
    )
    videos = filter_recent_videos(videos, max_age_days=90)
    videos = videos[:max_youtube]

    # Add YouTube sources (dedup)
    existing_sources = await client.sources.list(notebook_id)
    sources_added: list[dict] = []

    for video in videos:
        existing = _find_source_by_url(existing_sources, video["url"])
        added = False
        if existing is None:
            try:
                src = await client.sources.add_url(
                    notebook_id, video["url"], wait=False,
                )
                await client.sources.wait_until_ready(notebook_id, src.id)
                added = True
            except Exception as exc:
                print(f"[NLM Research] Failed to add source {video['url']}: {exc}")
        sources_added.append({
            "url": video["url"],
            "title": video.get("title", ""),
            "channel": video.get("channel", ""),
            "type": "youtube",
            "added": added,
        })

    # ── Step 2: NotebookLM Deep Research ──────────────────────
    deep_research_sources: list[dict] = []
    if deep_research:
        dr_queries = _build_deep_research_queries(ticker, target)
        dr_queries = dr_queries[:max_deep_research_queries]
        try:
            deep_research_sources = await _run_deep_research(
                client, notebook_id, dr_queries,
                max_sources_per_query=5,
            )
        except Exception as exc:
            print(f"[NLM Research] Deep research failed for {ticker}: {exc}")

    # ── Step 3: Ask fundamental questions ─────────────────────
    questions = select_question_set(target)
    answers: dict[str, dict[str, str]] = {}
    for key, question in questions.items():
        try:
            result = await client.chat.ask(notebook_id, question)
            answers[key] = {
                "question": question,
                "answer": result.answer,
                "conversation_id": getattr(result, "conversation_id", ""),
            }
        except Exception as exc:
            answers[key] = {
                "question": question,
                "answer": f"[ERROR] {exc}",
                "conversation_id": "",
            }

    # ── Step 4: Generate analyst briefing (簡報) ───────────────
    briefing_text = ""
    briefing_error = ""
    try:
        briefing_prompt = build_briefing_prompt(
            ticker, stock_name=target.get("stock_name"),
        )
        briefing_result = await client.chat.ask(notebook_id, briefing_prompt)
        briefing_text = getattr(briefing_result, "answer", "") or ""
    except Exception as exc:
        briefing_error = str(exc)
        print(f"[NLM Research] Briefing failed for {ticker}: {exc}")

    # Build payload
    all_sources = sources_added + deep_research_sources
    payload = {
        "ticker": ticker,
        "researched_at": _now_iso(),
        "signal": {
            k: v for k, v in target.items() if k != "ticker"
        },
        "notebook_id": notebook_id,
        "youtube_sources": sources_added,
        "deep_research_sources": deep_research_sources,
        "total_sources": len(all_sources),
        "questions": answers,
        "briefing": briefing_text,
        "briefing_error": briefing_error,
    }

    # Save per-ticker JSON
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{ticker}_research.json"
    out_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return payload


async def run_research_batch(
    targets: list[dict[str, Any]],
    *,
    storage_path: str | None = None,
    output_dir: Path,
    registry_path: Path | None = None,
    client_factory: Callable[[str | None], Awaitable[Any]] | None = None,
    max_youtube: int = 3,
    deep_research: bool = True,
    cookies_file: Path | None = None,
    on_ticker_complete: Callable[[dict], Any] | None = None,
) -> list[dict[str, Any]]:
    """Research a batch of tickers in a single NotebookLM session.

    Args:
        targets: List of signal target dicts from signals.py.
        storage_path: NotebookLM auth storage state path.
        output_dir: Where to write per-ticker JSON output.
        registry_path: Path to notebook_registry.json.
        client_factory: Async callable returning a NotebookLM client.
        max_youtube: Max YouTube sources per ticker.
        deep_research: Run NotebookLM deep research for web sources.
        cookies_file: Optional YouTube cookies path.
        on_ticker_complete: Callback after each ticker completes (e.g. Telegram alert).

    Returns:
        List of research payloads.
    """
    if not targets:
        return []

    reg_path = registry_path or (output_dir / "notebook_registry.json")
    registry = load_registry(reg_path)
    build_client = client_factory or _default_client_factory

    client = await build_client(storage_path)
    results: list[dict[str, Any]] = []

    async with client as active_client:
        for target in targets:
            try:
                payload = await research_ticker(
                    target,
                    client=active_client,
                    registry=registry,
                    registry_path=reg_path,
                    output_dir=output_dir,
                    max_youtube=max_youtube,
                    deep_research=deep_research,
                    cookies_file=cookies_file,
                )
                results.append(payload)
                if on_ticker_complete:
                    try:
                        on_ticker_complete(payload)
                    except Exception:
                        pass
            except Exception as exc:
                print(f"[NLM Research] Failed for {target.get('ticker', '?')}: {exc}")
                results.append({
                    "ticker": target.get("ticker", ""),
                    "error": str(exc),
                    "researched_at": _now_iso(),
                })

    return results
