# 28-Day Action Meditation Telegram Series Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a repo-tracked 28-day Traditional Chinese Telegram reminder series for 《平凡人的28天行動冥想》 with a canonical JSON artifact and a generated Markdown preview.

**Architecture:** Keep the content in a single JSON artifact under `outputs/telegram/` and treat it as the canonical source. Add a small Python helper that validates structure, rebuilds `telegram_html` from the structured fields, and writes a Markdown preview so the human-readable review stays aligned with the source.

**Tech Stack:** Python, JSON, Markdown, pytest

---

### Task 1: Add the validation and preview helper

**Files:**
- Create: `tools/action_meditation_series.py`
- Test: `tests/test_action_meditation_series.py`

**Implementation notes:**
- Expose `load_series`, `validate_series`, `build_telegram_html`, and `render_preview_markdown`.
- Validate the 28-day sequence, required fields, `telegram_html` determinism, and Telegram-safe message length.
- Support a CLI path to validate and write the preview.

### Task 2: Add the canonical content artifact

**Files:**
- Create: `outputs/telegram/28_day_action_meditation_series.json`

**Implementation notes:**
- Store the series metadata plus 28 day entries.
- Keep `core_message` as exactly two short paragraphs per day.
- Keep `practice_steps` at 2 to 3 steps per day.

### Task 3: Generate and track the review preview

**Files:**
- Create: `outputs/telegram/28_day_action_meditation_preview.md`

**Implementation notes:**
- Generate the preview from the JSON artifact through the helper.
- Include the rendered Telegram HTML for each day so editorial review can compare structure and tone quickly.

### Task 4: Add a small sender entrypoint without touching existing jobs

**Files:**
- Modify: `tools/action_meditation_series.py`
- Test: `tests/test_action_meditation_series.py`

**Implementation notes:**
- Support `--day` for explicit day selection.
- Support `--start-date` plus optional `--target-date` to resolve the current day in a 28-day run.
- Support `--send` and `--env-file`, reusing `tools.telegram_hub` for credentials and Telegram delivery.
- Keep the default behavior non-destructive: validation only unless a day is requested or `--send` is set.

### Verification

Run:
- `python -m pytest tests\test_action_meditation_series.py -q`
- `python tools\action_meditation_series.py --validate --write-canonical --write-preview`
- `python tools\action_meditation_series.py --validate`
- `python tools\action_meditation_series.py --day 1`
- `python tools\action_meditation_series.py --start-date 2026-04-01 --target-date 2026-04-14`

Expected:
- Tests pass.
- Preview is rewritten without validation errors.
- The artifact contains exactly 28 valid Telegram messages.
- The CLI can resolve explicit and date-based day selection without touching existing scheduler jobs.
