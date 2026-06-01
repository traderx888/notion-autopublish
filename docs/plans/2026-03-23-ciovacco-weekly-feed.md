# Ciovacco Weekly Feed Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Capture CiovaccoCapital's latest YouTube update as a recurring external-data source, emit a structured artifact under `scraped_data/ciovacco/`, and provide a local scheduled-task wrapper for Saturday 14:00 HKT plus a Sunday 14:00 HKT recheck.

**Architecture:** Use the YouTube channel RSS feed to discover the newest upload, then use `yt-dlp` metadata extraction to fetch English captions without downloading the full video. Parse the transcript into plain text plus lightweight ratio/technical signal observations, persist a stable JSON artifact for downstream consumers, and register a Windows scheduled task that runs the same capture command twice weekly.

**Tech Stack:** Python 3.12, `requests`, `yt-dlp`, `pytest`, Windows Task Scheduler via PowerShell, repo artifact conventions under `scraped_data/`.

---

### Task 1: Define the artifact contract

**Files:**
- Create: `tests/test_ciovacco_feed.py`
- Create: `ciovacco/__init__.py`
- Create: `ciovacco/feed.py`

**Step 1: Write the failing tests**

Add tests for:
- parsing the YouTube RSS feed into the latest video entry
- choosing the preferred English caption track from `yt-dlp` metadata
- extracting ratio mentions and technical keyword counts from transcript text

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_ciovacco_feed.py -q`
Expected: FAIL because the `ciovacco` module does not exist yet.

**Step 3: Write minimal implementation**

Implement:
- `parse_latest_feed_entry`
- `pick_preferred_caption_track`
- `extract_ratio_mentions`
- `extract_keyword_hits`

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_ciovacco_feed.py -q`
Expected: PASS for the new unit tests.

### Task 2: Add the capture runner and artifact writer

**Files:**
- Modify: `tests/test_ciovacco_feed.py`
- Create: `scrape_ciovacco.py`
- Modify: `ciovacco/feed.py`

**Step 1: Write the failing tests**

Add tests for:
- writing `scraped_data/ciovacco/ciovacco_latest.json`
- writing the per-video transcript text file
- CLI runner support for `--video-url` override and default latest-feed capture

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_ciovacco_feed.py -q`
Expected: FAIL because the artifact writer and CLI runner are not implemented.

**Step 3: Write minimal implementation**

Implement:
- capture orchestration that uses RSS + `yt-dlp`
- JSON/text artifact persistence
- `scrape_ciovacco.py` CLI entrypoint

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_ciovacco_feed.py -q`
Expected: PASS.

### Task 3: Register the recurring schedule

**Files:**
- Modify: `tests/test_ciovacco_feed.py`
- Create: `run_ciovacco_weekly.bat`
- Create: `register_ciovacco_weekly_task.ps1`
- Modify: `README.md`

**Step 1: Write the failing tests**

Add tests for:
- schedule metadata returned by the feed module
- runner command used by the batch wrapper

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_ciovacco_feed.py -q`
Expected: FAIL because the schedule metadata helper and wrapper expectations are missing.

**Step 3: Write minimal implementation**

Implement:
- a schedule metadata helper for `"Saturday 14:00 HKT"` and `"Sunday 14:00 HKT"`
- a `.bat` wrapper that runs `python scrape_ciovacco.py`
- a PowerShell registration script with two weekly triggers
- README notes for manual run and scheduled registration

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_ciovacco_feed.py -q`
Expected: PASS.

### Task 4: Verify the whole feature

**Files:**
- Modify: `requirements.txt`

**Step 1: Add any missing runtime dependency**

Add `yt-dlp` to `requirements.txt` if it is required by the implementation.

**Step 2: Run targeted verification**

Run:
- `pytest tests/test_ciovacco_feed.py -q`
- `python -m py_compile scrape_ciovacco.py ciovacco/feed.py`

Expected:
- tests pass
- compile check passes

**Step 3: Record verification evidence**

Document the exact commands and results in the final handoff/summary.

### Task 5: Downstream contract note

**Files:**
- Modify: `docs/plans/2026-03-23-ciovacco-weekly-feed.md`

**Step 1: Record the contract**

Document the upstream artifact path and core fields:
- `scraped_data/ciovacco/ciovacco_latest.json`
- latest video metadata
- transcript path
- ratio mentions
- keyword counts
- evidence-backed `analysis` fields for situation, core conclusion, ratio-specific reason/action, and operational watch items
- generated preview HTML at `output/ciovacco_latest_preview.html`
- schedule metadata

**Step 2: Note intended consumer**

Record that downstream consumers such as `fundman-jarvis` should treat this as an upstream external-observation feed sourced from CiovaccoCapital video analysis, not a market data API.
