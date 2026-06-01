# 學海無涯 Local Automation 完整架構與限制

## 兩個 Workflow 的本質差異

### Workflow A · Codex Review（30 天評估）

**核心邏輯**：用 LLM 對「事件型 thesis」做 evidence-based judgement

**適合的 thesis 類型**：
- ✅ **事件預測**：「Warsh 上任後 30Y 站穩 5%」→ 查 30Y 實際走勢
- ✅ **政策走勢**：「Hormuz 重新封鎖 → 油價 $120」→ 查油價 + 封鎖事件
- ✅ **公司動作**：「CXMT HBM3 量產延遲」→ 查 DIGITIMES 最新報導
- ✅ **市場狀態**：「LTA 鎖定西方產能」→ 查最新 HBM 合約新聞

**不適合的**：
- ❌ Educational tutorials (沒 thesis 可驗證)
- ❌ Framework 整合（Mini-Series）

### Workflow B · Backtest（量化回測）

**核心邏輯**：用實際股價驗證「方向性 trade thesis」

**適合的**：
- ✅ Long single ticker（「Micron 目標 $840」）
- ✅ Short single ticker（「TLT 空頭」）
- ✅ Pair Trade（「Long SK Hynix / Short Samsung」）

**不適合的**：
- ❌ 沒明確 ticker（「中國威脅評估」是 framework）
- ❌ Hedge thesis（沒 unidirectional return 可量化）
- ❌ Multi-Strategy（含太多 leg 難 isolate）
- ❌ Educational content

---

## 為什麼 Codex 能做 Review 卻不能完整做 Backtest

**Codex MCP 限制**：
- Notion MCP 支援 query / update → ✅ review 可用
- Notion MCP 不能跑長時間 price data download → ❌ backtest 需 Python
- LLM 對 quantitative comparison 容易 hallucinate → ❌ alpha 計算需精確

**結論**：
- Review = Codex 內完成（用 web search + Notion update）
- Backtest = Python script + Notion API（Codex 可協助寫 query 但不負責計算）

---

## 數據可靠性與限制

### Codex Review 的可靠性

**強項**：
- News-based evidence 對短期 thesis（1-3 month）很準
- Web search 找官方公告、財報 confirmations 準確

**弱項**：
- 對「結構性 framework」很難 grade（因為沒 binary outcome）
- 容易 over-confidence（建議 confidence flag）

**建議使用**：
- 對 Time Horizon = 1-3 months / 3-6 months 的 thesis 用 Codex review
- 對 12-24 months / 24M+ 的暫時跳過（等更多時間）

### Backtest 的可靠性

**強項**：
- 股價是 ground truth，alpha 計算客觀
- 大樣本累積後可做 statistical inference

**弱項**：
- **Sample size 太小**：36 個 entries 中只有 ~20 個可 backtest，且時間軸不一致
- **Benchmark mismatch**：HK 股配 SPY 不對等，需 mapping 到 HSI / EWY 等
- **Time horizon 對齊**：thesis publish date 不等於 entry date，可能造成「entry shift bias」
- **Pair trade 複雜**：long leg + short leg 需要分別處理 + spread calc

**建議改善**：
- 至少累積 60 個 entries 再做 statistical inference
- 用 multiple benchmarks（SPY、HSI、EWY、SOXX）按 Asset Class 動態 mapping
- 對 Pair Trade 用 spread return 而非 net return

---

## Backtest 進階：建議實現的功能

### Phase 1 · MVP（已寫好 skeleton）
- 拉 pending theses
- yfinance 拉股價
- 計算 raw return + benchmark alpha
- 寫回 Notion

### Phase 2 · Benchmark Mapping
- 按 Asset Class 動態選 benchmark：
  - US Equity → SPY
  - HK Equity → 2800.HK
  - Korean Equity → EWY
  - Memory/Semis → SOXX
  - A-Share → 510300.SS
  - Crypto → BTC-USD

### Phase 3 · Risk-Adjusted Metrics
- 不只算 raw alpha，加入：
  - Sharpe（return / vol）
  - Max drawdown
  - Time to peak

### Phase 4 · Confidence Weighting
- 對「高 confidence」thesis 給高 weight
- 用 Direction 細分：
  - Long: hit if alpha > +5%
  - Short: hit if return < -5%
  - Pair Trade: hit if spread > +3%

### Phase 5 · LLM-Augmented Parsing
- 目前 ticker extraction 是 regex-based,弱
- 升級為「LLM 解析 verdict → 結構化 trade plan」
- 例：「Long Micron / Short Western Digital」→ JSON `{"long": ["MU"], "short": ["WDC"]}`

---

## 與你現有 v3 Pipeline 的整合

```
你目前的流程
  ↓
v3 Pipeline (HTML/PDF/Telegram/Threads/Patreon/YouTube)
  ↓
Notion Database entry（手動 or 自動）
  ↓ (30 天後)
Codex Review (找證據 + update Hit/Miss)
  ↓ (季度)
Backtest Python (量化 alpha + 寫回 Review Notes)
  ↓ (累積 60+ entries 後)
Framework Calibration（哪些 Tag/Direction 命中率最高）
  ↓
強化下次 newsletter 的 thesis 構建
```

**這就是「人寫 newsletter → AI 自動 review → 累積資料 → 強化判斷」的完整閉環。**

---

## 立即可做的下一步

### 你的 immediate action（今天）

1. **裝 Codex CLI + Notion MCP**（如果還沒裝）
   ```bash
   npm install -g @openai/codex
   codex mcp add notion https://mcp.notion.com/mcp
   ```

2. **設環境變數**
   ```bash
   export NOTION_TOKEN="ntn_xxxxx"  # 從 https://www.notion.so/profile/integrations 取
   export NOTION_DB_ID="95034222f2c9447eabda963715eee382"
   ```

3. **裝 Python deps**
   ```bash
   pip install yfinance pandas notion-client tabulate
   ```

4. **測試 backtest skeleton（dry run）**
   ```bash
   python backtest/run_backtest.py --start 2026-04-28 --end 2026-05-22
   # 不會更新 Notion,只 print 結果
   ```

### 1 週內 action

5. **在 Codex 內手動跑一次 review prompt**（檢驗品質）
6. **觀察哪些 thesis 跳過率高**（指向 ticker extraction 需強化）
7. **微調 prompt template**（根據第一次跑的結果）

### 1 個月內 action

8. **設 cron job 自動週度 review**
9. **每週手動 confirm 一次 review 結果**
10. **積累 8 週後跑第一次 quarterly aggregate**

### 3-6 個月後

11. **跑完整 backtest with proper benchmark mapping**
12. **首次 framework calibration**（哪些 tag/direction 命中率最高）
13. **將結果寫進新的 Mini-Series（教戰友怎麼用 AI 做 review）**

---

## 教材化的價值

這套系統本身就是極好的「我要做富翁 × James AI 課程」材料：

| 課程模組 | 對應 deliverable |
|---|---|
| M1 · AI 研究系統搭建 | Notion DB schema + Codex setup |
| M2 · 自動化 Review | 30day_review_prompt.md |
| M3 · 量化驗證 | run_backtest.py |
| M4 · Framework Calibration | quarterly_hit_rate.py（待寫）|
| M5 · 從判斷到資料的閉環 | 完整 architecture |

**這份 toolkit 比一份 newsletter 更值錢——因為它讓任何訂閱戶都能複製你的研究方法論。**

---

## 限制與誠實聲明

1. **此系統不會讓你的判斷自動變好**——只是把你的判斷「結構化記錄」並「事後驗證」
2. **Backtest 永遠是 lookback bias** ——你的 thesis 寫的時候不知道後續發展，但 backtest 是後見之明
3. **Sample size 至少 60 才能說 statistical inference**——36 個 entries 還不夠
4. **Codex review 仍需 human-in-the-loop** ——LLM 對複雜 macro thesis 容易誤判
5. **股價 ≠ thesis 命中**——例如「Long Micron」可能 stock 漲了但 thesis（HBM 售罄）其實沒驗證

這套系統的價值不在「自動賺錢」，而在 **「把 6 個月以後的自己變成 6 個月以前自己的審判官」**。
