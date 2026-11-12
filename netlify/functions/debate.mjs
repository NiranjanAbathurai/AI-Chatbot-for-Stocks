/**
 * Netlify Function: POST /api/debate
 * Runs the Bull → Bear → Judge debate for a given stock.
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

/**
 * Format stock data into a readable prompt for AI agents.
 */
function formatStockDataPrompt(stockName, ticker, stockData, stockDataError) {
  const lines = [`# Stock Analysis Request: ${stockName} (${ticker})`, "", "## Current Stock Data:", ""];

  const fieldLabels = {
    current_price: "Current Price",
    market_cap: "Market Cap",
    pe_ratio: "P/E Ratio",
    pb_ratio: "P/B Ratio",
    eps: "EPS (Earnings Per Share)",
    dividend_yield: "Dividend Yield (%)",
    "52_week_high": "52-Week High",
    "52_week_low": "52-Week Low",
    debt_to_equity: "Debt-to-Equity Ratio",
    roe: "Return on Equity (ROE)",
    revenue_growth: "Revenue Growth (%)",
    profit_growth: "Profit/Earnings Growth (%)",
    promoter_holding: "Promoter/Insider Holding (%)",
    "1m_return": "1-Month Return (%)",
    "3m_return": "3-Month Return (%)",
    "6m_return": "6-Month Return (%)",
    "1y_return": "1-Year Return (%)",
    volume: "Current Volume",
    avg_volume: "Average Volume",
    sector: "Sector",
    industry: "Industry",
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
    if (stockDataError) {
      lines.push(`(Reason: ${stockDataError})`);
    }
    lines.push("");
    lines.push("Please provide your analysis based on your general knowledge of this stock,");
    lines.push("its fundamentals, recent news, sector trends, and historical performance.");
    lines.push("Clearly state that live data was unavailable and your analysis is based on general knowledge.");
  } else {
    lines.push("", "Analyze this stock based on the data above. Use specific numbers in your analysis.");
  }

  return lines.join("\n");
}

/**
 * Parse the judge's response to extract recommendation and confidence.
 */
function parseVerdict(judgeResponse) {
  let recommendation = "HOLD";
  let confidence = 5;

  // Extract verdict
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

  // Extract confidence
  const confPatterns = [
    /Confidence:\s*(\d+)\s*\/\s*10/i,
    /Confidence:\s*(\d+)/i,
    /(\d+)\s*\/\s*10/i,
  ];
  for (const pattern of confPatterns) {
    const match = judgeResponse.match(pattern);
    if (match) {
      const conf = parseInt(match[1], 10);
      if (conf >= 1 && conf <= 10) {
        confidence = conf;
        break;
      }
    }
  }

  return { recommendation, confidence, analysis: judgeResponse };
}

export default async (req, context) => {
  // Handle CORS preflight
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

    console.log(`Debate requested for: ${stockName}`);

    // Step 1: Resolve ticker
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

    // Step 2: Fetch stock data (with graceful degradation)
    let stockData;
    let stockDataError = null;
    try {
      stockData = await fetchStockData(ticker);
    } catch (err) {
      stockDataError = err.message;
      console.warn(`Stock data fetch failed for ${ticker}: ${err.message}`);
      // Always allow the debate to proceed with general knowledge
      // The AI agents can still provide analysis based on their training data
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

    // Step 3: Run the debate
    const dataPrompt = formatStockDataPrompt(fullName, ticker, stockData, stockDataError);

    // Run Bull and Bear in parallel
    const [bullResponse, bearResponse] = await Promise.allSettled([
      generateAI(BULLISH_SYSTEM_PROMPT, dataPrompt),
      generateAI(BEARISH_SYSTEM_PROMPT, dataPrompt),
    ]);

    const bullText =
      bullResponse.status === "fulfilled"
        ? bullResponse.value
        : "⚠️ The Bullish Analyst could not generate an analysis at this time.";

    const bearText =
      bearResponse.status === "fulfilled"
        ? bearResponse.value
        : "⚠️ The Bearish Analyst could not generate an analysis at this time.";

    // Run Judge with both arguments
    const judgePrompt = `# Stock: ${fullName} (${ticker})

## Stock Data Summary:
${dataPrompt}

---

## 🐂 Bullish Analyst's Argument:
${bullText}

---

## 🐻 Bearish Analyst's Argument:
${bearText}

---

Now evaluate both arguments and deliver your verdict. Remember to start with your verdict and confidence score.`;

    let judgeText;
    try {
      judgeText = await generateAI(JUDGE_SYSTEM_PROMPT, judgePrompt);
    } catch {
      judgeText =
        "⚠️ The Judge could not deliver a verdict at this time. Please review both arguments and form your own conclusion.";
    }

    const verdict = parseVerdict(judgeText);

    // Step 4: Build response
    const response = {
      ticker,
      stock_name: fullName,
      stock_data: stockData,
      bullish: {
        agent: "🐂 Bullish Analyst",
        argument: bullText,
      },
      bearish: {
        agent: "🐻 Bearish Analyst",
        argument: bearText,
      },
      verdict: {
        agent: "⚖️ Judge",
        recommendation: verdict.recommendation,
        confidence: verdict.confidence,
        analysis: verdict.analysis,
      },
      disclaimer:
        "⚠️ This is AI-generated analysis for educational purposes only. This is NOT financial advice. Always do your own research and consult a SEBI-registered financial advisor before making investment decisions.",
    };

    return new Response(JSON.stringify(response), {
      status: 200,
      headers: CORS_HEADERS,
    });
  } catch (err) {
    console.error("Debate function error:", err);
    return new Response(
      JSON.stringify({ detail: `Server error: ${err.message}` }),
      { status: 500, headers: CORS_HEADERS }
    );
  }
};

export const config = {
  path: "/api/debate",
};
