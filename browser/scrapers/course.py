"""
Course backup scraper base.

Implements the manifest + non-destructive diff/sync contract documented at
agents/skills/course-backup/references/backup-manifest.md, and orchestrates
the workflow defined at agents/skills/course-backup/SKILL.md.

Platform-specific work lives in subclasses (see course_skool.py). They
implement enumerate_structure() and capture_lesson(); the base owns the
orchestration: auth check, diffing, file writes, manifest + sync_history.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from browser.base import BrowserAutomation, SCRAPED_DIR


LESSON_TYPES = {"video", "text", "resource", "quiz"}
LESSON_STATUS = {"active", "retired", "failed"}


def utcnow_iso() -> str:
    """ISO-8601 UTC timestamp without microseconds, Z-suffixed."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def slugify(value: str, max_len: int = 60) -> str:
    s = re.sub(r"[^\w\-]+", "-", (value or "").strip().lower()).strip("-")
    return (s or "untitled")[:max_len]


def stable_lesson_slug(lesson_id: str, title: str, max_len: int = 60) -> str:
    """Slug derived from the platform's lesson id so a renamed lesson stays put.

    Falls back to a title slug only when no id is available, which should be
    avoided by enumerate_structure() — every live lesson should carry a stable
    id so the diff stays accurate across syncs.
    """
    if lesson_id:
        suffix = hashlib.sha1(lesson_id.encode("utf-8")).hexdigest()[:6]
        title_part = slugify(title, max_len=max_len - len(suffix) - 1) or "lesson"
        return f"{title_part}-{suffix}"
    return slugify(title, max_len=max_len)


def compute_lesson_hash(body: str | None, resources: Iterable[str] | None) -> str:
    h = hashlib.sha256()
    h.update((body or "").encode("utf-8"))
    h.update(b"\n--resources--\n")
    for r in sorted(resources or []):
        h.update(r.encode("utf-8"))
        h.update(b"\n")
    return f"sha256:{h.hexdigest()}"


def classify_lessons(existing: dict | None, live_lessons: list[dict]) -> dict:
    """Classify live lessons against an existing manifest.

    Match by lesson `id`, fallback to `source_url`. Returns four buckets keyed
    by `new` / `changed` / `retired` / `unchanged`. Live lessons must already
    carry `content_hash`.
    """
    by_id: dict[str, dict] = {}
    by_url: dict[str, dict] = {}
    if existing:
        for stored in existing.get("lessons", []):
            if stored.get("id"):
                by_id[stored["id"]] = stored
            if stored.get("source_url"):
                by_url[stored["source_url"]] = stored

    new: list[dict] = []
    changed: list[dict] = []
    unchanged: list[dict] = []
    seen_ids: set[str] = set()

    for live in live_lessons:
        live_id = live.get("id")
        stored = None
        if live_id and live_id in by_id:
            stored = by_id[live_id]
        elif live.get("url") and live["url"] in by_url:
            stored = by_url[live["url"]]

        if stored is None:
            new.append(live)
        else:
            seen_ids.add(stored["id"])
            if stored.get("content_hash") != live.get("content_hash"):
                changed.append({"live": live, "stored": stored})
            else:
                # Body+resources unchanged, but the live title/module may have
                # been edited — pass both so the orchestration can refresh
                # display metadata without re-downloading.
                unchanged.append({"live": live, "stored": stored})

    retired = [
        s
        for s in (existing.get("lessons", []) if existing else [])
        if s["id"] not in seen_ids and s.get("status") != "retired"
    ]

    return {
        "new": new,
        "changed": changed,
        "retired": retired,
        "unchanged": unchanged,
    }


def load_manifest(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_manifest(path: Path, manifest: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


class CourseScraper(BrowserAutomation):
    """Abstract base for course-backup scrapers.

    Subclass per platform. The subclass implements three things:
      - is_logged_in() / login()      (from BrowserAutomation)
      - enumerate_structure()         (live course tree)
      - capture_lesson(lesson, dir)   (download body / video / resources)

    The base owns the rest: hashing, diffing, writing files into the
    documented layout, and updating manifest.json + sync_history.
    """

    PLATFORM: str = "generic"

    def __init__(
        self,
        *,
        course_url: str | None = None,
        course_slug: str | None = None,
        course_title: str | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.course_url = course_url
        self.course_slug = course_slug
        self.course_title = course_title

    @property
    def courses_root(self) -> Path:
        d = SCRAPED_DIR / "courses" / self.PLATFORM
        d.mkdir(parents=True, exist_ok=True)
        return d

    def course_dir(self, slug: str) -> Path:
        d = self.courses_root / slug
        d.mkdir(parents=True, exist_ok=True)
        return d

    def manifest_path(self, slug: str) -> Path:
        return self.course_dir(slug) / "manifest.json"

    def lesson_dir(self, slug: str, lesson: dict) -> Path:
        module = lesson.get("module") or "00-uncategorized"
        lesson_slug = lesson.get("slug") or stable_lesson_slug(
            lesson.get("id", ""), lesson.get("title", "")
        )
        d = self.course_dir(slug) / "modules" / module / lesson_slug
        d.mkdir(parents=True, exist_ok=True)
        return d

    # --- abstract platform hooks -----------------------------------------

    def enumerate_structure(self) -> dict:
        """Walk the course and return:
            {"title": str, "course_id": str, "lessons": [LiveLesson]}

        Each LiveLesson must include: id, module, title, type, url, body
        (str or None), resources (list[str] of URLs), and may include
        transcript / video_url. The base computes slug + content_hash.
        """
        raise NotImplementedError

    def capture_lesson(self, lesson: dict, lesson_dir: Path) -> dict:
        """Download lesson assets into lesson_dir. Return a per-lesson meta
        dict that will be written to meta.json (free-form, platform-specific)."""
        raise NotImplementedError

    # --- orchestration ---------------------------------------------------

    def run(self, *, sync: bool = False) -> dict:
        if not self.course_url:
            raise ValueError("course_url is required")

        print(f"\n{'=' * 50}")
        print(f"  Course backup [{self.PLATFORM}] sync={sync}")
        print(f"  {self.course_url}")
        print(f"{'=' * 50}\n")

        self.ensure_logged_in()
        live = self.enumerate_structure()
        live_lessons = self._prepare_live_lessons(live)

        slug = self.course_slug or slugify(
            live.get("course_id") or live.get("title", "course")
        )
        course_dir = self.course_dir(slug)
        m_path = self.manifest_path(slug)
        existing = load_manifest(m_path)

        buckets = classify_lessons(existing, live_lessons)
        print(
            f"  Diff: new={len(buckets['new'])} changed={len(buckets['changed'])} "
            f"retired={len(buckets['retired'])} unchanged={len(buckets['unchanged'])}"
        )

        manifest = self._build_manifest_skeleton(existing, slug, live, sync=sync)
        failed = 0

        # New lessons: full capture, append.
        for live_lesson in buckets["new"]:
            stored = self._capture_into_manifest(slug, live_lesson, status="active")
            if stored.get("status") == "failed":
                failed += 1
            manifest["lessons"].append(stored)

        # Changed lessons: re-capture, keep prior file via timestamped suffix.
        for pair in buckets["changed"]:
            live_lesson = pair["live"]
            stored_prev = pair["stored"]
            stored = self._capture_into_manifest(
                slug, live_lesson, status="active", prior=stored_prev
            )
            if stored.get("status") == "failed":
                failed += 1
            manifest["lessons"].append(stored)

        # Unchanged content: pass through, but refresh title/module if the
        # live tree has renamed or moved the lesson.
        for pair in buckets["unchanged"]:
            stored = dict(pair["stored"])
            live = pair["live"]
            if live.get("title"):
                stored["title"] = live["title"]
            if live.get("module"):
                stored["module"] = live["module"]
            manifest["lessons"].append(stored)

        # Retired lessons: keep files, flip status. Never delete.
        for stored in buckets["retired"]:
            retired = dict(stored)
            retired["status"] = "retired"
            manifest["lessons"].append(retired)

        manifest["lesson_count"] = sum(
            1 for L in manifest["lessons"] if L.get("status") == "active"
        )
        manifest["sync_history"].append(
            {
                "synced_at": utcnow_iso(),
                "added": len(buckets["new"]),
                "updated": len(buckets["changed"]),
                "retired": len(buckets["retired"]),
                "failed": failed,
            }
        )

        save_manifest(m_path, manifest)
        print(f"\n  Manifest: {m_path}")
        print(f"  Active lessons: {manifest['lesson_count']}")
        return manifest

    # --- internals -------------------------------------------------------

    def _prepare_live_lessons(self, live_tree: dict) -> list[dict]:
        """Normalize each live lesson and attach slug + content_hash."""
        prepared = []
        for raw in live_tree["lessons"]:
            lesson = dict(raw)
            lesson["slug"] = lesson.get("slug") or stable_lesson_slug(
                lesson.get("id", ""), lesson.get("title", "")
            )
            lesson["type"] = lesson.get("type") or "text"
            if lesson["type"] not in LESSON_TYPES:
                lesson["type"] = "text"
            lesson["content_hash"] = compute_lesson_hash(
                lesson.get("body"), lesson.get("resources") or []
            )
            prepared.append(lesson)
        return prepared

    def _build_manifest_skeleton(
        self,
        existing: dict | None,
        slug: str,
        live: dict,
        *,
        sync: bool,
    ) -> dict:
        now = utcnow_iso()
        return {
            "platform": self.PLATFORM,
            "course_slug": slug,
            "course_title": (
                self.course_title
                or live.get("title")
                or (existing or {}).get("course_title", slug)
            ),
            "source_url": self.course_url,
            "first_backed_up_at": (existing or {}).get("first_backed_up_at", now),
            "last_synced_at": now,
            "lesson_count": 0,
            "lessons": [],
            "sync_history": list((existing or {}).get("sync_history", [])),
        }

    def _capture_into_manifest(
        self,
        slug: str,
        live: dict,
        *,
        status: str,
        prior: dict | None = None,
    ) -> dict:
        l_dir = self.lesson_dir(slug, live)
        captured_at = utcnow_iso()

        # On change: timestamp-preserve the prior body so history isn't lost.
        if prior is not None:
            primary = l_dir / "lesson.md"
            if primary.exists():
                archived = l_dir / f"lesson.{prior.get('captured_at', 'prev').replace(':', '').replace('-', '')}.md"
                if not archived.exists():
                    primary.rename(archived)

        try:
            meta = self.capture_lesson(live, l_dir) or {}
            (l_dir / "meta.json").write_text(
                json.dumps(
                    {
                        "id": live.get("id"),
                        "title": live.get("title"),
                        "type": live.get("type"),
                        "source_url": live.get("url"),
                        "captured_at": captured_at,
                        "content_hash": live.get("content_hash"),
                        **meta,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            current_status = status
        except Exception as e:
            print(f"    ERROR capturing {live.get('title')}: {e}")
            current_status = "failed"

        return {
            "id": live.get("id"),
            "module": live.get("module"),
            "slug": live["slug"],
            "title": live.get("title"),
            "type": live["type"],
            "path": f"modules/{live.get('module', '00-uncategorized')}/{live['slug']}/",
            "source_url": live.get("url"),
            "content_hash": live["content_hash"],
            "status": current_status,
            "captured_at": captured_at,
        }
