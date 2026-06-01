# course-backup — Artifact Layout / Manifest / Sync 契約

## 目錄結構

全部寫到 repo 標準的 `scraped_data/` 之下（`SCRAPED_DIR`，定義於 `browser/base.py`）：

```
scraped_data/courses/<platform>/<course-slug>/
  manifest.json
  modules/
    01-<module-slug>/
      <lesson-slug>-<id6>/                    # slug 由 lesson id 派生，重命名不會搬家
        lesson.md                              # 清過的文字 / lesson body
        lesson.<old_captured_at>.md            # 改過版本後，舊的這樣保留
        transcript.md                          # 字幕 / transcript（有就拿）
        video.url.txt                          # 影片來源 URL；下不下載看方案允許
        resources/                             # PDF、slides、worksheets、audio
        meta.json                              # per-lesson source URL / type / hash / captured_at
```

- `<platform>` ∈ `skool | kajabi | teachify | teachable | other`
- slug 全小寫、連字號、**穩定**：從 lesson 的 stable ID 派生（`stable_lesson_slug()`），所以課程改名不會被當成新 lesson、不會在 disk 上搬家
- 數字 prefix 保住順序，disk 看就是課程順序

## `manifest.json` schema

```json
{
  "platform": "skool",
  "course_slug": "example-course",
  "course_title": "Example Course",
  "source_url": "https://...",
  "first_backed_up_at": "2026-05-25T08:00:00Z",
  "last_synced_at": "2026-05-25T08:00:00Z",
  "lesson_count": 42,
  "lessons": [
    {
      "id": "stable-platform-id",
      "module": "01-getting-started",
      "slug": "welcome-abc123",
      "title": "Welcome",
      "type": "video|text|resource|quiz",
      "path": "modules/01-getting-started/welcome-abc123/",
      "source_url": "https://...",
      "content_hash": "sha256:...",
      "status": "active|retired|failed",
      "captured_at": "2026-05-25T08:00:00Z"
    }
  ],
  "sync_history": [
    {
      "synced_at": "2026-05-25T08:00:00Z",
      "added": 0,
      "updated": 0,
      "retired": 0,
      "failed": 0
    }
  ]
}
```

`content_hash` 是 **body + 排序後的 resource URL list** 的 SHA-256，所以：
- 改文字 / 換附件 → hash 變 → 標 changed
- 純改 title / 換 module → hash 不變 → 標 unchanged，但 manifest 的 title 仍會跟著刷新

## 每週 diff / sync 契約

1. 重新爬一次線上結構 → in-memory tree
2. 用 lesson `id` 對 manifest 配對（fallback：source URL）
3. 分類：
   - **new** — 線上有、manifest 沒 → 下載、append
   - **changed** — `content_hash` 不同 → 重抓寫回同一路徑，`captured_at` 更新，舊 `lesson.md` 改名成 `lesson.<old_captured_at>.md` 保留（**不靜默蓋掉**）
   - **retired** — manifest 有、線上沒 → `status: retired`，**檔案全留**
   - **unchanged** — 跳過下載；只刷新 manifest 上的 title / module（線上改名也跟上）
4. 寫一筆 `sync_history`、刷新 `last_synced_at`
5. 抓到一半噴錯的 lesson → `status: failed`，下次 sync 只重試這些

> Sync 預設 **加法、不刪**。要刪檔，使用者明講才做。

## 平台註記

- **Skool** — community + classroom。Classroom tree 是備份範圍；社群貼文不在 scope，除非使用者另外要。Lesson permalink 通常帶穩定 ID（`?md=` 或 `/lesson/<id>`），實作見 `course_skool._lesson_id_from_url`。
- **Kajabi** — Products → Categories → Lessons；每課掛 downloadable resources。
- **Teachify / Teachable** — chapter / lecture；影片常嵌 Wistia / Vimeo — 優先用平台自己的 download / transcript。
- 影片下載不被方案允許時：寫 `video.url.txt`（canonical URL）+ 抓 transcript 就好，**不要繞限制**。

## 授權邊界

這個 archive 給 **報名使用者本人** 的 **個人學習 + 非商業** 再用（知識庫 / AI coach / 自學）。**不可** 轉售、再發布、公開分享。
講師的 AI / 分享授權有疑問時，**先丟回去問使用者**，不要自己決定 — 這條跟 source 文章拉的線是一樣的。
