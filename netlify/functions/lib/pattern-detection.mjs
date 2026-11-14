/**
 * Chart pattern detection — pure JavaScript port of backend/services/technical_analysis.py
 * No numpy/pandas dependencies.
 */

function findPivots(highs, lows, w = 5) {
  const pH = [], pL = [], n = highs.length;
  for (let i = w; i < n - w; i++) {
    let isH = true, isL = true;
    for (let j = i - w; j <= i + w; j++) {
      if (highs[j] > highs[i]) { isH = false; break; }
    }
    for (let j = i - w; j <= i + w; j++) {
      if (lows[j] < lows[i]) { isL = false; break; }
    }
    if (isH) pH.push({ idx: i, price: highs[i] });
    if (isL) pL.push({ idx: i, price: lows[i] });
  }
  return { pH, pL };
}

function linRegSlope(arr) {
  const n = arr.length;
  if (n < 2) return 0;
  let sx = 0, sy = 0, sxy = 0, sxx = 0;
  for (let i = 0; i < n; i++) {
    sx += i; sy += arr[i]; sxy += i * arr[i]; sxx += i * i;
  }
  return (n * sxy - sx * sy) / (n * sxx - sx * sx);
}

function ema(arr, span) {
  const k = 2 / (span + 1);
  let e = arr[0];
  for (let i = 1; i < arr.length; i++) e = arr[i] * k + e * (1 - k);
  return e;
}

function detectDoubleTop(highs, closes, n) {
  const lb = Math.min(60, n), seg = highs.slice(-lb);
  const { pH } = findPivots(seg, seg, 3);
  if (pH.length < 2) return null;
  const a = pH[pH.length - 2], b = pH[pH.length - 1];
  if (Math.abs(a.price - b.price) / a.price >= 0.02 || b.idx <= a.idx + 3) return null;
  let nl = Infinity;
  for (let i = a.idx; i <= b.idx; i++) if (seg[i] < nl) nl = seg[i];
  const cur = closes[closes.length - 1];
  if (cur < a.price && cur > nl * 0.97) {
    return { pattern: "Double Top", type: "bearish", reliability: "high", description: `Two peaks near \u20b9${a.price.toFixed(2)}, neckline \u20b9${nl.toFixed(2)}. Bearish reversal.`, target: Math.round((nl - (a.price - nl)) * 100) / 100, neckline: Math.round(nl * 100) / 100, implication: "Breakdown below neckline targets lower levels." };
  }
  return null;
}

function detectDoubleBottom(lows, closes, n) {
  const lb = Math.min(60, n), seg = lows.slice(-lb);
  const { pL } = findPivots(seg, seg, 3);
  if (pL.length < 2) return null;
  const a = pL[pL.length - 2], b = pL[pL.length - 1];
  if (Math.abs(a.price - b.price) / a.price >= 0.02 || b.idx <= a.idx + 3) return null;
  let nl = -Infinity;
  for (let i = a.idx; i <= b.idx; i++) if (seg[i] > nl) nl = seg[i];
  const cur = closes[closes.length - 1];
  if (cur > a.price && cur < nl * 1.03) {
    return { pattern: "Double Bottom", type: "bullish", reliability: "high", description: `Two troughs near \u20b9${a.price.toFixed(2)}, neckline \u20b9${nl.toFixed(2)}. Bullish reversal.`, target: Math.round((nl + (nl - a.price)) * 100) / 100, neckline: Math.round(nl * 100) / 100, implication: "Breakout above neckline targets higher levels." };
  }
  return null;
}

function detectHS(highs, closes, n) {
  const lb = Math.min(80, n), seg = highs.slice(-lb);
  const { pH } = findPivots(seg, seg, 4);
  if (pH.length < 3) return null;
  const l = pH[pH.length - 3].price, h = pH[pH.length - 2].price, r = pH[pH.length - 1].price;
  const i1 = pH[pH.length - 3].idx, i3 = pH[pH.length - 1].idx;
  if (!(h > l && h > r && Math.abs(l - r) / l < 0.03)) return null;
  let nl = Infinity;
  for (let i = i1; i <= i3; i++) if (seg[i] < nl) nl = seg[i];
  return { pattern: "Head & Shoulders", type: "bearish", reliability: "very high", description: `Head \u20b9${h.toFixed(2)}, shoulders \u20b9${l.toFixed(2)}/\u20b9${r.toFixed(2)}, neckline \u20b9${nl.toFixed(2)}.`, target: Math.round((nl - (h - nl)) * 100) / 100, neckline: Math.round(nl * 100) / 100, implication: "Classic bearish reversal. Break below neckline confirms." };
}

function detectInvHS(lows, closes, n) {
  const lb = Math.min(80, n), seg = lows.slice(-lb);
  const { pL } = findPivots(seg, seg, 4);
  if (pL.length < 3) return null;
  const l = pL[pL.length - 3].price, h = pL[pL.length - 2].price, r = pL[pL.length - 1].price;
  const i1 = pL[pL.length - 3].idx, i3 = pL[pL.length - 1].idx;
  if (!(h < l && h < r && Math.abs(l - r) / l < 0.03)) return null;
  let nl = -Infinity;
  for (let i = i1; i <= i3; i++) if (seg[i] > nl) nl = seg[i];
  return { pattern: "Inverse Head & Shoulders", type: "bullish", reliability: "very high", description: `Head \u20b9${h.toFixed(2)}, shoulders \u20b9${l.toFixed(2)}/\u20b9${r.toFixed(2)}, neckline \u20b9${nl.toFixed(2)}.`, target: Math.round((nl + (nl - h)) * 100) / 100, neckline: Math.round(nl * 100) / 100, implication: "Classic bullish reversal. Break above neckline confirms." };
}

function detectAscTri(highs, lows, n) {
  const lb = Math.min(40, n), sH = highs.slice(-lb), sL = lows.slice(-lb);
  const { pH } = findPivots(sH, sL, 3);
  const { pL } = findPivots(sH, sL, 3);
  if (pH.length < 3 || pL.length < 3) return null;
  const hp = pH.slice(-3).map(p => p.price), lp = pL.slice(-3).map(p => p.price);
  if ((Math.max(...hp) - Math.min(...hp)) / Math.min(...hp) >= 0.015) return null;
  if (!(lp[0] < lp[1] && lp[1] < lp[2])) return null;
  const res = hp.reduce((a, b) => a + b, 0) / hp.length;
  return { pattern: "Ascending Triangle", type: "bullish", reliability: "high", description: `Flat resistance \u20b9${res.toFixed(2)} with rising lows.`, target: Math.round((res + (res - Math.min(...lp))) * 100) / 100, breakout_level: Math.round(res * 100) / 100, implication: "Breakout above resistance confirms bullish move." };
}

function detectDescTri(highs, lows, n) {
  const lb = Math.min(40, n), sH = highs.slice(-lb), sL = lows.slice(-lb);
  const { pH } = findPivots(sH, sL, 3);
  const { pL } = findPivots(sH, sL, 3);
  if (pH.length < 3 || pL.length < 3) return null;
  const lp = pL.slice(-3).map(p => p.price), hp = pH.slice(-3).map(p => p.price);
  if ((Math.max(...lp) - Math.min(...lp)) / Math.min(...lp) >= 0.015) return null;
  if (!(hp[0] > hp[1] && hp[1] > hp[2])) return null;
  const sup = lp.reduce((a, b) => a + b, 0) / lp.length;
  return { pattern: "Descending Triangle", type: "bearish", reliability: "high", description: `Flat support \u20b9${sup.toFixed(2)} with falling highs.`, target: Math.round((sup - (Math.max(...hp) - sup)) * 100) / 100, breakdown_level: Math.round(sup * 100) / 100, implication: "Breakdown below support confirms bearish move." };
}

function detectBullFlag(closes, n) {
  if (n < 25) return null;
  const pm = (closes[n - 10] - closes[n - 25]) / closes[n - 25];
  if (pm <= 0.08) return null;
  const fc = closes.slice(-10);
  const fr = (Math.max(...fc) - Math.min(...fc)) / Math.min(...fc);
  const fd = (fc[fc.length - 1] - fc[0]) / fc[0];
  if (fr >= 0.05 || fd <= -0.05 || fd >= 0.02) return null;
  return { pattern: "Bull Flag", type: "bullish", reliability: "medium-high", description: `Strong up-pole (${(pm * 100).toFixed(1)}%) + tight consolidation.`, target: Math.round((closes[n - 1] + (closes[n - 10] - closes[n - 25])) * 100) / 100, implication: "Bullish continuation on breakout." };
}

function detectBearFlag(closes, n) {
  if (n < 25) return null;
  const pm = (closes[n - 10] - closes[n - 25]) / closes[n - 25];
  if (pm >= -0.08) return null;
  const fc = closes.slice(-10);
  const fr = (Math.max(...fc) - Math.min(...fc)) / Math.min(...fc);
  const fd = (fc[fc.length - 1] - fc[0]) / fc[0];
  if (fr >= 0.05 || fd <= -0.02 || fd >= 0.05) return null;
  return { pattern: "Bear Flag", type: "bearish", reliability: "medium-high", description: `Strong down-pole (${(Math.abs(pm) * 100).toFixed(1)}%) + tight consolidation.`, target: Math.round((closes[n - 1] - Math.abs(closes[n - 10] - closes[n - 25])) * 100) / 100, implication: "Bearish continuation on breakdown." };
}

function detectRisingWedge(highs, lows, n) {
  const lb = Math.min(40, n);
  const hs = linRegSlope(highs.slice(-lb));
  const ls = linRegSlope(lows.slice(-lb));
  if (hs > 0 && ls > 0 && ls > hs * 0.5) {
    return { pattern: "Rising Wedge", type: "bearish", reliability: "medium", description: "Converging rising trendlines. Bearish reversal pattern.", implication: "Breakdown below lower trendline confirms." };
  }
  return null;
}

function detectFallingWedge(highs, lows, n) {
  const lb = Math.min(40, n);
  const hs = linRegSlope(highs.slice(-lb));
  const ls = linRegSlope(lows.slice(-lb));
  if (hs < 0 && ls < 0 && hs > ls * 0.5) {
    return { pattern: "Falling Wedge", type: "bullish", reliability: "medium", description: "Converging falling trendlines. Bullish reversal pattern.", implication: "Breakout above upper trendline confirms." };
  }
  return null;
}

function detectSidewaysRange(highs, lows, closes, n) {
  const lb = Math.min(40, n);
  const sH = highs.slice(-lb), sL = lows.slice(-lb), sC = closes.slice(-lb);
  const rH = Math.max(...sH), rL = Math.min(...sL);
  if (rL <= 0) return null;
  const rPct = (rH - rL) / rL * 100;
  if (rPct > 12) return null;
  const uZone = rH - (rH - rL) * 0.25, lZone = rL + (rH - rL) * 0.25;
  let uT = 0, lT = 0;
  for (const h of sH) if (h >= uZone) uT++;
  for (const l of sL) if (l <= lZone) lT++;
  if (uT < 3 || lT < 3) return null;
  const cur = sC[sC.length - 1], mid = (rH + rL) / 2;
  const pos = cur > mid ? "near upper range" : "near lower range";
  return { pattern: "Sideways Range", type: "sideways", reliability: "medium-high", description: `Stock consolidating in \u20b9${rL.toFixed(2)}\u2013\u20b9${rH.toFixed(2)} range (${rPct.toFixed(1)}% width). Currently ${pos}.`, target: Math.round((cur < mid ? rH : rL) * 100) / 100, implication: "Range-bound. Buy near support, sell near resistance, or wait for breakout." };
}

function detectSymTriangle(highs, lows, closes, n) {
  const lb = Math.min(50, n);
  const sH = highs.slice(-lb), sL = lows.slice(-lb), sC = closes.slice(-lb);
  const pivots = { pH: [], pL: [] };
  for (let i = 3; i < lb - 3; i++) {
    let isH = true, isL = true;
    for (let j = i - 3; j <= i + 3; j++) {
      if (sH[j] > sH[i]) { isH = false; break; }
    }
    for (let j = i - 3; j <= i + 3; j++) {
      if (sL[j] < sL[i]) { isL = false; break; }
    }
    if (isH) pivots.pH.push({ idx: i, price: sH[i] });
    if (isL) pivots.pL.push({ idx: i, price: sL[i] });
  }
  if (pivots.pH.length < 3 || pivots.pL.length < 3) return null;
  const h1 = pivots.pH[pivots.pH.length - 3].price;
  const h2 = pivots.pH[pivots.pH.length - 2].price;
  const h3 = pivots.pH[pivots.pH.length - 1].price;
  const l1 = pivots.pL[pivots.pL.length - 3].price;
  const l2 = pivots.pL[pivots.pL.length - 2].price;
  const l3 = pivots.pL[pivots.pL.length - 1].price;
  if (!(h1 > h2 && h2 > h3)) return null;
  if (!(l1 < l2 && l2 < l3)) return null;
  const initR = h1 - l1, curR = h3 - l3;
  if (initR <= 0 || curR <= 0 || curR / initR > 0.7) return null;
  const apex = (h3 + l3) / 2;
  return { pattern: "Symmetrical Triangle", type: "sideways", reliability: "medium-high", description: `Converging highs (${h1.toFixed(2)}\u2192${h3.toFixed(2)}) and lows (${l1.toFixed(2)}\u2192${l3.toFixed(2)}). Apex near \u20b9${apex.toFixed(2)}.`, target: Math.round((h3 + initR * 0.618) * 100) / 100, implication: "Breakout imminent. Direction uncertain \u2014 trade the breakout with volume confirmation." };
}

function analyzeTrend(closes, n) {
  if (n < 50) return null;
  const e20 = ema(closes, 20), e50 = ema(closes, 50);
  const cur = closes[closes.length - 1];
  const st = cur > e20 ? "bullish" : "bearish";
  const mt = cur > e50 ? "bullish" : "bearish";
  let lt = "N/A";
  if (n >= 200) {
    const e200 = ema(closes, 200);
    lt = cur > e200 ? "bullish" : "bearish";
  }
  let cs = null;
  if (n >= 50) {
    const prev = closes.slice(0, -5);
    const e20p = ema(prev, 20), e50p = ema(prev, 50);
    if (e20p < e50p && e20 > e50) cs = "Golden Cross (20 EMA > 50 EMA) \u2014 Bullish";
    else if (e20p > e50p && e20 < e50) cs = "Death Cross (20 EMA < 50 EMA) \u2014 Bearish";
  }
  let desc = `Short: ${st.toUpperCase()}, Medium: ${mt.toUpperCase()}, Long: ${lt.toUpperCase()}`;
  if (cs) desc += `. Signal: ${cs}`;
  const ov = (st === "bullish" && mt === "bullish") ? "bullish" : (st === "bearish" && mt === "bearish") ? "bearish" : "neutral";
  return { pattern: "Trend Analysis", type: ov, reliability: "high", description: desc, short_trend: st, medium_trend: mt, long_trend: lt, cross_signal: cs, implication: `Overall ${ov.toUpperCase()} trend. Trade with the trend.` };
}

/**
 * Run all pattern detectors on OHLCV arrays.
 * @param {number[]} closes
 * @param {number[]} highs
 * @param {number[]} lows
 * @returns {Array<Object>} detected patterns
 */
export function detectChartPatterns(closes, highs, lows) {
  const n = closes.length;
  if (n < 30) return [];
  const patterns = [];
  const detectors = [
    () => detectDoubleTop(highs, closes, n),
    () => detectDoubleBottom(lows, closes, n),
    () => detectHS(highs, closes, n),
    () => detectInvHS(lows, closes, n),
    () => detectAscTri(highs, lows, n),
    () => detectDescTri(highs, lows, n),
    () => detectBullFlag(closes, n),
    () => detectBearFlag(closes, n),
    () => detectRisingWedge(highs, lows, n),
    () => detectFallingWedge(highs, lows, n),
    () => detectSidewaysRange(highs, lows, closes, n),
    () => detectSymTriangle(highs, lows, closes, n),
    () => analyzeTrend(closes, n),
  ];
  for (const det of detectors) {
    try {
      const r = det();
      if (r) patterns.push(r);
    } catch { /* skip */ }
  }
  return patterns;
}

/**
 * Calculate volatility metrics for a stock given OHLCV arrays.
 * @returns {Object|null} metrics object or null
 */
export function calcVolatileMetrics(closes, highs, lows, volumes, currentPrice) {
  const n = closes.length;
  if (n < 20) return null;

  let price = currentPrice || closes[n - 1];

  // 1-month data (~21 trading days)
  const mLen = Math.min(21, n);
  const mCloses = closes.slice(-mLen);
  const mHighs = highs.slice(-mLen);
  const mLows = lows.slice(-mLen);
  const mVols = volumes.slice(-mLen);

  // Monthly volatility (annualized std dev of daily returns as %)
  const dailyReturns = [];
  for (let i = 1; i < mCloses.length; i++) {
    dailyReturns.push((mCloses[i] - mCloses[i - 1]) / mCloses[i - 1]);
  }
  const mean = dailyReturns.reduce((a, b) => a + b, 0) / dailyReturns.length;
  const variance = dailyReturns.reduce((a, b) => a + (b - mean) ** 2, 0) / dailyReturns.length;
  const monthlyVol = Math.sqrt(variance) * Math.sqrt(21) * 100;

  // ATR % (14-day ATR as % of price)
  const atrPeriod = Math.min(14, n - 1);
  const trValues = [];
  for (let i = n - atrPeriod; i < n; i++) {
    if (i <= 0) continue;
    const hl = highs[i] - lows[i];
    const hpc = Math.abs(highs[i] - closes[i - 1]);
    const lpc = Math.abs(lows[i] - closes[i - 1]);
    trValues.push(Math.max(hl, hpc, lpc));
  }
  const atr = trValues.length > 0 ? trValues.reduce((a, b) => a + b, 0) / trValues.length : 0;
  const atrPct = price > 0 ? (atr / price) * 100 : 0;

  // Volume ratio (5-day avg vs 60-day avg)
  const validVols = volumes.filter(v => v > 0);
  let volumeRatio = 1.0;
  if (validVols.length >= 10) {
    const recent5 = validVols.slice(-5).reduce((a, b) => a + b, 0) / 5;
    const longLen = Math.min(60, validVols.length);
    const long60 = validVols.slice(-longLen).reduce((a, b) => a + b, 0) / longLen;
    volumeRatio = long60 > 0 ? recent5 / long60 : 1.0;
  }

  // Price range % (month high-low / low)
  const monthHigh = Math.max(...mHighs);
  const monthLow = Math.min(...mLows);
  const priceRangePct = monthLow > 0 ? ((monthHigh - monthLow) / monthLow) * 100 : 0;

  // Volume spike days (>2x avg volume in past month)
  const avgVol60Len = Math.min(60, validVols.length);
  const avgVol60 = validVols.length > 0 ? validVols.slice(-avgVol60Len).reduce((a, b) => a + b, 0) / avgVol60Len : 0;
  let volumeSpikeDays = 0;
  if (avgVol60 > 0) {
    for (const v of mVols) {
      if (v > 2 * avgVol60) volumeSpikeDays++;
    }
  }

  // 1-month return
  const oneMReturn = mCloses.length >= 2 ? ((mCloses[mCloses.length - 1] - mCloses[0]) / mCloses[0]) * 100 : 0;

  // Composite volatility score (0-100)
  const volScore = Math.min(100, monthlyVol / 15 * 100) * 0.25;
  const atrScore = Math.min(100, atrPct / 5 * 100) * 0.20;
  const vrScore = Math.min(100, Math.max(0, (volumeRatio - 0.5) / 2.5 * 100)) * 0.25;
  const prScore = Math.min(100, priceRangePct / 25 * 100) * 0.15;
  const vsScore = Math.min(100, volumeSpikeDays / 10 * 100) * 0.15;
  const volatilityScore = volScore + atrScore + vrScore + prScore + vsScore;

  // Tags
  const tags = [];
  if (monthlyVol > 5) tags.push("High Volatility");
  if (volumeRatio > 1.5) tags.push("Volume Surge");
  if (priceRangePct > 10) tags.push("Wide Range");
  if (volumeSpikeDays >= 3) tags.push("Volume Spikes");

  // Average daily volume
  const adv21 = validVols.length >= 21
    ? validVols.slice(-21).reduce((a, b) => a + b, 0) / 21
    : validVols.length > 0
      ? validVols.reduce((a, b) => a + b, 0) / validVols.length
      : 0;

  return {
    price: Math.round(price * 100) / 100,
    volatility_score: Math.round(volatilityScore * 10) / 10,
    monthly_volatility: Math.round(monthlyVol * 10) / 10,
    atr_pct: Math.round(atrPct * 10) / 10,
    volume_ratio: Math.round(volumeRatio * 10) / 10,
    price_range_pct: Math.round(priceRangePct * 10) / 10,
    volume_spike_days: volumeSpikeDays,
    "1m_return": Math.round(oneMReturn * 10) / 10,
    avg_daily_volume: Math.round(adv21),
    tags,
  };
}
