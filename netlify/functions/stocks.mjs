/**
 * Netlify Function: GET /api/stocks
 * Returns categorized stock list for the search dropdown.
 */

import { TICKER_MAP } from "./lib/tickers.mjs";
import { NIFTY_50 } from "./lib/nifty-stocks.mjs";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Content-Type": "application/json",
};

/**
 * Build a categorized stock list from the ticker map and NIFTY 50 list.
 */
function buildStockList() {
  const seen = new Set();
  const stocks = [];

  // Categorize NIFTY 50 stocks
  const niftyTickers = new Set(NIFTY_50.map((s) => s.ticker));

  // Sector mapping for common stocks
  const sectorMap = {
    "HDFCBANK.NS": "Banking", "ICICIBANK.NS": "Banking", "SBIN.NS": "Banking",
    "AXISBANK.NS": "Banking", "KOTAKBANK.NS": "Banking", "INDUSINDBK.NS": "Banking",
    "BANKBARODA.NS": "Banking", "PNB.NS": "Banking", "CANBK.NS": "Banking",
    "YESBANK.NS": "Banking", "BANDHANBNK.NS": "Banking", "FEDERALBNK.NS": "Banking",
    "IDFCFIRSTB.NS": "Banking", "AUBANK.NS": "Banking",
    "INFY.NS": "IT", "TCS.NS": "IT", "HCLTECH.NS": "IT", "WIPRO.NS": "IT",
    "TECHM.NS": "IT", "LTIM.NS": "IT", "PERSISTENT.NS": "IT", "COFORGE.NS": "IT",
    "MPHASIS.NS": "IT",
    "RELIANCE.NS": "Energy & Oil", "ONGC.NS": "Energy & Oil", "BPCL.NS": "Energy & Oil",
    "IOC.NS": "Energy & Oil", "GAIL.NS": "Energy & Oil", "NTPC.NS": "Energy & Oil",
    "POWERGRID.NS": "Energy & Oil", "TATAPOWER.NS": "Energy & Oil",
    "ADANIGREEN.NS": "Energy & Oil", "ADANIPOWER.NS": "Energy & Oil",
    "SUNPHARMA.NS": "Pharma & Health", "DRREDDY.NS": "Pharma & Health",
    "CIPLA.NS": "Pharma & Health", "DIVISLAB.NS": "Pharma & Health",
    "BIOCON.NS": "Pharma & Health", "LUPIN.NS": "Pharma & Health",
    "APOLLOHOSP.NS": "Pharma & Health",
    "TATAMOTORS.NS": "Auto", "MARUTI.NS": "Auto", "M&M.NS": "Auto",
    "BAJAJ-AUTO.NS": "Auto", "HEROMOTOCO.NS": "Auto", "EICHERMOT.NS": "Auto",
    "TATASTEEL.NS": "Metals & Mining", "JSWSTEEL.NS": "Metals & Mining",
    "HINDALCO.NS": "Metals & Mining", "COALINDIA.NS": "Metals & Mining",
    "VEDL.NS": "Metals & Mining", "SAIL.NS": "Metals & Mining",
    "HINDUNILVR.NS": "FMCG", "ITC.NS": "FMCG", "NESTLEIND.NS": "FMCG",
    "BRITANNIA.NS": "FMCG", "TATACONSUM.NS": "FMCG", "DABUR.NS": "FMCG",
    "MARICO.NS": "FMCG", "COLPAL.NS": "FMCG",
    "BAJFINANCE.NS": "Finance", "BAJAJFINSV.NS": "Finance", "HDFCLIFE.NS": "Finance",
    "SBILIFE.NS": "Finance", "LICI.NS": "Finance", "JIOFIN.NS": "Finance",
    "PFC.NS": "Finance", "RECLTD.NS": "Finance", "IRFC.NS": "Finance",
    "ANGELONE.NS": "Finance", "CDSL.NS": "Finance", "BSE.NS": "Finance",
    "LT.NS": "Infrastructure", "GRASIM.NS": "Infrastructure",
    "ULTRACEMCO.NS": "Infrastructure", "SHREECEM.NS": "Infrastructure",
    "AMBUJACEM.NS": "Infrastructure", "ACC.NS": "Infrastructure",
    "ADANIENT.NS": "Conglomerate", "ADANIPORTS.NS": "Conglomerate",
    "TITAN.NS": "Consumer", "ASIANPAINT.NS": "Consumer", "PIDILITIND.NS": "Consumer",
    "HAVELLS.NS": "Consumer", "VOLTAS.NS": "Consumer", "DIXON.NS": "Consumer",
    "DMART.NS": "Consumer", "TRENT.NS": "Consumer", "JUBLFOOD.NS": "Consumer",
    "VBL.NS": "Consumer",
    "ZOMATO.NS": "New Age", "PAYTM.NS": "New Age", "NYKAA.NS": "New Age",
    "TATAELXSI.NS": "IT", "IRCTC.NS": "Travel", "HAL.NS": "Defence",
    "BHEL.NS": "Infrastructure", "NHPC.NS": "Energy & Oil", "RVNL.NS": "Infrastructure",
    "INDIGO.NS": "Travel", "SRF.NS": "Chemicals", "PIIND.NS": "Chemicals",
    "UPL.NS": "Chemicals", "IDEA.NS": "Telecom", "BHARTIARTL.NS": "Telecom",
  };

  // Build from ticker map (deduplicated by ticker)
  for (const [name, ticker] of Object.entries(TICKER_MAP)) {
    if (seen.has(ticker)) continue;
    seen.add(ticker);

    const displayName = name.replace(/\b\w/g, (c) => c.toUpperCase());
    const category = sectorMap[ticker] || (niftyTickers.has(ticker) ? "NIFTY 50" : "Other");

    stocks.push({
      name: displayName,
      ticker,
      category,
    });
  }

  // Sort by name
  stocks.sort((a, b) => a.name.localeCompare(b.name));

  // Extract unique categories
  const categories = [...new Set(stocks.map((s) => s.category))].sort();

  return { stocks, categories };
}

export default async (req, context) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: CORS_HEADERS });
  }

  const { stocks, categories } = buildStockList();

  return new Response(
    JSON.stringify({
      stocks,
      categories,
      count: stocks.length,
    }),
    { status: 200, headers: CORS_HEADERS }
  );
};

export const config = {
  path: "/api/stocks",
};
