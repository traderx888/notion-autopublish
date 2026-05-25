---
name: youtube-channel-to-notebooklm
description: Mirror an entire YouTube channel (or playlist) into a NotebookLM notebook so the whole body of work becomes queryable as one knowledge base. Use when a creator's channel is worth studying end-to-end, when turning a backlog of saved videos into an AI-queryable source, or when building a per-creator NotebookLM coach.
---

# YouTube Channel → NotebookLM (小備 — 頻道級備份)

The **content-archivist** persona for whole-channel video knowledge. Single
saved videos pile up unwatched; this skill converts an entire channel into one
NotebookLM notebook you can interrogate, rather than 200 bookmarks you never
open.

This skill builds on the repo's existing NotebookLM integration (see the
NotebookLM sections of `README.md` and `fundamental_research/notebooklm_research.py`).
For one-off single-video work, use **youtube-smart-transcript** instead.

## Setup (one-time)

```bash
pip install "notebooklm-py[browser]"
python -m notebooklm login          # opens a browser for Google sign-in
```

- Create one NotebookLM notebook per channel at notebooklm.google.com and copy
  the ID from the URL (`.../notebook/<NOTEBOOK_ID>`).
- Optionally set `NOTEBOOKLM_STORAGE_PATH` to control where the session cookie
  is stored. Sessions expire in ~1–2h; re-run `python -m notebooklm login` on
  auth errors.

## Workflow

1. **Resolve the channel/playlist** to its full list of video URLs (newest →
   oldest). Capture `video_id`, `title`, `published_at` for each.
2. **Load the sync ledger** at
   `scraped_data/youtube/channels/<channel-slug>/synced.json` (video_id →
   added_at) so re-runs only add videos not already in the notebook — mirror the
   idempotent `canonicalize_source_url` / `find_source_by_url` pattern the repo
   already uses for NotebookLM source de-duplication.
3. **Add each new video as a NotebookLM source** via `NotebookLMClient`. Prefer
   adding the YouTube URL directly; fall back to adding a captured transcript
   (delegate to youtube-smart-transcript) when a URL source is rejected.
4. **Update the ledger** and write a channel `manifest.json` (channel title,
   notebook_id, counts, last_synced_at).
5. **Report** videos added vs skipped, and the notebook URL the user can now
   query.

## Scope Rules

- NotebookLM is **historical-context enrichment**, not the only copy — keep the
  source list/ledger in `scraped_data/` so the archive survives independent of
  the notebook.
- Public videos only; do not attempt members-only or paywalled content here.
- Default the channel notebook env var (e.g.
  `YOUTUBE_CHANNEL_NOTEBOOKLM_NOTEBOOK_ID`) so the notebook ID need not be passed
  every run, matching the repo's `*_NOTEBOOKLM_NOTEBOOK_ID` convention.

## Composes with

- **youtube-smart-transcript** — fallback transcript capture and per-video
  extraction.
- **chief-of-staff / course-designer** — query the channel notebook to draft a
  synthesis or a derived curriculum.
