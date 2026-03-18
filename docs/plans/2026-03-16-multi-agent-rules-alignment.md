# Multi-Agent Rules Alignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Align Codex, Claude Code, and Antigravity on one visible collaboration workflow across `notion-autopublish` and `fundman-jarvis`, and add a small generator for plan/handoff notes.

**Architecture:** Add thin-wrapper IDE entrypoints (`CLAUDE.md`), mirror a shared cross-repo operating model into both repos, and provide a tiny local Python generator that can scaffold plan or handoff markdown files. Keep the generator repo-local so each repo can run it independently.

**Tech Stack:** Markdown docs, Python 3 standard library, pytest.

---

### Task 1: Add failing tests for the note generator

**Files:**
- Create: `tests/test_agent_note.py`
- Create: `C:/Users/User/Documents/GitHub/fundman-jarvis/tests/test_agent_note.py`

**Step 1: Write the failing test**
- Assert the generator creates a dated plan file under `docs/plans/`.
- Assert the generator creates a dated handoff file under `docs/handoffs/`.
- Assert the generated markdown contains the expected headings.

**Step 2: Run test to verify it fails**

Run: `pytest .\tests\test_agent_note.py -q`
Expected: FAIL because `tools/agent_note.py` does not exist yet.

**Step 3: Write minimal implementation**
- Add a small `tools/agent_note.py` script to both repos.
- Accept `plan` or `handoff`, plus `--slug`, `--title`, and optional `--date`.

**Step 4: Run tests to verify they pass**

Run: `pytest .\tests\test_agent_note.py -q`
Expected: PASS

### Task 2: Add shared IDE rule entrypoints

**Files:**
- Create: `CLAUDE.md`
- Create: `C:/Users/User/Documents/GitHub/fundman-jarvis/CLAUDE.md`

**Step 1: Add thin wrapper docs**
- Point `CLAUDE.md` to `AGENTS.md`, `docs/agent_contract.md`, `docs/agent_workflow.md`, and `docs/agent_handoff_template.md`.
- Make it explicit that hidden IDE state must not override the visible repo contract.

**Step 2: Review links and repo-specific wording**
- Keep content concise and local to each repo.

### Task 3: Add the cross-repo operating model

**Files:**
- Create: `docs/multi_agent_operating_model.md`
- Create: `C:/Users/User/Documents/GitHub/fundman-jarvis/docs/multi_agent_operating_model.md`

**Step 1: Document the operating model**
- Define role boundaries between repos.
- Define when to split work and when not to.
- Define branch/worktree, ownership, handoff, and verification expectations.

**Step 2: Add generator command examples**
- Show how to create a plan note.
- Show how to create a handoff note.

### Task 4: Verify both repos

**Files:**
- Modify as needed based on test or path issues.

**Step 1: Run targeted tests**

Run: `pytest .\tests\test_agent_note.py -q`
Expected: PASS

Run: `pytest C:\Users\User\Documents\GitHub\fundman-jarvis\tests\test_agent_note.py -q`
Expected: PASS

**Step 2: Run syntax checks**

Run: `python -m py_compile .\tools\agent_note.py C:\Users\User\Documents\GitHub\fundman-jarvis\tools\agent_note.py`
Expected: no output, exit 0

**Step 3: Check created docs exist**

Run:
- `Get-ChildItem CLAUDE.md,docs\multi_agent_operating_model.md`
- `Get-ChildItem C:\Users\User\Documents\GitHub\fundman-jarvis\CLAUDE.md,C:\Users\User\Documents\GitHub\fundman-jarvis\docs\multi_agent_operating_model.md`

Expected: all files present
