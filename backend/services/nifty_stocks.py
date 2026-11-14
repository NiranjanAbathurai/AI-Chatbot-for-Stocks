"""NSE stock lists — dynamically fetched from NSE India APIs with caching.

Fetches live index constituents from NSE India for:
  - NIFTY 50, NIFTY Next 50, NIFTY Midcap 50, NIFTY Bank, NIFTY IT,
    NIFTY Pharma, NIFTY Auto, NIFTY FMCG, NIFTY Metal, NIFTY Energy,
    NIFTY Infra, NIFTY Realty, NIFTY PSE, NIFTY Media, etc.

Falls back to a hardcoded list if the API is unreachable.
Results are cached for 6 hours to avoid hammering the NSE API.
"""

import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ── Cache ───────────────────────────────────────────────────────
_cache: dict = {
    "stocks": [],
    "categories": [],
    "timestamp": 0,
}
CACHE_TTL_SECONDS = 6 * 60 * 60  # 6 hours

# ── NSE Index endpoints ─────────────────────────────────────────
# Each tuple: (NSE index API name, display category)
NSE_INDICES = [
    ("NIFTY 50", "Nifty 50"),
    ("NIFTY NEXT 50", "Nifty Next 50"),
    ("NIFTY MIDCAP 50", "Nifty Midcap 50"),
    ("NIFTY BANK", "Banking"),
    ("NIFTY IT", "IT"),
    ("NIFTY PHARMA", "Pharma"),
    ("NIFTY AUTO", "Auto"),
    ("NIFTY FMCG", "FMCG"),
    ("NIFTY METAL", "Metals"),
    ("NIFTY ENERGY", "Energy"),
    ("NIFTY INFRA", "Infrastructure"),
    ("NIFTY REALTY", "Realty"),
    ("NIFTY PSE", "PSU"),
    ("NIFTY MEDIA", "Media"),
    ("NIFTY FINANCIAL SERVICES", "Finance"),
    ("NIFTY CONSUMER DURABLES", "Consumer Durables"),
    ("NIFTY OIL & GAS", "Oil & Gas"),
    ("NIFTY HEALTHCARE INDEX", "Healthcare"),
]

NSE_BASE_URL = "https://www.nseindia.com"
NSE_INDEX_API = "https://www.nseindia.com/api/equity-stockIndices"

# Headers to mimic a browser (NSE blocks non-browser requests)
NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/",
    "Connection": "keep-alive",
}


async def _fetch_nse_index(client: httpx.AsyncClient, index_name: str) -> list[dict]:
    """Fetch constituents of a single NSE index.

    Returns list of {symbol, companyName} dicts.
    """
    try:
        resp = await client.get(
            NSE_INDEX_API,
            params={"index": index_name},
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
        stocks = data.get("data", [])
        return [
            {
                "symbol": s.get("symbol", ""),
                "name": s.get("meta", {}).get("companyName", "") or s.get("symbol", ""),
            }
            for s in stocks
            if s.get("symbol") and s.get("symbol") != index_name
        ]
    except Exception as e:
        logger.warning(f"NSE API failed for index '{index_name}': {e}")
        return []


async def fetch_nse_stocks() -> list[dict]:
    """Fetch all NSE stocks from multiple index APIs.

    Returns a deduplicated list of:
      [{"name": "Reliance Industries", "ticker": "RELIANCE.NS", "category": "Nifty 50"}, ...]

    Each stock gets the category of the *first* index it appears in
    (priority order matches NSE_INDICES).
    """
    all_stocks: list[dict] = []
    seen_symbols: set[str] = set()

    try:
        async with httpx.AsyncClient(
            headers=NSE_HEADERS,
            follow_redirects=True,
            verify=False,  # NSE cert can be problematic behind proxies
        ) as client:
            # First hit the main page to get cookies (NSE requires this)
            try:
                await client.get(NSE_BASE_URL, timeout=10.0)
            except Exception:
                pass  # Cookie fetch failed, try anyway

            for index_name, category in NSE_INDICES:
                constituents = await _fetch_nse_index(client, index_name)
                for stock in constituents:
                    symbol = stock["symbol"]
                    if symbol not in seen_symbols:
                        seen_symbols.add(symbol)
                        all_stocks.append({
                            "name": _clean_company_name(stock["name"]),
                            "ticker": f"{symbol}.NS",
                            "category": category,
                        })

        logger.info(f"NSE API: fetched {len(all_stocks)} unique stocks from {len(NSE_INDICES)} indices")

    except Exception as e:
        logger.error(f"NSE API fetch failed entirely: {e}")

    return all_stocks


def _clean_company_name(name: str) -> str:
    """Clean up company names from NSE (remove 'Limited', etc.)."""
    if not name:
        return name
    # Remove common suffixes for cleaner display
    for suffix in [" Limited", " Ltd.", " Ltd", " Industries"]:
        if name.endswith(suffix) and len(name) > len(suffix) + 3:
            name = name[: -len(suffix)]
    return name.strip()


# ── Public API ──────────────────────────────────────────────────

async def get_all_stocks() -> list[dict]:
    """Return the full categorized stock list (cached, auto-refreshes).

    Returns list of {"name", "ticker", "category"} dicts.
    Falls back to hardcoded list if NSE API is unreachable.
    """
    now = time.time()

    # Return cached data if fresh
    if _cache["stocks"] and (now - _cache["timestamp"]) < CACHE_TTL_SECONDS:
        return _cache["stocks"]

    # Try fetching from NSE
    stocks = await fetch_nse_stocks()

    if stocks:
        # Add indices manually (they're not in constituent lists)
        stocks.extend([
            {"name": "Nifty 50", "ticker": "^NSEI", "category": "Index"},
            {"name": "Sensex", "ticker": "^BSESN", "category": "Index"},
            {"name": "Bank Nifty", "ticker": "^NSEBANK", "category": "Index"},
        ])
        # Sort by name within each category
        stocks.sort(key=lambda s: (s["category"], s["name"]))
        _cache["stocks"] = stocks
        _cache["categories"] = sorted(set(s["category"] for s in stocks))
        _cache["timestamp"] = now
        return stocks

    # Fallback to hardcoded list
    logger.warning("Using hardcoded stock list (NSE API unavailable)")
    fallback = _get_fallback_stocks()
    _cache["stocks"] = fallback
    _cache["categories"] = sorted(set(s["category"] for s in fallback))
    _cache["timestamp"] = now
    return fallback


async def get_stock_categories() -> list[str]:
    """Return sorted list of unique categories."""
    stocks = await get_all_stocks()
    return sorted(set(s["category"] for s in stocks))


async def search_stocks(query: str) -> list[dict]:
    """Search stocks by name or ticker (case-insensitive partial match)."""
    stocks = await get_all_stocks()
    q = query.strip().lower()
    if not q:
        return stocks
    return [
        s for s in stocks
        if q in s["name"].lower() or q in s["ticker"].lower()
    ]


# ── Legacy compatibility ────────────────────────────────────────

# Synchronous fallback for screener and other sync code
NIFTY_50: list[dict] = [
    {"name": "Adani Enterprises", "ticker": "ADANIENT.NS"},
    {"name": "Adani Ports", "ticker": "ADANIPORTS.NS"},
    {"name": "Apollo Hospitals", "ticker": "APOLLOHOSP.NS"},
    {"name": "Asian Paints", "ticker": "ASIANPAINT.NS"},
    {"name": "Axis Bank", "ticker": "AXISBANK.NS"},
    {"name": "Bajaj Auto", "ticker": "BAJAJ-AUTO.NS"},
    {"name": "Bajaj Finance", "ticker": "BAJFINANCE.NS"},
    {"name": "Bajaj Finserv", "ticker": "BAJAJFINSV.NS"},
    {"name": "Bharti Airtel", "ticker": "BHARTIARTL.NS"},
    {"name": "BPCL", "ticker": "BPCL.NS"},
    {"name": "Britannia", "ticker": "BRITANNIA.NS"},
    {"name": "Cipla", "ticker": "CIPLA.NS"},
    {"name": "Coal India", "ticker": "COALINDIA.NS"},
    {"name": "Divis Lab", "ticker": "DIVISLAB.NS"},
    {"name": "Dr Reddys", "ticker": "DRREDDY.NS"},
    {"name": "Eicher Motors", "ticker": "EICHERMOT.NS"},
    {"name": "Grasim", "ticker": "GRASIM.NS"},
    {"name": "HCL Tech", "ticker": "HCLTECH.NS"},
    {"name": "HDFC Bank", "ticker": "HDFCBANK.NS"},
    {"name": "HDFC Life", "ticker": "HDFCLIFE.NS"},
    {"name": "Hero MotoCorp", "ticker": "HEROMOTOCO.NS"},
    {"name": "Hindalco", "ticker": "HINDALCO.NS"},
    {"name": "Hindustan Unilever", "ticker": "HINDUNILVR.NS"},
    {"name": "ICICI Bank", "ticker": "ICICIBANK.NS"},
    {"name": "IndusInd Bank", "ticker": "INDUSINDBK.NS"},
    {"name": "Infosys", "ticker": "INFY.NS"},
    {"name": "ITC", "ticker": "ITC.NS"},
    {"name": "JSW Steel", "ticker": "JSWSTEEL.NS"},
    {"name": "Kotak Bank", "ticker": "KOTAKBANK.NS"},
    {"name": "L&T", "ticker": "LT.NS"},
    {"name": "M&M", "ticker": "M&M.NS"},
    {"name": "Maruti Suzuki", "ticker": "MARUTI.NS"},
    {"name": "Nestle India", "ticker": "NESTLEIND.NS"},
    {"name": "NTPC", "ticker": "NTPC.NS"},
    {"name": "ONGC", "ticker": "ONGC.NS"},
    {"name": "Power Grid", "ticker": "POWERGRID.NS"},
    {"name": "Reliance", "ticker": "RELIANCE.NS"},
    {"name": "SBI", "ticker": "SBIN.NS"},
    {"name": "SBI Life", "ticker": "SBILIFE.NS"},
    {"name": "Sun Pharma", "ticker": "SUNPHARMA.NS"},
    {"name": "Tata Consumer", "ticker": "TATACONSUM.NS"},
    {"name": "Tata Motors", "ticker": "TATAMOTORS.NS"},
    {"name": "Tata Steel", "ticker": "TATASTEEL.NS"},
    {"name": "TCS", "ticker": "TCS.NS"},
    {"name": "Tech Mahindra", "ticker": "TECHM.NS"},
    {"name": "Titan", "ticker": "TITAN.NS"},
    {"name": "UltraTech Cement", "ticker": "ULTRACEMCO.NS"},
    {"name": "UPL", "ticker": "UPL.NS"},
    {"name": "Wipro", "ticker": "WIPRO.NS"},
]


def get_nifty50_tickers() -> list[str]:
    """Return list of NIFTY 50 ticker symbols."""
    return [s["ticker"] for s in NIFTY_50]


def get_nifty50_stocks() -> list[dict]:
    """Return full NIFTY 50 stock list with names and tickers."""
    return NIFTY_50


# ── Hardcoded Fallback ──────────────────────────────────────────

def _get_fallback_stocks() -> list[dict]:
    """Hardcoded stock list used when NSE API is unreachable."""
    return [
        # Banking
        {"name": "HDFC Bank", "ticker": "HDFCBANK.NS", "category": "Banking"},
        {"name": "ICICI Bank", "ticker": "ICICIBANK.NS", "category": "Banking"},
        {"name": "Axis Bank", "ticker": "AXISBANK.NS", "category": "Banking"},
        {"name": "Kotak Bank", "ticker": "KOTAKBANK.NS", "category": "Banking"},
        {"name": "SBI", "ticker": "SBIN.NS", "category": "Banking"},
        {"name": "IndusInd Bank", "ticker": "INDUSINDBK.NS", "category": "Banking"},
        {"name": "Bank of Baroda", "ticker": "BANKBARODA.NS", "category": "Banking"},
        {"name": "PNB", "ticker": "PNB.NS", "category": "Banking"},
        {"name": "Canara Bank", "ticker": "CANBK.NS", "category": "Banking"},
        {"name": "Federal Bank", "ticker": "FEDERALBNK.NS", "category": "Banking"},
        {"name": "IDFC First Bank", "ticker": "IDFCFIRSTB.NS", "category": "Banking"},
        {"name": "AU Small Finance Bank", "ticker": "AUBANK.NS", "category": "Banking"},
        {"name": "Bandhan Bank", "ticker": "BANDHANBNK.NS", "category": "Banking"},
        {"name": "Yes Bank", "ticker": "YESBANK.NS", "category": "Banking"},
        # Finance
        {"name": "Bajaj Finance", "ticker": "BAJFINANCE.NS", "category": "Finance"},
        {"name": "Bajaj Finserv", "ticker": "BAJAJFINSV.NS", "category": "Finance"},
        {"name": "HDFC Life", "ticker": "HDFCLIFE.NS", "category": "Finance"},
        {"name": "SBI Life", "ticker": "SBILIFE.NS", "category": "Finance"},
        {"name": "HDFC AMC", "ticker": "HDFCAMC.NS", "category": "Finance"},
        {"name": "SBI Cards", "ticker": "SBICARD.NS", "category": "Finance"},
        {"name": "Muthoot Finance", "ticker": "MUTHOOTFIN.NS", "category": "Finance"},
        {"name": "Shriram Finance", "ticker": "SHRIRAMFIN.NS", "category": "Finance"},
        {"name": "Cholamandalam", "ticker": "CHOLAFIN.NS", "category": "Finance"},
        {"name": "Jio Financial", "ticker": "JIOFIN.NS", "category": "Finance"},
        {"name": "LIC", "ticker": "LICI.NS", "category": "Finance"},
        {"name": "Angel One", "ticker": "ANGELONE.NS", "category": "Finance"},
        # IT
        {"name": "TCS", "ticker": "TCS.NS", "category": "IT"},
        {"name": "Infosys", "ticker": "INFY.NS", "category": "IT"},
        {"name": "HCL Tech", "ticker": "HCLTECH.NS", "category": "IT"},
        {"name": "Wipro", "ticker": "WIPRO.NS", "category": "IT"},
        {"name": "Tech Mahindra", "ticker": "TECHM.NS", "category": "IT"},
        {"name": "LTIMindtree", "ticker": "LTIM.NS", "category": "IT"},
        {"name": "Persistent Systems", "ticker": "PERSISTENT.NS", "category": "IT"},
        {"name": "Coforge", "ticker": "COFORGE.NS", "category": "IT"},
        {"name": "Mphasis", "ticker": "MPHASIS.NS", "category": "IT"},
        {"name": "Tata Elxsi", "ticker": "TATAELXSI.NS", "category": "IT"},
        # Oil & Gas / Energy
        {"name": "Reliance", "ticker": "RELIANCE.NS", "category": "Energy"},
        {"name": "ONGC", "ticker": "ONGC.NS", "category": "Energy"},
        {"name": "BPCL", "ticker": "BPCL.NS", "category": "Energy"},
        {"name": "Indian Oil", "ticker": "IOC.NS", "category": "Energy"},
        {"name": "GAIL", "ticker": "GAIL.NS", "category": "Energy"},
        {"name": "NTPC", "ticker": "NTPC.NS", "category": "Energy"},
        {"name": "Power Grid", "ticker": "POWERGRID.NS", "category": "Energy"},
        {"name": "Coal India", "ticker": "COALINDIA.NS", "category": "Energy"},
        {"name": "Tata Power", "ticker": "TATAPOWER.NS", "category": "Energy"},
        {"name": "Adani Green", "ticker": "ADANIGREEN.NS", "category": "Energy"},
        {"name": "Adani Power", "ticker": "ADANIPOWER.NS", "category": "Energy"},
        {"name": "NHPC", "ticker": "NHPC.NS", "category": "Energy"},
        {"name": "PFC", "ticker": "PFC.NS", "category": "Energy"},
        {"name": "REC", "ticker": "RECLTD.NS", "category": "Energy"},
        # Auto
        {"name": "Bajaj Auto", "ticker": "BAJAJ-AUTO.NS", "category": "Auto"},
        {"name": "Eicher Motors", "ticker": "EICHERMOT.NS", "category": "Auto"},
        {"name": "Hero MotoCorp", "ticker": "HEROMOTOCO.NS", "category": "Auto"},
        {"name": "M&M", "ticker": "M&M.NS", "category": "Auto"},
        {"name": "Maruti Suzuki", "ticker": "MARUTI.NS", "category": "Auto"},
        {"name": "Tata Motors", "ticker": "TATAMOTORS.NS", "category": "Auto"},
        # Pharma
        {"name": "Sun Pharma", "ticker": "SUNPHARMA.NS", "category": "Pharma"},
        {"name": "Cipla", "ticker": "CIPLA.NS", "category": "Pharma"},
        {"name": "Dr Reddys", "ticker": "DRREDDY.NS", "category": "Pharma"},
        {"name": "Divis Lab", "ticker": "DIVISLAB.NS", "category": "Pharma"},
        {"name": "Lupin", "ticker": "LUPIN.NS", "category": "Pharma"},
        {"name": "Biocon", "ticker": "BIOCON.NS", "category": "Pharma"},
        {"name": "Aurobindo Pharma", "ticker": "AUROPHARMA.NS", "category": "Pharma"},
        {"name": "Torrent Pharma", "ticker": "TORNTPHARM.NS", "category": "Pharma"},
        {"name": "Apollo Hospitals", "ticker": "APOLLOHOSP.NS", "category": "Healthcare"},
        # FMCG
        {"name": "Hindustan Unilever", "ticker": "HINDUNILVR.NS", "category": "FMCG"},
        {"name": "ITC", "ticker": "ITC.NS", "category": "FMCG"},
        {"name": "Nestle India", "ticker": "NESTLEIND.NS", "category": "FMCG"},
        {"name": "Britannia", "ticker": "BRITANNIA.NS", "category": "FMCG"},
        {"name": "Tata Consumer", "ticker": "TATACONSUM.NS", "category": "FMCG"},
        {"name": "Dabur", "ticker": "DABUR.NS", "category": "FMCG"},
        {"name": "Marico", "ticker": "MARICO.NS", "category": "FMCG"},
        {"name": "Godrej Consumer", "ticker": "GODREJCP.NS", "category": "FMCG"},
        {"name": "Colgate Palmolive", "ticker": "COLPAL.NS", "category": "FMCG"},
        # Metals
        {"name": "Tata Steel", "ticker": "TATASTEEL.NS", "category": "Metals"},
        {"name": "JSW Steel", "ticker": "JSWSTEEL.NS", "category": "Metals"},
        {"name": "Hindalco", "ticker": "HINDALCO.NS", "category": "Metals"},
        {"name": "Vedanta", "ticker": "VEDL.NS", "category": "Metals"},
        {"name": "SAIL", "ticker": "SAIL.NS", "category": "Metals"},
        # Infrastructure
        {"name": "L&T", "ticker": "LT.NS", "category": "Infrastructure"},
        {"name": "Adani Enterprises", "ticker": "ADANIENT.NS", "category": "Infrastructure"},
        {"name": "Adani Ports", "ticker": "ADANIPORTS.NS", "category": "Infrastructure"},
        {"name": "IRCTC", "ticker": "IRCTC.NS", "category": "Infrastructure"},
        {"name": "IRFC", "ticker": "IRFC.NS", "category": "Infrastructure"},
        {"name": "RVNL", "ticker": "RVNL.NS", "category": "Infrastructure"},
        # Cement
        {"name": "UltraTech Cement", "ticker": "ULTRACEMCO.NS", "category": "Cement"},
        {"name": "Grasim", "ticker": "GRASIM.NS", "category": "Cement"},
        {"name": "Ambuja Cements", "ticker": "AMBUJACEM.NS", "category": "Cement"},
        {"name": "ACC", "ticker": "ACC.NS", "category": "Cement"},
        {"name": "Shree Cement", "ticker": "SHREECEM.NS", "category": "Cement"},
        # Consumer Durables
        {"name": "Titan", "ticker": "TITAN.NS", "category": "Consumer Durables"},
        {"name": "Asian Paints", "ticker": "ASIANPAINT.NS", "category": "Consumer Durables"},
        {"name": "Pidilite", "ticker": "PIDILITIND.NS", "category": "Consumer Durables"},
        {"name": "Havells", "ticker": "HAVELLS.NS", "category": "Consumer Durables"},
        {"name": "Dixon Technologies", "ticker": "DIXON.NS", "category": "Consumer Durables"},
        {"name": "Voltas", "ticker": "VOLTAS.NS", "category": "Consumer Durables"},
        # Telecom
        {"name": "Bharti Airtel", "ticker": "BHARTIARTL.NS", "category": "Telecom"},
        {"name": "Vodafone Idea", "ticker": "IDEA.NS", "category": "Telecom"},
        {"name": "Tata Communications", "ticker": "TATACOMM.NS", "category": "Telecom"},
        # Chemicals
        {"name": "UPL", "ticker": "UPL.NS", "category": "Chemicals"},
        {"name": "SRF", "ticker": "SRF.NS", "category": "Chemicals"},
        {"name": "PI Industries", "ticker": "PIIND.NS", "category": "Chemicals"},
        {"name": "Deepak Nitrite", "ticker": "DEEPAKNTR.NS", "category": "Chemicals"},
        {"name": "Tata Chemicals", "ticker": "TATACHEM.NS", "category": "Chemicals"},
        # Defence
        {"name": "HAL", "ticker": "HAL.NS", "category": "Defence"},
        {"name": "BHEL", "ticker": "BHEL.NS", "category": "Defence"},
        # New-Age Tech
        {"name": "Zomato", "ticker": "ZOMATO.NS", "category": "New-Age Tech"},
        {"name": "Paytm", "ticker": "PAYTM.NS", "category": "New-Age Tech"},
        {"name": "Nykaa", "ticker": "NYKAA.NS", "category": "New-Age Tech"},
        {"name": "PolicyBazaar", "ticker": "POLICYBZR.NS", "category": "New-Age Tech"},
        {"name": "Delhivery", "ticker": "DELHIVERY.NS", "category": "New-Age Tech"},
        # Retail
        {"name": "DMart", "ticker": "DMART.NS", "category": "Retail"},
        {"name": "Trent", "ticker": "TRENT.NS", "category": "Retail"},
        # Hospitality & Aviation
        {"name": "Indian Hotels", "ticker": "INDHOTEL.NS", "category": "Hospitality"},
        {"name": "IndiGo", "ticker": "INDIGO.NS", "category": "Aviation"},
        {"name": "SpiceJet", "ticker": "SPICEJET.NS", "category": "Aviation"},
        # Index
        {"name": "Nifty 50", "ticker": "^NSEI", "category": "Index"},
        {"name": "Sensex", "ticker": "^BSESN", "category": "Index"},
        {"name": "Bank Nifty", "ticker": "^NSEBANK", "category": "Index"},
    ]
