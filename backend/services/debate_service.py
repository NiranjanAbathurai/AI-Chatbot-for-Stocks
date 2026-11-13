"""Debate orchestration service: Bull → Bear → Judge flow with technical analysis."""

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


def _format_stock_data_prompt(
    stock_name: str, ticker: str, stock_data: dict, stock_data_error: Optional[str] = None
) -> str:
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

    has_data = False
    for key, label in field_labels.items():
        value = stock_data.get(key)
        if value is not None:
            has_data = True
            if isinstance(value, float):
                lines.append(f"- **{label}**: {value:.2f}")
            else:
                lines.append(f"- **{label}**: {value}")

    if not has_data:
        lines.append("⚠️ **Live market data is temporarily unavailable.**")
        if stock_data_error:
            lines.append(f"(Reason: {stock_data_error})")
        lines.append("")
        lines.append("Please provide your analysis based on your general knowledge of this stock,")
        lines.append("its fundamentals, recent news, sector trends, and historical performance.")
        lines.append("Clearly state that live data was unavailable and your analysis is based on general knowledge.")
    else:
        lines.append("")
        lines.append("Analyze this stock based on the data above. Use specific numbers in your analysis.")

    return "\n".join(lines)


def _format_technical_data_prompt(technical_data: dict) -> str:
    """Format technical analysis data into a readable prompt section."""
    if not technical_data:
        return ""

    lines = [
        "",
        "---",
        "",
        "## 📐 Technical Analysis Data (Computed from 1-Year Daily Charts):",
        "",
    ]

    # Support & Resistance
    sr = technical_data.get("support_resistance", {})

    if sr.get("support_levels"):
        lines.append("### 🟢 Support Levels (nearest first):")
        for i, s in enumerate(sr["support_levels"], 1):
            lines.append(f"  S{i}: ₹{s['price']} (zone: ₹{s['zone_low']}–₹{s['zone_high']}, strength: {s['strength']} touches)")
        lines.append("")

    if sr.get("resistance_levels"):
        lines.append("### 🔴 Resistance Levels (nearest first):")
        for i, r in enumerate(sr["resistance_levels"], 1):
            lines.append(f"  R{i}: ₹{r['price']} (zone: ₹{r['zone_low']}–₹{r['zone_high']}, strength: {r['strength']} touches)")
        lines.append("")

    if sr.get("fibonacci"):
        fib = sr["fibonacci"]
        lines.append("### 📏 Fibonacci Retracement (6-month swing):")
        lines.append(f"  Swing High: ₹{fib.get('swing_high', 'N/A')} | Swing Low: ₹{fib.get('swing_low', 'N/A')}")
        lines.append(f"  0% (High): ₹{fib.get('level_0', 'N/A')}")
        lines.append(f"  23.6%: ₹{fib.get('level_236', 'N/A')}")
        lines.append(f"  38.2%: ₹{fib.get('level_382', 'N/A')}")
        lines.append(f"  50.0%: ₹{fib.get('level_500', 'N/A')}")
        lines.append(f"  61.8%: ₹{fib.get('level_618', 'N/A')}")
        lines.append(f"  78.6%: ₹{fib.get('level_786', 'N/A')}")
        lines.append(f"  100% (Low): ₹{fib.get('level_100', 'N/A')}")
        lines.append("")

    if sr.get("moving_averages"):
        ma = sr["moving_averages"]
        lines.append("### 📊 Key Moving Averages:")
        for key in ["ema_20", "sma_20", "ema_50", "sma_50", "ema_100", "sma_100", "ema_200", "sma_200"]:
            if key in ma:
                label = key.upper().replace("_", " ")
                lines.append(f"  {label}: ₹{ma[key]}")
        lines.append("")

    if sr.get("pivot_classic"):
        pv = sr["pivot_classic"]
        lines.append("### 🎯 Classic Pivot Points:")
        lines.append(f"  R3: ₹{pv.get('r3','N/A')} | R2: ₹{pv.get('r2','N/A')} | R1: ₹{pv.get('r1','N/A')}")
        lines.append(f"  Pivot: ₹{pv.get('pivot','N/A')}")
        lines.append(f"  S1: ₹{pv.get('s1','N/A')} | S2: ₹{pv.get('s2','N/A')} | S3: ₹{pv.get('s3','N/A')}")
        lines.append("")

    # Chart Patterns
    patterns = technical_data.get("chart_patterns", [])
    if patterns:
        lines.append("### 📈 Detected Chart Patterns:")
        for p in patterns:
            emoji = "🟢" if p["type"] == "bullish" else "🔴" if p["type"] == "bearish" else "🟡"
            lines.append(f"  {emoji} **{p['pattern']}** ({p['type'].upper()}, reliability: {p.get('reliability', 'N/A')})")
            lines.append(f"     {p.get('description', '')}")
            if p.get("target"):
                lines.append(f"     Pattern target: ₹{p['target']}")
            if p.get("neckline"):
                lines.append(f"     Neckline: ₹{p['neckline']}")
            if p.get("implication"):
                lines.append(f"     Implication: {p['implication']}")
            lines.append("")

    # Swing Indicators
    swing = technical_data.get("swing_indicators", {})
    if swing:
        lines.append("### 🔧 Swing Trading Indicators:")
        if "rsi_14" in swing:
            lines.append(f"  RSI (14): {swing['rsi_14']} — {swing.get('rsi_signal', '')}")
        if "macd" in swing:
            lines.append(f"  MACD: {swing['macd']} | Signal: {swing.get('macd_signal', '')} | Histogram: {swing.get('macd_histogram', '')}")
            lines.append(f"  MACD Trend: {swing.get('macd_trend', '')} | Crossover: {swing.get('macd_crossover', 'None')}")
        if "bb_upper" in swing:
            lines.append(f"  Bollinger Bands: Upper ₹{swing['bb_upper']} | Middle ₹{swing.get('bb_middle','')} | Lower ₹{swing.get('bb_lower','')}")
            lines.append(f"  BB Width: {swing.get('bb_width_pct', '')}% | Signal: {swing.get('bb_signal', '')}")
        if "atr_14" in swing:
            lines.append(f"  ATR (14): ₹{swing['atr_14']} ({swing.get('atr_pct', '')}% of price)")
            lines.append(f"  ATR-based SL: ₹{swing.get('suggested_sl', '')} | Target: ₹{swing.get('suggested_target', '')}")
        if "stoch_rsi" in swing:
            lines.append(f"  Stochastic RSI: {swing['stoch_rsi']} — {swing.get('stoch_rsi_signal', '')}")
        if "relative_volume" in swing:
            lines.append(f"  Relative Volume: {swing['relative_volume']}x — {swing.get('volume_signal', '')}")
        if "obv_trend" in swing:
            lines.append(f"  OBV Trend: {swing['obv_trend']}")
        if "swing_score" in swing:
            lines.append(f"  **Swing Score: {swing['swing_score']}/100 — Bias: {swing.get('swing_bias', '')}**")
        lines.append("")

    return "\n".join(lines)


def _parse_verdict(judge_response: str) -> dict:
    """Parse the judge's response to extract recommendation and confidence."""
    recommendation = "HOLD"
    confidence = 5

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


async def run_debate(
    stock_name: str, ticker: str, stock_data: dict,
    technical_data: dict = None, stock_data_error: Optional[str] = None
) -> dict:
    """
    Run the full debate: Bull and Bear in parallel, then Judge.
    Now includes technical analysis data (S/R, patterns, swing indicators).
    """
    # Format the stock data prompt
    data_prompt = _format_stock_data_prompt(stock_name, ticker, stock_data, stock_data_error)

    # Format technical analysis data
    tech_prompt = _format_technical_data_prompt(technical_data or {})

    # Combined prompt for agents
    full_prompt = data_prompt + tech_prompt

    # ── Step 1: Run Bull and Bear in parallel ───────────────────
    logger.info(f"Starting debate for {stock_name} ({ticker})")

    bull_task = ai_service.generate(
        system_prompt=BULLISH_SYSTEM_PROMPT,
        user_prompt=full_prompt,
    )
    bear_task = ai_service.generate(
        system_prompt=BEARISH_SYSTEM_PROMPT,
        user_prompt=full_prompt,
    )

    bull_response, bear_response = await asyncio.gather(
        bull_task, bear_task, return_exceptions=True
    )

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

{tech_prompt}

---

## 🐂 Bullish Analyst's Argument:
{bull_response}

---

## 🐻 Bearish Analyst's Argument:
{bear_response}

---

Now evaluate both arguments and deliver your verdict. Remember to start with your verdict and confidence score.
Include specific support/resistance levels, chart pattern analysis, and actionable swing trading levels in your final recommendation."""

    try:
        judge_response = await ai_service.generate(
            system_prompt=JUDGE_SYSTEM_PROMPT,
            user_prompt=judge_prompt,
        )
    except Exception as e:
        logger.error(f"Judge agent failed: {e}")
        judge_response = "⚠️ The Judge could not deliver a verdict at this time. Please review both arguments and form your own conclusion."

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
