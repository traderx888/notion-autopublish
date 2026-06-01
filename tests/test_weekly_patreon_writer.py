from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import weekly_patreon_writer as writer


def _touch(path: Path, when: str) -> None:
    path.write_text("placeholder", encoding="utf-8")
    stamp = datetime.fromisoformat(when).timestamp()
    os.utime(path, (stamp, stamp))


def test_select_pdf_paths_uses_inclusive_since_exclusive_until(tmp_path: Path) -> None:
    included = tmp_path / "Included #rates.pdf"
    _touch(included, "2026-05-25T00:00:00")
    _touch(tmp_path / "Too old.pdf", "2026-05-24T23:59:59")
    _touch(tmp_path / "Too new.pdf", "2026-06-01T00:00:00")
    _touch(tmp_path / "Ignored.txt", "2026-05-26T12:00:00")

    paths = writer.select_pdf_paths(
        tmp_path,
        writer.parse_date("2026-05-25"),
        writer.parse_date("2026-06-01"),
    )

    assert paths == [included]


def test_render_markdown_groups_articles_and_limits_extract() -> None:
    article = writer.Article(
        source_path=Path("Rates Shock #rates #japan.pdf"),
        title="Rates Shock",
        topics=["rates", "japan"],
        modified_at=datetime(2026, 5, 26, 13, 46),
        text=" ".join(["alpha"] * 30),
    )

    markdown = writer.render_markdown(
        [article],
        root=Path(r"C:\blp\data"),
        since=writer.parse_date("2026-05-25"),
        until=writer.parse_date("2026-06-01"),
        max_article_chars=40,
    )

    assert "# BLP Weekly Bundle 2026-W22" in markdown
    assert "Date range: 2026-05-25 to 2026-06-01 (until exclusive)" in markdown
    assert "Articles: 1" in markdown
    assert "## Rates" in markdown
    assert "### 1. Rates Shock" in markdown
    assert "Tags: #rates #japan" in markdown
    assert "[excerpt truncated]" in markdown
    assert len(markdown) < 1500
