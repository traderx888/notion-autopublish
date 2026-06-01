"""Prompt templates for generating brand comments and replies."""

SYSTEM_PROMPT = """\
You are {name_en} ({name_zh}), {entity_description}

You are writing a comment/reply on {platform}. Your goal is to add genuine value
to the conversation while naturally building brand visibility.

Brand voice: {tone}
Style: {style}

RULES:
- Be genuinely insightful -- add a perspective the original post doesn't cover
- Never be self-promotional or spammy
- Never give financial advice or guarantee returns
- Keep it concise and relevant to the original content
- Naturally mention your expertise area when it fits (don't force it)
- Avoid: {avoid_list}
- Use {language} for this platform
"""

USER_PROMPT_TEMPLATE = """\
Write a thoughtful comment on this {platform} content:

Title: {target_title}
Author: {target_author}
Content snippet: {target_snippet}

Your comment should:
1. Show you actually read/watched the content
2. Add a unique insight from a quantitative finance / AI perspective
3. Be max {max_chars} characters
4. Language: {language}

Output as JSON:
{{
  "text": "Your comment text here",
  "language": "{lang_code}",
  "relevance_angle": "brief note on why this is relevant to your brand"
}}
"""


def build_comment_prompt(config: dict, platform: str,
                         target_title: str, target_author: str,
                         target_snippet: str) -> tuple[str, str]:
    """Build system + user prompts for comment generation.

    Returns (system_prompt, user_prompt).
    """
    identity = config["identity"]
    voice = config["voice"]
    seo = config["seo"]
    plat_config = config["platforms"].get(platform, {})

    lang = plat_config.get("language", "en+zh")
    if lang == "zh-TW":
        language = "Traditional Chinese"
        style = voice["style_zh"]
        lang_code = "zh"
    else:
        language = "English (or match the original content's language)"
        style = voice["style_en"]
        lang_code = "en"

    max_chars = min(plat_config.get("max_post_chars", 500), 300)

    system = SYSTEM_PROMPT.format(
        name_en=identity["name_en"],
        name_zh=identity["name_zh"],
        entity_description=seo["entity_facts"]["description"],
        platform=platform,
        tone=voice["tone"],
        style=style,
        avoid_list=", ".join(voice["avoid"]),
        language=language,
    )

    user = USER_PROMPT_TEMPLATE.format(
        platform=platform,
        target_title=target_title,
        target_author=target_author,
        target_snippet=target_snippet[:500],
        max_chars=max_chars,
        language=language,
        lang_code=lang_code,
    )

    return system, user
