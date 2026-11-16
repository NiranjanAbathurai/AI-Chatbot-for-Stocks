"""Developing Pattern Scanner Service.

Scans NIFTY 50 stocks for developing chart patterns using the
developing_patterns detection engine. Supports multiple timeframes.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

import pandas as pd
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from services.nifty_stocks import get_nifty50_stocks
from services.developing_patterns import detect_developing_patterns

logger = logging.getLogger(__name__)

# Cache
_last_scan: Optional[dict] = None
_last_scan_time: Optional[str] = None

# Timeframe configs for Yahoo Finance API
TIMEFRAME_CONFIG = {
    "15m": {"period": "5d", "interval": "15m"},
    "1h": {"period": "1mo", "interval": "60m"},
    "4h": {"period": "3mo", "interval": "1d"},  # Yahoo doesn't support 4h; use daily as proxy
    "1d": {"period": "6mo", "interval": "1d"},
}


def _fetch_yahoo_chart(ticker: str, period: str = "6mo", interval: str = "1d"):
    """Fetch OHLCV data from Yahoo Finance v8 Chart API."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"range": period, "interval": interval, "includePrePost": "false", "events": ""}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=12, verify=False)
        if resp.status_code != 200:
            return None, None, None
        data = resp.json()
        chart = data.get("chart", {})
        result = chart.get("result", [])
        if not result:
            return None, None, None
        r = result[0]
        timestamps = r.get("timestamp", [])
        quote = r.get("indicators", {}).get("quote", [{}])[0]
        if not timestamps or not quote:
            return None, None, None
        df = pd.DataFrame({
            "Open": quote.get("open", []),
            "High": quote.get("high", []),
            "Low": quote.get("low", []),
            "Close": quote.get("close", []),
            "Volume": quote.get("volume", []),
        }, index=pd.to_datetime(timestamps, unit="s"))
        df = df.dropna(subset=["Close"])
        if df.empty:
            return None, None, None
        meta = r.get("meta", {})
        current_price = meta.get("regularMarketPrice")
        # Last candle timestamp
        last_ts = datetime.utcfromtimestamp(timestamps[-1]).isoformat() + "Z"
        return df, current_price, last_ts
    except Exception as e:
        logger.warning(f"Yahoo Chart API error for {ticker}: {e}")
        return None, None, None


async def scan_developing_patterns(
    timeframe: str = "1d",
    pattern_filter: Optional[str] = None,
    type_filter: Optional[str] = None,
    stage_filter: Optional[str] = None,
    min_confidence: float = 0.0,
    refresh: bool = False,
) -> dict:
    """Scan NIFTY 50 stocks for developing chart patterns.

    Args:
        timeframe: One of '15m', '1h', '4h', '1d'
        pattern_filter: Filter by pattern name
        type_filter: 'bullish', 'bearish', or 'neutral'
        stage_filter: Filter by stage (e.g. 'Stage 1', 'Stage 2', etc.)
        min_confidence: Minimum structure confidence score
        refresh: Force fresh scan

    Returns:
        Dict with scan results.
    """
    global _last_scan, _last_scan_time

    # Return cached if available and not refreshing
    if not refresh and _last_scan and _last_scan.get("timeframe") == timeframe:
        cached = _apply_filters(_last_scan, pattern_filter, type_filter, stage_filter, min_confidence)
        cached["cached"] = True
        return cached

    stocks = get_nifty50_stocks()
    results = []
    tf_config = TIMEFRAME_CONFIG.get(timeframe, TIMEFRAME_CONFIG["1d"])

    logger.info(f"Starting developing pattern scan for {len(stocks)} stocks (timeframe={timeframe})...")

    loop = asyncio.get_event_loop()

    async def _scan_stock(stock: dict):
        try:
            def _fetch():
                return _fetch_yahoo_chart(stock["ticker"], tf_config["period"], tf_config["interval"])

            hist, price, last_ts = await loop.run_in_executor(None, _fetch)

            if hist is None or hist.empty or len(hist) < 20:
                return

            if not price and not hist.empty:
                price = float(hist["Close"].iloc[-1])

            patterns = detect_developing_patterns(hist, price)

            if not patterns:
                return

            # Mark data freshness
            is_live = False  # We can't guarantee live data from Yahoo
            for p in patterns:
                p["last_candle_time"] = last_ts
                p["data_status"] = "delayed" if not is_live else "live"
                p["timeframe"] = timeframe

            results.append({
                "name": stock["name"],
                "ticker": stock["ticker"],
                "price": round(price, 2) if price else None,
                "last_candle_time": last_ts,
                "data_status": "delayed",
                "patterns": patterns,
            })

        except Exception as e:
            logger.warning(f"Developing pattern scan error for {stock['name']}: {e}")

    # Run concurrently
    semaphore = asyncio.Semaphore(10)

    async def _limited(stock):
        async with semaphore:
            await _scan_stock(stock)

    await asyncio.gather(*[_limited(s) for s in stocks])

    # Sort by best pattern confidence
    def _sort_key(item):
        best = max((p.get("structure_confidence", 0) for p in item["patterns"]), default=0)
        return -best

    results.sort(key=_sort_key)

    result = {
        "last_scan": datetime.utcnow().isoformat(),
        "total_scanned": len(stocks),
        "stocks_with_patterns": len(results),
        "timeframe": timeframe,
        "results": results,
        "cached": False,
    }

    _last_scan = result
    _last_scan_time = result["last_scan"]

    logger.info(f"Developing pattern scan complete: {len(results)}/{len(stocks)} stocks have patterns")

    # Apply filters
    return _apply_filters(result, pattern_filter, type_filter, stage_filter, min_confidence)


def _apply_filters(data: dict, pattern_filter, type_filter, stage_filter, min_confidence) -> dict:
    """Apply filters to scan results."""
    results = data.get("results", [])

    if type_filter:
        filtered = []
        for r in results:
            pats = [p for p in r["patterns"] if p.get("type") == type_filter]
            if pats:
                filtered.append({**r, "patterns": pats})
        results = filtered

    if pattern_filter:
        filtered = []
        for r in results:
            pats = [p for p in r["patterns"] if pattern_filter.lower() in p.get("pattern", "").lower()]
            if pats:
                filtered.append({**r, "patterns": pats})
        results = filtered

    if stage_filter:
        filtered = []
        for r in results:
            pats = [p for p in r["patterns"] if stage_filter.lower() in p.get("stage", "").lower()]
            if pats:
                filtered.append({**r, "patterns": pats})
        results = filtered

    if min_confidence > 0:
        filtered = []
        for r in results:
            pats = [p for p in r["patterns"] if p.get("structure_confidence", 0) >= min_confidence]
            if pats:
                filtered.append({**r, "patterns": pats})
        results = filtered

    return {
        **data,
        "stocks_with_patterns": len(results),
        "results": results,
    }


def get_cached_developing_scan() -> Optional[dict]:
    """Return the last cached developing pattern scan."""
    return _last_scan
