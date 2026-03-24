# Dashboard Refresh Latest Data Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refresh the checked-in dashboard HTML to reflect the latest locally scraped author and institutional artifacts, with clear section-level freshness dates and no downstream schema change.

**Architecture:** Treat `output/dashboard.html` as the canonical checked-in dashboard artifact, update stale static cards directly from the latest source artifacts under `scraped_data/`, then mirror the same HTML into `scraped_data/dashboard.html` so both dashboard copies stay byte-identical.

**Tech Stack:** Static HTML, local text/JSON artifacts under `scraped_data/`, PowerShell inspection, `apply_patch` edits, Git diff verification.

---

### Task 1: Reconfirm latest inputs that should drive the refresh

**Files:**
- Verify only

**Step 1: Inspect current dashboard sections**
- Re-read the dashboard header, top signal chips, P-Model card, institutional cards, sector cards, and footer.

**Step 2: Inspect latest artifacts**
- Re-read the latest P-Model trade / flow notes, Citadel landing page snapshot, SemiAnalysis latest post, and Systematic Long Short latest post.

**Step 3: Decide refresh scope**
- Update only sections with clearly newer local artifacts and leave unchanged cards alone when their latest source remains the same.

### Task 2: Patch the stale dashboard content

**Files:**
- Modify: `output/dashboard.html`

**Step 1: Refresh metadata**
- Update the page title, subtitle, timestamp, top signal chips, and footer copy to March 24, 2026 language.

**Step 2: Refresh author and institutional cards**
- Update P-Model, Citadel Securities, SemiAnalysis, and Systematic Long Short with the latest source-backed summaries.

**Step 3: Refresh synthesis text where needed**
- Align the cross-source synthesis rows with the updated geopolitical / AI / flow context so the top-line summary does not contradict the refreshed cards.

### Task 3: Mirror the published artifact copy

**Files:**
- Modify: `scraped_data/dashboard.html`

**Step 1: Copy refreshed HTML**
- Mirror the updated `output/dashboard.html` into `scraped_data/dashboard.html`.

**Step 2: Confirm no divergence**
- Verify both dashboard files remain identical after the refresh.

### Task 4: Verification

**Files:**
- Verify only

**Step 1: Diff the changed files**
- Run: `git diff -- docs/plans/2026-03-24-dashboard-refresh-latest.md output/dashboard.html scraped_data/dashboard.html`

**Step 2: Confirm dashboard mirror parity**
- Run: `Compare-Object (Get-Content output/dashboard.html) (Get-Content scraped_data/dashboard.html) -SyncWindow 0`
- Expected: no output

**Step 3: Spot-check refreshed markers**
- Run targeted `Select-String` checks for `March 24, 2026`, `Nvidia`, `Citadel`, and `Your Agents Produce Slop Because You're Poor`.

**Step 4: Repo state capture**
- Run: `git status --short`
- Record that this is a static dashboard artifact refresh only; no `fundman-jarvis` schema or contract change is expected.

---

## Execution Notes

- Refreshed `output/dashboard.html` from the latest local artifacts for P-Model, Citadel Securities, SemiAnalysis, and Systematic Long Short.
- Mirrored the same HTML into `scraped_data/dashboard.html` for local parity.
- `scraped_data/dashboard.html` remains ignored by `.gitignore`, so the committed artifact for this refresh is `output/dashboard.html`.
- No upstream artifact schema changed and no `fundman-jarvis` handoff is required.

## Verification Evidence

- `git diff -- output/dashboard.html docs/plans/2026-03-24-dashboard-refresh-latest.md`
  Result: tracked diff is limited to the dashboard refresh plus this plan note.
- `Compare-Object (Get-Content output/dashboard.html) (Get-Content scraped_data/dashboard.html) -SyncWindow 0`
  Result: no output; local dashboard mirror matches exactly.
- `Select-String -Path output/dashboard.html -Pattern "March 24, 2026|Tactical Long, Rally Rented|April Capitulation Checklist|Nvidia &mdash; The Inference Kingdom Expands|Your Agents Produce Slop Because You're Poor"`
  Result: matched the refreshed timestamp/header, P-Model chip, Citadel item, SemiAnalysis card, and Systematic Long Short card.
- `git status --short output/dashboard.html docs/plans/2026-03-24-dashboard-refresh-latest.md`
  Result:
  - ` M output/dashboard.html`
  - `?? docs/plans/2026-03-24-dashboard-refresh-latest.md`
