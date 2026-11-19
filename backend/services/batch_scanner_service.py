"""Batch Swing Trading Scanner — Daily scan of all stocks for swing trade opportunities.

Runs through all NIFTY stocks (50+), fetches 6-month OHLCV data via Yahoo Chart API,
runs full technical analysis (S/R, patterns, swing indicators), and produces a
ranked list of swing trading opportunities with entry/SL/target levels.

Designed to run daily after market close (4:00 PM IST) via scheduler,
or on-demand via API.
"""

import asyncio
import logging
import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from services.nifty_stocks import get_nifty50_stocks
from services.technical_analysis import (
    detect_chart_patterns,
    calculate_swing_indicators,
    calculate_support_resistance,
)

logger = logging.getLogger(__name__)

# ── Cache & Persistence ─────────────────────────────────────────
_last_batch_scan: Optional[dict] = None
_last_batch_scan_time: Optional[str] = None
_scan_in_progress: bool = False

# Persist results to disk so they survive restarts
DATA_DIR = Path(__file__).parent.parent / "data"
BATCH_RESULTS_FILE = DATA_DIR / "batch_scan_results.json"

IST = timezone(timedelta(hours=5, minutes=30))


def _load_persisted_results() -> Optional[dict]:
    """Load last batch scan results from disk."""
    global _last_batch_scan, _last_batch_scan_time
    try:
        if BATCH_RESULTS_FILE.exists():
            with open(BATCH_RESULTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            _last_batch_scan = data
            _last_batch_scan_time = data.get("scan_time")
            logger.info(f"Loaded persisted batch scan from {_last_batch_scan_time}")
            return data
    except Exception as e:
        logger.warning(f"Could not load persisted batch scan: {e}")
    return None


def _persist_results(data: dict):
    """Save batch scan results to disk."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(BATCH_RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info(f"Persisted batch scan results to {BATCH_RESULTS_FILE}")
    except Exception as e:
        logger.warning(f"Could not persist batch scan results: {e}")


# ── Yahoo Finance Chart API ─────────────────────────────────────

def _fetch_yahoo_chart(ticker: str, period: str = "6mo", interval: str = "1d") -> tuple[Optional[pd.DataFrame], Optional[float]]:
    """Fetch OHLCV data from Yahoo Finance v8 Chart API."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {
        "range": period,
        "interval": interval,
        "includePrePost": "false",
        "events": "",
    }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=12, verify=False)
        if resp.status_code != 200:
            return None, None

        data = resp.json()
        chart = data.get("chart", {})
        result = chart.get("result", [])
        if not result:
            return None, None

        r = result[0]
        timestamps = r.get("timestamp", [])
        quote = r.get("indicators", {}).get("quote", [{}])[0]

        if not timestamps or not quote:
            return None, None

        df = pd.DataFrame({
            "Open": quote.get("open", []),
            "High": quote.get("high", []),
            "Low": quote.get("low", []),
            "Close": quote.get("close", []),
            "Volume": quote.get("volume", []),
        }, index=pd.to_datetime(timestamps, unit="s"))

        df = df.dropna(subset=["Close"])
        if df.empty:
            return None, None

        meta = r.get("meta", {})
        current_price = meta.get("regularMarketPrice")

        return df, current_price

    except Exception as e:
        logger.warning(f"Yahoo Chart API error for {ticker}: {e}")
        return None, None


# ── Swing Trade Scoring Engine ──────────────────────────────────

def _score_swing_opportunity(
    current_price: float,
    swing_indicators: dict,
    chart_patterns: list,
    support_resistance: dict,
) -> dict:
    """
    Score a stock for swing trading opportunity (0-100).

    Scoring criteria:
    - RSI positioning (oversold = bullish opportunity, overbought = bearish) — 15pts
    - MACD trend & crossover signals — 15pts
    - Bollinger Band positioning (squeeze, oversold bounce) — 10pts
    - Chart pattern signals (bullish patterns = buy, bearish = short) — 20pts
    - Support/Resistance proximity (near support = buy, near resistance = short) — 15pts
    - Volume confirmation (accumulation, volume spikes) — 10pts
    - Trend alignment (multi-timeframe trend) — 15pts

    Returns dict with:
    - swing_score: 0-100 composite score
    - direction: "LONG" or "SHORT"
    - confidence: "High", "Medium", "Low"
    - entry, stop_loss, target prices
    - reasons: list of scoring reasons
    - risk_reward: ratio
    """
    long_score = 0
    short_score = 0
    long_reasons = []
    short_reasons = []

    # ── RSI Analysis (15 pts) ──
    rsi = swing_indicators.get("rsi_14")
    if rsi is not None:
        if rsi < 30:
            long_score += 15
            long_reasons.append(f"RSI oversold at {rsi:.0f} — bounce likely")
        elif rsi < 40:
            long_score += 10
            long_reasons.append(f"RSI near oversold at {rsi:.0f}")
        elif rsi > 70:
            short_score += 15
            short_reasons.append(f"RSI overbought at {rsi:.0f} — pullback likely")
        elif rsi > 60:
            short_score += 8
            short_reasons.append(f"RSI elevated at {rsi:.0f}")
        # Neutral RSI (40-60) gives slight long bias if trending up
        elif 45 <= rsi <= 55:
            long_score += 3
            short_score += 3

    # ── MACD Analysis (15 pts) ──
    macd_trend = swing_indicators.get("macd_trend")
    macd_crossover = swing_indicators.get("macd_crossover")
    macd_hist = swing_indicators.get("macd_histogram", 0)

    if macd_trend == "Bullish":
        long_score += 8
        long_reasons.append("MACD bullish trend")
    elif macd_trend == "Bearish":
        short_score += 8
        short_reasons.append("MACD bearish trend")

    if macd_crossover == "Bullish crossover":
        long_score += 7
        long_reasons.append("MACD bullish crossover — fresh buy signal")
    elif macd_crossover == "Bearish crossover":
        short_score += 7
        short_reasons.append("MACD bearish crossover — fresh sell signal")

    # Histogram momentum
    if macd_hist > 0 and macd_trend == "Bullish":
        long_score += 3
    elif macd_hist < 0 and macd_trend == "Bearish":
        short_score += 3

    # ── Bollinger Band Analysis (10 pts) ──
    bb_signal = swing_indicators.get("bb_signal", "")
    bb_width = swing_indicators.get("bb_width_pct", 0)

    if "oversold" in bb_signal.lower() or "below lower" in bb_signal.lower():
        long_score += 10
        long_reasons.append("Price below lower Bollinger Band — oversold bounce setup")
    elif "overbought" in bb_signal.lower() or "above upper" in bb_signal.lower():
        short_score += 10
        short_reasons.append("Price above upper Bollinger Band — overbought")
    elif "squeeze" in bb_signal.lower():
        long_score += 5
        short_score += 5
        long_reasons.append(f"Bollinger squeeze ({bb_width:.1f}%) — big move expected")

    # ── Chart Pattern Analysis (20 pts) ──
    bullish_patterns = []
    bearish_patterns = []
    for p in chart_patterns:
        ptype = p.get("type", "")
        pname = p.get("pattern", "")
        reliability = p.get("reliability", "medium")
        rel_score = {"very high": 20, "high": 16, "medium-high": 12, "medium": 8}.get(reliability, 8)

        if ptype == "bullish":
            bullish_patterns.append(p)
            long_score += min(rel_score, 20)
            long_reasons.append(f"Bullish pattern: {pname} ({reliability} reliability)")
        elif ptype == "bearish":
            bearish_patterns.append(p)
            short_score += min(rel_score, 20)
            short_reasons.append(f"Bearish pattern: {pname} ({reliability} reliability)")

    # ── Support/Resistance Proximity (15 pts) ──
    supports = support_resistance.get("support_levels", [])
    resistances = support_resistance.get("resistance_levels", [])

    nearest_support = None
    nearest_resistance = None

    if supports:
        nearest_support = supports[0]  # Already sorted closest first
        dist_pct = abs(current_price - nearest_support["price"]) / current_price * 100
        if dist_pct < 2:
            long_score += 15
            long_reasons.append(f"At strong support ₹{nearest_support['price']:.0f} (strength: {nearest_support['strength']})")
        elif dist_pct < 5:
            long_score += 10
            long_reasons.append(f"Near support ₹{nearest_support['price']:.0f} ({dist_pct:.1f}% away)")
        elif dist_pct < 8:
            long_score += 5

    if resistances:
        nearest_resistance = resistances[0]
        dist_pct = abs(nearest_resistance["price"] - current_price) / current_price * 100
        if dist_pct < 2:
            short_score += 15
            short_reasons.append(f"At strong resistance ₹{nearest_resistance['price']:.0f} (strength: {nearest_resistance['strength']})")
        elif dist_pct < 5:
            short_score += 10
            short_reasons.append(f"Near resistance ₹{nearest_resistance['price']:.0f} ({dist_pct:.1f}% away)")
        elif dist_pct < 8:
            short_score += 5

    # ── Volume Analysis (10 pts) ──
    obv_trend = swing_indicators.get("obv_trend")
    rel_volume = swing_indicators.get("relative_volume", 1.0)
    vol_signal = swing_indicators.get("volume_signal", "")

    if obv_trend == "Accumulation":
        long_score += 5
        long_reasons.append("OBV shows accumulation")
    elif obv_trend == "Distribution":
        short_score += 5
        short_reasons.append("OBV shows distribution")

    if rel_volume > 1.5:
        long_score += 5
        short_score += 5  # High volume confirms either direction
        long_reasons.append(f"Volume surge: {rel_volume:.1f}x average")

    # ── Trend Alignment (15 pts) ──
    # Check from chart patterns for trend analysis
    trend_pattern = None
    for p in chart_patterns:
        if p.get("pattern") == "Trend Analysis":
            trend_pattern = p
            break

    if trend_pattern:
        short_trend = trend_pattern.get("short_trend", "")
        medium_trend = trend_pattern.get("medium_trend", "")
        overall = trend_pattern.get("type", "")

        if overall == "bullish":
            long_score += 10
            long_reasons.append(f"Trend aligned bullish (Short: {short_trend}, Medium: {medium_trend})")
        elif overall == "bearish":
            short_score += 10
            short_reasons.append(f"Trend aligned bearish (Short: {short_trend}, Medium: {medium_trend})")

        # Cross signals
        cross = trend_pattern.get("cross_signal")
        if cross and "Golden" in cross:
            long_score += 5
            long_reasons.append("Golden Cross signal (20 EMA > 50 EMA)")
        elif cross and "Death" in cross:
            short_score += 5
            short_reasons.append("Death Cross signal (20 EMA < 50 EMA)")

    # ── Stochastic RSI bonus ──
    stoch_rsi = swing_indicators.get("stoch_rsi")
    stoch_signal = swing_indicators.get("stoch_rsi_signal", "")
    if stoch_signal == "Oversold":
        long_score += 5
        long_reasons.append(f"Stochastic RSI oversold ({stoch_rsi:.0f})")
    elif stoch_signal == "Overbought":
        short_score += 5
        short_reasons.append(f"Stochastic RSI overbought ({stoch_rsi:.0f})")

    # ── Determine Direction ──
    if long_score > short_score:
        direction = "LONG"
        score = min(100, long_score)
        reasons = long_reasons
    elif short_score > long_score:
        direction = "SHORT"
        score = min(100, short_score)
        reasons = short_reasons
    else:
        direction = "NEUTRAL"
        score = max(long_score, short_score)
        reasons = long_reasons + short_reasons

    # ── Confidence Level ──
    if score >= 65:
        confidence = "High"
    elif score >= 45:
        confidence = "Medium"
    else:
        confidence = "Low"

    # ── Calculate Entry / SL / Target ──
    atr = swing_indicators.get("atr_14", 0)
    suggested_sl = swing_indicators.get("suggested_sl")
    suggested_target = swing_indicators.get("suggested_target")

    if direction == "LONG":
        entry = current_price
        # SL: below nearest support or 1.5x ATR below
        if nearest_support and nearest_support["price"] < current_price:
            stop_loss = round(nearest_support["zone_low"] - atr * 0.3, 2)
        elif suggested_sl:
            stop_loss = suggested_sl
        else:
            stop_loss = round(current_price - 1.5 * atr, 2)

        # Target: nearest resistance or 2x ATR above
        if nearest_resistance and nearest_resistance["price"] > current_price:
            target = round(nearest_resistance["price"], 2)
        elif suggested_target:
            target = suggested_target
        else:
            target = round(current_price + 2 * atr, 2)

        # Check pattern targets
        for p in bullish_patterns:
            if p.get("target") and p["target"] > current_price:
                target = max(target, p["target"])
                break

    elif direction == "SHORT":
        entry = current_price
        # SL: above nearest resistance or 1.5x ATR above
        if nearest_resistance and nearest_resistance["price"] > current_price:
            stop_loss = round(nearest_resistance["zone_high"] + atr * 0.3, 2)
        else:
            stop_loss = round(current_price + 1.5 * atr, 2)

        # Target: nearest support or 2x ATR below
        if nearest_support and nearest_support["price"] < current_price:
            target = round(nearest_support["price"], 2)
        elif suggested_sl:
            target = suggested_sl  # Use the suggested SL as short target
        else:
            target = round(current_price - 2 * atr, 2)

        # Check pattern targets
        for p in bearish_patterns:
            if p.get("target") and p["target"] < current_price:
                target = min(target, p["target"])
                break
    else:
        entry = current_price
        stop_loss = round(current_price - 1.5 * atr, 2) if atr else None
        target = round(current_price + 2 * atr, 2) if atr else None

    # ── Risk/Reward Ratio ──
    risk_reward = None
    if entry and stop_loss and target:
        risk = abs(entry - stop_loss)
        reward = abs(target - entry)
        if risk > 0:
            risk_reward = round(reward / risk, 2)

    return {
        "swing_score": score,
        "direction": direction,
        "confidence": confidence,
        "entry": round(entry, 2) if entry else None,
        "stop_loss": stop_loss,
        "target": target,
        "risk_reward": risk_reward,
        "reasons": reasons[:6],  # Top 6 reasons
        "long_score": long_score,
        "short_score": short_score,
        "bullish_patterns": [p.get("pattern") for p in bullish_patterns],
        "bearish_patterns": [p.get("pattern") for p in bearish_patterns],
    }


# ── Main Batch Scanner ──────────────────────────────────────────

async def run_batch_swing_scan(
    category_filter: Optional[str] = None,
    min_score: float = 0.0,
    direction_filter: Optional[str] = None,
) -> dict:
    """
    Scan all NIFTY stocks for swing trading opportunities.

    For each stock:
    1. Fetch 6-month daily OHLCV from Yahoo Chart API
    2. Run chart pattern detection
    3. Calculate swing indicators (RSI, MACD, BB, ATR, Stochastic, Volume)
    4. Calculate support/resistance levels
    5. Score for swing trading opportunity
    6. Rank and return top opportunities

    Args:
        category_filter: Optional category to filter (e.g., "Banking", "IT")
        min_score: Minimum swing score to include (default 0)
        direction_filter: "LONG", "SHORT", or None for all

    Returns:
        Dict with scan results, metadata, and ranked opportunities.
    """
    global _last_batch_scan, _last_batch_scan_time, _scan_in_progress

    if _scan_in_progress:
        return {"error": "Scan already in progress. Please wait.", "in_progress": True}

    _scan_in_progress = True
    scan_start = time.time()

    stocks = get_nifty50_stocks()

    # Filter by category if specified
    if category_filter:
        # Match against the fallback stock list categories
        stocks = [s for s in stocks if category_filter.lower() in s.get("name", "").lower()
                  or category_filter.lower() in s.get("ticker", "").lower()]

    results = []
    errors = []
    scanned = 0

    logger.info(f"🎯 Starting batch swing scan for {len(stocks)} stocks...")

    loop = asyncio.get_event_loop()

    async def _scan_single_stock(stock: dict):
        """Analyze a single stock for swing trading opportunity."""
        nonlocal scanned
        try:
            # Fetch 6-month daily data
            def _fetch():
                return _fetch_yahoo_chart(stock["ticker"], period="6mo", interval="1d")

            hist, price = await loop.run_in_executor(None, _fetch)

            if hist is None or hist.empty or len(hist) < 30:
                errors.append({"ticker": stock["ticker"], "error": "Insufficient data"})
                return

            if not price:
                price = float(hist["Close"].iloc[-1])

            current_price = float(price)

            # Run technical analysis
            patterns = detect_chart_patterns(hist)
            swing = calculate_swing_indicators(hist)
            sr = calculate_support_resistance(hist, current_price)

            # Score for swing trading
            opportunity = _score_swing_opportunity(
                current_price=current_price,
                swing_indicators=swing,
                chart_patterns=patterns,
                support_resistance=sr,
            )

            # Calculate additional metrics
            closes = hist["Close"].values
            volumes = hist["Volume"].values

            # 1-month return
            month_len = min(21, len(closes))
            one_m_return = float((closes[-1] - closes[-month_len]) / closes[-month_len] * 100)

            # 1-week return
            week_len = min(5, len(closes))
            one_w_return = float((closes[-1] - closes[-week_len]) / closes[-week_len] * 100)

            # ATR % for volatility
            atr_pct = swing.get("atr_pct", 0)

            # Volume ratio
            valid_vols = volumes[volumes > 0]
            if len(valid_vols) >= 10:
                recent_vol = float(np.mean(valid_vols[-5:]))
                long_vol = float(np.mean(valid_vols[-min(60, len(valid_vols)):]))
                volume_ratio = round(recent_vol / long_vol, 2) if long_vol > 0 else 1.0
            else:
                volume_ratio = 1.0

            # Pattern names for display
            pattern_names = [p.get("pattern") for p in patterns if p.get("pattern") != "Trend Analysis"]

            result = {
                "name": stock["name"],
                "ticker": stock["ticker"],
                "price": round(current_price, 2),
                "swing_score": opportunity["swing_score"],
                "direction": opportunity["direction"],
                "confidence": opportunity["confidence"],
                "entry": opportunity["entry"],
                "stop_loss": opportunity["stop_loss"],
                "target": opportunity["target"],
                "risk_reward": opportunity["risk_reward"],
                "reasons": opportunity["reasons"],
                "long_score": opportunity["long_score"],
                "short_score": opportunity["short_score"],
                # Technical indicators
                "rsi": swing.get("rsi_14"),
                "rsi_signal": swing.get("rsi_signal"),
                "macd_trend": swing.get("macd_trend"),
                "macd_crossover": swing.get("macd_crossover"),
                "bb_signal": swing.get("bb_signal"),
                "obv_trend": swing.get("obv_trend"),
                "stoch_rsi": swing.get("stoch_rsi"),
                # Price metrics
                "1w_return": round(one_w_return, 2),
                "1m_return": round(one_m_return, 2),
                "atr_pct": atr_pct,
                "volume_ratio": volume_ratio,
                # Patterns
                "patterns": pattern_names,
                "bullish_patterns": opportunity["bullish_patterns"],
                "bearish_patterns": opportunity["bearish_patterns"],
                # Key levels
                "nearest_support": supports[0]["price"] if (supports := sr.get("support_levels", [])) else None,
                "nearest_resistance": resistances[0]["price"] if (resistances := sr.get("resistance_levels", [])) else None,
            }

            results.append(result)
            scanned += 1

        except Exception as e:
            errors.append({"ticker": stock["ticker"], "error": str(e)[:100]})
            logger.warning(f"Batch scan error for {stock['name']}: {e}")

    # Run concurrently with semaphore (10 concurrent HTTP calls)
    semaphore = asyncio.Semaphore(10)

    async def _limited_scan(stock):
        async with semaphore:
            await _scan_single_stock(stock)

    await asyncio.gather(*[_limited_scan(s) for s in stocks])

    # Apply filters
    if min_score > 0:
        results = [r for r in results if r["swing_score"] >= min_score]

    if direction_filter:
        results = [r for r in results if r["direction"] == direction_filter.upper()]

    # Sort by swing score descending
    results.sort(key=lambda x: x["swing_score"], reverse=True)

    # Separate into opportunity tiers
    high_conviction = [r for r in results if r["confidence"] == "High" and r["direction"] != "NEUTRAL"]
    medium_conviction = [r for r in results if r["confidence"] == "Medium" and r["direction"] != "NEUTRAL"]
    watchlist = [r for r in results if r["confidence"] == "Low" or r["direction"] == "NEUTRAL"]

    # Long vs Short breakdown
    long_opportunities = [r for r in results if r["direction"] == "LONG"]
    short_opportunities = [r for r in results if r["direction"] == "SHORT"]

    scan_duration = round(time.time() - scan_start, 1)
    now_ist = datetime.now(IST)

    scan_result = {
        "scan_time": now_ist.isoformat(),
        "scan_date": now_ist.strftime("%d %b %Y"),
        "scan_time_display": now_ist.strftime("%I:%M %p IST"),
        "scan_duration_seconds": scan_duration,
        "total_stocks": len(stocks),
        "stocks_scanned": scanned,
        "stocks_with_opportunities": len([r for r in results if r["direction"] != "NEUTRAL"]),
        "errors_count": len(errors),
        # Summary stats
        "summary": {
            "high_conviction_count": len(high_conviction),
            "medium_conviction_count": len(medium_conviction),
            "watchlist_count": len(watchlist),
            "long_count": len(long_opportunities),
            "short_count": len(short_opportunities),
            "avg_score": round(np.mean([r["swing_score"] for r in results]), 1) if results else 0,
            "top_score": results[0]["swing_score"] if results else 0,
        },
        # Categorized results
        "high_conviction": high_conviction[:10],
        "medium_conviction": medium_conviction[:10],
        "long_opportunities": sorted(long_opportunities, key=lambda x: x["swing_score"], reverse=True)[:15],
        "short_opportunities": sorted(short_opportunities, key=lambda x: x["swing_score"], reverse=True)[:10],
        "all_results": results,
        "errors": errors[:10],  # First 10 errors
    }

    # Cache and persist
    _last_batch_scan = scan_result
    _last_batch_scan_time = scan_result["scan_time"]
    _scan_in_progress = False

    _persist_results(scan_result)

    logger.info(
        f"🎯 Batch swing scan complete in {scan_duration}s: "
        f"{scanned}/{len(stocks)} stocks scanned, "
        f"{len(high_conviction)} high conviction, "
        f"{len(medium_conviction)} medium conviction, "
        f"{len(long_opportunities)} long, {len(short_opportunities)} short"
    )

    return scan_result


def get_cached_batch_scan() -> Optional[dict]:
    """Return cached batch scan results, loading from disk if needed."""
    global _last_batch_scan
    if _last_batch_scan:
        return _last_batch_scan
    return _load_persisted_results()


def is_scan_in_progress() -> bool:
    """Check if a batch scan is currently running."""
    return _scan_in_progress


async def run_scheduled_batch_scan():
    """Entry point for the scheduler — runs the batch scan and logs results."""
    logger.info("⏰ Scheduled batch swing scan triggered (4:00 PM IST)")
    try:
        result = await run_batch_swing_scan()
        logger.info(
            f"⏰ Scheduled scan complete: "
            f"{result['summary']['high_conviction_count']} high conviction opportunities found"
        )
    except Exception as e:
        logger.error(f"⏰ Scheduled batch scan failed: {e}")
