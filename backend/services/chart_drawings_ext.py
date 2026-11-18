"""Chart Drawing Extension - Triangle, Wedge, Flag, Cup, Range, Trend + OHLC helper."""
import logging, numpy as np, pandas as pd
logger = logging.getLogger(__name__)

def _piv_ext(df, w=5):
    h, lo = df["High"].values, df["Low"].values
    hs, ls = [], []
    for i in range(w, len(df) - w):
        if h[i] == max(h[i-w:i+w+1]): hs.append({"i": i, "p": float(h[i])})
        if lo[i] == min(lo[i-w:i+w+1]): ls.append({"i": i, "p": float(lo[i])})
    return hs, ls

def _closest_ext(pivots, price, off=0):
    if not pivots or price is None: return None
    best, bd = None, float("inf")
    for p in pivots:
        d = abs(p["p"] - price)
        if d < bd: bd, best = d, p["i"] + off
    return best

def _mk_ext(d, xi, xp, xl, xc, xs, xsz):
    if xi is not None and xp:
        d.append({"type": "marker", "x": xi, "y": xp, "label": xl, "color": xc, "shape": xs, "size": xsz})

def _draw_at(pat, df):
    d, n, si = [], len(df), pat.get("pattern_start_idx", 0)
    res = pat.get("resistance") or pat.get("breakout_level")
    _, lows = _piv_ext(df.iloc[si:], 3)
    if res:
        d.append({"type": "horizontal", "y": res, "x1": si, "x2": n-1, "color": "#ff6b6b", "width": 2.5, "dash": False, "label": f"Resistance {res}"})
    if len(lows) >= 2 and res:
        fl, ll = lows[0], lows[-1]
        if ll["i"] != fl["i"]:
            slope = (ll["p"]-fl["p"])/(ll["i"]-fl["i"])
            ey = fl["p"]+slope*(n-1-si-fl["i"])
            fx, lx = fl["i"]+si, n-1
            d.append({"type": "line", "x1": fx, "y1": fl["p"], "x2": lx, "y2": ey, "color": "#51cf66", "width": 2.5, "dash": False, "label": "Rising Support"})
            d.append({"type": "polygon", "points": [{"x": fx, "y": fl["p"]}, {"x": fx, "y": res}, {"x": lx, "y": res}, {"x": lx, "y": ey}], "color": "#51cf6612", "border": "#51cf6630"})
            for low in lows:
                _mk_ext(d, low["i"]+si, low["p"], "", "#51cf66", "circle", 4)
    return d

def _draw_dtr(pat, df):
    d, n, si = [], len(df), pat.get("pattern_start_idx", 0)
    sup = pat.get("support") or pat.get("breakout_level")
    highs, _ = _piv_ext(df.iloc[si:], 3)
    if sup:
        d.append({"type": "horizontal", "y": sup, "x1": si, "x2": n-1, "color": "#51cf66", "width": 2.5, "dash": False, "label": f"Support {sup}"})
    if len(highs) >= 2 and sup:
        fh, lh = highs[0], highs[-1]
        if lh["i"] != fh["i"]:
            slope = (lh["p"]-fh["p"])/(lh["i"]-fh["i"])
            ey = fh["p"]+slope*(n-1-si-fh["i"])
            fx, lx = fh["i"]+si, n-1
            d.append({"type": "line", "x1": fx, "y1": fh["p"], "x2": lx, "y2": ey, "color": "#ff6b6b", "width": 2.5, "dash": False, "label": "Falling Resistance"})
            d.append({"type": "polygon", "points": [{"x": fx, "y": fh["p"]}, {"x": fx, "y": sup}, {"x": lx, "y": sup}, {"x": lx, "y": ey}], "color": "#ff6b6b12", "border": "#ff6b6b30"})
            for h in highs:
                _mk_ext(d, h["i"]+si, h["p"], "", "#ff6b6b", "circle", 4)
    return d

def _draw_st(pat, df):
    d, n, si = [], len(df), pat.get("pattern_start_idx", 0)
    highs, lows = _piv_ext(df.iloc[si:], 3)
    uey, ley, fhx, flx = None, None, None, None
    if len(highs) >= 2:
        fh, lh = highs[0], highs[-1]
        if lh["i"] != fh["i"]:
            slope = (lh["p"]-fh["p"])/(lh["i"]-fh["i"])
            uey, fhx = fh["p"]+slope*(n-1-si-fh["i"]), fh["i"]+si
            d.append({"type": "line", "x1": fhx, "y1": fh["p"], "x2": n-1, "y2": uey, "color": "#ff6b6b", "width": 2.5, "dash": False, "label": "Upper TL"})
            for h in highs:
                _mk_ext(d, h["i"]+si, h["p"], "", "#ff6b6b", "circle", 4)
    if len(lows) >= 2:
        fl, ll = lows[0], lows[-1]
        if ll["i"] != fl["i"]:
            slope = (ll["p"]-fl["p"])/(ll["i"]-fl["i"])
            ley, flx = fl["p"]+slope*(n-1-si-fl["i"]), fl["i"]+si
            d.append({"type": "line", "x1": flx, "y1": fl["p"], "x2": n-1, "y2": ley, "color": "#51cf66", "width": 2.5, "dash": False, "label": "Lower TL"})
            for low in lows:
                _mk_ext(d, low["i"]+si, low["p"], "", "#51cf66", "circle", 4)
    if uey is not None and ley is not None and fhx is not None and flx is not None:
        d.append({"type": "polygon", "points": [
            {"x": fhx, "y": highs[0]["p"]}, {"x": n-1, "y": uey},
            {"x": n-1, "y": ley}, {"x": flx, "y": lows[0]["p"]}
        ], "color": "#ffd70010", "border": "#ffd70030"})
    apex = pat.get("apex")
    if apex:
        _mk_ext(d, n-1, apex, "Apex", "#ffd700", "circle", 6)
    return d

def _draw_wedge(pat, df, rising):
    d, n, si = [], len(df), pat.get("pattern_start_idx", 0)
    lb = n - si
    if lb < 10: return d
    try:
        x = np.arange(lb)
        hs_s, hi = np.polyfit(x, df["High"].values[si:], 1)
        ls_s, li = np.polyfit(x, df["Low"].values[si:], 1)
        c = "#ff6b6b" if rising else "#51cf66"
        hy1, hy2 = float(hi), float(hi+hs_s*(lb-1))
        ly1, ly2 = float(li), float(li+ls_s*(lb-1))
        d.append({"type": "line", "x1": si, "y1": hy1, "x2": n-1, "y2": hy2, "color": c, "width": 2.5, "dash": False, "label": "Upper TL"})
        d.append({"type": "line", "x1": si, "y1": ly1, "x2": n-1, "y2": ly2, "color": c, "width": 2.5, "dash": False, "label": "Lower TL"})
        d.append({"type": "polygon", "points": [
            {"x": si, "y": hy1}, {"x": n-1, "y": hy2},
            {"x": n-1, "y": ly2}, {"x": si, "y": ly1}
        ], "color": c+"10", "border": c+"30"})
    except Exception: pass
    return d

def _draw_flag(pat, df, bullish):
    d, n, si = [], len(df), pat.get("pattern_start_idx", 0)
    ft, fb = pat.get("flag_top"), pat.get("flag_bottom")
    ps, pe = si, max(0, n-10)
    if pe > ps:
        pc = "#51cf66" if bullish else "#ff6b6b"
        d.append({"type": "line", "x1": ps, "y1": float(df["Close"].values[ps]), "x2": pe, "y2": float(df["Close"].values[pe]), "color": pc, "width": 3, "dash": False, "label": "Pole"})
    if ft and fb:
        fx1 = max(0, n-10)
        d.append({"type": "zone", "y1": fb, "y2": ft, "x1": fx1, "x2": n-1, "color": "#ffd70020", "border": "#ffd70060"})
        d.append({"type": "horizontal", "y": ft, "x1": fx1, "x2": n-1, "color": "#ffd700", "width": 1.5, "dash": True, "label": "Flag Top"})
        d.append({"type": "horizontal", "y": fb, "x1": fx1, "x2": n-1, "color": "#ffd700", "width": 1.5, "dash": True, "label": "Flag Bottom"})
    return d

def _draw_cup(pat, df):
    d, n, si = [], len(df), pat.get("pattern_start_idx", 0)
    lr, rr, cb = pat.get("left_rim"), pat.get("right_rim"), pat.get("cup_bottom")
    bo = pat.get("breakout_level")
    hs, ls = _piv_ext(df.iloc[si:], 4)
    lr_i = _closest_ext(hs, lr, si)
    rr_i = _closest_ext(hs, rr, si)
    cb_i = _closest_ext(ls, cb, si)
    _mk_ext(d, lr_i, lr, "L.Rim", "#51cf66", "diamond", 6)
    _mk_ext(d, cb_i, cb, "Bottom", "#ffd700", "circle", 6)
    _mk_ext(d, rr_i, rr, "R.Rim", "#51cf66", "diamond", 6)
    if lr_i is not None and cb_i is not None and lr and cb:
        d.append({"type": "line", "x1": lr_i, "y1": lr, "x2": cb_i, "y2": cb, "color": "#51cf6680", "width": 2, "dash": False})
    if cb_i is not None and rr_i is not None and cb and rr:
        d.append({"type": "line", "x1": cb_i, "y1": cb, "x2": rr_i, "y2": rr, "color": "#51cf6680", "width": 2, "dash": False})
    if bo:
        x1 = lr_i if lr_i else si
        d.append({"type": "horizontal", "y": bo, "x1": x1, "x2": n-1, "color": "#ffd700", "width": 2, "dash": True, "label": f"Breakout {bo}"})
    return d

def _draw_range(pat, df):
    d, n = [], len(df)
    lb = min(40, n)
    start = n - lb
    seg_high = float(df["High"].values[-lb:].max())
    seg_low = float(df["Low"].values[-lb:].min())
    mid = (seg_high + seg_low) / 2
    d.append({"type": "zone", "y1": seg_low, "y2": seg_high, "x1": start, "x2": n-1, "color": "#ffd70015", "border": "#ffd70040"})
    d.append({"type": "horizontal", "y": seg_high, "x1": start, "x2": n-1, "color": "#ff6b6b", "width": 2, "dash": True, "label": f"Resistance {seg_high:.1f}"})
    d.append({"type": "horizontal", "y": seg_low, "x1": start, "x2": n-1, "color": "#51cf66", "width": 2, "dash": True, "label": f"Support {seg_low:.1f}"})
    d.append({"type": "horizontal", "y": mid, "x1": start, "x2": n-1, "color": "#ffffff40", "width": 1, "dash": True, "label": "Mid"})
    return d

def _draw_trend(pat, df):
    d, n = [], len(df)
    close = pd.Series(df["Close"].values, dtype=float)
    if n >= 20:
        ema20 = close.ewm(span=20, adjust=False).mean().values
        pts = [{"x": i, "y": round(float(ema20[i]), 2)} for i in range(19, n, max(1, n // 40))]
        if pts: d.append({"type": "polyline", "points": pts, "color": "#4dabf7", "width": 1.5, "dash": False, "label": "EMA 20"})
    if n >= 50:
        ema50 = close.ewm(span=50, adjust=False).mean().values
        pts = [{"x": i, "y": round(float(ema50[i]), 2)} for i in range(49, n, max(1, n // 40))]
        if pts: d.append({"type": "polyline", "points": pts, "color": "#f783ac", "width": 1.5, "dash": False, "label": "EMA 50"})
    return d

def prepare_ohlc_for_chart(df, max_bars=80):
    if df is None or df.empty: return []
    subset = df.iloc[-max_bars:] if len(df) > max_bars else df
    bars = []
    for idx, row in subset.iterrows():
        bar = {
            "o": round(float(row["Open"]), 2) if pd.notna(row.get("Open")) else None,
            "h": round(float(row["High"]), 2) if pd.notna(row.get("High")) else None,
            "l": round(float(row["Low"]), 2) if pd.notna(row.get("Low")) else None,
            "c": round(float(row["Close"]), 2) if pd.notna(row.get("Close")) else None,
            "v": int(row["Volume"]) if pd.notna(row.get("Volume")) else 0,
        }
        try:
            if hasattr(idx, 'isoformat'): bar["t"] = idx.isoformat()
            elif hasattr(idx, 'strftime'): bar["t"] = idx.strftime("%Y-%m-%d")
            else: bar["t"] = str(idx)
        except Exception: bar["t"] = ""
        bars.append(bar)
    return bars
