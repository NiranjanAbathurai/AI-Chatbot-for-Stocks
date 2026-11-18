"""Pattern Chart Image Generator - Creates annotated candlestick chart PNG images."""

import io
import logging
import hashlib
from typing import Optional

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)

BG_COLOR = "#0f0f14"
TEXT_COLOR = "#c8c8d8"
CANDLE_UP = "#00d26a"
CANDLE_DOWN = "#ff4757"
BULLISH_COLOR = "#51cf66"
BEARISH_COLOR = "#ff6b6b"
NEUTRAL_COLOR = "#ffd700"
NECKLINE_COLOR = "#ffd700"
MARKER_COLOR = "#ff9f43"

_image_cache = {}
MAX_CACHE = 200


def _cache_key(ticker, pattern_name, timeframe):
    return hashlib.md5(f"{ticker}:{pattern_name}:{timeframe}".encode()).hexdigest()


def clear_image_cache():
    _image_cache.clear()


def generate_pattern_image(df, pattern, ticker="", timeframe="1d", max_bars=80,
                           width=1200, height=650, use_cache=True):
    """Generate a PNG image of candlestick chart with pattern annotations. Returns bytes."""
    pat_name = pattern.get("pattern", "Unknown")
    if use_cache:
        ck = _cache_key(ticker, pat_name, timeframe)
        cached = _image_cache.get(ck)
        if cached:
            return cached

    n = len(df)
    start = max(0, n - max_bars)
    chart_df = df.iloc[start:].copy().reset_index(drop=True)
    chart_n = len(chart_df)
    if chart_n < 5:
        return _empty_image(f"Insufficient data for {pat_name}")

    pat_start = max(0, pattern.get("pattern_start_idx", 0) - start)

    dpi = 100
    fig, ax = plt.subplots(figsize=(width / dpi, height / dpi), dpi=dpi)
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    _draw_candles(ax, chart_df)
    _draw_overlay(ax, chart_df, pattern, pat_start, chart_n)
    _draw_levels(ax, chart_df, pattern, chart_n)

    # Title
    td = ticker.replace(".NS", "") if ticker else ""
    title = f"{td} — {pat_name}" if td else pat_name
    stage = pattern.get("stage", "")
    if stage:
        title += f"  ({stage})"
    ax.set_title(title, color=TEXT_COLOR, fontsize=14, fontweight="bold", pad=12)

    # Axes style
    ax.tick_params(colors=TEXT_COLOR, labelsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_color("#333344")
    ax.spines["left"].set_color("#333344")
    ax.grid(True, alpha=0.08, color="#ffffff")
    _set_xlabels(ax, chart_df)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"₹{x:,.1f}"))

    # Confidence badge
    conf = pattern.get("structure_confidence")
    if conf:
        cc = BULLISH_COLOR if conf >= 70 else NEUTRAL_COLOR if conf >= 50 else BEARISH_COLOR
        ax.text(0.98, 0.02, f"Confidence: {conf}%", transform=ax.transAxes, fontsize=9,
                color=cc, ha="right", va="bottom",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#1a1a2e", edgecolor="#333355", alpha=0.9))

    plt.tight_layout(pad=1.5)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=fig.get_facecolor(), edgecolor="none",
                bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)
    buf.seek(0)
    img_bytes = buf.read()

    if use_cache:
        if len(_image_cache) >= MAX_CACHE:
            for k in list(_image_cache.keys())[:MAX_CACHE // 4]:
                _image_cache.pop(k, None)
        _image_cache[_cache_key(ticker, pat_name, timeframe)] = img_bytes

    return img_bytes


def _empty_image(msg):
    fig, ax = plt.subplots(figsize=(8, 4), dpi=100)
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    ax.text(0.5, 0.5, msg, transform=ax.transAxes, fontsize=14, color=TEXT_COLOR, ha="center", va="center")
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _draw_candles(ax, df):
    for i, (_, row) in enumerate(df.iterrows()):
        o, h, l, c = row["Open"], row["High"], row["Low"], row["Close"]
        if pd.isna(o) or pd.isna(c):
            continue
        color = CANDLE_UP if c >= o else CANDLE_DOWN
        ax.plot([i, i], [l, h], color=color, linewidth=0.8, alpha=0.7)
        bb = min(o, c)
        bh = max(abs(c - o), (h - l) * 0.02)
        ax.add_patch(plt.Rectangle((i - 0.35, bb), 0.7, bh, facecolor=color, edgecolor=color, linewidth=0.5))
    ax.set_xlim(-1, len(df) + 1)
    prices = df[["High", "Low"]].values.flatten()
    prices = prices[~np.isnan(prices)]
    if len(prices) > 0:
        pr = prices.max() - prices.min()
        ax.set_ylim(prices.min() - pr * 0.08, prices.max() + pr * 0.12)


def _set_xlabels(ax, df):
    n = len(df)
    step = max(1, n // 8)
    ticks, labels = [], []
    for i in range(0, n, step):
        ticks.append(i)
        idx = df.index[i] if hasattr(df.index[i], "strftime") else None
        labels.append(idx.strftime("%d %b") if idx else str(i))
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, fontsize=7, color=TEXT_COLOR)


# ── Pivot helpers ─────────────────────────────────────────────────────
def _pivots(df, w=5):
    h, lo = df["High"].values, df["Low"].values
    hs, ls = [], []
    for i in range(w, len(df) - w):
        if h[i] == max(h[i-w:i+w+1]):
            hs.append({"i": i, "p": float(h[i])})
        if lo[i] == min(lo[i-w:i+w+1]):
            ls.append({"i": i, "p": float(lo[i])})
    return hs, ls


def _cpiv(pivots, price, off=0):
    if not pivots or price is None:
        return None
    best, bd = None, float("inf")
    for p in pivots:
        d = abs(p["p"] - price)
        if d < bd:
            bd, best = d, p["i"] + off
    return best


# ── Drawing helpers ───────────────────────────────────────────────────
def _marker(ax, x, y, label, color, shape="D", sz=8):
    if x is None or y is None:
        return
    ax.plot(x, y, marker=shape, color=color, markersize=sz, zorder=5)
    ax.annotate(label, (x, y), textcoords="offset points", xytext=(0, 12),
                ha="center", fontsize=9, fontweight="bold", color=color,
                bbox=dict(boxstyle="round,pad=0.2", facecolor=BG_COLOR, edgecolor=color, alpha=0.85))


def _hline(ax, y, x1, x2, color, label=None, dash=True, lw=2):
    ax.hlines(y, x1, x2, colors=color, linestyles="--" if dash else "-", linewidth=lw, zorder=3)
    if label:
        ax.text(x2 + 0.5, y, f" {label}", color=color, fontsize=8, va="center",
                bbox=dict(boxstyle="round,pad=0.2", facecolor=BG_COLOR, edgecolor=color, alpha=0.8))


def _tline(ax, x1, y1, x2, y2, color, label=None, dash=False, lw=2.5):
    ax.plot([x1, x2], [y1, y2], color=color, linestyle="--" if dash else "-", linewidth=lw, zorder=3)
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mx, my, f" {label}", color=color, fontsize=8, va="bottom",
                bbox=dict(boxstyle="round,pad=0.2", facecolor=BG_COLOR, edgecolor=color, alpha=0.8))


def _arrow(ax, x, y1, y2, color, lw=2):
    ax.annotate("", xy=(x, y2), xytext=(x, y1),
                arrowprops=dict(arrowstyle="->", color=color, lw=lw, linestyle="--"))


# ── Levels (target, SL, CMP) ─────────────────────────────────────────
def _draw_levels(ax, df, pat, n):
    tgt = pat.get("target")
    tgt_up = pat.get("target_up")
    tgt_down = pat.get("target_down")
    inv = pat.get("invalidation")
    cp = pat.get("current_price") or (float(df["Close"].iloc[-1]) if n > 0 else None)
    pt = pat.get("type", "neutral")
    zs, ze = max(0, n - 8), n - 1

    if tgt:
        tc = BULLISH_COLOR if pt == "bullish" else BEARISH_COLOR if pt == "bearish" else NEUTRAL_COLOR
        _hline(ax, tgt, zs, ze, tc, f"Target ₹{tgt:.1f}", dash=True, lw=2)
        if cp:
            _arrow(ax, ze - 1, cp, tgt, tc, lw=1.5)
    if tgt_up:
        _hline(ax, tgt_up, zs, ze, BULLISH_COLOR, f"Target Up ₹{tgt_up:.1f}", dash=True)
    if tgt_down:
        _hline(ax, tgt_down, zs, ze, BEARISH_COLOR, f"Target Down ₹{tgt_down:.1f}", dash=True)
    if inv:
        _hline(ax, inv, zs, ze, "#ff4444", f"SL ₹{inv:.1f}", dash=True, lw=2)
    if cp:
        _hline(ax, cp, max(0, n - 5), ze, "#ffffff", f"CMP ₹{cp:.1f}", dash=False, lw=1.5)


# ── Pattern overlay router ───────────────────────────────────────────
def _draw_overlay(ax, df, pattern, si, n):
    name = pattern.get("pattern", "")
    fns = {
        "Head & Shoulders": _ov_hs,
        "Inverse Head & Shoulders": _ov_ihs,
        "Double Top": _ov_dt,
        "Double Bottom": _ov_db,
        "Ascending Triangle": _ov_at,
        "Descending Triangle": _ov_dtr,
        "Symmetrical Triangle": _ov_st,
        "Rising Wedge": _ov_rw,
        "Falling Wedge": _ov_fw,
        "Bull Flag": _ov_bf,
        "Bullish Flag": _ov_bf,
        "Bear Flag": _ov_brf,
        "Bearish Flag": _ov_brf,
        "Cup and Handle": _ov_cup,
        "Sideways Range": _ov_range,
        "Trend Analysis": _ov_trend,
    }
    for key, fn in fns.items():
        if key in name:
            try:
                fn(ax, df, pattern, si, n)
            except Exception as e:
                logger.warning(f"Overlay error {name}: {e}")
            return
    _ov_generic(ax, df, pattern, si, n)


# ── Head & Shoulders ─────────────────────────────────────────────────
def _ov_hs(ax, df, pat, si, n):
    ls_p, hd_p, rs_p = pat.get("left_shoulder"), pat.get("head"), pat.get("right_shoulder")
    nl_p = pat.get("dynamic_neckline") or pat.get("neckline")
    n1_p, n2_p = pat.get("neckline_1"), pat.get("neckline_2")
    hs, ls = _pivots(df.iloc[si:], 4)
    ls_i = _cpiv(hs, ls_p, si)
    hd_i = _cpiv(hs, hd_p, si)
    rs_i = _cpiv(hs, rs_p, si) if rs_p else None
    t1_i = _cpiv(ls, n1_p, si) if n1_p else None
    t2_i = _cpiv(ls, n2_p, si) if n2_p else None
    px, py = [], []
    for xi, yi in [(ls_i, ls_p), (t1_i, n1_p), (hd_i, hd_p), (t2_i, n2_p), (rs_i, rs_p)]:
        if xi is not None and yi is not None:
            px.append(xi)
            py.append(yi)
    if len(px) >= 3:
        ax.plot(px, py, color=BEARISH_COLOR, linewidth=2.5, zorder=4, alpha=0.9)
    _marker(ax, ls_i, ls_p, "LS", MARKER_COLOR, "D", 7)
    _marker(ax, hd_i, hd_p, "HEAD", BEARISH_COLOR, "D", 9)
    _marker(ax, rs_i, rs_p, "RS", MARKER_COLOR, "D", 7)
    if nl_p:
        ns = t1_i or ls_i or si
        ne = min(n - 1, (rs_i or n - 1) + 8)
        if n1_p and n2_p and t1_i and t2_i:
            _tline(ax, t1_i, n1_p, ne, nl_p, NECKLINE_COLOR, "Neckline", dash=True)
        else:
            _hline(ax, nl_p, ns, ne, NECKLINE_COLOR, f"Neckline ₹{nl_p:.1f}", dash=True)
    if ls_i and rs_i and ls_p and rs_p:
        ax.plot([ls_i, rs_i], [ls_p, rs_p], color=BEARISH_COLOR, linestyle=":", linewidth=1, alpha=0.4)


# ── Inverse Head & Shoulders ─────────────────────────────────────────
def _ov_ihs(ax, df, pat, si, n):
    ls_p, hd_p, rs_p = pat.get("left_shoulder"), pat.get("head"), pat.get("right_shoulder")
    nl_p = pat.get("dynamic_neckline") or pat.get("neckline")
    n1_p, n2_p = pat.get("neckline_1"), pat.get("neckline_2")
    hs, ls = _pivots(df.iloc[si:], 4)
    ls_i = _cpiv(ls, ls_p, si)
    hd_i = _cpiv(ls, hd_p, si)
    rs_i = _cpiv(ls, rs_p, si) if rs_p else None
    p1_i = _cpiv(hs, n1_p, si) if n1_p else None
    p2_i = _cpiv(hs, n2_p, si) if n2_p else None
    px, py = [], []
    for xi, yi in [(ls_i, ls_p), (p1_i, n1_p), (hd_i, hd_p), (p2_i, n2_p), (rs_i, rs_p)]:
        if xi is not None and yi is not None:
            px.append(xi)
            py.append(yi)
    if len(px) >= 3:
        ax.plot(px, py, color=BULLISH_COLOR, linewidth=2.5, zorder=4, alpha=0.9)
    _marker(ax, ls_i, ls_p, "LS", BULLISH_COLOR, "D", 7)
    _marker(ax, hd_i, hd_p, "HEAD", "#40c057", "D", 9)
    _marker(ax, rs_i, rs_p, "RS", BULLISH_COLOR, "D", 7)
    if nl_p:
        ns = p1_i or ls_i or si
        ne = min(n - 1, (rs_i or n - 1) + 8)
        if n1_p and n2_p and p1_i and p2_i:
            _tline(ax, p1_i, n1_p, ne, nl_p, NECKLINE_COLOR, "Neckline", dash=True)
        else:
            _hline(ax, nl_p, ns, ne, NECKLINE_COLOR, f"Neckline ₹{nl_p:.1f}", dash=True)


# ── Double Top ────────────────────────────────────────────────────────
def _ov_dt(ax, df, pat, si, n):
    p1, p2, nl = pat.get("peak_1"), pat.get("peak_2"), pat.get("neckline")
    hs, ls = _pivots(df.iloc[si:], 3)
    p1_i = _cpiv(hs, p1, si)
    p2_i = _cpiv(hs, p2, si)
    nl_i = _cpiv(ls, nl, si)
    px, py = [], []
    for xi, yi in [(p1_i, p1), (nl_i, nl), (p2_i, p2)]:
        if xi is not None and yi is not None:
            px.append(xi)
            py.append(yi)
    if len(px) >= 3:
        ax.plot(px, py, color=BEARISH_COLOR, linewidth=2.5, zorder=4, alpha=0.9)
    _marker(ax, p1_i, p1, "Top 1", BEARISH_COLOR, "v", 9)
    _marker(ax, p2_i, p2, "Top 2", BEARISH_COLOR, "v", 9)
    if p1 and p2:
        rl = max(p1, p2)
        x1, x2 = p1_i or si, min(n - 1, (p2_i or n - 1) + 5)
        ax.axhspan(min(p1, p2), rl, facecolor=BEARISH_COLOR, alpha=0.08, zorder=1)
        _hline(ax, rl, x1, x2, BEARISH_COLOR, f"Resistance ₹{rl:.1f}", dash=False)
    if nl:
        x1 = nl_i if nl_i else (p1_i or si)
        x2 = min(n - 1, (p2_i or n - 1) + 8)
        _hline(ax, nl, x1, x2, NECKLINE_COLOR, f"Neckline ₹{nl:.1f}", dash=True)


# ── Double Bottom ─────────────────────────────────────────────────────
def _ov_db(ax, df, pat, si, n):
    t1, t2, nl = pat.get("trough_1"), pat.get("trough_2"), pat.get("neckline")
    hs, ls = _pivots(df.iloc[si:], 3)
    t1_i = _cpiv(ls, t1, si)
    t2_i = _cpiv(ls, t2, si)
    nl_i = _cpiv(hs, nl, si)
    px, py = [], []
    for xi, yi in [(t1_i, t1), (nl_i, nl), (t2_i, t2)]:
        if xi is not None and yi is not None:
            px.append(xi)
            py.append(yi)
    if len(px) >= 3:
        ax.plot(px, py, color=BULLISH_COLOR, linewidth=2.5, zorder=4, alpha=0.9)
    _marker(ax, t1_i, t1, "Bottom 1", BULLISH_COLOR, "^", 9)
    _marker(ax, t2_i, t2, "Bottom 2", BULLISH_COLOR, "^", 9)
    if t1 and t2:
        sl = min(t1, t2)
        x1, x2 = t1_i or si, min(n - 1, (t2_i or n - 1) + 5)
        ax.axhspan(sl, max(t1, t2), facecolor=BULLISH_COLOR, alpha=0.08, zorder=1)
        _hline(ax, sl, x1, x2, BULLISH_COLOR, f"Support ₹{sl:.1f}", dash=False)
    if nl:
        x1 = nl_i if nl_i else (t1_i or si)
        x2 = min(n - 1, (t2_i or n - 1) + 8)
        _hline(ax, nl, x1, x2, NECKLINE_COLOR, f"Neckline ₹{nl:.1f}", dash=True)


# ── Ascending Triangle ────────────────────────────────────────────────
def _ov_at(ax, df, pat, si, n):
    res = pat.get("resistance") or pat.get("breakout_level")
    _, lows = _pivots(df.iloc[si:], 3)
    if res:
        _hline(ax, res, si, n - 1, BEARISH_COLOR, f"Resistance ₹{res:.1f}", dash=False, lw=2.5)
    if len(lows) >= 2 and res:
        fl, ll = lows[0], lows[-1]
        if ll["i"] != fl["i"]:
            slope = (ll["p"] - fl["p"]) / (ll["i"] - fl["i"])
            ey = fl["p"] + slope * (n - 1 - si - fl["i"])
            fx = fl["i"] + si
            _tline(ax, fx, fl["p"], n - 1, ey, BULLISH_COLOR, "Rising Support")
            ax.fill([fx, fx, n - 1, n - 1], [fl["p"], res, res, ey], color=BULLISH_COLOR, alpha=0.06, zorder=1)
            for low in lows:
                ax.plot(low["i"] + si, low["p"], "o", color=BULLISH_COLOR, markersize=5, zorder=5)


# ── Descending Triangle ──────────────────────────────────────────────
def _ov_dtr(ax, df, pat, si, n):
    sup = pat.get("support") or pat.get("breakout_level")
    highs, _ = _pivots(df.iloc[si:], 3)
    if sup:
        _hline(ax, sup, si, n - 1, BULLISH_COLOR, f"Support ₹{sup:.1f}", dash=False, lw=2.5)
    if len(highs) >= 2 and sup:
        fh, lh = highs[0], highs[-1]
        if lh["i"] != fh["i"]:
            slope = (lh["p"] - fh["p"]) / (lh["i"] - fh["i"])
            ey = fh["p"] + slope * (n - 1 - si - fh["i"])
            fx = fh["i"] + si
            _tline(ax, fx, fh["p"], n - 1, ey, BEARISH_COLOR, "Falling Resistance")
            ax.fill([fx, fx, n - 1, n - 1], [fh["p"], sup, sup, ey], color=BEARISH_COLOR, alpha=0.06, zorder=1)
            for h in highs:
                ax.plot(h["i"] + si, h["p"], "o", color=BEARISH_COLOR, markersize=5, zorder=5)


# ── Symmetrical Triangle ─────────────────────────────────────────────
def _ov_st(ax, df, pat, si, n):
    highs, lows = _pivots(df.iloc[si:], 3)
    uey, ley, fhx, flx = None, None, None, None
    if len(highs) >= 2:
        fh, lh = highs[0], highs[-1]
        if lh["i"] != fh["i"]:
            slope = (lh["p"] - fh["p"]) / (lh["i"] - fh["i"])
            uey = fh["p"] + slope * (n - 1 - si - fh["i"])
            fhx = fh["i"] + si
            _tline(ax, fhx, fh["p"], n - 1, uey, BEARISH_COLOR, "Upper TL")
            for h in highs:
                ax.plot(h["i"] + si, h["p"], "o", color=BEARISH_COLOR, markersize=5, zorder=5)
    if len(lows) >= 2:
        fl, ll = lows[0], lows[-1]
        if ll["i"] != fl["i"]:
            slope = (ll["p"] - fl["p"]) / (ll["i"] - fl["i"])
            ley = fl["p"] + slope * (n - 1 - si - fl["i"])
            flx = fl["i"] + si
            _tline(ax, flx, fl["p"], n - 1, ley, BULLISH_COLOR, "Lower TL")
            for low in lows:
                ax.plot(low["i"] + si, low["p"], "o", color=BULLISH_COLOR, markersize=5, zorder=5)
    if uey is not None and ley is not None and fhx is not None and flx is not None:
        ax.fill([fhx, n - 1, n - 1, flx], [highs[0]["p"], uey, ley, lows[0]["p"]],
                color=NEUTRAL_COLOR, alpha=0.06, zorder=1)
    apex = pat.get("apex")
    if apex:
        _marker(ax, n - 1, apex, "Apex", NEUTRAL_COLOR, "o", 7)


# ── Rising Wedge ──────────────────────────────────────────────────────
def _ov_rw(ax, df, pat, si, n):
    lb = n - si
    if lb < 10:
        return
    try:
        x = np.arange(lb)
        hs_s, hi = np.polyfit(x, df["High"].values[si:], 1)
        ls_s, li = np.polyfit(x, df["Low"].values[si:], 1)
        hy1, hy2 = float(hi), float(hi + hs_s * (lb - 1))
        ly1, ly2 = float(li), float(li + ls_s * (lb - 1))
        _tline(ax, si, hy1, n - 1, hy2, BEARISH_COLOR, "Upper TL")
        _tline(ax, si, ly1, n - 1, ly2, BEARISH_COLOR, "Lower TL")
        ax.fill([si, n - 1, n - 1, si], [hy1, hy2, ly2, ly1], color=BEARISH_COLOR, alpha=0.06, zorder=1)
    except Exception:
        pass


# ── Falling Wedge ─────────────────────────────────────────────────────
def _ov_fw(ax, df, pat, si, n):
    lb = n - si
    if lb < 10:
        return
    try:
        x = np.arange(lb)
        hs_s, hi = np.polyfit(x, df["High"].values[si:], 1)
        ls_s, li = np.polyfit(x, df["Low"].values[si:], 1)
        hy1, hy2 = float(hi), float(hi + hs_s * (lb - 1))
        ly1, ly2 = float(li), float(li + ls_s * (lb - 1))
        _tline(ax, si, hy1, n - 1, hy2, BULLISH_COLOR, "Upper TL")
        _tline(ax, si, ly1, n - 1, ly2, BULLISH_COLOR, "Lower TL")
        ax.fill([si, n - 1, n - 1, si], [hy1, hy2, ly2, ly1], color=BULLISH_COLOR, alpha=0.06, zorder=1)
    except Exception:
        pass


# ── Bull Flag ─────────────────────────────────────────────────────────
def _ov_bf(ax, df, pat, si, n):
    ft, fb = pat.get("flag_top"), pat.get("flag_bottom")
    ps, pe = si, max(0, n - 10)
    if pe > ps:
        ax.plot([ps, pe], [float(df["Close"].values[ps]), float(df["Close"].values[pe])],
                color=BULLISH_COLOR, linewidth=3, zorder=4, label="Pole")
        _marker(ax, ps, float(df["Close"].values[ps]), "Pole Start", BULLISH_COLOR, "^", 6)
    if ft and fb:
        fx1 = max(0, n - 10)
        ax.axhspan(fb, ft, xmin=fx1 / max(1, n), xmax=1.0, facecolor=NEUTRAL_COLOR, alpha=0.12, zorder=1)
        _hline(ax, ft, fx1, n - 1, NEUTRAL_COLOR, "Flag Top", dash=True, lw=1.5)
        _hline(ax, fb, fx1, n - 1, NEUTRAL_COLOR, "Flag Bottom", dash=True, lw=1.5)


# ── Bear Flag ─────────────────────────────────────────────────────────
def _ov_brf(ax, df, pat, si, n):
    ft, fb = pat.get("flag_top"), pat.get("flag_bottom")
    ps, pe = si, max(0, n - 10)
    if pe > ps:
        ax.plot([ps, pe], [float(df["Close"].values[ps]), float(df["Close"].values[pe])],
                color=BEARISH_COLOR, linewidth=3, zorder=4, label="Pole")
        _marker(ax, ps, float(df["Close"].values[ps]), "Pole Start", BEARISH_COLOR, "v", 6)
    if ft and fb:
        fx1 = max(0, n - 10)
        ax.axhspan(fb, ft, xmin=fx1 / max(1, n), xmax=1.0, facecolor=NEUTRAL_COLOR, alpha=0.12, zorder=1)
        _hline(ax, ft, fx1, n - 1, NEUTRAL_COLOR, "Flag Top", dash=True, lw=1.5)
        _hline(ax, fb, fx1, n - 1, NEUTRAL_COLOR, "Flag Bottom", dash=True, lw=1.5)


# ── Cup and Handle ────────────────────────────────────────────────────
def _ov_cup(ax, df, pat, si, n):
    lr, rr, cb = pat.get("left_rim"), pat.get("right_rim"), pat.get("cup_bottom")
    bo = pat.get("breakout_level")
    hs, ls = _pivots(df.iloc[si:], 4)
    lr_i = _cpiv(hs, lr, si)
    rr_i = _cpiv(hs, rr, si)
    cb_i = _cpiv(ls, cb, si)
    _marker(ax, lr_i, lr, "L.Rim", BULLISH_COLOR, "D", 6)
    _marker(ax, cb_i, cb, "Bottom", NEUTRAL_COLOR, "o", 6)
    _marker(ax, rr_i, rr, "R.Rim", BULLISH_COLOR, "D", 6)
    if lr_i is not None and cb_i is not None and lr and cb:
        ax.plot([lr_i, cb_i], [lr, cb], color=BULLISH_COLOR, linewidth=2, alpha=0.7, zorder=3)
    if cb_i is not None and rr_i is not None and cb and rr:
        ax.plot([cb_i, rr_i], [cb, rr], color=BULLISH_COLOR, linewidth=2, alpha=0.7, zorder=3)
    if bo:
        x1 = lr_i if lr_i else si
        _hline(ax, bo, x1, n - 1, NEUTRAL_COLOR, f"Breakout ₹{bo:.1f}", dash=True)


# ── Sideways Range ────────────────────────────────────────────────────
def _ov_range(ax, df, pat, si, n):
    lb = min(40, n)
    start = n - lb
    seg_high = float(df["High"].values[-lb:].max())
    seg_low = float(df["Low"].values[-lb:].min())
    mid = (seg_high + seg_low) / 2
    ax.axhspan(seg_low, seg_high, facecolor=NEUTRAL_COLOR, alpha=0.08, zorder=1)
    _hline(ax, seg_high, start, n - 1, BEARISH_COLOR, f"Resistance ₹{seg_high:.1f}", dash=True)
    _hline(ax, seg_low, start, n - 1, BULLISH_COLOR, f"Support ₹{seg_low:.1f}", dash=True)
    _hline(ax, mid, start, n - 1, "#ffffff40", "Mid", dash=True, lw=1)


# ── Trend Analysis (Parallel Channel) ────────────────────────────────
def _ov_trend(ax, df, pat, si, n):
    close = pd.Series(df["Close"].values, dtype=float)
    if n >= 20:
        ema20 = close.ewm(span=20, adjust=False).mean().values
        xs = list(range(19, n, max(1, n // 40)))
        ax.plot(xs, [ema20[i] for i in xs], color="#4dabf7", linewidth=1.5, zorder=3, label="EMA 20")
    if n >= 50:
        ema50 = close.ewm(span=50, adjust=False).mean().values
        xs = list(range(49, n, max(1, n // 40)))
        ax.plot(xs, [ema50[i] for i in xs], color="#f783ac", linewidth=1.5, zorder=3, label="EMA 50")
    # Draw parallel channel using linear regression
    if n >= 20:
        try:
            x = np.arange(n)
            slope, intercept = np.polyfit(x, close.values, 1)
            reg_line = slope * x + intercept
            residuals = close.values - reg_line
            upper_offset = np.percentile(residuals, 90)
            lower_offset = np.percentile(residuals, 10)
            ax.plot(x, reg_line + upper_offset, color="#4dabf7", linestyle="--", linewidth=1, alpha=0.6)
            ax.plot(x, reg_line + lower_offset, color="#4dabf7", linestyle="--", linewidth=1, alpha=0.6)
            ax.fill_between(x, reg_line + lower_offset, reg_line + upper_offset,
                            color="#4dabf7", alpha=0.05, zorder=1)
        except Exception:
            pass
    ax.legend(loc="upper left", fontsize=8, facecolor=BG_COLOR, edgecolor="#333355",
              labelcolor=TEXT_COLOR, framealpha=0.9)


# ── Generic fallback ──────────────────────────────────────────────────
def _ov_generic(ax, df, pat, si, n):
    """Fallback: just draw breakout level if available."""
    bl = pat.get("breakout_level")
    if bl:
        _hline(ax, bl, si, n - 1, NEUTRAL_COLOR, f"Breakout ₹{bl:.1f}", dash=True)