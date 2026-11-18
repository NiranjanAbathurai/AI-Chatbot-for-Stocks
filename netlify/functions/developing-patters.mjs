/**
 * Netlify Function: /api/developing-patterns/*
 * Developing pattern scanner — scans NIFTY 50 for developing chart patterns.
 */
import YahooFinance from "yahoo-finance2";
import { NIFTY_50 } from "./lib/nifty-stocks.mjs";
import { detectDevelopingPatterns } from "./lib/developing-patterns.mjs";

const yahooFinance = new YahooFinance({ suppressNotices: ["yahooSurvey"] });

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Content-Type": "application/json",
};

const TF_CONFIG = {
  "15m": { months: 0, days: 5, interval: "15m" },
  "1h": { months: 1, days: 0, interval: "60m" },
  "4h": { months: 3, days: 0, interval: "1d" },
  "1d": { months: 6, days: 0, interval: "1d" },
};

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function withRetry(fn, maxRetries = 3, baseDelay = 1500) {
  let lastError;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try { return await fn(); } catch (err) {
      lastError = err;
      const msg = (err.message || "").toLowerCase();
      const ok = msg.includes("too many") || msg.includes("429") || msg.includes("rate limit") ||
        msg.includes("not valid json") || msg.includes("fetch failed") || msg.includes("network") ||
        msg.includes("econnreset") || msg.includes("timeout") || msg.includes("socket hang up");
      if (ok && attempt < maxRetries) {
        await sleep(baseDelay * Math.pow(2, attempt) + Math.random() * 500);
        continue;
      }
      throw err;
    }
  }
  throw lastError;
}

async function fetchChartData(ticker, tfKey) {
  const tf = TF_CONFIG[tfKey] || TF_CONFIG["1d"];
  const end = new Date(), start = new Date();
  if (tf.months) start.setMonth(start.getMonth() - tf.months);
  if (tf.days) start.setDate(start.getDate() - tf.days);

  const res = await withRetry(() =>
    yahooFinance.chart(ticker, {
      period1: start.toISOString().split("T")[0],
      period2: end.toISOString().split("T")[0],
      interval: tf.interval,
    })
  );

  const quotes = res?.quotes || [];
  if (quotes.length < 20) return null;

  const closes = [], highs = [], lows = [], volumes = [];
  let lastTs = "";
  for (const q of quotes) {
    if (q.close == null || q.high == null || q.low == null) continue;
    closes.push(q.close);
    highs.push(q.high);
    lows.push(q.low);
    volumes.push(q.volume || 0);
    if (q.date) lastTs = new Date(q.date).toISOString();
  }

  if (closes.length < 20) return null;
  const currentPrice = (res?.meta || {}).regularMarketPrice || closes[closes.length - 1];
  return { closes, highs, lows, volumes, currentPrice, lastTs };
}

async function scanDevelopingPatterns(timeframe, typeFilter, patternFilter, stageFilter, minConfidence) {
  const results = [];
  console.log(`Starting developing pattern scan for ${NIFTY_50.length} stocks (tf=${timeframe})...`);

  const batchSize = 3;
  for (let i = 0; i < NIFTY_50.length; i += batchSize) {
    const batch = NIFTY_50.slice(i, i + batchSize);
    const fetches = await Promise.allSettled(
      batch.map(stock => fetchChartData(stock.ticker, timeframe))
    );
    if (i + batchSize < NIFTY_50.length) await sleep(1500);

    for (let j = 0; j < fetches.length; j++) {
      if (fetches[j].status !== "fulfilled" || !fetches[j].value) continue;
      const stock = batch[j];
      const data = fetches[j].value;

      let patterns = detectDevelopingPatterns(data.closes, data.highs, data.lows, data.volumes, data.currentPrice);
      if (!patterns || patterns.length === 0) continue;

      // Add metadata to each pattern
      for (const p of patterns) {
        p.last_candle_time = data.lastTs;
        p.data_status = "delayed";
        p.timeframe = timeframe;
      }

      // Apply filters
      if (typeFilter) patterns = patterns.filter(p => p.type === typeFilter);
      if (patternFilter) patterns = patterns.filter(p => (p.pattern || "").toLowerCase().includes(patternFilter.toLowerCase()));
      if (stageFilter) patterns = patterns.filter(p => (p.stage || "").toLowerCase().includes(stageFilter.toLowerCase()));
      if (minConfidence > 0) patterns = patterns.filter(p => (p.structure_confidence || 0) >= minConfidence);

      if (patterns.length === 0) continue;

      results.push({
        name: stock.name,
        ticker: stock.ticker,
        price: data.currentPrice ? Math.round(data.currentPrice * 100) / 100 : null,
        last_candle_time: data.lastTs,
        data_status: "delayed",
        patterns,
      });
    }
  }

  // Sort by best pattern confidence
  results.sort((a, b) => {
    const aMax = Math.max(...a.patterns.map(p => p.structure_confidence || 0));
    const bMax = Math.max(...b.patterns.map(p => p.structure_confidence || 0));
    return bMax - aMax;
  });

  return {
    last_scan: new Date().toISOString(),
    total_scanned: NIFTY_50.length,
    stocks_with_patterns: results.length,
    timeframe,
    results,
    cached: false,
  };
}

export default async (req, context) => {
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
  if (req.method !== "GET") return new Response(JSON.stringify({ detail: "Method not allowed" }), { status: 405, headers: CORS });

  const url = new URL(req.url);
  const path = url.pathname;

  try {
    // /api/developing-patterns/cached — return empty (no persistent cache in serverless)
    if (path.endsWith("/cached")) {
      return new Response(JSON.stringify({ results: [], cached: false, message: "No cached scan available in serverless mode. Run a scan." }), { status: 200, headers: CORS });
    }

    // /api/developing-patterns/scan
    const timeframe = url.searchParams.get("timeframe") || "1d";
    const validTF = new Set(["15m", "1h", "4h", "1d"]);
    if (!validTF.has(timeframe)) {
      return new Response(JSON.stringify({ detail: `Invalid timeframe '${timeframe}'. Valid: ${[...validTF].join(", ")}` }), { status: 400, headers: CORS });
    }

    const typeFilter = url.searchParams.get("type") || null;
    const patternFilter = url.searchParams.get("pattern") || null;
    const stageFilter = url.searchParams.get("stage") || null;
    const minConfidence = parseFloat(url.searchParams.get("min_confidence") || "0") || 0;

    const result = await scanDevelopingPatterns(timeframe, typeFilter, patternFilter, stageFilter, minConfidence);
    return new Response(JSON.stringify(result), { status: 200, headers: CORS });

  } catch (err) {
    console.error("Developing patterns function error:", err);
    return new Response(JSON.stringify({ detail: `Scan failed: ${err.message}` }), { status: 500, headers: CORS });
  }
};

export const config = {
  path: [
    "/api/developing-patterns/scan",
    "/api/developing-patterns/cached",
  ],
};
