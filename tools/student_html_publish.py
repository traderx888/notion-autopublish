from __future__ import annotations

import argparse
import html
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "output"
STUDENT_HTML = OUTPUT_DIR / "student.html"
HKT = ZoneInfo("Asia/Hong_Kong")

AUTH_SCRIPT = (
    '<script>if(window.self===window.top&&sessionStorage.getItem("student_auth")!=="1")'
    '{document.body.innerHTML="";window.location.replace("student.html");}</script>'
)

NAV_STYLE = """\
<style id="student-portal-nav-style">
  .student-portal-nav { max-width: 800px; margin: 0 auto; padding: 14px 1.2rem 0; font-family: 'Source Sans Pro', 'Segoe UI', sans-serif; }
  .student-portal-nav a { color: #f0d87a; text-decoration: none; font-size: 0.78rem; letter-spacing: 1px; text-transform: uppercase; }
  .student-portal-nav a:hover { color: #ffffff; }
</style>"""

NAV_HTML = '<div class="student-portal-nav"><a href="student.html">&larr; 返回學生目錄</a></div>'


@dataclass(frozen=True)
class PortalTag:
    label: str
    css_class: str = "tag-resource"


def _default_card_date() -> str:
    now = datetime.now(HKT)
    return f"{now.year}年{now.month}月{now.day}日"


def _strip_tags(fragment: str) -> str:
    no_tags = re.sub(r"<[^>]+>", " ", fragment)
    return " ".join(html.unescape(no_tags).split())


def _extract_first(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return _strip_tags(match.group(1)).strip()


def extract_source_metadata(html_text: str, source_path: Path) -> tuple[str, str, str]:
    title = _extract_first(html_text, r"<title>(.*?)</title>") or source_path.stem.replace("_", " ")

    date_match = re.search(r"(\d{4}年\d{1,2}月\d{1,2}日)", html_text)
    card_date = date_match.group(1) if date_match else _default_card_date()

    description = (
        _extract_first(html_text, r'<div[^>]*class="hero-subtitle"[^>]*>(.*?)</div>')
        or _extract_first(html_text, r'<div[^>]*class="masthead-date"[^>]*>(.*?)</div>')
        or title
    )
    return title, card_date, description


def parse_tag_specs(tag_specs: list[str] | None) -> list[PortalTag]:
    tags: list[PortalTag] = []
    for spec in tag_specs or []:
        if ":" in spec:
            label, css_class = spec.split(":", 1)
            tags.append(PortalTag(label=label.strip(), css_class=css_class.strip() or "tag-resource"))
        else:
            tags.append(PortalTag(label=spec.strip()))
    return tags


def ensure_html_filename(name: str) -> str:
    return name if name.lower().endswith(".html") else f"{name}.html"


def inject_student_gate_and_nav(html_text: str) -> str:
    injected = html_text

    head_injections: list[str] = []
    if 'sessionStorage.getItem("student_auth")' not in injected:
        head_injections.append(AUTH_SCRIPT)
    if "student-portal-nav-style" not in injected:
        head_injections.append(NAV_STYLE)

    if head_injections:
        injected, count = re.subn(
            r"</head\s*>",
            "\n" + "\n".join(head_injections) + "\n</head>",
            injected,
            count=1,
            flags=re.IGNORECASE,
        )
        if count == 0:
            raise ValueError("Source HTML is missing a closing </head> tag.")

    if 'href="student.html"' not in injected:
        injected, count = re.subn(
            r"<body([^>]*)>",
            lambda match: f"<body{match.group(1)}>\n{NAV_HTML}\n",
            injected,
            count=1,
            flags=re.IGNORECASE,
        )
        if count == 0:
            raise ValueError("Source HTML is missing an opening <body> tag.")

    return injected


def build_portal_card_html(
    *,
    filename: str,
    title: str,
    card_date: str,
    description: str,
    tags: list[PortalTag],
    icon: str,
    border_color: str,
) -> str:
    tag_html = "\n".join(
        f'<span class="tag {html.escape(tag.css_class)}">{html.escape(tag.label)}</span>'
        for tag in tags
    )
    if not tag_html:
        tag_html = '<span class="tag tag-resource">HTML教材</span>'

    return f"""\
<a class="card" href="{html.escape(filename)}" style="border-color: {html.escape(border_color)};">
<div class="card-header">
<span class="card-icon">{icon}</span>
<span class="card-title">{html.escape(title)}</span>
<span class="card-date">{html.escape(card_date)}</span>
</div>
<div class="card-desc">
{tag_html}<br/>
    {html.escape(description)}
  </div>
</a>"""


def upsert_portal_card(student_html_text: str, card_html: str, filename: str) -> str:
    card_pattern = re.compile(
        rf"\s*<a class=\"card\" href=\"{re.escape(filename)}\".*?</a>\s*",
        flags=re.DOTALL,
    )
    updated = re.sub(card_pattern, "\n", student_html_text)

    insertion_markers = [
        r'(<div class="section-label">[^<]*NEWSLETTERS[^<]*</div>)',
        r'(<div class="footer">)',
    ]

    for marker in insertion_markers:
        updated, count = re.subn(marker, card_html.rstrip() + "\n" + r"\1", updated, count=1)
        if count:
            return updated

    raise ValueError("Could not find a safe insertion point in output/student.html.")


def publish_student_html(
    source_path: Path,
    *,
    output_name: str | None = None,
    title: str | None = None,
    card_date: str | None = None,
    description: str | None = None,
    tag_specs: list[str] | None = None,
    icon: str = "📘",
    border_color: str = "var(--accent)",
) -> dict[str, str]:
    source_text = source_path.read_text(encoding="utf-8")
    detected_title, detected_date, detected_description = extract_source_metadata(source_text, source_path)

    output_filename = ensure_html_filename(output_name or source_path.name)
    published_title = title or detected_title
    published_date = card_date or detected_date
    published_description = description or detected_description
    tags = parse_tag_specs(tag_specs)

    rendered_html = inject_student_gate_and_nav(source_text)
    output_path = OUTPUT_DIR / output_filename
    output_path.write_text(rendered_html, encoding="utf-8")

    student_html_text = STUDENT_HTML.read_text(encoding="utf-8")
    card_html = build_portal_card_html(
        filename=output_filename,
        title=published_title,
        card_date=published_date,
        description=published_description,
        tags=tags,
        icon=icon,
        border_color=border_color,
    )
    STUDENT_HTML.write_text(
        upsert_portal_card(student_html_text, card_html, output_filename),
        encoding="utf-8",
    )

    return {
        "output_path": str(output_path),
        "student_html": str(STUDENT_HTML),
        "title": published_title,
        "date": published_date,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish a standalone HTML issue into the student portal.")
    parser.add_argument("source", help="Path to the source HTML file.")
    parser.add_argument("--output-name", help="Output filename under output/. Defaults to the source filename.")
    parser.add_argument("--title", help="Portal card title override.")
    parser.add_argument("--date", dest="card_date", help="Portal card date override.")
    parser.add_argument("--description", help="Portal card description override.")
    parser.add_argument("--tag", action="append", dest="tag_specs", default=[], help="Portal tag spec in label[:css_class] form.")
    parser.add_argument("--icon", default="📘", help="Portal card icon.")
    parser.add_argument("--border-color", default="var(--accent)", help="Portal card border color.")
    args = parser.parse_args()

    result = publish_student_html(
        Path(args.source),
        output_name=args.output_name,
        title=args.title,
        card_date=args.card_date,
        description=args.description,
        tag_specs=args.tag_specs,
        icon=args.icon,
        border_color=args.border_color,
    )

    print(f"[OK] Published {result['title']} -> {result['output_path']}")
    print(f"[OK] Updated student portal -> {result['student_html']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
