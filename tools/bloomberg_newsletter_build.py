"""Bloomberg Newsletter Builder — Editorial Synthesis via Claude.

Reads unprocessed markdown articles from state, groups by topic,
uses Claude to synthesize editorial summaries (stat grids, investment
implications, bilingual conclusions), then generates newsletter HTML
matching the hand-crafted style of newsletters #4 and #5.

Continues newsletter numbering from the last issued number in state.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import html as html_mod
from datetime import datetime, timezone, timedelta
from pathlib import Path
from textwrap import shorten

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Fix Windows cp950 encoding
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from tools.bloomberg_pdf_convert import (
    STATE_PATH,
    read_state,
    write_state,
    now_hkt_iso,
    HKT,
)

OUTPUT_DIR = REPO_ROOT / "output"
STUDENT_HTML = OUTPUT_DIR / "student.html"
MIN_ARTICLES = 3

# ---------------------------------------------------------------------------
# Topic metadata
# ---------------------------------------------------------------------------
TOPIC_META: dict[str, tuple[str, str, str, str]] = {
    "rates":        ("利率",       "Rates",         "tag-rates",  "&#127975;"),
    "china":        ("中國",       "China",         "tag-china",  "&#127464;"),
    "japan":        ("日本",       "Japan",         "tag-japan",  "&#127471;"),
    "geopolitics":  ("地緣政治",   "Geopolitics",   "tag-geo",    "&#128165;"),
    "oil":          ("石油",       "Oil & Energy",  "tag-oil",    "&#9981;"),
    "trade":        ("貿易",       "Trade",         "tag-trade",  "&#128230;"),
    "growth":       ("成長",       "Growth",        "tag-growth", "&#128200;"),
    "metals":       ("金屬",       "Metals",        "tag-metals", "&#129353;"),
    "inflation":    ("通膨",       "Inflation",     "tag-infl",   "&#128293;"),
    "policy":       ("政策",       "Policy",        "tag-policy", "&#128220;"),
    "valuations":   ("估值",       "Valuations",    "tag-val",    "&#128176;"),
    "volatility":   ("波動",       "Volatility",    "tag-vol",    "&#128168;"),
    "semiconductor":("半導體",     "Semiconductor", "tag-semi",   "&#128187;"),
    "credit":       ("信用",       "Credit",        "tag-credit", "&#127974;"),
    "space":        ("太空",       "Space",         "tag-space",  "&#128640;"),
}
DEFAULT_META = ("其他", "Miscellaneous", "tag-misc", "&#128196;")
CARD_ICONS = ["&#128202;", "&#127975;", "&#128165;", "&#128176;", "&#127760;", "&#9889;", "&#128293;", "&#128200;"]

# ---------------------------------------------------------------------------
# CSS (from newsletter_5)
# ---------------------------------------------------------------------------
NEWSLETTER_CSS = """\
  :root { --bg: #0d1117; --card: #161b22; --border: #30363d; --accent: #58a6ff;
          --green: #3fb950; --red: #f85149; --yellow: #d29922; --text: #c9d1d9; --muted: #8b949e;
          --orange: #f0883e; --purple: #bc8cff; --cyan: #39d2c0; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans TC', 'Microsoft JhengHei', Helvetica, Arial, sans-serif; line-height: 1.7; padding: 20px; max-width: 860px; margin: 0 auto; }
  h1 { color: #fff; font-size: 1.7em; margin-bottom: 4px; }
  .subtitle { color: var(--muted); font-size: 0.9em; margin-bottom: 8px; }
  .issue-badge { display: inline-block; background: rgba(88,166,255,0.15); color: var(--accent); padding: 3px 10px; border-radius: 12px; font-size: 0.8em; font-weight: 600; margin-bottom: 20px; }
  .tag { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.72em; font-weight: 600; margin-right: 4px; }
  .tag-rates { background: rgba(88,166,255,0.15); color: var(--accent); }
  .tag-china { background: rgba(240,136,62,0.15); color: var(--orange); }
  .tag-japan { background: rgba(248,81,73,0.15); color: var(--red); }
  .tag-geo   { background: rgba(248,81,73,0.15); color: var(--red); }
  .tag-oil   { background: rgba(210,153,34,0.15); color: var(--yellow); }
  .tag-trade { background: rgba(210,153,34,0.15); color: var(--yellow); }
  .tag-growth{ background: rgba(63,185,80,0.15); color: var(--green); }
  .tag-metals{ background: rgba(188,140,255,0.15); color: var(--purple); }
  .tag-infl  { background: rgba(248,81,73,0.15); color: var(--red); }
  .tag-policy{ background: rgba(88,166,255,0.15); color: var(--accent); }
  .tag-val   { background: rgba(63,185,80,0.15); color: var(--green); }
  .tag-vol   { background: rgba(248,81,73,0.15); color: var(--red); }
  .tag-semi  { background: rgba(57,210,192,0.15); color: var(--cyan); }
  .tag-credit{ background: rgba(188,140,255,0.15); color: var(--purple); }
  .tag-space { background: rgba(88,166,255,0.15); color: var(--accent); }
  .tag-misc  { background: rgba(139,148,158,0.15); color: var(--muted); }
  .section { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 20px; margin-bottom: 16px; }
  .section h2 { color: #fff; font-size: 1.15em; margin-bottom: 12px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }
  .section h3 { color: var(--accent); font-size: 0.95em; margin: 14px 0 6px; }
  .article { margin-bottom: 18px; padding-bottom: 14px; border-bottom: 1px solid rgba(48,54,61,0.5); }
  .article:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
  .article-title { color: #fff; font-weight: 700; font-size: 0.95em; margin-bottom: 4px; }
  .article-title-cn { color: var(--muted); font-size: 0.85em; margin-bottom: 8px; }
  .article p { font-size: 0.9em; margin: 6px 0; }
  .data-point { background: rgba(255,255,255,0.03); padding: 8px 12px; border-radius: 6px; margin: 8px 0; font-size: 0.85em; }
  .data-point .num { color: #fff; font-weight: 700; }
  .implication { background: rgba(88,166,255,0.06); border-left: 3px solid var(--accent); padding: 10px 14px; margin: 10px 0; border-radius: 0 6px 6px 0; font-size: 0.88em; }
  .implication .label { color: var(--accent); font-weight: 700; font-size: 0.8em; text-transform: uppercase; margin-bottom: 4px; }
  .callout { background: rgba(210,153,34,0.08); border: 1px solid rgba(210,153,34,0.3); border-radius: 6px; padding: 16px; margin: 16px 0; }
  .callout-title { color: var(--yellow); font-weight: 700; font-size: 0.95em; margin-bottom: 8px; }
  .callout ul { padding-left: 18px; }
  .callout li { margin: 4px 0; font-size: 0.88em; }
  ul { padding-left: 18px; }
  li { margin: 3px 0; font-size: 0.88em; }
  .stat-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 12px 0; }
  .stat { background: rgba(255,255,255,0.03); padding: 12px; border-radius: 6px; text-align: center; }
  .stat .val { font-size: 1.4em; font-weight: 700; color: #fff; }
  .stat .lbl { font-size: 0.72em; color: var(--muted); margin-top: 2px; }
  .toc { background: rgba(88,166,255,0.05); border: 1px solid rgba(88,166,255,0.2); border-radius: 8px; padding: 16px 20px; margin-bottom: 20px; }
  .toc-title { color: var(--accent); font-weight: 700; font-size: 0.9em; margin-bottom: 8px; }
  .toc a { color: var(--accent); text-decoration: none; font-size: 0.88em; }
  .toc a:hover { text-decoration: underline; }
  .toc ol { padding-left: 20px; }
  .toc li { margin: 4px 0; }
  .nav-links { display: flex; justify-content: space-between; margin: 20px 0; font-size: 0.85em; }
  .nav-links a { color: var(--accent); text-decoration: none; }
  .nav-links a:hover { text-decoration: underline; }
  .stat-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 12px 0; }
  .stat { background: rgba(255,255,255,0.03); padding: 12px; border-radius: 6px; text-align: center; }
  .stat .val { font-size: 1.4em; font-weight: 700; color: #fff; }
  .stat .lbl { font-size: 0.72em; color: var(--muted); margin-top: 2px; }
  .footer { text-align: center; color: var(--muted); font-size: 0.75em; margin-top: 32px; padding-top: 16px; border-top: 1px solid var(--border); }"""


# ---------------------------------------------------------------------------
# Claude editorial synthesis prompt
# ---------------------------------------------------------------------------
SYNTHESIS_PROMPT = """\
You are an editorial assistant for a fund management research newsletter targeting finance students in Hong Kong.

You will receive raw Bloomberg research articles grouped by topic. Your job is to synthesize them into a structured newsletter in JSON format.

## Output Format (strict JSON)

```json
{
  "title_zh": "央行困局與全球利率前景",
  "title_en": "Central Bank Dilemma & Global Rate Outlook",
  "sections": [
    {
      "id": "section-anchor",
      "tag_zh": "聯準會",
      "tag_en": "Fed",
      "heading_zh": "鷹派當道，按兵不動",
      "stats": [
        {"val": "3.50-3.75%", "lbl_zh": "聯邦基金利率\\n預計維持不變", "color": ""},
        {"val": "-9.2萬", "lbl_zh": "2月非農就業\\n（初值）", "color": "red"},
        {"val": "~3%", "lbl_zh": "3月CPI預測\\n（受油價推升）", "color": "orange"}
      ],
      "articles": [
        {
          "title": "聯儲會料按兵不動 — 利率路徑面臨雙向風險",
          "summary_zh": "FOMC預計在3月會議上維持利率在 **3.50%-3.75%** 不變。會後聲明將承認...",
          "data_points": "預計異議票：**Milan、Waller**（主張降息） | SEP中位數：**今年仍降息25bp** | 通膨見頂預期：**5月**",
          "implication_zh": "Fed上半年按兵不動的概率極高。下半年降息路徑仍在 — **做多前端利率期貨**。"
        }
      ]
    }
  ],
  "fund_manager_takeaways": [
    "<strong>聯準會：</strong>上半年按兵不動。PCE通膨預計5月見頂。做多前端利率期貨。",
    "<strong>日銀：</strong>3月持有0.75%，但4月加息概率高。"
  ]
}
```

## Rules

1. **Language**: Write primarily in Traditional Chinese (繁體中文). Use English for proper nouns, tickers, and technical terms.
2. **Stat grids**: Extract 3 key numbers per section. Use color "red" for negative/risk, "orange" for warning, "green" for positive, "" for neutral.
3. **Article summaries**: Write 100-150 words of narrative prose per article. Bold key numbers with **double asterisks**. Don't just list facts — tell a story.
4. **Data points**: Structured "label: **value**" pairs separated by " | ". Extract 2-4 key metrics.
5. **Investment implications**: Actionable advice for fund managers. Be specific (e.g., "做多前端利率期貨", "減持日圓套利"). Bold the action.
6. **Fund manager takeaways**: 3-6 bullet points covering all sections. Each starts with a bold category label followed by colon. Mix facts + actions.
7. **Sections**: Group related articles into 3-5 sections. Each section has a short punchy Chinese heading.
8. **Don't invent data**: Only use numbers and facts from the source articles.
9. Output ONLY the JSON, no markdown fences, no explanation.

## Source Articles

"""


def _date_label() -> str:
    now = datetime.now(HKT)
    return f"{now.year}年{now.month}月{now.day}日"


def _month_label() -> str:
    now = datetime.now(HKT)
    months_zh = {1:"一月",2:"二月",3:"三月",4:"四月",5:"五月",6:"六月",
                 7:"七月",8:"八月",9:"九月",10:"十月",11:"十一月",12:"十二月"}
    period = "上旬" if now.day <= 10 else ("中旬" if now.day <= 20 else "下旬")
    return f"{now.year}年{months_zh[now.month]}{period}"


def _slug(topics: list[str]) -> str:
    if not topics:
        return "misc"
    return "_".join(topics[:3])


# ---------------------------------------------------------------------------
# Article grouping (reused from before)
# ---------------------------------------------------------------------------
def _group_articles(state: dict) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for fname, info in state["processedFiles"].items():
        if info.get("newsletterNumber") is not None:
            continue
        md_path = Path(info["mdPath"])
        if not md_path.exists():
            continue
        topics = info.get("topics") or ["uncategorized"]
        primary = topics[0]
        entry = {
            "filename": fname,
            "mdPath": str(md_path),
            "topics": topics,
            "title": _title_from_md(md_path),
        }
        groups.setdefault(primary, []).append(entry)
    return groups


def _title_from_md(md_path: Path) -> str:
    try:
        text = md_path.read_text(encoding="utf-8")
        m = re.match(r"^#\s+(.+)$", text, re.MULTILINE)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    return md_path.stem


def _merge_small_groups(
    groups: dict[str, list[dict]], min_size: int = 3
) -> list[tuple[list[str], list[dict]]]:
    affinity = {
        "rates": {"japan", "inflation", "policy", "credit"},
        "japan": {"rates", "inflation", "policy"},
        "china": {"trade", "growth", "credit"},
        "trade": {"china", "policy", "growth"},
        "geopolitics": {"oil", "volatility"},
        "oil": {"geopolitics", "metals"},
        "metals": {"oil", "china", "growth"},
        "growth": {"china", "trade", "valuations"},
    }
    used: set[str] = set()
    newsletters: list[tuple[list[str], list[dict]]] = []
    sorted_topics = sorted(groups.keys(), key=lambda t: len(groups[t]), reverse=True)

    for topic in sorted_topics:
        if topic in used:
            continue
        articles = list(groups[topic])
        merged_topics = [topic]
        used.add(topic)
        if len(articles) < min_size:
            for related in affinity.get(topic, set()):
                if related in groups and related not in used:
                    articles.extend(groups[related])
                    merged_topics.append(related)
                    used.add(related)
                    if len(articles) >= min_size:
                        break
        newsletters.append((merged_topics, articles))
    return newsletters


# ---------------------------------------------------------------------------
# Claude synthesis
# ---------------------------------------------------------------------------
def _read_article_text(md_path: str, max_chars: int = 3000) -> str:
    """Read article markdown, truncated to max_chars."""
    try:
        text = Path(md_path).read_text(encoding="utf-8")
        # Skip the header block
        parts = text.split("---", 2)
        body = parts[2] if len(parts) >= 3 else text
        return body.strip()[:max_chars]
    except Exception:
        return ""


def _build_prompt(topics: list[str], articles: list[dict]) -> str:
    """Build the full prompt with article content for Claude."""
    prompt = SYNTHESIS_PROMPT

    # For large groups, reduce per-article text to fit context
    max_chars_per_article = 3000
    if len(articles) > 15:
        max_chars_per_article = 1500
    elif len(articles) > 30:
        max_chars_per_article = 800

    # Group articles by topic for the prompt
    by_topic: dict[str, list[dict]] = {}
    for a in articles:
        primary = a["topics"][0] if a.get("topics") else "uncategorized"
        by_topic.setdefault(primary, []).append(a)

    for topic, arts in by_topic.items():
        meta = TOPIC_META.get(topic, DEFAULT_META)
        prompt += f"\n### Topic: {meta[1]} ({meta[0]})\n\n"
        for a in arts:
            body = _read_article_text(a["mdPath"], max_chars=max_chars_per_article)
            prompt += f"#### {a['title']}\n{body}\n\n---\n\n"

    return prompt


def _parse_claude_json(output: str) -> dict | None:
    """Parse JSON from Claude CLI or SDK output."""
    # claude --output-format json wraps in {"result": "...", ...}
    try:
        wrapper = json.loads(output)
        raw_text = wrapper.get("result", output)
    except json.JSONDecodeError:
        raw_text = output

    # Extract JSON from the response
    json_match = re.search(r"\{[\s\S]*\}", raw_text)
    if not json_match:
        return None
    try:
        return json.loads(json_match.group())
    except json.JSONDecodeError:
        return None


def synthesize_with_claude(topics: list[str], articles: list[dict]) -> dict | None:
    """Call Claude to synthesize articles into structured editorial content."""
    prompt = _build_prompt(topics, articles)

    # Try claude CLI (non-interactive) — pipe prompt via stdin to avoid
    # Windows command-line length limits
    try:
        print(f"  [CLAUDE] Synthesizing {len(articles)} articles ({len(prompt)} chars)...")
        result = subprocess.run(
            ["claude", "-p", "--output-format", "json"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=300,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            print(f"  [CLAUDE ERR] rc={result.returncode}: {result.stderr[:300]}")
            return None

        parsed = _parse_claude_json(result.stdout.strip())
        if not parsed:
            print(f"  [CLAUDE ERR] No valid JSON found in response")
            return None
        return parsed

    except FileNotFoundError:
        print("  [CLAUDE] 'claude' CLI not found, trying Anthropic SDK...")
        return _synthesize_with_sdk(prompt)
    except subprocess.TimeoutExpired:
        print("  [CLAUDE ERR] Timeout after 300s")
        return None
    except Exception as e:
        print(f"  [CLAUDE ERR] {e}")
        return None


def _synthesize_with_sdk(prompt: str) -> dict | None:
    """Fallback: use Anthropic SDK if available."""
    try:
        import anthropic
        client = anthropic.Anthropic()  # uses ANTHROPIC_API_KEY env var
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = message.content[0].text
        json_match = re.search(r"\{[\s\S]*\}", raw_text)
        if json_match:
            return json.loads(json_match.group())
        return None
    except ImportError:
        print("  [ERR] Neither 'claude' CLI nor anthropic SDK available.")
        return None
    except Exception as e:
        print(f"  [SDK ERR] {e}")
        return None


# ---------------------------------------------------------------------------
# HTML rendering from synthesized content
# ---------------------------------------------------------------------------
def _bold_to_html(text: str) -> str:
    """Convert **bold** markdown to <span> with white bold styling."""
    return re.sub(
        r"\*\*(.+?)\*\*",
        r'<span style="color:#fff;font-weight:700">\1</span>',
        text,
    )


def _render_section_html(section: dict, topics: list[str]) -> str:
    """Render a section from synthesized JSON."""
    section_id = section.get("id", "section")
    tag_zh = section.get("tag_zh", "")
    tag_en = section.get("tag_en", "")
    heading = section.get("heading_zh", tag_en)

    # Find matching CSS class
    css_class = "tag-misc"
    for topic in topics:
        if topic in TOPIC_META:
            meta = TOPIC_META[topic]
            # Match by Chinese or English name
            if meta[0] == tag_zh or meta[1].lower() == tag_en.lower():
                css_class = meta[2]
                break
    # Fallback: try matching tag_en directly
    if css_class == "tag-misc":
        for k, v in TOPIC_META.items():
            if v[0] == tag_zh or v[1].lower() == tag_en.lower() or k == tag_en.lower():
                css_class = v[2]
                break

    # Stat grid
    stats_html = ""
    stats = section.get("stats") or []
    if stats:
        stat_items = ""
        for s in stats[:3]:
            color = s.get("color", "")
            style = f' style="color:var(--{color})"' if color else ""
            lbl = s.get("lbl_zh", "").replace("\\n", "<br>")
            stat_items += f'    <div class="stat"><div class="val"{style}>{html_mod.escape(s.get("val", ""))}</div><div class="lbl">{lbl}</div></div>\n'
        stats_html = f'\n  <div class="stat-grid">\n{stat_items}  </div>\n'

    # Articles
    articles_html = ""
    for a in section.get("articles", []):
        title = html_mod.escape(a.get("title", ""))
        summary = _bold_to_html(html_mod.escape(a.get("summary_zh", "")))

        dp_html = ""
        dp = a.get("data_points", "")
        if dp:
            # Convert **bold** in data points
            dp_formatted = _bold_to_html(html_mod.escape(dp))
            dp_formatted = dp_formatted.replace(" | ", " &nbsp;|&nbsp; ")
            dp_html = f'\n    <div class="data-point">{dp_formatted}</div>'

        impl_html = ""
        impl = a.get("implication_zh", "")
        if impl:
            impl_formatted = _bold_to_html(html_mod.escape(impl))
            impl_html = f'\n    <div class="implication"><div class="label">投資啟示</div>{impl_formatted}</div>'

        articles_html += f"""\
  <div class="article">
    <div class="article-title">{title}</div>
    <p>{summary}</p>{dp_html}{impl_html}
  </div>
"""

    return f"""\
<div class="section" id="{section_id}">
  <h2><span class="tag {css_class}">{tag_zh}</span> {heading}</h2>
{stats_html}
{articles_html}</div>"""


def render_newsletter_html(
    number: int,
    synthesized: dict,
    topics: list[str],
    prev_newsletter: str | None = None,
) -> str:
    """Render the full newsletter HTML from synthesized editorial content."""
    title_zh = synthesized.get("title_zh", "研究摘要")
    title_en = synthesized.get("title_en", "Research Summary")

    # TOC
    toc_items = ""
    sections = synthesized.get("sections", [])
    for s in sections:
        sid = s.get("id", "section")
        label = s.get("tag_zh", "") + " " + s.get("heading_zh", "")
        toc_items += f'    <li><a href="#{sid}">{label}</a></li>\n'

    # Sections HTML
    sections_html = "\n\n".join(
        _render_section_html(s, topics) for s in sections
    )

    # Fund manager takeaways
    takeaways = synthesized.get("fund_manager_takeaways", [])
    takeaways_html = ""
    if takeaways:
        items = "\n".join(f"    <li>{t}</li>" for t in takeaways)
        takeaways_html = f"""\
<div class="callout" id="takeaways">
  <div class="callout-title">基金經理人重點摘要</div>
  <ul>
{items}
  </ul>
</div>"""

    # Nav
    prev_link = f'<span><a href="{prev_newsletter}">&larr; 前期</a></span>' if prev_newsletter else "<span></span>"
    date_label = _date_label()
    month_label = _month_label()

    return f"""\
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>彭博研究摘要 #{number} — {title_zh}</title>
<style>
{NEWSLETTER_CSS}
</style>
<script>if(window.self===window.top&&sessionStorage.getItem("student_auth")!=="1"){document.body.innerHTML="";window.location.replace("student.html");}</script>
</head>
<body>

<h1>彭博研究摘要</h1>
<p class="subtitle">第{number}期 | {title_zh}</p>
<span class="issue-badge">{month_label}更新</span>

<div class="nav-links">
  {prev_link}
  <span><a href="student.html">返回目錄 &rarr;</a></span>
</div>

<div class="toc">
  <div class="toc-title">目錄</div>
  <ol>
{toc_items}    <li><a href="#takeaways">基金經理人重點摘要</a></li>
  </ol>
</div>

{sections_html}

{takeaways_html}

<div class="nav-links">
  {prev_link}
  <span><a href="student.html">返回目錄 &rarr;</a></span>
</div>

<div class="footer">
  彭博研究摘要 | 僅供教學與討論用途 | {date_label}<br>
  資料來源：Bloomberg Intelligence, Bloomberg Economics, Bloomberg News
</div>

</body>
</html>"""


# ---------------------------------------------------------------------------
# Student portal update
# ---------------------------------------------------------------------------
def update_student_portal(
    number: int,
    filename: str,
    title_zh: str,
    topics: list[str],
    article_count: int,
) -> None:
    from bs4 import BeautifulSoup

    html_text = STUDENT_HTML.read_text(encoding="utf-8")
    soup = BeautifulSoup(html_text, "html.parser")

    footer = soup.find("div", class_="footer")
    if not footer:
        print("[WARN] Could not find footer in student.html")
        return

    icon = CARD_ICONS[(number - 1) % len(CARD_ICONS)]
    date_label = _date_label()

    tags_html = ""
    for t in topics[:4]:
        meta = TOPIC_META.get(t, DEFAULT_META)
        tags_html += f'<span class="tag {meta[2]}">{meta[0]}</span>\n    '

    card_html = f"""\
<a class="card" href="{filename}">
  <div class="card-header">
    <span class="card-icon">{icon}</span>
    <span class="card-title">第{number}期 — {title_zh}</span>
    <span class="card-date">{date_label}</span>
  </div>
  <div class="card-desc">
    {tags_html}<br>
    {article_count} articles
  </div>
</a>
"""
    new_card = BeautifulSoup(card_html, "html.parser")
    footer.insert_before(new_card)
    footer.insert_before("\n")

    STUDENT_HTML.write_text(str(soup), encoding="utf-8")
    print(f"[OK] Updated student.html with newsletter #{number}")


# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------
def build(dry_run: bool = False) -> list[dict]:
    state = read_state()
    groups = _group_articles(state)

    total_unprocessed = sum(len(v) for v in groups.values())
    print(f"Unprocessed articles: {total_unprocessed} across {len(groups)} topics")

    if total_unprocessed < MIN_ARTICLES:
        print(f"Below minimum threshold ({MIN_ARTICLES}), skipping.")
        return []

    merged = _merge_small_groups(groups, min_size=MIN_ARTICLES)
    generated = []
    number = state["lastNewsletterNumber"]

    prev_newsletter = None
    if state.get("newsletters"):
        last_num = str(number)
        if last_num in state["newsletters"]:
            prev_newsletter = state["newsletters"][last_num]["filename"]

    for topics, articles in merged:
        if len(articles) < MIN_ARTICLES:
            print(f"  Skipping {topics}: only {len(articles)} articles")
            continue

        number += 1
        slug = _slug(topics)
        filename = f"newsletter_{number}_{slug}.html"
        out_path = OUTPUT_DIR / filename

        if dry_run:
            print(f"  [DRY-RUN] Would generate {filename}: {len(articles)} articles, topics={topics}")
            continue

        # Claude editorial synthesis
        synthesized = synthesize_with_claude(topics, articles)
        if not synthesized:
            print(f"  [SKIP] Claude synthesis failed for {topics}, skipping")
            continue

        html_content = render_newsletter_html(number, synthesized, topics, prev_newsletter)
        out_path.write_text(html_content, encoding="utf-8")
        print(f"  [OK] Generated {filename}: {len(articles)} articles")

        title_zh = synthesized.get("title_zh", "研究摘要")

        state["newsletters"][str(number)] = {
            "filename": filename,
            "generatedAt": now_hkt_iso(),
            "articleCount": len(articles),
            "topics": topics,
        }
        for a in articles:
            fname = a["filename"]
            if fname in state["processedFiles"]:
                state["processedFiles"][fname]["newsletterNumber"] = number

        update_student_portal(number, filename, title_zh, topics, len(articles))

        generated.append({
            "number": number,
            "filename": filename,
            "articles": len(articles),
            "topics": topics,
        })
        prev_newsletter = filename

    if not dry_run and generated:
        state["lastNewsletterNumber"] = number
        write_state(state)

    print(f"\nTotal newsletters generated: {len(generated)}")
    return generated


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build Bloomberg newsletters with Claude editorial synthesis")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    build(dry_run=args.dry_run)
