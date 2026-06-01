"""
Supabase signal persistence — fire-and-forget inserts into model_signals table.

Reads SUPABASE_URL + SUPABASE_KEY from environment or fundman-jarvis/.env fallback.
Never raises; all errors are logged to stderr so telegram sends are never blocked.

Usage:
    from tools.supabase_signals import store_signal, store_commodity_signals

    store_signal("h_model", asset=None, signal="EXPANDING", score=42, regime="RISK_ON")
    store_commodity_signals(success_rows, slot="0945")
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_DEFAULT_ROOT = Path(r"C:\Users\User\Documents\GitHub")
_ENV_FALLBACKS = [
    _DEFAULT_ROOT / "fundman-jarvis" / ".env",
    Path.cwd() / ".env",
]

_client = None  # lazy singleton


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists() or not path.is_file():
        return {}
    out: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        return {}
    return out


def _resolve_credentials() -> tuple[str, str]:
    """Return (url, key) from env vars or fallback .env files."""
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_KEY", "").strip()
    if url and key:
        return url, key

    for path in _ENV_FALLBACKS:
        vals = _read_env_file(path)
        if not url:
            url = vals.get("SUPABASE_URL", "").strip()
        if not key:
            key = vals.get("SUPABASE_KEY", "").strip()
        if url and key:
            return url, key

    raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY")


def _get_client():
    """Lazy-init Supabase client singleton."""
    global _client
    if _client is not None:
        return _client
    try:
        from supabase import create_client
    except ImportError:
        print("[supabase_signals] supabase package not installed. Run: pip install supabase", file=sys.stderr)
        return None
    url, key = _resolve_credentials()
    _client = create_client(url, key)
    return _client


def store_signal(
    model_name: str,
    asset: str | None,
    signal: str | None,
    score: float | None,
    regime: str | None,
    *,
    slot: str | None = None,
    metadata: dict[str, Any] | None = None,
    run_at: str | None = None,
) -> bool:
    """Insert one row into model_signals. Returns True on success, False on error."""
    try:
        client = _get_client()
        if client is None:
            return False

        row: dict[str, Any] = {
            "model_name": model_name,
            "run_at": run_at or datetime.now(timezone.utc).isoformat(),
            "asset": asset,
            "signal": signal,
            "regime": regime,
        }
        if score is not None:
            row["score"] = score
        if slot:
            row["slot"] = slot
        if metadata:
            row["metadata"] = metadata

        client.table("model_signals").insert(row).execute()
        return True
    except Exception as exc:
        print(f"[supabase_signals] store_signal failed: {exc}", file=sys.stderr)
        return False


def store_commodity_signals(
    payloads: list[tuple[str, dict]],
    slot: str = "default",
    run_at: str | None = None,
) -> int:
    """
    Batch-insert commodity model signals from (label, payload) tuples.

    Args:
        payloads: list of (label, payload) as produced by send_commodity_live_overlay_report.py
        slot: schedule slot token, e.g. '0945'
        run_at: ISO timestamp override (defaults to now UTC)

    Returns:
        Number of rows successfully inserted.
    """
    try:
        client = _get_client()
        if client is None:
            return 0

        ts = run_at or datetime.now(timezone.utc).isoformat()
        rows = []
        for label, payload in payloads:
            score_val = payload.get("combined_score", payload.get("strength", payload.get("gpsi")))
            rows.append({
                "model_name": "commodity",
                "run_at": ts,
                "slot": slot,
                "asset": label,
                "signal": str(payload.get("signal", "N/A") or "N/A"),
                "score": float(score_val) if isinstance(score_val, (int, float)) else None,
                "regime": str(payload.get("regime", "N/A") or "N/A"),
                "metadata": {
                    "alerts": [str(a) for a in (payload.get("alerts") or []) if str(a).strip()],
                    "recommended_actions": payload.get("recommended_actions", []),
                },
            })

        if rows:
            client.table("model_signals").insert(rows).execute()
        return len(rows)
    except Exception as exc:
        print(f"[supabase_signals] store_commodity_signals failed: {exc}", file=sys.stderr)
        return 0
