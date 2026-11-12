/**
 * Netlify Function: /api/watchlist
 * Watchlist CRUD operations using Netlify Blobs for persistence.
 *
 * Endpoints:
 *   GET    /api/watchlist          — List all watchlist stocks
 *   POST   /api/watchlist          — Add a stock to watchlist
 *   DELETE /api/watchlist/:ticker   — Remove a stock from watchlist
 */

import { getValue, setValue } from "./lib/store.mjs";
import { resolveTicker } from "./lib/tickers.mjs";

const WATCHLIST_KEY = "watchlist";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Content-Type": "application/json",
};

/**
 * Get the watchlist from persistent storage.
 */
async function getWatchlist() {
  const data = await getValue(WATCHLIST_KEY);
  return Array.isArray(data) ? data : [];
}

/**
 * Save the watchlist to persistent storage.
 */
async function saveWatchlist(watchlist) {
  await setValue(WATCHLIST_KEY, watchlist);
}

export default async (req, context) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: CORS_HEADERS });
  }

  const url = new URL(req.url);
  const path = url.pathname;

  try {
    // ── GET /api/watchlist — List watchlist ──────────────────
    if (req.method === "GET") {
      const stocks = await getWatchlist();
      return new Response(
        JSON.stringify({ stocks }),
        { status: 200, headers: CORS_HEADERS }
      );
    }

    // ── POST /api/watchlist — Add stock ─────────────────────
    if (req.method === "POST") {
      const body = await req.json();
      const stockName = (body.stock_name || "").trim();
      let ticker = (body.ticker || "").trim();

      if (!stockName) {
        return new Response(
          JSON.stringify({ detail: "stock_name is required" }),
          { status: 400, headers: CORS_HEADERS }
        );
      }

      if (!ticker) {
        ticker = resolveTicker(stockName);
        if (!ticker) {
          return new Response(
            JSON.stringify({ detail: `Could not resolve ticker for '${stockName}'` }),
            { status: 404, headers: CORS_HEADERS }
          );
        }
      }

      const watchlist = await getWatchlist();

      // Check if already exists
      const existing = watchlist.find((item) => item.ticker === ticker);
      if (existing) {
        return new Response(
          JSON.stringify({ message: `${stockName} is already in watchlist`, item: existing }),
          { status: 200, headers: CORS_HEADERS }
        );
      }

      const newItem = {
        ticker,
        stock_name: stockName,
        added_at: new Date().toISOString(),
      };

      watchlist.push(newItem);
      await saveWatchlist(watchlist);

      return new Response(
        JSON.stringify({ message: `Added ${stockName} to watchlist`, item: newItem }),
        { status: 201, headers: CORS_HEADERS }
      );
    }

    // ── DELETE /api/watchlist/:ticker — Remove stock ────────
    if (req.method === "DELETE") {
      // Extract ticker from path: /api/watchlist/TICKER.NS
      const tickerMatch = path.match(/\/api\/watchlist\/(.+)/);
      if (!tickerMatch) {
        return new Response(
          JSON.stringify({ detail: "Ticker is required in URL path" }),
          { status: 400, headers: CORS_HEADERS }
        );
      }

      const ticker = decodeURIComponent(tickerMatch[1]);
      const watchlist = await getWatchlist();
      const filtered = watchlist.filter((item) => item.ticker !== ticker);

      if (filtered.length === watchlist.length) {
        return new Response(
          JSON.stringify({ detail: `Ticker '${ticker}' not found in watchlist` }),
          { status: 404, headers: CORS_HEADERS }
        );
      }

      await saveWatchlist(filtered);

      return new Response(
        JSON.stringify({ message: `Removed ${ticker} from watchlist` }),
        { status: 200, headers: CORS_HEADERS }
      );
    }

    // Method not allowed
    return new Response(
      JSON.stringify({ detail: "Method not allowed" }),
      { status: 405, headers: CORS_HEADERS }
    );
  } catch (err) {
    console.error("Watchlist function error:", err);
    return new Response(
      JSON.stringify({ detail: `Server error: ${err.message}` }),
      { status: 500, headers: CORS_HEADERS }
    );
  }
};

export const config = {
  path: ["/api/watchlist", "/api/watchlist/*"],
};
