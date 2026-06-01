"""Extra screening extractors that complement notebooklm_research.signals.

Each extractor returns a list of normalized dicts shaped for ``targets.py``:

    {
        "kind": "ticker" | "sector" | "macro_keyword" | "event_topic",
        "slug": "<filesystem-safe identifier>",
        "keywords": [<crawl query strings>],
        "source": "<provenance label>",
        "note": "<optional human note>",
        ...source-specific fields preserved for traceability
    }
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


# ── DCB family → keyword phrases ─────────────────────────────────

_DCB_PHRASE_MAP: dict[str, list[str]] = {
    "DCB_MACRO_GROWTH": ["macro growth", "ISM PMI", "economic surprises"],
    "DCB_POLICY_RATES": ["fed policy", "interest rates", "FOMC"],
    "DCB_LIQUIDITY": ["liquidity", "bank reserves", "RRP TGA"],
    "DCB_RISK_SENTIMENT": ["risk sentiment", "volatility", "credit spreads"],
    "DCB_POSITIONING": ["positioning", "CTA flows", "systematic"],
    "DCB_EARNINGS_REVISIONS": ["earnings revisions", "analyst estimates", "guidance"],
}

# Signals strong enough to be worth a watch profile.
_DCB_STRONG_SIGNALS = {"BULL", "BEAR", "STRONG_BULL", "STRONG_BEAR"}


def extract_dcb_targets(readings_path: Path) -> list[dict[str, Any]]:
    """Build macro_keyword targets from Dailychartbook family scorecard.

    Picks ``readings[]`` rows whose ``signal`` is in {BULL, BEAR, STRONG_BULL,
    STRONG_BEAR}, mapping the family ticker (DCB_*) to a small bag of keyword
    phrases the news crawlers can actually search on.
    """
    if not readings_path.exists():
        return []

    try:
        data = json.loads(readings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    out: list[dict[str, Any]] = []
    for row in data.get("readings", []):
        ticker = row.get("ticker", "")
        if not ticker.startswith("DCB_"):
            continue
        signal = (row.get("signal") or "").upper()
        if signal not in _DCB_STRONG_SIGNALS:
            continue
        phrases = _DCB_PHRASE_MAP.get(ticker)
        if not phrases:
            continue
        out.append({
            "kind": "macro_keyword",
            "slug": ticker.lower(),
            "keywords": phrases,
            "source": "dailychartbook",
            "note": signal,
            "bull_score": row.get("bull_score"),
            "bear_score": row.get("bear_score"),
            "value": row.get("value"),
        })
    return out


# ── Polymarket trader_tags → event topics ────────────────────────

# Map tag fragments to (topic_slug, search keywords). Generic threshold
# descriptors like "Overall PnL > $1m" simply won't match any pattern below
# and are silently dropped.
_POLYMARKET_TOPIC_MAP: list[tuple[re.Pattern, str, list[str]]] = [
    (re.compile(r"us election", re.I), "us_election",
     ["US election", "presidential election", "polymarket election"]),
    (re.compile(r"\bpolitics\b", re.I), "politics",
     ["politics", "political risk", "election odds"]),
    (re.compile(r"\bsports\b", re.I), "sports",
     ["sports betting", "polymarket sports"]),
    (re.compile(r"\bcrypto\b", re.I), "crypto",
     ["crypto", "bitcoin", "ethereum"]),
    (re.compile(r"french whale", re.I), "france",
     ["France politics", "French election"]),
]


def _split_trader_tags(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(t).strip() for t in raw if str(t).strip()]
    if isinstance(raw, str):
        return [t.strip() for t in raw.split(";") if t.strip()]
    return []


def extract_polymarket_targets(signals_path: Path) -> list[dict[str, Any]]:
    """Build event_topic targets from Polymarket trader_signals."""
    if not signals_path.exists():
        return []

    try:
        data = json.loads(signals_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    seen: dict[str, dict[str, Any]] = {}
    for trader in data.get("tracked_traders", []):
        for tag in _split_trader_tags(trader.get("trader_tags")):
            # Match topic patterns FIRST. If none hit, fall through to the
            # noise filter (which would otherwise drop "Politics PnL > $100k"
            # before we noticed the "Politics" topic).
            for pattern, slug, keywords in _POLYMARKET_TOPIC_MAP:
                if pattern.search(tag):
                    if slug in seen:
                        seen[slug]["mention_count"] += 1
                    else:
                        seen[slug] = {
                            "kind": "event_topic",
                            "slug": slug,
                            "keywords": keywords,
                            "source": "polymarket",
                            "note": tag[:120],
                            "mention_count": 1,
                        }
                    break
    return list(seen.values())


# ── Liquidity tracker H-Model → macro keyword bundle ─────────────

_NOUN_PHRASE_RE = re.compile(r"\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})\b")

# Words that look capitalized but are too generic to be useful keywords.
_NOUN_PHRASE_STOPLIST = {
    "We", "It", "They", "This", "That", "Broadly", "Over", "If", "As", "Now",
    "But", "And", "We Might", "Risk On", "Risk Off",
}


def _extract_keyphrases(evidence: list[str], limit: int = 6) -> list[str]:
    seen: list[str] = []
    for line in evidence:
        for match in _NOUN_PHRASE_RE.finditer(line):
            phrase = match.group(1).strip()
            if phrase in _NOUN_PHRASE_STOPLIST:
                continue
            if len(phrase) < 4:
                continue
            if phrase in seen:
                continue
            seen.append(phrase)
            if len(seen) >= limit:
                return seen
    return seen


def extract_liquidity_targets(
    h_model_path: Path,
    *,
    min_score_magnitude: int = 50,
) -> list[dict[str, Any]]:
    """Build a macro_keyword target from the H-Model liquidity tracker.

    Only emits a target if the H-Model is fresh (``available is True``) and the
    absolute signal_score crosses ``min_score_magnitude``.
    """
    if not h_model_path.exists():
        return []

    try:
        data = json.loads(h_model_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    if not data.get("available"):
        return []

    score = data.get("signal_score")
    try:
        if abs(int(score)) < min_score_magnitude:
            return []
    except (TypeError, ValueError):
        return []

    bias = (data.get("market_bias") or "").lower()
    direction = (data.get("liquidity_direction") or "").lower()
    bias_label = "contracting liquidity" if "contract" in direction else "expanding liquidity"

    keyphrases = _extract_keyphrases(data.get("evidence", []) or [])
    keywords: list[str] = [bias_label]
    if bias:
        keywords.append(bias.replace("_", " "))
    keywords.extend(keyphrases)
    # Drop duplicates preserving order.
    deduped: list[str] = []
    seen_set: set[str] = set()
    for k in keywords:
        kl = k.lower()
        if kl in seen_set:
            continue
        seen_set.add(kl)
        deduped.append(k)

    return [{
        "kind": "macro_keyword",
        "slug": "liquidity_h_model",
        "keywords": deduped[:8],
        "source": "liquidity_tracker",
        "note": f"{bias} score={score}",
        "signal_score": score,
        "market_bias": data.get("market_bias"),
    }]
