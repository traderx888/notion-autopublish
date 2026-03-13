from __future__ import annotations

from liquidity.composite import build_composite_liquidity_snapshot


def test_composite_uses_h_model_when_fresh_and_checker_agrees():
    h_model = {
        "available": True,
        "freshness": "fresh",
        "liquidity_direction": "EXPANDING",
        "market_bias": "RISK_ON",
    }
    checker = {
        "available": True,
        "liquidity_direction": "EXPANDING",
    }

    result = build_composite_liquidity_snapshot(h_model, checker, prior_history=[])

    assert result["composite"]["regime"] == "EXPANDING"
    assert result["composite"]["override_active"] is False
    assert result["composite"]["confidence"] == "HIGH"


def test_composite_overrides_when_h_model_stale():
    h_model = {
        "available": True,
        "freshness": "stale",
        "liquidity_direction": "FLAT",
        "market_bias": "TRANSITION",
    }
    checker = {
        "available": True,
        "liquidity_direction": "CONTRACTING",
    }

    result = build_composite_liquidity_snapshot(h_model, checker, prior_history=[])

    assert result["composite"]["override_active"] is True
    assert result["composite"]["override_reason"] == "H_STALE"
    assert result["composite"]["regime"] == "CONTRACTING"


def test_composite_overrides_after_two_run_divergence():
    h_model = {
        "available": True,
        "freshness": "fresh",
        "liquidity_direction": "EXPANDING",
        "market_bias": "RISK_ON",
    }
    checker = {
        "available": True,
        "liquidity_direction": "CONTRACTING",
    }
    prior_history = [
        {"checker_direction": "CONTRACTING", "h_direction": "EXPANDING"},
        {"checker_direction": "CONTRACTING", "h_direction": "EXPANDING"},
    ]

    result = build_composite_liquidity_snapshot(h_model, checker, prior_history=prior_history)

    assert result["composite"]["override_active"] is True
    assert result["composite"]["override_reason"] == "CHECKER_2RUN_DIVERGENCE"
    assert result["composite"]["confidence"] == "MEDIUM"
