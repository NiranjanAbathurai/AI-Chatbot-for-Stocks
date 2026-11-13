"""Technical Analysis: S/R, Chart Patterns, Swing Indicators."""
import logging
from typing import Optional
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

def _find_pivot_points(df: pd.DataFrame, window: int = 5):
    highs, lows = [], []
    h, l = df["High"].values, df["Low"].values
    for i in range(window, len(df) - window):
        if h[i] == max(h[i-window:i+window+1]):
            highs.append((i, float(h[i])))
        if l[i] == min(l[i-window:i+window+1]):
            lows.append((i, float(l[i])))
    return highs, lows

def _cluster_levels(levels, threshold_pct=1.5):
    if not levels:
        return []
    s = sorted(levels)
    clusters, cur = [], [s[0]]
    for i in range(1, len(s)):
        if s[i] <= cur[-1] * (1 + threshold_pct/100):
            cur.append(s[i])
        else:
            avg = sum(cur)/len(cur)
            clusters.append({"price": round(avg,2), "strength": len(cur), "zone_low": round(min(cur),2), "zone_high": round(max(cur),2)})
            cur = [s[i]]
    if cur:
        avg = sum(cur)/len(cur)
        clusters.append({"price": round(avg,2), "strength": len(cur), "zone_low": round(min(cur),2), "zone_high": round(max(cur),2)})
    return clusters

def calculate_support_resistance(df: pd.DataFrame, current_price: float) -> dict:
    result = {"support_levels": [], "resistance_levels": [], "fibonacci": {}, "moving_averages": {}, "pivot_classic": {}, "key_levels_summary": []}
    if df is None or df.empty or len(df) < 20:
        return result
    try:
        close, high, low = df["Close"].values, df["High"].values, df["Low"].values
        volume = df["Volume"].values if "Volume" in df.columns else None
        res_prices, sup_prices = [], []
        for w in [3, 5, 8, 13]:
            ph, pl = _find_pivot_points(df, window=w)
            for _, p in ph:
                (res_prices if p > current_price else sup_prices).append(p)
            for _, p in pl:
                (sup_prices if p < current_price else res_prices).append(p)
        if volume is not None and len(volume) > 0:
            pr = max(close) - min(close)
            if pr > 0:
                nb = min(50, max(10, len(df)//5))
                edges = np.linspace(min(close), max(close), nb+1)
                vp = np.zeros(nb)
                for i in range(len(close)):
                    bi = min(int((close[i]-min(close))/pr*nb), nb-1)
                    vp[bi] += volume[i]
                th = np.percentile(vp, 80)
                for idx in range(nb):
                    if vp[idx] >= th:
                        lp = (edges[idx]+edges[idx+1])/2
                        (res_prices if lp > current_price else sup_prices).append(float(lp))
        sc = _cluster_levels(sup_prices, 1.5)
        rc = _cluster_levels(res_prices, 1.5)
        sc.sort(key=lambda x: x["price"], reverse=True)
        rc.sort(key=lambda x: x["price"])
        result["support_levels"] = sc[:6]
        result["resistance_levels"] = rc[:6]
        lb = min(len(df), 126)
        rec = df.iloc[-lb:]
        sh, sl = float(rec["High"].max()), float(rec["Low"].min())
        fr = sh - sl
        if fr > 0:
            result["fibonacci"] = {"swing_high": round(sh,2), "swing_low": round(sl,2), "level_0": round(sh,2), "level_236": round(sh-0.236*fr,2), "level_382": round(sh-0.382*fr,2), "level_500": round(sh-0.5*fr,2), "level_618": round(sh-0.618*fr,2), "level_786": round(sh-0.786*fr,2), "level_100": round(sl,2)}
        for p in [20, 50, 100, 200]:
            if len(close) >= p:
                result["moving_averages"][f"ema_{p}"] = round(float(pd.Series(close).ewm(span=p, adjust=False).mean().iloc[-1]), 2)
                result["moving_averages"][f"sma_{p}"] = round(float(pd.Series(close).rolling(window=p).mean().iloc[-1]), 2)
        if len(df) >= 2:
            ph2, pl2, pc2 = float(high[-2]), float(low[-2]), float(close[-2])
            pv = (ph2+pl2+pc2)/3
            result["pivot_classic"] = {"pivot": round(pv,2), "r1": round(2*pv-pl2,2), "r2": round(pv+(ph2-pl2),2), "r3": round(ph2+2*(pv-pl2),2), "s1": round(2*pv-ph2,2), "s2": round(pv-(ph2-pl2),2), "s3": round(pl2-2*(ph2-pv),2)}
        kl = []
        for s in result["support_levels"][:3]:
            pa = round(((current_price-s["price"])/current_price)*100, 1)
            kl.append({"type": "Support", "price": s["price"], "zone": f"\u20b9{s['zone_low']} - \u20b9{s['zone_high']}", "strength": s["strength"], "pct_from_cmp": f"-{pa}%"})
        for r in result["resistance_levels"][:3]:
            pa = round(((r["price"]-current_price)/current_price)*100, 1)
            kl.append({"type": "Resistance", "price": r["price"], "zone": f"\u20b9{r['zone_low']} - \u20b9{r['zone_high']}", "strength": r["strength"], "pct_from_cmp": f"+{pa}%"})
        result["key_levels_summary"] = kl
    except Exception as e:
        logger.error(f"Error calculating S/R levels: {e}")
    return result

def detect_chart_patterns(df: pd.DataFrame) -> list[dict]:
    patterns = []
    if df is None or df.empty or len(df) < 30:
        return patterns
    try:
        close, high, low = df["Close"].values, df["High"].values, df["Low"].values
        n = len(close)
        detectors = [
            lambda: _detect_double_top(high, close, n), lambda: _detect_double_bottom(low, close, n),
            lambda: _detect_head_shoulders(high, close, n), lambda: _detect_inv_hs(low, close, n),
            lambda: _detect_asc_tri(high, low, close, n), lambda: _detect_desc_tri(high, low, close, n),
            lambda: _detect_bull_flag(close, n), lambda: _detect_bear_flag(close, n),
            lambda: _detect_rising_wedge(high, low, n), lambda: _detect_falling_wedge(high, low, n),
            lambda: _analyze_trend(close, n),
        ]
        for det in detectors:
            try:
                r = det()
                if r:
                    patterns.append(r)
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Pattern detection error: {e}")
    return patterns

def _detect_double_top(high, close, n):
    lb = min(60, n)
    seg = high[-lb:]
    df_s = pd.DataFrame({"High": seg, "Low": seg, "Close": seg})
    hs, _ = _find_pivot_points(df_s, 3)
    if len(hs) >= 2:
        p1, p2 = hs[-2][1], hs[-1][1]
        if abs(p1-p2)/p1 < 0.02 and hs[-1][0] > hs[-2][0]+3:
            nl = float(min(seg[hs[-2][0]:hs[-1][0]+1]))
            if float(close[-1]) < p1 and float(close[-1]) > nl*0.97:
                return {"pattern": "Double Top", "type": "bearish", "reliability": "high", "description": f"Two peaks near \u20b9{p1:.2f}, neckline \u20b9{nl:.2f}. Bearish reversal.", "target": round(nl-(p1-nl),2), "neckline": round(nl,2), "implication": "Breakdown below neckline targets lower levels."}
    return None

def _detect_double_bottom(low, close, n):
    lb = min(60, n)
    seg = low[-lb:]
    df_s = pd.DataFrame({"High": seg, "Low": seg, "Close": seg})
    _, ls = _find_pivot_points(df_s, 3)
    if len(ls) >= 2:
        t1, t2 = ls[-2][1], ls[-1][1]
        if abs(t1-t2)/t1 < 0.02 and ls[-1][0] > ls[-2][0]+3:
            nl = float(max(seg[ls[-2][0]:ls[-1][0]+1]))
            if float(close[-1]) > t1 and float(close[-1]) < nl*1.03:
                return {"pattern": "Double Bottom", "type": "bullish", "reliability": "high", "description": f"Two troughs near \u20b9{t1:.2f}, neckline \u20b9{nl:.2f}. Bullish reversal.", "target": round(nl+(nl-t1),2), "neckline": round(nl,2), "implication": "Breakout above neckline targets higher levels."}
    return None

def _detect_head_shoulders(high, close, n):
    lb = min(80, n)
    seg = high[-lb:]
    df_s = pd.DataFrame({"High": seg, "Low": seg, "Close": seg})
    hs, _ = _find_pivot_points(df_s, 4)
    if len(hs) >= 3:
        l, h, r = hs[-3][1], hs[-2][1], hs[-1][1]
        if h > l and h > r and abs(l-r)/l < 0.03:
            nl = float(min(seg[hs[-3][0]:hs[-1][0]+1]))
            return {"pattern": "Head & Shoulders", "type": "bearish", "reliability": "very high", "description": f"Head \u20b9{h:.2f}, shoulders \u20b9{l:.2f}/\u20b9{r:.2f}, neckline \u20b9{nl:.2f}.", "target": round(nl-(h-nl),2), "neckline": round(nl,2), "implication": "Classic bearish reversal. Break below neckline confirms."}
    return None

def _detect_inv_hs(low, close, n):
    lb = min(80, n)
    seg = low[-lb:]
    df_s = pd.DataFrame({"High": seg, "Low": seg, "Close": seg})
    _, ls = _find_pivot_points(df_s, 4)
    if len(ls) >= 3:
        l, h, r = ls[-3][1], ls[-2][1], ls[-1][1]
        if h < l and h < r and abs(l-r)/l < 0.03:
            nl = float(max(seg[ls[-3][0]:ls[-1][0]+1]))
            return {"pattern": "Inverse Head & Shoulders", "type": "bullish", "reliability": "very high", "description": f"Head \u20b9{h:.2f}, shoulders \u20b9{l:.2f}/\u20b9{r:.2f}, neckline \u20b9{nl:.2f}.", "target": round(nl+(nl-h),2), "neckline": round(nl,2), "implication": "Classic bullish reversal. Break above neckline confirms."}
    return None

def _detect_asc_tri(high, low, close, n):
    lb = min(40, n)
    df_s = pd.DataFrame({"High": high[-lb:], "Low": low[-lb:], "Close": close[-lb:]})
    hs, _ = _find_pivot_points(df_s, 3)
    _, ls = _find_pivot_points(df_s, 3)
    if len(hs) >= 3 and len(ls) >= 3:
        hp = [h[1] for h in hs[-3:]]
        lp = [l[1] for l in ls[-3:]]
        if (max(hp)-min(hp))/min(hp) < 0.015 and all(lp[i] < lp[i+1] for i in range(len(lp)-1)):
            res = sum(hp)/len(hp)
            return {"pattern": "Ascending Triangle", "type": "bullish", "reliability": "high", "description": f"Flat resistance \u20b9{res:.2f} with rising lows.", "target": round(res+(res-min(lp)),2), "breakout_level": round(res,2), "implication": "Breakout above resistance confirms bullish move."}
    return None

def _detect_desc_tri(high, low, close, n):
    lb = min(40, n)
    df_s = pd.DataFrame({"High": high[-lb:], "Low": low[-lb:], "Close": close[-lb:]})
    hs, _ = _find_pivot_points(df_s, 3)
    _, ls = _find_pivot_points(df_s, 3)
    if len(hs) >= 3 and len(ls) >= 3:
        lp = [l[1] for l in ls[-3:]]
        hp = [h[1] for h in hs[-3:]]
        if (max(lp)-min(lp))/min(lp) < 0.015 and all(hp[i] > hp[i+1] for i in range(len(hp)-1)):
            sup = sum(lp)/len(lp)
            return {"pattern": "Descending Triangle", "type": "bearish", "reliability": "high", "description": f"Flat support \u20b9{sup:.2f} with falling highs.", "target": round(sup-(max(hp)-sup),2), "breakdown_level": round(sup,2), "implication": "Breakdown below support confirms bearish move."}
    return None

def _detect_bull_flag(close, n):
    if n < 25:
        return None
    pm = (close[-10]-close[-25])/close[-25]
    if pm > 0.08:
        fc = close[-10:]
        fr = (max(fc)-min(fc))/min(fc)
        fd = (fc[-1]-fc[0])/fc[0]
        if fr < 0.05 and -0.05 < fd < 0.02:
            return {"pattern": "Bull Flag", "type": "bullish", "reliability": "medium-high", "description": f"Strong up-pole ({pm*100:.1f}%) + tight consolidation.", "target": round(float(close[-1])+(close[-10]-close[-25]),2), "implication": "Bullish continuation on breakout."}
    return None

def _detect_bear_flag(close, n):
    if n < 25:
        return None
    pm = (close[-10]-close[-25])/close[-25]
    if pm < -0.08:
        fc = close[-10:]
        fr = (max(fc)-min(fc))/min(fc)
        fd = (fc[-1]-fc[0])/fc[0]
        if fr < 0.05 and -0.02 < fd < 0.05:
            return {"pattern": "Bear Flag", "type": "bearish", "reliability": "medium-high", "description": f"Strong down-pole ({abs(pm)*100:.1f}%) + tight consolidation.", "target": round(float(close[-1])-abs(close[-10]-close[-25]),2), "implication": "Bearish continuation on breakdown."}
    return None

def _detect_rising_wedge(high, low, n):
    lb = min(40, n)
    x = np.arange(lb)
    try:
        hs = np.polyfit(x, high[-lb:], 1)[0]
        ls = np.polyfit(x, low[-lb:], 1)[0]
        if hs > 0 and ls > 0 and ls > hs*0.5:
            return {"pattern": "Rising Wedge", "type": "bearish", "reliability": "medium", "description": "Converging rising trendlines. Bearish reversal pattern.", "implication": "Breakdown below lower trendline confirms."}
    except Exception:
        pass
    return None

def _detect_falling_wedge(high, low, n):
    lb = min(40, n)
    x = np.arange(lb)
    try:
        hs = np.polyfit(x, high[-lb:], 1)[0]
        ls = np.polyfit(x, low[-lb:], 1)[0]
        if hs < 0 and ls < 0 and hs > ls*0.5:
            return {"pattern": "Falling Wedge", "type": "bullish", "reliability": "medium", "description": "Converging falling trendlines. Bullish reversal pattern.", "implication": "Breakout above upper trendline confirms."}
    except Exception:
        pass
    return None

def _analyze_trend(close, n):
    if n < 50:
        return None
    e20 = pd.Series(close).ewm(span=20, adjust=False).mean().iloc[-1]
    e50 = pd.Series(close).ewm(span=50, adjust=False).mean().iloc[-1]
    cur = float(close[-1])
    st = "bullish" if cur > e20 else "bearish"
    mt = "bullish" if cur > e50 else "bearish"
    lt = "N/A"
    if n >= 200:
        e200 = pd.Series(close).ewm(span=200, adjust=False).mean().iloc[-1]
        lt = "bullish" if cur > e200 else "bearish"
    cs = None
    if n >= 50:
        e20p = pd.Series(close).ewm(span=20, adjust=False).mean().iloc[-5]
        e50p = pd.Series(close).ewm(span=50, adjust=False).mean().iloc[-5]
        if e20p < e50p and e20 > e50:
            cs = "Golden Cross (20 EMA > 50 EMA) \u2014 Bullish"
        elif e20p > e50p and e20 < e50:
            cs = "Death Cross (20 EMA < 50 EMA) \u2014 Bearish"
    desc = f"Short: {st.upper()}, Medium: {mt.upper()}, Long: {lt.upper()}"
    if cs:
        desc += f". Signal: {cs}"
    ov = "bullish" if st == "bullish" and mt == "bullish" else "bearish" if st == "bearish" and mt == "bearish" else "neutral"
    return {"pattern": "Trend Analysis", "type": ov, "reliability": "high", "description": desc, "short_trend": st, "medium_trend": mt, "long_trend": lt, "cross_signal": cs, "implication": f"Overall {ov.upper()} trend. Trade with the trend."}

def calculate_swing_indicators(df: pd.DataFrame) -> dict:
    """Calculate RSI, MACD, Bollinger Bands, ATR, Stochastic, Volume analysis."""
    ind = {}
    if df is None or df.empty or len(df) < 26:
        return ind
    try:
        close = pd.Series(df["Close"].values, dtype=float)
        high = pd.Series(df["High"].values, dtype=float)
        low = pd.Series(df["Low"].values, dtype=float)
        vol = pd.Series(df["Volume"].values, dtype=float) if "Volume" in df.columns else None

        # RSI 14
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        ag = gain.rolling(14, min_periods=14).mean().iloc[-1]
        al = loss.rolling(14, min_periods=14).mean().iloc[-1]
        rsi = 100 - (100/(1+ag/al)) if al > 0 else 100.0
        ind["rsi_14"] = round(float(rsi), 2)
        ind["rsi_signal"] = "Overbought" if rsi > 70 else "Bullish momentum" if rsi > 60 else "Oversold" if rsi < 30 else "Bearish momentum" if rsi < 40 else "Neutral"

        # MACD
        e12 = close.ewm(span=12, adjust=False).mean()
        e26 = close.ewm(span=26, adjust=False).mean()
        macd = e12 - e26
        sig = macd.ewm(span=9, adjust=False).mean()
        hist = macd - sig
        ind["macd"] = round(float(macd.iloc[-1]), 2)
        ind["macd_signal"] = round(float(sig.iloc[-1]), 2)
        ind["macd_histogram"] = round(float(hist.iloc[-1]), 2)
        ind["macd_trend"] = "Bullish" if macd.iloc[-1] > sig.iloc[-1] else "Bearish"
        co = None
        if len(macd) >= 3:
            if macd.iloc[-2] < sig.iloc[-2] and macd.iloc[-1] > sig.iloc[-1]:
                co = "Bullish crossover"
            elif macd.iloc[-2] > sig.iloc[-2] and macd.iloc[-1] < sig.iloc[-1]:
                co = "Bearish crossover"
        ind["macd_crossover"] = co

        # Bollinger Bands
        sma20 = close.rolling(20).mean()
        std20 = close.rolling(20).std()
        ind["bb_upper"] = round(float((sma20 + 2*std20).iloc[-1]), 2)
        ind["bb_middle"] = round(float(sma20.iloc[-1]), 2)
        ind["bb_lower"] = round(float((sma20 - 2*std20).iloc[-1]), 2)
        bb_width = (ind["bb_upper"] - ind["bb_lower"]) / ind["bb_middle"] * 100
        ind["bb_width_pct"] = round(bb_width, 2)
        cur = float(close.iloc[-1])
        if cur > ind["bb_upper"]:
            ind["bb_signal"] = "Price above upper band \u2014 overbought/breakout"
        elif cur < ind["bb_lower"]:
            ind["bb_signal"] = "Price below lower band \u2014 oversold/breakdown"
        elif bb_width < 5:
            ind["bb_signal"] = "Squeeze \u2014 low volatility, big move expected"
        else:
            ind["bb_signal"] = "Price within bands \u2014 normal range"

        # ATR 14
        tr = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        ind["atr_14"] = round(float(atr), 2)
        ind["atr_pct"] = round(float(atr/cur*100), 2)
        ind["suggested_sl"] = round(cur - 1.5*float(atr), 2)
        ind["suggested_target"] = round(cur + 2*float(atr), 2)

        # Stochastic RSI
        if len(close) >= 28:
            rsi_series = pd.Series(dtype=float)
            d = close.diff()
            g = d.where(d > 0, 0.0)
            l_s = (-d).where(d < 0, 0.0)
            ag_s = g.rolling(14).mean()
            al_s = l_s.rolling(14).mean()
            rs_s = ag_s / al_s.replace(0, np.nan)
            rsi_s = 100 - (100/(1+rs_s))
            rsi_min = rsi_s.rolling(14).min()
            rsi_max = rsi_s.rolling(14).max()
            stoch_rsi = ((rsi_s - rsi_min) / (rsi_max - rsi_min).replace(0, np.nan)) * 100
            ind["stoch_rsi"] = round(float(stoch_rsi.iloc[-1]), 2) if not np.isnan(stoch_rsi.iloc[-1]) else 50.0
            ind["stoch_rsi_signal"] = "Overbought" if ind["stoch_rsi"] > 80 else "Oversold" if ind["stoch_rsi"] < 20 else "Neutral"

        # Volume Analysis
        if vol is not None and len(vol) >= 20:
            avg_vol = vol.rolling(20).mean().iloc[-1]
            cur_vol = float(vol.iloc[-1])
            rel_vol = cur_vol / avg_vol if avg_vol > 0 else 1.0
            ind["relative_volume"] = round(float(rel_vol), 2)
            ind["volume_signal"] = "High volume \u2014 strong conviction" if rel_vol > 1.5 else "Low volume \u2014 weak conviction" if rel_vol < 0.5 else "Normal volume"
            # OBV trend
            obv = (vol * np.sign(close.diff().fillna(0))).cumsum()
            obv_sma = obv.rolling(20).mean()
            ind["obv_trend"] = "Accumulation" if obv.iloc[-1] > obv_sma.iloc[-1] else "Distribution"

        # Swing Trade Score
        score = 50
        if rsi < 35: score += 15
        elif rsi > 65: score -= 10
        if ind.get("macd_trend") == "Bullish": score += 10
        else: score -= 10
        if ind.get("macd_crossover") == "Bullish crossover": score += 10
        elif ind.get("macd_crossover") == "Bearish crossover": score -= 10
        if ind.get("obv_trend") == "Accumulation": score += 10
        else: score -= 5
        if ind.get("relative_volume", 1) > 1.3: score += 5
        ind["swing_score"] = max(0, min(100, score))
        ind["swing_bias"] = "Bullish" if score >= 60 else "Bearish" if score <= 40 else "Neutral"

    except Exception as e:
        logger.error(f"Error calculating swing indicators: {e}")
    return ind

def run_full_technical_analysis(df: pd.DataFrame, current_price: float) -> dict:
    """Run all technical analysis and return combined results."""
    sr = calculate_support_resistance(df, current_price)
    patterns = detect_chart_patterns(df)
    swing = calculate_swing_indicators(df)
    return {"support_resistance": sr, "chart_patterns": patterns, "swing_indicators": swing}
