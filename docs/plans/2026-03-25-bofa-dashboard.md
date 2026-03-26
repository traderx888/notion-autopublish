# BofA Dashboard Card Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Clarify the canonical BofA report location semantics and add a BofA Flow Show card to the live `notion-autopublish` dashboard using the latest March 19 PDF supplied by the user.

**Architecture:** Treat the March 19 BofA PDF as a manually supplied institutional source for this refresh. Extract the report title and a small set of stable headline metrics from the PDF, splice a new BofA card into the institutional dashboard section, and update the dashboard metadata/footer so the live Pages artifact reflects the new source without changing any downstream artifact schema.

**Tech Stack:** Static HTML, local PDF text extraction via `pypdf`, PowerShell inspection, `apply_patch`, GitHub Pages publish flow on `main`.

---

### Task 1: Confirm source-location semantics

**Files:**
- Read: `C:/Users/User/Documents/GitHub/fundman-jarvis/refresh_bofa_fms.py`

**Step 1: Inspect BofA discovery paths**
- Verify whether `fundman-jarvis` scans the repo-root `docs/research` for the active checkout.

**Step 2: Record operator guidance**
- Note that a PDF inside `.claude/worktrees/<branch>/docs/research` is valid for that worktree, but not the canonical shared location for other checkouts unless also copied to the root repo path.

### Task 2: Add BofA to the dashboard

**Files:**
- Modify: `output/dashboard.html`

**Step 1: Extract headline report facts**
- Use the user-provided PDF to extract the report title, date, Bull & Bear reading, weekly flow totals, and Hartnett tactical levels.

**Step 2: Add a BofA institutional card**
- Insert a new BofA card alongside the existing institutional cards, using only metrics grounded in the March 19 PDF.

**Step 3: Align top-level metadata**
- Refresh the dashboard title/timestamp/footer source list so the dashboard build date and source list include BofA.

**Step 4: Add one synthesis row**
- Add a compact synthesis row that captures BofA's “not capitulation yet” read without overstating it.

### Task 3: Verification and publish

**Files:**
- Verify only

**Step 1: Spot-check the HTML**
- Run targeted `Select-String` checks for the BofA card and refreshed timestamp/footer markers.

**Step 2: Browser-check the live dashboard**
- Load the live GitHub Pages dashboard with a cache-busting query string and confirm the new BofA card renders in the DOM.

**Step 3: Repo-state capture**
- Record the exact commit pushed to `main`, and note that no `fundman-jarvis` schema changed.

---

## Execution Notes

- `fundman-jarvis/refresh_bofa_fms.py` scans `repo_root/docs/research` for the active checkout, so `C:/Users/User/Documents/GitHub/fundman-jarvis/.claude/worktrees/thirsty-hopper/docs/research` is valid for that specific worktree only.
- If the report should be shared across other `fundman-jarvis` checkouts and sessions, it should also exist under the root repo path `C:/Users/User/Documents/GitHub/fundman-jarvis/docs/research`.
- The dashboard change uses the March 19 PDF `BofA_The Flow Show The Gravy Pain_20260319.pdf` as a manually supplied institutional source and does not introduce any new structured artifact contract.
- The publish worktree does not include the ignored `scraped_data/` mirror; the live Pages deployment depends only on `output/dashboard.html`.

## Verification Evidence

- `Select-String -Path output/dashboard.html -Pattern "March 25, 2026|BofA Global Research|The Flow Show &mdash; The Gravy Pain|BofA: Not Capitulation Yet|GS, Citadel, BofA, MS"`
  Result: matched the refreshed timestamp, BofA institutional card, BofA synthesis row, and footer source list.
- `git status --short`
  Result:
  - ` M output/dashboard.html`
  - `?? docs/plans/2026-03-25-bofa-dashboard.md`
- `git diff --stat`
  Result: `output/dashboard.html | 35 ++++++++++++++++++++++++++++++-----`
