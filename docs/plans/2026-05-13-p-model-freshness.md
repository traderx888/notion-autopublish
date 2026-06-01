# P-model Freshness Repair Implementation Plan

**Goal:** Restore fresh P-model/PAM signals in downstream digests by keeping Seeking Alpha scraped artifacts parseable.

**Architecture:** `notion-autopublish` remains the upstream owner of `scraped_data/sa_group_predictive_models.txt` and `scraped_data/sa_group_p_model_manifest.json`. The scraper should preserve source line boundaries while still deduping by normalized text, so downstream consumers can split individual PAM posts reliably.

**Owner:** Codex on `codex/2026-05-13-p-model-freshness`

**Scope:**
- Modify `scrape_sa_group.py` and `tests/test_scrape_sa_group.py`.
- Cross-repo consumer: `fundman-jarvis` parser reads `scraped_data/sa_group_predictive_models.txt`.
- Downstream impact: no schema change; artifact text formatting becomes more structured and less lossy.

## Tasks

1. Add a failing scraper regression test proving dedupe preserves meaningful line breaks while normalizing duplicate comparisons.
2. Patch `dedupe_content_blocks()` so it hashes collapsed whitespace but returns a trimmed, newline-preserving block.
3. Run `pytest tests/test_scrape_sa_group.py -q`.
4. Validate that the downstream parser can recover the latest May 2026 signal from the current cached artifact after the consumer-side fix.

## Verification

- `python -m pytest tests/test_scrape_sa_group.py -q`
- Cross-repo: `python -m pytest tests/test_p_model_pipeline.py -q` in `fundman-jarvis`
- Cross-repo: parse `C:\Users\User\Documents\GitHub\notion-autopublish\scraped_data\sa_group_predictive_models.txt` and confirm latest timestamp is May 2026, not November 2025.
