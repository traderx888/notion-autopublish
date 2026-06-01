"""Map a screening target onto an Info Hub watch-profile activation payload.

Info Hub's watch profiles are taxonomy-anchored — the ``focus`` keyword must
come from a small allow-list defined in
``Info Hub/docs/taxonomy/<domain>.yml``. We can't use raw tickers there.

The strategy: choose a *coarse umbrella* focus keyword per (kind, source)
combo, then put the actual differentiating keywords (tickers, family
phrases) into ``queries``. Multiple targets will share an umbrella; that
is fine — per-target news still gets fetched via ``crawl run --keywords``
and stored in per-target output files.
"""

from __future__ import annotations

from typing import Any

from .targets import ScreeningTarget


# Crawl source families per kind. Only sources we know accept --keywords
# (run_type=keyword_endtime) are listed.
_SOURCE_PRESETS: dict[str, list[str]] = {
    "ticker": [
        "cnbc_search",
        "wsj_search",
        "seekingalpha",
        "substack",
        "reddit",
    ],
    "sector": [
        "cnbc_search",
        "wsj_search",
        "bbc_search",
    ],
    "macro_keyword": [
        "bbc_search",
        "cnbc_search",
        "reddit",
        "matt_levine",
    ],
    "event_topic": [
        "bbc_search",
        "reddit",
        "cnbc_search",
    ],
}


# (kind, source-or-family) → (domain_l1, theme_l2, focus_l3)
def _resolve_taxonomy(target: ScreeningTarget) -> tuple[str, str, str]:
    kind = target.kind
    src = (target.source or "").lower()
    if kind == "ticker":
        return "finance", "equities", "earnings reset"
    if kind == "sector":
        return "finance", "equities", "multiple expansion"
    if kind == "event_topic":
        return "finance", "macro", "inflation surprise"
    if kind == "macro_keyword":
        if src == "liquidity_tracker":
            return "finance", "macro", "fed cuts"
        if src == "dailychartbook":
            slug = target.slug
            if slug in {"dcb_policy_rates", "dcb_liquidity"}:
                return "finance", "macro", "fed cuts"
            if slug in {"dcb_macro_growth"}:
                return "finance", "macro", "nonfarm payrolls"
            return "finance", "macro", "inflation surprise"
        return "finance", "macro", "inflation surprise"
    return "finance", "macro", "inflation surprise"


def _priority_for(target: ScreeningTarget) -> int:
    src = (target.source or "").lower()
    note = (target.note or "").upper()
    if src == "stockbee_ep":
        return 80
    if src == "deepvue_capscreen":
        return 60
    if src == "dailychartbook" and note.startswith("STRONG_"):
        return 55
    if src == "dailychartbook":
        return 50
    if src == "liquidity_tracker":
        return 50
    if src in ("semianalysis", "fomo"):
        return 40
    if src == "deepvue_stage":
        return 35
    return 30


def build_profile_spec(target: ScreeningTarget) -> dict[str, Any]:
    """Translate one target into the kwargs for ``InfoHubClient.activate_profile``.

    The returned dict also carries a ``sources`` list (the actual crawl
    sources to fan out to) and a ``crawl_keywords`` list (what to send to
    ``crawl run --keywords``). Both are persisted in the per-target output
    JSON for traceability.
    """
    domain, theme, focus = _resolve_taxonomy(target)
    sources = _SOURCE_PRESETS.get(target.kind, _SOURCE_PRESETS["macro_keyword"])

    # Use the umbrella focus + the target's own keywords as query seeds.
    queries: list[str] = [focus]
    for k in target.keywords:
        if k and k not in queries:
            queries.append(k)

    name_label = {
        "ticker": "Equity ticker watch",
        "sector": "Equity sector watch",
        "macro_keyword": "Macro signal watch",
        "event_topic": "Event topic watch",
    }.get(target.kind, "Info Hub research watch")

    return {
        "name": name_label,
        "domain": domain,
        "theme": theme,
        "focus": focus,
        "queries": queries,
        "sources": sources,
        "priority": _priority_for(target),
        "notes": f"infohub_research bridge: kind={target.kind} source={target.source}",
        # Per-target crawl payload (not part of the activate-profile flags
        # — kept here so research.py doesn't need to recompute it).
        "crawl_keywords": list(target.keywords),
    }
