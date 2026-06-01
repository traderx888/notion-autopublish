"""
Fed Delta source — intra-week FRED poll for Fed Balance Sheet, RRP, TGA.

Purpose
-------
Michael Howell's H-Model publishes weekly on Capital Wars Substack. Between
publishes, if Fed BS / RRP / TGA move significantly, the H-Model regime can
become stale-but-fresh (the article is recent, but the underlying liquidity
picture has shifted). This module polls FRED daily, computes week-over-week
deltas, and flags "significant" moves so build_composite_liquidity_snapshot
can mark the composite confidence as LOW with override_reason="FED_DELTA".

Design notes
------------
- Flag-only override (option ii): we do NOT overwrite Howell's regime. We just
  raise a flag and drop confidence, so downstream consumers know to re-check
  the H-Model manually or wait for Howell's next weekly publish.
- "Last data point date" awareness: FRED releases on Thursdays (H.4.1) and
  Mondays (TGA). Running this daily is cheap but redundant when data hasn't
  changed. We track each series' latest observation date in the output
  artifact so downstream code can see when FRED actually moved.
- All FRED values normalized to USD billions for consistency with Howell's
  own units and downstream readings.json tickers (FED_RRP, FED_TGA, etc.).
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests

# FRED series IDs and their reporting units.
# WALCL:     Fed Total Assets, weekly (Wed release), reported in millions USD
# RRPONTSYD: Overnight RRP, daily, reported in billions USD
# WTREGEN:   Treasury General Account, weekly (Wed release), reported in millions USD
FRED_SERIES = {
    "WALCL": {"description": "Fed Total Assets (Balance Sheet)", "unit_scale": 0.001},  # millions → billions
    "RRPONTSYD": {"description": "Overnight Reverse Repo (RRP)", "unit_scale": 1.0},    # already billions
    "WTREGEN": {"description": "Treasury General Account (TGA)", "unit_scale": 0.001},  # millions → billions
}

# Default WoW delta thresholds in USD billions. Breach any one of these and the
# snapshot is marked `significant`. These match the values agreed with the user.
DEFAULT_THRESHOLDS_B = {
    "walcl": 40.0,    # Fed Balance Sheet WoW ≥ ±$40B
    "rrp": 75.0,      # RRP WoW ≥ ±$75B
    "tga": 100.0,     # TGA WoW ≥ ±$100B
    "net_liq": 100.0, # Net liquidity (WALCL - RRP - TGA) WoW ≥ ±$100B
}

FRED_API_URL = "https://api.stlouisfed.org/fred/series/observations"


def _now_iso(now_iso: str | None = None) -> str:
    return now_iso or datetime.now(timezone.utc).isoformat()


def _fetch_series_observations(
    series_id: str,
    *,
    api_key: str,
    lookback_days: int = 45,
    timeout: int = 30,
) -> list[dict[str, Any]]:
    """Return FRED observations list for the given series, newest first.

    Each observation is a dict with 'date' and 'value' (string). Caller converts.
    Empty list on any failure — never raises, so the composite build never blocks.
    """
    if not api_key:
        return []
    start = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": start,
        "sort_order": "desc",
        "limit": 100,
    }
    try:
        response = requests.get(FRED_API_URL, params=params, timeout=timeout)
        if response.status_code != 200:
            return []
        return response.json().get("observations", []) or []
    except Exception:
        return []


def _latest_and_prior_week(
    observations: list[dict[str, Any]],
    *,
    unit_scale: float,
) -> tuple[tuple[date, float] | None, tuple[date, float] | None]:
    """Return (latest, prior) as (date, value_in_billions) tuples or (None, None).

    `prior` is the observation closest to 7 calendar days before `latest.date`
    (approximation: prior week's same release). If fewer than 2 valid
    observations exist, returns (latest, None) or (None, None).
    """
    # Parse and filter valid numeric observations
    parsed: list[tuple[date, float]] = []
    for obs in observations:
        raw = obs.get("value")
        if raw in (None, "", "."):
            continue
        try:
            value_b = float(raw) * unit_scale
        except (TypeError, ValueError):
            continue
        try:
            obs_date = date.fromisoformat(obs.get("date", ""))
        except ValueError:
            continue
        parsed.append((obs_date, value_b))

    if not parsed:
        return None, None

    # Newest first (FRED returns desc, but re-sort to be safe)
    parsed.sort(key=lambda x: x[0], reverse=True)
    latest = parsed[0]

    # Find observation closest to latest.date - 7 days. For weekly series this
    # is the prior week's release; for daily series (RRPONTSYD) it's the prior
    # trading day closest to that mark.
    target = latest[0] - timedelta(days=7)
    prior_candidates = [p for p in parsed[1:] if p[0] <= latest[0]]
    if not prior_candidates:
        return latest, None
    prior = min(prior_candidates, key=lambda p: abs((p[0] - target).days))
    return latest, prior


def build_fed_delta_snapshot(
    *,
    api_key: str | None = None,
    thresholds: dict[str, float] | None = None,
    now_iso: str | None = None,
) -> dict[str, Any]:
    """Poll FRED, compute WoW deltas, and evaluate threshold breaches.

    Returns a snapshot dict suitable for persisting to
    outputs/liquidity/fed_delta_latest.json and passing to
    build_composite_liquidity_snapshot as the `fed_delta` argument.
    """
    thresholds = thresholds or DEFAULT_THRESHOLDS_B
    api_key = api_key or os.environ.get("FRED_API_KEY", "").strip()
    generated_at = _now_iso(now_iso)

    snapshot: dict[str, Any] = {
        "available": False,
        "generated_at": generated_at,
        "api_key_present": bool(api_key),
        "series": {},
        "net_liquidity": None,
        "significant": False,
        "breaches": [],
        "thresholds_b": dict(thresholds),
        "error": None,
    }

    if not api_key:
        snapshot["error"] = "FRED_API_KEY not set — Fed delta override unavailable"
        return snapshot

    # Fetch each series and compute (latest_b, prior_b, delta_b).
    series_data: dict[str, dict[str, Any]] = {}
    for series_id, meta in FRED_SERIES.items():
        observations = _fetch_series_observations(series_id, api_key=api_key)
        latest, prior = _latest_and_prior_week(observations, unit_scale=meta["unit_scale"])
        entry: dict[str, Any] = {
            "description": meta["description"],
            "latest_date": latest[0].isoformat() if latest else None,
            "latest_b": round(latest[1], 2) if latest else None,
            "prior_date": prior[0].isoformat() if prior else None,
            "prior_b": round(prior[1], 2) if prior else None,
            "delta_b": round(latest[1] - prior[1], 2) if (latest and prior) else None,
        }
        series_data[series_id] = entry

    snapshot["series"] = series_data

    walcl = series_data.get("WALCL", {})
    rrp = series_data.get("RRPONTSYD", {})
    tga = series_data.get("WTREGEN", {})

    # Need at least the three latests to be usable.
    if walcl.get("latest_b") is None or rrp.get("latest_b") is None or tga.get("latest_b") is None:
        snapshot["error"] = "FRED returned incomplete data for one or more series"
        return snapshot

    net_liq_latest = walcl["latest_b"] - rrp["latest_b"] - tga["latest_b"]
    net_liq_prior: float | None = None
    if all(series_data[s].get("prior_b") is not None for s in ("WALCL", "RRPONTSYD", "WTREGEN")):
        net_liq_prior = walcl["prior_b"] - rrp["prior_b"] - tga["prior_b"]

    net_liq_delta = round(net_liq_latest - net_liq_prior, 2) if net_liq_prior is not None else None
    snapshot["net_liquidity"] = {
        "latest_b": round(net_liq_latest, 2),
        "prior_b": round(net_liq_prior, 2) if net_liq_prior is not None else None,
        "delta_b": net_liq_delta,
        "formula": "WALCL - RRPONTSYD - WTREGEN (all in USD billions)",
    }

    # Threshold evaluation — breach any → significant.
    breaches: list[str] = []

    def _check(key: str, delta_b: float | None, threshold_key: str) -> None:
        if delta_b is None:
            return
        limit = thresholds.get(threshold_key)
        if limit is None:
            return
        if abs(delta_b) >= limit:
            direction = "up" if delta_b > 0 else "down"
            breaches.append(f"{key}:{direction}:{delta_b:+.1f}B_vs_{limit:.0f}B")

    _check("walcl", walcl.get("delta_b"), "walcl")
    _check("rrp", rrp.get("delta_b"), "rrp")
    _check("tga", tga.get("delta_b"), "tga")
    _check("net_liq", net_liq_delta, "net_liq")

    snapshot["breaches"] = breaches
    snapshot["significant"] = bool(breaches)
    snapshot["available"] = True
    return snapshot
