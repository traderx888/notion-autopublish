# Student HTML Publish Plan

**Goal:** Publish the provided `bigtech_q1_2026_earnings_fomc_newsletter.html` file into the student portal as a gated student-facing HTML issue.

**Owner:** Codex

**Scope:** Repo-local static student portal output only. No `fundman-jarvis` artifact or schema impact is expected.

**Architecture:** Add a small reusable helper that copies a source HTML file into `output/`, injects the standard `student_auth` gate plus a portal back-link, and upserts a matching card into `output/student.html` under course materials.

**Tech Stack:** Python 3 standard library, static HTML, targeted unittest verification.

---

### Task 1: Add a reusable student HTML publish helper

**Files:**
- Create: `tools/student_html_publish.py`

**Steps:**
1. Read a source HTML file from disk.
2. Inject the standard student auth redirect if missing.
3. Inject a lightweight back-link to `student.html`.
4. Upsert a matching course-material card into `output/student.html`.

### Task 2: Lock the workflow with focused regression coverage

**Files:**
- Create: `tests/test_student_html_publish.py`

**Steps:**
1. Verify the helper injects the auth gate and portal link.
2. Verify portal card insertion is idempotent.
3. Verify a temp publish run writes the output HTML and updates a temp `student.html`.

### Task 3: Run the helper on the provided student issue

**Files:**
- Create: `output/bigtech_q1_2026_earnings_fomc_newsletter.html`
- Modify: `output/student.html`

**Steps:**
1. Publish the downloaded HTML into `output/`.
2. Add a highlighted portal card with tags for earnings, AI, FOMC, and oil risk.
3. Verify the generated page remains gated and reachable from the student portal.

### Task 4: Verify and record results

**Commands:**
- `python3 -m unittest discover -s tests -p 'test_student_html_publish.py' -q`
- `rg -n "bigtech_q1_2026_earnings_fomc_newsletter.html|科技巨頭 AI 軍備競賽 × FOMC 宏觀裂變|student_auth" output/student.html output/bigtech_q1_2026_earnings_fomc_newsletter.html`

**Expected result:**
- Tests pass.
- The published HTML contains the student gate and portal back-link.
- `output/student.html` links to the new HTML issue exactly once.
