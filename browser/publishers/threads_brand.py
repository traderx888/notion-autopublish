"""Threads brand publisher -- wraps existing Threads API for brand automation.

Reuses publish_threads_single() and publish_threads_thread() from publish.py,
adding brand-specific features: comment replies, discovery integration, SEO.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")
THREADS_USER_ID = os.getenv("THREADS_USER_ID")

HKT = timezone(timedelta(hours=8))


def _threads_api(endpoint: str, params: dict | None = None,
                 payload: dict | None = None) -> dict:
    """Make a Threads Graph API call."""
    url = f"https://graph.threads.net/v1.0/{endpoint}"
    if params is None:
        params = {}
    params["access_token"] = THREADS_ACCESS_TOKEN

    resp = requests.post(url, params=params, json=payload or {})
    resp.raise_for_status()
    return resp.json()


def publish_single(text: str, dry_run: bool = False) -> str | None:
    """Publish a single Threads post. Returns media_id."""
    if dry_run:
        print(f"  [DRY-RUN] Threads post ({len(text)} chars):")
        print(f"  {text[:200]}...")
        return "dry-run-id"

    # Create container
    data = _threads_api(
        f"{THREADS_USER_ID}/threads",
        payload={"media_type": "TEXT", "text": text},
    )
    creation_id = data["id"]
    time.sleep(5)

    # Publish
    data = _threads_api(
        f"{THREADS_USER_ID}/threads_publish",
        payload={"creation_id": creation_id},
    )
    media_id = data["id"]
    print(f"  Threads post published (ID: {media_id})")
    return media_id


def publish_thread(posts: list[str], dry_run: bool = False) -> list[str]:
    """Publish a multi-post thread. Returns list of media_ids."""
    if dry_run:
        print(f"  [DRY-RUN] Threads thread ({len(posts)} posts):")
        for i, p in enumerate(posts, 1):
            print(f"  [{i}/{len(posts)}] {p[:100]}...")
        return ["dry-run-id"] * len(posts)

    ids = []
    reply_to_id = None

    for i, text in enumerate(posts):
        payload = {"media_type": "TEXT", "text": text}
        if reply_to_id:
            payload["reply_to_id"] = reply_to_id

        data = _threads_api(f"{THREADS_USER_ID}/threads", payload=payload)
        creation_id = data["id"]
        time.sleep(5)

        data = _threads_api(
            f"{THREADS_USER_ID}/threads_publish",
            payload={"creation_id": creation_id},
        )
        reply_to_id = data["id"]
        ids.append(reply_to_id)
        print(f"  Thread ({i + 1}/{len(posts)}) published")

        if i < len(posts) - 1:
            time.sleep(5)

    return ids


def post_reply(reply_to_id: str, text: str, dry_run: bool = False) -> str | None:
    """Post a reply/comment to an existing thread. Returns media_id."""
    if dry_run:
        print(f"  [DRY-RUN] Threads reply to {reply_to_id}:")
        print(f"  {text[:200]}...")
        return "dry-run-id"

    data = _threads_api(
        f"{THREADS_USER_ID}/threads",
        payload={
            "media_type": "TEXT",
            "text": text,
            "reply_to_id": reply_to_id,
        },
    )
    creation_id = data["id"]
    time.sleep(5)

    data = _threads_api(
        f"{THREADS_USER_ID}/threads_publish",
        payload={"creation_id": creation_id},
    )
    media_id = data["id"]
    print(f"  Threads reply published (ID: {media_id})")
    return media_id


def log_activity(action: str, platform: str = "threads", details: dict | None = None):
    """Log brand publishing activity."""
    log_dir = PROJECT_ROOT / "outputs" / "brand"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "brand_activity.log"

    entry = {
        "timestamp": datetime.now(HKT).isoformat(),
        "platform": platform,
        "action": action,
        **(details or {}),
    }

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
