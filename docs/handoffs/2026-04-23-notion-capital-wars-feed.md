# Handoff

## Task
- Replace the Capital Wars / GLI upstream capture path with a Notion-first collector that reads the user's saved Michael Howell page and writes the artifact consumed by `fundman-jarvis`.

## Owner
- Current agent/IDE: Codex
- Branch or worktree: `2026-04-23-notion-capital-wars-feed`
- Date: 2026-04-23

## Scope
- Files changed:
  - `liquidity/notion_capital_wars_source.py`
  - `liquidity/h_model_source.py`
  - `tests/test_notion_capital_wars_source.py`
  - `tests/test_h_model_source.py`
  - `.env.example`
  - `README.md`
  - `docs/plans/2026-04-23-notion-capital-wars-feed.md`
  - `docs/handoffs/2026-04-23-notion-capital-wars-feed.md`
- Files intentionally not touched:
  - Local `.env`, because it may contain secrets and currently has no Notion token.
  - Downstream `fundman-jarvis`, which already has a Notion-first cache fallback from the prior change.
- Repo-local or cross-repo: cross-repo artifact producer for `fundman-jarvis`.

## What Changed
- Added a Notion REST collector that reads child pages under `Michael Howell- Capital War`, selects the latest GLI/liquidity update page, converts Notion blocks to text, and writes:
  - `scraped_data/notion/michael_howell_capital_war_latest.txt`
  - `scraped_data/notion/michael_howell_capital_war_latest.json`
- Updated `capture_latest_h_model()` so `H_MODEL_SOURCE=notion` is the default path and Substack remains a fallback if Notion credentials or capture fail.
- Added token resolution from sibling `fundman-jarvis/.env` so the existing downstream Notion token does not need to be duplicated in this repo.
- Updated `.env.example` and README with the Notion H-model settings.

## Verification
- Commands run:
  - `python -m pytest tests/test_notion_capital_wars_source.py tests/test_h_model_source.py::test_capture_latest_h_model_can_use_notion_source -q`
  - `python -m pytest tests/test_notion_capital_wars_source.py tests/test_h_model_source.py tests/test_h_model_parser.py tests/test_liquidity_tracker_cli.py -q`
  - `python -m py_compile liquidity\notion_capital_wars_source.py liquidity\h_model_source.py liquidity_tracker.py scrape_h_model.py`
  - Live export via `capture_latest_notion_capital_wars(...)` using the sibling `fundman-jarvis/.env` token.
  - `python liquidity_tracker.py run`
- Result:
  - passed; targeted suite result was 14 passed.
  - live export selected `Global Liquidity Watch: Weekly Update Apr 21, 2026`.
  - liquidity tracker printed `Liquidity Tracker: EXPANDING | MEDIUM | override=False`.

## Current State
- Working now: code and tests for Notion-first GLI capture are in place, and live artifact generation succeeded using `fundman-jarvis/.env`.
- Still open: keep the Notion parent page shared with the integration behind the token.
- Manual step required: none for the current local machine; the sibling token is enough.

## Risks / Notes
- Schema changes: additive only. The old raw H-model shape still has `articles`; new fields include Notion artifact paths and `source_mode`.
- Environment or credential dependencies:
  - `NOTION_TOKEN` or `H_MODEL_NOTION_TOKEN`
  - fallback token source: sibling `fundman-jarvis/.env`
  - optional `H_MODEL_SOURCE=notion`
  - optional `H_MODEL_NOTION_PARENT_PAGE_ID=15d3caa8a48780bf84ffcc796104a627`
  - optional `H_MODEL_NOTION_OUTPUT_DIR=scraped_data/notion`
- Known edge cases:
  - If the Notion integration is not shared into the parent page, the collector will fail and Substack fallback will run.
  - If new GLI pages omit a parseable date in the title, selection falls back to Notion `last_edited_time`.

## Next Recommended Step
- Keep the scheduled `python liquidity_tracker.py run` task active; it now refreshes the Notion artifact before `fundman-jarvis` consumes it.
