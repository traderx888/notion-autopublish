# BofA Chart 1 Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add BofA Chart 1 to the existing dashboard card so the live static page shows the Bull & Bear gauge instead of only summarizing it in table form.

**Architecture:** Keep the change inside the static dashboard artifact by adding a small inline SVG/CSS chart block to the existing BofA institutional card. Add a focused regression test that inspects `output/dashboard.html` for the new chart container and key labels so future refreshes do not silently remove it.

**Tech Stack:** Static HTML/CSS, inline SVG, pytest

---

### Task 1: Lock the expected chart markup with a failing regression test

**Files:**
- Create: `tests/test_dashboard_bofa_chart.py`

**Step 1: Write the failing test**

Add a pytest that reads `output/dashboard.html` and asserts the file contains:
- a `bofa-chart` container
- `Chart 1: BofA Bull & Bear Indicator`
- `Down to 8.4 from 8.5`
- `Source: BofA Global Investment Strategy`

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_dashboard_bofa_chart.py -q`
Expected: FAIL because the chart block does not exist yet.

### Task 2: Implement the chart inside the BofA card

**Files:**
- Modify: `output/dashboard.html`

**Step 1: Add minimal implementation**

Insert a compact chart panel into the existing BofA card:
- add scoped CSS for a `bofa-chart` block
- add inline SVG gauge markup and source note
- preserve the existing table and thesis below the chart

**Step 2: Run test to verify it passes**

Run: `pytest tests/test_dashboard_bofa_chart.py -q`
Expected: PASS

### Task 3: Verify the publish artifact and record evidence

**Files:**
- Modify: `docs/plans/2026-03-25-bofa-chart1-dashboard.md`

**Step 1: Run targeted verification**

Run:
- `pytest tests/test_dashboard_bofa_chart.py -q`
- `Select-String -Path output/dashboard.html -Pattern "Chart 1: BofA Bull & Bear Indicator|Down to 8.4 from 8.5|Source: BofA Global Investment Strategy"`

**Step 2: Record results**

Append the exact commands and actual outputs to this plan note before handoff or completion.

---

## Execution Notes

- The existing live dashboard already contained the BofA card from the earlier Mar 25 refresh. This task only adds Chart 1 markup inside that card and does not change any upstream data schema.
- The chart is implemented as inline SVG inside `output/dashboard.html` so GitHub Pages can publish it without a separate asset upload step.

## Verification Evidence

1. Red test

Run:
`pytest tests/test_dashboard_bofa_chart.py -q`

Actual result:
`FAILED tests/test_dashboard_bofa_chart.py::test_dashboard_contains_bofa_chart_1_block`

2. Green test

Run:
`pytest tests/test_dashboard_bofa_chart.py -q`

Actual result:
`.                                                                        [100%]`
`1 passed in 0.03s`

3. Artifact content check

Run:
`Select-String -Path output/dashboard.html -Pattern 'Chart 1: BofA Bull &amp; Bear Indicator','Down to 8.4 from 8.5','Source: BofA Global Investment Strategy','class="bofa-chart"'`

Actual result:
- `output/dashboard.html:488: <div class="bofa-chart">`
- `output/dashboard.html:489: <div class="bofa-chart-head">Chart 1: BofA Bull &amp; Bear Indicator</div>`
- `output/dashboard.html:490: <div class="bofa-chart-subhead">Down to 8.4 from 8.5</div>`
- `output/dashboard.html:514: <div class="bofa-chart-footnote"><strong>Source: BofA Global Investment Strategy.</strong> ...</div>`
