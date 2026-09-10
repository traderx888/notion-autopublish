# Codex Newsletter Self-Hosted Runner

## Task

Replace Claude-based Bloomberg newsletter synthesis with a bounded Codex CLI
call using `gpt-5.6-sol`, retain the pytest gate and direct `main` publication,
and register a Windows self-hosted runner on this computer.

## Owner and Isolation

- Owner: Codex
- Branch: `codex/2026-09-10-codex-newsletter-runner`
- Worktree: `tmp/worktrees/codex-newsletter-runner`
- Repo-local code change plus host-level GitHub Actions runner installation

## Scope

- Add a reusable, read-only, ephemeral Codex JSON synthesis adapter.
- Switch both newsletter and Sunday digest synthesis away from Claude/Anthropic.
- Pin and verify the Codex CLI in the GitHub Actions workflow.
- Add focused tests for command construction, parsing, and failure behavior.
- Update the operator runbook.
- Register and start a repo-scoped Windows x64 self-hosted runner with the
  dedicated `notion-autopublish` label only after the updated workflow reaches
  `main`.

## Safety Boundaries

- Do not reuse or clean the existing dirty checkout.
- Do not expose GitHub registration tokens or Codex credentials in logs.
- Codex runs with `--ignore-user-config`, `--ephemeral`, and a read-only sandbox.
- Cancel the currently queued old-workflow run before bringing the runner online.
- Stage only owned files, secret-scan the staged diff, verify the private remote,
  and push the reviewed commit to the task branch before the authorized `main`
  update.

## Verification

- Focused unit tests for the Codex adapter and Bloomberg pipeline.
- Python compile checks for touched modules.
- Local minimal `gpt-5.6-sol` probe returning an exact sentinel.
- Workflow YAML parse/read-back.
- GitHub runner registration read-back (`online`, correct labels).
- Fresh manual workflow dispatch from the updated `main`, followed through to
  completion or an evidence-backed blocker.

## Downstream Impact

- Generated newsletter HTML and `outputs/ops/bloomberg_pipeline_state.json`
  retain their existing shape.
- No `fundman-jarvis` schema or consumer change is intended.

## Verification Results — 2026-09-10

- `python -m pytest tests/test_codex_synthesis.py tests/test_bloomberg_pipeline.py`
  passed: `25 passed`.
- `python -m py_compile` passed for both builders, the Codex adapter, and the
  focused tests.
- A real adapter probe using `gpt-5.6-sol` returned
  `{"probe": "CODEX_SOL_OK"}`.
- The workflow-pinned `@openai/codex@0.154.0` returned `CODEX_154_OK` in a
  separate live probe.
- Staged diff check passed and the credential-literal scan found zero matches.
- Commits `71d7b61` and `50c75bd` were pushed to `main` after confirming the
  remote SHA had not advanced.
- Old queued run `34441214110`, which referenced the Claude workflow at
  `5185ee0`, was cancelled before the runner started.
- GitHub runner `notion-autopublish-windows` (runner id 21) registered with
  runner version `2.337.0`; initial GitHub read-back showed `online`,
  `busy=false`, and the `notion-autopublish` label.
- After the connectivity proof, the runner process was stopped and GitHub
  read-back showed `offline`, preventing the scheduled workflow from publishing
  the unclassified backlog. Reboot/logon persistence is not configured.

## Live-Run Gate

`bloomberg_pdf_convert.py --dry-run` found 138 unprocessed PDFs in
`C:\blp\data`; all currently lack topic hashtags and would enter the pipeline
as `uncategorized`. A live workflow dispatch is intentionally withheld until
the operator chooses whether to classify first or publish the whole backlog.
