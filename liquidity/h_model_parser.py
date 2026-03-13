from __future__ import annotations

import math
import re
from copy import deepcopy
from datetime import datetime, timezone

RELEVANCE_PATTERNS = {
    "liquidity": 3,
    "global liquidity": 3,
    "us liquidity": 3,
    "repo": 2,
    "reserves": 2,
    "sofr": 2,
    "treasury market": 2,
    "term premia": 2,
    "risk off": 2,
    "rotation": 1,
    "cash": 1,
}
POSITIVE_PATTERNS = ["improving", "expanding", "support", "supportive", "easing", "add more liquidity", "lift"]
FLAT_PATTERNS = ["peaking", "flat-lining", "flat lining", "topping out", "transition", "current levels", "not enough impetus"]
NEGATIVE_PATTERNS = ["risk off", "defensive", "cash", "draining", "contracting", "tougher", "peaking", "rotation"]


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


def _now(now_iso: str | None) -> datetime:
    parsed = _parse_iso(now_iso) if now_iso else None
    return parsed or datetime.now(timezone.utc)


def _score_matches(text: str, patterns: list[str]) -> int:
    lowered = text.lower()
    return sum(lowered.count(pattern) for pattern in patterns)


def _relevance_score(article: dict) -> int:
    text = f"{article.get('title', '')}\n{article.get('body_text', '')}".lower()
    return sum(weight for keyword, weight in RELEVANCE_PATTERNS.items() if keyword in text)


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def _extract_evidence(text: str) -> list[str]:
    evidence = []
    for sentence in _split_sentences(text):
        lowered = sentence.lower()
        if any(keyword in lowered for keyword in RELEVANCE_PATTERNS):
            evidence.append(sentence)
        if len(evidence) >= 5:
            break
    if evidence:
        return evidence[:5]
    if text.strip():
        return [text.strip()[:240]]
    return []


def classify_h_model_direction(text: str) -> dict:
    positive = _score_matches(text, POSITIVE_PATTERNS)
    flat = _score_matches(text, FLAT_PATTERNS)
    negative = _score_matches(text, NEGATIVE_PATTERNS)
    signal_score = max(-100, min(100, positive * 20 - negative * 25 - flat * 5))

    if positive == 0 and flat == 0 and negative == 0:
        direction = "UNKNOWN"
        bias = "UNKNOWN"
    elif negative > positive and negative >= flat:
        direction = "CONTRACTING"
        bias = "RISK_OFF"
    elif positive > negative and positive >= flat:
        direction = "EXPANDING"
        bias = "RISK_ON"
    else:
        direction = "FLAT"
        bias = "TRANSITION"

    return {
        "liquidity_direction": direction,
        "market_bias": bias,
        "signal_score": signal_score,
    }


def _freshness_from_hours(staleness_hours: float) -> str:
    if staleness_hours <= 72:
        return "fresh"
    if staleness_hours <= 120:
        return "aging"
    return "stale"


def _build_unavailable(payload: dict, now_value: datetime) -> dict:
    captured_at = payload.get("captured_at") or now_value.isoformat()
    return {
        "provider": "capital_wars_michael_howell",
        "article_url": "",
        "title": "",
        "published_at": captured_at,
        "captured_at": captured_at,
        "freshness": "stale",
        "staleness_hours": math.inf,
        "liquidity_direction": "UNKNOWN",
        "market_bias": "UNKNOWN",
        "signal_score": 0,
        "relevance_score": 0,
        "carry_forward": False,
        "evidence": [],
        "screenshot_path": payload.get("screenshot_path", ""),
        "available": False,
    }


def _apply_previous(previous: dict, captured_at: str, now_value: datetime) -> dict:
    carried = deepcopy(previous)
    published_at = _parse_iso(carried.get("published_at")) or now_value
    staleness_hours = max(0.0, (now_value - published_at).total_seconds() / 3600.0)
    carried["captured_at"] = captured_at
    carried["staleness_hours"] = staleness_hours
    carried["freshness"] = _freshness_from_hours(staleness_hours)
    carried["carry_forward"] = True
    carried["available"] = carried.get("available", True)
    return carried


def parse_h_model_article(article: dict, now_iso: str | None = None) -> dict:
    now_value = _now(now_iso)
    if not article:
        return _build_unavailable({}, now_value)

    previous = article.get("previous")
    articles = article.get("articles") or []
    candidates = []
    for item in articles:
        score = _relevance_score(item)
        if score >= 5:
            candidates.append((score, _parse_iso(item.get("date")) or datetime.min.replace(tzinfo=timezone.utc), item))

    if not candidates:
        if previous:
            return _apply_previous(previous, article.get("captured_at", now_value.isoformat()), now_value)
        return _build_unavailable(article, now_value)

    candidates.sort(key=lambda entry: entry[1], reverse=True)
    relevance_score, published_at, chosen = candidates[0]
    classification = classify_h_model_direction(chosen.get("body_text", ""))
    staleness_hours = max(0.0, (now_value - published_at).total_seconds() / 3600.0)

    return {
        "provider": "capital_wars_michael_howell",
        "article_url": chosen.get("url", ""),
        "title": chosen.get("title", ""),
        "published_at": published_at.isoformat(),
        "captured_at": article.get("captured_at", now_value.isoformat()),
        "freshness": _freshness_from_hours(staleness_hours),
        "staleness_hours": staleness_hours,
        "liquidity_direction": classification["liquidity_direction"],
        "market_bias": classification["market_bias"],
        "signal_score": classification["signal_score"],
        "relevance_score": relevance_score,
        "carry_forward": False,
        "evidence": _extract_evidence(chosen.get("body_text", ""))[:5],
        "screenshot_path": article.get("screenshot_path", ""),
        "available": True,
    }
