# Stock Debate Chat — Architecture & Implementation Plan

## Overview
A chat-style web application with three core capabilities:

### Phase 1: Core Debate Chat
A user enters an NSE stock name and three AI agents debate whether to buy it:
- **🐂 Bullish Agent** — Makes the strongest case FOR buying
- **🐻 Bearish Agent** — Makes the strongest case AGAINST buying
- **⚖️ Judge Agent** — Evaluates both arguments and delivers a verdict

### Phase 2: Stock Screener & Auto-Suggestions
The app proactively scans NIFTY 50/200 stocks and suggests:
- **Top stocks to BUY** — Showing strong bullish signals
- **Top stocks to SHORT** — Showing bearish/weakness signals
- User can click any suggestion to trigger a full debate analysis

### Phase 3: Notification Alerts
Background monitoring with alerts for significant events:
- Price breakouts, volume spikes, 52-week highs/lows
- Delivered via browser notifications or Telegram bot
- User maintains a watchlist of stocks to monitor

## Tech Stack

| Layer | Technology | Reason |
|-------|-----------|--------|
| Backend | Python FastAPI | Async, fast, familiar |
| Frontend | Plain HTML/CSS/JS | Simple chat UI, no framework overhead |
| AI (Primary) | Google Gemini API | Free tier, generous limits |
| AI (Fallback 2) | Groq (Llama 3.1) | Free tier, fast inference |
| Stock Data | yfinance Python library | Free, reliable NSE data |

## Architecture Flow

```
User Input ("Axis Bank")
    │
    ▼
Backend: Resolve ticker (AXISBANK.NS)
    │
    ▼
Backend: Fetch live data via yfinance
    │
    ├──────────────────────┐
    ▼                      ▼
Bullish Agent          Bearish Agent
(parallel call)        (parallel call)
    │                      │
    ├──────────────────────┘
    ▼
Judge Agent (receives both arguments)
    │
    ▼
Response sent to frontend
    │
    ▼
Chat UI renders: Stock Data → Bull → Bear → Verdict
```

## Project Structure

```
StockDebateChat/
├── backend/
│   ├── main.py                    # FastAPI app entry point + CORS
│   ├── requirements.txt           # Python dependencies
│   ├── .env.example               # Template for API keys
│   ├── .env                       # Actual API keys (gitignored)
│   ├── config.py                  # App configuration loader
│   ├── routers/
│   │   └── debate.py              # POST /api/debate endpoint
│   ├── services/
│   │   ├── stock_service.py       # Ticker resolution + yfinance data fetch
│   │   ├── ai_service.py          # Provider-agnostic AI wrapper with failover
│   │   ├── debate_service.py      # Orchestrates Bull → Bear → Judge flow
│   │   └── providers/
│   │       ├── base.py            # Abstract base class
│   │       ├── gemini_provider.py # Google Gemini implementation
│   │       ├── openai_provider.py # OpenAI GPT implementation
│   │       └── groq_provider.py   # Groq/Llama implementation
│   ├── prompts/
│   │   ├── bullish.py             # Bull agent system prompt
│   │   ├── bearish.py             # Bear agent system prompt
│   │   └── judge.py               # Judge agent system prompt
│   └── models/
│       └── schemas.py             # Pydantic request/response models
├── frontend/
│   ├── index.html                 # Single page chat layout
│   ├── style.css                  # Chat bubble styling (dark theme)
│   └── app.js                     # API calls + message rendering
└── README.md                      # Setup & usage instructions
```

## API Design

### POST /api/debate

**Request:**
```json
{
    "stock_name": "Axis Bank"
}
```

**Response:**
```json
{
    "ticker": "AXISBANK.NS",
    "stock_name": "Axis Bank Ltd",
    "stock_data": {
        "current_price": 1125.50,
        "market_cap": "3.47L Cr",
        "pe_ratio": 14.2,
        "pb_ratio": 2.1,
        "eps": 79.26,
        "dividend_yield": 0.89,
        "52_week_high": 1340.00,
        "52_week_low": 895.00,
        "debt_to_equity": 0.0,
        "roe": 16.5,
        "revenue_growth": 18.2,
        "profit_growth": 22.1,
        "promoter_holding": 8.22,
        "1m_return": -2.3,
        "3m_return": 5.1,
        "6m_return": 12.4,
        "1y_return": 18.7
    },
    "bullish": {
        "agent": "🐂 Bullish Analyst",
        "argument": "... detailed bullish case with facts ..."
    },
    "bearish": {
        "agent": "🐻 Bearish Analyst",
        "argument": "... detailed bearish case with facts ..."
    },
    "verdict": {
        "agent": "⚖️ Judge",
        "recommendation": "BUY",
        "confidence": 7,
        "analysis": "... balanced verdict ..."
    },
    "disclaimer": "⚠️ This is AI-generated analysis for educational purposes only. This is NOT financial advice. Always do your own research and consult a SEBI-registered financial advisor before making investment decisions."
}
```

## Failsafe AI Provider Strategy

```
Request comes in
    │
    ▼
Try Gemini (primary, free)
    │
    ├── Success → Use response
    │
    ├── Failure → Try OpenAI (fallback 1)
    │               │
    │               ├── Success → Use response
    │               │
    │               ├── Failure → Try Groq (fallback 2)
    │               │               │
    │               │               ├── Success → Use response
    │               │               │
    │               │               └── Failure → Return error
    │               │
    │               └── No API key → Skip, try next
    │
    └── No API key → Skip, try next
```

## Stock Data Package (fed to all agents)

From yfinance for any NSE stock:
- Current price, 52-week high/low, market cap
- P/E ratio, P/B ratio, EPS, dividend yield
- Revenue & profit growth (quarterly/annual)
- Debt-to-equity ratio, ROE
- Promoter holding %
- Recent returns: 1M, 3M, 6M, 1Y
- Volume trends
- Sector & industry classification

## Agent Prompt Design

### 🐂 Bullish Agent
- Role: Passionate stock market bull / buy-side analyst
- Task: Build the strongest possible BUY case using provided data
- Structure: Executive Summary → 5-7 Key Bullish Points → Price Target Reasoning → Risks Acknowledged
- Must use actual numbers from the data
- Tone: Confident, persuasive, data-driven

### 🐻 Bearish Agent
- Role: Cautious, skeptical bear / risk analyst
- Task: Build the strongest possible AVOID case using provided data
- Structure: Executive Summary → 5-7 Key Bearish Points → Downside Risk → What Would Change My Mind
- Must use actual numbers from the data
- Tone: Cautious, analytical, risk-focused

### ⚖️ Judge Agent
- Role: Neutral, experienced portfolio manager
- Input: Both Bull and Bear arguments + original stock data
- Task: Evaluate both sides and deliver a balanced verdict
- Structure: Verdict (BUY/HOLD/AVOID) → Confidence (1-10) → Strongest Bull Point → Strongest Bear Point → Key Metrics to Watch → Final Recommendation
- Tone: Balanced, authoritative, practical

## Frontend Design

Simple dark-themed chat interface:
- Input bar at bottom to type stock name
- Messages appear as chat bubbles:
  1. User message: "Analyze AXIS Bank"
  2. System: Stock data summary card
  3. 🐂 Bull: Green-tinted bubble with bullish argument
  4. 🐻 Bear: Red-tinted bubble with bearish argument
  5. ⚖️ Judge: Gold-tinted bubble with verdict
- Loading animation while agents are "thinking"
- Markdown rendering for formatted agent responses

## Error Handling Strategy

| Scenario | Handling |
|----------|---------|
| Stock name not recognized | Return suggestion list of similar tickers |
| yfinance returns no data | Clear error: "Could not fetch data for this stock" |
| Primary AI provider fails | Auto-fallback to next provider |
| All AI providers fail | Error: "AI services unavailable, try again later" |
| AI returns garbage | Validate response structure before sending |
| Network timeout | 30s timeout per AI call, then fallback |
| Rate limiting | Exponential backoff + provider switch |

## Dependencies (requirements.txt)

```
fastapi
uvicorn[standard]
python-dotenv
yfinance
google-generativeai
openai
groq
pydantic
httpx
aiohttp
apscheduler
pandas
numpy
```

## Environment Variables (.env)

```
# AI Providers - at least one required
GEMINI_API_KEY=your_gemini_key_here
OPENAI_API_KEY=your_openai_key_here
GROQ_API_KEY=your_groq_key_here

# App Config
AI_PROVIDER_PRIORITY=gemini,openai,groq
BACKEND_PORT=8000

# Phase 3: Alerts - optional
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
ALERT_SCAN_INTERVAL_HOURS=4
```

## NSE Ticker Resolution

A dictionary mapping common names to NSE tickers:
```python
TICKER_MAP = {
    "axis bank": "AXISBANK.NS",
    "reliance": "RELIANCE.NS",
    "tcs": "TCS.NS",
    "infosys": "INFY.NS",
    "hdfc bank": "HDFCBANK.NS",
    "icici bank": "ICICIBANK.NS",
    "sbi": "SBIN.NS",
    "wipro": "WIPRO.NS",
    "bharti airtel": "BHARTIARTL.NS",
    "itc": "ITC.NS",
    # ... 200+ popular NSE stocks
}
```
Plus a fuzzy search fallback using yfinance's search if not in the map.

---

## Phase 2: Stock Screener & Auto-Suggestions

### How It Works

The screener scans NIFTY 50 stocks (expandable to NIFTY 200) and applies a scoring system:

**Screening Criteria for BUY signals:**
| Criteria | Weight | Logic |
|----------|--------|-------|
| P/E ratio below sector average | 15% | Value play |
| RSI below 30 (oversold) | 15% | Technical bounce candidate |
| Price near 52-week low (within 10%) | 10% | Potential bottom |
| Revenue growth > 15% YoY | 15% | Growth story |
| Profit growth > 20% YoY | 15% | Earnings momentum |
| Promoter holding > 50% | 10% | Skin in the game |
| Debt-to-equity < 1 | 10% | Financial health |
| Volume spike (2x avg) | 10% | Institutional interest |

**Screening Criteria for SHORT/AVOID signals:**
| Criteria | Weight | Logic |
|----------|--------|-------|
| P/E ratio above sector average by 50%+ | 15% | Overvalued |
| RSI above 70 (overbought) | 15% | Due for correction |
| Price near 52-week high (within 5%) | 10% | Limited upside |
| Revenue decline YoY | 15% | Deteriorating business |
| Profit decline YoY | 15% | Earnings weakness |
| Promoter holding decreasing | 10% | Insiders selling |
| Debt-to-equity > 2 | 10% | Leverage risk |
| Volume drying up | 10% | Lack of interest |

Each stock gets a composite score (0-100). Top 5 BUY and Top 5 SHORT candidates are returned.

### API Endpoints

```
GET /api/screener/top-buys
Response: { "stocks": [{ "name": "...", "ticker": "...", "score": 82, "reasons": [...] }, ...] }

GET /api/screener/top-shorts
Response: { "stocks": [{ "name": "...", "ticker": "...", "score": 75, "reasons": [...] }, ...] }

GET /api/screener/scan
Response: { "last_scan": "2026-11-12T10:30:00", "buy_candidates": [...], "short_candidates": [...] }
```

### Frontend Integration
- A "Discover" section above the chat input
- Two cards: "🟢 Top Buys" and "🔴 Top Shorts"
- Each shows 5 stocks with score and top reason
- Clicking a stock auto-triggers the full debate analysis

### Updated Project Structure (Phase 2 additions)

```
backend/
├── services/
│   ├── screener_service.py        # Stock screening logic + scoring
│   └── nifty_stocks.py            # NIFTY 50/200 stock lists
├── routers/
│   └── screener.py                # Screener API endpoints
```

```
frontend/
├── app.js                         # Updated with discover section logic
```

---

## Phase 3: Notification Alerts

### How It Works

A background scheduler (APScheduler) runs every N hours and:
1. Scans the user's watchlist stocks (or NIFTY 50 by default)
2. Checks for significant events/triggers
3. Sends alerts via browser notification or Telegram

### Alert Triggers

| Trigger | Condition | Priority |
|---------|-----------|----------|
| Price Breakout | Stock breaks above 52-week high | 🔴 High |
| Price Breakdown | Stock breaks below 52-week low | 🔴 High |
| Big Daily Move | Stock moves > 5% in a day | 🟡 Medium |
| Volume Spike | Volume > 3x 20-day average | 🟡 Medium |
| RSI Extreme | RSI < 25 or RSI > 80 | 🟡 Medium |
| Earnings Beat/Miss | Significant deviation from estimates | 🔴 High |

### Notification Delivery Options

**Option A: Browser Push Notifications**
- Uses the Web Push API
- Works when the browser tab is open
- No external service needed

**Option B: Telegram Bot (Recommended)**
- Create a Telegram bot via @BotFather
- Bot sends messages to your personal chat
- Works even when browser is closed
- Free, reliable, instant

### Watchlist Feature
- User can add/remove stocks from their watchlist
- Stored in a local JSON file (no database needed for v1)
- Watchlist stocks get priority scanning

### API Endpoints

```
GET  /api/alerts              # Get recent alerts
POST /api/watchlist           # Add stock to watchlist
DELETE /api/watchlist/{ticker} # Remove stock from watchlist
GET  /api/watchlist           # Get current watchlist
POST /api/alerts/scan-now     # Trigger immediate scan
```

### Updated Project Structure (Phase 3 additions)

```
backend/
├── services/
│   ├── alert_service.py           # Background scheduler + alert logic
│   └── notification_service.py    # Telegram/browser notification delivery
├── routers/
│   ├── alerts.py                  # Alert API endpoints
│   └── watchlist.py               # Watchlist CRUD endpoints
├── data/
│   ├── watchlist.json             # Persisted watchlist
│   └── alerts_history.json        # Recent alert history
```

```
frontend/
├── app.js                         # Updated with alerts panel + watchlist UI
```

---

## Complete Final Project Structure

```
StockDebateChat/
├── backend/
│   ├── main.py                        # FastAPI app + CORS + startup events
│   ├── requirements.txt               # All Python dependencies
│   ├── .env.example                   # Template for API keys
│   ├── .env                           # Actual keys - gitignored
│   ├── config.py                      # Configuration loader
│   ├── routers/
│   │   ├── debate.py                  # POST /api/debate
│   │   ├── screener.py               # GET /api/screener/*
│   │   ├── alerts.py                  # GET /api/alerts
│   │   └── watchlist.py              # CRUD /api/watchlist
│   ├── services/
│   │   ├── stock_service.py           # Ticker resolution + yfinance
│   │   ├── ai_service.py             # Provider-agnostic AI with failover
│   │   ├── debate_service.py          # Bull + Bear + Judge orchestration
│   │   ├── screener_service.py        # Stock screening + scoring
│   │   ├── alert_service.py           # Background scheduler + triggers
│   │   ├── notification_service.py    # Telegram/browser notifications
│   │   ├── nifty_stocks.py           # NIFTY 50/200 stock lists
│   │   └── providers/
│   │       ├── base.py               # Abstract AI provider
│   │       ├── gemini_provider.py    # Google Gemini
│   │       ├── openai_provider.py    # OpenAI GPT
│   │       └── groq_provider.py      # Groq/Llama
│   ├── prompts/
│   │   ├── bullish.py                # Bull system prompt
│   │   ├── bearish.py                # Bear system prompt
│   │   └── judge.py                  # Judge system prompt
│   ├── models/
│   │   └── schemas.py                # All Pydantic models
│   └── data/
│       ├── watchlist.json            # User watchlist
│       └── alerts_history.json       # Alert log
├── frontend/
│   ├── index.html                    # Full page layout
│   ├── style.css                     # Dark theme chat styling
│   └── app.js                        # All frontend logic
└── README.md                         # Setup + usage guide
```

## Implementation Order

1. **Phase 1** — Core Debate Chat (get this working first)
2. **Phase 2** — Stock Screener (adds discovery)
3. **Phase 3** — Alerts (adds proactive monitoring)

Each phase builds on the previous one. Phase 1 is the foundation.
