"""Chart Drawing Generator - Pattern visualization with proper diagrams.
Drawing types: line, horizontal, zone, marker, polyline, polygon, arrow
"""
import logging, numpy as np, pandas as pd
logger = logging.getLogger(__name__)

def generate_pattern_drawings(pattern, df):
    drawings, name = [], pattern.get("pattern", "")
    try:
        fn_map = {
            "Head & Shoulders": _draw_hs, "Inverse Head & Shoulders": _draw_ihs,
            "Double Top": _draw_dt, "Double Bottom": _draw_db,
            "Ascending Triangle": _draw_at, "Descending Triangle": _draw_dtr,
            "Symmetrical Triangle": _draw_st,
            "Rising Wedge": lambda p,d: _draw_wedge(p,d,True),
            "Falling Wedge": lambda p,d: _draw_wedge(p,d,False),
            "Bull Flag": lambda p,d: _draw_flag(p,d,True),
            "Bullish Flag": lambda p,d: _draw_flag(p,d,True),
            "Bear Flag": lambda p,d: _draw_flag(p,d,False),
            "Bearish Flag": lambda p,d: _draw_flag(p,d,False),
            "Cup and Handle": _draw_cup, "Sideways Range": _draw_range,
            "Trend Analysis": _draw_trend,
        }
        for k, fn in fn_map.items():
            if k in name:
                drawings = fn(pattern, df)
                break
        _add_levels(drawings, pattern, df)
    except Exception as e:
        logger.warning(f"Drawing error for {name}: {e}")
    return drawings

def _piv(df, w=5):
    h, lo = df["High"].values, df["Low"].values
    hs, ls = [], []
    for i in range(w, len(df) - w):
        if h[i] == max(h[i-w:i+w+1]): hs.append({"i": i, "p": float(h[i])})
        if lo[i] == min(lo[i-w:i+w+1]): ls.append({"i": i, "p": float(lo[i])})
    return hs, ls

def _closest(pivots, price, off=0):
    if not pivots or price is None: return None
    best, bd = None, float("inf")
    for p in pivots:
        d = abs(p["p"] - price)
        if d < bd: bd, best = d, p["i"] + off
    return best

def _add_levels(drawings, pat, df):
    n = len(df)
    tgt, tgt_up, tgt_down = pat.get("target"), pat.get("target_up"), pat.get("target_down")
    inv, pt = pat.get("invalidation"), pat.get("type", "neutral")
    cp = pat.get("current_price") or (float(df["Close"].iloc[-1]) if n > 0 else None)
    zs, ze = max(0, n - 8), n - 1
    if tgt:
        tc = "#51cf66" if pt == "bullish" else "#ff6b6b" if pt == "bearish" else "#ffd700"
        drawings.append({"type": "horizontal", "y": tgt, "x1": zs, "x2": ze, "color": tc, "width": 2, "dash": True, "label": f"Target {tgt}"})
        if cp:
            zh = abs(tgt - cp) * 0.06
            drawings.append({"type": "zone", "y1": tgt-zh, "y2": tgt+zh, "x1": zs, "x2": ze, "color": tc+"18", "border": tc+"50"})
            drawings.append({"type": "arrow", "x": ze, "y1": cp, "y2": tgt, "color": tc, "width": 2})
    if tgt_up:
        drawings.append({"type": "horizontal", "y": tgt_up, "x1": zs, "x2": ze, "color": "#51cf66", "width": 2, "dash": True, "label": f"Target Up {tgt_up}"})
    if tgt_down:
        drawings.append({"type": "horizontal", "y": tgt_down, "x1": zs, "x2": ze, "color": "#ff6b6b", "width": 2, "dash": True, "label": f"Target Down {tgt_down}"})
    if inv:
        drawings.append({"type": "horizontal", "y": inv, "x1": zs, "x2": ze, "color": "#ff4444", "width": 2, "dash": True, "label": f"SL {inv}"})
        if cp:
            zh = abs(inv - cp) * 0.06
            drawings.append({"type": "zone", "y1": inv-zh, "y2": inv+zh, "x1": zs, "x2": ze, "color": "#ff444420", "border": "#ff444460"})
    if cp:
        drawings.append({"type": "horizontal", "y": cp, "x1": max(0, n-5), "x2": ze, "color": "#ffffff", "width": 1.5, "dash": False, "label": f"CMP {cp}"})

def _mk(d, xi, xp, xl, xc, xs, xsz):
    if xi is not None and xp:
        d.append({"type": "marker", "x": xi, "y": xp, "label": xl, "color": xc, "shape": xs, "size": xsz})

def _draw_hs(pat, df):
    d, n, si = [], len(df), pat.get("pattern_start_idx", 0)
    ls_p, hd_p, rs_p = pat.get("left_shoulder"), pat.get("head"), pat.get("right_shoulder")
    nl_p = pat.get("dynamic_neckline") or pat.get("neckline")
    n1_p, n2_p = pat.get("neckline_1"), pat.get("neckline_2")
    hs, ls = _piv(df.iloc[si:], 4)
    ls_i, hd_i = _closest(hs, ls_p, si), _closest(hs, hd_p, si)
    rs_i = _closest(hs, rs_p, si) if rs_p else None
    t1_i = _closest(ls, n1_p, si) if n1_p else None
    t2_i = _closest(ls, n2_p, si) if n2_p else None
    pts = []
    if ls_i is not None and ls_p: pts.append({"x": ls_i, "y": ls_p})
    if t1_i is not None and n1_p: pts.append({"x": t1_i, "y": n1_p})
    if hd_i is not None and hd_p: pts.append({"x": hd_i, "y": hd_p})
    if t2_i is not None and n2_p: pts.append({"x": t2_i, "y": n2_p})
    if rs_i is not None and rs_p: pts.append({"x": rs_i, "y": rs_p})
    if len(pts) >= 3:
        d.append({"type": "polyline", "points": pts, "color": "#ff6b6b", "width": 2.5, "dash": False, "label": "H&S"})
    _mk(d, ls_i, ls_p, "LS", "#ff9f43", "diamond", 7)
    _mk(d, hd_i, hd_p, "HEAD", "#ff4444", "diamond", 9)
    _mk(d, rs_i, rs_p, "RS", "#ff9f43", "diamond", 7)
    _mk(d, t1_i, n1_p, "T1", "#ffd700", "circle", 5)
    _mk(d, t2_i, n2_p, "T2", "#ffd700", "circle", 5)
    if nl_p:
        ns, ne = t1_i or ls_i or si, min(n-1, (rs_i or n-1)+8)
        if n1_p and n2_p and t1_i and t2_i:
            d.append({"type": "line", "x1": t1_i, "y1": n1_p, "x2": ne, "y2": nl_p, "color": "#ffd700", "width": 2.5, "dash": True, "label": f"Neckline {nl_p}"})
        else:
            d.append({"type": "horizontal", "y": nl_p, "x1": ns, "x2": ne, "color": "#ffd700", "width": 2.5, "dash": True, "label": f"Neckline {nl_p}"})
    if ls_i and rs_i and ls_p and rs_p:
        d.append({"type": "line", "x1": ls_i, "y1": ls_p, "x2": rs_i, "y2": rs_p, "color": "#ff6b6b40", "width": 1, "dash": True})
    return d

def _draw_ihs(pat, df):
    d, n, si = [], len(df), pat.get("pattern_start_idx", 0)
    ls_p, hd_p, rs_p = pat.get("left_shoulder"), pat.get("head"), pat.get("right_shoulder")
    nl_p = pat.get("dynamic_neckline") or pat.get("neckline")
    n1_p, n2_p = pat.get("neckline_1"), pat.get("neckline_2")
    hs, ls = _piv(df.iloc[si:], 4)
    ls_i, hd_i = _closest(ls, ls_p, si), _closest(ls, hd_p, si)
    rs_i = _closest(ls, rs_p, si) if rs_p else None
    p1_i = _closest(hs, n1_p, si) if n1_p else None
    p2_i = _closest(hs, n2_p, si) if n2_p else None
    pts = []
    if ls_i is not None and ls_p: pts.append({"x": ls_i, "y": ls_p})
    if p1_i is not None and n1_p: pts.append({"x": p1_i, "y": n1_p})
    if hd_i is not None and hd_p: pts.append({"x": hd_i, "y": hd_p})
    if p2_i is not None and n2_p: pts.append({"x": p2_i, "y": n2_p})
    if rs_i is not None and rs_p: pts.append({"x": rs_i, "y": rs_p})
    if len(pts) >= 3:
        d.append({"type": "polyline", "points": pts, "color": "#51cf66", "width": 2.5, "dash": False, "label": "Inv H&S"})
    _mk(d, ls_i, ls_p, "LS", "#51cf66", "diamond", 7)
    _mk(d, hd_i, hd_p, "HEAD", "#40c057", "diamond", 9)
    _mk(d, rs_i, rs_p, "RS", "#51cf66", "diamond", 7)
    _mk(d, p1_i, n1_p, "P1", "#ffd700", "circle", 5)
    _mk(d, p2_i, n2_p, "P2", "#ffd700", "circle", 5)
    if nl_p:
        ns, ne = p1_i or ls_i or si, min(n-1, (rs_i or n-1)+8)
        if n1_p and n2_p and p1_i and p2_i:
            d.append({"type": "line", "x1": p1_i, "y1": n1_p, "x2": ne, "y2": nl_p, "color": "#ffd700", "width": 2.5, "dash": True, "label": f"Neckline {nl_p}"})
        else:
            d.append({"type": "horizontal", "y": nl_p, "x1": ns, "x2": ne, "color": "#ffd700", "width": 2.5, "dash": True, "label": f"Neckline {nl_p}"})
    if ls_i and rs_i and ls_p and rs_p:
        d.append({"type": "line", "x1": ls_i, "y1": ls_p, "x2": rs_i, "y2": rs_p, "color": "#51cf6640", "width": 1, "dash": True})
    return d

def _draw_dt(pat, df):
    d, n, si = [], len(df), pat.get("pattern_start_idx", 0)
    p1, p2, nl = pat.get("peak_1"), pat.get("peak_2"), pat.get("neckline")
    hs, ls = _piv(df.iloc[si:], 3)
    p1_i, p2_i, nl_i = _closest(hs, p1, si), _closest(hs, p2, si), _closest(ls, nl, si)
    pts = []
    if p1_i is not None and p1: pts.append({"x": p1_i, "y": p1})
    if nl_i is not None and nl: pts.append({"x": nl_i, "y": nl})
    if p2_i is not None and p2: pts.append({"x": p2_i, "y": p2})
    if len(pts) >= 3:
        d.append({"type": "polyline", "points": pts, "color": "#ff6b6b", "width": 2.5, "dash": False, "label": "Double Top"})
    _mk(d, p1_i, p1, "P1", "#ff6b6b", "triangle_down", 7)
    _mk(d, p2_i, p2, "P2", "#ff6b6b", "triangle_down", 7)
    if p1 and p2:
        rl = max(p1, p2)
        x1, x2 = p1_i or si, min(n-1, (p2_i or n-1)+5)
        d.append({"type": "zone", "y1": min(p1,p2), "y2": rl, "x1": x1, "x2": x2, "color": "#ff6b6b15", "border": "#ff6b6b40"})
        d.append({"type": "horizontal", "y": rl, "x1": x1, "x2": x2, "color": "#ff6b6b", "width": 2, "dash": False, "label": f"Resistance {rl}"})
    if nl:
        x1 = nl_i if nl_i else (p1_i or si)
        x2 = min(n-1, (p2_i or n-1)+8)
        d.append({"type": "horizontal", "y": nl, "x1": x1, "x2": x2, "color": "#ffd700", "width": 2.5, "dash": True, "label": f"Neckline {nl}"})
    return d

def _draw_db(pat, df):
    d, n, si = [], len(df), pat.get("pattern_start_idx", 0)
    t1, t2, nl = pat.get("trough_1"), pat.get("trough_2"), pat.get("neckline")
    hs, ls = _piv(df.iloc[si:], 3)
    t1_i, t2_i, nl_i = _closest(ls, t1, si), _closest(ls, t2, si), _closest(hs, nl, si)
    pts = []
    if t1_i is not None and t1: pts.append({"x": t1_i, "y": t1})
    if nl_i is not None and nl: pts.append({"x": nl_i, "y": nl})
    if t2_i is not None and t2: pts.append({"x": t2_i, "y": t2})
    if len(pts) >= 3:
        d.append({"type": "polyline", "points": pts, "color": "#51cf66", "width": 2.5, "dash": False, "label": "Double Bottom"})
    _mk(d, t1_i, t1, "T1", "#51cf66", "triangle_up", 7)
    _mk(d, t2_i, t2, "T2", "#51cf66", "triangle_up", 7)
    if t1 and t2:
        sl = min(t1, t2)
        x1, x2 = t1_i or si, min(n-1, (t2_i or n-1)+5)
        d.append({"type": "zone", "y1": sl, "y2": max(t1,t2), "x1": x1, "x2": x2, "color": "#51cf6615", "border": "#51cf6640"})
        d.append({"type": "horizontal", "y": sl, "x1": x1, "x2": x2, "color": "#51cf66", "width": 2, "dash": False, "label": f"Support {sl}"})
    if nl:
        x1 = nl_i if nl_i else (t1_i or si)
        x2 = min(n-1, (t2_i or n-1)+8)
        d.append({"type": "horizontal", "y": nl, "x1": x1, "x2": x2, "color": "#ffd700", "width": 2.5, "dash": True, "label": f"Neckline {nl}"})
    return d

# Import remaining pattern drawers from chart_drawings_ext
from services.chart_drawings_ext import _draw_at, _draw_dtr, _draw_st, _draw_wedge, _draw_flag, _draw_cup, _draw_range, _draw_trend, prepare_ohlc_for_chart
