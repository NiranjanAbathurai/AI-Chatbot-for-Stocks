/**
 * Stock data service using yahoo-finance2.
 */

import yahooFinance from "yahoo-finance2";

/**
 * Format market cap into human-readable Indian format.
 */
function formatMarketCap(value) {
  if (!value) return null;
  if (value >= 1e12) return `₹${(value / 1e12).toFixed(2)}L Cr`;
  if (value >= 1e10) return `₹${(value / 1e10).toFixed(2)}K Cr`;
  if (value >= 1e7) return `₹${(value / 1e7).toFixed(2)} Cr`;
  return `₹${value.toLocaleString("en-IN")}`;
}

/**
 * Calculate percentage return from historical data.
 */
function calculateReturn(history, days) {
  if (!history || history.length < 2) return null;
  try {
    const current = history[history.length - 1]?.close;
    const pastIdx = Math.max(0, history.length - days);
    const past = history[pastIdx]?.close;
    if (current && past && past > 0) {
      return Math.round(((current - past) / past) * 100 * 100) / 100;
    }
  } catch {
    // ignore
  }
  return null;
}

/**
 * Fetch comprehensive stock data from Yahoo Finance.
 */
export async function fetchStockData(ticker) {
  try {
    // Fetch quote summary
    const quote = await yahooFinance.quoteSummary(ticker, {
      modules: [
        "price",
        "summaryDetail",
        "defaultKeyStatistics",
        "financialData",
        "assetProfile",
      ],
    });

    const price = quote.price || {};
    const summary = quote.summaryDetail || {};
    const keyStats = quote.defaultKeyStatistics || {};
    const financial = quote.financialData || {};
    const profile = quote.assetProfile || {};

    // Fetch historical data for return calculations
    let history = [];
    try {
      const endDate = new Date();
      const startDate = new Date();
      startDate.setFullYear(startDate.getFullYear() - 1);

      const histResult = await yahooFinance.chart(ticker, {
        period1: startDate.toISOString().split("T")[0],
        period2: endDate.toISOString().split("T")[0],
        interval: "1d",
      });
      history = histResult?.quotes || [];
    } catch {
      // Historical data may not be available
    }

    const currentPrice =
      financial.currentPrice || price.regularMarketPrice || null;

    const data = {
      current_price: currentPrice,
      market_cap: formatMarketCap(price.marketCap),
      pe_ratio: summary.trailingPE || keyStats.forwardPE || null,
      pb_ratio: keyStats.priceToBook || null,
      eps: keyStats.trailingEps || null,
      dividend_yield: summary.dividendYield
        ? Math.round(summary.dividendYield * 100 * 100) / 100
        : null,
      "52_week_high": summary.fiftyTwoWeekHigh || null,
      "52_week_low": summary.fiftyTwoWeekLow || null,
      debt_to_equity: financial.debtToEquity || null,
      roe: financial.returnOnEquity
        ? Math.round(financial.returnOnEquity * 100 * 100) / 100
        : null,
      revenue_growth: financial.revenueGrowth
        ? Math.round(financial.revenueGrowth * 100 * 100) / 100
        : null,
      profit_growth: financial.earningsGrowth
        ? Math.round(financial.earningsGrowth * 100 * 100) / 100
        : null,
      promoter_holding: keyStats.heldPercentInsiders
        ? Math.round(keyStats.heldPercentInsiders * 100 * 100) / 100
        : null,
      "1m_return": calculateReturn(history, 21),
      "3m_return": calculateReturn(history, 63),
      "6m_return": calculateReturn(history, 126),
      "1y_return": calculateReturn(history, 252),
      volume: price.regularMarketVolume || null,
      avg_volume: summary.averageVolume || null,
      sector: profile.sector || null,
      industry: profile.industry || null,
      stock_name:
        price.longName || price.shortName || ticker.replace(".NS", ""),
    };

    return data;
  } catch (err) {
    console.error(`Error fetching stock data for ${ticker}:`, err.message);
    throw new Error(`Could not fetch data for ${ticker}: ${err.message}`);
  }
}
