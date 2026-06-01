# Dailychartbook Research + Signals Integration Plan

**Goal:** ingest the local Dailychartbook packet archive, normalize each day into durable JSON artifacts, and publish a stable family scorecard plus promoted readings for downstream consumption by `fundman-jarvis`.

**Owner:** Codex

**Counterpart repo:** `C:/Users/User/Documents/GitHub/fundman-jarvis`

**Primary downstream consumers:** `external_scrapers.py`, `cio_moe_system.py`, `agents/market_research.py`, `agents/fundamental_analyst.py`

## Scope

1. Add a local-file Dailychartbook parser in `notion-autopublish`.
2. Backfill the latest 30 calendar days from `DAILYCHARTBOOK_DIR`.
3. Persist:
   - `scraped_data/dailychartbook/by_date/<date>.json`
   - `scraped_data/dailychartbook/dailychartbook_family_scorecard_latest.json`
   - `scraped_data/dailychartbook/dailychartbook_readings_latest.json`
4. Keep contradictory evidence visible in the scorecard instead of flattening it away.
5. Promote only stable family-level signals into the readings artifact.

## Artifact Contract

### Per-day packet archive
- One JSON file per date under `scraped_data/dailychartbook/by_date/`
- Includes normalized packets plus packet-level family mappings
- Additive contract: unknown labels stay in the packet payload and do not produce promoted readings

### Latest family scorecard
- Contains the latest date's family summaries
- Each family records:
  - bull score
  - bear score
  - promoted flag
  - signal and value
  - top supporting bull and bear packets
  - packet count
- Includes conflict count for families with non-zero bull and bear evidence

### Latest promoted readings
- Stable `DCB_*` indicators only
- Intended downstream mapping into `fundman-jarvis` `daily_readings`
- Includes source metadata `source="dailychartbook"` and `category="chartbook"`

## Implementation Tasks

### Task 1: Lock behavior with tests
- Add parser tests for required fields, paired image paths, and unknown taxonomy labels
- Add scorecard tests proving mixed evidence is preserved while one-sided families are promoted
- Add artifact tests for per-day archives and latest scorecard/readings outputs

### Task 2: Implement upstream parser and taxonomy
- Add `browser/scrapers/dailychartbook.py`
- Add `config/dailychartbook_taxonomy.json`
- Add `scrape_dailychartbook.py`
- Keep root path configurable via CLI or `DAILYCHARTBOOK_DIR`

### Task 3: Verify on local source data
- Run focused pytest coverage for the new scraper
- Run a local scrape against the provided Dailychartbook directory
- Record the exact command and whether the generated artifacts are valid

## Downstream Handoff Expectations

When this upstream slice is ready, the `fundman-jarvis` handoff must include:
- artifact path
- scorecard field names
- promoted `DCB_*` tickers
- verification command proving the upstream latest artifacts exist and parse
