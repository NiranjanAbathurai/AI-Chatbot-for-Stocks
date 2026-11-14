/**
 * Netlify Function: POST /api/stock-data
 * Fetches stock data from Yahoo Finance for a given stock name.
 * This is Step 1 of the sequential debate flow.
 */

import { resolveTicker, getSimilarTickers } from "./lib/tickers.mjs";
import { fetchStockData } from "./lib/stock-service.mjs";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Content-Type": "application/json",
};

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

  try {
    const body = await req.json();
    const stockName = (body.stock_name || "").trim();

    if (!stockName) {
      return new Response(
        JSON.stringify({ detail: "stock_name is required" }),
        { status: 400, headers: CORS_HEADERS }
      );
    }

    // Resolve ticker
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

    // Fetch stock data (with graceful degradation)
    let stockData;
    let stockDataError = null;
    try {
      stockData = await fetchStockData(ticker);
    } catch (err) {
      stockDataError = err.message;
      console.warn(`Stock data fetch failed for ${ticker}: ${err.message}`);
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

    // Return stock data (technical_data is empty on Netlify — computed client-side or skipped)
    return new Response(
      JSON.stringify({
        ticker,
        stock_name: fullName,
        stock_data: stockData,
        technical_data: {},
      }),
      { status: 200, headers: CORS_HEADERS }
    );
  } catch (err) {
    console.error("Stock data function error:", err);
    return new Response(
      JSON.stringify({ detail: `Server error: ${err.message}` }),
      { status: 500, headers: CORS_HEADERS }
    );
  }
};

export const config = {
  path: "/api/stock-data",
};
