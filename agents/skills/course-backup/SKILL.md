---
name: course-backup
description: Back up an enrolled online course (Skool, Kajabi, Teachify, Teachable, and similar platforms) including videos, text lessons, and downloadable resources, then keep the local archive in sync with a weekly diff scan. Use when archiving a paid course you have access to, preserving content before a platform or instructor shuts it down, mirroring lesson updates, or building a course knowledge base for later AI ingest (NotebookLM, an AI coach, or a derived skill).
---

# Course Backup (小備 — 有價內容備份員)

This is the **content-archivist** persona for course content. It is the entry
point of the backup → knowledge → action pipeline: a course is only usable as a
knowledge base, AI coach, or derived skill *after* it has been fully and
faithfully archived.

Back up four things per course, in order of fragility: **downloadable resources
→ text/lesson bodies → video → metadata/structure**.

## Scope Rules (read first)

- Only back up courses the user is **legitimately enrolled in / has paid for**.
  This skill is for **personal, non-commercial** preservation and study, not
  redistribution. If the user asks to share, resell, or publish course content,
  stop and confirm the instructor's stated AI/sharing license first.
- Never bypass paywalls, DRM, or access controls. Use the user's own
  authenticated session only.
- Treat the archive as private. Do not push course video/text into any public
  output (`output/`, Notion publish flow, Threads) without explicit instruction.
- Do not auto-delete or overwrite a prior backup on a sync run — diff first, then
  add/update, and keep superseded versions (see `references/backup-manifest.md`).

## Workflow

1. **Identify the target.** Get the platform (Skool / Kajabi / Teachify /
   Teachable / other), the course URL, and the course slug. Decide if this is a
   first full backup or a weekly sync.
2. **Authenticate via a persistent browser session.** Course capture extends the
   repo's Playwright framework: subclass `BrowserAutomation` in `browser/base.py`
   (persistent session, `--chrome` real-profile reuse for Google/SSO logins,
   manual-intervention prompt for 2FA). The implementation surface is a
   `browser/scrapers/course_<platform>.py` collector; if it does not exist yet,
   create it on that base rather than inventing a one-off script.
3. **Enumerate structure.** Walk modules → lessons. Record the full tree
   (titles, order, URLs, lesson type) before downloading anything, so a partial
   run is resumable.
4. **Download per lesson:**
   - downloadable resources (PDF, slides, worksheets, audio) — most likely to
     vanish, grab first;
   - text/lesson HTML → cleaned markdown;
   - video → highest available quality the user's plan permits, plus captions/
     transcript when offered.
5. **Write artifacts** under `scraped_data/courses/<platform>/<course-slug>/`
   following the layout in `references/backup-manifest.md`, and emit/refresh
   `manifest.json`.
6. **Weekly sync = diff, not re-download.** Re-enumerate structure, compare
   against the existing manifest, download only new/changed lessons, mark
   removed lessons as `retired` (keep the file, flag it). Append a dated entry to
   the manifest's `sync_history`.
7. **Report.** Summarize: lessons added / updated / retired / unchanged, total
   size, and any lessons that failed to capture (with reason) for a retry pass.

## Decide what is worth archiving

Back it up if it meets **any one** of: paid for it · high time-cost to relearn ·
encodes a key personal decision · scarce / about to disappear · worth re-querying
later. One condition is enough to add it to 小備's active backup list.

## Composes with

- **youtube-smart-transcript / youtube-channel-to-notebooklm** — for the video
  layer when course lessons are hosted on YouTube.
- **NotebookLM ingest** (`python -m notebooklm login`, see repo README) — point a
  notebook at the archived markdown/transcripts to turn the backup into a
  queryable knowledge base / AI coach.
- **course-designer (小課)** — consumes the archive to produce new curriculum or
  a derived skill, closing the loop from backup → action.

## References

- `references/backup-manifest.md` — artifact layout, `manifest.json` schema, the
  weekly diff/sync contract, per-platform notes, and the authorized-use boundary.
