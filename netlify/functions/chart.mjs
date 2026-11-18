/**
 * Netlify Function: /api/chart/*
 * Chart endpoints: pattern-chart (JSON), pattern-image-all (JSON), pattern-image (not supported in serverless)
 */
import YahooFinance from "yahoo-finance2";
import { detectDevelopingPatterns } from "./lib/developing-patterns.mjs";
import { detectChartPatterns } from "./lib/pattern-detection.mjs";
import { generatePatternDrawings } from "./lib/chart-drawings.mjs";

const yahooFinance = new YahooFinance({ suppressNotices: ["yahooSurvey"] });

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Content-Type": "application/json",
};

const TF_CONFIG = {
  "15m": { period1Months: 0, period1Days: 5, interval: "15m" },
  "1h": { period1Months: 1, period1Days: 0, interval: "60m" },
  "4h": { period1Months: 3, period1Days: 0, interval: "1d" },
  "1d": { period1Months: 6, period1Days: 0, interval: "1d" },
};

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function withRetry(fn, maxRetries = 3, baseDelay = 1500) {
  let lastError;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try { return await fn(); } catch (err) {
      lastError = err;
      const msg = (err.message || "").toLowerCase();
      const retryable = msg.includes("too many") || msg.includes("429") || msg.includes("rate limit") ||
        msg.includes("not valid json") || msg.includes("fetch failed") || msg.includes("network");
      if (retryable && attempt < maxRetries) {
        await sleep(baseDelay * Math.pow(2, attempt) + Math.random() * 500);
        continue;
      }
      throw err;
    }
  }
  throw lastError;
}

async function fetchChart(ticker, tfKey) {
  const tf = TF_CONFIG[tfKey] || TF_CONFIG["1d"];
  const end = new Date(), start = new Date();
  if (tf.period1Months) start.setMonth(start.getMonth() - tf.period1Months);
  if (tf.period1Days) start.setDate(start.getDate() - tf.period1Days);

  if (!ticker.endsWith(".NS") && !ticker.startsWith("^")) ticker += ".NS";

  const res = await withRetry(() =>
    yahooFinance.chart(ticker, {
      period1: start.toISOString().split("T")[0],
      period2: end.toISOString().split("T")[0],
      interval: tf.interval,
    })
  );

  const quotes = res?.quotes || [];
  if (quotes.length < 20) return null;

  const opens = [], highs = [], lows = [], closes = [], volumes = [], timestamps = [];
  for (const q of quotes) {
    if (q.close == null || q.high == null || q.low == null || q.open == null) continue;
    opens.push(q.open);
    highs.push(q.high);
    lows.push(q.low);
    closes.push(q.close);
    volumes.push(q.volume || 0);
    timestamps.push(q.date ? new Date(q.date).toISOString() : "");
  }

  if (closes.length < 20) return null;
  const currentPrice = (res?.meta || {}).regularMarketPrice || closes[closes.length - 1];
  const lastTs = timestamps[timestamps.length - 1];

  return { opens, highs, lows, closes, volumes, timestamps, currentPrice, lastTs, ticker };
}

function prepareOHLC(data, maxBars = 80) {
  const n = data.closes.length;
  const start = Math.max(0, n - maxBars);
  const bars = [];
  for (let i = start; i < n; i++) {
    bars.push({
      o: Math.round(data.opens[i] * 100) / 100,
      h: Math.round(data.highs[i] * 100) / 100,
      l: Math.round(data.lows[i] * 100) / 100,
      c: Math.round(data.closes[i] * 100) / 100,
      v: data.volumes[i],
      t: data.timestamps[i],
    });
  }
  return bars;
}

export default async (req, context) => {
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
  if (req.method !== "GET") return new Response(JSON.stringify({ detail: "Method not allowed" }), { status: 405, headers: CORS });

  const url = new URL(req.url);
  const path = url.pathname;
  const ticker = url.searchParams.get("ticker");
  const timeframe = url.searchParams.get("timeframe") || "1d";
  const maxBars = parseInt(url.searchParams.get("max_bars") || "80") || 80;
  const detector = url.searchParams.get("detector") || "developing";

  if (!ticker) return new Response(JSON.stringify({ detail: "ticker parameter required" }), { status: 400, headers: CORS });

  const validTF = new Set(["15m", "1h", "4h", "1d"]);
  if (!validTF.has(timeframe)) return new Response(JSON.stringify({ detail: `Invalid timeframe. Valid: ${[...validTF].join(", ")}` }), { status: 400, headers: CORS });

  try {
    // pattern-image returns PNG — not possible in serverless JS, return error
    if (path.endsWith("/pattern-image") && !path.endsWith("/pattern-image-all")) {
      return new Response(JSON.stringify({ detail: "Pattern image generation is not available in serverless mode. Use the interactive chart viewer instead." }), { status: 501, headers: CORS });
    }

    const data = await fetchChart(ticker, timeframe);
    if (!data) return new Response(JSON.stringify({ detail: `Insufficient chart data for ${ticker}` }), { status: 404, headers: CORS });

    // Detect patterns
    let rawPatterns;
    if (detector === "developing") {
      rawPatterns = detectDevelopingPatterns(data.closes, data.highs, data.lows, data.volumes, data.currentPrice);
    } else {
      rawPatterns = detectChartPatterns(data.closes, data.highs, data.lows);
    }

    // /api/chart/pattern-image-all — metadata + image URLs
    if (path.endsWith("/pattern-image-all")) {
      const results = rawPatterns.map((pat, i) => ({
        index: i,
        pattern: pat.pattern || "Unknown",
        type: pat.type || "neutral",
        stage: pat.stage || "",
        structure_confidence: pat.structure_confidence,
        description: pat.description || "",
        target: pat.target,
        invalidation: pat.invalidation,
        image_url: `/api/chart/pattern-image?ticker=${encodeURIComponent(data.ticker)}&timeframe=${timeframe}&max_bars=${maxBars}&detector=${detector}&pattern_index=${i}`,
      }));
      return new Response(JSON.stringify({
        ticker: data.ticker,
        timeframe,
        current_price: Math.round(data.currentPrice * 100) / 100,
        pattern_count: results.length,
        patterns: results,
      }), { status: 200, headers: CORS });
    }

    // /api/chart/pattern-chart — OHLC + drawings
    const n = data.closes.length;
    const chartStart = Math.max(0, n - maxBars);
    const patternsWithDrawings = rawPatterns.map(pat => {
      const drawings = generatePatternDrawings(pat, data.closes, data.highs, data.lows, n);
      const adjusted = drawings.map(d => {
        const ad = { ...d };
        if ("x" in ad) ad.x -= chartStart;
        if ("x1" in ad) ad.x1 -= chartStart;
        if ("x2" in ad) ad.x2 -= chartStart;
        if (ad.points) ad.points = ad.points.map(p => ({ x: p.x - chartStart, y: p.y }));
        // Skip if entirely outside
        if ("x1" in ad && "x2" in ad && ad.x2 < 0) return null;
        if ("x1" in ad) ad.x1 = Math.max(0, ad.x1);
        if ("x" in ad && ad.x < 0) return null;
        return ad;
      }).filter(Boolean);
      return { ...pat, drawings: adjusted };
    });

    const ohlc = prepareOHLC(data, maxBars);

    return new Response(JSON.stringify({
      ticker: data.ticker,
      timeframe,
      current_price: Math.round(data.currentPrice * 100) / 100,
      last_candle_time: data.lastTs,
      total_bars: ohlc.length,
      ohlc,
      patterns: patternsWithDrawings,
    }), { status: 200, headers: CORS });

  } catch (err) {
    console.error("Chart function error:", err);
    return new Response(JSON.stringify({ detail: `Chart error: ${err.message}` }), { status: 500, headers: CORS });
  }
};

export const config = {
  path: [
    "/api/chart/pattern-chart",
    "/api/chart/pattern-image",
    "/api/chart/pattern-image-all",
  ],
};
