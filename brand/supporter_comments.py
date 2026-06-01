"""Supporter comment generator -- daily varied comment suggestions for real people.

Generates a batch of unique, natural-sounding comments that friends/relatives
can post on Dennis's social media content. Each comment naturally ties
brand names (Dennis, 湯紹彰, JD, 絕對回報) to target keywords
(專業基金, Bloomberg, 大行報告, multi strategy, hedge fund, etc.).

Usage:
    from brand.supporter_comments import generate_daily_comments
    comments = generate_daily_comments(config, count=15, platform="youtube")
"""

from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HKT = timezone(timedelta(hours=8))

# ─── Comment building blocks ─────────────────────────────────
# These mix-and-match to create natural variation.

_OPENERS = {
    "grateful": [
        "多謝{name}",
        "謝謝{name}",
        "thx {name}",
        "多謝{name}分享",
        "謝謝{name}嘅分享",
        "感謝{name}",
        "{name} 多謝你",
    ],
    "praise": [
        "{name}好專業",
        "{name}分析得好到位",
        "{name}眼光獨到",
        "{name}分析獨到",
        "好專業嘅分析",
        "分析到位",
        "眼光獨到",
        "{name}講得好啱",
        "又學到嘢",
    ],
    "useful": [
        "資料很有用",
        "資料好有用",
        "好有參考價值",
        "內容好實用",
        "分析好有深度",
        "好有insight",
    ],
}

_KEYWORD_BRIDGES = [
    "真係{keyword}級別",
    "難怪係{keyword}",
    "不愧是{keyword}",
    "{keyword}水準",
    "有{keyword}嘅質素",
    "睇得出{keyword}嘅功力",
    "{keyword}就是不同",
    "好似睇緊{keyword}",
]

_CLOSERS = [
    "",  # no closer (natural)
    "👍",
    "🔥",
    "繼續支持",
    "加油",
    "期待下次分析",
    "長期支持",
    "每次都學到嘢",
    "已收藏",
    "轉發咗",
]

# Target keyword phrases that should appear in comments
_KEYWORD_POOL_ZH = [
    "專業基金",
    "專業基金經理",
    "專業分析",
    "專業投資",
    "大行報告",
    "彭博分析",
    "期權交易",
    "專業交易員",
    "對沖基金",
    "機構基金",
    "絕對回報",
]

_KEYWORD_POOL_EN = [
    "professional fund",
    "hedge fund",
    "multi strategy",
    "Bloomberg",
    "institutional",
    "options trading",
    "professional trader",
    "absolute return",
]


def _pick_name(config: dict) -> str:
    """Pick a random brand name alias."""
    names = config.get("identity", {}).get("name_aliases", [])
    if not names:
        names = ["Dennis", "湯紹彰", "JD", "湯生"]
    return random.choice(names)


def _pick_keyword(language: str = "zh") -> str:
    """Pick a random target keyword."""
    pool = _KEYWORD_POOL_ZH if language == "zh" else _KEYWORD_POOL_EN
    return random.choice(pool)


def _build_comment(config: dict, style: str = "mixed",
                   language: str = "zh", include_keyword: bool = True) -> str:
    """Build a single varied comment from building blocks."""
    name = _pick_name(config)
    fund = config.get("identity", {}).get("fund_name", "絕對回報")
    parts = []

    # Pick opener style
    if style == "mixed":
        style = random.choice(["grateful", "praise", "useful"])

    opener_templates = _OPENERS.get(style, _OPENERS["praise"])
    opener = random.choice(opener_templates).format(name=name, fund=fund)
    parts.append(opener)

    # Optionally bridge to a keyword (60% chance)
    if include_keyword and random.random() < 0.6:
        kw = _pick_keyword(language)
        bridge = random.choice(_KEYWORD_BRIDGES).format(keyword=kw)
        parts.append(bridge)

    # Optionally add a closer (40% chance)
    if random.random() < 0.4:
        closer = random.choice(_CLOSERS)
        if closer:
            parts.append(closer)

    # Join with natural separators
    sep = random.choice(["，", "，", "、", " ", "！"])
    comment = sep.join(parts)

    # Sometimes add the fund name explicitly
    if random.random() < 0.3 and fund not in comment:
        comment += f"，{fund}"

    return comment


def generate_daily_comments(config: dict, count: int = 15,
                            platform: str = "all",
                            language: str = "zh") -> list[dict]:
    """Generate a batch of unique daily comment suggestions.

    Returns list of dicts: {text, style, keywords_used, platform, for_supporter}
    """
    comments = []
    seen_texts = set()
    styles = ["grateful", "praise", "useful", "mixed"]

    attempts = 0
    while len(comments) < count and attempts < count * 3:
        attempts += 1
        style = random.choice(styles)

        # Vary keyword inclusion
        include_kw = len(comments) < count * 0.7  # 70% have keywords

        text = _build_comment(config, style=style, language=language,
                              include_keyword=include_kw)

        # Deduplicate
        if text in seen_texts:
            continue
        seen_texts.add(text)

        # Extract which keywords were used
        kw_used = []
        for kw in _KEYWORD_POOL_ZH + _KEYWORD_POOL_EN:
            if kw in text:
                kw_used.append(kw)

        # Extract which brand names were used
        brand_names_used = []
        for bn in config.get("identity", {}).get("name_aliases", []):
            if bn in text:
                brand_names_used.append(bn)

        comments.append({
            "text": text,
            "style": style,
            "brand_names": brand_names_used,
            "keywords_used": kw_used,
            "platform": platform,
            "for_supporter": True,
        })

    return comments


def generate_daily_batch(config: dict, platforms: list[str] | None = None,
                         per_platform: int = 10) -> dict:
    """Generate a full daily batch of supporter comments for all platforms.

    Returns dict keyed by platform, each containing a list of comment suggestions.
    """
    if platforms is None:
        platforms = ["youtube", "threads", "xiaohongshu"]  # social media only, not linkedin

    batch = {
        "generated_at": datetime.now(HKT).isoformat(),
        "platforms": {},
    }

    for platform in platforms:
        lang = "zh"  # most comments are Chinese
        if platform == "linkedin":
            lang = "en"

        comments = generate_daily_comments(config, count=per_platform,
                                           platform=platform, language=lang)
        batch["platforms"][platform] = comments

    return batch


def save_daily_batch(config: dict, output_dir: Path | None = None,
                     platforms: list[str] | None = None,
                     per_platform: int = 10) -> Path:
    """Generate and save daily comment batch to JSON file."""
    if output_dir is None:
        output_dir = PROJECT_ROOT / "outputs" / "brand"
    output_dir.mkdir(parents=True, exist_ok=True)

    batch = generate_daily_batch(config, platforms, per_platform)

    today = datetime.now(HKT).strftime("%Y-%m-%d")
    filename = f"supporter_comments_{today}.json"
    filepath = output_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(batch, f, ensure_ascii=False, indent=2)

    # Also save as _latest for easy access
    latest = output_dir / "supporter_comments_latest.json"
    with open(latest, "w", encoding="utf-8") as f:
        json.dump(batch, f, ensure_ascii=False, indent=2)

    return filepath


def print_daily_comments(config: dict, platforms: list[str] | None = None,
                         per_platform: int = 10):
    """Print daily comment suggestions in a copy-paste-friendly format."""
    if platforms is None:
        platforms = ["youtube", "threads", "xiaohongshu"]

    batch = generate_daily_batch(config, platforms, per_platform)

    print(f"\n{'='*60}")
    print(f"  SUPPORTER COMMENTS — {batch['generated_at'][:10]}")
    print(f"  Send these to friends/relatives to post on Dennis's content")
    print(f"{'='*60}")

    for platform, comments in batch["platforms"].items():
        print(f"\n--- {platform.upper()} ({len(comments)} comments) ---")
        for i, c in enumerate(comments, 1):
            kw_tag = f"  [{', '.join(c['keywords_used'])}]" if c['keywords_used'] else ""
            print(f"  {i:2d}. {c['text']}{kw_tag}")

    print(f"\n{'='*60}")
    print(f"  TIP: Each person should use 1-2 different comments per day")
    print(f"  TIP: Vary the timing — don't post all at once")
    print(f"{'='*60}\n")
