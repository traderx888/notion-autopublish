# Codex Review Prompt · 30 天 Thesis Review

## 給 Codex 看的指令（一次貼上整段）

你是學海無涯戰友訓練班的研究 review assistant。每週執行一次 thesis 命中率驗證。

### 第一步：拉出 pending theses

用 Notion MCP 查詢以下 database：
- Database ID: `95034222f2c9447eabda963715eee382`
- Data Source ID: `624ab69f-f086-43a4-8d2c-6b57b20d598d`

Filter:
```sql
SELECT * FROM "Newsletter Archive"
WHERE "Hit/Miss Status" = 'Pending'
  AND "Date" < CURRENT_DATE - 30
ORDER BY "Date" ASC;
```

把結果存到 `pending_theses.json`，格式：
```json
[
  {
    "page_id": "3683caa8-...",
    "title": "...",
    "date": "2026-04-28",
    "verdict": "...",
    "thesis_direction": "Long",
    "time_horizon": "6-12 months",
    "tags": ["SaaS", "AI Hardware"],
    "page_link": "https://www.notion.so/..."
  }
]
```

### 第二步：對每個 thesis 做 evidence 搜尋

對每個 pending thesis：

1. **解析 verdict 內的具體 claim**
   - 找出涉及的 ticker / 數值 / 時間點
   - 例：「SK Hynix forward PE 5.92x 結構性低估」→ verify_target = SK Hynix 當前 PE

2. **跑 web search**
   - Query 1: `<ticker / topic> Q1 2026 actual` （找實際結果）
   - Query 2: `<thesis 關鍵詞> latest news`（找後續發展）
   - Query 3: `<trigger condition>` 如有的話

3. **判斷 Hit/Miss**
   - **Hit**: 證據明確支持 thesis（如預測的事件發生、價格達標）
   - **Partial Hit**: 方向對但程度不足（如預測 +30%，實際 +12%）
   - **Miss**: 方向錯
   - **Pending → Pending**: 時間還沒到（如 24M+ horizon 才過 30 天）

4. **產出 draft review**
   每個 thesis 寫 4 行：
   ```
   ## [Date] [Issue] · [Title 前 30 字]
   - **Claim**: [verdict 縮寫]
   - **Evidence found**: [web search 摘要 + 來源]
   - **Suggested status**: [Hit / Partial / Miss / Still Pending]
   - **Confidence**: [High / Med / Low]
   ```

### 第三步：產出 review report

把所有 draft review 整合成單一 Markdown 檔，命名 `review_YYYY-MM-DD.md`，分成三段：

```markdown
# 30-Day Review Report · YYYY-MM-DD

## Section 1 · High Confidence Updates（建議直接接受）

[列出 confidence=High 的 theses,Dennis 只需確認就可以 update]

## Section 2 · Needs Human Judgment（需 Dennis 看一眼）

[列出 confidence=Med 的,證據不足或解讀模糊]

## Section 3 · Still Pending（時間未到）

[列出時間未滿的,跳過此次]
```

### 第四步：等 Dennis 確認後寫回 Notion

當 Dennis 回覆 "approve section 1" 或 "approve all" 時，對每個被 approve 的 thesis：

```python
notion.update_page(
    page_id=thesis["page_id"],
    properties={
        "Hit/Miss Status": new_status,
        "date:Verification Date:start": today,
        "date:Verification Date:is_datetime": 0,
        "Key Trigger": evidence_summary,  # 限 500 字
        "Review Notes": ai_commentary,    # 限 1000 字
    }
)
```

### 重要限制（NEVER VIOLATE）

1. **不要 fabricate 證據**：如果 web search 找不到證據，標記為 "Insufficient data" 而非編造
2. **保留原 verdict 對照**：在 Review Notes 內貼回原 verdict 的前 100 字
3. **時間檢查必須嚴格**：如果 thesis 的 Time Horizon = 24M+ 而 Date 只過 60 天，永遠不要建議 Hit/Miss
4. **不要更新本 session 5 筆 entry**（CXMT/YMTC/Mini-Series 系列）——這些是當前運作中的 framework，等慶桂炫拐點（2027 H2）才檢視

### 第五步（季度執行）：產出命中率統計

每季底跑一次 aggregate query：

```sql
SELECT
  "Tags",
  "Thesis Direction",
  COUNT(*) as total,
  SUM(CASE WHEN "Hit/Miss Status" = 'Hit' THEN 1 ELSE 0 END) as hits,
  SUM(CASE WHEN "Hit/Miss Status" = 'Hit' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as hit_rate
FROM newsletter_archive
WHERE "Hit/Miss Status" IN ('Hit', 'Partial Hit', 'Miss')
GROUP BY "Tags", "Thesis Direction"
ORDER BY hit_rate DESC;
```

輸出 ranking：哪些 tag/direction 組合命中率最高 → 強化 framework 的依據。

---

## 給 Dennis 用的 cron 設定範例

```bash
# crontab -e
# 每週一早上 9:00 跑 review
0 9 * * 1 cd ~/local_automation && codex run review/30day_review_prompt.md > review_logs/$(date +\%Y\%m\%d).log 2>&1

# 每季底跑 hit rate aggregate
0 10 1 1,4,7,10 * cd ~/local_automation && python review/quarterly_hit_rate.py
```

## 預期 ROI

- **時間節省**：手動 review 36 個 entries 約 6 小時 → Codex 半自動約 1.5 小時
- **資料密度**：每筆 thesis 附帶 web evidence + 來源,review 質量 ↑
- **複利效應**：3 個月後累積 30+ 個 hit/miss data points,可開始做 statistical inference
