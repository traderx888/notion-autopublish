"""
Tests for the course-backup orchestration in browser/scrapers/course.py.

The Playwright-driven platform subclasses (course_skool, etc.) are not
exercised here — the contract that needs to be correct under all conditions
is the manifest + diff/sync, which we can stub freely.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

# browser/scrapers/__init__.py imports modules that don't yet exist in this
# tree (pre-existing). Load course.py directly to bypass the package init —
# same pattern as tests/test_agent_note.py.
_REPO = Path(__file__).resolve().parents[1]


def _ensure_playwright_stub():
    """Stub `playwright.sync_api` if Playwright isn't installed.

    The orchestration tests never call into Playwright code paths, but
    `browser.base` imports its symbols at module import time.
    """
    if "playwright.sync_api" in sys.modules:
        return
    try:
        import playwright.sync_api  # noqa: F401
    except ModuleNotFoundError:
        pw = types.ModuleType("playwright")
        sync_api = types.ModuleType("playwright.sync_api")
        sync_api.sync_playwright = lambda: None  # type: ignore[attr-defined]
        sync_api.BrowserContext = object  # type: ignore[attr-defined]
        sync_api.Page = object  # type: ignore[attr-defined]
        sys.modules["playwright"] = pw
        sys.modules["playwright.sync_api"] = sync_api


def _load_course_module() -> types.ModuleType:
    _ensure_playwright_stub()
    # browser/scrapers/__init__.py references modules that don't exist in this
    # tree (pre-existing). Stub the package so the relative import in
    # course.py resolves without executing the init.
    pkg_name = "browser.scrapers"
    if pkg_name not in sys.modules:
        pkg = types.ModuleType(pkg_name)
        pkg.__path__ = [str(_REPO / "browser" / "scrapers")]
        sys.modules[pkg_name] = pkg
    spec = importlib.util.spec_from_file_location(
        "browser.scrapers.course", _REPO / "browser" / "scrapers" / "course.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


course_mod = _load_course_module()
CourseScraper = course_mod.CourseScraper
classify_lessons = course_mod.classify_lessons
compute_lesson_hash = course_mod.compute_lesson_hash
stable_lesson_slug = course_mod.stable_lesson_slug


class StubCourseScraper(CourseScraper):
    """In-memory scraper: skips browser, returns a canned course tree."""

    PLATFORM = "stub"
    SERVICE_NAME = "course-stub"

    def __init__(self, tree, *, course_url="https://example.test/c", course_slug="stub-course"):
        super().__init__(course_url=course_url, course_slug=course_slug)
        self._tree = tree

    def ensure_logged_in(self):  # no browser
        return None

    def enumerate_structure(self) -> dict:
        return self._tree

    def capture_lesson(self, lesson, lesson_dir: Path) -> dict:
        (lesson_dir / "lesson.md").write_text(
            f"# {lesson.get('title')}\n\n{lesson.get('body', '')}\n", encoding="utf-8"
        )
        return {"captured": True}


def _redirect_scraped_dir(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(course_mod, "SCRAPED_DIR", tmp_path)


def _tree(lessons):
    return {"title": "Stub Course", "course_id": "stub-course", "lessons": lessons}


def _live(lesson_id, title, body="hello", resources=None, module="01-intro", type_="text", url=None):
    return {
        "id": lesson_id,
        "module": module,
        "title": title,
        "type": type_,
        "url": url or f"https://example.test/lesson/{lesson_id}",
        "body": body,
        "resources": list(resources or []),
    }


# --- pure helpers ----------------------------------------------------------


def test_compute_lesson_hash_is_resource_order_invariant():
    a = compute_lesson_hash("body", ["a.pdf", "b.pdf"])
    b = compute_lesson_hash("body", ["b.pdf", "a.pdf"])
    assert a == b


def test_compute_lesson_hash_changes_on_body_edit():
    assert compute_lesson_hash("body", []) != compute_lesson_hash("body!", [])


def test_stable_lesson_slug_survives_rename():
    s1 = stable_lesson_slug("lesson-id-123", "Welcome")
    s2 = stable_lesson_slug("lesson-id-123", "Renamed Welcome")
    assert s1.endswith(s2.split("-")[-1])  # same id-derived suffix


def test_classify_lessons_first_run_all_new():
    live = [
        dict(_live("L1", "One"), content_hash="h1"),
        dict(_live("L2", "Two"), content_hash="h2"),
    ]
    buckets = classify_lessons(None, live)
    assert len(buckets["new"]) == 2
    assert buckets["changed"] == [] and buckets["retired"] == [] and buckets["unchanged"] == []


def test_classify_lessons_identifies_changed_and_unchanged():
    existing = {
        "lessons": [
            {"id": "L1", "content_hash": "h1", "status": "active", "source_url": "u1"},
            {"id": "L2", "content_hash": "h2", "status": "active", "source_url": "u2"},
        ]
    }
    live = [
        dict(_live("L1", "One"), content_hash="h1", url="u1"),         # unchanged
        dict(_live("L2", "Two edited"), content_hash="h2x", url="u2"), # changed
    ]
    buckets = classify_lessons(existing, live)
    assert len(buckets["unchanged"]) == 1
    assert len(buckets["changed"]) == 1
    assert buckets["new"] == [] and buckets["retired"] == []


def test_classify_lessons_retires_missing_lesson():
    existing = {
        "lessons": [
            {"id": "L1", "content_hash": "h1", "status": "active"},
            {"id": "L2", "content_hash": "h2", "status": "active"},
        ]
    }
    live = [dict(_live("L1", "One"), content_hash="h1")]
    buckets = classify_lessons(existing, live)
    assert [s["id"] for s in buckets["retired"]] == ["L2"]


def test_classify_lessons_rename_matches_by_id_not_title():
    existing = {"lessons": [{"id": "L1", "content_hash": "h1", "status": "active"}]}
    live = [dict(_live("L1", "Renamed"), content_hash="h1")]
    buckets = classify_lessons(existing, live)
    assert buckets["new"] == []
    assert len(buckets["unchanged"]) == 1


def test_classify_lessons_already_retired_does_not_re_retire():
    existing = {"lessons": [{"id": "L1", "content_hash": "h1", "status": "retired"}]}
    live = []
    buckets = classify_lessons(existing, live)
    assert buckets["retired"] == []


# --- orchestration ---------------------------------------------------------


def test_first_run_writes_manifest_and_lessons(tmp_path, monkeypatch):
    _redirect_scraped_dir(tmp_path, monkeypatch)
    tree = _tree([_live("L1", "One"), _live("L2", "Two")])
    scraper = StubCourseScraper(tree)
    manifest = scraper.run(sync=False)

    assert manifest["platform"] == "stub"
    assert manifest["lesson_count"] == 2
    assert len(manifest["lessons"]) == 2
    assert manifest["sync_history"][-1] == {
        "synced_at": manifest["sync_history"][-1]["synced_at"],
        "added": 2,
        "updated": 0,
        "retired": 0,
        "failed": 0,
    }
    # On disk
    m_path = tmp_path / "courses" / "stub" / "stub-course" / "manifest.json"
    assert m_path.exists()
    on_disk = json.loads(m_path.read_text(encoding="utf-8"))
    assert on_disk["lesson_count"] == 2
    # Each lesson has a directory with lesson.md + meta.json
    for L in on_disk["lessons"]:
        ld = tmp_path / "courses" / "stub" / "stub-course" / L["path"]
        assert (ld / "lesson.md").exists()
        assert (ld / "meta.json").exists()


def test_second_run_with_no_changes_is_idempotent(tmp_path, monkeypatch):
    _redirect_scraped_dir(tmp_path, monkeypatch)
    tree = _tree([_live("L1", "One"), _live("L2", "Two")])
    StubCourseScraper(tree).run()
    manifest = StubCourseScraper(tree).run()
    assert manifest["lesson_count"] == 2
    history = manifest["sync_history"]
    assert len(history) == 2
    assert history[-1] == {
        "synced_at": history[-1]["synced_at"],
        "added": 0,
        "updated": 0,
        "retired": 0,
        "failed": 0,
    }


def test_changed_lesson_preserves_prior_file(tmp_path, monkeypatch):
    _redirect_scraped_dir(tmp_path, monkeypatch)
    StubCourseScraper(_tree([_live("L1", "One", body="v1")])).run()
    StubCourseScraper(_tree([_live("L1", "One", body="v2")])).run()

    # lesson.md is rewritten; the prior version is archived alongside.
    lesson_dirs = list(
        (tmp_path / "courses" / "stub" / "stub-course" / "modules" / "01-intro").iterdir()
    )
    assert len(lesson_dirs) == 1
    lesson_dir = lesson_dirs[0]
    assert (lesson_dir / "lesson.md").read_text(encoding="utf-8").endswith("v2\n")
    archived = [p for p in lesson_dir.iterdir() if p.name.startswith("lesson.") and p.name != "lesson.md"]
    assert archived, "prior lesson.md should be archived, not overwritten"


def test_retired_lesson_keeps_files_and_flips_status(tmp_path, monkeypatch):
    _redirect_scraped_dir(tmp_path, monkeypatch)
    StubCourseScraper(_tree([_live("L1", "One"), _live("L2", "Two")])).run()
    manifest = StubCourseScraper(_tree([_live("L1", "One")])).run()

    by_id = {L["id"]: L for L in manifest["lessons"]}
    assert by_id["L2"]["status"] == "retired"
    # Files for L2 still exist on disk
    l2_path = tmp_path / "courses" / "stub" / "stub-course" / by_id["L2"]["path"] / "lesson.md"
    assert l2_path.exists()
    assert manifest["sync_history"][-1]["retired"] == 1


def test_renamed_lesson_does_not_create_duplicate(tmp_path, monkeypatch):
    _redirect_scraped_dir(tmp_path, monkeypatch)
    StubCourseScraper(_tree([_live("L1", "Original")])).run()
    manifest = StubCourseScraper(_tree([_live("L1", "Renamed", body="hello")])).run()
    assert len(manifest["lessons"]) == 1
    assert manifest["lessons"][0]["title"] == "Renamed"
    # body unchanged → unchanged bucket
    assert manifest["sync_history"][-1]["updated"] == 0


def test_capture_failure_is_recorded_not_silent(tmp_path, monkeypatch):
    _redirect_scraped_dir(tmp_path, monkeypatch)

    class Boom(StubCourseScraper):
        def capture_lesson(self, lesson, lesson_dir):
            raise RuntimeError("network down")

    manifest = Boom(_tree([_live("L1", "One")])).run()
    assert manifest["lessons"][0]["status"] == "failed"
    assert manifest["sync_history"][-1]["failed"] == 1
