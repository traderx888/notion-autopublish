"""Bloomberg Newsletter Builder.

Reads unprocessed markdown articles from state, groups by topic,
generates a newsletter HTML (dark-theme, bilingual), and updates
the student portal (output/student.html).

Continues newsletter numbering from the last issued number in state.
"""
from __future__ import annotations

import json
import re
import sys
import html as html_mod
from datetime import datetime, timezone, timedelta
from pathlib import Path
from textwrap import shorten

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.bloomberg_pdf_convert import (
    STATE_PATH,
    read_state,
    write_state,
    now_hkt_iso,
    HKT,
)

OUTPUT_DIR = REPO_ROOT / "output"
STUDENT_HTML = OUTPUT_DIR / "student.html"
MIN_ARTICLES = 3  # minimum to generate a newsletter

# ---------------------------------------------------------------------------
# Topic metadata: slug → (display_zh, display_en, css_class, icon)
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

# Icons to cycle through for newsletter cards
CARD_ICONS = ["&#128202;", "&#127975;", "&#128165;", "&#128176;", "&#127760;", "&#9889;", "&#128293;", "&#128200;"]

# ---------------------------------------------------------------------------
# CSS (extracted from newsletter_5_central_banks_china.html)
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
  .article { margin-bottom: 18px; padding-bottom: 14px; border-bottom: 1px solid rgba(48,54,61,0.5); }
  .article:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
  .article-title { color: #fff; font-weight: 700; font-size: 0.95em; margin-bottom: 4px; }
  .article p { font-size: 0.9em; margin: 6px 0; }
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
# Helpers
# ---------------------------------------------------------------------------
def _slug(topics: list[str]) -> str:
    """Generate a filename slug from a list of topics."""
    if not topics:
        return "misc"
    return "_".join(topics[:3])


def _excerpt(md_text: str, max_chars: int = 400) -> str:
    """Extract a readable excerpt from markdown text (after the header)."""
    # Skip the header block (title, tags, source, ---)
    parts = md_text.split("---", 2)
    body = parts[2] if len(parts) >= 3 else md_text
    # Take first meaningful paragraph
    paragraphs = [p.strip() for p in body.strip().split("\n\n") if p.strip()]
    for para in paragraphs[:3]:
        # Skip very short lines (likely metadata)
        if len(para) > 60:
            return shorten(para, width=max_chars, placeholder="...")
    return shorten(body[:max_chars], width=max_chars, placeholder="...")


def _date_label() -> str:
    """Current date in Chinese format for display."""
    now = datetime.now(HKT)
    return f"{now.year}年{now.month}月{now.day}日"


def _month_label() -> str:
    now = datetime.now(HKT)
    months_zh = {1:"一月",2:"二月",3:"三月",4:"四月",5:"五月",6:"六月",
                 7:"七月",8:"八月",9:"九月",10:"十月",11:"十一月",12:"十二月"}
    period = "上旬" if now.day <= 10 else ("中旬" if now.day <= 20 else "下旬")
    return f"{now.year}年{months_zh[now.month]}{period}"


# ---------------------------------------------------------------------------
# Group articles by topic
# ---------------------------------------------------------------------------
def _group_articles(state: dict) -> dict[str, list[dict]]:
    """Group unassigned articles by their primary topic.

    Returns {topic: [{"filename": ..., "mdPath": ..., "topics": [...], "title": ...}]}
    """
    groups: dict[str, list[dict]] = {}
    for fname, info in state["processedFiles"].items():
        if info.get("newsletterNumber") is not None:
            continue  # already in a newsletter
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
    """Read the first H1 from a markdown file."""
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
    """Merge small topic groups into combined newsletters.

    Returns [(topic_list, articles), ...] where each tuple is one newsletter.
    """
    # Affinity map: related topics that merge well together
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

    # Sort topics by article count descending
    sorted_topics = sorted(groups.keys(), key=lambda t: len(groups[t]), reverse=True)

    for topic in sorted_topics:
        if topic in used:
            continue
        articles = list(groups[topic])
        merged_topics = [topic]
        used.add(topic)

        # Try merging related small groups
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
# HTML rendering
# ---------------------------------------------------------------------------
def _render_article_html(article: dict) -> str:
    """Render a single article block."""
    title = html_mod.escape(article["title"])
    md_path = Path(article["mdPath"])
    excerpt = ""
    try:
        text = md_path.read_text(encoding="utf-8")
        excerpt = html_mod.escape(_excerpt(text))
    except Exception:
        pass

    tags_html = ""
    for t in article.get("topics", []):
        meta = TOPIC_META.get(t, DEFAULT_META)
        tags_html += f'<span class="tag {meta[2]}">{meta[0]}</span> '

    return f"""\
  <div class="article">
    <div class="article-title">{title}</div>
    <div style="margin-bottom:6px">{tags_html}</div>
    <p>{excerpt}</p>
  </div>"""


def _render_section_html(topic: str, articles: list[dict]) -> str:
    """Render a topic section with all its articles."""
    meta = TOPIC_META.get(topic, DEFAULT_META)
    zh_name, en_name, css_class, _ = meta
    section_id = topic.replace(" ", "-")

    articles_html = "\n".join(_render_article_html(a) for a in articles)

    return f"""\
<div class="section" id="{section_id}">
  <h2><span class="tag {css_class}">{zh_name}</span> {en_name} ({len(articles)} articles)</h2>
{articles_html}
</div>"""


def render_newsletter_html(
    number: int,
    topics: list[str],
    articles: list[dict],
    prev_newsletter: str | None = None,
) -> str:
    """Render a complete newsletter HTML page."""
    # Group articles by topic for sections
    by_topic: dict[str, list[dict]] = {}
    for a in articles:
        primary = a["topics"][0] if a.get("topics") else "uncategorized"
        by_topic.setdefault(primary, []).append(a)

    # Title
    topic_names_zh = [TOPIC_META.get(t, DEFAULT_META)[0] for t in topics]
    topic_names_en = [TOPIC_META.get(t, DEFAULT_META)[1] for t in topics]
    title_zh = "、".join(topic_names_zh[:3])
    title_en = ", ".join(topic_names_en[:3])
    full_title = f"第{number}期 — {title_zh}"

    # TOC
    toc_items = ""
    for i, topic in enumerate(by_topic.keys(), 1):
        meta = TOPIC_META.get(topic, DEFAULT_META)
        toc_items += f'    <li><a href="#{topic.replace(" ", "-")}">{meta[0]} {meta[1]} &rarr;</a></li>\n'

    # Sections
    sections_html = "\n\n".join(
        _render_section_html(topic, arts) for topic, arts in by_topic.items()
    )

    # Nav links
    prev_link = ""
    if prev_newsletter:
        prev_link = f'<span><a href="{prev_newsletter}">&larr; 前期</a></span>'
    else:
        prev_link = "<span></span>"

    # Stat grid
    stat_items = ""
    for topic in list(by_topic.keys())[:3]:
        meta = TOPIC_META.get(topic, DEFAULT_META)
        count = len(by_topic[topic])
        stat_items += f'    <div class="stat"><div class="val">{count}</div><div class="lbl">{meta[0]}<br>{meta[1]}</div></div>\n'

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
</head>
<body>

<h1>彭博研究摘要</h1>
<p class="subtitle">{full_title} | {title_en}</p>
<span class="issue-badge">{month_label}更新</span>

<div class="nav-links">
  {prev_link}
  <span><a href="student.html">返回目錄 &rarr;</a></span>
</div>

<div class="stat-grid">
{stat_items}</div>

<div class="toc">
  <div class="toc-title">目錄</div>
  <ol>
{toc_items}  </ol>
</div>

{sections_html}

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
    topics: list[str],
    article_count: int,
) -> None:
    """Insert a new newsletter card into student.html before the footer."""
    from bs4 import BeautifulSoup

    html_text = STUDENT_HTML.read_text(encoding="utf-8")
    soup = BeautifulSoup(html_text, "html.parser")

    # Find the footer div
    footer = soup.find("div", class_="footer")
    if not footer:
        print("[WARN] Could not find footer in student.html, skipping portal update")
        return

    # Build card
    topic_names_zh = [TOPIC_META.get(t, DEFAULT_META)[0] for t in topics]
    topic_names_en = [TOPIC_META.get(t, DEFAULT_META)[1] for t in topics]
    title_zh = "、".join(topic_names_zh[:3])
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
    {article_count} articles: {", ".join(topic_names_en[:3])}
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
    """Build newsletters from unprocessed articles. Returns list of generated newsletters."""
    state = read_state()
    groups = _group_articles(state)

    total_unprocessed = sum(len(v) for v in groups.values())
    print(f"Unprocessed articles: {total_unprocessed} across {len(groups)} topics")

    if total_unprocessed < MIN_ARTICLES:
        print(f"Below minimum threshold ({MIN_ARTICLES}), skipping generation.")
        return []

    merged = _merge_small_groups(groups, min_size=MIN_ARTICLES)
    generated = []
    number = state["lastNewsletterNumber"]

    # Find the previous newsletter filename for nav links
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

        html_content = render_newsletter_html(number, topics, articles, prev_newsletter)
        out_path.write_text(html_content, encoding="utf-8")
        print(f"  [OK] Generated {filename}: {len(articles)} articles")

        # Update state
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

        # Update student portal
        update_student_portal(number, filename, topics, len(articles))

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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build Bloomberg newsletters from converted markdown")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()
    build(dry_run=args.dry_run)
