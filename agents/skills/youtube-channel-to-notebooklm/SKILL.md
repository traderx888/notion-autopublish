---
name: youtube-channel-to-notebooklm
description: Mirror an entire YouTube channel (or playlist) into a NotebookLM notebook so the whole body of work becomes queryable as one knowledge base. Use when a creator's channel is worth studying end-to-end, when turning a backlog of saved videos into an AI-queryable source, or when building a per-creator NotebookLM coach.
---

# youtube-channel-to-notebooklm（小備 — 頻道級備份）

小備在「整個頻道」這條線的工作。

>> YouTube 收藏一堆，永遠下次看 <<

單支影片改寫成貼文 → 走 `youtube-smart-transcript`。整個頻道想當一個知識庫慢慢查 → 走這個 skill。把頻道整個丟進一本 NotebookLM，從 200 個收藏變成 1 個可以對話的 source。

接 repo 既有的 NotebookLM 整合（見 README 的 NotebookLM 段、`fundamental_research/notebooklm_research.py`）。

## Setup（一次性）

```bash
pip install "notebooklm-py[browser]"
python -m notebooklm login          # 開瀏覽器登 Google
```

- 在 notebooklm.google.com 為這個頻道建一個 notebook，從 URL 拿 ID（`.../notebook/<NOTEBOOK_ID>`）
- 可選：`NOTEBOOKLM_STORAGE_PATH` 控制 session cookie 路徑。Session 約 1-2 小時會過期，掉了就重跑 `python -m notebooklm login`

## 工作流

1. **解析 channel / playlist** → 完整影片清單（newest → oldest）。記 `video_id`、`title`、`published_at`
2. **載入 sync ledger** `scraped_data/youtube/channels/<channel-slug>/synced.json`（video_id → added_at）— 同 repo NotebookLM 整合用的去重 pattern（`canonicalize_source_url` / `find_source_by_url`）
3. **逐支 add 為 NotebookLM source**（`NotebookLMClient`）：
   - 優先丟 YouTube URL
   - URL 被拒（少見）→ fallback 用 `youtube-smart-transcript` 抓 transcript 丟上去
4. **更新 ledger** + 寫 channel `manifest.json`（channel title、notebook_id、counts、last_synced_at）
5. **回報** added / skipped，把 notebook URL 給使用者直接去查

## Scope

- NotebookLM 是 **歷史脈絡的副本**，不是唯一備份：source list / ledger 留在 `scraped_data/`，notebook 掉了不會全沒
- 只跑公開影片；會員制 / 付費影片不在這個 skill 的 scope
- 預設 channel notebook env var（例：`YOUTUBE_CHANNEL_NOTEBOOKLM_NOTEBOOK_ID`），跟 repo 既有的 `*_NOTEBOOKLM_NOTEBOOK_ID` 慣例一致 — 不用每次 pass

## 串接

- **youtube-smart-transcript** — 單支 transcript 抓取 + per-video extraction（也是這個 skill 的 fallback）
- **chief-of-staff（小流）／ course-designer（小課）**— 對 channel notebook 提問，產出 synthesis / 教學素材
