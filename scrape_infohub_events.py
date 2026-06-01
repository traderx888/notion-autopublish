"""CLI: pull Info Hub news coverage for ad-hoc US economic-calendar events.

Used by the fundman-jarvis ``usdata`` Telegram task to surface "market
consensus" snippets for the top-3 high-impact events of the day.

Input (JSON file, via ``--events-json``):

    [
      {"name": "FOMC Meeting Minutes", "time_hkt": "02:00",
       "forecast": "", "previous": ""},
      ...
    ]

For each event we fan out to a small set of news sources, run a
``crawl run`` with the event name as the keyword, and collect whatever the
source's ``items latest`` endpoint now holds. Items are filtered back to
the event (by query-marker match or title overlap) and deduped by URL.

Output JSON (written to ``scraped_data/infohub/usdata_events_latest.json``
by default; also printed to stdout):

    {
      "generated_at": "2026-04-08T10:28:00+00:00",
      "sources_tried": ["cnbc_search", "bbc_search"],
      "events": [
        {
          "name": "FOMC Meeting Minutes",
          "time_hkt": "02:00",
          "forecast": "",
          "previous": "",
          "items": [
            {"title": "...", "url": "...", "source": "cnbc_search",
             "publish_time": "...", "query_marker": "..."}
          ],
          "errors": {}
        }
      ]
    }

The script exits 0 on best-effort success (even if some sources failed)
and non-zero only on a hard infrastructure error (Info Hub not found,
unreadable input). Callers MUST tolerate empty ``items`` lists.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Force UTF-8 stdout on Windows so non-ASCII titles don't crash cp950.
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).parent.resolve()
DEFAULT_OUTPUT = REPO_ROOT / "scraped_data" / "infohub" / "usdata_events_latest.json"

# News sources to fan out to per event. Keep this small — each source is
# one subprocess hop to the Info Hub CLI.
DEFAULT_SOURCES = ["cnbc_search", "bbc_search"]

# Words that the news-search endpoints rarely index literally. Dropping them
# from event names (e.g. "FOMC Meeting Minutes" → "FOMC Minutes") widens the
# hit rate without losing topical signal.
_EVENT_NAME_STOPWORDS = {
    "meeting", "auction", "inventories", "inventory", "index", "report",
    "release", "change", "rate", "data", "number", "numbers", "month",
    "quarter", "weekly", "monthly", "quarterly", "yearly", "annual",
    "preliminary", "revised", "final", "speaks", "speech", "statement",
    "minutes",  # kept in Fed-specific variants below via event_name verbatim
}

# Aliases injected as extra keyword variants for common US economic-calendar
# events so the underlying news search endpoints have a better chance of
# hitting topical coverage.
_EVENT_KEYWORD_ALIASES: list[tuple[tuple[str, ...], list[str]]] = [
    (("fomc", "fed", "powell", "federal reserve"),
     ["Fed", "Federal Reserve"]),
    (("nonfarm", "payroll", "nfp"),
     ["nonfarm payrolls", "US jobs"]),
    (("cpi",), ["US CPI", "inflation"]),
    (("pce",), ["PCE inflation"]),
    (("ism",), ["ISM PMI"]),
    (("crude", "oil"), ["crude oil", "oil inventories"]),
    (("treasury", "note", "bond"), ["Treasury auction", "bond yields"]),
    (("gdp",), ["US GDP"]),
    (("unemployment", "jobless"), ["jobless claims", "US labor"]),
]


def _build_event_keywords(event_name: str) -> list[str]:
    """Return an ordered, deduped list of keyword variants for one event.

    The first element is always the verbatim event name (so lineage tracking
    stays traceable). Subsequent variants are broader synonyms drawn from
    ``_EVENT_KEYWORD_ALIASES``, plus a stop-word-stripped form. Order is
    preserved by the caller's dedupe.
    """
    keywords: list[str] = [event_name]
    name_lc = event_name.lower()

    # Stop-word-stripped variant.
    stripped_tokens = [
        tok for tok in re.split(r"[^A-Za-z0-9]+", event_name)
        if tok and tok.lower() not in _EVENT_NAME_STOPWORDS
    ]
    if stripped_tokens and " ".join(stripped_tokens) != event_name:
        keywords.append(" ".join(stripped_tokens))

    # Alias variants for common event families.
    for triggers, variants in _EVENT_KEYWORD_ALIASES:
        if any(trigger in name_lc for trigger in triggers):
            for variant in variants:
                if variant not in keywords:
                    keywords.append(variant)

    # Drop empties and dedupe case-insensitively while preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for kw in keywords:
        kw = kw.strip()
        if not kw:
            continue
        key = kw.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(kw)
    return out


_LOG = logging.getLogger("scrape_infohub_events")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch Info Hub news per event")
    p.add_argument(
        "--events-json",
        required=True,
        help="Path to a JSON file containing a list of event dicts "
             "(name, time_hkt, forecast, previous).",
    )
    p.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Output JSON path (default: scraped_data/infohub/usdata_events_latest.json)",
    )
    p.add_argument(
        "--sources",
        default=",".join(DEFAULT_SOURCES),
        help="Comma-separated Info Hub source keys to crawl per event.",
    )
    p.add_argument("--days", type=int, default=2)
    p.add_argument("--max-items-per-source", type=int, default=5)
    p.add_argument(
        "--crawl-timeout",
        type=float,
        default=90.0,
        help="Per-source crawl_run timeout (seconds).",
    )
    p.add_argument(
        "--infohub-dir",
        default=None,
        help="Override Info Hub install path (else INFOHUB_DIR / sibling / hardcoded).",
    )
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _load_events(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"{path}: expected a JSON list of event dicts")
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("event") or "").strip()
        if not name:
            continue
        out.append({
            "name": name,
            "time_hkt": str(item.get("time_hkt") or "").strip(),
            "forecast": str(item.get("forecast") or "").strip(),
            "previous": str(item.get("previous") or "").strip(),
        })
    return out


# Words that are too generic to be a match signal on their own, even when
# they appear in an event name ("10-Year Note AUCTION" → "auction" alone
# pulls in unrelated headlines like "Signed Oasis guitar up for auction").
_GENERIC_MATCH_STOPWORDS = {
    "the", "and", "for", "are", "was", "with", "from", "year", "note",
    "day", "rate", "data", "high", "low", "new", "top", "big", "all",
    "week", "month", "time", "news",
}


def _significant_tokens(text: str) -> set[str]:
    """Extract tokens suitable for title-match filtering.

    Keeps tokens that are (a) ≥3 chars, (b) not in the event-name
    stopword list, and (c) not in the generic match-stopword list. This
    lets acronyms like "Fed" / "FOMC" / "CPI" through while dropping filler
    words like "meeting", "auction", "year".
    """
    out: set[str] = set()
    for raw in re.split(r"[^A-Za-z0-9]+", text or ""):
        tok = raw.strip().lower()
        if not tok or len(tok) < 3:
            continue
        if tok in _EVENT_NAME_STOPWORDS or tok in _GENERIC_MATCH_STOPWORDS:
            continue
        out.add(tok)
    return out


def _build_match_tokens(event_name: str, variants: list[str]) -> set[str]:
    """Union of significant tokens across the event name and all variants."""
    tokens: set[str] = set()
    tokens.update(_significant_tokens(event_name))
    for v in variants:
        tokens.update(_significant_tokens(v))
    return tokens


def _item_matches_tokens(item: dict[str, Any], match_tokens: set[str]) -> bool:
    """True if the item's title contains any significant token."""
    if not match_tokens:
        return False
    title = str(item.get("title") or "").lower()
    if not title:
        return False
    title_tokens = _significant_tokens(title)
    return bool(match_tokens & title_tokens)


# Back-compat shim so the existing tests (and _item_matches_any_variant)
# can keep calling _item_matches_event with just the raw event name.
def _item_matches_event(item: dict[str, Any], event_name: str) -> bool:
    match_tokens = _build_match_tokens(event_name, [event_name])
    return _item_matches_tokens(item, match_tokens)


def _slim_item(item: dict[str, Any], source: str) -> dict[str, Any]:
    lineage_raw = item.get("lineage_json") or ""
    query_marker = ""
    if isinstance(lineage_raw, str) and lineage_raw:
        try:
            query_marker = str(json.loads(lineage_raw).get("query_marker") or "")
        except json.JSONDecodeError:
            query_marker = ""
    return {
        "title": str(item.get("title") or "").strip(),
        "url": str(item.get("url") or "").strip(),
        "source": source,
        "publish_time": str(item.get("publish_time") or "").strip(),
        "fetched_at": str(item.get("fetched_at") or "").strip(),
        "query_marker": query_marker,
    }


def _collect_for_event(
    client,  # infohub_research.bridge.InfoHubClient
    event_name: str,
    *,
    sources: list[str],
    days: int,
    max_items_per_source: int,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Run a crawl per source for one event and return (items, errors)."""
    from infohub_research.bridge import InfoHubError  # local import

    collected: list[dict[str, Any]] = []
    errors: dict[str, str] = {}
    seen_urls: set[str] = set()

    keyword_variants = _build_event_keywords(event_name)
    match_tokens = _build_match_tokens(event_name, keyword_variants)

    for source in sources:
        crawl_hit_count = 0
        try:
            # Pass ALL variants as one crawl — Info Hub will OR-search them.
            summary = client.crawl_run(
                source=source,
                keywords=keyword_variants,
                days=days,
                max_items=max_items_per_source,
            )
            try:
                crawl_hit_count = int(summary.get("items", 0) or 0)
            except (TypeError, ValueError):
                crawl_hit_count = 0
            items = client.items_latest(source=source, limit=max_items_per_source * 4)
        except InfoHubError as exc:
            errors[source] = str(exc)
            _LOG.warning("crawl failed for %s/%s: %s", event_name, source, exc)
            continue

        # If crawl_run ingested nothing fresh, items_latest will return
        # stale unrelated items — skip the matching loop entirely.
        if crawl_hit_count <= 0:
            _LOG.info("no fresh items for %s on %s", event_name, source)
            continue

        matched = 0
        for raw in items:
            if not isinstance(raw, dict):
                continue
            if not _item_matches_tokens(raw, match_tokens):
                continue
            slim = _slim_item(raw, source)
            if not slim["url"] or slim["url"] in seen_urls:
                continue
            seen_urls.add(slim["url"])
            collected.append(slim)
            matched += 1
            if matched >= max_items_per_source:
                break

    # Sort newest first by publish_time (lexicographic is fine for ISO-ish).
    collected.sort(key=lambda it: it.get("publish_time") or "", reverse=True)
    return collected, errors


def main() -> int:
    args = _parse_args()
    _setup_logging(args.verbose)

    events_path = Path(args.events_json)
    if not events_path.exists():
        print(f"ERROR: events file not found: {events_path}", file=sys.stderr)
        return 2

    try:
        events = _load_events(events_path)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: could not parse {events_path}: {exc}", file=sys.stderr)
        return 2

    if not events:
        print(f"WARN: no events in {events_path}", file=sys.stderr)

    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    if not sources:
        sources = list(DEFAULT_SOURCES)

    # Import lazily so bad input errors surface before we probe Info Hub.
    from infohub_research.bridge import InfoHubClient, InfoHubError

    try:
        client = InfoHubClient(
            infohub_dir=args.infohub_dir,
            crawl_timeout=args.crawl_timeout,
        )
    except InfoHubError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3

    results: list[dict[str, Any]] = []
    for ev in events:
        items, errors = _collect_for_event(
            client,
            ev["name"],
            sources=sources,
            days=args.days,
            max_items_per_source=args.max_items_per_source,
        )
        results.append({
            "name": ev["name"],
            "time_hkt": ev["time_hkt"],
            "forecast": ev["forecast"],
            "previous": ev["previous"],
            "items": items,
            "errors": errors,
        })

    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources_tried": sources,
        "events": results,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Also emit to stdout so the caller (fundman-jarvis subprocess bridge)
    # can parse without re-reading the file.
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
