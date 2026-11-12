/**
 * NIFTY 50 stock list for screening.
 */

export const NIFTY_50 = [
  { name: "Adani Enterprises", ticker: "ADANIENT.NS" },
  { name: "Adani Ports", ticker: "ADANIPORTS.NS" },
  { name: "Apollo Hospitals", ticker: "APOLLOHOSP.NS" },
  { name: "Asian Paints", ticker: "ASIANPAINT.NS" },
  { name: "Axis Bank", ticker: "AXISBANK.NS" },
  { name: "Bajaj Auto", ticker: "BAJAJ-AUTO.NS" },
  { name: "Bajaj Finance", ticker: "BAJFINANCE.NS" },
  { name: "Bajaj Finserv", ticker: "BAJAJFINSV.NS" },
  { name: "Bharti Airtel", ticker: "BHARTIARTL.NS" },
  { name: "BPCL", ticker: "BPCL.NS" },
  { name: "Britannia", ticker: "BRITANNIA.NS" },
  { name: "Cipla", ticker: "CIPLA.NS" },
  { name: "Coal India", ticker: "COALINDIA.NS" },
  { name: "Divis Lab", ticker: "DIVISLAB.NS" },
  { name: "Dr Reddys", ticker: "DRREDDY.NS" },
  { name: "Eicher Motors", ticker: "EICHERMOT.NS" },
  { name: "Grasim", ticker: "GRASIM.NS" },
  { name: "HCL Tech", ticker: "HCLTECH.NS" },
  { name: "HDFC Bank", ticker: "HDFCBANK.NS" },
  { name: "HDFC Life", ticker: "HDFCLIFE.NS" },
  { name: "Hero MotoCorp", ticker: "HEROMOTOCO.NS" },
  { name: "Hindalco", ticker: "HINDALCO.NS" },
  { name: "Hindustan Unilever", ticker: "HINDUNILVR.NS" },
  { name: "ICICI Bank", ticker: "ICICIBANK.NS" },
  { name: "IndusInd Bank", ticker: "INDUSINDBK.NS" },
  { name: "Infosys", ticker: "INFY.NS" },
  { name: "ITC", ticker: "ITC.NS" },
  { name: "JSW Steel", ticker: "JSWSTEEL.NS" },
  { name: "Kotak Bank", ticker: "KOTAKBANK.NS" },
  { name: "L&T", ticker: "LT.NS" },
  { name: "M&M", ticker: "M&M.NS" },
  { name: "Maruti Suzuki", ticker: "MARUTI.NS" },
  { name: "Nestle India", ticker: "NESTLEIND.NS" },
  { name: "NTPC", ticker: "NTPC.NS" },
  { name: "ONGC", ticker: "ONGC.NS" },
  { name: "Power Grid", ticker: "POWERGRID.NS" },
  { name: "Reliance", ticker: "RELIANCE.NS" },
  { name: "SBI", ticker: "SBIN.NS" },
  { name: "SBI Life", ticker: "SBILIFE.NS" },
  { name: "Sun Pharma", ticker: "SUNPHARMA.NS" },
  { name: "Tata Consumer", ticker: "TATACONSUM.NS" },
  { name: "Tata Motors", ticker: "TATAMOTORS.NS" },
  { name: "Tata Steel", ticker: "TATASTEEL.NS" },
  { name: "TCS", ticker: "TCS.NS" },
  { name: "Tech Mahindra", ticker: "TECHM.NS" },
  { name: "Titan", ticker: "TITAN.NS" },
  { name: "UltraTech Cement", ticker: "ULTRACEMCO.NS" },
  { name: "UPL", ticker: "UPL.NS" },
  { name: "Wipro", ticker: "WIPRO.NS" },
];

export function getNifty50Tickers() {
  return NIFTY_50.map((s) => s.ticker);
}

export function getNifty50Stocks() {
  return NIFTY_50;
}
