"""Google Finance scraper — primary stock data source.

Scrapes the public Google Finance quote page to extract stock data.
No API key required. Works behind corporate proxies (Zscaler, etc.)
that block Yahoo Finance.

Usage:
    data = await fetch_google_finance("TCS.NS")
    # Returns dict with current_price, pe_ratio, 52_week_high, etc.
"""

import asyncio
import logging
import re
from typing import Optional

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# ── Ticker conversion ───────────────────────────────────────────

# Map NSE ticker suffix to Google Finance exchange code
_EXCHANGE_MAP = {
    ".NS": "NSE",
    ".BO": "BOM",
}

# Special tickers (indices, etc.)
_SPECIAL_TICKERS = {
    "^NSEI": ("NIFTY_50", "INDEXNSE"),
    "^BSESN": ("SENSEX", "INDEXBOM"),
    "^NSEBANK": ("NIFTY_BANK", "INDEXNSE"),
}


def _to_google_ticker(yf_ticker: str) -> Optional[str]:
    """Convert a yfinance-style ticker to Google Finance format.

    Examples:
        TCS.NS  → TCS:NSE
        RELIANCE.NS → RELIANCE:NSE
        ^NSEI → NIFTY_50:INDEXNSE
    """
    if yf_ticker in _SPECIAL_TICKERS:
        symbol, exchange = _SPECIAL_TICKERS[yf_ticker]
        return f"{symbol}:{exchange}"

    for suffix, exchange in _EXCHANGE_MAP.items():
        if yf_ticker.endswith(suffix):
            symbol = yf_ticker[: -len(suffix)]
            return f"{symbol}:{exchange}"

    return None


# ── Value parsing helpers ────────────────────────────────────────

def _parse_price(value: str) -> Optional[float]:
    """Parse a price string like '₹2,438.60' or '2,438.60' to float."""
    if not value:
        return None
    # Remove currency symbols and commas
    cleaned = re.sub(r"[₹$€£,\s]", "", value)
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _parse_large_number(value: str) -> Optional[str]:
    """Parse market cap like '8.72T' and return human-readable Indian format."""
    if not value:
        return None
    cleaned = value.strip().replace(",", "")
    match = re.match(r"([\d.]+)\s*([TBMK])?", cleaned)
    if not match:
        return value
    num = float(match.group(1))
    suffix = match.group(2) or ""

    # Convert to raw number
    multipliers = {"T": 1e12, "B": 1e9, "M": 1e6, "K": 1e3}
    raw = num * multipliers.get(suffix, 1)

    # Format in Indian style
    if raw >= 1e12:
        return f"₹{raw / 1e12:.2f}L Cr"
    elif raw >= 1e10:
        return f"₹{raw / 1e10:.2f}K Cr"
    elif raw >= 1e7:
        return f"₹{raw / 1e7:.2f} Cr"
    else:
        return f"₹{raw:,.0f}"


def _parse_percentage(value: str) -> Optional[float]:
    """Parse a percentage string like '2.74%' to float."""
    if not value:
        return None
    cleaned = re.sub(r"[%\s]", "", value)
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _parse_volume(value: str) -> Optional[int]:
    """Parse volume string like '3.45M' or '1,234,567' to int."""
    if not value:
        return None
    cleaned = value.strip().replace(",", "")
    # Handle suffixed values like 3.45M
    match = re.match(r"([\d.]+)\s*([TBMK])?", cleaned)
    if not match:
        return None
    num = float(match.group(1))
    suffix = match.group(2) or ""
    multipliers = {"T": 1e12, "B": 1e9, "M": 1e6, "K": 1e3}
    raw = num * multipliers.get(suffix, 1)
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


# ── Main scraper ─────────────────────────────────────────────────

def _scrape_google_finance(yf_ticker: str) -> dict:
    """Scrape Google Finance for stock data (synchronous, run in executor).

    Args:
        yf_ticker: yfinance-style ticker (e.g., 'TCS.NS')

    Returns:
        Dict with stock data fields matching the yfinance format.
    """
    google_ticker = _to_google_ticker(yf_ticker)
    if not google_ticker:
        logger.warning(f"Cannot convert '{yf_ticker}' to Google Finance format")
        return {}

    url = f"https://www.google.com/finance/quote/{google_ticker}"
    logger.info(f"Google Finance: fetching {url}")

    try:
        response = requests.get(
            url,
            timeout=15,
            verify=False,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

        if response.status_code != 200:
            logger.warning(f"Google Finance returned status {response.status_code}")
            return {}

        html = response.text
        if len(html) < 1000:
            logger.warning("Google Finance returned suspiciously short response")
            return {}

    except Exception as e:
        logger.error(f"Google Finance request failed: {e}")
        return {}

    # ── Extract the main current price ───────────────────────────
    # The main price on the page is in a div with class "YMlKec fxKbKc"
    # Pattern: <div class="YMlKec fxKbKc">₹2,438.60</div>
    current_price = None
    price_match = re.search(
        r'class="YMlKec fxKbKc"[^>]*>([^<]+)</div>',
        html,
    )
    if price_match:
        current_price = _parse_price(price_match.group(1))
        logger.info(f"Google Finance: main price element = {price_match.group(1)} → {current_price}")

    # ── Extract the stock name ───────────────────────────────────
    # The company name is in: <div class="zzDege">Company Name</div>
    stock_name_extracted = None
    name_match = re.search(r'class="zzDege"[^>]*>([^<]+)</div>', html)
    if name_match:
        stock_name_extracted = name_match.group(1).strip()

    # ── Parse key-value data table ───────────────────────────────
    # Extract key-value pairs: <div class="SwQK7">LABEL</div>...<div class="dO6ijd">VALUE</div>
    pairs = re.findall(
        r'class="SwQK7">([^<]+)</div>.*?class="dO6ijd">([^<]+)</div>',
        html,
        re.DOTALL,
    )

    # Build a lookup dict (first occurrence only — page has duplicates)
    kv: dict[str, str] = {}
    for label, value in pairs:
        label = label.strip()
        value = value.strip()
        if label not in kv:
            kv[label] = value

    logger.info(f"Google Finance: extracted {len(kv)} data fields for {yf_ticker}: {list(kv.keys())}")

    # ── Fallback price from table data ───────────────────────────
    if current_price is None:
        open_price = _parse_price(kv.get("Open", ""))
        high_price = _parse_price(kv.get("High", ""))
        low_price = _parse_price(kv.get("Low", ""))
        prev_close = _parse_price(kv.get("Previous close", ""))

        if high_price and low_price:
            current_price = round((high_price + low_price) / 2, 2)
        elif open_price:
            current_price = open_price
        elif prev_close:
            current_price = prev_close

    # ── Map to our standard format ───────────────────────────────
    week_52_high = _parse_price(kv.get("52-wk high", ""))
    week_52_low = _parse_price(kv.get("52-wk low", ""))

    # Extract stock symbol from the ticker
    symbol = yf_ticker.replace(".NS", "").replace(".BO", "")

    data = {
        "current_price": current_price,
        "open_price": _parse_price(kv.get("Open", "")),
        "day_high": _parse_price(kv.get("High", "")),
        "day_low": _parse_price(kv.get("Low", "")),
        "previous_close": _parse_price(kv.get("Previous close", "")),
        "market_cap": _parse_large_number(kv.get("Mkt. cap", "") or kv.get("Market cap", "")),
        "pe_ratio": _parse_percentage(kv.get("P/E ratio", "")),
        "eps": _parse_price(kv.get("EPS", "")),
        "dividend_yield": _parse_percentage(kv.get("Dividend yield", "") or kv.get("Dividend", "") or kv.get("Div yield", "")),
        "52_week_high": week_52_high,
        "52_week_low": week_52_low,
        "volume": _parse_volume(kv.get("Volume", "")),
        "avg_volume": _parse_volume(kv.get("Avg. vol.", "") or kv.get("Avg volume", "")),
        # These aren't available from Google Finance
        "pb_ratio": None,
        "debt_to_equity": None,
        "roe": None,
        "revenue_growth": None,
        "profit_growth": None,
        "promoter_holding": None,
        "sector": None,
        "industry": None,
        # Returns not available from Google Finance (no historical data)
        "1m_return": None,
        "3m_return": None,
        "6m_return": None,
        "1y_return": None,
        # Stock name
        "stock_name": stock_name_extracted or symbol,
        # Source marker
        "_source": "google_finance",
    }

    # Log what we got
    non_null = {k: v for k, v in data.items() if v is not None and not k.startswith("_")}
    logger.info(f"Google Finance: got {len(non_null)} non-null fields, price={current_price}")

    return data


async def fetch_google_finance(yf_ticker: str) -> dict:
    """Async wrapper for Google Finance scraping.

    Args:
        yf_ticker: yfinance-style ticker (e.g., 'TCS.NS')

    Returns:
        Dict with stock data fields, or empty dict on failure.
    """
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, _scrape_google_finance, yf_ticker)
    except Exception as e:
        logger.error(f"Google Finance async fetch failed: {e}")
        return {}
