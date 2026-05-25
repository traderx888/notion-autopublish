# Course Backup — Artifact Layout, Manifest, and Sync Contract

## Directory layout

All course archives live under the repo's standard `scraped_data/` root
(`SCRAPED_DIR` in `browser/base.py`):

```
scraped_data/courses/<platform>/<course-slug>/
  manifest.json
  modules/
    01-<module-slug>/
      01-<lesson-slug>/
        lesson.md            # cleaned text/body
        transcript.md        # video captions/transcript, when available
        video.mp4            # or video.url.txt if download is not permitted
        resources/           # PDFs, slides, worksheets, audio
        meta.json            # per-lesson source URL, type, hashes, captured_at
```

- `<platform>` ∈ `skool | kajabi | teachify | teachable | other`.
- Slugs are lowercase, hyphenated, and **stable** across syncs (derive from the
  lesson's permanent ID/URL, not its display title, so a renamed lesson is not
  treated as new).
- Numeric prefixes preserve course order so the tree reads in sequence on disk.

## `manifest.json` schema

```json
{
  "platform": "skool",
  "course_slug": "example-course",
  "course_title": "Example Course",
  "source_url": "https://...",
  "first_backed_up_at": "2026-05-25T08:00:00Z",
  "last_synced_at": "2026-05-25T08:00:00Z",
  "lesson_count": 42,
  "lessons": [
    {
      "id": "stable-platform-id",
      "module": "01-getting-started",
      "slug": "01-welcome",
      "title": "Welcome",
      "type": "video|text|resource|quiz",
      "path": "modules/01-getting-started/01-welcome/",
      "content_hash": "sha256:...",
      "status": "active|retired|failed",
      "captured_at": "2026-05-25T08:00:00Z"
    }
  ],
  "sync_history": [
    {
      "synced_at": "2026-05-25T08:00:00Z",
      "added": 0,
      "updated": 0,
      "retired": 0,
      "failed": 0
    }
  ]
}
```

`content_hash` is over the normalized lesson body + the resource file list, so a
text edit or a swapped attachment is detected even when the title is unchanged.

## Weekly diff / sync contract

1. Re-enumerate the live course structure into a fresh in-memory tree.
2. Match live lessons to manifest lessons **by `id`** (fallback: source URL).
3. Classify each:
   - **new** — present live, absent in manifest → download, append lesson.
   - **changed** — `content_hash` differs → re-download into the same path,
     bump `captured_at`, keep the previous file as `lesson.<captured_at>.md`
     (never silently overwrite history).
   - **retired** — present in manifest, absent live → set `status: retired`,
     keep all files. Do not delete.
   - **unchanged** — skip.
4. Record counts in a new `sync_history` entry and refresh `last_synced_at`.
5. A lesson that errors mid-capture is marked `status: failed` so the next run
   retries only the gaps instead of re-pulling the whole course.

Sync is **additive and non-destructive by default.** Deleting archived content
requires an explicit user instruction.

## Per-platform notes

- **Skool** — community + classroom; lessons can be gated by membership level.
  Capture the classroom tree; community posts are out of scope unless asked.
- **Kajabi** — "Products" → "Categories" → "Lessons"; downloadable resources are
  attached per lesson.
- **Teachify / Teachable** — chapter/lecture model; video is often Wistia/Vimeo
  embedded — prefer the platform's own download/transcript when offered.
- For any platform, if video download is not permitted by the user's plan, store
  `video.url.txt` with the canonical URL plus the transcript rather than
  attempting to circumvent the restriction.

## Authorized-use boundary

This archive exists for the enrolled user's **personal learning and
non-commercial** re-use (knowledge base, AI coach, study). It must not be
redistributed, resold, or published. When in doubt about an instructor's AI /
sharing license, surface the question to the user before any outward use — the
same boundary the source workflow essay calls out.
