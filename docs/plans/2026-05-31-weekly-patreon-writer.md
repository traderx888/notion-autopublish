# Weekly Patreon Writer

**Owner:** Codex
**Date:** 2026-05-31
**Scope:** `notion-autopublish` local Bloomberg weekly bundle generation

## Task

Run the requested weekly BLP Patreon bundle command:

```powershell
python tools/weekly_patreon_writer.py --root "C:\blp\data" --since 2026-05-25 --until 2026-06-01 --out outputs/weekly/2026-W22-blp-bundle.md
```

## Finding

`tools/weekly_patreon_writer.py` is missing from the branch. The nearest existing
Bloomberg weekly tool is `tools/bloomberg_weekly_digest.py`, but it does not
accept the requested `--root`, `--since`, `--until`, or `--out` arguments.

## Plan

1. Add focused tests for selecting PDFs by an inclusive/exclusive date window and
   rendering a bounded Markdown bundle.
2. Implement `tools/weekly_patreon_writer.py` using existing Bloomberg PDF text
   extraction and disclaimer cleanup helpers.
3. Run the requested command against `C:\blp\data`.
4. Verify the output file exists, is non-empty, and contains the expected
   2026-W22 date window metadata.

## Downstream Impact

This creates a new Markdown artifact under `outputs/weekly/`. It does not change
the existing Bloomberg pipeline state schema in
`outputs/ops/bloomberg_pipeline_state.json` and does not require a
`fundman-jarvis` handoff.

## Verification

- `python -m pytest tests/test_weekly_patreon_writer.py -q`
  - Result: passed, `2 passed in 0.07s`
- `python -m py_compile tools/weekly_patreon_writer.py`
  - Result: passed, exit code 0
- `python tools/weekly_patreon_writer.py --root "C:\blp\data" --since 2026-05-25 --until 2026-06-01 --out outputs/weekly/2026-W22-blp-bundle.md`
  - Result: passed, wrote `outputs/weekly/2026-W22-blp-bundle.md` with 17 articles and 0 extraction errors
- Output integrity check:
  - Result: passed, file exists, size is 59,372 bytes, metadata includes `- Articles: 17`, metadata includes `- Extraction errors: 0`, and the file contains 17 article sections

## Existing Test Gap

- `python -m pytest tests/test_bloomberg_pipeline.py tests/test_weekly_patreon_writer.py -q`
  - Result: failed with 3 existing Bloomberg newsletter test failures unrelated to the new writer. The failures are legacy test/API mismatches around `render_newsletter_html(...)` and `update_student_portal(...)`.
