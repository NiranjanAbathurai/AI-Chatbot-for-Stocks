"""Debate orchestration service: Bull → Bear → Judge flow."""

import asyncio
import json
import logging
import re
from typing import Optional

from services.ai_service import ai_service
from prompts.bullish import BULLISH_SYSTEM_PROMPT
from prompts.bearish import BEARISH_SYSTEM_PROMPT
from prompts.judge import JUDGE_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def _format_stock_data_prompt(stock_name: str, ticker: str, stock_data: dict) -> str:
    """Format stock data into a readable prompt for the AI agents."""
    lines = [
        f"# Stock Analysis Request: {stock_name} ({ticker})",
        "",
        "## Current Stock Data:",
        "",
    ]

    field_labels = {
        "current_price": "Current Price",
        "market_cap": "Market Cap",
        "pe_ratio": "P/E Ratio",
        "pb_ratio": "P/B Ratio",
        "eps": "EPS (Earnings Per Share)",
        "dividend_yield": "Dividend Yield (%)",
        "52_week_high": "52-Week High",
        "52_week_low": "52-Week Low",
        "debt_to_equity": "Debt-to-Equity Ratio",
        "roe": "Return on Equity (ROE)",
        "revenue_growth": "Revenue Growth (%)",
        "profit_growth": "Profit/Earnings Growth (%)",
        "promoter_holding": "Promoter/Insider Holding (%)",
        "1m_return": "1-Month Return (%)",
        "3m_return": "3-Month Return (%)",
        "6m_return": "6-Month Return (%)",
        "1y_return": "1-Year Return (%)",
        "volume": "Current Volume",
        "avg_volume": "Average Volume",
        "sector": "Sector",
        "industry": "Industry",
    }

    for key, label in field_labels.items():
        value = stock_data.get(key)
        if value is not None:
            if isinstance(value, float):
                lines.append(f"- **{label}**: {value:.2f}")
            else:
                lines.append(f"- **{label}**: {value}")

    lines.append("")
    lines.append("Analyze this stock based on the data above. Use specific numbers in your analysis.")

    return "\n".join(lines)


def _parse_verdict(judge_response: str) -> dict:
    """
    Parse the judge's response to extract recommendation and confidence.

    Returns:
        Dict with 'recommendation', 'confidence', and 'analysis' keys.
    """
    recommendation = "HOLD"  # default
    confidence = 5  # default

    # Try to extract verdict
    verdict_patterns = [
        r"Verdict:\s*(BUY|HOLD|AVOID|SELL)",
        r"\*\*(BUY|HOLD|AVOID|SELL)\*\*",
        r"recommendation[:\s]*(BUY|HOLD|AVOID|SELL)",
    ]
    for pattern in verdict_patterns:
        match = re.search(pattern, judge_response, re.IGNORECASE)
        if match:
            recommendation = match.group(1).upper()
            if recommendation == "SELL":
                recommendation = "AVOID"
            break

    # Try to extract confidence
    confidence_patterns = [
        r"Confidence:\s*(\d+)\s*/\s*10",
        r"Confidence:\s*(\d+)",
        r"(\d+)\s*/\s*10",
    ]
    for pattern in confidence_patterns:
        match = re.search(pattern, judge_response, re.IGNORECASE)
        if match:
            try:
                conf = int(match.group(1))
                if 1 <= conf <= 10:
                    confidence = conf
                    break
            except ValueError:
                pass

    return {
        "recommendation": recommendation,
        "confidence": confidence,
        "analysis": judge_response,
    }


async def run_debate(stock_name: str, ticker: str, stock_data: dict) -> dict:
    """
    Run the full debate: Bull and Bear in parallel, then Judge.

    Args:
        stock_name: Human-readable stock name.
        ticker: NSE ticker symbol.
        stock_data: Dict of stock data from yfinance.

    Returns:
        Dict with bullish, bearish, and verdict results.
    """
    # Format the stock data prompt
    data_prompt = _format_stock_data_prompt(stock_name, ticker, stock_data)

    # ── Step 1: Run Bull and Bear in parallel ───────────────────
    logger.info(f"Starting debate for {stock_name} ({ticker})")

    bull_task = ai_service.generate(
        system_prompt=BULLISH_SYSTEM_PROMPT,
        user_prompt=data_prompt,
    )
    bear_task = ai_service.generate(
        system_prompt=BEARISH_SYSTEM_PROMPT,
        user_prompt=data_prompt,
    )

    bull_response, bear_response = await asyncio.gather(
        bull_task, bear_task, return_exceptions=True
    )

    # Handle errors
    if isinstance(bull_response, Exception):
        logger.error(f"Bull agent failed: {bull_response}")
        bull_response = "⚠️ The Bullish Analyst could not generate an analysis at this time."

    if isinstance(bear_response, Exception):
        logger.error(f"Bear agent failed: {bear_response}")
        bear_response = "⚠️ The Bearish Analyst could not generate an analysis at this time."

    # ── Step 2: Run Judge with both arguments ───────────────────
    judge_prompt = f"""# Stock: {stock_name} ({ticker})

## Stock Data Summary:
{data_prompt}

---

## 🐂 Bullish Analyst's Argument:
{bull_response}

---

## 🐻 Bearish Analyst's Argument:
{bear_response}

---

Now evaluate both arguments and deliver your verdict. Remember to start with your verdict and confidence score."""

    try:
        judge_response = await ai_service.generate(
            system_prompt=JUDGE_SYSTEM_PROMPT,
            user_prompt=judge_prompt,
        )
    except Exception as e:
        logger.error(f"Judge agent failed: {e}")
        judge_response = "⚠️ The Judge could not deliver a verdict at this time. Please review both arguments and form your own conclusion."

    # Parse the judge's verdict
    verdict = _parse_verdict(judge_response)

    return {
        "bullish": {
            "agent": "🐂 Bullish Analyst",
            "argument": bull_response,
        },
        "bearish": {
            "agent": "🐻 Bearish Analyst",
            "argument": bear_response,
        },
        "verdict": {
            "agent": "⚖️ Judge",
            "recommendation": verdict["recommendation"],
            "confidence": verdict["confidence"],
            "analysis": verdict["analysis"],
        },
    }
