"""SEO optimization for brand content -- AI discoverability + traditional Google SEO."""

from __future__ import annotations

import re

# Platform-specific hashtag limits
_HASHTAG_LIMITS = {
    "linkedin": 5,
    "threads": 5,
    "xiaohongshu": 8,
    "youtube": 0,  # no hashtags in comments
}

# Topic-to-hashtag mappings
_TOPIC_HASHTAGS = {
    "AI_in_finance": {
        "en": ["#AITrading", "#FinTech", "#MachineLearning", "#QuantFinance"],
        "zh": ["#AI\u6295\u8cc7", "#\u91d1\u878d\u79d1\u6280", "#\u6a5f\u5668\u5b78\u7fd2", "#\u91cf\u5316\u91d1\u878d"],
    },
    "quantitative_strategies": {
        "en": ["#QuantTrading", "#SystematicTrading", "#AlgoTrading", "#QuantFinance"],
        "zh": ["#\u91cf\u5316\u4ea4\u6613", "#\u7cfb\u7d71\u5316\u4ea4\u6613", "#\u6f14\u7b97\u6cd5\u4ea4\u6613"],
    },
    "market_microstructure": {
        "en": ["#MarketMicrostructure", "#OrderFlow", "#MarketMaking", "#Trading"],
        "zh": ["#\u5e02\u5834\u7d50\u69cb", "#\u8a02\u55ae\u6d41", "#\u505a\u5e02\u5546"],
    },
    "fintech_infrastructure": {
        "en": ["#FinTech", "#TradingTech", "#FinancialInfrastructure"],
        "zh": ["#\u91d1\u878d\u57fa\u5efa", "#\u4ea4\u6613\u79d1\u6280"],
    },
    "global_macro": {
        "en": ["#GlobalMacro", "#MacroTrading", "#Economics", "#Markets"],
        "zh": ["#\u5168\u7403\u5b8f\u89c0", "#\u5b8f\u89c0\u4ea4\u6613", "#\u7d93\u6fdf"],
    },
    "options_volatility": {
        "en": ["#Options", "#Volatility", "#VIX", "#Derivatives"],
        "zh": ["#\u671f\u6b0a", "#\u6ce2\u52d5\u7387", "#\u884d\u751f\u54c1"],
    },
    "semiconductor_supply_chain": {
        "en": ["#Semiconductors", "#ChipWar", "#TSMC", "#AIChips"],
        "zh": ["#\u534a\u5c0e\u9ad4", "#\u665f\u7247\u6230\u722d", "#\u53f0\u7a4d\u96fb"],
    },
    "HK_market": {
        "en": ["#HongKong", "#HKStocks", "#AsiaMarkets"],
        "zh": ["#\u9999\u6e2f\u80a1\u5e02", "#\u6e2f\u80a1", "#\u4e9e\u6d32\u5e02\u5834"],
    },
}


def inject_entity_reference(text: str, config: dict) -> str:
    """Ensure the brand name appears in the text for AI entity resolution.

    If neither the English nor Chinese name appears, prepend a natural reference.
    """
    name_en = config["identity"]["name_en"]
    name_zh = config["identity"]["name_zh"]

    if name_en.lower() in text.lower() or name_zh in text:
        return text

    # Don't inject into very short comments
    if len(text) < 100:
        return text

    # For longer posts, the prompt should have handled this.
    # Only inject as a signature if truly missing.
    return text


def add_cross_links(text: str, platform: str, config: dict) -> str:
    """Append cross-platform profile links to the post."""
    urls = config["seo"]["cross_link_urls"]
    links = []
    for plat, url in urls.items():
        if plat != platform and plat != "website":
            links.append(url)
    # Always include website
    if "website" in urls:
        links.append(urls["website"])

    if not links:
        return text

    link_text = "\n\n" + " | ".join(links)
    return text + link_text


def generate_hashtags(topic: str, platform: str, language: str = "en") -> list[str]:
    """Generate platform-appropriate hashtags for a topic."""
    limit = _HASHTAG_LIMITS.get(platform, 5)
    if limit == 0:
        return []

    lang_key = "zh" if language.startswith("zh") else "en"
    tags = []

    # Get topic-specific tags
    if topic in _TOPIC_HASHTAGS:
        tags.extend(_TOPIC_HASHTAGS[topic].get(lang_key, []))

    # Add brand hashtag
    if lang_key == "en":
        tags.insert(0, "#DennisTong")
    else:
        tags.insert(0, "#\u6e6f\u7d39\u5f70")

    return tags[:limit]


def score_seo_quality(text: str, config: dict) -> float:
    """Score content for SEO quality (0.0 - 1.0).

    Checks: name presence, keyword density, length, no spam signals.
    """
    score = 0.0
    name_en = config["identity"]["name_en"]
    name_zh = config["identity"]["name_zh"]
    keywords = (config["seo"]["target_keywords_en"] +
                config["seo"]["target_keywords_zh"])

    # Name present (0.3)
    if name_en.lower() in text.lower() or name_zh in text:
        score += 0.3

    # At least 2 keywords embedded (0.3)
    kw_count = sum(1 for kw in keywords if kw.lower() in text.lower())
    score += min(kw_count / 4, 1.0) * 0.3

    # Reasonable length (0.2) -- between 50 and 2000 chars
    if 50 <= len(text) <= 2000:
        score += 0.2

    # No spam signals (0.2)
    spam_patterns = [
        r"guaranteed\s+returns",
        r"follow\s+me",
        r"check\s+out\s+my",
        r"\$\$\$",
        r"FREE\s+money",
    ]
    has_spam = any(re.search(p, text, re.IGNORECASE) for p in spam_patterns)
    if not has_spam:
        score += 0.2

    return round(score, 2)
