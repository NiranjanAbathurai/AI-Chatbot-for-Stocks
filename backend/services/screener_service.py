"""Stock screening service with scoring system for BUY and SHORT signals."""

import asyncio
import logging
from datetime import datetime
from typing import Optional

import yfinance as yf
import numpy as np
import pandas as pd
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from services.nifty_stocks import get_nifty50_stocks
from services.technical_analysis import detect_chart_patterns

logger = logging.getLogger(__name__)

# Cache for scan results
_last_scan: Optional[dict] = None
_last_scan_time: Optional[str] = None

# Cache for pattern scan results
_last_pattern_scan: Optional[dict] = None
_last_pattern_scan_time: Optional[str] = None

# Cache for volatile/active scan results
_last_volatile_scan: Optional[dict] = None
_last_volatile_scan_time: Optional[str] = None


def _fetch_yahoo_chart(ticker: str, period: str = "6mo", interval: str = "1d") -> tuple[Optional[pd.DataFrame], Optional[float]]:
    """
    Fetch OHLCV data directly from Yahoo Finance v8 Chart API.

    This is faster and more reliable than the yfinance library,
    and returns fresh/current data.

    Args:
        ticker: Yahoo Finance ticker (e.g., 'RELIANCE.NS')
        period: Data period ('1mo', '3mo', '6mo', '1y')
        interval: Candle interval ('1d', '1wk')

    Returns:
        Tuple of (DataFrame with OHLCV columns, current_price).
        Returns (None, None) on failure.
    """
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
            logger.warning(f"Yahoo Chart API returned {resp.status_code} for {ticker}")
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

        # Drop rows with NaN close prices
        df = df.dropna(subset=["Close"])

        if df.empty:
            return None, None

        # Get current price from meta
        meta = r.get("meta", {})
        current_price = meta.get("regularMarketPrice")

        return df, current_price

    except Exception as e:
        logger.warning(f"Yahoo Chart API error for {ticker}: {e}")
        return None, None


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


async def scan_chart_patterns(pattern_filter: Optional[str] = None, type_filter: Optional[str] = None) -> dict:
    """
    Scan NIFTY 50 stocks for active chart patterns.

    Uses Yahoo Finance v8 Chart API (direct HTTP) to fetch fresh 6-month
    daily OHLCV data, then runs detect_chart_patterns() on each stock.

    Falls back to yfinance if the direct API fails.

    Args:
        pattern_filter: Optional pattern name to filter (e.g. "Double Bottom")
        type_filter: Optional type filter — "bullish", "bearish", or None for all

    Returns dict with:
        - last_scan: ISO timestamp
        - total_scanned: number of stocks scanned
        - stocks_with_patterns: number of stocks that have at least one pattern
        - results: list of {name, ticker, price, patterns: [...]}
    """
    global _last_pattern_scan, _last_pattern_scan_time

    stocks = get_nifty50_stocks()
    results = []

    logger.info(f"Starting chart pattern scan for {len(stocks)} stocks (Yahoo Chart API)...")

    loop = asyncio.get_event_loop()

    async def _scan_stock(stock: dict):
        """Fetch history and detect patterns for a single stock."""
        try:
            # Use Yahoo Finance v8 Chart API (fresh, real-time data)
            def _fetch_chart():
                return _fetch_yahoo_chart(stock["ticker"], period="6mo", interval="1d")

            hist, price = await loop.run_in_executor(None, _fetch_chart)

            if hist is None or hist.empty or len(hist) < 30:
                return

            # Use the existing pattern detection engine
            patterns = detect_chart_patterns(hist)

            if not patterns:
                return

            # Apply filters
            filtered = patterns
            if type_filter:
                # Handle "sideways" filter: match both "sideways" and "neutral" types
                if type_filter == "sideways":
                    match_types = {"sideways", "neutral"}
                else:
                    match_types = {type_filter}
                filtered = [p for p in filtered if p.get("type") in match_types]
            if pattern_filter:
                filtered = [p for p in filtered if pattern_filter.lower() in p.get("pattern", "").lower()]

            if not filtered:
                return

            # Get price from last close if not available from API
            if not price and not hist.empty:
                price = float(hist["Close"].iloc[-1])

            results.append({
                "name": stock["name"],
                "ticker": stock["ticker"],
                "price": round(price, 2) if price else None,
                "patterns": filtered,
            })

        except Exception as e:
            logger.warning(f"Pattern scan error for {stock['name']}: {e}")

    # Run concurrently with semaphore (10 concurrent for fast HTTP calls)
    semaphore = asyncio.Semaphore(10)

    async def _limited_scan(stock):
        async with semaphore:
            await _scan_stock(stock)

    await asyncio.gather(*[_limited_scan(s) for s in stocks])

    # Sort: stocks with more patterns first, then by pattern reliability
    reliability_order = {"very high": 4, "high": 3, "medium-high": 2, "medium": 1}

    def _sort_key(item):
        best_reliability = max(
            reliability_order.get(p.get("reliability", "medium"), 1)
            for p in item["patterns"]
        )
        return (-best_reliability, -len(item["patterns"]))

    results.sort(key=_sort_key)

    result = {
        "last_scan": datetime.utcnow().isoformat(),
        "total_scanned": len(stocks),
        "stocks_with_patterns": len(results),
        "results": results,
    }

    _last_pattern_scan = result
    _last_pattern_scan_time = result["last_scan"]

    logger.info(
        f"Pattern scan complete: {len(results)}/{len(stocks)} stocks have patterns"
    )

    return result


def get_cached_pattern_scan() -> Optional[dict]:
    """Return the last cached pattern scan result, if available."""
    return _last_pattern_scan


def get_cached_volatile_scan() -> Optional[dict]:
    """Return the last cached volatile scan result, if available."""
    return _last_volatile_scan


async def scan_volatile_active_stocks(
    sort_by: str = "volatility_score",
    min_score: float = 0.0,
) -> dict:
    """
    Scan NIFTY 50 for high volatility and high volume stocks.

    Metrics calculated per stock:
    - 1-month price volatility (std dev of daily returns)
    - Average True Range (ATR) as % of price
    - Volume ratio (recent 5-day avg volume vs 60-day avg volume)
    - Price range % (high-low / low) in past month
    - Recent volume spikes (days with >2x avg volume in past month)

    Scoring weights:
    - Monthly Volatility: 25%
    - ATR %: 20%
    - Volume Ratio: 25%
    - Price Range: 15%
    - Volume Spike Days: 15%
    """
    global _last_volatile_scan, _last_volatile_scan_time

    stocks = get_nifty50_stocks()
    results = []

    logger.info(f"Starting volatile/active scan for {len(stocks)} stocks...")

    loop = asyncio.get_event_loop()

    async def _scan_stock(stock: dict):
        """Fetch history and calculate volatility metrics for a single stock."""
        try:
            def _fetch_chart():
                return _fetch_yahoo_chart(stock["ticker"], period="3mo", interval="1d")

            hist, price = await loop.run_in_executor(None, _fetch_chart)

            if hist is None or hist.empty or len(hist) < 20:
                return

            closes = hist["Close"].values
            highs = hist["High"].values
            lows = hist["Low"].values
            volumes = hist["Volume"].values

            # Current price
            if not price:
                price = float(closes[-1])

            # ── 1-month data (last ~21 trading days) ──
            month_len = min(21, len(closes))
            month_closes = closes[-month_len:]
            month_highs = highs[-month_len:]
            month_lows = lows[-month_len:]
            month_volumes = volumes[-month_len:]

            # ── Monthly Volatility (annualized std dev of daily returns) ──
            daily_returns = np.diff(month_closes) / month_closes[:-1]
            monthly_vol = float(np.std(daily_returns) * np.sqrt(21) * 100)  # as percentage

            # ── ATR % (14-day ATR as % of current price) ──
            atr_period = min(14, len(closes) - 1)
            tr_values = []
            for i in range(1, atr_period + 1):
                idx = len(closes) - atr_period - 1 + i
                if idx < len(closes) and idx > 0:
                    high_low = highs[idx] - lows[idx]
                    high_prev_close = abs(highs[idx] - closes[idx - 1])
                    low_prev_close = abs(lows[idx] - closes[idx - 1])
                    tr_values.append(max(high_low, high_prev_close, low_prev_close))
            atr = float(np.mean(tr_values)) if tr_values else 0
            atr_pct = (atr / price * 100) if price > 0 else 0

            # ── Volume Ratio (5-day avg vs 60-day avg) ──
            valid_volumes = volumes[volumes > 0]
            if len(valid_volumes) >= 10:
                recent_vol = float(np.mean(valid_volumes[-5:]))
                long_vol = float(np.mean(valid_volumes[-min(60, len(valid_volumes)):]))
                volume_ratio = recent_vol / long_vol if long_vol > 0 else 1.0
            else:
                recent_vol = 0
                long_vol = 0
                volume_ratio = 1.0

            # ── Price Range % (month high-low / low) ──
            month_high = float(np.max(month_highs))
            month_low = float(np.min(month_lows))
            price_range_pct = ((month_high - month_low) / month_low * 100) if month_low > 0 else 0

            # ── Volume Spike Days (days with >2x avg volume in past month) ──
            avg_vol_60 = float(np.mean(valid_volumes[-min(60, len(valid_volumes)):])) if len(valid_volumes) > 0 else 0
            volume_spike_days = 0
            if avg_vol_60 > 0:
                for v in month_volumes:
                    if v > 2 * avg_vol_60:
                        volume_spike_days += 1

            # ── 1-month return ──
            if len(month_closes) >= 2:
                one_m_return = float((month_closes[-1] - month_closes[0]) / month_closes[0] * 100)
            else:
                one_m_return = 0.0

            # ── Composite Volatility Score (0-100) ──
            # Normalize each metric to 0-100 range, then apply weights
            # Monthly Vol: typical range 0-15%, map to 0-100
            vol_score = min(100, monthly_vol / 15 * 100) * 0.25
            # ATR %: typical range 0-5%, map to 0-100
            atr_score = min(100, atr_pct / 5 * 100) * 0.20
            # Volume Ratio: typical range 0.5-3x, map to 0-100
            vr_score = min(100, max(0, (volume_ratio - 0.5) / 2.5 * 100)) * 0.25
            # Price Range: typical range 0-25%, map to 0-100
            pr_score = min(100, price_range_pct / 25 * 100) * 0.15
            # Volume Spikes: 0-10 days, map to 0-100
            vs_score = min(100, volume_spike_days / 10 * 100) * 0.15

            volatility_score = vol_score + atr_score + vr_score + pr_score + vs_score

            # ── Tags ──
            tags = []
            if monthly_vol > 5:
                tags.append("High Volatility")
            if volume_ratio > 1.5:
                tags.append("Volume Surge")
            if price_range_pct > 10:
                tags.append("Wide Range")
            if volume_spike_days >= 3:
                tags.append("Volume Spikes")

            # Average daily volume
            avg_daily_volume = float(np.mean(valid_volumes[-21:])) if len(valid_volumes) >= 21 else float(np.mean(valid_volumes)) if len(valid_volumes) > 0 else 0

            results.append({
                "name": stock["name"],
                "ticker": stock["ticker"],
                "price": round(price, 2),
                "volatility_score": round(volatility_score, 1),
                "monthly_volatility": round(monthly_vol, 1),
                "atr_pct": round(atr_pct, 1),
                "volume_ratio": round(volume_ratio, 1),
                "price_range_pct": round(price_range_pct, 1),
                "volume_spike_days": volume_spike_days,
                "1m_return": round(one_m_return, 1),
                "avg_daily_volume": round(avg_daily_volume),
                "tags": tags,
            })

        except Exception as e:
            logger.warning(f"Volatile scan error for {stock['name']}: {e}")

    # Run concurrently with semaphore
    semaphore = asyncio.Semaphore(10)

    async def _limited_scan(stock):
        async with semaphore:
            await _scan_stock(stock)

    await asyncio.gather(*[_limited_scan(s) for s in stocks])

    # Apply min_score filter
    if min_score > 0:
        results = [r for r in results if r["volatility_score"] >= min_score]

    # Sort by requested field
    valid_sorts = {"volatility_score", "volume_ratio", "atr_pct", "price_range_pct"}
    if sort_by in valid_sorts:
        results.sort(key=lambda x: x.get(sort_by, 0), reverse=True)
    else:
        results.sort(key=lambda x: x.get("volatility_score", 0), reverse=True)

    result = {
        "last_scan": datetime.utcnow().isoformat(),
        "total_scanned": len(stocks),
        "results": results,
    }

    _last_volatile_scan = result
    _last_volatile_scan_time = result["last_scan"]

    logger.info(
        f"Volatile scan complete: {len(results)} stocks scored"
    )

    return result
