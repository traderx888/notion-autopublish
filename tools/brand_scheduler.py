"""Brand scheduler -- rate limiting, daily quotas, and scheduling state.

Tracks what was posted when, enforces per-platform daily limits,
and provides optimal posting time windows.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = PROJECT_ROOT / "outputs" / "brand"
STATE_FILE = STATE_DIR / "schedule_state.json"

HKT = timezone(timedelta(hours=8))


def _load_state() -> dict:
    """Load scheduling state."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if STATE_FILE.exists():
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"daily_counts": {}, "last_reset": ""}


def _save_state(state: dict):
    """Save scheduling state."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _today() -> str:
    return datetime.now(HKT).strftime("%Y-%m-%d")


def _reset_if_new_day(state: dict) -> dict:
    """Reset daily counters if it's a new day."""
    today = _today()
    if state.get("last_reset") != today:
        state["daily_counts"] = {}
        state["last_reset"] = today
    return state


def can_post(platform: str, action: str, config: dict) -> bool:
    """Check if we can post (haven't exceeded daily limit)."""
    state = _load_state()
    state = _reset_if_new_day(state)

    plat_config = config["platforms"].get(platform, {})
    key = f"{platform}_{action}"
    current = state["daily_counts"].get(key, 0)

    if action in ("original_post", "thread", "self_reply"):
        limit = plat_config.get("daily_post_limit", 2)
    elif action == "comment":
        limit = plat_config.get("daily_comment_limit", 5)
    else:
        limit = 10

    return current < limit


def record_post(platform: str, action: str):
    """Record that a post was made (increment daily counter)."""
    state = _load_state()
    state = _reset_if_new_day(state)

    key = f"{platform}_{action}"
    state["daily_counts"][key] = state["daily_counts"].get(key, 0) + 1
    _save_state(state)


def get_daily_summary(config: dict) -> dict:
    """Get current daily posting summary across all platforms."""
    state = _load_state()
    state = _reset_if_new_day(state)

    summary = {"date": _today(), "platforms": {}}

    for platform, plat_config in config["platforms"].items():
        if not plat_config.get("enabled"):
            continue

        post_key = f"{platform}_original_post"
        comment_key = f"{platform}_comment"
        post_limit = plat_config.get("daily_post_limit", 2)
        comment_limit = plat_config.get("daily_comment_limit", 5)

        summary["platforms"][platform] = {
            "posts": {
                "used": state["daily_counts"].get(post_key, 0),
                "limit": post_limit,
            },
            "comments": {
                "used": state["daily_counts"].get(comment_key, 0),
                "limit": comment_limit,
            },
        }

    return summary


def print_status(config: dict):
    """Print current scheduling status."""
    summary = get_daily_summary(config)
    print(f"\nBrand Schedule Status — {summary['date']}")
    print(f"{'Platform':<15} {'Posts':<15} {'Comments':<15}")
    print("-" * 45)
    for platform, data in summary["platforms"].items():
        p = data["posts"]
        c = data["comments"]
        print(f"{platform:<15} {p['used']}/{p['limit']:<10} {c['used']}/{c['limit']:<10}")


# ─── Optimal posting schedule (HKT) ─────────────────────────

DAILY_SCHEDULE = {
    "09:00": {"platforms": ["linkedin"], "mode": "original", "note": "Asia morning"},
    "12:00": {"platforms": ["threads"], "mode": "original", "note": "Lunch break"},
    "14:00": {"platforms": ["youtube"], "mode": "comment", "note": "Afternoon engagement"},
    "18:00": {"platforms": ["linkedin"], "mode": "original", "note": "HK evening / US morning"},
    "20:00": {"platforms": ["threads"], "mode": "thread", "note": "Evening deep content"},
    "21:00": {"platforms": ["xiaohongshu"], "mode": "original", "note": "XHS prime time"},
}


def get_next_scheduled_action() -> dict | None:
    """Get the next scheduled action based on current HKT time."""
    now = datetime.now(HKT)
    current_time = now.strftime("%H:%M")

    for sched_time, action in sorted(DAILY_SCHEDULE.items()):
        if sched_time > current_time:
            return {"time": sched_time, **action}

    return None  # All done for today
