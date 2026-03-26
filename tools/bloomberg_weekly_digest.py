"""Bloomberg Weekly Digest — Sunday summary of past 7 days.

Generates a condensed "Week in Review" newsletter from all articles
processed in the last 7 days, grouped by topic with first-paragraph
excerpts and a key-themes callout.
"""
from __future__ import annotations

import html as html_mod
import json
import re
import sys
from datetime import datetime, timedelta
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
from tools.bloomberg_newsletter_build import (
    NEWSLETTER_CSS,
    TOPIC_META,
    DEFAULT_META,
    OUTPUT_DIR,
    STUDENT_HTML,
    _excerpt,
    _title_from_md,
    _date_label,
)


def _iso_to_dt(s: str) -> datetime:
    """Parse ISO timestamp to datetime."""
    return datetime.fromisoformat(s)


def _week_label() -> str:
    now = datetime.now(HKT)
    iso_cal = now.isocalendar()
    return f"{iso_cal[0]}-W{iso_cal[1]:02d}"


def _collect_recent_articles(state: dict, days: int = 7) -> dict[str, list[dict]]:
    """Collect articles processed in the last N days, grouped by primary topic."""
    cutoff = datetime.now(HKT) - timedelta(days=days)
    groups: dict[str, list[dict]] = {}

    for fname, info in state["processedFiles"].items():
        processed_at = info.get("processedAt")
        if not processed_at:
            continue
        try:
            dt = _iso_to_dt(processed_at)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=HKT)
        except Exception:
            continue

        if dt < cutoff:
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


def _render_digest_section(topic: str, articles: list[dict]) -> str:
    """Render a condensed topic section for the digest."""
    meta = TOPIC_META.get(topic, DEFAULT_META)
    zh_name, en_name, css_class, _ = meta

    items_html = ""
    for a in articles:
        title = html_mod.escape(a["title"])
        excerpt = ""
        try:
            text = Path(a["mdPath"]).read_text(encoding="utf-8")
            excerpt = html_mod.escape(_excerpt(text, max_chars=200))
        except Exception:
            pass
        items_html += f"""\
  <div class="article">
    <div class="article-title">{title}</div>
    <p>{excerpt}</p>
  </div>
"""

    return f"""\
<div class="section" id="{topic}">
  <h2><span class="tag {css_class}">{zh_name}</span> {en_name} ({len(articles)})</h2>
{items_html}</div>"""


def render_digest_html(
    week_label: str,
    groups: dict[str, list[dict]],
) -> str:
    """Render the weekly digest newsletter."""
    total = sum(len(v) for v in groups.values())
    date_label = _date_label()

    # Stat grid: top 3 topics by article count
    sorted_topics = sorted(groups.keys(), key=lambda t: len(groups[t]), reverse=True)

    stat_items = ""
    for topic in sorted_topics[:3]:
        meta = TOPIC_META.get(topic, DEFAULT_META)
        stat_items += f'    <div class="stat"><div class="val">{len(groups[topic])}</div><div class="lbl">{meta[0]}<br>{meta[1]}</div></div>\n'

    # TOC
    toc_items = ""
    for topic in sorted_topics:
        meta = TOPIC_META.get(topic, DEFAULT_META)
        toc_items += f'    <li><a href="#{topic}">{meta[0]} {meta[1]} ({len(groups[topic])}) &rarr;</a></li>\n'

    # Sections
    sections_html = "\n\n".join(
        _render_digest_section(topic, groups[topic]) for topic in sorted_topics
    )

    # Key themes callout
    themes_html = ""
    for topic in sorted_topics[:5]:
        meta = TOPIC_META.get(topic, DEFAULT_META)
        themes_html += f"    <li><strong>{meta[0]} {meta[1]}:</strong> {len(groups[topic])} articles this week</li>\n"

    return f"""\
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>彭博週報 {week_label} — Week in Review</title>
<style>
{NEWSLETTER_CSS}
  .callout {{ background: rgba(210,153,34,0.08); border: 1px solid rgba(210,153,34,0.3); border-radius: 6px; padding: 16px; margin: 16px 0; }}
  .callout-title {{ color: var(--yellow); font-weight: 700; font-size: 0.95em; margin-bottom: 8px; }}
  .callout ul {{ padding-left: 18px; }}
  .callout li {{ margin: 4px 0; font-size: 0.88em; }}
</style>
</head>
<body>

<h1>彭博週報 Week in Review</h1>
<p class="subtitle">{week_label} | {total} articles across {len(groups)} topics</p>
<span class="issue-badge">{date_label} 週報</span>

<div class="nav-links">
  <span></span>
  <span><a href="student.html">返回目錄 &rarr;</a></span>
</div>

<div class="stat-grid">
{stat_items}</div>

<div class="toc">
  <div class="toc-title">本週主題 Topics This Week</div>
  <ol>
{toc_items}  </ol>
</div>

{sections_html}

<div class="callout">
  <div class="callout-title">本週重點主題 Key Themes This Week</div>
  <ul>
{themes_html}  </ul>
</div>

<div class="nav-links">
  <span></span>
  <span><a href="student.html">返回目錄 &rarr;</a></span>
</div>

<div class="footer">
  彭博週報 | 僅供教學與討論用途 | {date_label}<br>
  資料來源：Bloomberg Intelligence, Bloomberg Economics, Bloomberg News
</div>

</body>
</html>"""


def _update_student_portal_digest(week_label: str, filename: str, total: int, topic_count: int) -> None:
    """Insert a weekly digest card into student.html."""
    from bs4 import BeautifulSoup

    html_text = STUDENT_HTML.read_text(encoding="utf-8")
    soup = BeautifulSoup(html_text, "html.parser")

    footer = soup.find("div", class_="footer")
    if not footer:
        print("[WARN] Could not find footer in student.html")
        return

    # Check if there's already a WEEKLY DIGESTS section label
    digest_label = None
    for el in soup.find_all("div", class_="section-label"):
        if "WEEKLY" in (el.get_text() or "").upper():
            digest_label = el
            break

    date_label = _date_label()

    card_html = f"""\
<a class="card" href="{filename}">
  <div class="card-header">
    <span class="card-icon">&#128214;</span>
    <span class="card-title">週報 {week_label} — Week in Review</span>
    <span class="card-date">{date_label}</span>
  </div>
  <div class="card-desc">
    <span class="tag tag-rates">週報</span><br>
    {total} articles across {topic_count} topics
  </div>
</a>
"""
    new_card = BeautifulSoup(card_html, "html.parser")

    if not digest_label:
        # Create the section label
        label_html = '<div class="section-label">週報 WEEKLY DIGESTS</div>\n'
        label_el = BeautifulSoup(label_html, "html.parser")
        footer.insert_before(label_el)
        footer.insert_before("\n")

    footer.insert_before(new_card)
    footer.insert_before("\n")

    STUDENT_HTML.write_text(str(soup), encoding="utf-8")
    print(f"[OK] Updated student.html with weekly digest {week_label}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def build_digest(dry_run: bool = False) -> dict | None:
    """Build the weekly digest. Returns metadata or None if nothing to digest."""
    state = read_state()
    week_label = _week_label()

    # Check if already generated this week
    if week_label in state.get("weeklyDigests", {}):
        print(f"Weekly digest for {week_label} already exists, skipping.")
        return None

    groups = _collect_recent_articles(state, days=7)
    total = sum(len(v) for v in groups.values())

    if total == 0:
        print("No articles in the last 7 days, skipping digest.")
        return None

    print(f"Weekly digest {week_label}: {total} articles across {len(groups)} topics")

    filename = f"newsletter_digest_{week_label.replace('-', '').lower()}.html"
    out_path = OUTPUT_DIR / filename

    if dry_run:
        print(f"[DRY-RUN] Would generate {filename}")
        return {"week": week_label, "filename": filename, "total": total}

    html_content = render_digest_html(week_label, groups)
    out_path.write_text(html_content, encoding="utf-8")
    print(f"[OK] Generated {filename}")

    # Update state
    state.setdefault("weeklyDigests", {})[week_label] = {
        "filename": filename,
        "generatedAt": now_hkt_iso(),
        "articleCount": total,
        "topicCount": len(groups),
    }
    write_state(state)

    # Update student portal
    _update_student_portal_digest(week_label, filename, total, len(groups))

    return {"week": week_label, "filename": filename, "total": total}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build Bloomberg weekly digest")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    build_digest(dry_run=args.dry_run)
