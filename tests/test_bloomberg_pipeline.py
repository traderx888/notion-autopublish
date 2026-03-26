"""Tests for the Bloomberg PDF → Newsletter pipeline."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.bloomberg_pdf_convert import (
    parse_topics,
    title_from_filename,
    strip_disclaimers,
    read_state,
    write_state,
    STATE_PATH,
)


# ---------------------------------------------------------------------------
# Topic parsing
# ---------------------------------------------------------------------------
class TestParseTopics:
    def test_single_tag(self):
        assert parse_topics("BOJ PREVIEW #rates.pdf") == ["rates"]

    def test_multiple_tags(self):
        result = parse_topics("Article #rates #japan #inflation.pdf")
        assert result == ["rates", "japan", "inflation"]

    def test_no_tags(self):
        assert parse_topics("BofAs Hartnett Sees European J.pdf") == []

    def test_chinese_filename_with_tags(self):
        result = parse_topics("中國 3 月 #rates #china.pdf")
        assert result == ["rates", "china"]

    def test_case_insensitive(self):
        # hashtags in filenames are always lowercase, but test mixed case
        result = parse_topics("Article #Growth #CHINA.pdf")
        assert result == ["growth", "china"]


# ---------------------------------------------------------------------------
# Title extraction
# ---------------------------------------------------------------------------
class TestTitleFromFilename:
    def test_basic(self):
        assert title_from_filename("BOJ PREVIEW Hold Likely Watch #rates #japan.pdf") == "BOJ PREVIEW Hold Likely Watch"

    def test_removes_trailing_parens(self):
        assert title_from_filename("Article Title (1).pdf") == "Article Title"

    def test_no_tags(self):
        assert title_from_filename("Simple Article Name.pdf") == "Simple Article Name"


# ---------------------------------------------------------------------------
# Disclaimer stripping
# ---------------------------------------------------------------------------
class TestStripDisclaimers:
    def test_strips_exclusive_use(self):
        text = "This document is being provided for the exclusive use of JEFF WONG at WAI MING WONG. Not for redistribution.\n\nActual content here."
        result = strip_disclaimers(text)
        assert "exclusive use" not in result
        assert "Actual content here" in result

    def test_strips_printed_on(self):
        text = "Some content\nPrinted on 02/04/2026\nMore content"
        result = strip_disclaimers(text)
        assert "Printed on" not in result
        assert "Some content" in result

    def test_strips_page_numbers(self):
        text = "Content\nPage 1 of 8\nMore content"
        result = strip_disclaimers(text)
        assert "Page 1 of 8" not in result

    def test_strips_news_story_header(self):
        text = "Bloomberg\n\nNews Story\n\nActual article"
        result = strip_disclaimers(text)
        assert "News Story" not in result

    def test_preserves_real_content(self):
        text = "China's export engine continues to hum. That backs our assessment."
        assert strip_disclaimers(text) == text


# ---------------------------------------------------------------------------
# State file roundtrip
# ---------------------------------------------------------------------------
class TestStateRoundtrip:
    def test_read_default(self, tmp_path, monkeypatch):
        fake_path = tmp_path / "state.json"
        monkeypatch.setattr("tools.bloomberg_pdf_convert.STATE_PATH", fake_path)
        state = read_state()
        assert state["lastNewsletterNumber"] == 5
        assert state["processedFiles"] == {}

    def test_write_and_read(self, tmp_path, monkeypatch):
        fake_path = tmp_path / "ops" / "state.json"
        monkeypatch.setattr("tools.bloomberg_pdf_convert.STATE_PATH", fake_path)
        state = {
            "lastRunAt": "2026-03-26T10:00:00+08:00",
            "lastNewsletterNumber": 7,
            "processedFiles": {"test.pdf": {"processedAt": "2026-03-26T10:00:00+08:00"}},
            "newsletters": {},
            "weeklyDigests": {},
        }
        write_state(state)
        loaded = json.loads(fake_path.read_text(encoding="utf-8"))
        assert loaded["lastNewsletterNumber"] == 7
        assert "test.pdf" in loaded["processedFiles"]


# ---------------------------------------------------------------------------
# Newsletter HTML structure
# ---------------------------------------------------------------------------
class TestNewsletterHtml:
    def test_html_has_required_elements(self):
        from tools.bloomberg_newsletter_build import render_newsletter_html

        articles = [
            {"filename": "test1.pdf", "mdPath": "", "topics": ["rates"], "title": "Test Article 1"},
            {"filename": "test2.pdf", "mdPath": "", "topics": ["rates"], "title": "Test Article 2"},
            {"filename": "test3.pdf", "mdPath": "", "topics": ["china"], "title": "Test Article 3"},
        ]
        html = render_newsletter_html(6, ["rates", "china"], articles)
        assert "<!DOCTYPE html>" in html
        assert "彭博研究摘要" in html
        assert 'class="toc"' in html
        assert 'class="section"' in html
        assert 'class="nav-links"' in html
        assert 'class="footer"' in html
        assert "student.html" in html
        assert "第6期" in html

    def test_html_contains_article_titles(self):
        from tools.bloomberg_newsletter_build import render_newsletter_html

        articles = [
            {"filename": "t.pdf", "mdPath": "", "topics": ["rates"], "title": "Fed Holds Rate Steady"},
        ]
        html = render_newsletter_html(7, ["rates"], articles)
        assert "Fed Holds Rate Steady" in html


# ---------------------------------------------------------------------------
# Student portal card insertion
# ---------------------------------------------------------------------------
class TestStudentPortal:
    def test_card_insertion(self, tmp_path, monkeypatch):
        from tools import bloomberg_newsletter_build as bnb

        # Create a minimal student.html
        portal = tmp_path / "student.html"
        portal.write_text(
            '<!DOCTYPE html><html><body>'
            '<div class="section-label">NEWSLETTERS</div>'
            '<div class="footer">Footer</div>'
            '</body></html>',
            encoding="utf-8",
        )
        monkeypatch.setattr(bnb, "STUDENT_HTML", portal)

        bnb.update_student_portal(6, "newsletter_6_rates.html", ["rates"], 5)

        result = portal.read_text(encoding="utf-8")
        assert "newsletter_6_rates.html" in result
        assert "第6期" in result
        assert "Footer" in result  # footer preserved


# ---------------------------------------------------------------------------
# Weekly digest date range
# ---------------------------------------------------------------------------
class TestWeeklyDigest:
    def test_collect_filters_by_date(self, monkeypatch):
        from tools.bloomberg_weekly_digest import _collect_recent_articles, HKT
        from datetime import datetime, timedelta

        now = datetime.now(HKT)
        recent = (now - timedelta(days=2)).isoformat(timespec="seconds")
        old = (now - timedelta(days=10)).isoformat(timespec="seconds")

        # Create temp md files
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("# Recent Article\n\nContent here")
            recent_md = f.name

        state = {
            "processedFiles": {
                "recent.pdf": {"processedAt": recent, "mdPath": recent_md, "topics": ["rates"]},
                "old.pdf": {"processedAt": old, "mdPath": recent_md, "topics": ["china"]},
            }
        }

        groups = _collect_recent_articles(state, days=7)
        # Should include recent but not old
        all_fnames = [a["filename"] for arts in groups.values() for a in arts]
        assert "recent.pdf" in all_fnames
        assert "old.pdf" not in all_fnames

        Path(recent_md).unlink(missing_ok=True)
