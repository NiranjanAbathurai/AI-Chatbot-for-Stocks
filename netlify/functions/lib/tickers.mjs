/**
 * NSE Ticker resolution map — maps common stock names to NSE ticker symbols.
 */

export const TICKER_MAP = {
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
  "zomato": "ZOMATO.NS",
  "paytm": "PAYTM.NS",
  "nykaa": "NYKAA.NS",
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
  "pnb": "PNB.NS",
  "punjab national bank": "PNB.NS",
  "canara bank": "CANBK.NS",
  "yes bank": "YESBANK.NS",
  "bandhan bank": "BANDHANBNK.NS",
  "federal bank": "FEDERALBNK.NS",
  "idfc first bank": "IDFCFIRSTB.NS",
  "au bank": "AUBANK.NS",
  "pidilite": "PIDILITIND.NS",
  "havells": "HAVELLS.NS",
  "voltas": "VOLTAS.NS",
  "dixon": "DIXON.NS",
  "dmart": "DMART.NS",
  "trent": "TRENT.NS",
  "jubilant food": "JUBLFOOD.NS",
  "dabur": "DABUR.NS",
  "marico": "MARICO.NS",
  "colgate": "COLPAL.NS",
  "biocon": "BIOCON.NS",
  "lupin": "LUPIN.NS",
  "persistent": "PERSISTENT.NS",
  "coforge": "COFORGE.NS",
  "mphasis": "MPHASIS.NS",
  "ltimindtree": "LTIM.NS",
  "adani green": "ADANIGREEN.NS",
  "adani power": "ADANIPOWER.NS",
  "ambuja cements": "AMBUJACEM.NS",
  "ambuja": "AMBUJACEM.NS",
  "acc": "ACC.NS",
  "shree cement": "SHREECEM.NS",
  "srf": "SRF.NS",
  "pi industries": "PIIND.NS",
  "indigo": "INDIGO.NS",
  "irfc": "IRFC.NS",
  "rvnl": "RVNL.NS",
  "nhpc": "NHPC.NS",
  "pfc": "PFC.NS",
  "rec": "RECLTD.NS",
  "angel one": "ANGELONE.NS",
  "cdsl": "CDSL.NS",
  "bse": "BSE.NS",
  "varun beverages": "VBL.NS",
  "vodafone idea": "IDEA.NS",
  "vi": "IDEA.NS",
  "jio financial": "JIOFIN.NS",
  "lic": "LICI.NS",
};

/**
 * Resolve a stock name to its NSE ticker symbol.
 */
export function resolveTicker(stockName) {
  const name = stockName.trim().toLowerCase();

  // Direct match
  if (TICKER_MAP[name]) return TICKER_MAP[name];

  // Already a ticker format
  const upper = stockName.trim().toUpperCase();
  if (upper.endsWith(".NS") || upper.endsWith(".BO")) return upper;

  // Try appending .NS
  const potential = `${upper}.NS`;

  // Partial match
  const matches = Object.entries(TICKER_MAP).filter(
    ([k]) => name.includes(k) || k.includes(name)
  );
  if (matches.length === 1) return matches[0][1];

  // Return potential ticker (yahoo-finance2 will validate)
  return potential;
}

/**
 * Get similar ticker suggestions.
 */
export function getSimilarTickers(stockName) {
  const name = stockName.trim().toLowerCase();
  const suggestions = [];
  const seenTickers = new Set();

  for (const [key, ticker] of Object.entries(TICKER_MAP)) {
    const searchWords = name.split(" ");
    if (
      searchWords.some((w) => key.includes(w)) ||
      key.split(" ").some((w) => name.includes(w))
    ) {
      if (!seenTickers.has(ticker)) {
        seenTickers.add(ticker);
        suggestions.push(key.replace(/\b\w/g, (c) => c.toUpperCase()));
      }
    }
  }

  return suggestions.slice(0, 10);
}
