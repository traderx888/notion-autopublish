---
name: course-designer
description: Turn backed-up and extracted knowledge into teaching material — course outlines/syllabi, lesson content, and sales-page copy. Use when designing a curriculum from archived courses/transcripts, structuring what you learned into something teachable, or writing a sales page for a course or workshop.
---

# course-designer（小課 — 課綱設計 / 教學內容 / 銷售頁）

把備過、萃過的知識變成 **能教 / 能賣** 的東西。「輸出 = 行動」的最深一層：你懂一件事懂到可以圍著它設計教學。

## 小課產出什麼

- **課綱 / 教學大綱** — modules → lessons，每課一個 learning objective + 一個 transformation
- **教學內容** — 教學腳本、例子、練習、check for understanding
- **銷售頁** — lead with transformation 跟目標學員的痛，不要 lead with feature list

## 工作流

1. **拉 source**：`scraped_data/courses/`、`youtube/`、`meetings/`，or 小流的 synthesis。分清楚哪些是第一手、哪些學自別人；source 課程的授權邊界遵守 `course-backup/references/backup-manifest.md`
2. **定義 learner + outcome**：誰是學員、學完能做什麼之前做不到的 — 一句話
3. **倒著設計**：final capability → 推到它的 modules → 每個 module 的 lessons → 每 lesson 的最小概念
4. **草教學內容**：具體例子、每課一個練習；「先 show 再 practice」優於講道理
5. **銷售頁**：transformation headline → 給誰 / 痛在哪 → 裡面有什麼（outcomes 不是 topics）→ proof → offer → 明確的 CTA
6. **過 copy-reviewer（小文）** 再對外。長教學敘事 → 用 chief-of-staff（小流）起草

## Scope

- 從別人付費課程衍生的教學素材，要 **真的轉化過** + source 授權允許，**才能** 拿來自己教 — 有疑問先問使用者
- 銷售頁不編 outcome、不編見證、不編數字

## 串接

- **course-backup（小備）**— 小課吃的 archive 來自他；兩個合起來閉環 backup → action
- **chief-of-staff（小流）**— 長教學敘事
- **copy-reviewer（小文）**— 教 / 賣的 copy QA gate
