# AI 員工 — Course Workflow Skills Plan

**Goal:** 把「備份 → 知識萃取 → 輸出 / 行動」這條工作流，從個人 mental model
變成 repo 裡可 discover / 可執行的 8 個 AI 員工 skills；centerpiece
`course-backup` 同時把 scraper scaffolding（manifest + diff/sync 契約）一起
立起來，讓 skill 不只是 playbook，是真的跑得起來的工作流。

**Owner:** Claude Code

**Scope:** Repo-local。新增 `agents/skills/<name>/` 8 個、
`browser/scrapers/course.py` + `course_skool.py`、`browser/cli.py` 加一條
`scrape course` route、`tests/test_course_backup.py`、本 plan。
不動既有 scraper、publish.py、artifact schema → **沒有 fundman-jarvis 影響**。

`scraped_data/courses/<platform>/<course-slug>/` 是新的產物目錄，但 schema
是新的、沒有下游消費者，所以是 additive。

**Architecture:**
- Skill 端：每個 skill 一份 `SKILL.md`，沿用既有 `telegram-schedule-audit-expert`
  的 frontmatter + body 格式。Frontmatter `description` 留英文（skill discovery
  靠它），body 寫使用者言氣（CN/EN 混）。Centerpiece `course-backup` 多一份
  `references/backup-manifest.md`，把產物 layout、`manifest.json` schema、weekly
  diff/sync 契約、授權邊界寫清楚。
- 程式端：`browser/scrapers/course.py` 提供 `CourseScraper(BrowserAutomation)`
  抽象 base — 包 manifest / diff / sync 的全部 orchestration（不靠 live
  browser，可純測）。`browser/scrapers/course_skool.py` 是第一個 platform
  subclass，DOM selectors 標明 best-effort，有 fallback 走 `wait_for_user`
  的 manual walk，跑得起來但需使用者第一次跑時驗 selectors。
- CLI: `python -m browser scrape course --platform skool --course-url <url> [--sync] [--course-slug <slug>]`。

**Tech Stack:** Python 3 + `browser/base.py`（Playwright persistent session）
+ `requests`（resource 下載沿用 browser cookies）+ pytest（orchestration test）
+ Markdown skills。

---

### Task 1: 備份組 skills（小備 / content-archivist）

**Files:**
- Create: `agents/skills/course-backup/SKILL.md`
- Create: `agents/skills/course-backup/references/backup-manifest.md`
- Create: `agents/skills/fireflies-meeting-downloader/SKILL.md`
- Create: `agents/skills/youtube-channel-to-notebooklm/SKILL.md`
- Create: `agents/skills/youtube-smart-transcript/SKILL.md`

### Task 2: 輸出 / 行動組 skills（小脆、小文、小流、小課）

**Files:**
- Create: `agents/skills/threads-writer/SKILL.md`
- Create: `agents/skills/copy-reviewer/SKILL.md`
- Create: `agents/skills/chief-of-staff/SKILL.md`
- Create: `agents/skills/course-designer/SKILL.md`

### Task 3: course-backup scraper scaffolding

**Files:**
- Create: `browser/scrapers/course.py`（`CourseScraper` base + manifest/diff/sync orchestration）
- Create: `browser/scrapers/course_skool.py`（`SkoolCourseScraper` subclass，Playwright login + DOM 遍歷 + manual fallback）
- Modify: `browser/cli.py`（加 `course` service + `--platform/--course-url/--course-slug/--sync` flags）

### Task 4: Orchestration 測試（不需 live browser）

**Files:**
- Create: `tests/test_course_backup.py`

**Cover:**
- content hash 對 resource 順序不敏感、對 body 編輯敏感
- stable slug 在 rename 後仍指向同一個 lesson
- 首次跑 → 全部進 new
- 第二次跑（無異動）→ idempotent，sync_history 第二筆 0/0/0/0
- 改 body → changed，舊 `lesson.md` 自動保留為 `lesson.<timestamp>.md`
- 線上消失 lesson → retired，檔案不刪
- 純 rename（body 不變）→ unchanged 但 manifest title 跟著刷新
- capture exception → status=failed，sync_history `failed` +1

### Task 5: Verify

**Commands:**
- `python3 -m pytest tests/test_course_backup.py -v`
- `find agents/skills -name SKILL.md | sort`
- frontmatter 驗證：每個 `SKILL.md` 都解析得到 `name` + `description`

**Expected:**
- 14/14 test pass
- 9 個 SKILL.md（既有 1 + 新增 8），全部 frontmatter 有效
- `python -m browser scrape course --platform skool --course-url <url>` 在 CLI parser 解得開
