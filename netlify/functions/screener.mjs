/**
 * Netlify Function: GET /api/screener/*
 * Stock screener — scans NIFTY 50 for BUY and SHORT signals.
 *
 * Endpoints:
 *   GET /api/screener/scan       — Full scan (may be slow)
 *   GET /api/screener/top-buys   — Top BUY candidates
 *   GET /api/screener/top-shorts — Top SHORT candidates
 */

import yahooFinance from "yahoo-finance2";
import { NIFTY_50 } from "./lib/nifty-stocks.mjs";

// Suppress yahoo-finance2 validation errors (e.g., non-JSON responses)
yahooFinance.setGlobalConfig({
  validation: { logErrors: false },
});

/**
 * Sleep for a given number of milliseconds.
 */
function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Retry a function with exponential backoff.
 */
async function withRetry(fn, maxRetries = 3, baseDelay = 1000) {
  let lastError;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      lastError = err;
      const msg = (err.message || "").toLowerCase();
      const isRetryable =
        msg.includes("too many requests") ||
        msg.includes("429") ||
        msg.includes("rate limit") ||
        msg.includes("not valid json");

      if (isRetryable && attempt < maxRetries) {
        const delay = baseDelay * Math.pow(2, attempt) + Math.random() * 500;
        console.log(
          `Rate limited, retrying in ${Math.round(delay)}ms (attempt ${attempt + 1}/${maxRetries})...`
        );
        await sleep(delay);
        continue;
      }
      throw err;
    }
  }
  throw lastError;
}

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Content-Type": "application/json",
};

// ── RSI Calculation ────────────────────────────────────────────

function calculateRSI(prices, period = 14) {
  if (!prices || prices.length < period + 1) return null;
  try {
    const deltas = [];
    for (let i = 1; i < prices.length; i++) {
      deltas.push(prices[i] - prices[i - 1]);
    }

    const recentDeltas = deltas.slice(-period);
    let avgGain = 0;
    let avgLoss = 0;

    for (const d of recentDeltas) {
      if (d > 0) avgGain += d;
      else avgLoss += Math.abs(d);
    }

    avgGain /= period;
    avgLoss /= period;

    if (avgLoss === 0) return 100.0;
    const rs = avgGain / avgLoss;
    return Math.round((100 - 100 / (1 + rs)) * 100) / 100;
  } catch {
    return null;
  }
}

// ── Scoring Functions ──────────────────────────────────────────

function scoreBuySignal(info, rsi) {
  let score = 0;
  const reasons = [];

  // P/E ratio below 25 (value play) — weight 15%
  const pe = info.trailingPE || info.forwardPE;
  if (pe && pe < 25) {
    const points = Math.min(15, ((25 - pe) / 25) * 15);
    score += points;
    reasons.push(`Low P/E: ${pe.toFixed(1)}`);
  }

  // RSI below 30 (oversold) — weight 15%
  if (rsi !== null && rsi < 30) {
    score += 15;
    reasons.push(`Oversold RSI: ${rsi.toFixed(0)}`);
  } else if (rsi !== null && rsi < 40) {
    score += 8;
    reasons.push(`Near oversold RSI: ${rsi.toFixed(0)}`);
  }

  // Price near 52-week low (within 10%) — weight 10%
  const low52 = info.fiftyTwoWeekLow;
  const price = info.currentPrice || info.regularMarketPrice;
  if (low52 && price && low52 > 0) {
    const pctAboveLow = ((price - low52) / low52) * 100;
    if (pctAboveLow <= 10) {
      score += 10;
      reasons.push(`Near 52W low (${pctAboveLow.toFixed(1)}% above)`);
    } else if (pctAboveLow <= 20) {
      score += 5;
    }
  }

  // Revenue growth > 15% — weight 15%
  const revGrowth = info.revenueGrowth;
  if (revGrowth && revGrowth > 0.15) {
    score += Math.min(15, (revGrowth * 100) / 30 * 15);
    reasons.push(`Revenue growth: ${(revGrowth * 100).toFixed(1)}%`);
  }

  // Profit growth > 20% — weight 15%
  const earnGrowth = info.earningsGrowth;
  if (earnGrowth && earnGrowth > 0.2) {
    score += Math.min(15, (earnGrowth * 100) / 40 * 15);
    reasons.push(`Earnings growth: ${(earnGrowth * 100).toFixed(1)}%`);
  }

  // Promoter holding > 50% — weight 10%
  const insider = info.heldPercentInsiders;
  if (insider && insider > 0.5) {
    score += 10;
    reasons.push(`High promoter holding: ${(insider * 100).toFixed(1)}%`);
  }

  // Debt-to-equity < 1 — weight 10%
  const de = info.debtToEquity;
  if (de !== undefined && de !== null && de < 100) {
    score += 10;
    reasons.push(`Low debt: D/E ${de.toFixed(1)}`);
  }

  // Volume spike — weight 10%
  const vol = info.volume || info.regularMarketVolume;
  const avgVol = info.averageVolume;
  if (vol && avgVol && avgVol > 0) {
    const volRatio = vol / avgVol;
    if (volRatio > 2) {
      score += 10;
      reasons.push(`Volume spike: ${volRatio.toFixed(1)}x avg`);
    } else if (volRatio > 1.5) {
      score += 5;
    }
  }

  return { score: Math.min(score, 100), reasons: reasons.slice(0, 3) };
}

function scoreShortSignal(info, rsi) {
  let score = 0;
  const reasons = [];

  // P/E ratio very high — weight 15%
  const pe = info.trailingPE || info.forwardPE;
  if (pe && pe > 50) {
    score += 15;
    reasons.push(`High P/E: ${pe.toFixed(1)}`);
  } else if (pe && pe > 35) {
    score += 8;
    reasons.push(`Elevated P/E: ${pe.toFixed(1)}`);
  }

  // RSI above 70 (overbought) — weight 15%
  if (rsi !== null && rsi > 70) {
    score += 15;
    reasons.push(`Overbought RSI: ${rsi.toFixed(0)}`);
  } else if (rsi !== null && rsi > 65) {
    score += 8;
    reasons.push(`Near overbought RSI: ${rsi.toFixed(0)}`);
  }

  // Price near 52-week high — weight 10%
  const high52 = info.fiftyTwoWeekHigh;
  const price = info.currentPrice || info.regularMarketPrice;
  if (high52 && price && high52 > 0) {
    const pctBelowHigh = ((high52 - price) / high52) * 100;
    if (pctBelowHigh <= 5) {
      score += 10;
      reasons.push(`Near 52W high (${pctBelowHigh.toFixed(1)}% below)`);
    } else if (pctBelowHigh <= 10) {
      score += 5;
    }
  }

  // Revenue decline — weight 15%
  const revGrowth = info.revenueGrowth;
  if (revGrowth !== undefined && revGrowth !== null && revGrowth < 0) {
    score += Math.min(15, (Math.abs(revGrowth) * 100) / 20 * 15);
    reasons.push(`Revenue decline: ${(revGrowth * 100).toFixed(1)}%`);
  }

  // Profit decline — weight 15%
  const earnGrowth = info.earningsGrowth;
  if (earnGrowth !== undefined && earnGrowth !== null && earnGrowth < 0) {
    score += Math.min(15, (Math.abs(earnGrowth) * 100) / 20 * 15);
    reasons.push(`Earnings decline: ${(earnGrowth * 100).toFixed(1)}%`);
  }

  // Low promoter holding — weight 10%
  const insider = info.heldPercentInsiders;
  if (insider !== undefined && insider !== null && insider < 0.2) {
    score += 10;
    reasons.push(`Low promoter holding: ${(insider * 100).toFixed(1)}%`);
  }

  // High debt — weight 10%
  const de = info.debtToEquity;
  if (de !== undefined && de !== null && de > 200) {
    score += 10;
    reasons.push(`High debt: D/E ${de.toFixed(1)}`);
  } else if (de !== undefined && de !== null && de > 150) {
    score += 5;
  }

  // Volume drying up — weight 10%
  const vol = info.volume || info.regularMarketVolume;
  const avgVol = info.averageVolume;
  if (vol && avgVol && avgVol > 0) {
    const volRatio = vol / avgVol;
    if (volRatio < 0.5) {
      score += 10;
      reasons.push(`Low volume: ${volRatio.toFixed(1)}x avg`);
    } else if (volRatio < 0.7) {
      score += 5;
    }
  }

  return { score: Math.min(score, 100), reasons: reasons.slice(0, 3) };
}

// ── Stock Analysis ─────────────────────────────────────────────

async function analyzeStock(stock) {
  try {
    // Fetch quote summary with retry
    const quote = await withRetry(() =>
      yahooFinance.quoteSummary(stock.ticker, {
        modules: ["price", "summaryDetail", "defaultKeyStatistics", "financialData"],
      })
    );

    const price = quote.price || {};
    const summary = quote.summaryDetail || {};
    const keyStats = quote.defaultKeyStatistics || {};
    const financial = quote.financialData || {};

    // Build info object similar to yfinance's .info
    const info = {
      trailingPE: summary.trailingPE,
      forwardPE: keyStats.forwardPE,
      currentPrice: financial.currentPrice || price.regularMarketPrice,
      regularMarketPrice: price.regularMarketPrice,
      fiftyTwoWeekHigh: summary.fiftyTwoWeekHigh,
      fiftyTwoWeekLow: summary.fiftyTwoWeekLow,
      revenueGrowth: financial.revenueGrowth,
      earningsGrowth: financial.earningsGrowth,
      heldPercentInsiders: keyStats.heldPercentInsiders,
      debtToEquity: financial.debtToEquity,
      volume: price.regularMarketVolume,
      regularMarketVolume: price.regularMarketVolume,
      averageVolume: summary.averageVolume,
    };

    // Fetch 1-month history for RSI
    let rsi = null;
    try {
      const endDate = new Date();
      const startDate = new Date();
      startDate.setDate(startDate.getDate() - 35); // ~5 weeks for RSI(14)

      const histResult = await withRetry(() =>
        yahooFinance.chart(stock.ticker, {
          period1: startDate.toISOString().split("T")[0],
          period2: endDate.toISOString().split("T")[0],
          interval: "1d",
        })
      );

      const quotes = histResult?.quotes || [];
      if (quotes.length > 14) {
        const closePrices = quotes.map((q) => q.close).filter((c) => c != null);
        rsi = calculateRSI(closePrices);
      }
    } catch {
      // Historical data may not be available
    }

    return { info, rsi };
  } catch (err) {
    console.warn(`Error analyzing ${stock.name}: ${err.message}`);
    return null;
  }
}

// ── Main Scan ──────────────────────────────────────────────────

async function scanStocks() {
  const buyResults = [];
  const shortResults = [];

  console.log(`Starting stock scan for ${NIFTY_50.length} stocks...`);

  // Process in batches of 3 to avoid rate limiting (reduced from 5)
  const batchSize = 3;
  for (let i = 0; i < NIFTY_50.length; i += batchSize) {
    const batch = NIFTY_50.slice(i, i + batchSize);
    const results = await Promise.allSettled(
      batch.map((stock) => analyzeStock(stock))
    );

    // Add delay between batches to avoid rate limiting
    if (i + batchSize < NIFTY_50.length) {
      await sleep(1500);
    }

    for (let j = 0; j < results.length; j++) {
      const result = results[j];
      if (result.status !== "fulfilled" || !result.value) continue;

      const stock = batch[j];
      const { info, rsi } = result.value;

      // Score for BUY
      const buy = scoreBuySignal(info, rsi);
      if (buy.score > 20) {
        buyResults.push({
          name: stock.name,
          ticker: stock.ticker,
          score: Math.round(buy.score * 10) / 10,
          reasons: buy.reasons,
        });
      }

      // Score for SHORT
      const short = scoreShortSignal(info, rsi);
      if (short.score > 20) {
        shortResults.push({
          name: stock.name,
          ticker: stock.ticker,
          score: Math.round(short.score * 10) / 10,
          reasons: short.reasons,
        });
      }
    }
  }

  // Sort by score descending, take top 5
  buyResults.sort((a, b) => b.score - a.score);
  shortResults.sort((a, b) => b.score - a.score);

  return {
    last_scan: new Date().toISOString(),
    buy_candidates: buyResults.slice(0, 5),
    short_candidates: shortResults.slice(0, 5),
  };
}

// ── Handler ────────────────────────────────────────────────────

export default async (req, context) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: CORS_HEADERS });
  }

  if (req.method !== "GET") {
    return new Response(
      JSON.stringify({ detail: "Method not allowed" }),
      { status: 405, headers: CORS_HEADERS }
    );
  }

  const url = new URL(req.url);
  const path = url.pathname;

  try {
    // Determine which endpoint was called
    if (path.endsWith("/top-buys")) {
      const result = await scanStocks();
      return new Response(
        JSON.stringify({ stocks: result.buy_candidates }),
        { status: 200, headers: CORS_HEADERS }
      );
    }

    if (path.endsWith("/top-shorts")) {
      const result = await scanStocks();
      return new Response(
        JSON.stringify({ stocks: result.short_candidates }),
        { status: 200, headers: CORS_HEADERS }
      );
    }

    // Default: full scan
    const result = await scanStocks();
    return new Response(JSON.stringify(result), {
      status: 200,
      headers: CORS_HEADERS,
    });
  } catch (err) {
    console.error("Screener function error:", err);
    return new Response(
      JSON.stringify({ detail: `Scan failed: ${err.message}` }),
      { status: 500, headers: CORS_HEADERS }
    );
  }
};

export const config = {
  path: ["/api/screener/scan", "/api/screener/top-buys", "/api/screener/top-shorts"],
};
