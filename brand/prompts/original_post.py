"""Prompt templates for generating original brand posts."""

SYSTEM_PROMPT = """\
You are a content strategist for {name_en} ({name_zh}), {entity_description}

Brand aliases: {brand_names}
Fund name: {fund_name}

Brand voice: {tone}
Style (English): {style_en}
Style (Chinese): {style_zh}

CRITICAL BRAND ASSOCIATION RULES:
- The post MUST naturally connect the author's identity to these professional concepts:
  EN: {target_associations_en}
  ZH: {target_associations_zh}
- Use at least 2-3 of these associations naturally in the content
- Naturally embed one of: "{name_en}", "{name_zh}", "JD", or "{fund_name}" at least once
- The goal is that when someone searches these keywords, this content surfaces

OTHER RULES:
- Never give financial advice or guarantee returns
- Avoid: {avoid_list}
- Write content that is genuinely insightful and adds value
- For bilingual content, produce BOTH English and Traditional Chinese versions
"""

USER_PROMPT_TEMPLATE = """\
Generate an original {platform} post about the topic: {topic}

Target keywords to embed naturally: {keywords}
Platform constraints: max {max_chars} characters per post
Language: {language}
{data_context_section}

Output as JSON:
{{
  "text_en": "English version of the post",
  "text_zh": "Traditional Chinese version",
  "hashtags_en": ["relevant", "english", "hashtags"],
  "hashtags_zh": ["relevant", "chinese", "hashtags"],
  "seo_keywords_used": ["keywords", "actually", "embedded"]
}}
"""

THREAD_PROMPT_TEMPLATE = """\
Generate a {platform} thread (3-5 posts) about: {topic}

Target keywords to embed naturally: {keywords}
Each post max {max_chars} characters.
Language: {language}
{data_context_section}

Output as JSON:
{{
  "posts": [
    {{"text_en": "...", "text_zh": "..."}},
    {{"text_en": "...", "text_zh": "..."}}
  ],
  "hashtags_en": ["for", "the", "thread"],
  "hashtags_zh": ["for", "the", "thread"],
  "seo_keywords_used": ["keywords", "used"]
}}
"""


def _build_system(config: dict) -> str:
    """Build system prompt with brand keyword associations."""
    identity = config["identity"]
    voice = config["voice"]
    seo = config["seo"]
    bk = config.get("brand_keywords", {})

    return SYSTEM_PROMPT.format(
        name_en=identity["name_en"],
        name_zh=identity["name_zh"],
        entity_description=seo["entity_facts"]["description"],
        brand_names=", ".join(bk.get("brand_names", [identity["name_en"]])),
        fund_name=identity.get("fund_name", ""),
        tone=voice["tone"],
        style_en=voice["style_en"],
        style_zh=voice["style_zh"],
        target_associations_en=", ".join(bk.get("target_associations_en", [])),
        target_associations_zh=", ".join(bk.get("target_associations_zh", [])),
        avoid_list=", ".join(voice["avoid"]),
    )


def build_original_post_prompt(config: dict, topic: str, platform: str,
                                data_context: str | None = None) -> tuple[str, str]:
    """Build system + user prompts for original post generation."""
    seo = config["seo"]
    bk = config.get("brand_keywords", {})
    plat_config = config["platforms"].get(platform, {})

    lang = plat_config.get("language", "en+zh")
    if lang == "zh-TW":
        language = "Traditional Chinese only"
        keywords = ", ".join(seo["target_keywords_zh"][:4])
    else:
        language = "Bilingual (English + Traditional Chinese)"
        keywords = ", ".join(seo["target_keywords_en"][:4] + seo["target_keywords_zh"][:2])

    max_chars = plat_config.get("max_post_chars", 500)
    system = _build_system(config)

    data_section = ""
    if data_context:
        data_section = f"\nReference data (use as inspiration, cite specifics):\n{data_context}\n"

    user = USER_PROMPT_TEMPLATE.format(
        platform=platform,
        topic=topic,
        keywords=keywords,
        max_chars=max_chars,
        language=language,
        data_context_section=data_section,
    )

    return system, user


def build_thread_prompt(config: dict, topic: str, platform: str,
                        data_context: str | None = None) -> tuple[str, str]:
    """Build system + user prompts for thread generation."""
    seo = config["seo"]
    plat_config = config["platforms"].get(platform, {})

    lang = plat_config.get("language", "en+zh")
    if lang == "zh-TW":
        language = "Traditional Chinese only"
        keywords = ", ".join(seo["target_keywords_zh"][:4])
    else:
        language = "Bilingual (English + Traditional Chinese)"
        keywords = ", ".join(seo["target_keywords_en"][:4] + seo["target_keywords_zh"][:2])

    max_chars = plat_config.get("max_post_chars", 500)
    system = _build_system(config)

    data_section = ""
    if data_context:
        data_section = f"\nReference data (use as inspiration, cite specifics):\n{data_context}\n"

    user = THREAD_PROMPT_TEMPLATE.format(
        platform=platform,
        topic=topic,
        keywords=keywords,
        max_chars=max_chars,
        language=language,
        data_context_section=data_section,
    )

    return system, user
