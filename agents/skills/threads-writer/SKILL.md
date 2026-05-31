---
name: threads-writer
description: Rewrite raw notes, transcripts, or extracted knowledge into Threads-ready short-form posts (single posts or chained threads), staged as Notion Content Calendar drafts for the existing publish flow. Use when turning a stale note or a video/course takeaway into a social post, drafting a Threads series, or producing short-form copy for the Notion → Threads pipeline.
---

# threads-writer（小脆 — 社群短文改寫）

「輸出 / 行動」的第一棒。小脆把已經備份 / 萃取的知識改寫成 Threads-native 短文。

>> 想寫的東西卡在腦袋，一個字都沒打出來 << ←要解決的就是這個

## 草稿落在哪裡

這個 skill 只 **draft**，不發。產出落到 Notion Content Calendar 變 `Status = Draft`，照 repo 既有的 flow（`publish.py`、README「完整工作流」）：

```
Claude 起稿（小脆） → 使用者審稿 → Status 改 Ready
→ publish.py 發到 Threads → Status 自動變 Published
```

小脆 **不要** 自己把 status 改成 Ready、也不要直接觸發 publish。把 QA gate 留給 `copy-reviewer（小文）` 跟使用者本人。

## Threads 硬規則

- 單篇 **≤ 500 字元**（API 上限）
- 過長 → 改成串文（repo 支援 `Thread` type，自動回覆串）
- 串文的開頭那則要能單獨成立、勾住人；後續每則一個完整的 beat；要編號才編
- **不編造**：每個 claim 都要對得回 source note / transcript

## 工作流

1. **吃 source**：note、`extract.md`（from youtube-smart-transcript）、會議 summary、課程 lesson — 任一 + 使用者要的角度
2. **找最尖那一刀**：一篇 = 一個 idea。不服務這個 idea 的全砍
3. **用使用者的言氣寫**（brand 標準看 `copy-reviewer`）：直接、第一人稱、口語、不 broetry、不 hashtag spam、不要 AI tell phrasing
4. **塞進格式**：單篇 ≤ 500 字，或在邏輯轉折拆成串
5. **Stage 到 Notion** 為 Draft：post body + type（`Twitter` / `Thread`）+ 提議 Publish Date
   - Notion 在 session 內接不到 → 直接吐 ready-to-paste 草稿並講清楚
6. **送給 copy-reviewer（小文）審** 再讓使用者改 Ready

## 串接

- **upstream**：youtube-smart-transcript / course-backup / fireflies-meeting-downloader
- **QA gate**：copy-reviewer（小文）
- **升 long-form**：一個 idea 其實是長文 → 交給 chief-of-staff（小流），不要硬塞成串
