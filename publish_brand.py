"""
Brand Automation Entry Point -- Dennis Tong personal brand builder.

Generates and publishes branded content across social media platforms
using Claude for content generation and platform-specific publishers.

Usage:
    python publish_brand.py                        # Full cycle (all platforms)
    python publish_brand.py --platform threads     # Single platform
    python publish_brand.py --mode original        # Original posts only
    python publish_brand.py --mode comment         # Comments only
    python publish_brand.py --mode self-reply      # Self-reply on own posts
    python publish_brand.py --dry-run              # Preview, no publish
    python publish_brand.py --topic AI_in_finance  # Specific topic
    python publish_brand.py --discover             # Discovery only (no posting)
    python publish_brand.py --list-topics          # Show available topics
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from brand.engine import (
    load_config,
    generate_original_post,
    generate_thread,
    generate_comment,
    generate_self_reply,
    adapt_for_platform,
)
from brand.seo import add_cross_links, score_seo_quality
from browser.publishers.threads_brand import (
    publish_single as threads_publish_single,
    publish_thread as threads_publish_thread,
    post_reply as threads_post_reply,
    log_activity,
)

HKT = timezone(timedelta(hours=8))


def pick_topic(config: dict, requested_topic: str | None = None) -> str:
    """Pick a topic to write about. Uses requested or random from primary+secondary."""
    all_topics = config["topics"]["primary"] + config["topics"]["secondary"]
    if requested_topic:
        if requested_topic in all_topics:
            return requested_topic
        print(f"  Warning: '{requested_topic}' not in config topics, using anyway")
        return requested_topic
    return random.choice(all_topics)


# ─── Original Post ───────────────────────────────────────────

def run_original_post(platform: str, topic: str, config: dict,
                      dry_run: bool = False) -> bool:
    """Generate and publish an original post."""
    print(f"\n--- Original Post: {platform} / {topic} ---")

    plat_config = config["platforms"].get(platform, {})
    if not plat_config.get("enabled"):
        print(f"  Platform '{platform}' is disabled in config, skipping")
        return False

    if "original_post" not in plat_config.get("content_types", []):
        print(f"  Platform '{platform}' doesn't support original posts, skipping")
        return False

    print(f"  Generating content with Claude...")
    content = generate_original_post(topic, platform, config=config)
    if not content:
        print(f"  Content generation failed")
        return False

    text = adapt_for_platform(content, platform, config)

    if platform in ("linkedin", "threads"):
        text = add_cross_links(text, platform, config)

    seo_score = content.get("seo_score", 0)
    print(f"  SEO score: {seo_score:.2f}")

    if platform == "threads":
        threads_publish_single(text, dry_run=dry_run)
    elif platform == "linkedin":
        from browser.publishers.linkedin_brand import publish_post as li_publish
        li_publish(text, dry_run=dry_run)
    else:
        if dry_run:
            print(f"  [DRY-RUN] {platform} post ({len(text)} chars):")
            print(f"  {text[:300]}...")
        else:
            print(f"  Publisher for '{platform}' not yet implemented for original posts")
            return False

    log_activity("original_post", platform, {
        "topic": topic,
        "chars": len(text),
        "seo_score": seo_score,
        "dry_run": dry_run,
    })
    return True


# ─── Thread ──────────────────────────────────────────────────

def run_thread(platform: str, topic: str, config: dict,
               dry_run: bool = False) -> bool:
    """Generate and publish a thread."""
    print(f"\n--- Thread: {platform} / {topic} ---")

    plat_config = config["platforms"].get(platform, {})
    if "thread" not in plat_config.get("content_types", []):
        print(f"  Platform '{platform}' doesn't support threads, skipping")
        return False

    print(f"  Generating thread with Claude...")
    content = generate_thread(topic, platform, config=config)
    if not content or not content.get("posts"):
        print(f"  Thread generation failed")
        return False

    posts = content["posts"]
    formatted = [adapt_for_platform(post, platform, config) for post in posts]

    if platform == "threads":
        threads_publish_thread(formatted, dry_run=dry_run)
    else:
        print(f"  Thread publisher for '{platform}' not yet implemented")
        return False

    log_activity("thread", platform, {
        "topic": topic,
        "post_count": len(formatted),
        "dry_run": dry_run,
    })
    return True


# ─── Comment (discover + comment on others' content) ─────────

def run_comment(platform: str, config: dict, dry_run: bool = False,
                limit: int = 3) -> bool:
    """Discover relevant content and post comments."""
    print(f"\n--- Comment Discovery + Post: {platform} ---")

    plat_config = config["platforms"].get(platform, {})
    if "comment" not in plat_config.get("content_types", []):
        print(f"  Platform '{platform}' doesn't support comments, skipping")
        return False

    if platform == "youtube":
        return _run_youtube_comments(config, dry_run, limit)
    elif platform == "linkedin":
        print(f"  LinkedIn comment flow requires browser session.")
        print(f"  Use: python publish_brand.py --platform linkedin --mode comment")
        if dry_run:
            return _run_linkedin_comments_dry(config, limit)
        return False
    elif platform == "threads":
        print(f"  Threads comment discovery not yet implemented (needs Apify search)")
        return False
    else:
        print(f"  Comment discovery for '{platform}' not yet implemented")
        return False


def _run_youtube_comments(config: dict, dry_run: bool, limit: int) -> bool:
    """Discover YouTube videos and post comments."""
    from browser.discovery.youtube_discover import discover

    print(f"  Discovering relevant videos...")
    targets = discover(config, limit=limit)

    if not targets:
        print(f"  No relevant videos found")
        return False

    print(f"  Found {len(targets)} relevant videos")

    yt_config = config["platforms"]["youtube"]
    min_delay = yt_config.get("min_delay_seconds", 120)
    max_delay = yt_config.get("max_delay_seconds", 600)

    if dry_run:
        for t in targets:
            print(f"\n  Video: {t.title}")
            print(f"  Author: {t.author} | Score: {t.relevance_score}")
            print(f"  URL: {t.url}")

            comment = generate_comment(t.title, t.author, t.content_snippet,
                                       "youtube", config=config)
            if comment:
                print(f"  [DRY-RUN] Comment: {comment.get('text', '')[:200]}...")

        log_activity("comment_discovery", "youtube", {
            "found": len(targets),
            "dry_run": True,
        })
        return True

    # Live mode: use browser automation
    from browser.publishers.youtube_brand import YouTubeBrandPublisher

    posted = 0
    with YouTubeBrandPublisher() as yt:
        yt.ensure_logged_in()
        for i, t in enumerate(targets):
            print(f"\n  [{i+1}/{len(targets)}] {t.title[:60]}...")

            comment = generate_comment(t.title, t.author, t.content_snippet,
                                       "youtube", config=config)
            if not comment or not comment.get("text"):
                print(f"  Skipping (generation failed)")
                continue

            ok = yt.post_comment(t.url, comment["text"])
            if ok:
                posted += 1
                log_activity("comment", "youtube", {
                    "video_url": t.url,
                    "video_title": t.title[:80],
                    "chars": len(comment["text"]),
                })

            # Delay between comments
            if i < len(targets) - 1:
                delay = random.randint(min_delay, max_delay)
                print(f"  Waiting {delay}s before next comment...")
                time.sleep(delay)

    print(f"  Posted {posted}/{len(targets)} YouTube comments")
    return posted > 0


def _run_linkedin_comments_dry(config: dict, limit: int) -> bool:
    """Dry-run LinkedIn comment flow (no browser needed)."""
    print(f"  [DRY-RUN] Would discover {limit} LinkedIn posts and generate comments")
    print(f"  (LinkedIn discovery requires browser session for live mode)")
    return True


# ─── Self-Reply ──────────────────────────────────────────────

def run_self_reply(platform: str, topic: str, config: dict,
                   dry_run: bool = False) -> bool:
    """Generate and post a self-reply to your own most recent post."""
    print(f"\n--- Self-Reply: {platform} / {topic} ---")

    # First generate what the original post would be (or use a provided one)
    print(f"  Generating original post for self-reply context...")
    original = generate_original_post(topic, platform, config=config)
    if not original:
        print(f"  Could not generate original post context")
        return False

    original_text = adapt_for_platform(original, platform, config)

    print(f"  Generating self-reply...")
    reply = generate_self_reply(original_text, platform, config=config)
    if not reply or not reply.get("text"):
        print(f"  Self-reply generation failed")
        return False

    reply_text = reply["text"]
    print(f"  Angle: {reply.get('angle', 'N/A')}")

    if dry_run:
        print(f"  [DRY-RUN] Original post ({len(original_text)} chars):")
        print(f"  {original_text[:200]}...")
        print(f"  [DRY-RUN] Self-reply ({len(reply_text)} chars):")
        print(f"  {reply_text[:200]}...")
    else:
        if platform == "threads":
            media_id = threads_publish_single(original_text)
            if media_id:
                time.sleep(10)
                threads_post_reply(media_id, reply_text)
        else:
            print(f"  Self-reply for '{platform}' requires browser automation (live mode)")

    log_activity("self_reply", platform, {
        "topic": topic,
        "original_chars": len(original_text),
        "reply_chars": len(reply_text),
        "angle": reply.get("angle", ""),
        "dry_run": dry_run,
    })
    return True


# ─── Discovery Only ──────────────────────────────────────────

def run_discover(platform: str, config: dict, limit: int = 10) -> bool:
    """Run discovery only (no posting) and print results."""
    print(f"\n--- Discovery: {platform} ---")

    if platform == "youtube":
        from browser.discovery.youtube_discover import discover
        targets = discover(config, limit=limit)
        if not targets:
            print(f"  No results found")
            return False

        for i, t in enumerate(targets, 1):
            print(f"\n  [{i}] {t.title[:70]}")
            print(f"      Author: {t.author}")
            print(f"      Score: {t.relevance_score} | Views: {t.engagement.get('views', '?')}")
            print(f"      URL: {t.url}")
        return True

    elif platform == "linkedin":
        print(f"  LinkedIn discovery requires browser session.")
        print(f"  Run with browser: LinkedInDiscovery context manager")
        return False

    else:
        print(f"  Discovery for '{platform}' not yet implemented")
        return False


# ─── Main ────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Brand automation for Dennis Tong",
    )
    parser.add_argument(
        "--platform",
        choices=["threads", "linkedin", "youtube", "xiaohongshu", "all"],
        default="all",
        help="Target platform (default: all enabled)",
    )
    parser.add_argument(
        "--mode",
        choices=["original", "thread", "comment", "self-reply", "all"],
        default="all",
        help="Content mode (default: all)",
    )
    parser.add_argument(
        "--topic",
        help="Specific topic to write about",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview content without publishing",
    )
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Run discovery only (no posting)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="Max items to discover/comment on (default: 3)",
    )
    parser.add_argument(
        "--supporter-comments",
        action="store_true",
        help="Generate daily supporter comment suggestions for friends/relatives",
    )
    parser.add_argument(
        "--supporter-count",
        type=int,
        default=10,
        help="Comments per platform for supporter batch (default: 10)",
    )
    parser.add_argument(
        "--supporter-save",
        action="store_true",
        help="Save supporter comments to JSON file (outputs/brand/)",
    )
    parser.add_argument(
        "--list-topics",
        action="store_true",
        help="List available topics and exit",
    )
    args = parser.parse_args()

    config = load_config()

    if args.list_topics:
        print("Primary topics:")
        for t in config["topics"]["primary"]:
            print(f"  - {t}")
        print("\nSecondary topics:")
        for t in config["topics"]["secondary"]:
            print(f"  - {t}")
        return

    # Supporter comment generation mode
    if args.supporter_comments:
        from brand.supporter_comments import print_daily_comments, save_daily_batch
        platforms = None  # all social platforms
        if args.platform != "all":
            platforms = [args.platform]
        print_daily_comments(config, platforms=platforms,
                             per_platform=args.supporter_count)
        if args.supporter_save:
            from brand.supporter_comments import save_daily_batch as save_batch
            path = save_batch(config, platforms=platforms,
                              per_platform=args.supporter_count)
            print(f"  Saved to: {path}")
        return

    print(f"Brand automation: Dennis Tong")
    print(f"Time: {datetime.now(HKT).strftime('%Y-%m-%d %H:%M HKT')}")
    print(f"Platform: {args.platform}")
    print(f"Mode: {args.mode}")
    print(f"Dry run: {args.dry_run}")

    # Determine platforms
    if args.platform == "all":
        platforms = [p for p, cfg in config["platforms"].items() if cfg.get("enabled")]
    else:
        platforms = [args.platform]

    # Discovery-only mode
    if args.discover:
        for platform in platforms:
            run_discover(platform, config, limit=args.limit)
        return

    topic = pick_topic(config, args.topic)
    print(f"Topic: {topic}")

    results = []
    for platform in platforms:
        if args.mode in ("original", "all"):
            ok = run_original_post(platform, topic, config, dry_run=args.dry_run)
            results.append(("original", platform, ok))

        if args.mode in ("thread", "all"):
            ok = run_thread(platform, topic, config, dry_run=args.dry_run)
            results.append(("thread", platform, ok))

        if args.mode in ("comment", "all"):
            ok = run_comment(platform, config, dry_run=args.dry_run, limit=args.limit)
            results.append(("comment", platform, ok))

        if args.mode in ("self-reply", "all"):
            ok = run_self_reply(platform, topic, config, dry_run=args.dry_run)
            results.append(("self-reply", platform, ok))

    # Summary
    print(f"\n--- Summary ---")
    for mode, platform, ok in results:
        status = "OK" if ok else "SKIP"
        print(f"  [{status}] {platform} / {mode}")


if __name__ == "__main__":
    main()
