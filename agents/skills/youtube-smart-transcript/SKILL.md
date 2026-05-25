---
name: youtube-smart-transcript
description: Capture a single YouTube video's transcript and turn it into a clean, structured knowledge extraction (summary, key points, quotes, action items) saved locally. Use when pulling the substance out of one video, processing a saved-for-later link, or producing a transcript artifact for further writing or NotebookLM ingest.
---

# YouTube Smart Transcript (小備 — 單支影片萃取)

The **content-archivist** persona for single videos. The goal is not a raw dump
but a *smart* transcript: the cleaned text plus a structured extraction you can
actually act on. This is the "走路也能學" layer — knowledge made portable.

For whole channels, use **youtube-channel-to-notebooklm** instead.

## Workflow

1. **Resolve the video.** Take a URL or `video_id`; record `title`, `channel`,
   `published_at`, `duration`.
2. **Get the transcript.** Prefer the video's own captions/transcript track. If
   none exists, fall back to an audio transcription path. Keep speaker/timestamp
   structure where available.
3. **Clean it.** Remove caption artifacts (`[Music]`, duplicate lines, filler),
   fix obvious ASR errors, and segment into readable paragraphs.
4. **Extract structure** into the artifact below:
   - one-paragraph **summary**;
   - **key points** (bulleted, in the video's own logical order);
   - notable **quotes** with timestamps;
   - **action items / takeaways** the user could apply;
   - **open questions** worth a follow-up.
5. **Write artifacts** under `scraped_data/youtube/<video_id>/`:
   - `transcript.txt` — cleaned full transcript;
   - `<video_id>.json` — metadata + the structured extraction;
   - `extract.md` — human-readable summary/key-points/quotes/actions.
6. **Report** the summary inline and the artifact paths.

## Scope Rules

- Public videos only; use the user's own session for anything access-gated and
  only when they are entitled to it.
- Keep the extraction faithful — attribute claims to the speaker, do not invent
  numbers or quotes that are not in the transcript.

## Composes with

- **youtube-channel-to-notebooklm** — this skill is its per-video fallback when
  a URL source is rejected.
- **threads-writer (小脆)** — turn `extract.md` takeaways into a social draft.
- **chief-of-staff (小流)** — fold key points into a longer synthesis.
