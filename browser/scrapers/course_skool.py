"""
Skool course backup.

Best-effort Playwright capture of a Skool classroom course. The orchestration
(manifest, diff, sync history) lives in CourseScraper; this subclass only
handles Skool-specific login + DOM walking.

NOTE on selectors: Skool's classroom UI changes from time to time. The
selectors below worked at authoring but should be verified on the first run
against your own account. If a step fails, the scraper falls back to
wait_for_user() so you can navigate manually and the run is still resumable.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import requests

from browser.scrapers.course import CourseScraper


class SkoolCourseScraper(CourseScraper):
    SERVICE_NAME = "course-skool"
    PLATFORM = "skool"
    SIGN_IN_URL = "https://www.skool.com/login"

    def is_logged_in(self) -> bool:
        self.page.goto(self.course_url, wait_until="domcontentloaded")
        self.page.wait_for_timeout(2500)
        return "/login" not in self.page.url

    def login(self):
        self.page.goto(self.SIGN_IN_URL, wait_until="domcontentloaded")
        self.wait_for_user(
            "Sign in to Skool in the open browser window (incl. any 2FA), "
            "then return here."
        )
        self.page.goto(self.course_url, wait_until="domcontentloaded")
        self.page.wait_for_timeout(2000)

    # --- enumerate -------------------------------------------------------

    def enumerate_structure(self) -> dict:
        """Walk the classroom and return the live course tree.

        Skool exposes modules as expandable sections on the classroom page;
        each lesson is a link with a stable id segment in its href. If the
        DOM walk fails, we fall back to a user-driven manual walk where the
        user clicks through lessons and we capture URLs from page navigation.
        """
        self.page.goto(self.course_url, wait_until="domcontentloaded")
        self.page.wait_for_timeout(3000)

        title = self._extract_course_title()
        course_id = self._extract_course_id(self.course_url)

        lessons = self._enumerate_via_dom()
        if not lessons:
            print("  DOM enumeration found nothing; switching to manual walk.")
            lessons = self._enumerate_via_manual_walk()

        return {"title": title, "course_id": course_id, "lessons": lessons}

    def _extract_course_title(self) -> str:
        for sel in ["h1", '[class*="title"]', "title"]:
            loc = self.page.locator(sel).first
            if loc.count() > 0:
                txt = (loc.inner_text() or "").strip()
                if txt:
                    return txt
        return "Skool Course"

    def _extract_course_id(self, url: str) -> str:
        parts = [p for p in urlparse(url).path.split("/") if p]
        # e.g. /<community>/classroom/<course-id-or-slug>
        if "classroom" in parts:
            i = parts.index("classroom")
            if i + 1 < len(parts):
                return parts[i + 1]
        return parts[-1] if parts else "course"

    def _enumerate_via_dom(self) -> list[dict]:
        lessons: list[dict] = []
        # VERIFY: Skool's classroom DOM. These selectors are best-effort.
        module_blocks = self.page.locator(
            '[class*="module"], [data-testid*="module"], section'
        )
        try:
            count = module_blocks.count()
        except Exception:
            count = 0

        for i in range(count):
            block = module_blocks.nth(i)
            module_title = ""
            header = block.locator("h2, h3, [class*='title']").first
            if header.count() > 0:
                module_title = (header.inner_text() or "").strip()
            module_slug = f"{i + 1:02d}-" + (self._slug(module_title) or "module")

            lesson_links = block.locator(
                'a[href*="/classroom/"], a[href*="/lesson/"], a[href*="?md="]'
            )
            try:
                lcount = lesson_links.count()
            except Exception:
                lcount = 0

            for j in range(lcount):
                link = lesson_links.nth(j)
                href = link.get_attribute("href") or ""
                title = (link.inner_text() or "").strip().splitlines()[0] if link.inner_text() else ""
                if not href or not title:
                    continue
                full_url = href if href.startswith("http") else f"https://www.skool.com{href}"
                lesson_id = self._lesson_id_from_url(full_url)
                lessons.append(
                    {
                        "id": lesson_id,
                        "module": module_slug,
                        "title": title,
                        "type": "video",  # captured later refines via DOM
                        "url": full_url,
                    }
                )
        # Best-effort body/resource fetch per lesson so the hash + capture
        # have something to work with. Skip body fetch here — done in
        # capture_lesson() — but we still need it for hashing.
        for lesson in lessons:
            body, resources, video_url = self._peek_lesson(lesson["url"])
            lesson["body"] = body
            lesson["resources"] = resources
            lesson["video_url"] = video_url
        return lessons

    def _enumerate_via_manual_walk(self) -> list[dict]:
        """Fallback: user clicks through lessons in order, presses Enter
        between each, and we record the URL + page text at each step.
        """
        lessons: list[dict] = []
        idx = 1
        while True:
            self.wait_for_user(
                f"Manual walk: navigate to lesson #{idx} in the browser, then press Enter. "
                "Type 'done' + Enter when there are no more lessons."
            )
            # Re-read stdin: wait_for_user already consumed Enter. Allow exit via env.
            url = self.page.url
            if not url or "/classroom/" not in url:
                break
            title = self._extract_lesson_title()
            body, resources, video_url = self._peek_lesson(url, already_on_page=True)
            lessons.append(
                {
                    "id": self._lesson_id_from_url(url),
                    "module": "01-manual",
                    "title": title,
                    "type": "video" if video_url else "text",
                    "url": url,
                    "body": body,
                    "resources": resources,
                    "video_url": video_url,
                }
            )
            idx += 1
            # Loop break is operator-driven; we keep this simple intentionally.
            if idx > 200:
                break
        return lessons

    # --- capture ---------------------------------------------------------

    def capture_lesson(self, lesson: dict, lesson_dir: Path) -> dict:
        # Text body
        body = lesson.get("body") or ""
        if not body:
            body, resources, video_url = self._peek_lesson(lesson["url"])
            lesson.setdefault("resources", resources)
            lesson.setdefault("video_url", video_url)
        (lesson_dir / "lesson.md").write_text(
            f"# {lesson.get('title', '')}\n\n{body}\n",
            encoding="utf-8",
        )

        # Resources: download visible attachment URLs.
        res_dir = lesson_dir / "resources"
        res_dir.mkdir(exist_ok=True)
        for url in lesson.get("resources") or []:
            try:
                self._download(url, res_dir)
            except Exception as e:
                print(f"      resource failed: {url} ({e})")

        # Video: record canonical URL; download path is plan/CDN-dependent
        # and is intentionally not bypassed here.
        if lesson.get("video_url"):
            (lesson_dir / "video.url.txt").write_text(
                lesson["video_url"] + "\n", encoding="utf-8"
            )

        return {
            "video_url": lesson.get("video_url"),
            "resource_count": len(lesson.get("resources") or []),
        }

    # --- helpers ---------------------------------------------------------

    def _peek_lesson(self, url: str, *, already_on_page: bool = False):
        if not already_on_page:
            self.page.goto(url, wait_until="domcontentloaded")
            self.page.wait_for_timeout(2000)
        body = ""
        body_el = self.page.locator(
            '[class*="lesson"], [class*="content"], article, main'
        ).first
        if body_el.count() > 0:
            try:
                body = (body_el.inner_text() or "").strip()
            except Exception:
                body = ""
        resources: list[str] = []
        for a in self.page.locator("a[href]").all():
            href = a.get_attribute("href") or ""
            if self._looks_like_resource(href):
                full = href if href.startswith("http") else f"https://www.skool.com{href}"
                if full not in resources:
                    resources.append(full)
        video_url = None
        v = self.page.locator("video, iframe[src*='vimeo'], iframe[src*='youtube']").first
        if v.count() > 0:
            video_url = v.get_attribute("src") or v.get_attribute("data-src")
        return body, resources, video_url

    def _looks_like_resource(self, href: str) -> bool:
        return bool(re.search(r"\.(pdf|zip|docx?|xlsx?|pptx?|csv|mp3|wav)(\?|$)", href, re.I))

    def _extract_lesson_title(self) -> str:
        for sel in ["h1", "h2", '[class*="lesson-title"]', "title"]:
            loc = self.page.locator(sel).first
            if loc.count() > 0:
                t = (loc.inner_text() or "").strip()
                if t:
                    return t
        return "Untitled"

    def _lesson_id_from_url(self, url: str) -> str:
        # Skool lesson permalinks usually include a stable id query/segment.
        m = re.search(r"[?&]md=([^&]+)", url)
        if m:
            return m.group(1)
        m = re.search(r"/(lesson|md)/([^/?#]+)", url)
        if m:
            return m.group(2)
        parts = [p for p in urlparse(url).path.split("/") if p]
        return parts[-1] if parts else url

    def _slug(self, value: str) -> str:
        s = re.sub(r"[^\w\-]+", "-", (value or "").strip().lower()).strip("-")
        return s[:40]

    def _download(self, url: str, dest_dir: Path):
        # Reuse the browser session's cookies so paywalled resources work.
        cookies = self.context.cookies() if self.context else []
        jar = {c["name"]: c["value"] for c in cookies}
        r = requests.get(url, cookies=jar, timeout=60)
        r.raise_for_status()
        name = url.split("?")[0].rsplit("/", 1)[-1] or "resource.bin"
        (dest_dir / name).write_bytes(r.content)
