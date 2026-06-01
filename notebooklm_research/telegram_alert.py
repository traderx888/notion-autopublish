"""Telegram alert for NotebookLM research results.

Sends a brief summary plus the full analyst briefing (簡報) to Telegram
when research completes for a ticker.
"""

from __future__ import annotations

import html
import os
import urllib.parse
import urllib.request
from typing import Any

# Telegram limits a single sendMessage payload to 4096 UTF-16 code units.
# Stay well under that to leave room for the header.
TELEGRAM_MAX_CHARS = 3800


def format_research_alert(payload: dict[str, Any]) -> str:
    """Format a research result into a Telegram-friendly HTML summary."""
    ticker = payload.get("ticker", "?")
    signal = payload.get("signal", {})
    source = signal.get("source", "manual")
    grade = signal.get("grade", "")
    gap_pct = signal.get("gap_pct", 0)
    questions = payload.get("questions", {})
    sources = payload.get("youtube_sources", [])

    def esc(s: Any) -> str:
        return html.escape(str(s), quote=False)

    # Header
    parts = [f"🔬 <b>NotebookLM Research: {esc(ticker)}</b>"]

    # Signal info
    signal_parts = [f"Source: {esc(source)}"]
    if grade:
        signal_parts.append(f"Grade: {esc(grade)}")
    if gap_pct:
        signal_parts.append(f"Gap: {gap_pct:.1f}%")
    parts.append(" | ".join(signal_parts))

    # YouTube sources
    source_count = len(sources)
    added_count = sum(1 for s in sources if s.get("added"))
    parts.append(f"📹 {source_count} videos ({added_count} new)")

    # Key findings (first 2 sentences of each answer)
    parts.append("")
    for key, qa in questions.items():
        answer = qa.get("answer", "")
        if answer.startswith("[ERROR]"):
            continue
        sentences = answer.replace("\n", " ").split(". ")
        brief = ". ".join(sentences[:2])
        if len(brief) > 300:
            brief = brief[:297] + "..."
        label = key.replace("_", " ").title()
        parts.append(f"<b>{esc(label)}:</b> {esc(brief)}")

    return "\n".join(parts)


def _chunk_text(text: str, limit: int = TELEGRAM_MAX_CHARS) -> list[str]:
    """Split long text into Telegram-sized chunks on paragraph boundaries."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        # Prefer to break on a double newline, then single newline, then space.
        cut = remaining.rfind("\n\n", 0, limit)
        if cut == -1:
            cut = remaining.rfind("\n", 0, limit)
        if cut == -1:
            cut = remaining.rfind(" ", 0, limit)
        if cut == -1 or cut < limit // 2:
            cut = limit
        chunks.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks


def _post_message(
    token: str,
    chat_id: str,
    text: str,
    *,
    parse_mode: str | None = "Markdown",
) -> bool:
    """POST a single message to Telegram. Returns True on HTTP 200."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    data = urllib.parse.urlencode(payload).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status == 200
    except Exception as exc:
        print(f"[Telegram] Failed to send message: {exc}")
        return False


def send_research_alert(
    payload: dict[str, Any],
    *,
    bot_token: str | None = None,
    chat_id: str | None = None,
) -> bool:
    """Send research summary + analyst briefing to Telegram.

    Uses TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars if not provided.

    Sends two logical messages:
      1. Markdown-formatted summary (signal info + question excerpts)
      2. The full 簡報 (analyst briefing) as plain-text, split into
         multiple messages if it exceeds Telegram's per-message limit.

    Returns True if every message in the sequence delivered successfully.
    """
    token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    cid = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not cid:
        print("[Telegram] Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
        return False

    summary = format_research_alert(payload)
    ok = _post_message(token, cid, summary, parse_mode="HTML")

    briefing = (payload.get("briefing") or "").strip()
    if not briefing:
        err = payload.get("briefing_error", "")
        if err:
            _post_message(
                token, cid,
                f"⚠️ Briefing generation failed for "
                f"{payload.get('ticker', '?')}: {err}",
                parse_mode=None,
            )
        return ok

    ticker = payload.get("ticker", "?")
    chunks = _chunk_text(briefing)
    total = len(chunks)
    for idx, chunk in enumerate(chunks, start=1):
        header = (
            f"📄 簡報 {ticker} ({idx}/{total})\n\n"
            if total > 1
            else f"📄 簡報 {ticker}\n\n"
        )
        # Plain text (no parse_mode) — the briefing contains many `*` `_` `[`
        # characters that would otherwise break Markdown parsing.
        ok = _post_message(token, cid, header + chunk, parse_mode=None) and ok

    return ok


def send_research_alert_sync(payload: dict[str, Any]) -> bool:
    """Synchronous wrapper for use as on_ticker_complete callback."""
    return send_research_alert(payload)
