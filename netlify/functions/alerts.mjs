/**
 * Netlify Function: /api/alerts
 * Alert system — checks watchlist stocks for alert triggers.
 *
 * Endpoints:
 *   GET  /api/alerts          — Get recent alert history
 *   POST /api/alerts/scan-now — Trigger immediate alert scan on watchlist
 */

import yahooFinance from "yahoo-finance2";
import { getValue, setValue } from "./lib/store.mjs";

const WATCHLIST_KEY = "watchlist";
const ALERTS_KEY = "alerts_history";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
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

// ── Alert Checks ───────────────────────────────────────────────

async function checkStockAlerts(ticker, stockName) {
  const alerts = [];

  try {
    const quote = await yahooFinance.quoteSummary(ticker, {
      modules: ["price", "summaryDetail"],
    });

    const price = quote.price || {};
    const summary = quote.summaryDetail || {};

    const currentPrice = price.regularMarketPrice;
    const high52 = summary.fiftyTwoWeekHigh;
    const low52 = summary.fiftyTwoWeekLow;
    const prevClose = price.regularMarketPreviousClose;
    const volume = price.regularMarketVolume;
    const avgVolume = summary.averageVolume;

    if (!currentPrice) return alerts;

    // 1. Price Breakout — above 52-week high
    if (high52 && currentPrice >= high52) {
      alerts.push({
        ticker,
        stock_name: stockName,
        trigger: "52-Week High Breakout",
        message: `Price ₹${currentPrice.toFixed(2)} has reached/exceeded 52-week high of ₹${high52.toFixed(2)}`,
        priority: "high",
        timestamp: new Date().toISOString(),
      });
    }

    // 2. Price Breakdown — below 52-week low
    if (low52 && currentPrice <= low52) {
      alerts.push({
        ticker,
        stock_name: stockName,
        trigger: "52-Week Low Breakdown",
        message: `Price ₹${currentPrice.toFixed(2)} has reached/fallen below 52-week low of ₹${low52.toFixed(2)}`,
        priority: "high",
        timestamp: new Date().toISOString(),
      });
    }

    // 3. Big Daily Move — > 5% change
    if (prevClose && prevClose > 0) {
      const dailyChange = ((currentPrice - prevClose) / prevClose) * 100;
      if (Math.abs(dailyChange) > 5) {
        const direction = dailyChange > 0 ? "up" : "down";
        alerts.push({
          ticker,
          stock_name: stockName,
          trigger: `Big Daily Move (${direction})`,
          message: `Price moved ${dailyChange >= 0 ? "+" : ""}${dailyChange.toFixed(2)}% today (₹${prevClose.toFixed(2)} → ₹${currentPrice.toFixed(2)})`,
          priority: "medium",
          timestamp: new Date().toISOString(),
        });
      }
    }

    // 4. Volume Spike — > 3x average
    if (volume && avgVolume && avgVolume > 0) {
      const volRatio = volume / avgVolume;
      if (volRatio > 3) {
        alerts.push({
          ticker,
          stock_name: stockName,
          trigger: "Volume Spike",
          message: `Volume ${volume.toLocaleString()} is ${volRatio.toFixed(1)}x the 20-day average (${avgVolume.toLocaleString()})`,
          priority: "medium",
          timestamp: new Date().toISOString(),
        });
      }
    }

    // 5. RSI Extreme
    try {
      const endDate = new Date();
      const startDate = new Date();
      startDate.setDate(startDate.getDate() - 35);

      const histResult = await yahooFinance.chart(ticker, {
        period1: startDate.toISOString().split("T")[0],
        period2: endDate.toISOString().split("T")[0],
        interval: "1d",
      });

      const quotes = histResult?.quotes || [];
      if (quotes.length > 14) {
        const closePrices = quotes.map((q) => q.close).filter((c) => c != null);
        const rsi = calculateRSI(closePrices);

        if (rsi !== null && rsi < 25) {
          alerts.push({
            ticker,
            stock_name: stockName,
            trigger: "RSI Extremely Oversold",
            message: `RSI at ${rsi.toFixed(0)} — stock is extremely oversold`,
            priority: "medium",
            timestamp: new Date().toISOString(),
          });
        } else if (rsi !== null && rsi > 80) {
          alerts.push({
            ticker,
            stock_name: stockName,
            trigger: "RSI Extremely Overbought",
            message: `RSI at ${rsi.toFixed(0)} — stock is extremely overbought`,
            priority: "medium",
            timestamp: new Date().toISOString(),
          });
        }
      }
    } catch {
      // Historical data may not be available
    }
  } catch (err) {
    console.warn(`Error checking alerts for ${ticker}: ${err.message}`);
  }

  return alerts;
}

// ── Alert History ──────────────────────────────────────────────

async function getAlertsHistory(limit = 50) {
  const data = await getValue(ALERTS_KEY);
  const alerts = Array.isArray(data) ? data : [];
  return alerts.slice(-limit);
}

async function saveAlerts(newAlerts) {
  const existing = await getAlertsHistory(500);
  const combined = [...existing, ...newAlerts];
  // Keep only last 500 alerts
  const trimmed = combined.slice(-500);
  await setValue(ALERTS_KEY, trimmed);
}

// ── Handler ────────────────────────────────────────────────────

export default async (req, context) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: CORS_HEADERS });
  }

  const url = new URL(req.url);
  const path = url.pathname;

  try {
    // ── GET /api/alerts — Get alert history ─────────────────
    if (req.method === "GET") {
      const alerts = await getAlertsHistory(50);
      return new Response(
        JSON.stringify({ alerts }),
        { status: 200, headers: CORS_HEADERS }
      );
    }

    // ── POST /api/alerts/scan-now — Trigger scan ────────────
    if (req.method === "POST" && path.endsWith("/scan-now")) {
      const watchlist = await getValue(WATCHLIST_KEY);
      const stocks = Array.isArray(watchlist) ? watchlist : [];

      if (stocks.length === 0) {
        return new Response(
          JSON.stringify({
            message: "No stocks in watchlist to scan.",
            alerts: [],
          }),
          { status: 200, headers: CORS_HEADERS }
        );
      }

      console.log(`Running alert scan for ${stocks.length} stocks...`);

      const allAlerts = [];

      // Process in batches of 3 to avoid rate limiting
      const batchSize = 3;
      for (let i = 0; i < stocks.length; i += batchSize) {
        const batch = stocks.slice(i, i + batchSize);
        const results = await Promise.allSettled(
          batch.map((s) => checkStockAlerts(s.ticker, s.stock_name))
        );

        for (const result of results) {
          if (result.status === "fulfilled" && Array.isArray(result.value)) {
            allAlerts.push(...result.value);
          }
        }
      }

      // Save alerts to history
      if (allAlerts.length > 0) {
        await saveAlerts(allAlerts);
      }

      return new Response(
        JSON.stringify({
          message: `Scan complete. ${allAlerts.length} alerts triggered.`,
          alerts: allAlerts,
        }),
        { status: 200, headers: CORS_HEADERS }
      );
    }

    // Method not allowed
    return new Response(
      JSON.stringify({ detail: "Method not allowed" }),
      { status: 405, headers: CORS_HEADERS }
    );
  } catch (err) {
    console.error("Alerts function error:", err);
    return new Response(
      JSON.stringify({ detail: `Server error: ${err.message}` }),
      { status: 500, headers: CORS_HEADERS }
    );
  }
};

export const config = {
  path: ["/api/alerts", "/api/alerts/scan-now"],
};
