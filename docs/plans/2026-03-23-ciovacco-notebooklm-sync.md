# Ciovacco NotebookLM Sync Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Sync the latest Ciovacco artifact into a NotebookLM notebook, query NotebookLM for historical-context answers, and persist the enriched result back into `scraped_data/ciovacco/`.

**Architecture:** Keep the existing YouTube RSS + caption capture as the source-of-truth ingest path. Add a separate NotebookLM enrichment layer using `notebooklm-py` that can attach the latest YouTube URL to a configured notebook, avoid duplicate source inserts, ask a fixed Ciovacco prompt set, and write a structured `notebooklm` payload into the upstream artifact. Authentication remains external to the repo through NotebookLM storage state.

**Tech Stack:** Python 3.11/3.12, `notebooklm-py`, `pytest`, existing `ciovacco` artifact pipeline.

---

### Task 1: Define the NotebookLM contract in tests

**Files:**
- Create: `tests/test_ciovacco_notebooklm_sync.py`
- Modify: `requirements.txt`

**Step 1: Write the failing tests**

Add tests for:
- resolving NotebookLM config from CLI args and env vars
- building the fixed Ciovacco question set from the latest artifact
- detecting an existing YouTube source in a notebook by URL
- shaping the persisted NotebookLM result payload

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_ciovacco_notebooklm_sync.py -q`
Expected: FAIL because the NotebookLM sync module does not exist yet.

**Step 3: Add the runtime dependency**

Add `notebooklm-py[browser]` to `requirements.txt`.

**Step 4: Run test to verify it still fails for the missing implementation**

Run: `pytest tests/test_ciovacco_notebooklm_sync.py -q`
Expected: FAIL with import / missing function errors, not dependency errors.

### Task 2: Implement NotebookLM sync helpers

**Files:**
- Create: `ciovacco/notebooklm_sync.py`
- Modify: `ciovacco/__init__.py`

**Step 1: Write minimal implementation**

Implement:
- NotebookLM config resolution
- fixed prompt generation for `core_thesis`, `ratio_logic`, `what_changed`, and `action_items`
- helper to find an existing NotebookLM source by URL
- async sync function that:
  - opens `NotebookLMClient.from_storage`
  - validates notebook access
  - lists existing sources
  - adds the latest Ciovacco YouTube URL only if missing
  - waits until the source is ready when newly added
  - asks the fixed prompt set
  - captures notebook summary and sources metadata

**Step 2: Run targeted tests**

Run: `pytest tests/test_ciovacco_notebooklm_sync.py -q`
Expected: PASS.

### Task 3: Wire NotebookLM into the Ciovacco workflow

**Files:**
- Modify: `scrape_ciovacco.py`
- Modify: `ciovacco/feed.py`

**Step 1: Write the failing tests**

Add tests for:
- optional CLI flags for NotebookLM sync
- artifact update behavior when NotebookLM enrichment is returned
- no-op / graceful skip behavior when NotebookLM is not requested

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_ciovacco_feed.py tests/test_ciovacco_notebooklm_sync.py -q`
Expected: FAIL because CLI orchestration and artifact persistence are incomplete.

**Step 3: Write minimal implementation**

Implement:
- `--sync-notebooklm`
- `--notebook-id`
- `--notebooklm-storage`
- artifact persistence of a `notebooklm` block and a dedicated snapshot file if sync succeeds

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_ciovacco_feed.py tests/test_ciovacco_notebooklm_sync.py -q`
Expected: PASS.

### Task 4: Document the manual auth dependency

**Files:**
- Modify: `README.md`
- Modify: `docs/plans/2026-03-23-ciovacco-notebooklm-sync.md`

**Step 1: Document the login flow**

Document:
- `python -m notebooklm login`
- default storage path
- required notebook ID env var / CLI flag
- the fact that NotebookLM is enrichment, not the primary ingest source

**Step 2: Note downstream contract**

Record the new upstream fields:
- `notebooklm.notebook_id`
- `notebooklm.summary`
- `notebooklm.questions`
- `notebooklm.source`
- `notebooklm.synced_at`

### Task 5: Verify end to end

**Files:**
- No new files required

**Step 1: Run targeted verification**

Run:
- `pytest tests/test_ciovacco_feed.py tests/test_ciovacco_notebooklm_sync.py -q`
- `python -m py_compile scrape_ciovacco.py ciovacco/feed.py ciovacco/notebooklm_sync.py`

**Step 2: Run live commands**

Run:
- `python scrape_ciovacco.py`
- `python scrape_ciovacco.py --sync-notebooklm --notebook-id 99e260ac-3813-4c85-9eee-c05bd3f57b50`

Expected:
- first command refreshes the Ciovacco artifact normally
- second command either enriches successfully or fails with an explicit auth-required message if NotebookLM login has not been completed

**Step 3: Record verification evidence**

Document the exact commands and results in the final handoff/summary, including whether NotebookLM live sync was blocked by missing authentication.
