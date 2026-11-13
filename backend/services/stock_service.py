"""Stock data service: ticker resolution + yfinance data fetching."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

import yfinance as yf
import pandas as pd

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

    # Try yfinance search as last resort
    try:
        ticker = yf.Ticker(potential_ticker)
        info = ticker.info
        if info and info.get("regularMarketPrice"):
            return potential_ticker
    except Exception:
        pass

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


async def fetch_stock_data(ticker: str) -> dict:
    """
    Fetch comprehensive stock data from yfinance.

    Args:
        ticker: NSE ticker symbol (e.g., 'AXISBANK.NS').

    Returns:
        Dictionary with stock data fields.
    """
    loop = asyncio.get_event_loop()

    def _fetch():
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
        }

        return data, hist

    try:
        data, hist = await loop.run_in_executor(None, _fetch)
        return data, hist
    except Exception as e:
        logger.error(f"Error fetching stock data for {ticker}: {e}")
        raise RuntimeError(f"Could not fetch data for {ticker}: {str(e)}")
