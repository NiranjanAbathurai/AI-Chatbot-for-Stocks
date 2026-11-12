# 📈 Stock Debate Chat

AI-powered stock analysis with **Bull 🐂**, **Bear 🐻**, and **Judge ⚖️** agents debating Indian equities (NSE/BSE). Deployed on **Netlify** with serverless functions.

## 🎯 Features

### Phase 1: Core Debate Chat
- Enter any Indian stock name (e.g., "Reliance", "TCS", "HDFC Bank")
- **Bull Agent** builds the strongest BUY case with real data
- **Bear Agent** builds the strongest AVOID case with real data
- **Judge Agent** delivers a balanced verdict (BUY / HOLD / AVOID) with confidence score
- Real-time stock data from Yahoo Finance
- AI provider failover: Gemini → OpenAI → Groq

### Phase 2: Stock Screener
- Scans NIFTY 50 stocks for BUY and SHORT signals
- Scoring system based on P/E, RSI, growth, debt, volume, and more
- Top 5 BUY and SHORT candidates with reasons

### Phase 3: Alerts & Watchlist
- Add stocks to a persistent watchlist (Netlify Blobs)
- Alert triggers: 52-week breakout/breakdown, big daily moves, volume spikes, RSI extremes
- On-demand alert scanning

---

## 🏗️ Architecture

```
StockDebateChat/
├── public/                          # Static frontend (served by Netlify CDN)
│   ├── index.html                   # Dark-themed chat UI
│   ├── style.css                    # Full dark theme with agent-colored bubbles
│   └── app.js                       # Frontend logic, API calls, markdown rendering
├── netlify/
│   └── functions/                   # Netlify Serverless Functions (v2)
│       ├── debate.mjs               # POST /api/debate — Bull/Bear/Judge debate
│       ├── health.mjs               # GET  /api/health — Health check + providers
│       ├── screener.mjs             # GET  /api/screener/* — Stock screener
│       ├── watchlist.mjs            # CRUD /api/watchlist — Watchlist management
│       ├── alerts.mjs               # GET/POST /api/alerts — Alert system
│       └── lib/                     # Shared libraries
│           ├── ai-service.mjs       # AI provider failover (Gemini/OpenAI/Groq)
│           ├── stock-service.mjs    # Yahoo Finance data fetching
│           ├── prompts.mjs          # Agent system prompts
│           ├── tickers.mjs          # NSE ticker resolution (200+ stocks)
│           ├── nifty-stocks.mjs     # NIFTY 50 stock list
│           └── store.mjs            # Netlify Blobs persistence
├── netlify.toml                     # Netlify build & function config
├── package.json                     # Node.js dependencies
└── README.md
```

---

## 🚀 Deploy to Netlify

### 1. Push to GitHub

```bash
cd StockDebateChat
git init
git add .
git commit -m "Initial commit: Stock Debate Chat"
git remote add origin https://github.com/YOUR_USERNAME/stock-debate-chat.git
git push -u origin main
```

### 2. Connect to Netlify

1. Go to [app.netlify.com](https://app.netlify.com)
2. Click **"Add new site"** → **"Import an existing project"**
3. Select your GitHub repository
4. Netlify will auto-detect the config from `netlify.toml`:
   - **Build command**: `echo 'No build step needed'`
   - **Publish directory**: `public`
   - **Functions directory**: `netlify/functions`
5. Click **"Deploy site"**

### 3. Set Environment Variables (API Keys)

Go to **Site settings** → **Environment variables** and add:

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | ✅ (at least one) | Google Gemini API key ([Get one](https://aistudio.google.com/apikey)) |
| `OPENAI_API_KEY` | Optional | OpenAI API key ([Get one](https://platform.openai.com/api-keys)) |
| `GROQ_API_KEY` | Optional | Groq API key ([Get one](https://console.groq.com/keys)) |
| `AI_PROVIDER_PRIORITY` | Optional | Comma-separated priority order (default: `gemini,openai,groq`) |

> **Note:** You need at least ONE AI provider key. The system automatically fails over to the next provider if one is unavailable.

### 4. Redeploy

After setting environment variables, trigger a redeploy:
- Go to **Deploys** → **Trigger deploy** → **Deploy site**

---

## 🧪 Local Development

### Prerequisites
- Node.js 18+
- Netlify CLI

### Setup

```bash
cd StockDebateChat
npm install

# Create a .env file for local development
echo "GEMINI_API_KEY=your_key_here" > .env
echo "OPENAI_API_KEY=your_key_here" >> .env
echo "GROQ_API_KEY=your_key_here" >> .env

# Start local dev server
npx netlify dev
```

The app will be available at `http://localhost:8888`.

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check + available AI providers |
| `POST` | `/api/debate` | Run Bull/Bear/Judge debate for a stock |
| `GET` | `/api/screener/scan` | Full NIFTY 50 scan |
| `GET` | `/api/screener/top-buys` | Top BUY candidates |
| `GET` | `/api/screener/top-shorts` | Top SHORT candidates |
| `GET` | `/api/watchlist` | List watchlist stocks |
| `POST` | `/api/watchlist` | Add stock to watchlist |
| `DELETE` | `/api/watchlist/:ticker` | Remove stock from watchlist |
| `GET` | `/api/alerts` | Get alert history |
| `POST` | `/api/alerts/scan-now` | Trigger alert scan on watchlist |

### Example: Debate Request

```bash
curl -X POST https://your-site.netlify.app/api/debate \
  -H "Content-Type: application/json" \
  -d '{"stock_name": "Reliance"}'
```

---

## 🤖 AI Providers

The system supports three AI providers with automatic failover:

1. **Google Gemini** (default, free tier available) — `gemini-2.0-flash`
2. **OpenAI** — `gpt-4o-mini`
3. **Groq** (fast, free tier) — `llama-3.1-70b-versatile`

Set `AI_PROVIDER_PRIORITY` to customize the order (e.g., `groq,gemini,openai`).

---

## 📊 Supported Stocks

The app supports **200+ Indian stocks** including all NIFTY 50 constituents. You can enter:
- Common names: "Reliance", "TCS", "Infosys", "HDFC Bank"
- Abbreviations: "SBI", "HUL", "L&T", "M&M"
- Ticker symbols: "RELIANCE.NS", "INFY.NS"

---

## ⚠️ Disclaimer

This is AI-generated analysis for **educational purposes only**. This is NOT financial advice. Always do your own research and consult a SEBI-registered financial advisor before making investment decisions.

---

## 📄 License

MIT
