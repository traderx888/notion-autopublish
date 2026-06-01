from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from liquidity.fed_delta_source import (
    DEFAULT_THRESHOLDS_B,
    _latest_and_prior_week,
    build_fed_delta_snapshot,
)


def _obs(date_str: str, value: str) -> dict:
    return {"date": date_str, "value": value}


def test_latest_and_prior_week_picks_nearest_to_7_days_back():
    # Weekly cadence: 3 observations, each 7 days apart. Latest=Apr 9,
    # prior should be Apr 2 (exactly 7 days back).
    observations = [
        _obs("2026-04-09", "7100000"),  # 7.1T millions
        _obs("2026-04-02", "7140000"),  # 7.14T
        _obs("2026-03-26", "7180000"),  # 7.18T
    ]
    latest, prior = _latest_and_prior_week(observations, unit_scale=0.001)
    assert latest == (date(2026, 4, 9), 7100.0)
    assert prior == (date(2026, 4, 2), 7140.0)


def test_latest_and_prior_week_skips_missing_values():
    observations = [
        _obs("2026-04-09", "."),           # masked
        _obs("2026-04-08", ""),            # blank
        _obs("2026-04-07", "500"),         # valid
        _obs("2026-03-31", "450"),
    ]
    latest, prior = _latest_and_prior_week(observations, unit_scale=1.0)
    assert latest == (date(2026, 4, 7), 500.0)
    assert prior == (date(2026, 3, 31), 450.0)


def test_latest_and_prior_week_single_observation_returns_none_prior():
    observations = [_obs("2026-04-09", "100")]
    latest, prior = _latest_and_prior_week(observations, unit_scale=1.0)
    assert latest == (date(2026, 4, 9), 100.0)
    assert prior is None


def test_latest_and_prior_week_empty_returns_none():
    assert _latest_and_prior_week([], unit_scale=1.0) == (None, None)


def test_build_fed_delta_snapshot_missing_key_returns_unavailable():
    snapshot = build_fed_delta_snapshot(api_key="", now_iso="2026-04-09T00:00:00+00:00")
    assert snapshot["available"] is False
    assert snapshot["api_key_present"] is False
    assert "FRED_API_KEY not set" in snapshot["error"]
    assert snapshot["significant"] is False


def _stub_observations(series_values: dict[str, list[tuple[str, str]]]):
    """Return a fake _fetch_series_observations that yields canned data per series."""

    def _fake(series_id, *, api_key, lookback_days=45, timeout=30):
        rows = series_values.get(series_id, [])
        return [{"date": d, "value": v} for d, v in rows]

    return _fake


def test_build_fed_delta_snapshot_significant_tga_and_net_liq_breach():
    # WALCL flat, RRP flat, TGA up $150B week-over-week → breaches tga + net_liq.
    # Values given in FRED native units (millions for WALCL/TGA, billions for RRP).
    series = {
        # WALCL in millions USD: 7,100,000M = 7100B (no change)
        "WALCL": [("2026-04-09", "7100000"), ("2026-04-02", "7100000")],
        # RRPONTSYD in billions USD (no change)
        "RRPONTSYD": [("2026-04-08", "100"), ("2026-04-01", "100")],
        # WTREGEN in millions USD: 800,000M = 800B → 650,000M = 650B (prior)
        # Delta = +150B (breach on tga, breach on net_liq)
        "WTREGEN": [("2026-04-09", "800000"), ("2026-04-02", "650000")],
    }
    with patch("liquidity.fed_delta_source._fetch_series_observations", _stub_observations(series)):
        snap = build_fed_delta_snapshot(api_key="test", now_iso="2026-04-09T00:00:00+00:00")

    assert snap["available"] is True
    assert snap["significant"] is True
    assert any(b.startswith("tga:up:") for b in snap["breaches"])
    assert any(b.startswith("net_liq:") for b in snap["breaches"])
    # TGA up → net liquidity down
    assert snap["net_liquidity"]["delta_b"] == pytest.approx(-150.0)
    assert snap["series"]["WTREGEN"]["delta_b"] == pytest.approx(150.0)


def test_build_fed_delta_snapshot_all_within_threshold_is_not_significant():
    series = {
        "WALCL": [("2026-04-09", "7100000"), ("2026-04-02", "7110000")],   # -10B
        "RRPONTSYD": [("2026-04-08", "100"), ("2026-04-01", "120")],        # -20B
        "WTREGEN": [("2026-04-09", "700000"), ("2026-04-02", "720000")],    # -20B
    }
    with patch("liquidity.fed_delta_source._fetch_series_observations", _stub_observations(series)):
        snap = build_fed_delta_snapshot(api_key="test")

    assert snap["available"] is True
    assert snap["significant"] is False
    assert snap["breaches"] == []


def test_build_fed_delta_snapshot_incomplete_series_marks_error():
    # WALCL returns empty → snapshot cannot compute net liquidity.
    series = {
        "WALCL": [],
        "RRPONTSYD": [("2026-04-08", "100"), ("2026-04-01", "100")],
        "WTREGEN": [("2026-04-09", "700000"), ("2026-04-02", "700000")],
    }
    with patch("liquidity.fed_delta_source._fetch_series_observations", _stub_observations(series)):
        snap = build_fed_delta_snapshot(api_key="test")

    assert snap["available"] is False
    assert "incomplete data" in (snap["error"] or "")


def test_thresholds_match_agreed_defaults():
    # Guardrail: the agreed thresholds are walcl=40, rrp=75, tga=100, net_liq=100.
    # Any future tuning should change this test deliberately.
    assert DEFAULT_THRESHOLDS_B == {
        "walcl": 40.0,
        "rrp": 75.0,
        "tga": 100.0,
        "net_liq": 100.0,
    }
