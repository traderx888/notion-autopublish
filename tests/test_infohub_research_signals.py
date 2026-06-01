"""Unit tests for infohub_research.screening_sources and targets."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from infohub_research.screening_sources import (
    extract_dcb_targets,
    extract_liquidity_targets,
    extract_polymarket_targets,
)
from infohub_research.targets import (
    ScreeningTarget,
    collect_all_targets,
    filter_kinds,
)


# ── DCB ──────────────────────────────────────────────────────────


def _write(path: Path, payload) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_extract_dcb_targets_picks_strong_signals(tmp_path: Path):
    f = _write(tmp_path / "dcb.json", {
        "readings": [
            {"ticker": "DCB_POLICY_RATES", "signal": "STRONG_BEAR",
             "bull_score": 0, "bear_score": 10, "value": -2},
            {"ticker": "DCB_LIQUIDITY", "signal": "BEAR",
             "bull_score": 4, "bear_score": 7, "value": -1},
            {"ticker": "DCB_POSITIONING", "signal": "NEUTRAL",
             "bull_score": 5, "bear_score": 5, "value": 0},
            {"ticker": "DCB_PACKET_COUNT", "signal": "BEAR",
             "bull_score": 0, "bear_score": 0, "value": 0},
            {"ticker": "DCB_MACRO_GROWTH", "signal": "STRONG_BEAR",
             "bull_score": 20, "bear_score": 30, "value": -2},
        ]
    })

    out = extract_dcb_targets(f)
    slugs = sorted(t["slug"] for t in out)
    # PACKET_COUNT has no phrase mapping, NEUTRAL filtered, others kept.
    assert slugs == ["dcb_liquidity", "dcb_macro_growth", "dcb_policy_rates"]
    rates = next(t for t in out if t["slug"] == "dcb_policy_rates")
    assert rates["kind"] == "macro_keyword"
    assert "fed policy" in rates["keywords"]
    assert rates["note"] == "STRONG_BEAR"


def test_extract_dcb_targets_missing_file(tmp_path: Path):
    assert extract_dcb_targets(tmp_path / "nope.json") == []


def test_extract_dcb_targets_malformed(tmp_path: Path):
    p = tmp_path / "bad.json"
    p.write_text("not json", encoding="utf-8")
    assert extract_dcb_targets(p) == []


# ── Polymarket ───────────────────────────────────────────────────


def test_extract_polymarket_targets_dedupes_topics(tmp_path: Path):
    f = _write(tmp_path / "poly.json", {
        "tracked_traders": [
            {"handle": "a", "trader_tags":
             "Overall PnL > $1m; 67%+ Positions in US Election ; Politics PnL > $100k; French Whale"},
            {"handle": "b", "trader_tags":
             "Overall PnL > $1m; Sports PnL > $100k; Crypto PnL > $100k"},
            {"handle": "c", "trader_tags":
             "67%+ Positions in US Election ; Politics PnL > $100k"},
        ]
    })

    out = extract_polymarket_targets(f)
    slugs = {t["slug"] for t in out}
    # Topics: us_election, politics, france (French Whale), sports, crypto.
    assert "us_election" in slugs
    assert "politics" in slugs
    assert "france" in slugs
    assert "sports" in slugs
    assert "crypto" in slugs

    election = next(t for t in out if t["slug"] == "us_election")
    assert election["kind"] == "event_topic"
    assert election["mention_count"] >= 2  # two traders mention it


def test_extract_polymarket_targets_missing(tmp_path: Path):
    assert extract_polymarket_targets(tmp_path / "missing.json") == []


# ── Liquidity tracker ────────────────────────────────────────────


def test_extract_liquidity_targets_emits_when_score_strong(tmp_path: Path):
    f = _write(tmp_path / "h.json", {
        "available": True,
        "signal_score": -90,
        "market_bias": "RISK_OFF",
        "liquidity_direction": "CONTRACTING",
        "evidence": [
            "We might claim that this is consistent with the similar peak in the pace of US and Global Liquidity",
            "Broadly, over recent months we have emphasised two things",
            "shifting from, say, tech into energy, and ultimately towards more defensive positioning in consumer staples",
        ],
    })
    out = extract_liquidity_targets(f)
    assert len(out) == 1
    target = out[0]
    assert target["kind"] == "macro_keyword"
    assert target["slug"] == "liquidity_h_model"
    # Bias label always first.
    assert "contracting liquidity" in target["keywords"]
    # At least one capitalised noun phrase made it through.
    extra = [k for k in target["keywords"] if k not in ("contracting liquidity", "risk off")]
    assert extra, "expected at least one extracted keyphrase"


def test_extract_liquidity_targets_skips_weak_score(tmp_path: Path):
    f = _write(tmp_path / "h.json", {
        "available": True,
        "signal_score": -10,
        "market_bias": "NEUTRAL",
        "liquidity_direction": "FLAT",
        "evidence": [],
    })
    assert extract_liquidity_targets(f) == []


def test_extract_liquidity_targets_skips_unavailable(tmp_path: Path):
    f = _write(tmp_path / "h.json", {
        "available": False,
        "signal_score": -90,
    })
    assert extract_liquidity_targets(f) == []


# ── collect_all_targets integration ──────────────────────────────


def test_collect_all_targets_unifies_kinds(tmp_path: Path):
    scraped = tmp_path / "scraped"
    outputs = tmp_path / "outputs"
    fundman = tmp_path / "fundman"
    fundman.mkdir()

    # SMM signal (notebooklm.signals path).
    _write(fundman / "stockbee_momentum.json", {
        "episodic_pivots": {
            "top_eps": [
                {"ticker": "XENE", "grade": "SWAN", "is_golden": True,
                 "gap_pct": 45.2, "vol_multiple": 8, "price": 12.4, "date": "2026-04-08"},
            ]
        }
    })

    # DCB
    _write(scraped / "dailychartbook" / "dailychartbook_readings_latest.json", {
        "readings": [
            {"ticker": "DCB_POLICY_RATES", "signal": "STRONG_BEAR",
             "bull_score": 0, "bear_score": 10, "value": -2},
        ]
    })

    # Polymarket
    _write(scraped / "polymarketanalytics" / "trader_signals_latest.json", {
        "tracked_traders": [
            {"handle": "a", "trader_tags": "67%+ Positions in US Election ; Crypto PnL > $100k"},
        ]
    })

    # Liquidity
    _write(outputs / "liquidity" / "h_model_latest.json", {
        "available": True,
        "signal_score": -90,
        "market_bias": "RISK_OFF",
        "liquidity_direction": "CONTRACTING",
        "evidence": ["US and Global Liquidity peak momentum"],
    })

    out = collect_all_targets(
        scraped_dir=scraped,
        fundman_data_dir=fundman,
        outputs_dir=outputs,
        max_per_kind=10,
    )
    kinds = {t.kind for t in out}
    assert "ticker" in kinds
    assert "macro_keyword" in kinds
    assert "event_topic" in kinds

    xene = next(t for t in out if t.slug == "xene")
    assert xene.kind == "ticker"
    assert "XENE" in xene.keywords
    assert xene.raw["grade"] == "SWAN"


def test_filter_kinds_passthrough_when_none():
    targets = [ScreeningTarget(kind="ticker", slug="a", keywords=["A"], source="x")]
    assert filter_kinds(targets, None) == targets


def test_filter_kinds_restricts():
    targets = [
        ScreeningTarget(kind="ticker", slug="a", keywords=["A"], source="x"),
        ScreeningTarget(kind="macro_keyword", slug="b", keywords=["B"], source="y"),
    ]
    only = filter_kinds(targets, ["ticker"])
    assert len(only) == 1
    assert only[0].slug == "a"
