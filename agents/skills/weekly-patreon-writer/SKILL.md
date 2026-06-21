---
name: weekly-patreon-writer
description: Produce a weekly Patreon-ready long-form draft by pulling this week's Notion research notes (workspace-wide by date), this week's local files under a configured root (e.g. C:\blp\data Bloomberg exports), letting chief-of-staff (小流) synthesize, and copy-reviewer (小文) review — staged on the Notion Content Calendar with Status=`In progress`. Use when running the weekly Patreon write-up cycle, drafting a Sunday weekly digest, or turning the week's scattered research into one publishable piece.
---

# weekly-patreon-writer（週復盤 / 週 Patreon 草稿）

把 **這週** 散落在 Notion 各處 + `C:\blp\data` 的東西，撈出來 → 小流合稿 → 小文審 → 變成可發布的 Patreon 草稿。

>> 融入日常，知識此刻才有價值 <<

**不要** 把整個 backlog 灌進來。一次只跑一週。

## Scope

- 來源 = **這週**（預設 Mon → Sun HKT）的：
  - **Notion**：workspace-wide 搜，不綁單一 page；按 created/last-edited date 過濾
  - **本地**：`C:\blp\data`（Bloomberg exports）或其他 `--root` 路徑，按 mtime 過濾
- **過濾掉**：純內部會議記錄（infra / 系統 setup / 排程討論）、純個人 task list、操作 cheat sheet — 這些不是 Patreon 素材
- **留下**：market view、deep dive、interview content、名人 digest 候選、本週重點數據
- 草稿 staging：Notion Content Calendar 變 `Status = In progress`（= 草稿 / 待 review）。**不要** 自己改去 `Published` — 那是 user 過完稿才動

### Content Calendar canonical IDs

Workspace 有兩個 Content Calendar — **只用新那個**：
- DB: `12b3caa8-a487-8049-8baa-d010e7b6fb29`
- Data source: `12b3caa8-a487-815e-a65f-000bd8adfad6`
- URL: https://app.notion.com/p/12b3caa8a48780498baad010e7b6fb29

舊那個 `5c6b531d-a701-4543-8be5-6366b12f26ca`（2026-02 last-edited）不要寫進去。

### Status 選項（真實 schema）

只有四個：`Not started`（紅）/ `In progress`（黃）/ `Published`（綠）/ `Archive`（灰）。沒有 `Draft`、沒有 `Ready`。對應：
- 寫稿中 / 待小文 review → `In progress`
- 小文 pass + user 過 → user 自己改 `Published`，agent 不動

## 工作流

### 1. 框定週

預設 ISO 週（Mon-Sun）：
- `since = 本週一 00:00 HKT`
- `until = 下週一 00:00 HKT`

`docs/handoffs/` 看上週的 handoff（如果有），確認上次跑到哪。

### 2. 拉 Notion 這週

用 Notion MCP `notion-search`：
- `query_type: "internal"`
- `filters.created_date_range.start_date: <since>`
- **不要** 給 `page_url`（要 workspace-wide）
- 分批用 keyword：`market` / `update` / `report` / `analysis` / 行業 ticker / 個股

對每個 hit 跑 `notion-fetch`，看 ancestor-path 過濾掉內部會議 parent（例如 `ERNST` / `Task List` / `Vector house` 這類運營 parent — 但這判斷靠你看 parent path 的命名）。

把留下的存成 `outputs/weekly/<YYYY-Www>-notion-bundle.md`，每篇一個 section：標題、parent path、source URL、TL;DR、原文重點摘錄。

### 3. 拉本地這週

在 Windows 上跑：
```bash
python tools/weekly_patreon_writer.py \
    --root "C:\blp\data" \
    --since YYYY-MM-DD --until YYYY-MM-DD \
    --out outputs/weekly/<YYYY-Www>-blp-bundle.md
```

Default window = 過去 7 天。
Script 會掃 `--root` 下這週改過的檔：
- **PDF**（BBG / GS / BofA exports）：透過 `tools.bloomberg_pdf_convert` 共用 helper 抽文字（pypdf）+ 剝 disclaimer + 從檔名抽 `#topic` 標籤 + 抽 title。`PDF_MAX_BYTES` 25MB 上限。萃取失敗只記 metadata，**不會中斷整個 bundle**。
- **文字類**（`.md` `.txt` `.csv` `.json` …）：直接嵌 UTF-8 head。
- **其他**：metadata only。

bundle 推 commit 上 PR branch（不要 paste 內容，太長）— 我這邊 `git checkout <commit> -- outputs/weekly/<YYYY-Www>-blp-bundle.md` 就能拿到。

### 4. 小流合稿

用 `chief-of-staff` skill。Spine 一句話講完。Source 兩個 bundle。

格式參考（沿用使用者既有 Patreon 體例，見 `第 119 期 v2 · CMI` 那種骨架）：
- 結論先行
- 核心數據快照（如果有數據）
- 2-4 個 section（一條 thesis 一節）
- 紅隊推演（自己反駁自己）
- 三條情境（Bull / Base / Bear，附機率與目標價）
- 操作配置
- 下週監察清單

長度：本週若是 deep dive，1500-2500 字；若是 weekly digest，800-1500 字。

寫到 `outputs/weekly/<YYYY-Www>-draft.md`。

### 5. 小文審稿

跑 `copy-reviewer` skill。pass / revise verdict。Revise 就 line-level 改回 draft，重審。

### 6. Stage 到 Notion

`notion-create-pages` 到 data source `12b3caa8-a487-815e-a65f-000bd8adfad6`（or `notion-update-page` 若是改既有 row）。Properties：

- `Post Title`：標題（剝掉 markdown H1 — 由 properties 承載）
- `Post Description`：1-2 句 summary（會在 Calendar 列表顯示）
- `Status`：**`In progress`**（不是字面 `Draft`，schema 沒這選項）
- `Article`：`__YES__`（這是 Patreon 文，勾上）
- `Purpose`：通常 `Community`（Patreon = 支持者社群）；偶爾用 `Discoverability` 或 `Conversion`
- `Publish Day`：對應日（e.g. `Sunday`）
- `date:Publish Date:start`：ISO date，提議下週某天（user 可改）
- `date:Publish Date:is_datetime`：`0`（單日，不含時間）

Body：放完整 markdown draft，**剝掉 H1 + status preamble**（由 properties 承載）。Source URLs 留在 body 底，連 repo 內 `outputs/weekly/<YYYY-Www>-draft.md` 跟 `*-blp-bundle.md` 路徑。

**不要** 改 `Status = Published` — 那是 user 過完稿才動。

### 7. Handoff

`tools/agent_note.py handoff --slug weekly-patreon-<YYYY-Www>`，記：
- 這週 source 用了哪幾篇
- 草稿路徑
- 小文 verdict
- 下週要追的線索

## Scope Rules

- 一次跑一週 — 過去的 backlog 不在這 skill 的 scope（要做歷史補檔，另開 batch task）
- 不自動發布；不自己改 Notion `Status = Published`
- Source 不夠寫不出 spine 時 → 老實寫「本週素材不足以撐起一篇 weekly」，不要硬擠。寧可寫個 200 字短文 stage 給 Threads（交給 `threads-writer`）

## 串接

- **upstream**：Notion workspace、`C:\blp\data` 或同等 local research root
- **synthesis**：`chief-of-staff`（小流）
- **gate**：`copy-reviewer`（小文）
- **降短形**：素材不夠長 → `threads-writer`（小脆）
- **publish**：repo 既有 `publish.py` flow（Threads / LinkedIn / Patreon）
