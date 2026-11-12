"""Alert service: background scheduler + alert trigger logic."""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import yfinance as yf
import numpy as np

from services.notification_service import send_alert_notification

logger = logging.getLogger(__name__)

# Data directory for persistence
DATA_DIR = Path(__file__).parent.parent / "data"
WATCHLIST_FILE = DATA_DIR / "watchlist.json"
ALERTS_FILE = DATA_DIR / "alerts_history.json"


def _ensure_data_dir():
    """Ensure the data directory and files exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not WATCHLIST_FILE.exists():
        WATCHLIST_FILE.write_text("[]")
    if not ALERTS_FILE.exists():
        ALERTS_FILE.write_text("[]")


# ── Watchlist Management ────────────────────────────────────────

def get_watchlist() -> list[dict]:
    """Load the watchlist from disk."""
    _ensure_data_dir()
    try:
        data = json.loads(WATCHLIST_FILE.read_text())
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def add_to_watchlist(ticker: str, stock_name: str) -> dict:
    """Add a stock to the watchlist."""
    _ensure_data_dir()
    watchlist = get_watchlist()

    # Check if already exists
    for item in watchlist:
        if item["ticker"] == ticker:
            return item  # Already in watchlist

    new_item = {
        "ticker": ticker,
        "stock_name": stock_name,
        "added_at": datetime.utcnow().isoformat(),
    }
    watchlist.append(new_item)
    WATCHLIST_FILE.write_text(json.dumps(watchlist, indent=2))
    logger.info(f"Added {stock_name} ({ticker}) to watchlist")
    return new_item


def remove_from_watchlist(ticker: str) -> bool:
    """Remove a stock from the watchlist."""
    _ensure_data_dir()
    watchlist = get_watchlist()
    original_len = len(watchlist)
    watchlist = [item for item in watchlist if item["ticker"] != ticker]

    if len(watchlist) < original_len:
        WATCHLIST_FILE.write_text(json.dumps(watchlist, indent=2))
        logger.info(f"Removed {ticker} from watchlist")
        return True
    return False


# ── Alert History ───────────────────────────────────────────────

def get_alerts_history(limit: int = 50) -> list[dict]:
    """Load recent alerts from disk."""
    _ensure_data_dir()
    try:
        data = json.loads(ALERTS_FILE.read_text())
        if isinstance(data, list):
            return data[-limit:]
        return []
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def _save_alert(alert: dict):
    """Save an alert to the history file."""
    _ensure_data_dir()
    alerts = get_alerts_history(limit=500)
    alerts.append(alert)
    # Keep only last 500 alerts
    if len(alerts) > 500:
        alerts = alerts[-500:]
    ALERTS_FILE.write_text(json.dumps(alerts, indent=2))


# ── Alert Trigger Checks ───────────────────────────────────────

def _calculate_rsi(prices, period: int = 14) -> Optional[float]:
    """Calculate RSI from price series."""
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
        return round(100 - (100 / (1 + rs)), 2)
    except Exception:
        return None


async def check_stock_alerts(ticker: str, stock_name: str) -> list[dict]:
    """
    Check a single stock for alert triggers.

    Returns list of triggered alerts.
    """
    alerts = []
    loop = asyncio.get_event_loop()

    try:
        def _fetch():
            t = yf.Ticker(ticker)
            info = t.info or {}
            try:
                hist = t.history(period="1mo")
            except Exception:
                hist = None
            return info, hist

        info, hist = await loop.run_in_executor(None, _fetch)

        price = info.get("currentPrice") or info.get("regularMarketPrice")
        high_52 = info.get("fiftyTwoWeekHigh")
        low_52 = info.get("fiftyTwoWeekLow")
        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
        volume = info.get("volume") or info.get("regularMarketVolume")
        avg_volume = info.get("averageVolume")

        if not price:
            return alerts

        # 1. Price Breakout — above 52-week high
        if high_52 and price >= high_52:
            alerts.append({
                "ticker": ticker,
                "stock_name": stock_name,
                "trigger": "52-Week High Breakout",
                "message": f"Price ₹{price:.2f} has reached/exceeded 52-week high of ₹{high_52:.2f}",
                "priority": "high",
                "timestamp": datetime.utcnow().isoformat(),
            })

        # 2. Price Breakdown — below 52-week low
        if low_52 and price <= low_52:
            alerts.append({
                "ticker": ticker,
                "stock_name": stock_name,
                "trigger": "52-Week Low Breakdown",
                "message": f"Price ₹{price:.2f} has reached/fallen below 52-week low of ₹{low_52:.2f}",
                "priority": "high",
                "timestamp": datetime.utcnow().isoformat(),
            })

        # 3. Big Daily Move — > 5% change
        if prev_close and prev_close > 0:
            daily_change = ((price - prev_close) / prev_close) * 100
            if abs(daily_change) > 5:
                direction = "up" if daily_change > 0 else "down"
                alerts.append({
                    "ticker": ticker,
                    "stock_name": stock_name,
                    "trigger": f"Big Daily Move ({direction})",
                    "message": f"Price moved {daily_change:+.2f}% today (₹{prev_close:.2f} → ₹{price:.2f})",
                    "priority": "medium",
                    "timestamp": datetime.utcnow().isoformat(),
                })

        # 4. Volume Spike — > 3x average
        if volume and avg_volume and avg_volume > 0:
            vol_ratio = volume / avg_volume
            if vol_ratio > 3:
                alerts.append({
                    "ticker": ticker,
                    "stock_name": stock_name,
                    "trigger": "Volume Spike",
                    "message": f"Volume {volume:,} is {vol_ratio:.1f}x the 20-day average ({avg_volume:,})",
                    "priority": "medium",
                    "timestamp": datetime.utcnow().isoformat(),
                })

        # 5. RSI Extreme
        if hist is not None and not hist.empty:
            rsi = _calculate_rsi(hist["Close"].values)
            if rsi is not None:
                if rsi < 25:
                    alerts.append({
                        "ticker": ticker,
                        "stock_name": stock_name,
                        "trigger": "RSI Extremely Oversold",
                        "message": f"RSI at {rsi:.0f} — stock is extremely oversold",
                        "priority": "medium",
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                elif rsi > 80:
                    alerts.append({
                        "ticker": ticker,
                        "stock_name": stock_name,
                        "trigger": "RSI Extremely Overbought",
                        "message": f"RSI at {rsi:.0f} — stock is extremely overbought",
                        "priority": "medium",
                        "timestamp": datetime.utcnow().isoformat(),
                    })

    except Exception as e:
        logger.warning(f"Error checking alerts for {ticker}: {e}")

    return alerts


async def run_alert_scan(tickers: Optional[list[dict]] = None) -> list[dict]:
    """
    Run alert scan on watchlist stocks (or provided list).

    Args:
        tickers: Optional list of {"ticker": ..., "stock_name": ...} dicts.
                 If None, uses the watchlist.

    Returns:
        List of triggered alerts.
    """
    if tickers is None:
        tickers = get_watchlist()

    if not tickers:
        logger.info("No stocks to scan for alerts (watchlist is empty)")
        return []

    logger.info(f"Running alert scan for {len(tickers)} stocks...")
    all_alerts = []

    semaphore = asyncio.Semaphore(5)

    async def _check_with_limit(stock):
        async with semaphore:
            return await check_stock_alerts(stock["ticker"], stock["stock_name"])

    results = await asyncio.gather(
        *[_check_with_limit(s) for s in tickers],
        return_exceptions=True,
    )

    for result in results:
        if isinstance(result, list):
            all_alerts.extend(result)
        elif isinstance(result, Exception):
            logger.warning(f"Alert check error: {result}")

    # Save and notify
    for alert in all_alerts:
        _save_alert(alert)
        await send_alert_notification(
            ticker=alert["ticker"],
            stock_name=alert["stock_name"],
            trigger=alert["trigger"],
            message=alert["message"],
            priority=alert["priority"],
        )

    logger.info(f"Alert scan complete: {len(all_alerts)} alerts triggered")
    return all_alerts
