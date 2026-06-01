# 2026-05-13 Jarvis Memory Capsules

## Goal

Emit curated Notion, Claude, ChatGPT, and research-summary insights as portable
`MemoryCapsule` records for Fundman-Jarvis and Hermes memory ingestion.

## Artifact Contract

- Producer repo: `C:\Users\User\Documents\GitHub\notion-autopublish`
- Inbox: `scraped_data/jarvis_memory/inbox`
- Latest JSONL artifact: `scraped_data/jarvis_memory/memory_capsules_latest.jsonl`
- Manifest: `scraped_data/jarvis_memory/memory_capsules_latest.manifest.json`
- Consumer repo: `C:\Users\User\Documents\GitHub\fundman-jarvis`

Each capsule must include `source`, `source_id`, `captured_at`, `summary`, and
`evidence`. Long raw transcripts stay in Notion or source storage; the artifact
contains curated reusable memory only.

## Implementation

`tools/jarvis_memory_capsules.py` exports curated JSON, JSONL, or Markdown
inputs into the JSONL artifact and writes a manifest with counts and timestamp.
Secrets are redacted before artifact write.

## Verification

Run:

`python -m pytest tools/test_jarvis_memory_capsules.py -q`
