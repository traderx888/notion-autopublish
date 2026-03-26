"""Bloomberg Weekly Digest — Sunday summary of past 7 days.

Uses Claude to synthesize a "Week in Review" editorial newsletter
from all articles processed in the last 7 days.
"""
from __future__ import annotations

import html as html_mod
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Fix Windows cp950 encoding
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from tools.bloomberg_pdf_convert import (
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
    _title_from_md,
    _date_label,
    _read_article_text,
    synthesize_with_claude,
    _render_section_html,
    _bold_to_html,
)


def _iso_to_dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _week_label() -> str:
    now = datetime.now(HKT)
    iso_cal = now.isocalendar()
    return f"{iso_cal[0]}-W{iso_cal[1]:02d}"


def _collect_recent_articles(state: dict, days: int = 7) -> dict[str, list[dict]]:
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


# ---------------------------------------------------------------------------
# Weekly digest synthesis prompt
# ---------------------------------------------------------------------------
DIGEST_PROMPT = """\
You are an editorial assistant for a fund management weekly digest targeting finance students in Hong Kong.

You will receive Bloomberg research articles from the past week grouped by topic. Synthesize them into a concise weekly digest in JSON format.

## Output Format (strict JSON)

```json
{
  "title_zh": "本週市場回顧",
  "title_en": "Week in Review",
  "sections": [
    {
      "id": "section-anchor",
      "tag_zh": "利率",
      "tag_en": "Rates",
      "heading_zh": "央行政策與利率走向",
      "stats": [
        {"val": "3.50%", "lbl_zh": "Fed利率\\n維持不變", "color": ""},
        {"val": "+0.25%", "lbl_zh": "BOJ加息\\n4月預期", "color": "red"}
      ],
      "articles": [
        {
          "title": "本週利率焦點",
          "summary_zh": "本週三大央行政策動態：聯準會按兵不動，日銀... **關鍵數據**突出顯示。",
          "data_points": "Fed利率：**3.50-3.75%** | BOJ下次決議：**4月** | ECB通膨目標：**2%**",
          "implication_zh": "利率前端仍有空間。**關注4月BOJ決議**。"
        }
      ]
    }
  ],
  "fund_manager_takeaways": [
    "<strong>本週最重要：</strong>概述要點。",
    "<strong>利率：</strong>要點與行動建議。",
    "<strong>下週關注：</strong>即將到來的事件。"
  ]
}
```

## Rules

1. **This is a WEEKLY DIGEST** — condense each topic into 1-2 synthesized articles (not one per source article). Merge related information.
2. **Language**: Traditional Chinese (繁體中文). English for proper nouns, tickers, technical terms.
3. **Stat grids**: 2-3 key numbers per section. Color: "red" negative, "orange" warning, "green" positive, "" neutral.
4. **Summaries**: 100-200 words per synthesized article. **Bold** key numbers. Tell the story of the week.
5. **Data points**: Key metrics with " | " separators.
6. **Implications**: Actionable and specific.
7. **Fund manager takeaways**: 4-6 bullets. Always include "下週關注" as the last bullet.
8. **Don't invent data**: Only use facts from source articles.
9. Output ONLY the JSON, no markdown fences, no explanation.

## This Week's Articles

"""


def _build_digest_prompt(groups: dict[str, list[dict]]) -> str:
    prompt = DIGEST_PROMPT
    for topic, articles in sorted(groups.items(), key=lambda x: -len(x[1])):
        meta = TOPIC_META.get(topic, DEFAULT_META)
        prompt += f"\n### Topic: {meta[1]} ({meta[0]}) — {len(articles)} articles\n\n"
        for a in articles:
            body = _read_article_text(a["mdPath"], max_chars=2000)
            prompt += f"#### {a['title']}\n{body}\n\n---\n\n"
    return prompt


def _synthesize_digest(groups: dict[str, list[dict]]) -> dict | None:
    """Use Claude to synthesize the weekly digest."""
    all_articles = [a for arts in groups.values() for a in arts]
    topics = list(groups.keys())
    prompt = _build_digest_prompt(groups)

    from tools.bloomberg_newsletter_build import _parse_claude_json
    import subprocess
    try:
        print(f"  [CLAUDE] Synthesizing weekly digest: {len(all_articles)} articles across {len(topics)} topics ({len(prompt)} chars)...")
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
            print(f"  [CLAUDE ERR] rc={result.returncode}")
            return None

        parsed = _parse_claude_json(result.stdout.strip())
        if parsed:
            return parsed
        print("  [CLAUDE ERR] No valid JSON in response")
        return None
    except FileNotFoundError:
        # Fallback to SDK
        try:
            import anthropic
            client = anthropic.Anthropic()
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8000,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = message.content[0].text
            json_match = re.search(r"\{[\s\S]*\}", raw_text)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            print(f"  [ERR] {e}")
        return None
    except Exception as e:
        print(f"  [CLAUDE ERR] {e}")
        return None


def render_digest_html(week_label: str, synthesized: dict) -> str:
    """Render digest HTML from Claude-synthesized content."""
    title_zh = synthesized.get("title_zh", "本週市場回顧")
    title_en = synthesized.get("title_en", "Week in Review")
    sections = synthesized.get("sections", [])
    date_label = _date_label()

    # TOC
    toc_items = ""
    for s in sections:
        sid = s.get("id", "section")
        label = s.get("tag_zh", "") + " " + s.get("heading_zh", "")
        toc_items += f'    <li><a href="#{sid}">{label}</a></li>\n'

    # Sections
    topics_all = [s.get("tag_en", "").lower() for s in sections]
    sections_html = "\n\n".join(
        _render_section_html(s, topics_all) for s in sections
    )

    # Takeaways
    takeaways = synthesized.get("fund_manager_takeaways", [])
    takeaways_html = ""
    if takeaways:
        items = "\n".join(f"    <li>{t}</li>" for t in takeaways)
        takeaways_html = f"""\
<div class="callout" id="takeaways">
  <div class="callout-title">基金經理人本週重點摘要</div>
  <ul>
{items}
  </ul>
</div>"""

    return f"""\
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>彭博週報 {week_label} — {title_zh}</title>
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
<p class="subtitle">{week_label} | {title_zh}</p>
<span class="issue-badge">{date_label} 週報</span>

<div class="nav-links">
  <span></span>
  <span><a href="student.html">返回目錄 &rarr;</a></span>
</div>

<div class="toc">
  <div class="toc-title">本週主題 Topics This Week</div>
  <ol>
{toc_items}    <li><a href="#takeaways">基金經理人重點摘要</a></li>
  </ol>
</div>

{sections_html}

{takeaways_html}

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


def _update_student_portal_digest(week_label: str, filename: str, title_zh: str, total: int) -> None:
    from bs4 import BeautifulSoup

    html_text = STUDENT_HTML.read_text(encoding="utf-8")
    soup = BeautifulSoup(html_text, "html.parser")

    footer = soup.find("div", class_="footer")
    if not footer:
        print("[WARN] Could not find footer in student.html")
        return

    # Check for existing WEEKLY DIGESTS label
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
    <span class="card-title">週報 {week_label} — {title_zh}</span>
    <span class="card-date">{date_label}</span>
  </div>
  <div class="card-desc">
    <span class="tag tag-rates">週報</span><br>
    {total} articles — Week in Review
  </div>
</a>
"""
    new_card = BeautifulSoup(card_html, "html.parser")

    if not digest_label:
        label_html = '<div class="section-label">週報 WEEKLY DIGESTS</div>\n'
        label_el = BeautifulSoup(label_html, "html.parser")
        footer.insert_before(label_el)
        footer.insert_before("\n")

    footer.insert_before(new_card)
    footer.insert_before("\n")

    STUDENT_HTML.write_text(str(soup), encoding="utf-8")
    print(f"[OK] Updated student.html with weekly digest {week_label}")


def build_digest(dry_run: bool = False) -> dict | None:
    state = read_state()
    week_label = _week_label()

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

    # Claude synthesis
    synthesized = _synthesize_digest(groups)
    if not synthesized:
        print("[SKIP] Claude synthesis failed for weekly digest")
        return None

    html_content = render_digest_html(week_label, synthesized)
    out_path.write_text(html_content, encoding="utf-8")
    print(f"[OK] Generated {filename}")

    title_zh = synthesized.get("title_zh", "本週市場回顧")

    state.setdefault("weeklyDigests", {})[week_label] = {
        "filename": filename,
        "generatedAt": now_hkt_iso(),
        "articleCount": total,
        "topicCount": len(groups),
    }
    write_state(state)

    _update_student_portal_digest(week_label, filename, title_zh, total)

    return {"week": week_label, "filename": filename, "total": total}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build Bloomberg weekly digest with Claude synthesis")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    build_digest(dry_run=args.dry_run)
