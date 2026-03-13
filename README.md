# 📤 Notion Auto Publisher

從 Notion Content Calendar 自動發布到 Threads / LinkedIn / Patreon。

```
Notion (Status=Ready + Publish Date=今天)
    ├── Twitter  → Threads API（單篇）
    ├── LinkedIn → LinkedIn API
    ├── Newsletter → Patreon API
    └── Thread   → Threads API（串文自動回覆）
    └── 成功 → Notion Status 自動改為 Published
```

---

## Quick Start

```bash
# 1. Clone & 安裝
git clone <your-repo-url>
cd notion-autopublish
pip install -r requirements.txt

# 2. 設定 API tokens
cp .env.example .env
# 用 VSCode 打開 .env 填入你的 tokens

# 3. 先用預覽模式測試
python publish.py --dry-run

# 4. 正式發布
python publish.py
```

---

## 取得 API Tokens

### 1️⃣ Notion Integration Token

1. 前往 https://www.notion.so/my-integrations
2. **New Integration** → 命名 `autopublish`
3. 複製 `ntn_` 開頭的 token → 填入 `.env` 的 `NOTION_TOKEN`
4. **重要**：回到 Content Calendar → 右上 `⋯` → Connections → 加入你的 Integration

```
NOTION_TOKEN=ntn_xxxxxxxxxxxxxxxxxxxx
NOTION_DATABASE_ID=cf022656-54bf-41ca-a77d-538d6c2675dc   # 已預設你的
```

### 2️⃣ Threads (Meta) API Token

1. 前往 https://developers.facebook.com/ → 建立 App → 類型選 **Business**
2. 在 App Dashboard → Add Products → 加入 **Threads API**
3. 進入 **Graph API Explorer**：
   - 選你的 App
   - 權限勾選：`threads_basic`, `threads_content_publish`
   - **Generate Access Token** → 這是短期 token（1 小時）

4. 取得 User ID：
```bash
curl "https://graph.threads.net/v1.0/me?access_token=你的短期TOKEN"
# 回傳的 id 就是 THREADS_USER_ID
```

5. 換成長期 token（60 天）：
```bash
curl "https://graph.threads.net/access_token?\
grant_type=th_exchange_token&\
client_secret=你的APP_SECRET&\
access_token=你的短期TOKEN"
```

6. 刷新長期 token（到期前執行）：
```bash
curl "https://graph.threads.net/refresh_access_token?\
grant_type=th_refresh_token&\
access_token=你的長期TOKEN"
```

```
THREADS_ACCESS_TOKEN=THQWxxxxxxxxxxxxxxxxx
THREADS_USER_ID=12345678901234567
```

### 3️⃣ LinkedIn API Token

1. 前往 https://www.linkedin.com/developers/ → Create App
2. 在 **Products** 頁申請：
   - ✅ Share on LinkedIn
   - ✅ Sign In with LinkedIn using OpenID Connect
3. 在 **Auth** 頁取得 Client ID + Secret
4. 用 OAuth 2.0 三步驟取得 Access Token：

```bash
# Step 1: 在瀏覽器打開，授權後會 redirect 到你設定的 URL，拿到 code
https://www.linkedin.com/oauth/v2/authorization?\
response_type=code&\
client_id=你的CLIENT_ID&\
redirect_uri=http://localhost:3000/callback&\
scope=openid%20profile%20w_member_social

# Step 2: 用 code 換 token
curl -X POST https://www.linkedin.com/oauth/v2/accessToken \
  -d "grant_type=authorization_code" \
  -d "code=你拿到的CODE" \
  -d "client_id=你的CLIENT_ID" \
  -d "client_secret=你的CLIENT_SECRET" \
  -d "redirect_uri=http://localhost:3000/callback"

# Step 3: 取得 Person ID
curl -H "Authorization: Bearer 你的TOKEN" \
  https://api.linkedin.com/v2/userinfo
# 回傳的 sub 就是你的 Person ID，格式：urn:li:person:xxxxxxxxxx
```

```
LINKEDIN_ACCESS_TOKEN=AQVxxxxxxxxxxxxxxxxx
LINKEDIN_PERSON_ID=urn:li:person:xxxxxxxxxx
```

### 4️⃣ Patreon API Token

1. 前往 https://www.patreon.com/portal/registration/register-clients
2. 建立新 Client → 取得 **Creator's Access Token**（不會過期）
3. 取得 Campaign ID：

```bash
curl -H "Authorization: Bearer 你的TOKEN" \
  "https://www.patreon.com/api/oauth2/v2/campaigns"
# 回傳的 data[0].id 就是 PATREON_CAMPAIGN_ID
```

```
PATREON_ACCESS_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxx
PATREON_CAMPAIGN_ID=12345678
```

---

## 使用方式

### 本地執行

```bash
# 發布今天 Ready 的內容
python publish.py

# 預覽模式（不會真的發布）
python publish.py --dry-run

# 指定日期
python publish.py --date 2026-03-01

# 預覽指定日期
python publish.py --dry-run --date 2026-03-01
```

### VSCode 快捷鍵（推薦）

在 `.vscode/tasks.json` 中已預設好 3 個 Task：

- `Ctrl+Shift+P` → `Tasks: Run Task` →
  - **Publish Today** — 發布今天的內容
  - **Dry Run Today** — 預覽今天的內容
  - **Publish Specific Date** — 輸入日期後發布

### GitHub Actions 自動排程（免費）

每天 HKT 9:00 自動執行。設定方式：

1. 把專案推到 GitHub（private repo）
2. 進入 repo → Settings → Secrets and variables → Actions
3. 加入以下 Secrets（名稱要一模一樣）：

| Secret Name | 值 |
|---|---|
| `NOTION_TOKEN` | 你的 Notion token |
| `NOTION_DATABASE_ID` | `cf022656-54bf-41ca-a77d-538d6c2675dc` |
| `THREADS_ACCESS_TOKEN` | Threads token |
| `THREADS_USER_ID` | Threads user ID |
| `LINKEDIN_ACCESS_TOKEN` | LinkedIn token |
| `LINKEDIN_PERSON_ID` | LinkedIn person URN |
| `PATREON_ACCESS_TOKEN` | Patreon token |
| `PATREON_CAMPAIGN_ID` | Patreon campaign ID |

4. 推上去後 Actions 會自動啟用
5. 也可以在 Actions tab 手動觸發 **Run workflow**

---

## 完整工作流

```
1. Claude 生成 4 篇內容 → 寫入 Notion (Status = Draft)
2. 你在 Notion 審稿 → 改 Status 為 "Ready"
3. 發布日到了：
   - GitHub Actions 自動執行（HKT 9:00）
   - 或你在 VSCode 手動 Ctrl+Shift+P → Publish Today
4. 發布成功 → Notion Status 自動變 "Published"
```

---

## 故障排查

| 問題 | 解法 |
|---|---|
| `401 Unauthorized` (Notion) | Integration 沒有連接到 Content Calendar，去 Notion 頁面加 Connection |
| `401` (Threads) | Token 過期，重新換長期 token（每 60 天一次） |
| `403` (LinkedIn) | App 未通過 Share on LinkedIn 審核，或 token scope 不對 |
| `422` (Threads) | 貼文可能太長（Threads 單篇上限 500 字），或包含不允許的字元 |
| 找不到 Ready 的文章 | 確認 Publish Date 格式是 `YYYY-MM-DD`，且跟執行日期一致 |
| Thread 串文順序亂 | 正常，每段之間有 5 秒等待確保 API 處理完成 |

---

## Token 有效期一覽

| 平台 | 有效期 | 刷新方式 |
|---|---|---|
| Notion | 永久 | 不需要 |
| Threads | 60 天 | 到期前跑 refresh 指令（見上方） |
| LinkedIn | 60 天 | 需要重新走 OAuth 流程 |
| Patreon | 永久 | Creator Token 不會過期 |

---

## 跨 Repo Telegram 彙總

可用 `tools/telegram_hub.py` 掃描 `C:\Users\User\Documents\GitHub` 下所有 repo，彙總最近更新後發到同一個 Telegram chat。
腳本只會挑「有內容價值」的新聞/摘要輸出，會自動過濾技術性檔案（例如 log、memory、run 記錄）。若本輪沒有可用內容，會自動跳過發送。

```bash
# 預覽（不發送）
python tools/telegram_hub.py --root C:\Users\User\Documents\GitHub --hours 8

# 正式發送
python tools/telegram_hub.py --root C:\Users\User\Documents\GitHub --hours 8 --send
```

也可用 `tools/run_telegram_hub.bat` 直接執行，方便掛到 Windows Task Scheduler。

---

## Liquidity Tracker

This repo now includes a separate H-model liquidity tracker. It is a tracking sidecar, not a Notion publishing flow and not a trading engine.

What it does:
- captures the latest Michael Howell / Capital Wars liquidity update
- parses a structured H-model regime from article text
- reads your local daily Excel plus screenshot inputs for a fast internal checker
- writes a composite liquidity snapshot and history

Setup:
1. Fill the new liquidity values in `.env`
2. Copy `config/liquidity_checker.example.json` to `config/liquidity_checker.local.json`
3. Update the local config so the sheet name, columns, OCR patterns, and env-mapped paths match your current daily files

Run commands:
```bash
python scrape_h_model.py --headless
python liquidity_tracker.py run
python liquidity_tracker.py run --skip-h-capture
python liquidity_tracker.py run --skip-internal-checker
```

Scheduler:
```powershell
.\register_liquidity_tracker_task.ps1 -WhatIf
.\register_liquidity_tracker_task.ps1
```

Generated files:
- `scraped_data/liquidity/h_model_latest_raw.json`
- `scraped_data/liquidity/h_model_latest_screenshot.png`
- `outputs/liquidity/h_model_latest.json`
- `outputs/liquidity/internal_checker_latest.json`
- `outputs/liquidity/liquidity_tracker_latest.json`
- `outputs/liquidity/liquidity_tracker_history.csv`

Status meanings:
- `fresh`: H-model article is 72 hours old or newer
- `aging`: H-model article is older than 72 hours and up to 120 hours
- `stale`: H-model article is older than 120 hours
- `divergence_flag=true`: the internal checker disagrees with the H-model baseline
- `override_active=true`: the checker is temporarily overriding the H-model baseline because the H model is stale or divergence has persisted
