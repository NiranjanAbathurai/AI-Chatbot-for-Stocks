/**
 * Netlify Function: GET /api/screener/*
 * Stock screener — 5 endpoints: scan, top-buys, top-shorts, patterns, volatile-active.
 * Updated for yahoo-finance2 v4.
 */
import YahooFinance from "yahoo-finance2";
import { NIFTY_50 } from "./lib/nifty-stocks.mjs";
import { detectChartPatterns, calcVolatileMetrics } from "./lib/pattern-detection.mjs";

const yahooFinance = new YahooFinance({ suppressNotices: ["yahooSurvey"] });

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function withRetry(fn, maxRetries = 4, baseDelay = 1500) {
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

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Content-Type": "application/json",
};

// ── RSI ────────────────────────────────────────────────────────

function calcRSI(prices, period = 14) {
  if (!prices || prices.length < period + 1) return null;
  const deltas = [];
  for (let i = 1; i < prices.length; i++) deltas.push(prices[i] - prices[i - 1]);
  const rec = deltas.slice(-period);
  let ag = 0, al = 0;
  for (const d of rec) { if (d > 0) ag += d; else al += Math.abs(d); }
  ag /= period; al /= period;
  if (al === 0) return 100;
  return Math.round((100 - 100 / (1 + ag / al)) * 100) / 100;
}

// ── BUY/SHORT Scoring ──────────────────────────────────────────

function scoreBuy(info, rsi) {
  let s = 0; const r = [];
  const pe = info.trailingPE || info.forwardPE;
  if (pe && pe < 25) { s += Math.min(15, ((25 - pe) / 25) * 15); r.push(`Low P/E: ${pe.toFixed(1)}`); }
  if (rsi !== null && rsi < 30) { s += 15; r.push(`Oversold RSI: ${rsi.toFixed(0)}`); }
  else if (rsi !== null && rsi < 40) { s += 8; r.push(`Near oversold RSI: ${rsi.toFixed(0)}`); }
  const low52 = info.fiftyTwoWeekLow, price = info.currentPrice || info.regularMarketPrice;
  if (low52 && price && low52 > 0) {
    const p = ((price - low52) / low52) * 100;
    if (p <= 10) { s += 10; r.push(`Near 52W low (${p.toFixed(1)}% above)`); } else if (p <= 20) s += 5;
  }
  if (info.revenueGrowth && info.revenueGrowth > 0.15) { s += Math.min(15, (info.revenueGrowth * 100 / 30) * 15); r.push(`Revenue growth: ${(info.revenueGrowth * 100).toFixed(1)}%`); }
  if (info.earningsGrowth && info.earningsGrowth > 0.2) { s += Math.min(15, (info.earningsGrowth * 100 / 40) * 15); r.push(`Earnings growth: ${(info.earningsGrowth * 100).toFixed(1)}%`); }
  if (info.heldPercentInsiders && info.heldPercentInsiders > 0.5) { s += 10; r.push(`High promoter: ${(info.heldPercentInsiders * 100).toFixed(1)}%`); }
  if (info.debtToEquity != null && info.debtToEquity < 100) { s += 10; r.push(`Low debt: D/E ${info.debtToEquity.toFixed(1)}`); }
  const vol = info.volume || info.regularMarketVolume, avgV = info.averageVolume;
  if (vol && avgV && avgV > 0) { const vr = vol / avgV; if (vr > 2) { s += 10; r.push(`Volume spike: ${vr.toFixed(1)}x`); } else if (vr > 1.5) s += 5; }
  return { score: Math.min(s, 100), reasons: r.slice(0, 3) };
}

function scoreShort(info, rsi) {
  let s = 0; const r = [];
  const pe = info.trailingPE || info.forwardPE;
  if (pe && pe > 50) { s += 15; r.push(`High P/E: ${pe.toFixed(1)}`); }
  else if (pe && pe > 35) { s += 8; r.push(`Elevated P/E: ${pe.toFixed(1)}`); }
  if (rsi !== null && rsi > 70) { s += 15; r.push(`Overbought RSI: ${rsi.toFixed(0)}`); }
  else if (rsi !== null && rsi > 65) { s += 8; r.push(`Near overbought RSI: ${rsi.toFixed(0)}`); }
  const high52 = info.fiftyTwoWeekHigh, price = info.currentPrice || info.regularMarketPrice;
  if (high52 && price && high52 > 0) {
    const p = ((high52 - price) / high52) * 100;
    if (p <= 5) { s += 10; r.push(`Near 52W high (${p.toFixed(1)}% below)`); } else if (p <= 10) s += 5;
  }
  if (info.revenueGrowth != null && info.revenueGrowth < 0) { s += Math.min(15, (Math.abs(info.revenueGrowth) * 100 / 20) * 15); r.push(`Revenue decline: ${(info.revenueGrowth * 100).toFixed(1)}%`); }
  if (info.earningsGrowth != null && info.earningsGrowth < 0) { s += Math.min(15, (Math.abs(info.earningsGrowth) * 100 / 20) * 15); r.push(`Earnings decline: ${(info.earningsGrowth * 100).toFixed(1)}%`); }
  if (info.heldPercentInsiders != null && info.heldPercentInsiders < 0.2) { s += 10; r.push(`Low promoter: ${(info.heldPercentInsiders * 100).toFixed(1)}%`); }
  const de = info.debtToEquity;
  if (de != null && de > 200) { s += 10; r.push(`High debt: D/E ${de.toFixed(1)}`); } else if (de != null && de > 150) s += 5;
  const vol = info.volume || info.regularMarketVolume, avgV = info.averageVolume;
  if (vol && avgV && avgV > 0) { const vr = vol / avgV; if (vr < 0.5) { s += 10; r.push(`Low volume: ${vr.toFixed(1)}x`); } else if (vr < 0.7) s += 5; }
  return { score: Math.min(s, 100), reasons: r.slice(0, 3) };
}

// ── BUY/SHORT Scan ─────────────────────────────────────────────

async function analyzeStockBS(stock) {
  try {
    const q = await withRetry(() =>
      yahooFinance.quoteSummary(stock.ticker, {
        modules: ["price", "summaryDetail", "defaultKeyStatistics", "financialData"],
      })
    );
    const pr = q.price || {}, sd = q.summaryDetail || {};
    const ks = q.defaultKeyStatistics || {}, fd = q.financialData || {};
    const info = {
      trailingPE: sd.trailingPE, forwardPE: ks.forwardPE,
      currentPrice: fd.currentPrice || pr.regularMarketPrice,
      regularMarketPrice: pr.regularMarketPrice,
      fiftyTwoWeekHigh: sd.fiftyTwoWeekHigh, fiftyTwoWeekLow: sd.fiftyTwoWeekLow,
      revenueGrowth: fd.revenueGrowth, earningsGrowth: fd.earningsGrowth,
      heldPercentInsiders: ks.heldPercentInsiders, debtToEquity: fd.debtToEquity,
      volume: pr.regularMarketVolume, regularMarketVolume: pr.regularMarketVolume,
      averageVolume: sd.averageVolume,
    };
    let rsi = null;
    try {
      const end = new Date(), start = new Date();
      start.setDate(start.getDate() - 35);
      const hist = await withRetry(() =>
        yahooFinance.chart(stock.ticker, {
          period1: start.toISOString().split("T")[0],
          period2: end.toISOString().split("T")[0],
          interval: "1d",
        })
      );
      const quotes = hist?.quotes || [];
      if (quotes.length > 14) {
        rsi = calcRSI(quotes.map(q2 => q2.close).filter(c => c != null));
      }
    } catch { /* ignore */ }
    return { info, rsi };
  } catch (err) {
    console.warn(`BS analyze error ${stock.name}: ${err.message}`);
    return null;
  }
}

async function scanStocks() {
  const buyR = [], shortR = [];
  const bs = 3;
  for (let i = 0; i < NIFTY_50.length; i += bs) {
    const batch = NIFTY_50.slice(i, i + bs);
    const results = await Promise.allSettled(batch.map(s => analyzeStockBS(s)));
    if (i + bs < NIFTY_50.length) await sleep(1500);
    for (let j = 0; j < results.length; j++) {
      if (results[j].status !== "fulfilled" || !results[j].value) continue;
      const { info, rsi } = results[j].value;
      const b = scoreBuy(info, rsi);
      if (b.score > 20) buyR.push({ name: batch[j].name, ticker: batch[j].ticker, score: Math.round(b.score * 10) / 10, reasons: b.reasons });
      const sh = scoreShort(info, rsi);
      if (sh.score > 20) shortR.push({ name: batch[j].name, ticker: batch[j].ticker, score: Math.round(sh.score * 10) / 10, reasons: sh.reasons });
    }
  }
  buyR.sort((a, b) => b.score - a.score);
  shortR.sort((a, b) => b.score - a.score);
  return { last_scan: new Date().toISOString(), buy_candidates: buyR.slice(0, 5), short_candidates: shortR.slice(0, 5) };
}

// ── Fetch chart OHLCV data ─────────────────────────────────────

async function fetchChart(ticker, months = 6) {
  try {
    const end = new Date(), start = new Date();
    start.setMonth(start.getMonth() - months);
    const res = await withRetry(() =>
      yahooFinance.chart(ticker, {
        period1: start.toISOString().split("T")[0],
        period2: end.toISOString().split("T")[0],
        interval: "1d",
      })
    );
    const quotes = res?.quotes || [];
    if (quotes.length < 30) return null;
    const closes = [], highs = [], lows = [], volumes = [];
    for (const q of quotes) {
      if (q.close == null || q.high == null || q.low == null) continue;
      closes.push(q.close); highs.push(q.high); lows.push(q.low); volumes.push(q.volume || 0);
    }
    if (closes.length < 30) return null;
    const cp = (res?.meta || {}).regularMarketPrice || closes[closes.length - 1];
    return { closes, highs, lows, volumes, currentPrice: cp };
  } catch (err) {
    console.warn(`Chart fetch fail ${ticker}: ${err.message}`);
    return null;
  }
}

// ── Pattern Scan ───────────────────────────────────────────────

async function scanPatterns(typeFilter, patternFilter) {
  const results = [];
  console.log(`Starting pattern scan for ${NIFTY_50.length} stocks...`);

  const batchSize = 3;
  for (let i = 0; i < NIFTY_50.length; i += batchSize) {
    const batch = NIFTY_50.slice(i, i + batchSize);
    const fetches = await Promise.allSettled(
      batch.map(stock => fetchChart(stock.ticker, 6))
    );
    if (i + batchSize < NIFTY_50.length) await sleep(1500);

    for (let j = 0; j < fetches.length; j++) {
      if (fetches[j].status !== "fulfilled" || !fetches[j].value) continue;
      const stock = batch[j];
      const { closes, highs, lows, currentPrice } = fetches[j].value;

      let patterns = detectChartPatterns(closes, highs, lows);
      if (!patterns || patterns.length === 0) continue;

      // Apply type filter
      if (typeFilter) {
        const matchTypes = typeFilter === "sideways" ? new Set(["sideways", "neutral"]) : new Set([typeFilter]);
        patterns = patterns.filter(p => matchTypes.has(p.type));
      }
      // Apply pattern name filter
      if (patternFilter) {
        patterns = patterns.filter(p => p.pattern.toLowerCase().includes(patternFilter.toLowerCase()));
      }
      if (patterns.length === 0) continue;

      results.push({
        name: stock.name,
        ticker: stock.ticker,
        price: currentPrice ? Math.round(currentPrice * 100) / 100 : null,
        patterns,
      });
    }
  }

  // Sort: best reliability first, then most patterns
  const relOrder = { "very high": 4, "high": 3, "medium-high": 2, "medium": 1 };
  results.sort((a, b) => {
    const aRel = Math.max(...a.patterns.map(p => relOrder[p.reliability] || 1));
    const bRel = Math.max(...b.patterns.map(p => relOrder[p.reliability] || 1));
    if (bRel !== aRel) return bRel - aRel;
    return b.patterns.length - a.patterns.length;
  });

  return {
    last_scan: new Date().toISOString(),
    total_scanned: NIFTY_50.length,
    stocks_with_patterns: results.length,
    results,
    cached: false,
  };
}

// ── Volatile/Active Scan ───────────────────────────────────────

async function scanVolatileActive(sortBy, minScore) {
  let results = [];
  console.log(`Starting volatile/active scan for ${NIFTY_50.length} stocks...`);

  const batchSize = 3;
  for (let i = 0; i < NIFTY_50.length; i += batchSize) {
    const batch = NIFTY_50.slice(i, i + batchSize);
    const fetches = await Promise.allSettled(
      batch.map(stock => fetchChart(stock.ticker, 3))
    );
    if (i + batchSize < NIFTY_50.length) await sleep(1500);

    for (let j = 0; j < fetches.length; j++) {
      if (fetches[j].status !== "fulfilled" || !fetches[j].value) continue;
      const stock = batch[j];
      const { closes, highs, lows, volumes, currentPrice } = fetches[j].value;

      const metrics = calcVolatileMetrics(closes, highs, lows, volumes, currentPrice);
      if (!metrics) continue;

      results.push({
        name: stock.name,
        ticker: stock.ticker,
        ...metrics,
      });
    }
  }

  // Apply min_score filter
  if (minScore > 0) {
    results = results.filter(r => r.volatility_score >= minScore);
  }

  // Sort
  const validSorts = new Set(["volatility_score", "volume_ratio", "atr_pct", "price_range_pct"]);
  const sortField = validSorts.has(sortBy) ? sortBy : "volatility_score";
  results.sort((a, b) => (b[sortField] || 0) - (a[sortField] || 0));

  return {
    last_scan: new Date().toISOString(),
    total_scanned: NIFTY_50.length,
    results,
    cached: false,
  };
}

// ── Handler ────────────────────────────────────────────────────

export default async (req, context) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: CORS });
  }
  if (req.method !== "GET") {
    return new Response(JSON.stringify({ detail: "Method not allowed" }), { status: 405, headers: CORS });
  }

  const url = new URL(req.url);
  const path = url.pathname;

  try {
    // /api/screener/patterns
    if (path.endsWith("/patterns")) {
      const typeFilter = url.searchParams.get("type") || "";
      const patternFilter = url.searchParams.get("pattern") || "";
      const result = await scanPatterns(typeFilter || null, patternFilter || null);
      return new Response(JSON.stringify(result), { status: 200, headers: CORS });
    }

    // /api/screener/volatile-active
    if (path.endsWith("/volatile-active")) {
      const sortBy = url.searchParams.get("sort_by") || "volatility_score";
      const minScore = parseFloat(url.searchParams.get("min_score") || "0") || 0;
      const result = await scanVolatileActive(sortBy, minScore);
      return new Response(JSON.stringify(result), { status: 200, headers: CORS });
    }

    // /api/screener/top-buys
    if (path.endsWith("/top-buys")) {
      const result = await scanStocks();
      return new Response(JSON.stringify({ stocks: result.buy_candidates }), { status: 200, headers: CORS });
    }

    // /api/screener/top-shorts
    if (path.endsWith("/top-shorts")) {
      const result = await scanStocks();
      return new Response(JSON.stringify({ stocks: result.short_candidates }), { status: 200, headers: CORS });
    }

    // /api/screener/scan (default)
    const result = await scanStocks();
    return new Response(JSON.stringify(result), { status: 200, headers: CORS });

  } catch (err) {
    console.error("Screener function error:", err);
    return new Response(
      JSON.stringify({ detail: `Scan failed: ${err.message}` }),
      { status: 500, headers: CORS }
    );
  }
};

export const config = {
  path: [
    "/api/screener/scan",
    "/api/screener/top-buys",
    "/api/screener/top-shorts",
    "/api/screener/patterns",
    "/api/screener/volatile-active",
  ],
};
