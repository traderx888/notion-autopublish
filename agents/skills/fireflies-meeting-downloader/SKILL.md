---
name: fireflies-meeting-downloader
description: Download meeting recordings, transcripts, and AI summaries from Fireflies.ai via its GraphQL API into a local archive. Use when backing up recorded meetings, preserving decisions and action items before they get buried, or feeding meeting transcripts into a knowledge base / AI coach.
---

# fireflies-meeting-downloader（小備 — 會議備份）

小備在「會議」這條線的工作。

>> 會議錄了沒然後，重要決策永遠淹沒 <<

把 Fireflies 已經錄起來的會抓下來，存到本地。決策、行動項、誰講了什麼，從會議裡撈回來變可查、可餵 AI、可派工。

## Scope

- 用使用者自己的 `FIREFLIES_API_KEY`（放 `.env`，不要硬編）
- 只備份使用者自己 / 自己團隊的會。錄音時的揭露 / 同意是 capture 階段就處理過的事，這個 skill 只負責 **取已有的 transcript**
- Transcript 是敏感資料：留在 `scraped_data/`，不自動推到任何公開出口

## 工作流

1. **認證**：讀 `FIREFLIES_API_KEY`。Fireflies API 是 GraphQL，endpoint `https://api.fireflies.ai/graphql`，header `Authorization: Bearer <key>`。
2. **List transcripts**：查 `transcripts` connection，預設範圍 = 比 last archived `date` 新的會。Paginate，記 `id`、`title`、`date`、`duration`、`participants`。
3. **Fetch each meeting**（by `id`）：
   - `sentences`（speaker、text、timestamp）
   - `summary` block（overview、action_items、keywords、bullet_gist）
   - recording / audio URL（有提供就拿）
4. **寫到 `scraped_data/meetings/<YYYY-MM-DD>-<slug>/`**：
   - `transcript.md` — speaker + timestamp
   - `summary.md` — overview + **action items** + decisions + keywords
   - `meta.json` — id、date、duration、participants、source URLs
   - `recording.url.txt` — 有的話
5. **Rolling index** `scraped_data/meetings/index.json`（id → path、date）— 再跑只抓沒抓過的會
6. **回報** 新進來的會 + 把開放中的 action items 浮上來，讓使用者可以接到主線任務

## 串接

- **chief-of-staff（小流）**— 把 summary + decisions 寫成復盤 / 決策備忘
- **NotebookLM ingest** — notebook 指到 `scraped_data/meetings/`，可以跨會議查

## 註記

- Fireflies 免費方案有歷史長度限制 → 主動往前備，不要假設舊會永遠抓得到
- 遇 rate limit → backoff + 從 rolling index 續跑（流程設計就是可中斷可續跑的）
