# Agent Workflow

## Goal

Use this workflow when more than one agent or IDE may touch the same project.
The aim is to keep work parallel without allowing hidden rules, stale context,
or silent schema drift to break the repo.

## Standard Flow

1. Intake
   - Restate the task in one sentence.
   - Decide whether the task is repo-local or cross-repo.

2. Claim ownership
   - Create a branch or worktree for the task.
   - Record the task in a dated file under `docs/plans/` if the work is more
     than a quick single-file tweak.
   - Note the owner agent and the file or subsystem boundary.

3. Gather local context
   - Read only the files needed for the task.
   - Check for existing plans, related tests, and generated artifacts.
   - If another agent recently touched the same area, read its handoff first.

4. Implement
   - Keep changes scoped to the claimed area.
   - Avoid concurrent edits on the same file by multiple agents.
   - If the work changes an artifact contract, update docs and tests in the
     same change set.

5. Verify
   - Run targeted tests.
   - Run syntax or compile checks if applicable.
   - For scraping changes, validate against a fixture or safe live target when
     possible.

6. Handoff or merge
   - Use [docs/agent_handoff_template.md](agent_handoff_template.md)
     for any non-trivial pass to another agent.
   - If the task is complete, include verification evidence in the final note.

## When To Split Work Across Agents

Split the task if:
- one part is research-heavy and another is implementation-heavy
- one agent needs a long-running manual browser flow while another can work on
  downstream consumers
- the change spans distinct ownership boundaries, such as scraper code vs
  downstream schema consumers

Do not split the task if:
- two agents would edit the same file set
- the integration risk is higher than the benefit from parallelism

## Cross-Repo Workflow

When work spans `notion-autopublish` and `fundman-jarvis`:
- finish and verify the upstream artifact in this repo first
- record the artifact path and fields that downstream code will consume
- then hand off or implement the downstream consumer
- avoid making both repos depend on undocumented implicit behavior

## Branch and Worktree Guidance

- Prefer one worktree per active agent if several agents are running in
  parallel.
- Name branches by date and topic, for example:
  - `2026-03-16-macromicro-industry-research`
  - `2026-03-16-p-model-freshness`

## Definition Of Done

The task is not done until:
- the change is documented enough for another agent to continue
- verification has been run
- any downstream impact is called out explicitly
