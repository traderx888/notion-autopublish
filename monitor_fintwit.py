"""
FinTwit Signal Monitor
Polls X/Twitter accounts for high-conviction trade signals and alerts via Telegram.

Usage:
    python monitor_fintwit.py                # Single run (for cron/scheduler)
    python monitor_fintwit.py --dry-run      # Score + print, no Telegram
    python monitor_fintwit.py --backfill     # Process without dedup (test scoring)
    python monitor_fintwit.py --loop         # Continuous polling (alternative to cron)
"""

import argparse
import io
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Windows encoding fix
if sys.platform == "win32":
    if sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if sys.stderr.encoding.lower() != "utf-8":
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Load environment
load_dotenv()
JARVIS_ENV = Path(r"c:\Users\User\Documents\GitHub\fundman-jarvis\.env")
if JARVIS_ENV.exists():
    load_dotenv(JARVIS_ENV)

ROOT = Path(__file__).parent
CONFIG_PATH = ROOT / "config" / "fintwit_monitor.json"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _setup_logging(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("fintwit")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(fh)
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        logger.addHandler(sh)
    return logger

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)

# ---------------------------------------------------------------------------
# State management (seen tweet IDs + daily alert count)
# ---------------------------------------------------------------------------

def load_state(path: Path) -> dict:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"seen_ids": [], "daily_alerts": {}, "last_run": None}


def save_state(state: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Keep only last 5000 seen IDs to prevent unbounded growth
    state["seen_ids"] = state["seen_ids"][-5000:]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False, default=str)

# ---------------------------------------------------------------------------
# Data fetching — Apify primary, xreach fallback
# ---------------------------------------------------------------------------

def fetch_tweets_apify(handles: list[str], limit_per_account: int, logger: logging.Logger) -> list[dict]:
    """Fetch tweets via Apify (altimis/scweet actor)."""
    try:
        from apify_client import ApifyClient
    except ImportError:
        logger.error("apify_client not installed: pip install apify-client")
        return []

    token = os.getenv("APIFY_TOKEN")
    if not token:
        logger.error("APIFY_TOKEN not set")
        return []

    client = ApifyClient(token)
    at_handles = [f"@{h.lstrip('@')}" for h in handles]
    total_limit = max(len(handles) * limit_per_account, 100)  # actor min 100

    logger.info(f"Apify: fetching {len(handles)} accounts (limit={total_limit})")

    try:
        run = client.actor("altimis/scweet").call(run_input={
            "source_mode": "profiles",
            "profile_urls": at_handles,
            "max_items": total_limit,
        })
        items = client.dataset(run["defaultDatasetId"]).list_items().items
        logger.info(f"Apify: got {len(items)} tweets")
        return list(items)
    except Exception as e:
        logger.error(f"Apify error: {e}")
        return []


def fetch_tweets_xreach(handles: list[str], limit_per_account: int, logger: logging.Logger) -> list[dict]:
    """Fallback: fetch via xreach CLI (agent-reach)."""
    import subprocess
    auth_token = os.getenv("X_AUTH_TOKEN", "")
    ct0 = os.getenv("X_CT0", "")
    if not auth_token or not ct0:
        logger.warning("xreach: X_AUTH_TOKEN / X_CT0 not set in .env — skipping")
        return []
    all_tweets = []
    for handle in handles:
        try:
            cmd = [
                "npx", "xreach", "tweets", f"@{handle.lstrip('@')}",
                "-n", str(limit_per_account), "--json",
                "--auth-token", auth_token, "--ct0", ct0,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                                    encoding="utf-8", shell=(sys.platform == "win32"))
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                items = []
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict) and "items" in data:
                    items = data["items"]
                elif isinstance(data, dict) and "tweets" in data:
                    items = data["tweets"]
                all_tweets.extend(items)
                logger.info(f"  xreach @{handle.lstrip('@')}: {len(items)} tweets")
        except Exception as e:
            logger.warning(f"xreach failed for @{handle}: {e}")
    logger.info(f"xreach: got {len(all_tweets)} tweets from {len(handles)} accounts")
    return all_tweets

# ---------------------------------------------------------------------------
# Tweet normalization
# ---------------------------------------------------------------------------

def normalize_tweet(raw: dict) -> dict:
    """Normalize tweet fields across different data sources."""
    user = raw.get("user", {})
    handle = (raw.get("handle", "")
              or user.get("handle", "")
              or user.get("screenName", "")  # xreach format
              or raw.get("username", ""))
    handle = handle.lstrip("@")

    text = raw.get("text", "") or raw.get("full_text", "") or raw.get("content", "")

    # Parse created_at to datetime — xreach uses "createdAt"
    created_str = (raw.get("created_at", "")
                   or raw.get("createdAt", "")  # xreach format
                   or raw.get("date", "")
                   or raw.get("timestamp", ""))
    created_at = None
    if created_str:
        for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
                     "%a %b %d %H:%M:%S %z %Y",  # xreach: "Fri Apr 10 14:14:09 +0000 2026"
                     "%Y-%m-%d %H:%M:%S"]:
            try:
                created_at = datetime.strptime(created_str, fmt)
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue

    tweet_id = str(raw.get("id", "") or raw.get("tweet_id", "") or raw.get("id_str", ""))
    if not tweet_id and raw.get("tweet_url"):
        # Extract ID from URL
        parts = str(raw["tweet_url"]).rstrip("/").split("/")
        if parts:
            tweet_id = parts[-1]

    url = raw.get("tweet_url", "") or raw.get("url", "")
    if not url and handle and tweet_id:
        url = f"https://x.com/{handle}/status/{tweet_id}"

    return {
        "id": tweet_id,
        "handle": handle,
        "text": text,
        "created_at": created_at,
        "created_at_str": created_str,
        "likes": int(raw.get("favorite_count", 0) or raw.get("likeCount", 0) or raw.get("likes", 0) or 0),
        "retweets": int(raw.get("retweet_count", 0) or raw.get("retweetCount", 0) or raw.get("retweets", 0) or 0),
        "replies": int(raw.get("reply_count", 0) or raw.get("replyCount", 0) or raw.get("replies", 0) or 0),
        "views": int(raw.get("viewCount", 0) or raw.get("views", 0) or 0),
        "url": url,
        "is_retweet": bool(raw.get("is_retweet", False) or raw.get("isRetweet", False) or raw.get("retweeted", False)),
    }

# ---------------------------------------------------------------------------
# Ticker extraction
# ---------------------------------------------------------------------------

def extract_tickers(text: str, config: dict) -> list[dict]:
    """Extract tickers from tweet text. Returns list of {ticker, asset_class, source}."""
    tp = config["ticker_patterns"]
    found = {}

    # 1. Cashtags ($TICKER)
    for match in re.finditer(tp["cashtag_regex"], text):
        ticker = match.group(1)
        found[ticker] = "cashtag"

    # 2. Known tickers (word boundary match, case-insensitive for crypto)
    text_upper = text.upper()
    for ticker in tp["known_tickers"]:
        if ticker not in found:
            pattern = rf"\b{re.escape(ticker)}\b"
            if re.search(pattern, text_upper):
                found[ticker] = "known_ticker"

    # 3. Company name mapping
    text_lower = text.lower()
    for name, ticker in tp["company_map"].items():
        if name in text_lower and ticker not in found:
            found[ticker] = "company_name"

    # Classify asset classes
    asset_classes = tp.get("asset_classes", {})
    results = []
    for ticker, source in found.items():
        ac = "unknown"
        for cls, tickers in asset_classes.items():
            if ticker in tickers:
                ac = cls
                break
        results.append({"ticker": ticker, "asset_class": ac, "source": source})

    return results

# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_account(handle: str, config: dict) -> float:
    """Score based on account tier."""
    accounts = {a["handle"].lower(): a for a in config["accounts"]}
    acct = accounts.get(handle.lower())
    if not acct:
        return 50  # Unknown account, neutral score
    tier = str(acct.get("tier", 4))
    return config["tier_scores"].get(tier, 60)


def score_content(text: str, config: dict) -> float:
    """Score tweet content for trade signal strength."""
    score = 0
    text_lower = text.lower()
    matched_categories: set[str] = set()

    for category, signal in config["content_signals"].items():
        for pattern in signal["patterns"]:
            if re.search(pattern, text_lower):
                score += signal["weight"]
                matched_categories.add(category)
                break  # One match per category

    # Bonus: explicit ticker mention + validated direction = strong signal
    has_ticker = bool(re.search(r"\$[A-Z]{1,5}\b", text))
    if has_ticker and "direction" in matched_categories:
        score += 25

    return max(0, min(100, score))


def score_engagement(tweet: dict) -> float:
    """Score based on engagement velocity (likes, retweets, replies, views)."""
    now = datetime.now(timezone.utc)
    created = tweet.get("created_at")
    if not created:
        hours = 12  # Default if unknown
    else:
        hours = max((now - created).total_seconds() / 3600, 0.5)

    likes = tweet.get("likes", 0)
    retweets = tweet.get("retweets", 0)
    replies = tweet.get("replies", 0)
    views = tweet.get("views", 0)

    # For older tweets, cap hours to avoid diluting genuinely viral posts
    effective_hours = min(hours, 48)

    # Core engagement velocity (interactions per hour)
    interaction_velocity = (likes + retweets * 3 + replies * 2) / effective_hours
    interaction_score = min(100, interaction_velocity / 50 * 100)

    # View velocity bonus: high views = people are paying attention
    # 10K views/hour is notable, 100K/hour is viral
    view_velocity = views / effective_hours
    view_score = min(100, view_velocity / 5000 * 100)

    # Blend: 70% interactions, 30% views
    return min(100, interaction_score * 0.7 + view_score * 0.3)


def score_recency(tweet: dict) -> float:
    """Score based on how recent the tweet is.

    Decay curve: 100 for <1h, ~75 at 6h, ~50 at 24h, ~25 at 72h, 0 at 7d.
    This is gentler than linear decay — important because we poll every 2h
    and tweets from credible accounts remain actionable for 1-3 days.
    """
    now = datetime.now(timezone.utc)
    created = tweet.get("created_at")
    if not created:
        return 50
    hours = (now - created).total_seconds() / 3600
    if hours <= 1:
        return 100
    # Logarithmic decay: drops ~50% at 24h, ~0 at 168h (7 days)
    import math
    return max(0, 100 * (1 - math.log(hours) / math.log(168)))


def score_tweet(tweet: dict, config: dict) -> dict:
    """Compute final score for a tweet. Returns enriched tweet dict."""
    weights = config["scoring_weights"]

    acct_score = score_account(tweet["handle"], config)
    cont_score = score_content(tweet["text"], config)
    eng_score = score_engagement(tweet)
    rec_score = score_recency(tweet)

    final = (acct_score * weights["account"] +
             cont_score * weights["content"] +
             eng_score * weights["engagement"] +
             rec_score * weights["recency"])

    # Content gate: require minimum content signal to pass threshold
    min_content = config.get("min_content_score", 15)
    threshold = config.get("score_threshold", 60)
    if cont_score < min_content:
        final = min(final, threshold - 10)

    tickers = extract_tickers(tweet["text"], config)

    tweet["scores"] = {
        "account": round(acct_score, 1),
        "content": round(cont_score, 1),
        "engagement": round(eng_score, 1),
        "recency": round(rec_score, 1),
        "final": round(final, 1),
    }
    tweet["tickers"] = tickers
    return tweet

# ---------------------------------------------------------------------------
# Telegram alert
# ---------------------------------------------------------------------------

def format_alert(tweet: dict, config: dict) -> str:
    """Format a scored tweet as an HTML Telegram message."""
    score = tweet["scores"]["final"]
    handle = tweet["handle"]

    # Look up account info
    accounts = {a["handle"].lower(): a for a in config["accounts"]}
    acct = accounts.get(handle.lower(), {})
    name = acct.get("name", "")
    tier = acct.get("tier", "?")
    tags = ", ".join(acct.get("tags", []))

    # Ticker display
    ticker_parts = []
    for t in tweet.get("tickers", []):
        label = t["asset_class"].replace("_", " ").title()
        ticker_parts.append(f"<code>${t['ticker']}</code> [{label}]")
    ticker_line = " ".join(ticker_parts) if ticker_parts else "<i>No explicit ticker</i>"

    # Truncate text
    text = tweet["text"]
    if len(text) > 500:
        text = text[:497] + "..."

    # Engagement
    likes = f"{tweet['likes']:,}" if tweet['likes'] else "0"
    rts = f"{tweet['retweets']:,}" if tweet['retweets'] else "0"
    replies = f"{tweet['replies']:,}" if tweet['replies'] else "0"

    # Time ago
    time_ago = ""
    if tweet.get("created_at"):
        hours = (datetime.now(timezone.utc) - tweet["created_at"]).total_seconds() / 3600
        if hours < 1:
            time_ago = f"{int(hours * 60)}m ago"
        elif hours < 24:
            time_ago = f"{hours:.1f}h ago"
        else:
            time_ago = f"{hours / 24:.1f}d ago"

    # Score breakdown
    s = tweet["scores"]

    msg = (
        f"<b>FinTwit Signal</b> \u2014 Score: {score:.0f}/100\n\n"
        f"<b>@{handle}</b>"
    )
    if name:
        msg += f" ({name})"
    msg += f" | Tier {tier}"
    if tags:
        msg += f" | {tags}"
    msg += f"\nTickers: {ticker_line}\n\n"
    msg += f"\"{text}\"\n\n"
    msg += f"Likes: {likes} | RT: {rts} | Replies: {replies}"
    if time_ago:
        msg += f" | {time_ago}"
    msg += f"\nScoring: acct={s['account']:.0f} content={s['content']:.0f} eng={s['engagement']:.0f} recency={s['recency']:.0f}"
    if tweet.get("url"):
        msg += f"\n\n{tweet['url']}"

    return msg


def send_telegram_alert(message: str, config: dict, logger: logging.Logger) -> bool:
    """Send alert via Telegram Bot API."""
    import requests

    bot_token = os.getenv(config.get("telegram_bot_token_env", "TELEGRAM_BOT_TOKEN_OPS"))
    chat_id = os.getenv(config.get("telegram_chat_id_env", "TELEGRAM_CHAT_ID_OPS"))

    if not bot_token or not chat_id:
        logger.error(f"Telegram credentials missing: token={'set' if bot_token else 'MISSING'}, chat={'set' if chat_id else 'MISSING'}")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    try:
        resp = requests.post(url, json=payload, timeout=20)
        if resp.status_code == 200:
            logger.info("Telegram alert sent")
            return True
        else:
            logger.error(f"Telegram error {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
        return False

# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline(dry_run: bool = False, backfill: bool = False):
    """Execute one polling cycle."""
    config = load_config()
    log_path = ROOT / config["log_file"]
    logger = _setup_logging(log_path)
    state_path = ROOT / config["state_file"]
    state = load_state(state_path)

    today = datetime.now().strftime("%Y-%m-%d")

    # Daily alert counter
    if today not in state.get("daily_alerts", {}):
        state["daily_alerts"] = {today: 0}
    alerts_today = state["daily_alerts"].get(today, 0)
    max_alerts = config.get("max_alerts_per_day", 10)

    logger.info(f"=== FinTwit Monitor run ({today}) | alerts today: {alerts_today}/{max_alerts} ===")

    # Fetch tweets
    handles = [a["handle"] for a in config["accounts"]]
    limit = config.get("tweets_per_account", 10)

    # xreach primary (free, no quota), Apify fallback
    tweets_raw = fetch_tweets_xreach(handles, limit, logger)
    if not tweets_raw:
        logger.warning("xreach returned 0 tweets, trying Apify fallback")
        tweets_raw = fetch_tweets_apify(handles, limit, logger)

    if not tweets_raw:
        logger.error("No tweets fetched from any source")
        state["last_run"] = datetime.now(timezone.utc).isoformat()
        save_state(state, state_path)
        return

    # Normalize
    tweets = [normalize_tweet(t) for t in tweets_raw]
    logger.info(f"Normalized {len(tweets)} tweets")

    # Dedup
    seen = set(state.get("seen_ids", []))
    if backfill:
        new_tweets = tweets
    else:
        new_tweets = [t for t in tweets if t["id"] and t["id"] not in seen]
    logger.info(f"New tweets after dedup: {len(new_tweets)} (backfill={backfill})")

    # Score
    scored = [score_tweet(t, config) for t in new_tweets]
    threshold = config.get("score_threshold", 60)
    passing = [t for t in scored if t["scores"]["final"] >= threshold]

    # Sort by score descending
    passing.sort(key=lambda t: t["scores"]["final"], reverse=True)

    logger.info(f"Scored {len(scored)} tweets | {len(passing)} pass threshold ({threshold})")

    # Log top scores for debugging
    for t in scored[:5]:
        logger.info(f"  @{t['handle']}: {t['scores']['final']:.0f} | {t['text'][:80]}...")

    # Save scored output
    scored_path = ROOT / "scraped_data" / "twitter" / "fintwit_scored_latest.json"
    scored_path.parent.mkdir(parents=True, exist_ok=True)
    scored_serializable = []
    for t in scored:
        s = dict(t)
        if s.get("created_at"):
            s["created_at"] = s["created_at"].isoformat()
        scored_serializable.append(s)
    with open(scored_path, "w", encoding="utf-8") as f:
        json.dump(scored_serializable, f, indent=2, ensure_ascii=False, default=str)

    # Send alerts
    alerts_sent = 0
    for tweet in passing:
        if alerts_today + alerts_sent >= max_alerts:
            logger.warning(f"Daily alert limit reached ({max_alerts})")
            break

        msg = format_alert(tweet, config)

        if dry_run:
            print("\n" + "=" * 60)
            print("[DRY RUN] Would send alert:")
            print(msg)
            print("=" * 60)
            alerts_sent += 1
        else:
            if send_telegram_alert(msg, config, logger):
                alerts_sent += 1
                time.sleep(1)  # Rate limit Telegram

    # Update state
    new_ids = [t["id"] for t in tweets if t["id"]]
    state["seen_ids"] = list(set(state.get("seen_ids", []) + new_ids))
    state["daily_alerts"][today] = alerts_today + alerts_sent
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    save_state(state, state_path)

    logger.info(f"Done. Alerts sent: {alerts_sent} | Total seen IDs: {len(state['seen_ids'])}")

    # Daily summary at end of day (optional)
    if alerts_sent == 0 and len(passing) == 0:
        logger.info("No signals this cycle — all quiet")


def main():
    parser = argparse.ArgumentParser(description="FinTwit Signal Monitor")
    parser.add_argument("--dry-run", action="store_true", help="Score and print, don't send Telegram")
    parser.add_argument("--backfill", action="store_true", help="Process all tweets ignoring dedup")
    parser.add_argument("--loop", action="store_true", help="Run continuously with configured interval")
    args = parser.parse_args()

    if args.loop:
        config = load_config()
        interval = config.get("polling_interval_minutes", 120)
        print(f"FinTwit Monitor — looping every {interval} minutes. Ctrl+C to stop.")
        while True:
            try:
                run_pipeline(dry_run=args.dry_run, backfill=args.backfill)
            except Exception as e:
                print(f"ERROR in pipeline: {e}")
            time.sleep(interval * 60)
    else:
        run_pipeline(dry_run=args.dry_run, backfill=args.backfill)


if __name__ == "__main__":
    main()
