# Student PDF Share Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Publish the uploaded Q2 2026 market intelligence PDF into the student portal so students can open it from the website.

**Architecture:** Keep the change repo-local and static. Add the PDF as a served asset under `output/assets/`, add a gated HTML viewer page under `output/`, and link that viewer from `output/student.html` so the student flow matches the existing protected newsletter pattern.

**Tech Stack:** Static HTML, pytest, PowerShell file copy.

---

### Task 1: Lock the expected portal behavior with a regression test

**Files:**
- Create: `tests/test_student_pdf_share.py`
- Verify: `pytest tests/test_student_pdf_share.py -q`

**Steps:**
1. Add a test that expects `output/student.html` to link to a new Q2 2026 PDF viewer page.
2. Add a test that expects the viewer page to enforce the existing `student_auth` session gate and reference the copied PDF asset.
3. Add a test that expects the PDF asset to exist under `output/assets/`.

### Task 2: Publish the student-facing PDF resource

**Files:**
- Create: `output/q2_2026_market_intelligence_newsletter.html`
- Modify: `output/student.html`
- Create: `output/assets/q2_2026_market_intelligence_newsletter.pdf`

**Steps:**
1. Copy the uploaded PDF into `output/assets/`.
2. Create a gated viewer page with back navigation to `student.html`.
3. Add a highlighted course-material card near the top of the student portal.

### Task 3: Verify the static share path

**Files:**
- Verify only: `output/student.html`, `output/q2_2026_market_intelligence_newsletter.html`, `output/assets/q2_2026_market_intelligence_newsletter.pdf`

**Steps:**
1. Run `pytest tests/test_student_pdf_share.py -q`.
2. Record the exact command and result in the final handoff-style summary.
