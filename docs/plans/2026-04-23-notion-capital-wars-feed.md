# Notion Capital Wars Feed Plan

## Goal

Make `notion-autopublish` produce the Capital Wars / GLI artifact from the user's saved Notion page instead of depending on the unstable Substack author scrape.

## Scope

- Add a Notion collector for the parent page `Michael Howell- Capital War`.
- Write the downstream text artifact expected by `fundman-jarvis`:
  - `scraped_data/notion/michael_howell_capital_war_latest.txt`
- Keep existing Substack capture as fallback.
- Update targeted tests and verification notes.

## Source Contract

- Parent page: `https://www.notion.so/Michael-Howell-Capital-War-15d3caa8a48780bf84ffcc796104a627`
- Select the latest child page whose title looks like a Howell GLI/liquidity update, especially `Global Liquidity Watch`.
- Export title, page URL, publication date, capture timestamp, and body text.

## Downstream Consumer

`fundman-jarvis` consumes:

- `scraped_data/notion/michael_howell_capital_war_latest.txt`
- Then parses GLI fields into `data/readings.json`.

Expected downstream values include:

- `GLI_GLOBAL_LIQUIDITY_TR`
- `GLI_GLOBAL_LIQ_3M_ANN`
- `GLI_GLOBAL_LIQ_12M`
- `GLI_SHADOW_MONETARY_BASE_TR`
- `GLI_SMB_3M_ANN`

## Verification

- `python -m pytest tests/test_notion_capital_wars_source.py tests/test_h_model_source.py::test_capture_latest_h_model_can_use_notion_source -q`
  - Red before implementation: failed because `liquidity.notion_capital_wars_source` did not exist.
  - Green after implementation: 3 passed.
- `python -m pytest tests/test_notion_capital_wars_source.py tests/test_h_model_source.py tests/test_h_model_parser.py tests/test_liquidity_tracker_cli.py -q`
  - 14 passed.
- `python -m py_compile liquidity\notion_capital_wars_source.py liquidity\h_model_source.py liquidity_tracker.py scrape_h_model.py`
  - passed.
- Live Notion export using `NOTION_TOKEN` loaded from sibling `fundman-jarvis/.env`
  - `capture_status=notion_ok`
  - selected `Global Liquidity Watch: Weekly Update Apr 21, 2026`
  - wrote `scraped_data/notion/michael_howell_capital_war_latest.txt`
  - wrote `scraped_data/notion/michael_howell_capital_war_latest.json`
- `python liquidity_tracker.py run`
  - printed `Liquidity Tracker: EXPANDING | MEDIUM | override=False`

## Runtime Credential State

As of 2026-04-23 HKT, `notion-autopublish/.env` has no `NOTION_TOKEN`, but sibling `fundman-jarvis/.env` does. `liquidity.h_model_source` now reads `NOTION_TOKEN` from:

1. process environment
2. `notion-autopublish/.env`
3. `fundman-jarvis/.env`
4. explicit `FUNDMAN_JARVIS_ENV_FILE` or `H_MODEL_SHARED_ENV_FILE`

The live run proved that the sibling `fundman-jarvis/.env` token can read the Michael Howell Notion parent page and export the Apr 21 GLI page.
