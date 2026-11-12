"""Stock screening service with scoring system for BUY and SHORT signals."""

import asyncio
import logging
from datetime import datetime
from typing import Optional

import yfinance as yf
import numpy as np

from services.nifty_stocks import get_nifty50_stocks

logger = logging.getLogger(__name__)

# Cache for scan results
_last_scan: Optional[dict] = None
_last_scan_time: Optional[str] = None


def _calculate_rsi(prices, period: int = 14) -> Optional[float]:
    """Calculate RSI (Relative Strength Index) from price series."""
    try:
        if prices is None or len(prices) < period + 1:
            return None
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return round(float(rsi), 2)
    except Exception:
        return None


def _score_buy_signal(info: dict, rsi: Optional[float], hist) -> tuple[float, list[str]]:
    """
    Score a stock for BUY signals (0-100).

    Returns (score, list_of_reasons).
    """
    score = 0.0
    reasons = []

    # P/E ratio below 25 (value play) — weight 15%
    pe = info.get("trailingPE") or info.get("forwardPE")
    if pe and pe < 25:
        points = min(15, (25 - pe) / 25 * 15)
        score += points
        reasons.append(f"Low P/E: {pe:.1f}")
    elif pe and pe < 15:
        score += 15
        reasons.append(f"Very low P/E: {pe:.1f}")

    # RSI below 30 (oversold) — weight 15%
    if rsi is not None and rsi < 30:
        score += 15
        reasons.append(f"Oversold RSI: {rsi:.0f}")
    elif rsi is not None and rsi < 40:
        score += 8
        reasons.append(f"Near oversold RSI: {rsi:.0f}")

    # Price near 52-week low (within 10%) — weight 10%
    low_52 = info.get("fiftyTwoWeekLow")
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if low_52 and price and low_52 > 0:
        pct_above_low = ((price - low_52) / low_52) * 100
        if pct_above_low <= 10:
            score += 10
            reasons.append(f"Near 52W low ({pct_above_low:.1f}% above)")
        elif pct_above_low <= 20:
            score += 5

    # Revenue growth > 15% — weight 15%
    rev_growth = info.get("revenueGrowth")
    if rev_growth and rev_growth > 0.15:
        score += min(15, rev_growth * 100 / 30 * 15)
        reasons.append(f"Revenue growth: {rev_growth*100:.1f}%")

    # Profit growth > 20% — weight 15%
    earn_growth = info.get("earningsGrowth")
    if earn_growth and earn_growth > 0.20:
        score += min(15, earn_growth * 100 / 40 * 15)
        reasons.append(f"Earnings growth: {earn_growth*100:.1f}%")

    # Promoter holding > 50% — weight 10%
    insider = info.get("heldPercentInsiders")
    if insider and insider > 0.50:
        score += 10
        reasons.append(f"High promoter holding: {insider*100:.1f}%")

    # Debt-to-equity < 1 — weight 10%
    de = info.get("debtToEquity")
    if de is not None and de < 100:  # yfinance returns as percentage
        score += 10
        reasons.append(f"Low debt: D/E {de:.1f}")

    # Volume spike (current > 1.5x average) — weight 10%
    vol = info.get("volume") or info.get("regularMarketVolume")
    avg_vol = info.get("averageVolume")
    if vol and avg_vol and avg_vol > 0:
        vol_ratio = vol / avg_vol
        if vol_ratio > 2:
            score += 10
            reasons.append(f"Volume spike: {vol_ratio:.1f}x avg")
        elif vol_ratio > 1.5:
            score += 5

    return min(score, 100), reasons


def _score_short_signal(info: dict, rsi: Optional[float], hist) -> tuple[float, list[str]]:
    """
    Score a stock for SHORT/AVOID signals (0-100).

    Returns (score, list_of_reasons).
    """
    score = 0.0
    reasons = []

    # P/E ratio very high (overvalued) — weight 15%
    pe = info.get("trailingPE") or info.get("forwardPE")
    if pe and pe > 50:
        score += 15
        reasons.append(f"High P/E: {pe:.1f}")
    elif pe and pe > 35:
        score += 8
        reasons.append(f"Elevated P/E: {pe:.1f}")

    # RSI above 70 (overbought) — weight 15%
    if rsi is not None and rsi > 70:
        score += 15
        reasons.append(f"Overbought RSI: {rsi:.0f}")
    elif rsi is not None and rsi > 65:
        score += 8
        reasons.append(f"Near overbought RSI: {rsi:.0f}")

    # Price near 52-week high (within 5%) — weight 10%
    high_52 = info.get("fiftyTwoWeekHigh")
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if high_52 and price and high_52 > 0:
        pct_below_high = ((high_52 - price) / high_52) * 100
        if pct_below_high <= 5:
            score += 10
            reasons.append(f"Near 52W high ({pct_below_high:.1f}% below)")
        elif pct_below_high <= 10:
            score += 5

    # Revenue decline — weight 15%
    rev_growth = info.get("revenueGrowth")
    if rev_growth is not None and rev_growth < 0:
        score += min(15, abs(rev_growth) * 100 / 20 * 15)
        reasons.append(f"Revenue decline: {rev_growth*100:.1f}%")

    # Profit decline — weight 15%
    earn_growth = info.get("earningsGrowth")
    if earn_growth is not None and earn_growth < 0:
        score += min(15, abs(earn_growth) * 100 / 20 * 15)
        reasons.append(f"Earnings decline: {earn_growth*100:.1f}%")

    # Promoter holding decreasing / low — weight 10%
    insider = info.get("heldPercentInsiders")
    if insider is not None and insider < 0.20:
        score += 10
        reasons.append(f"Low promoter holding: {insider*100:.1f}%")

    # Debt-to-equity > 2 — weight 10%
    de = info.get("debtToEquity")
    if de is not None and de > 200:
        score += 10
        reasons.append(f"High debt: D/E {de:.1f}")
    elif de is not None and de > 150:
        score += 5

    # Volume drying up — weight 10%
    vol = info.get("volume") or info.get("regularMarketVolume")
    avg_vol = info.get("averageVolume")
    if vol and avg_vol and avg_vol > 0:
        vol_ratio = vol / avg_vol
        if vol_ratio < 0.5:
            score += 10
            reasons.append(f"Low volume: {vol_ratio:.1f}x avg")
        elif vol_ratio < 0.7:
            score += 5

    return min(score, 100), reasons


async def scan_stocks() -> dict:
    """
    Scan NIFTY 50 stocks and return top BUY and SHORT candidates.

    Returns dict with buy_candidates and short_candidates lists.
    """
    global _last_scan, _last_scan_time

    stocks = get_nifty50_stocks()
    buy_results = []
    short_results = []

    logger.info(f"Starting stock scan for {len(stocks)} stocks...")

    loop = asyncio.get_event_loop()

    async def _analyze_stock(stock: dict):
        """Analyze a single stock."""
        try:
            def _fetch():
                t = yf.Ticker(stock["ticker"])
                info = t.info or {}
                try:
                    hist = t.history(period="1mo")
                except Exception:
                    hist = None
                return info, hist

            info, hist = await loop.run_in_executor(None, _fetch)

            # Calculate RSI
            rsi = None
            if hist is not None and not hist.empty:
                rsi = _calculate_rsi(hist["Close"].values)

            # Score for BUY
            buy_score, buy_reasons = _score_buy_signal(info, rsi, hist)
            if buy_score > 20:  # Minimum threshold
                buy_results.append({
                    "name": stock["name"],
                    "ticker": stock["ticker"],
                    "score": round(buy_score, 1),
                    "reasons": buy_reasons[:3],  # Top 3 reasons
                })

            # Score for SHORT
            short_score, short_reasons = _score_short_signal(info, rsi, hist)
            if short_score > 20:
                short_results.append({
                    "name": stock["name"],
                    "ticker": stock["ticker"],
                    "score": round(short_score, 1),
                    "reasons": short_reasons[:3],
                })

        except Exception as e:
            logger.warning(f"Error analyzing {stock['name']}: {e}")

    # Run all analyses concurrently (with semaphore to limit concurrency)
    semaphore = asyncio.Semaphore(5)  # Max 5 concurrent yfinance calls

    async def _limited_analyze(stock):
        async with semaphore:
            await _analyze_stock(stock)

    await asyncio.gather(*[_limited_analyze(s) for s in stocks])

    # Sort by score descending, take top 5
    buy_results.sort(key=lambda x: x["score"], reverse=True)
    short_results.sort(key=lambda x: x["score"], reverse=True)

    result = {
        "last_scan": datetime.utcnow().isoformat(),
        "buy_candidates": buy_results[:5],
        "short_candidates": short_results[:5],
    }

    _last_scan = result
    _last_scan_time = result["last_scan"]

    logger.info(
        f"Scan complete: {len(buy_results)} buy candidates, "
        f"{len(short_results)} short candidates"
    )

    return result


def get_cached_scan() -> Optional[dict]:
    """Return the last cached scan result, if available."""
    return _last_scan
