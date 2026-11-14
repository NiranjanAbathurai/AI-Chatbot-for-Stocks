"""Stock data service: ticker resolution + multi-source data fetching.

Data source strategy (controlled by STOCK_DATA_SOURCE env var):
  - "google_finance" (default): Scrapes Google Finance. Fast, works behind
    corporate proxies (Zscaler, etc.) that block Yahoo Finance.
  - "yfinance": Uses yfinance library. Best data quality when it works,
    but hangs behind Zscaler/corporate firewalls.
  - "auto": Tries Google Finance first, falls back to yfinance.
"""

import asyncio
import logging
from typing import Optional

import pandas as pd

from config import settings

logger = logging.getLogger(__name__)

# ── NSE Ticker Map ──────────────────────────────────────────────
# Maps common stock names to NSE ticker symbols
TICKER_MAP: dict[str, str] = {
    # NIFTY 50 Stocks
    "adani enterprises": "ADANIENT.NS",
    "adani ports": "ADANIPORTS.NS",
    "apollo hospitals": "APOLLOHOSP.NS",
    "asian paints": "ASIANPAINT.NS",
    "axis bank": "AXISBANK.NS",
    "bajaj auto": "BAJAJ-AUTO.NS",
    "bajaj finance": "BAJFINANCE.NS",
    "bajaj finserv": "BAJAJFINSV.NS",
    "bharti airtel": "BHARTIARTL.NS",
    "airtel": "BHARTIARTL.NS",
    "bpcl": "BPCL.NS",
    "britannia": "BRITANNIA.NS",
    "cipla": "CIPLA.NS",
    "coal india": "COALINDIA.NS",
    "divis lab": "DIVISLAB.NS",
    "divis laboratories": "DIVISLAB.NS",
    "dr reddy": "DRREDDY.NS",
    "dr reddys": "DRREDDY.NS",
    "eicher motors": "EICHERMOT.NS",
    "grasim": "GRASIM.NS",
    "hcl tech": "HCLTECH.NS",
    "hcltech": "HCLTECH.NS",
    "hdfc bank": "HDFCBANK.NS",
    "hdfc life": "HDFCLIFE.NS",
    "hero motocorp": "HEROMOTOCO.NS",
    "hindalco": "HINDALCO.NS",
    "hindustan unilever": "HINDUNILVR.NS",
    "hul": "HINDUNILVR.NS",
    "icici bank": "ICICIBANK.NS",
    "indusind bank": "INDUSINDBK.NS",
    "infosys": "INFY.NS",
    "infy": "INFY.NS",
    "itc": "ITC.NS",
    "jsw steel": "JSWSTEEL.NS",
    "kotak bank": "KOTAKBANK.NS",
    "kotak mahindra bank": "KOTAKBANK.NS",
    "larsen": "LT.NS",
    "l&t": "LT.NS",
    "lt": "LT.NS",
    "larsen & toubro": "LT.NS",
    "mahindra": "M&M.NS",
    "m&m": "M&M.NS",
    "mahindra and mahindra": "M&M.NS",
    "maruti": "MARUTI.NS",
    "maruti suzuki": "MARUTI.NS",
    "nestle": "NESTLEIND.NS",
    "nestle india": "NESTLEIND.NS",
    "ntpc": "NTPC.NS",
    "ongc": "ONGC.NS",
    "power grid": "POWERGRID.NS",
    "reliance": "RELIANCE.NS",
    "reliance industries": "RELIANCE.NS",
    "ril": "RELIANCE.NS",
    "sbi": "SBIN.NS",
    "sbi life": "SBILIFE.NS",
    "state bank": "SBIN.NS",
    "state bank of india": "SBIN.NS",
    "sun pharma": "SUNPHARMA.NS",
    "sun pharmaceutical": "SUNPHARMA.NS",
    "tata consumer": "TATACONSUM.NS",
    "tata motors": "TATAMOTORS.NS",
    "tata steel": "TATASTEEL.NS",
    "tcs": "TCS.NS",
    "tata consultancy": "TCS.NS",
    "tech mahindra": "TECHM.NS",
    "titan": "TITAN.NS",
    "ultratech": "ULTRACEMCO.NS",
    "ultratech cement": "ULTRACEMCO.NS",
    "upl": "UPL.NS",
    "wipro": "WIPRO.NS",

    # Popular Mid-Cap / Other Stocks
    "zomato": "ZOMATO.NS",
    "paytm": "PAYTM.NS",
    "nykaa": "NYKAA.NS",
    "policybazaar": "POLICYBZR.NS",
    "delhivery": "DELHIVERY.NS",
    "vedanta": "VEDL.NS",
    "tata power": "TATAPOWER.NS",
    "tata elxsi": "TATAELXSI.NS",
    "irctc": "IRCTC.NS",
    "hal": "HAL.NS",
    "hindustan aeronautics": "HAL.NS",
    "bhel": "BHEL.NS",
    "ioc": "IOC.NS",
    "indian oil": "IOC.NS",
    "gail": "GAIL.NS",
    "sail": "SAIL.NS",
    "bank of baroda": "BANKBARODA.NS",
    "bob": "BANKBARODA.NS",
    "pnb": "PNB.NS",
    "punjab national bank": "PNB.NS",
    "canara bank": "CANBK.NS",
    "idbi bank": "IDBI.NS",
    "yes bank": "YESBANK.NS",
    "bandhan bank": "BANDHANBNK.NS",
    "federal bank": "FEDERALBNK.NS",
    "idfcfirst": "IDFCFIRSTB.NS",
    "idfc first bank": "IDFCFIRSTB.NS",
    "au bank": "AUBANK.NS",
    "au small finance bank": "AUBANK.NS",
    "hdfc amc": "HDFCAMC.NS",
    "sbi cards": "SBICARD.NS",
    "bajaj holdings": "BAJAJHLDNG.NS",
    "muthoot finance": "MUTHOOTFIN.NS",
    "shriram finance": "SHRIRAMFIN.NS",
    "lic housing": "LICHSGFIN.NS",
    "manappuram": "MANAPPURAM.NS",
    "cholafin": "CHOLAFIN.NS",
    "cholamandalam": "CHOLAFIN.NS",
    "pidilite": "PIDILITIND.NS",
    "berger paints": "BERGEPAINT.NS",
    "havells": "HAVELLS.NS",
    "voltas": "VOLTAS.NS",
    "crompton": "CROMPTON.NS",
    "dixon": "DIXON.NS",
    "dixon technologies": "DIXON.NS",
    "dmart": "DMART.NS",
    "avenue supermarts": "DMART.NS",
    "trent": "TRENT.NS",
    "page industries": "PAGEIND.NS",
    "jubilant food": "JUBLFOOD.NS",
    "jubilant foodworks": "JUBLFOOD.NS",
    "dabur": "DABUR.NS",
    "godrej consumer": "GODREJCP.NS",
    "marico": "MARICO.NS",
    "colgate": "COLPAL.NS",
    "colgate palmolive": "COLPAL.NS",
    "p&g": "PGHH.NS",
    "procter & gamble": "PGHH.NS",
    "biocon": "BIOCON.NS",
    "lupin": "LUPIN.NS",
    "aurobindo pharma": "AUROPHARMA.NS",
    "torrent pharma": "TORNTPHARM.NS",
    "abbott india": "ABBOTINDIA.NS",
    "alkem": "ALKEM.NS",
    "laurus labs": "LAURUSLABS.NS",
    "syngene": "SYNGENE.NS",
    "persistent": "PERSISTENT.NS",
    "persistent systems": "PERSISTENT.NS",
    "coforge": "COFORGE.NS",
    "mphasis": "MPHASIS.NS",
    "ltimindtree": "LTIM.NS",
    "lt mindtree": "LTIM.NS",
    "mindtree": "LTIM.NS",
    "ltts": "LTTS.NS",
    "l&t technology": "LTTS.NS",
    "happiest minds": "HAPPSTMNDS.NS",
    "infosys bpm": "INFY.NS",
    "adani green": "ADANIGREEN.NS",
    "adani power": "ADANIPOWER.NS",
    "adani total gas": "ATGL.NS",
    "adani wilmar": "AWL.NS",
    "ambuja cements": "AMBUJACEM.NS",
    "ambuja": "AMBUJACEM.NS",
    "acc": "ACC.NS",
    "shree cement": "SHREECEM.NS",
    "dalmia bharat": "DALBHARAT.NS",
    "ramco cements": "RAMCOCEM.NS",
    "srf": "SRF.NS",
    "pi industries": "PIIND.NS",
    "aarti industries": "AARTIIND.NS",
    "deepak nitrite": "DEEPAKNTR.NS",
    "clean science": "CLEAN.NS",
    "tata chemicals": "TATACHEM.NS",
    "indian hotels": "INDHOTEL.NS",
    "lemon tree": "LEMONTREE.NS",
    "interglobe": "INDIGO.NS",
    "indigo": "INDIGO.NS",
    "spicejet": "SPICEJET.NS",
    "irfc": "IRFC.NS",
    "rvnl": "RVNL.NS",
    "nhpc": "NHPC.NS",
    "sjvn": "SJVN.NS",
    "recltd": "RECLTD.NS",
    "rec": "RECLTD.NS",
    "pfc": "PFC.NS",
    "power finance": "PFC.NS",
    "iifl finance": "IIFL.NS",
    "angel one": "ANGELONE.NS",
    "cdsl": "CDSL.NS",
    "bse": "BSE.NS",
    "mcdowell": "MCDOWELL-N.NS",
    "united spirits": "MCDOWELL-N.NS",
    "united breweries": "UBL.NS",
    "varun beverages": "VBL.NS",
    "tata communications": "TATACOMM.NS",
    "bharti hexacom": "BHARTIHEXA.NS",
    "idea": "IDEA.NS",
    "vodafone idea": "IDEA.NS",
    "vi": "IDEA.NS",
    "jio financial": "JIOFIN.NS",
    "jio": "JIOFIN.NS",
    "life insurance": "LICI.NS",
    "lic": "LICI.NS",
    "nifty": "^NSEI",
    "sensex": "^BSESN",
    "nifty bank": "^NSEBANK",
    "bank nifty": "^NSEBANK",
}


def resolve_ticker(stock_name: str) -> Optional[str]:
    """
    Resolve a stock name to its NSE ticker symbol.

    Args:
        stock_name: Common name or ticker symbol.

    Returns:
        NSE ticker symbol (e.g., 'AXISBANK.NS') or None if not found.
    """
    name = stock_name.strip().lower()

    # Direct match in ticker map
    if name in TICKER_MAP:
        return TICKER_MAP[name]

    # Check if it's already a valid ticker format
    upper = stock_name.strip().upper()
    if upper.endswith(".NS") or upper.endswith(".BO"):
        return upper

    # Try appending .NS
    potential_ticker = f"{upper}.NS"

    # Partial match - find tickers containing the search term
    matches = [
        (k, v) for k, v in TICKER_MAP.items() if name in k or k in name
    ]
    if len(matches) == 1:
        return matches[0][1]

    # If yfinance is enabled, try it as last resort for unknown tickers
    if settings.STOCK_DATA_SOURCE in ("yfinance", "auto"):
        try:
            import yfinance as yf
            ticker = yf.Ticker(potential_ticker)
            info = ticker.info
            if info and info.get("regularMarketPrice"):
                return potential_ticker
        except Exception:
            pass

    # For google_finance mode, just accept the .NS ticker if it looks valid
    # (Google Finance will return empty data if the ticker doesn't exist)
    if len(upper) <= 20 and upper.isalnum():
        return potential_ticker

    return None


def get_similar_tickers(stock_name: str) -> list[str]:
    """Return a list of similar stock names from the ticker map."""
    name = stock_name.strip().lower()
    suggestions = []

    for key in TICKER_MAP:
        # Check if any word in the search matches any word in the key
        search_words = name.split()
        key_words = key.split()
        if any(sw in key for sw in search_words) or any(kw in name for kw in key_words):
            suggestions.append(key.title())

    # Deduplicate (different names can map to same ticker)
    seen_tickers = set()
    unique_suggestions = []
    for s in suggestions:
        ticker = TICKER_MAP.get(s.lower(), "")
        if ticker not in seen_tickers:
            seen_tickers.add(ticker)
            unique_suggestions.append(s)

    return unique_suggestions[:10]


# ── Helpers ──────────────────────────────────────────────────────

def _format_market_cap(value: Optional[float]) -> Optional[str]:
    """Format market cap into human-readable Indian format."""
    if not value:
        return None
    if value >= 1e12:
        return f"₹{value / 1e12:.2f}L Cr"
    elif value >= 1e10:
        return f"₹{value / 1e10:.2f}K Cr"
    elif value >= 1e7:
        return f"₹{value / 1e7:.2f} Cr"
    else:
        return f"₹{value:,.0f}"


def _calculate_return(hist: pd.DataFrame, days: int) -> Optional[float]:
    """Calculate percentage return over N days from historical data."""
    if hist is None or hist.empty or len(hist) < 2:
        return None
    try:
        current = hist["Close"].iloc[-1]
        if len(hist) >= days:
            past = hist["Close"].iloc[-days]
        else:
            past = hist["Close"].iloc[0]
        if past and past > 0:
            return round(((current - past) / past) * 100, 2)
    except (IndexError, KeyError, TypeError):
        pass
    return None


def _is_data_sufficient(data: dict) -> bool:
    """Check if stock data has enough non-null fields to be useful.

    We consider data sufficient if at least current_price and 2 other
    key fields are present.
    """
    key_fields = [
        "current_price", "pe_ratio", "52_week_high", "52_week_low",
        "market_cap", "eps", "volume",
    ]
    non_null = sum(1 for f in key_fields if data.get(f) is not None)
    return non_null >= 3


def _merge_data(primary: dict, fallback: dict) -> dict:
    """Merge fallback data into primary, filling only null fields."""
    merged = dict(primary)
    for key, value in fallback.items():
        if key.startswith("_"):
            continue  # Skip internal markers
        if merged.get(key) is None and value is not None:
            merged[key] = value
    return merged


# ── yfinance fetcher (opt-in) ────────────────────────────────────

def _fetch_yfinance_sync(ticker: str) -> tuple[dict, pd.DataFrame]:
    """Fetch stock data from yfinance synchronously (runs in thread pool).

    WARNING: This can hang indefinitely behind corporate proxies (Zscaler).
    Only used when STOCK_DATA_SOURCE is 'yfinance' or 'auto'.
    """
    import yfinance as yf

    stock = yf.Ticker(ticker)
    info = stock.info or {}

    # Fetch historical data for return calculations
    try:
        hist = stock.history(period="1y")
    except Exception:
        hist = pd.DataFrame()

    # Calculate returns
    return_1m = _calculate_return(hist, 21)   # ~21 trading days
    return_3m = _calculate_return(hist, 63)   # ~63 trading days
    return_6m = _calculate_return(hist, 126)  # ~126 trading days
    return_1y = _calculate_return(hist, 252)  # ~252 trading days

    # Build stock data dict
    data = {
        "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "market_cap": _format_market_cap(info.get("marketCap")),
        "pe_ratio": info.get("trailingPE") or info.get("forwardPE"),
        "pb_ratio": info.get("priceToBook"),
        "eps": info.get("trailingEps"),
        "dividend_yield": round(info.get("dividendYield", 0) * 100, 2) if info.get("dividendYield") else None,
        "52_week_high": info.get("fiftyTwoWeekHigh"),
        "52_week_low": info.get("fiftyTwoWeekLow"),
        "debt_to_equity": info.get("debtToEquity"),
        "roe": info.get("returnOnEquity"),
        "revenue_growth": round(info.get("revenueGrowth", 0) * 100, 2) if info.get("revenueGrowth") else None,
        "profit_growth": round(info.get("earningsGrowth", 0) * 100, 2) if info.get("earningsGrowth") else None,
        "promoter_holding": info.get("heldPercentInsiders"),
        "1m_return": return_1m,
        "3m_return": return_3m,
        "6m_return": return_6m,
        "1y_return": return_1y,
        "volume": info.get("volume") or info.get("regularMarketVolume"),
        "avg_volume": info.get("averageVolume"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "stock_name": info.get("longName") or info.get("shortName") or ticker,
        "_source": "yfinance",
    }

    return data, hist


async def _fetch_yfinance(ticker: str) -> tuple[dict, pd.DataFrame]:
    """Fetch stock data from yfinance asynchronously.

    WARNING: yfinance can hang behind corporate proxies. This uses
    run_in_executor which cannot kill the underlying thread. Only use
    when STOCK_DATA_SOURCE is 'yfinance' or 'auto'.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_yfinance_sync, ticker)


# ── Main fetch function ──────────────────────────────────────────

async def fetch_stock_data(ticker: str) -> tuple[dict, pd.DataFrame]:
    """
    Fetch comprehensive stock data using the configured data source.

    Strategy depends on STOCK_DATA_SOURCE setting:
      - "google_finance" (default): Google Finance only (fast, proxy-safe)
      - "yfinance": yfinance only (best data, but may hang behind proxies)
      - "auto": Google Finance first, yfinance fallback if insufficient

    Args:
        ticker: NSE ticker symbol (e.g., 'AXISBANK.NS').

    Returns:
        Tuple of (stock_data_dict, historical_dataframe).
        historical_dataframe may be empty when using Google Finance
        (no historical data available from scraping).
    """
    from services.google_finance import fetch_google_finance

    source = settings.STOCK_DATA_SOURCE.lower().strip()
    hist = pd.DataFrame()

    logger.info(f"Fetching stock data for {ticker} (source={source})")

    # ── Strategy: Google Finance only (default) ──────────────────
    if source == "google_finance":
        gf_data = await fetch_google_finance(ticker)
        if gf_data and gf_data.get("current_price") is not None:
            gf_data["_data_source"] = "google_finance"
            logger.info(f"Google Finance: {ticker} price={gf_data['current_price']}")
            return gf_data, hist

        raise RuntimeError(
            f"Google Finance returned no data for {ticker}. "
            f"Check if the ticker is valid or try STOCK_DATA_SOURCE=auto"
        )

    # ── Strategy: yfinance only ──────────────────────────────────
    if source == "yfinance":
        try:
            yf_data, hist = await _fetch_yfinance(ticker)
            if _is_data_sufficient(yf_data):
                yf_data["_data_source"] = "yfinance"
                return yf_data, hist
            logger.warning(f"yfinance returned insufficient data for {ticker}")
            yf_data["_data_source"] = "yfinance_partial"
            return yf_data, hist
        except Exception as e:
            raise RuntimeError(f"yfinance failed for {ticker}: {e}")

    # ── Strategy: auto (Google Finance first, yfinance fallback) ─
    if source == "auto":
        # Step 1: Try Google Finance (fast, reliable behind proxies)
        gf_data = {}
        gf_error = None
        try:
            gf_data = await fetch_google_finance(ticker)
            if gf_data and _is_data_sufficient(gf_data):
                gf_data["_data_source"] = "google_finance"
                logger.info(f"Auto mode: using Google Finance for {ticker}")
                return gf_data, hist
        except Exception as e:
            gf_error = str(e)[:200]
            logger.warning(f"Auto mode: Google Finance failed for {ticker}: {gf_error}")

        # Step 2: Try yfinance as fallback
        yf_data = {}
        yf_error = None
        try:
            yf_data, hist = await _fetch_yfinance(ticker)
            if _is_data_sufficient(yf_data):
                # Merge Google Finance data into yfinance (yfinance is richer)
                if gf_data:
                    merged = _merge_data(yf_data, gf_data)
                    merged["_data_source"] = "yfinance+google_finance"
                    return merged, hist
                yf_data["_data_source"] = "yfinance"
                return yf_data, hist
        except Exception as e:
            yf_error = str(e)[:200]
            logger.warning(f"Auto mode: yfinance also failed for {ticker}: {yf_error}")

        # Step 3: Return whatever partial data we have
        if gf_data and gf_data.get("current_price") is not None:
            gf_data["_data_source"] = "google_finance_partial"
            return gf_data, hist

        if yf_data:
            yf_data["_data_source"] = "yfinance_partial"
            return yf_data, hist

        raise RuntimeError(
            f"Could not fetch data for {ticker}: "
            f"Google Finance: {gf_error or 'no data'}; "
            f"yfinance: {yf_error or 'no data'}"
        )

    # Unknown source
    raise ValueError(
        f"Unknown STOCK_DATA_SOURCE='{source}'. "
        f"Valid options: google_finance, yfinance, auto"
    )
