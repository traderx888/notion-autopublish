from __future__ import annotations

from datetime import datetime, timezone


def _now_iso(now_iso: str | None = None) -> str:
    return now_iso or datetime.now(timezone.utc).isoformat()


def _direction_to_regime(direction: str) -> str:
    if direction == "EXPANDING":
        return "EXPANDING"
    if direction == "CONTRACTING":
        return "CONTRACTING"
    return "NEUTRAL"


def _direction_to_bias(direction: str) -> str:
    if direction == "EXPANDING":
        return "RISK_ON"
    if direction == "CONTRACTING":
        return "RISK_OFF"
    return "TRANSITION"


def _has_two_run_divergence(prior_history: list[dict], h_direction: str, checker_direction: str) -> bool:
    if checker_direction in {"FLAT", "UNKNOWN", ""}:
        return False
    recent = prior_history[-2:]
    if len(recent) < 2:
        return False
    return all(
        row.get("checker_direction") == checker_direction and row.get("h_direction") == h_direction
        for row in recent
    )


def build_composite_liquidity_snapshot(
    h_model: dict,
    checker: dict,
    prior_history: list[dict] | None = None,
    now_iso: str | None = None,
) -> dict:
    prior_history = prior_history or []
    h_available = bool(h_model.get("available"))
    checker_available = bool(checker.get("available"))
    h_direction = h_model.get("liquidity_direction", "UNKNOWN")
    checker_direction = checker.get("liquidity_direction", "UNKNOWN")
    divergence_flag = h_available and checker_available and h_direction not in {"UNKNOWN", ""} and checker_direction not in {"UNKNOWN", ""} and h_direction != checker_direction

    regime = _direction_to_regime(h_direction if h_available else checker_direction)
    override_active = False
    override_reason = "NONE"
    baseline_source = "H_MODEL" if h_available else "CHECKER"

    if h_available and checker_available and h_model.get("freshness") == "stale" and checker_direction != "UNKNOWN":
        override_active = True
        override_reason = "H_STALE"
        regime = _direction_to_regime(checker_direction)
    elif divergence_flag and _has_two_run_divergence(prior_history, h_direction, checker_direction):
        override_active = True
        override_reason = "CHECKER_2RUN_DIVERGENCE"
        regime = _direction_to_regime(checker_direction)

    if not h_available or h_direction == "UNKNOWN" or h_model.get("freshness") == "stale":
        confidence = "LOW"
    elif h_model.get("freshness") == "aging" or divergence_flag:
        confidence = "MEDIUM"
    else:
        confidence = "HIGH"

    return {
        "generated_at": _now_iso(now_iso),
        "h_model": h_model,
        "internal_checker": checker,
        "composite": {
            "regime": regime,
            "trading_bias": _direction_to_bias(regime if regime != "NEUTRAL" else "FLAT"),
            "baseline_source": baseline_source,
            "override_active": override_active,
            "override_reason": override_reason,
            "divergence_flag": divergence_flag,
            "confidence": confidence,
        },
        "status": {
            "h_model_capture": "ok" if h_available else "missing",
            "internal_checker": "ok" if checker_available else "missing",
        },
    }

