"""Mobile-friendly publisher: Patreon API post + YouTube Community caption.

Designed to be called from Claude Code remote triggers (mobile app).
Takes a Netlify URL + optional title, creates a Patreon post and
generates a YouTube Community post caption.

Usage:
    python tools/mobile_publish.py <url> [--title "..."] [--dry-run]
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Fix Windows encoding
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HKT = timezone(timedelta(hours=8))

# Load .env
ENV_PATH = REPO_ROOT / ".env"
if ENV_PATH.exists():
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def _patreon_api(method: str, path: str, body: dict | None = None) -> dict:
    """Call Patreon API v2."""
    token = os.environ.get("PATREON_ACCESS_TOKEN", "")
    if not token:
        raise RuntimeError("PATREON_ACCESS_TOKEN not set")

    url = f"https://www.patreon.com/api/oauth2/v2{path}"
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, method=method, data=data)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/vnd.api+json")

    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read()) if resp.read() else {}


def get_campaign_id() -> str:
    """Get the creator's campaign ID."""
    token = os.environ.get("PATREON_ACCESS_TOKEN", "")
    req = urllib.request.Request(
        "https://www.patreon.com/api/oauth2/v2/campaigns?fields[campaign]=creation_name",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    campaigns = data.get("data", [])
    if not campaigns:
        raise RuntimeError("No Patreon campaigns found")
    return campaigns[0]["id"]


def post_to_patreon(
    title: str,
    url: str,
    campaign_id: str,
    dry_run: bool = False,
) -> dict:
    """Create a Patreon post with link."""
    body_text = (
        f"最新研究報告已上線 👇\n\n"
        f"📊 {title}\n\n"
        f"🔗 完整版：{url}\n\n"
        f"如有任何問題歡迎留言討論！"
    )

    payload = {
        "data": {
            "type": "post",
            "attributes": {
                "title": title,
                "content": body_text,
                "is_paid": False,
                "post_type": "text_only",
            },
            "relationships": {
                "campaign": {
                    "data": {"type": "campaign", "id": campaign_id}
                }
            },
        }
    }

    if dry_run:
        print(f"[DRY-RUN] Patreon post:")
        print(f"  Title: {title}")
        print(f"  Body: {body_text}")
        return {"dry_run": True, "title": title}

    token = os.environ.get("PATREON_ACCESS_TOKEN", "")
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://www.patreon.com/api/oauth2/v2/posts",
        method="POST",
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/vnd.api+json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())

    post_id = result.get("data", {}).get("id", "unknown")
    print(f"[OK] Patreon post created: id={post_id}")
    return result


def generate_youtube_caption(title: str, url: str) -> str:
    """Generate a YouTube Community post caption."""
    return (
        f"📊 {title}\n\n"
        f"最新研究報告已上線！\n"
        f"完整版 👉 {url}\n\n"
        f"#投資研究 #市場分析 #彭博研究"
    )


def infer_title_from_url(url: str) -> str:
    """Try to infer a title from the Netlify URL slug."""
    # e.g. https://2026-05-17-bloomberg-55.netlify.app -> Bloomberg #55
    m = re.search(r"(\d{4}-\d{2}-\d{2})-(.+?)\.netlify", url)
    if m:
        slug = m.group(2).replace("-", " ").title()
        return f"彭博研究摘要 — {slug}"
    return "最新研究報告"


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Publish URL to Patreon + YouTube caption")
    parser.add_argument("url", help="Netlify URL to publish")
    parser.add_argument("--title", help="Post title (auto-inferred from URL if omitted)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    title = args.title or infer_title_from_url(args.url)
    date_str = datetime.now(HKT).strftime("%Y-%m-%d")

    # 1. Patreon
    print(f"Publishing: {title}")
    print(f"URL: {args.url}")
    print()

    try:
        campaign_id = get_campaign_id()
        patreon_result = post_to_patreon(title, args.url, campaign_id, dry_run=args.dry_run)
        patreon_ok = True
        patreon_id = patreon_result.get("data", {}).get("id", "dry_run" if args.dry_run else "unknown")
    except Exception as e:
        print(f"[ERR] Patreon: {e}", file=sys.stderr)
        patreon_ok = False
        patreon_id = None

    # 2. YouTube caption (always just generated text)
    yt_caption = generate_youtube_caption(title, args.url)
    print(f"\n[YouTube Community Post — copy & paste]")
    print("─" * 40)
    print(yt_caption)
    print("─" * 40)

    output = {
        "ok": patreon_ok,
        "url": args.url,
        "title": title,
        "date": date_str,
        "patreon": {"posted": patreon_ok, "post_id": patreon_id},
        "youtube_caption": yt_caption,
    }

    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))

    return 0 if patreon_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
