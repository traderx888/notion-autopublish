"""Build a weekly Markdown bundle from Bloomberg PDF exports.

The tool is intentionally read-only with respect to the existing Bloomberg
pipeline state. It selects PDFs from a date window, extracts cleaned text using
the existing converter helpers, and writes a bounded Markdown draft suitable for
review before publishing.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from tools.bloomberg_pdf_convert import (
    extract_pdf_text,
    parse_topics,
    strip_disclaimers,
    title_from_filename,
)

DEFAULT_MAX_ARTICLE_CHARS = 2500

TOPIC_LABELS = {
    "rates": "Rates",
    "china": "China",
    "japan": "Japan",
    "geopolitics": "Geopolitics",
    "oil": "Oil & Energy",
    "trade": "Trade",
    "growth": "Growth",
    "metals": "Metals",
    "inflation": "Inflation",
    "policy": "Policy",
    "valuations": "Valuations",
    "volatility": "Volatility",
    "semiconductor": "Semiconductor",
    "credit": "Credit",
    "space": "Space",
    "uncategorized": "Uncategorized",
}


@dataclass(frozen=True)
class Article:
    source_path: Path
    title: str
    topics: list[str]
    modified_at: datetime
    text: str


@dataclass(frozen=True)
class ExtractionError:
    source_path: Path
    message: str


def parse_date(value: str) -> datetime:
    """Parse a YYYY-MM-DD date as a local midnight datetime."""
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"{value!r} is not a valid YYYY-MM-DD date"
        ) from exc


def select_pdf_paths(root: Path, since: datetime, until: datetime) -> list[Path]:
    """Return PDFs with modified times in [since, until)."""
    if until <= since:
        raise ValueError("--until must be later than --since")
    if not root.exists():
        raise FileNotFoundError(f"source root does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"source root is not a directory: {root}")

    selected = []
    for path in root.glob("*.pdf"):
        modified_at = datetime.fromtimestamp(path.stat().st_mtime)
        if since <= modified_at < until:
            selected.append(path)

    return sorted(
        selected,
        key=lambda item: (datetime.fromtimestamp(item.stat().st_mtime), item.name.lower()),
    )


def extract_article(path: Path) -> Article:
    raw_text = extract_pdf_text(path)
    text = strip_disclaimers(raw_text)
    return Article(
        source_path=path,
        title=title_from_filename(path.name),
        topics=parse_topics(path.name),
        modified_at=datetime.fromtimestamp(path.stat().st_mtime),
        text=text,
    )


def build_articles(paths: Iterable[Path]) -> tuple[list[Article], list[ExtractionError]]:
    articles: list[Article] = []
    errors: list[ExtractionError] = []
    for path in paths:
        try:
            articles.append(extract_article(path))
        except Exception as exc:  # keep processing the rest of the weekly pack
            errors.append(ExtractionError(source_path=path, message=str(exc)))
    return articles, errors


def _week_label(since: datetime) -> str:
    year, week, _ = since.isocalendar()
    return f"{year}-W{week:02d}"


def _topic_key(article: Article) -> str:
    return article.topics[0] if article.topics else "uncategorized"


def _topic_label(topic: str) -> str:
    return TOPIC_LABELS.get(topic, topic.replace("_", " ").title())


def _tags(topics: list[str]) -> str:
    if not topics:
        return "none"
    return " ".join(f"#{topic}" for topic in topics)


def _clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


def _excerpt(text: str, max_chars: int) -> str:
    cleaned = _clean_text(text)
    if not cleaned:
        return "_No extractable text found._"
    if len(cleaned) <= max_chars:
        return cleaned

    excerpt = cleaned[:max_chars].rsplit(" ", 1)[0].rstrip()
    if not excerpt:
        excerpt = cleaned[:max_chars].rstrip()
    return f"{excerpt}\n\n[excerpt truncated]"


def render_markdown(
    articles: list[Article],
    *,
    root: Path,
    since: datetime,
    until: datetime,
    max_article_chars: int = DEFAULT_MAX_ARTICLE_CHARS,
    errors: list[ExtractionError] | None = None,
) -> str:
    """Render the weekly bundle Markdown."""
    errors = errors or []
    generated_at = datetime.now().isoformat(timespec="seconds")
    week_label = _week_label(since)

    grouped: dict[str, list[Article]] = {}
    for article in articles:
        grouped.setdefault(_topic_key(article), []).append(article)

    lines: list[str] = [
        f"# BLP Weekly Bundle {week_label}",
        "",
        f"- Date range: {since.date()} to {until.date()} (until exclusive)",
        f"- Source root: `{root}`",
        f"- Generated: {generated_at}",
        f"- Articles: {len(articles)}",
        f"- Extraction errors: {len(errors)}",
        "",
        "## Topic Map",
        "",
    ]

    if grouped:
        for topic, topic_articles in sorted(
            grouped.items(), key=lambda item: (-len(item[1]), _topic_label(item[0]))
        ):
            lines.append(f"- {_topic_label(topic)}: {len(topic_articles)}")
    else:
        lines.append("- No PDFs matched this date window.")

    lines.extend(["", "## Article Index", ""])
    if articles:
        for index, article in enumerate(articles, start=1):
            modified = article.modified_at.isoformat(sep=" ", timespec="minutes")
            lines.append(
                f"{index}. **{article.title}** ({_tags(article.topics)}) - "
                f"{modified} - `{article.source_path.name}`"
            )
    else:
        lines.append("No articles selected.")

    article_number = 1
    for topic, topic_articles in sorted(
        grouped.items(), key=lambda item: (-len(item[1]), _topic_label(item[0]))
    ):
        lines.extend(["", f"## {_topic_label(topic)}", ""])
        for article in topic_articles:
            modified = article.modified_at.isoformat(sep=" ", timespec="minutes")
            lines.extend(
                [
                    f"### {article_number}. {article.title}",
                    "",
                    f"- Source: `{article.source_path.name}`",
                    f"- Modified: {modified}",
                    f"- Tags: {_tags(article.topics)}",
                    "",
                    "#### Extract",
                    "",
                    _excerpt(article.text, max_article_chars),
                    "",
                ]
            )
            article_number += 1

    if errors:
        lines.extend(["", "## Extraction Errors", ""])
        for error in errors:
            lines.append(f"- `{error.source_path.name}`: {error.message}")

    return "\n".join(lines).rstrip() + "\n"


def write_bundle(
    *,
    root: Path,
    since: datetime,
    until: datetime,
    out_path: Path,
    max_article_chars: int = DEFAULT_MAX_ARTICLE_CHARS,
) -> tuple[int, int]:
    paths = select_pdf_paths(root, since, until)
    articles, errors = build_articles(paths)
    markdown = render_markdown(
        articles,
        root=root,
        since=since,
        until=until,
        max_article_chars=max_article_chars,
        errors=errors,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8")
    return len(articles), len(errors)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a weekly Markdown bundle from Bloomberg PDF exports"
    )
    parser.add_argument("--root", required=True, type=Path, help="Source PDF folder")
    parser.add_argument("--since", required=True, type=parse_date, help="Inclusive YYYY-MM-DD")
    parser.add_argument("--until", required=True, type=parse_date, help="Exclusive YYYY-MM-DD")
    parser.add_argument("--out", required=True, type=Path, help="Output Markdown path")
    parser.add_argument(
        "--max-article-chars",
        type=int,
        default=DEFAULT_MAX_ARTICLE_CHARS,
        help=f"Maximum extracted characters per article (default: {DEFAULT_MAX_ARTICLE_CHARS})",
    )
    args = parser.parse_args(argv)

    if args.max_article_chars < 200:
        parser.error("--max-article-chars must be at least 200")

    try:
        count, errors = write_bundle(
            root=args.root,
            since=args.since,
            until=args.until,
            out_path=args.out,
            max_article_chars=args.max_article_chars,
        )
    except Exception as exc:
        print(f"[ERR] {exc}", file=sys.stderr)
        return 1

    print(f"[OK] Wrote {args.out} ({count} articles, {errors} extraction errors)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
