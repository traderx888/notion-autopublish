---
name: course-backup
description: Back up an enrolled online course (Skool, Kajabi, Teachify, Teachable, and similar platforms) including videos, text lessons, and downloadable resources, then keep the local archive in sync with a weekly diff scan. Use when archiving a paid course you have access to, preserving content before a platform or instructor shuts it down, mirroring lesson updates, or building a course knowledge base for later AI ingest (NotebookLM, an AI coach, or a derived skill).
---

# course-backup（小備 — 有價內容備份員 · 課程組）

整套工作流的起點。**先完整備份一門線上課程**，後面的「知識萃取 → 輸出 / 行動」才有東西可餵。

>> 一旦完整備份轉化成 Skills / Agents，未來才能持續重複融入於日常工作流中 <<

能解決的常見困擾：
- 線上課買了沒看，平台倒就沒了
- 退群、退課訊息消失
- 講師收掉平台課程
- 因沒空看課遲遲不敢取消訂閱（噗）
- 課程異動但知識庫沒跟著更新

## Scope（先讀這段）

- 只備份 **使用者本人合法報名／已付費** 的課程；用途為 **個人學習、非商業** 保存。
  要分享、轉售、再發布，先停下來確認講師有沒有寫 AI 應用 / 分享授權。
- 不繞 paywall、不破 DRM、不偷別人的 session。用使用者自己的登入。
- 備份是私有的。不要把課程影片 / 文字推到任何公開出口（`output/`、Notion publish flow、Threads），除非使用者明講。
- Sync 是 **加法**：絕對不靜默蓋掉之前的版本。先 diff 再寫，舊版本保留（見 `references/backup-manifest.md`）。

## 工作流

1. **鎖定目標**：平台（Skool / Kajabi / Teachify / Teachable / other）、course URL、course slug。判斷是首次完整備份還是每週同步。
2. **登入**：吃 repo 既有的 `browser/base.py` `BrowserAutomation`（persistent session、`--chrome` 沿用真實 Chrome profile 接 Google SSO、2FA 走 `wait_for_user` 手動）。實作面在 `browser/scrapers/course_<platform>.py`；Skool 已備（`SkoolCourseScraper`），其他平台照樣畫葫蘆。
3. **CLI 跑起來**：
   ```bash
   python -m browser scrape course --platform skool \
       --course-url https://www.skool.com/<community>/classroom/<course>
   # 每週同步：
   python -m browser scrape course --platform skool \
       --course-url https://www.skool.com/<community>/classroom/<course> --sync
   ```
4. **列出結構**：modules → lessons 整棵樹先抓下來（titles、order、URL、type），這樣中斷可以續跑。
5. **下載順序（脆弱的先抓）**：
   - downloadable resources（PDF、slides、worksheets、audio）→ 最容易消失
   - 文字 / lesson HTML → 清成 markdown
   - 影片 → 在使用者方案允許的最高畫質；有字幕 / transcript 一起拿
6. **寫到 `scraped_data/courses/<platform>/<course-slug>/`**，layout 跟 manifest schema 見 `references/backup-manifest.md`。
7. **每週同步 = diff，不是重抓**：重新列結構 → 跟 manifest 比對 → 只抓新的 / 改過的 → 消失的 lesson 標 `retired`（不刪檔）→ 寫一筆 `sync_history`。
8. **回報**：added / updated / retired / unchanged / failed 各幾筆、總大小、失敗的下次重試。

## 判斷要不要備份

滿足任一條就丟進小備的清單：
- 付費取得 / 學習時間成本高 / 個人關鍵決策 / 稀缺即將消失 / 值得回查

## 串接

- **youtube-smart-transcript / youtube-channel-to-notebooklm** — 課程影片掛在 YouTube 時用
- **NotebookLM ingest**（`python -m notebooklm login`，see README）— notebook 指到 `scraped_data/courses/.../` 的 markdown / transcript，備份直接變 AI coach
- **course-designer（小課）**— 把備份內容變成自己的課綱 / 銷售頁，閉環 backup → action

## References

- `references/backup-manifest.md` — 產物結構、`manifest.json` schema、每週 diff/sync 契約、平台註記、授權使用邊界
