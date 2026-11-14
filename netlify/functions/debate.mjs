/**
 * Netlify Function: /api/debate/*
 * Handles all debate endpoints:
 *   POST /api/debate       — Legacy combined debate (bull + bear + judge)
 *   POST /api/debate/bull  — Individual bull analysis
 *   POST /api/debate/bear  — Individual bear analysis
 *   POST /api/debate/judge — Individual judge verdict
 */

import { resolveTicker, getSimilarTickers } from "./lib/tickers.mjs";
import { fetchStockData } from "./lib/stock-service.mjs";
import { generateAI } from "./lib/ai-service.mjs";
import {
  BULLISH_SYSTEM_PROMPT,
  BEARISH_SYSTEM_PROMPT,
  JUDGE_SYSTEM_PROMPT,
} from "./lib/prompts.mjs";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Content-Type": "application/json",
};

// ── Helpers ────────────────────────────────────────────────────

function formatStockDataPrompt(stockName, ticker, stockData, stockDataError) {
  const lines = [`# Stock Analysis Request: ${stockName} (${ticker})`, "", "## Current Stock Data:", ""];

  const fieldLabels = {
    current_price: "Current Price", market_cap: "Market Cap",
    pe_ratio: "P/E Ratio", pb_ratio: "P/B Ratio",
    eps: "EPS (Earnings Per Share)", dividend_yield: "Dividend Yield (%)",
    "52_week_high": "52-Week High", "52_week_low": "52-Week Low",
    debt_to_equity: "Debt-to-Equity Ratio", roe: "Return on Equity (ROE)",
    revenue_growth: "Revenue Growth (%)", profit_growth: "Profit/Earnings Growth (%)",
    promoter_holding: "Promoter/Insider Holding (%)",
    "1m_return": "1-Month Return (%)", "3m_return": "3-Month Return (%)",
    "6m_return": "6-Month Return (%)", "1y_return": "1-Year Return (%)",
    volume: "Current Volume", avg_volume: "Average Volume",
    sector: "Sector", industry: "Industry",
  };

  let hasData = false;
  for (const [key, label] of Object.entries(fieldLabels)) {
    const value = stockData[key];
    if (value !== null && value !== undefined) {
      hasData = true;
      lines.push(
        typeof value === "number"
          ? `- **${label}**: ${value.toFixed(2)}`
          : `- **${label}**: ${value}`
      );
    }
  }

  if (!hasData) {
    lines.push("⚠️ **Live market data is temporarily unavailable.**");
    if (stockDataError) lines.push(`(Reason: ${stockDataError})`);
    lines.push("", "Please provide your analysis based on your general knowledge of this stock,");
    lines.push("its fundamentals, recent news, sector trends, and historical performance.");
    lines.push("Clearly state that live data was unavailable and your analysis is based on general knowledge.");
  } else {
    lines.push("", "Analyze this stock based on the data above. Use specific numbers in your analysis.");
  }

  return lines.join("\n");
}

function formatTechnicalDataPrompt(technicalData) {
  if (!technicalData || Object.keys(technicalData).length === 0) return "";

  const lines = ["", "---", "", "## 📐 Technical Analysis Data:", ""];

  const sr = technicalData.support_resistance || {};
  if (sr.support_levels?.length) {
    lines.push("### 🟢 Support Levels:");
    sr.support_levels.forEach((s, i) => {
      lines.push(`  S${i + 1}: ₹${s.price} (zone: ₹${s.zone_low}–₹${s.zone_high}, strength: ${s.strength})`);
    });
    lines.push("");
  }
  if (sr.resistance_levels?.length) {
    lines.push("### 🔴 Resistance Levels:");
    sr.resistance_levels.forEach((r, i) => {
      lines.push(`  R${i + 1}: ₹${r.price} (zone: ₹${r.zone_low}–₹${r.zone_high}, strength: ${r.strength})`);
    });
    lines.push("");
  }

  const patterns = technicalData.chart_patterns || [];
  if (patterns.length) {
    lines.push("### 📈 Chart Patterns:");
    for (const p of patterns) {
      const emoji = p.type === "bullish" ? "🟢" : p.type === "bearish" ? "🔴" : "🟡";
      lines.push(`  ${emoji} **${p.pattern}** (${p.type}, reliability: ${p.reliability || "N/A"})`);
      if (p.description) lines.push(`     ${p.description}`);
      if (p.target) lines.push(`     Target: ₹${p.target}`);
    }
    lines.push("");
  }

  const swing = technicalData.swing_indicators || {};
  if (Object.keys(swing).length) {
    lines.push("### 🔧 Swing Indicators:");
    if (swing.rsi_14 !== undefined) lines.push(`  RSI (14): ${swing.rsi_14} — ${swing.rsi_signal || ""}`);
    if (swing.macd !== undefined) lines.push(`  MACD: ${swing.macd} | Trend: ${swing.macd_trend || ""}`);
    if (swing.atr_14 !== undefined) lines.push(`  ATR (14): ₹${swing.atr_14} (${swing.atr_pct || ""}%)`);
    if (swing.swing_score !== undefined) lines.push(`  **Swing Score: ${swing.swing_score}/100 — ${swing.swing_bias || ""}**`);
    lines.push("");
  }

  return lines.join("\n");
}

function parseVerdict(judgeResponse) {
  let recommendation = "HOLD";
  let confidence = 5;

  const verdictPatterns = [
    /Verdict:\s*(BUY|HOLD|AVOID|SELL)/i,
    /\*\*(BUY|HOLD|AVOID|SELL)\*\*/i,
    /recommendation[:\s]*(BUY|HOLD|AVOID|SELL)/i,
  ];
  for (const pattern of verdictPatterns) {
    const match = judgeResponse.match(pattern);
    if (match) {
      recommendation = match[1].toUpperCase();
      if (recommendation === "SELL") recommendation = "AVOID";
      break;
    }
  }

  const confPatterns = [
    /Confidence:\s*(\d+)\s*\/\s*10/i,
    /Confidence:\s*(\d+)/i,
    /(\d+)\s*\/\s*10/i,
  ];
  for (const pattern of confPatterns) {
    const match = judgeResponse.match(pattern);
    if (match) {
      const conf = parseInt(match[1], 10);
      if (conf >= 1 && conf <= 10) { confidence = conf; break; }
    }
  }

  return { recommendation, confidence, analysis: judgeResponse };
}

function extractErrorInfo(err) {
  const errors = {};
  const errStr = err.message || String(err);
  if (errStr.includes("Errors:")) {
    const parts = errStr.split("Errors:")[1].trim().split("; ");
    for (const part of parts) {
      if (part.includes(": ")) {
        const [prov, msg] = part.split(": ", 2);
        errors[prov.trim()] = (msg || "").substring(0, 150);
      }
    }
  } else {
    errors["all"] = errStr.substring(0, 150);
  }
  return errors;
}

// ── Individual Agent Handlers ──────────────────────────────────

async function handleBull(body) {
  const { ticker, stock_name, stock_data, technical_data, analysis_mode } = body;

  if (!ticker || !stock_name) {
    return new Response(
      JSON.stringify({ detail: "ticker and stock_name are required" }),
      { status: 400, headers: CORS_HEADERS }
    );
  }

  const dataPrompt = formatStockDataPrompt(stock_name, ticker, stock_data || {});
  const techPrompt = formatTechnicalDataPrompt(technical_data || {});
  const fullPrompt = dataPrompt + techPrompt;

  try {
    const text = await generateAI(BULLISH_SYSTEM_PROMPT, fullPrompt);
    return new Response(
      JSON.stringify({
        agent: "🐂 Bullish Analyst",
        argument: text,
        provider: "ai",
        providers_attempted: [],
        errors: {},
      }),
      { status: 200, headers: CORS_HEADERS }
    );
  } catch (err) {
    console.error("Bull analysis failed:", err);
    return new Response(
      JSON.stringify({
        agent: "🐂 Bullish Analyst",
        argument: "⚠️ The Bullish Analyst could not generate an analysis at this time.",
        provider: "none",
        providers_attempted: [],
        errors: extractErrorInfo(err),
      }),
      { status: 200, headers: CORS_HEADERS }
    );
  }
}

async function handleBear(body) {
  const { ticker, stock_name, stock_data, technical_data, analysis_mode, bull_argument } = body;

  if (!ticker || !stock_name) {
    return new Response(
      JSON.stringify({ detail: "ticker and stock_name are required" }),
      { status: 400, headers: CORS_HEADERS }
    );
  }

  const dataPrompt = formatStockDataPrompt(stock_name, ticker, stock_data || {});
  const techPrompt = formatTechnicalDataPrompt(technical_data || {});

  let fullPrompt;
  if (bull_argument) {
    fullPrompt = `${dataPrompt}${techPrompt}

---

## 🐂 Bull Analyst's Argument (counter this):
${bull_argument}

---

Now present your bearish counter-argument. Directly address and counter the Bull's key points.`;
  } else {
    fullPrompt = dataPrompt + techPrompt;
  }

  try {
    const text = await generateAI(BEARISH_SYSTEM_PROMPT, fullPrompt);
    return new Response(
      JSON.stringify({
        agent: "🐻 Bearish Analyst",
        argument: text,
        provider: "ai",
        providers_attempted: [],
        errors: {},
      }),
      { status: 200, headers: CORS_HEADERS }
    );
  } catch (err) {
    console.error("Bear analysis failed:", err);
    return new Response(
      JSON.stringify({
        agent: "🐻 Bearish Analyst",
        argument: "⚠️ The Bearish Analyst could not generate an analysis at this time.",
        provider: "none",
        providers_attempted: [],
        errors: extractErrorInfo(err),
      }),
      { status: 200, headers: CORS_HEADERS }
    );
  }
}

async function handleJudge(body) {
  const { ticker, stock_name, stock_data, technical_data, analysis_mode, bull_argument, bear_argument } = body;

  if (!ticker || !stock_name) {
    return new Response(
      JSON.stringify({ detail: "ticker and stock_name are required" }),
      { status: 400, headers: CORS_HEADERS }
    );
  }

  const dataPrompt = formatStockDataPrompt(stock_name, ticker, stock_data || {});
  const techPrompt = formatTechnicalDataPrompt(technical_data || {});

  const judgePrompt = `# Stock: ${stock_name} (${ticker})

## Stock Data Summary:
${dataPrompt}

${techPrompt}

---

## 🐂 Bullish Analyst's Argument:
${bull_argument || "Not available."}

---

## 🐻 Bearish Analyst's Argument:
${bear_argument || "Not available."}

---

Now evaluate both arguments and deliver your verdict. Remember to start with your verdict and confidence score.`;

  try {
    const text = await generateAI(JUDGE_SYSTEM_PROMPT, judgePrompt);
    const verdict = parseVerdict(text);
    return new Response(
      JSON.stringify({
        agent: "⚖️ Judge",
        recommendation: verdict.recommendation,
        confidence: verdict.confidence,
        analysis: verdict.analysis,
        provider: "ai",
        providers_attempted: [],
        errors: {},
      }),
      { status: 200, headers: CORS_HEADERS }
    );
  } catch (err) {
    console.error("Judge verdict failed:", err);
    return new Response(
      JSON.stringify({
        agent: "⚖️ Judge",
        recommendation: "HOLD",
        confidence: 5,
        analysis: "⚠️ The Judge could not deliver a verdict at this time. Please review both arguments and form your own conclusion.",
        provider: "none",
        providers_attempted: [],
        errors: extractErrorInfo(err),
      }),
      { status: 200, headers: CORS_HEADERS }
    );
  }
}

// ── Legacy Combined Debate ─────────────────────────────────────

async function handleCombinedDebate(body) {
  const stockName = (body.stock_name || "").trim();

  if (!stockName) {
    return new Response(
      JSON.stringify({ detail: "stock_name is required" }),
      { status: 400, headers: CORS_HEADERS }
    );
  }

  const ticker = resolveTicker(stockName);
  if (!ticker) {
    const suggestions = getSimilarTickers(stockName);
    const suggestionText = suggestions.length > 0
      ? ` Did you mean: ${suggestions.join(", ")}?`
      : "";
    return new Response(
      JSON.stringify({ detail: `Could not find stock '${stockName}'.${suggestionText}` }),
      { status: 404, headers: CORS_HEADERS }
    );
  }

  let stockData;
  let stockDataError = null;
  try {
    stockData = await fetchStockData(ticker);
  } catch (err) {
    stockDataError = err.message;
    stockData = {
      stock_name: ticker.replace(".NS", "").replace(".BO", ""),
      current_price: null, market_cap: null, pe_ratio: null,
      pb_ratio: null, eps: null, dividend_yield: null,
      "52_week_high": null, "52_week_low": null,
      debt_to_equity: null, roe: null, revenue_growth: null,
      profit_growth: null, promoter_holding: null,
      "1m_return": null, "3m_return": null,
      "6m_return": null, "1y_return": null,
      volume: null, avg_volume: null, sector: null, industry: null,
    };
  }

  const fullName = stockData.stock_name || stockName;
  delete stockData.stock_name;

  const dataPrompt = formatStockDataPrompt(fullName, ticker, stockData, stockDataError);

  const [bullResponse, bearResponse] = await Promise.allSettled([
    generateAI(BULLISH_SYSTEM_PROMPT, dataPrompt),
    generateAI(BEARISH_SYSTEM_PROMPT, dataPrompt),
  ]);

  const bullText = bullResponse.status === "fulfilled" ? bullResponse.value : "⚠️ Bull analysis unavailable.";
  const bearText = bearResponse.status === "fulfilled" ? bearResponse.value : "⚠️ Bear analysis unavailable.";

  const judgePrompt = `# Stock: ${fullName} (${ticker})\n\n## Stock Data:\n${dataPrompt}\n\n---\n\n## 🐂 Bullish:\n${bullText}\n\n---\n\n## 🐻 Bearish:\n${bearText}\n\n---\n\nDeliver your verdict.`;

  let judgeText;
  try {
    judgeText = await generateAI(JUDGE_SYSTEM_PROMPT, judgePrompt);
  } catch {
    judgeText = "⚠️ Judge could not deliver a verdict.";
  }

  const verdict = parseVerdict(judgeText);

  return new Response(
    JSON.stringify({
      ticker,
      stock_name: fullName,
      stock_data: stockData,
      bullish: { agent: "🐂 Bullish Analyst", argument: bullText },
      bearish: { agent: "🐻 Bearish Analyst", argument: bearText },
      verdict: {
        agent: "⚖️ Judge",
        recommendation: verdict.recommendation,
        confidence: verdict.confidence,
        analysis: verdict.analysis,
      },
      disclaimer: "⚠️ This is AI-generated analysis for educational purposes only. Not financial advice.",
    }),
    { status: 200, headers: CORS_HEADERS }
  );
}

// ── Main Handler ───────────────────────────────────────────────

export default async (req, context) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: CORS_HEADERS });
  }

  if (req.method !== "POST") {
    return new Response(
      JSON.stringify({ detail: "Method not allowed" }),
      { status: 405, headers: CORS_HEADERS }
    );
  }

  const url = new URL(req.url);
  const path = url.pathname;

  try {
    const body = await req.json();

    if (path.endsWith("/bull")) {
      return await handleBull(body);
    }
    if (path.endsWith("/bear")) {
      return await handleBear(body);
    }
    if (path.endsWith("/judge")) {
      return await handleJudge(body);
    }

    // Default: combined debate
    return await handleCombinedDebate(body);
  } catch (err) {
    console.error("Debate function error:", err);
    return new Response(
      JSON.stringify({ detail: `Server error: ${err.message}` }),
      { status: 500, headers: CORS_HEADERS }
    );
  }
};

export const config = {
  path: ["/api/debate", "/api/debate/bull", "/api/debate/bear", "/api/debate/judge"],
};
