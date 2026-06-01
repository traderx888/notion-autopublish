---
name: youtube-smart-transcript
description: Capture a single YouTube video's transcript and turn it into a clean, structured knowledge extraction (summary, key points, quotes, action items) saved locally. Use when pulling the substance out of one video, processing a saved-for-later link, or producing a transcript artifact for further writing or NotebookLM ingest.
---

# youtube-smart-transcript（小備 — 單支影片萃取）

小備在「單支影片」這條線的工作。

不是 raw 逐字稿 dump，是 **smart** transcript：清過的內容 + 結構化萃取，看完就能用。
走路也能學的那一層。

整個頻道想灌進 NotebookLM → 走 `youtube-channel-to-notebooklm`。

## 工作流

1. **Resolve**：吃 URL 或 `video_id`。記 `title`、`channel`、`published_at`、`duration`
2. **抓 transcript**：
   - 優先用影片本身的字幕 / transcript track
   - 沒有 → fallback 走 audio transcription
   - 有 speaker / timestamp 就保留結構
3. **清乾淨**：拿掉 `[Music]`、重複行、贅字；明顯的 ASR 錯誤改回來；切成可讀的段落
4. **結構化萃取**：
   - 一段話 **summary**
   - **key points**（bullet，照影片自己的邏輯順序）
   - 重點 **quotes** + timestamp
   - **action items / takeaways**（使用者能套到自己工作流的）
   - **open questions**（值得追下去的）
5. **寫到 `scraped_data/youtube/<video_id>/`**：
   - `transcript.txt` — 清過的全文
   - `<video_id>.json` — metadata + 結構化萃取
   - `extract.md` — 人讀版（summary + key points + quotes + actions）
6. **回報** summary 直接 inline + artifact paths

## Scope

- 公開影片優先；access-gated 內容只用使用者自己的 session 而且權限要對
- **忠於來源**：claims、quotes、數字都要對得回 transcript，不要編

## 串接

- **youtube-channel-to-notebooklm** — 這個 skill 是它的 per-video fallback
- **threads-writer（小脆）**— takeaways 直接改寫成貼文
- **chief-of-staff（小流）**— key points 折進長文 synthesis
