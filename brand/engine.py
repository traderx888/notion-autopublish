"""Claude-powered content generation engine for brand posts and comments.

Follows the synthesize_with_claude() pattern from tools/bloomberg_newsletter_build.py:
  1. Try Claude CLI (non-interactive, pipe via stdin)
  2. Fallback to Anthropic SDK
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "brand_identity.json"

from brand.prompts.original_post import build_original_post_prompt, build_thread_prompt
from brand.prompts.comment_reply import build_comment_prompt
from brand.prompts.self_reply import build_self_reply_prompt
from brand.seo import generate_hashtags, score_seo_quality, add_cross_links


def load_config() -> dict:
    """Load brand identity config."""
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def _extract_json(text: str) -> dict | None:
    """Extract first JSON object from Claude response text."""
    # Try full response as JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find JSON block in markdown code fence
    match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Find first { ... } block
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


def _call_claude_cli(system_prompt: str, user_prompt: str) -> str | None:
    """Call Claude via CLI, piping the prompt via stdin."""
    try:
        full_prompt = f"[System]\n{system_prompt}\n\n[User]\n{user_prompt}"
        result = subprocess.run(
            ["claude", "-p", "--output-format", "json"],
            input=full_prompt,
            capture_output=True,
            text=True,
            timeout=120,
            encoding="utf-8",
        )
        if result.returncode != 0:
            print(f"  Claude CLI failed: {result.stderr[:200]}", file=sys.stderr)
            return None

        # Parse CLI JSON output
        try:
            cli_output = json.loads(result.stdout)
            return cli_output.get("result", result.stdout)
        except json.JSONDecodeError:
            return result.stdout

    except FileNotFoundError:
        return None  # claude CLI not installed, fall through to SDK
    except subprocess.TimeoutExpired:
        print("  Claude CLI timed out", file=sys.stderr)
        return None


def _call_claude_sdk(system_prompt: str, user_prompt: str) -> str | None:
    """Call Claude via Anthropic SDK."""
    try:
        import anthropic
        client = anthropic.Anthropic()  # uses ANTHROPIC_API_KEY env var
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return message.content[0].text
    except ImportError:
        print("  anthropic SDK not installed", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  Anthropic SDK error: {e}", file=sys.stderr)
        return None


def _generate(system_prompt: str, user_prompt: str) -> dict | None:
    """Generate content via Claude (CLI first, SDK fallback), return parsed JSON."""
    # Try CLI first
    raw = _call_claude_cli(system_prompt, user_prompt)
    if raw:
        result = _extract_json(raw)
        if result:
            return result

    # Fallback to SDK
    raw = _call_claude_sdk(system_prompt, user_prompt)
    if raw:
        return _extract_json(raw)

    return None


def generate_original_post(topic: str, platform: str,
                           data_context: str | None = None,
                           config: dict | None = None) -> dict | None:
    """Generate an original brand post.

    Returns dict with keys: text_en, text_zh, hashtags_en, hashtags_zh, seo_keywords_used
    """
    if config is None:
        config = load_config()

    system, user = build_original_post_prompt(config, topic, platform, data_context)
    result = _generate(system, user)

    if result:
        # Enrich with generated hashtags if Claude didn't provide good ones
        if not result.get("hashtags_en"):
            result["hashtags_en"] = generate_hashtags(topic, platform, "en")
        if not result.get("hashtags_zh"):
            result["hashtags_zh"] = generate_hashtags(topic, platform, "zh")

        # Score SEO quality
        text = result.get("text_en", "") + " " + result.get("text_zh", "")
        result["seo_score"] = score_seo_quality(text, config)

    return result


def generate_thread(topic: str, platform: str,
                    data_context: str | None = None,
                    config: dict | None = None) -> dict | None:
    """Generate a multi-post thread.

    Returns dict with keys: posts (list), hashtags_en, hashtags_zh, seo_keywords_used
    """
    if config is None:
        config = load_config()

    system, user = build_thread_prompt(config, topic, platform, data_context)
    return _generate(system, user)


def generate_comment(target_title: str, target_author: str,
                     target_snippet: str, platform: str,
                     config: dict | None = None) -> dict | None:
    """Generate a comment/reply for discovered content.

    Returns dict with keys: text, language, relevance_angle
    """
    if config is None:
        config = load_config()

    system, user = build_comment_prompt(
        config, platform, target_title, target_author, target_snippet,
    )
    return _generate(system, user)


def adapt_for_platform(content: dict, platform: str,
                       config: dict | None = None) -> str:
    """Format generated content for a specific platform.

    Takes the raw generation output and returns a ready-to-publish string.
    """
    if config is None:
        config = load_config()

    plat_config = config["platforms"].get(platform, {})
    lang = plat_config.get("language", "en+zh")
    max_chars = plat_config.get("max_post_chars", 500)

    # Pick the right language version
    if lang == "zh-TW":
        text = content.get("text_zh", content.get("text_en", ""))
        hashtags = content.get("hashtags_zh", [])
    else:
        # For bilingual platforms, combine EN then ZH
        text_en = content.get("text_en", "")
        text_zh = content.get("text_zh", "")
        if text_en and text_zh:
            text = f"{text_en}\n\n---\n\n{text_zh}"
        else:
            text = text_en or text_zh
        hashtags = content.get("hashtags_en", [])

    # Append hashtags
    if hashtags:
        tag_str = " ".join(hashtags)
        text = f"{text}\n\n{tag_str}"

    # Truncate if over limit (leave room for ellipsis)
    if len(text) > max_chars:
        text = text[:max_chars - 3] + "..."

    return text


def generate_self_reply(original_text: str, platform: str,
                        config: dict | None = None) -> dict | None:
    """Generate a follow-up reply to your own post.

    Returns dict with keys: text, angle
    """
    if config is None:
        config = load_config()

    system, user = build_self_reply_prompt(config, platform, original_text)
    return _generate(system, user)
