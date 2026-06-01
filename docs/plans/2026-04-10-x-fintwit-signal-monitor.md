# X/FinTwit Signal Monitor — Design Document

**Date**: 2026-04-10
**Status**: Draft — awaiting user approval before implementation

---

## 1. Problem Statement

High-conviction posts from credible fund managers on X (Twitter) occasionally
signal tradeable opportunities with significant asymmetric payoff (e.g. Burry +
Ackman on FNMA/FMCC → 50% gap the following Monday). These signals are rare,
time-sensitive, and drowned in noise. Missing them costs real alpha.

**Goal**: An automated pipeline that continuously monitors ~25 curated finance
accounts, scores each post for trade-relevance, and pushes only high-conviction
alerts (1-5/day) to Telegram.

---

## 2. System Architecture

```
┌────────────────────────────────────────────────────────────┐
│                    DATA SOURCE LAYER                        │
│                                                             │
│  Primary: Apify (scrape_twitter.py — already working)       │
│  Backup:  xreach CLI (agent-reach, zero-cost)               │
│                                                             │
│  Polling: cron every 60 min (configurable)                  │
│  Output:  scraped_data/twitter/fintwit_raw_latest.json      │
└──────────────────────┬─────────────────────────────────────┘
                       │
┌──────────────────────▼─────────────────────────────────────┐
│                   PROCESSING LAYER                          │
│                                                             │
│  1. Dedup — skip tweets already seen (SQLite or JSON state) │
│  2. Ticker extraction — regex + NLP for $TICKER, company    │
│     names, CUSIP-like references                            │
│  3. Post scoring (0-100):                                   │
│     - Account tier weight (30%)                             │
│     - Content signal strength (40%)                         │
│     - Engagement velocity (20%)                             │
│     - Recency decay (10%)                                   │
│  4. Threshold filter — only posts ≥ 60 pass                 │
│                                                             │
│  Output: scraped_data/twitter/fintwit_scored_latest.json    │
└──────────────────────┬─────────────────────────────────────┘
                       │
┌──────────────────────▼─────────────────────────────────────┐
│                  NOTIFICATION LAYER                          │
│                                                             │
│  Channel: Telegram via tools/telegram_hub.py                │
│  Bot:     @Jarvisdd168_bot (TELEGRAM_BOT_TOKEN_OPS)         │
│  Chat:    TELEGRAM_CHAT_ID_OPS (dedicated ops channel)      │
│                                                             │
│  Message format (HTML):                                     │
│  ┌─────────────────────────────────────────────┐            │
│  │ 🔔 <b>FinTwit Signal</b> — Score: 82/100    │            │
│  │                                              │            │
│  │ <b>@michaeljburry</b> (Scion Asset Mgmt)     │            │
│  │ Tickers: $FNMA $FMCC                         │            │
│  │                                              │            │
│  │ "Fannie and Freddie are absurdly cheap..."   │            │
│  │                                              │            │
│  │ 💬 1.2K  🔁 3.4K  ❤️ 12K                     │            │
│  │ 🔗 https://x.com/michaeljburry/status/...    │            │
│  └─────────────────────────────────────────────┘            │
└────────────────────────────────────────────────────────────┘
```

---

## 3. Account List — Proposed Starter (25 accounts)

### Tier 1 — Legendary Fund Managers (weight: 1.0)
| Handle | Name | Why |
|--------|------|-----|
| @michaeljburry | Michael Burry | Scion, "Big Short", FNMA thesis |
| @BillAckman | Bill Ackman | Pershing Square, activist, macro calls |
| @Carl_C_Icahn | Carl Icahn | Icahn Enterprises, activist |
| @chaaborsi | Chamath Palihapitiya | Social Capital, macro + tech |

### Tier 2 — Active Macro / Rates Voices (weight: 0.85)
| Handle | Name | Why |
|--------|------|-----|
| @dampedspring | Andy Constan | Damped Spring, macro + vol |
| @BobEUnlworthy | Bob Elliott | Unlimited Funds, macro |
| @LukeGromen | Luke Gromen | FFTT, fiscal/gold thesis |
| @SantiagoAuFund | Santiago Capital | Gold, macro |
| @biaborsi | Cem Karsan | Kai Vol, gamma/vol expert |
| @jam_croissant | Cem Karsan alt | Options flow |
| @KevinLMak | Kevin Mak | Stock picker |
| @Speculator_io | Speculator | Stock picker |

### Tier 3 — Respected Analysts / Short-Sellers (weight: 0.75)
| Handle | Name | Why |
|--------|------|-----|
| @HindsightPete | Peter Atwater | Confidence/sentiment |
| @markbspiegel | Mark Spiegel | Stanphyl Capital, short-seller |
| @AlderLaneeggs | Nate Anderson | Hindenburg Research |
| @MuddyWatersRes | Carson Block | Muddy Waters, short reports |
| @ClarityToast | Jesse Felder | Felder Report, valuation |
| @FedGuy12 | Joseph Wang | Ex-Fed, rates/liquidity |

### Tier 4 — FinTwit Signal Amplifiers (weight: 0.6)
| Handle | Name | Why |
|--------|------|-----|
| @zaborniki | Zaborniki | Macro charts, ES signals |
| @Fxhedgers | FXHedge | Breaking news aggregator |
| @WallStreetSilv | WallStreetSilver | Precious metals, macro |
| @MacroAlf | Alfonso Peccatiello | Macro/rates commentary |
| @GameofTrades_ | Game of Trades | Technical + macro |
| @unusual_whales | Unusual Whales | Options flow |
| @DeItaone | Walter Bloomberg | Breaking headlines |
| @elerianm | Mohamed El-Erian | Macro, former PIMCO |
| @TastyEddy | Hedgeye | Risk mgmt, quad framework |
| @PeterSchiff | Peter Schiff | Gold, bearish macro |

### Tier 5 — Commodities Specialists (weight: 0.75)
| Handle | Name | Why |
|--------|------|-----|
| @KingKong9888 | KingKong | Commodities trader |
| @JavierBlas | Javier Blas | Bloomberg commodities columnist |
| @PTM_Ltd | PTM | Precious/base metals |
| @profitsplusid | ProfitsPlus | Commodities signals |

### Dynamic Account Discovery (future)
- Track who Tier 1 accounts repost or quote-tweet
- Monitor follower velocity (accounts gaining >5K followers/week in finance)
- User can add/remove via config JSON, no code change needed

---

## 4. Data Source Options

| Option | Cost | Rate Limit | Latency | Reliability | Recommendation |
|--------|------|-----------|---------|-------------|----------------|
| **Apify (altimis/scweet)** | $0.30/1K tweets (free tier: 5K/mo) | ~100 min per call | 30-60s per batch | Good | **Use for MVP** — already integrated |
| **xreach CLI** (agent-reach) | Free | Depends on X auth | 5-10s/query | Medium (can break) | **Backup / dev testing** |
| **X API Basic** | $100/month | 10K reads/mo | Real-time | Excellent | Phase 2 if volume grows |
| **X API Pro** | $5K/month | 1M reads/mo | Real-time + streaming | Excellent | Overkill |
| **Nitter/scraping** | Free | Fragile | Variable | Poor (often blocked) | Not recommended |

**MVP plan**: Apify primary. 25 accounts × 10 tweets × hourly = ~6K tweets/day.
Free tier won't cover this, so we batch: fetch all 25 accounts in one Apify call
every hour → ~600 tweets/hour → ~14.4K/day → ~$4.30/day on Apify pay-as-you-go.

**Cost-optimized plan**: Fetch every 2 hours instead → ~$2.15/day (~$65/month).
Or use xreach for Tier 3-4 accounts (free) and Apify only for Tier 1-2.

---

## 5. Scoring Algorithm

### 5.1 Account Score (30% of total)

```
account_score = tier_weight × 100

Tier 1: 100  (Burry, Ackman, Icahn, Chamath)
Tier 2: 85   (Constan, Gromen, Karsan, etc.)
Tier 3: 75   (Short-sellers, analysts)
Tier 4: 60   (Aggregators, amplifiers)
```

### 5.2 Content Signal Score (40% of total)

Keyword/pattern matching with weights:

| Pattern | Weight | Example |
|---------|--------|---------|
| Explicit ticker ($XXX) | +25 | "$FNMA is absurdly cheap" |
| Direction word + ticker | +20 | "long", "short", "buy", "sell", "undervalued" |
| Conviction language | +15 | "extremely", "absurdly", "10x", "asymmetric", "mispriced" |
| Specific price target | +15 | "fair value $50", "target $200" |
| Risk/crisis language | +10 | "collapse", "squeeze", "black swan", "systemic" |
| Position disclosure | +10 | "we bought", "added to position", "our largest holding" |
| Thread (not standalone) | +5 | Multi-tweet analysis |
| Generic market commentary | +0 | "markets are volatile today" |
| Retweet without comment | -10 | Low signal |
| Self-promotion / ads | -20 | "subscribe to my newsletter" |

Cap at 100.

### 5.3 Engagement Velocity Score (20% of total)

```python
hours_since_post = (now - created_at).total_seconds() / 3600
velocity = (likes + retweets * 3 + replies * 2) / max(hours_since_post, 0.5)

engagement_score = min(100, velocity / 50 * 100)
```

Retweets weighted 3x (signal amplification), replies 2x (discussion = interest).

### 5.4 Recency Decay (10% of total)

```python
recency_score = max(0, 100 - hours_since_post * 4)  # 0 after 25 hours
```

### 5.5 Final Score

```python
final = (account_score * 0.30 +
         content_score * 0.40 +
         engagement_score * 0.20 +
         recency_score * 0.10)
```

**Threshold**: alert if `final >= 60`. Configurable in `config/fintwit_monitor.json`.

---

## 6. Ticker Extraction

```python
# Priority order:
# 1. Cashtags: $FNMA, $SPX, $BTC
# 2. Known ticker list: NVDA, AAPL, TSLA (without $)
# 3. Company name → ticker mapping: "Fannie Mae" → FNMA
# 4. Crypto: BTC, ETH, SOL (case-insensitive)
# 5. Macro instruments: SPX, NDX, VIX, TLT, GLD, USO, DXY
```

Asset class tagging:
- US equities (primary)
- Crypto (BTC, ETH, SOL, etc.)
- Commodities (GLD, SLV, USO, copper)
- Rates/bonds (TLT, TMV, TBT)
- Macro indices (SPX, NDX, VIX, DXY)

---

## 7. Implementation Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11+ |
| Scheduler | Windows Task Scheduler (.bat) or cron via `CronCreate` |
| State store | `scraped_data/twitter/fintwit_state.json` (seen tweet IDs + scores) |
| Config | `config/fintwit_monitor.json` (accounts, thresholds, weights) |
| Alerts | `tools/telegram_hub.py` → @Jarvisdd168_bot |
| Logging | `outputs/ops/fintwit_monitor.log` |
| Entry point | `monitor_fintwit.py` (single script, no framework) |

### File layout (new files only)
```
monitor_fintwit.py              # Main entry point
config/fintwit_monitor.json     # Account list, thresholds, weights
```

---

## 8. Telegram Alert Format

```html
<b>FinTwit Signal</b> — Score: 82/100

<b>@michaeljburry</b> (Tier 1 — Scion Asset Mgmt)
Tickers: <code>$FNMA</code> <code>$FMCC</code> [US Equity]

"Fannie and Freddie are absurdly cheap. The government will
eventually release them. This is a 10x opportunity."

Likes: 12,340 | RT: 3,412 | Replies: 1,205
Posted: 2h ago

https://x.com/michaeljburry/status/1234567890
```

---

## 9. Iteration & Robustness

### Error handling
- Apify failures → fall back to xreach → log + continue
- Telegram send failure → retry once, then log to file
- All errors logged to `outputs/ops/fintwit_monitor.log`

### Threshold tuning
- Config-driven: adjust `score_threshold` in `config/fintwit_monitor.json`
- Daily digest at end-of-day: count of posts scanned vs. alerts sent
- If >5 alerts/day for 3 consecutive days → auto-suggest raising threshold

### Account expansion
- Manual: edit `config/fintwit_monitor.json`, add handle + tier
- Semi-auto (future): track who Tier 1 accounts interact with, suggest additions

### Future: WebSocket integration
- Your `wss://vectorhouse.io:18002/...` endpoint for real-time price data
- When a FinTwit alert mentions $TICKER, immediately fetch current price
- Enrich alert with: "Current: $42.50 | Day change: +3.2%"
- This is Phase 2 — after the polling pipeline is validated

---

## 10. Phase Plan

| Phase | Scope | Effort |
|-------|-------|--------|
| **Phase 1 (now)** | `monitor_fintwit.py` + config + Telegram alerts, hourly cron | Build today |
| **Phase 2** | WebSocket price enrichment, engagement velocity tracking | Next week |
| **Phase 3** | Dynamic account discovery, historical hit-rate scoring | Future |

---

## Approval Requested

Please review and confirm:
1. Account list — add/remove anyone?
2. Scoring weights — reasonable?
3. Alert threshold 60 — start there?
4. Telegram destination — @Jarvisdd168_bot to ops chat?
5. Polling frequency — every 2 hours (cost-optimized)?
6. Anything else before I start coding?
