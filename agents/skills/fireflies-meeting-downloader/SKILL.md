---
name: fireflies-meeting-downloader
description: Download meeting recordings, transcripts, and AI summaries from Fireflies.ai via its GraphQL API into a local archive. Use when backing up recorded meetings, preserving decisions and action items before they get buried, or feeding meeting transcripts into a knowledge base / AI coach.
---

# Fireflies Meeting Downloader (小備 — 會議備份)

The **content-archivist** persona for meetings. Recorded calls are where key
decisions live and where they most often get lost. This skill pulls them into a
durable local archive so they can be re-queried, summarized, or turned into
follow-up actions.

## Scope Rules

- Use the user's own `FIREFLIES_API_KEY` (store in `.env`, never hardcode).
- Personal/team archival of the user's own meetings only. Respect participant
  consent and any recording-disclosure obligations already handled at capture
  time — this skill does not record, it only retrieves what Fireflies stored.
- Treat transcripts as sensitive: keep them in `scraped_data/`, never auto-push
  to public output.

## Workflow

1. **Authenticate.** Read `FIREFLIES_API_KEY` from the environment. The Fireflies
   API is GraphQL at `https://api.fireflies.ai/graphql` with a
   `Authorization: Bearer <key>` header.
2. **List transcripts.** Query the `transcripts` connection for the requested
   window (default: meetings newer than the last archived `date`). Page through
   results; collect `id`, `title`, `date`, `duration`, `participants`.
3. **Fetch each meeting** by `id`: full `sentences` (speaker, text, timestamps),
   the `summary` block (overview, action_items, keywords, bullet_gist), and the
   recording/audio URL when exposed.
4. **Write artifacts** under `scraped_data/meetings/<YYYY-MM-DD>-<slug>/`:
   - `transcript.md` — speaker-attributed, timestamped;
   - `summary.md` — overview + **action items** + decisions + keywords;
   - `meta.json` — id, date, duration, participants, source URLs;
   - `recording.url.txt` — recording link if provided.
5. **Maintain a rolling index** at `scraped_data/meetings/index.json` (id →
   path, date) so re-runs only fetch meetings not already archived.
6. **Report** new meetings archived and surface any open action items found, so
   they can be routed to the user's main-line tasks.

## Composes with

- **chief-of-staff (小流)** — turn a meeting summary + decisions into a
  retrospective or decision memo.
- **NotebookLM ingest** — point a notebook at `scraped_data/meetings/` to query
  across past calls.

## Notes

- The Fireflies free tier limits transcript history; archive forward regularly
  rather than assuming old meetings stay retrievable.
- If a query returns a rate-limit error, back off and resume from the rolling
  index — the run is resumable by design.
