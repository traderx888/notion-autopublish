# AI Employee Course Workflow Skills Plan

**Goal:** Stand up the full set of "AI employee" skills that implement the
backup → knowledge → output/action workflow, so each persona (小備, 小脆,
小文, 小流, 小課) has a concrete, repo-resident `SKILL.md` that Claude Code can
discover and execute.

**Owner:** Claude Code

**Scope:** Repo-local. New skill folders under `agents/skills/` plus this plan.
No change to scraper code, publish code, or generated artifact schemas, so no
`fundman-jarvis` impact. Skills describe how to drive *existing* tooling
(`browser/` Playwright automation, the `notebooklm` integration, the Notion →
Threads/LinkedIn/Patreon publish flow); where an implementation surface does not
yet exist (e.g. a course scraper subclass), the skill names that surface
explicitly instead of inventing a CLI command.

**Architecture:** Each skill follows the existing
`telegram-schedule-audit-expert` shape — a `SKILL.md` with `name` +
`description` frontmatter, a Workflow section, Scope Rules, and a Composes-With
note that wires the personas into one pipeline. The centerpiece `course-backup`
also gets a `references/backup-manifest.md` for the artifact layout, the weekly
diff/sync contract, and the authorized-use boundary the source essay raises.

**Tech Stack:** Markdown skills only. Referenced runtime: Python 3,
`browser/base.py` (`BrowserAutomation`, `SCRAPED_DIR`), the `notebooklm`
package + `python -m notebooklm login`, `publish.py` + Notion Content Calendar,
Fireflies GraphQL API.

---

### Task 1: Backup family (小備 / content-archivist)

**Files:**
- Create: `agents/skills/course-backup/SKILL.md`
- Create: `agents/skills/course-backup/references/backup-manifest.md`
- Create: `agents/skills/fireflies-meeting-downloader/SKILL.md`
- Create: `agents/skills/youtube-channel-to-notebooklm/SKILL.md`
- Create: `agents/skills/youtube-smart-transcript/SKILL.md`

**Steps:**
1. course-backup: drive a persistent browser session to enumerate and download
   course video/text/resources into `scraped_data/courses/`, emit a manifest,
   support weekly diff/sync, and enforce the personal/non-commercial boundary.
2. fireflies-meeting-downloader: pull meeting recordings + transcripts via the
   Fireflies GraphQL API into `scraped_data/meetings/`.
3. youtube-channel-to-notebooklm: sync a whole channel into a NotebookLM
   notebook using the repo's `notebooklm` integration.
4. youtube-smart-transcript: capture and clean a single video transcript into a
   structured extraction artifact.

### Task 2: Output / Action team (小脆, 小文, 小流, 小課)

**Files:**
- Create: `agents/skills/threads-writer/SKILL.md`
- Create: `agents/skills/copy-reviewer/SKILL.md`
- Create: `agents/skills/chief-of-staff/SKILL.md`
- Create: `agents/skills/course-designer/SKILL.md`

**Steps:**
1. threads-writer (小脆): rewrite extracted knowledge into Threads/social
   short-form, staged as Notion Content Calendar drafts for the publish flow.
2. copy-reviewer (小文): brand-voice review gate for all outward-facing copy.
3. chief-of-staff (小流): chief-of-staff long-form synthesis (blogs,
   retrospectives, decision memos).
4. course-designer (小課): curriculum, teaching content, and sales-page copy
   from backed-up/extracted knowledge.

### Task 3: Verify and record results

**Commands:**
- `python3 -c "import pathlib,yaml,sys; [yaml.safe_load(p.read_text().split('---')[1]) for p in pathlib.glob... ]"` — validate every `SKILL.md` frontmatter parses with `name` + `description`.
- `find agents/skills -name SKILL.md | sort` — confirm all 8 skills exist.

**Expected result:**
- 8 new skill folders, each with a `SKILL.md` whose frontmatter parses and
  carries a discovery-friendly `description`.
- course-backup additionally has `references/backup-manifest.md`.
