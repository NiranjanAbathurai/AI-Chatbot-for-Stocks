/**
 * Chart Drawing Generator — JS port of backend/services/chart_drawings.py + chart_drawings_ext.py
 * Drawing types: line, horizontal, zone, marker, polyline, polygon, arrow
 */

function _piv(highs, lows, w = 5) {
  const hs = [], ls = [], n = highs.length;
  for (let i = w; i < n - w; i++) {
    let isH = true, isL = true;
    for (let j = i - w; j <= i + w; j++) { if (highs[j] > highs[i]) { isH = false; break; } }
    for (let j = i - w; j <= i + w; j++) { if (lows[j] < lows[i]) { isL = false; break; } }
    if (isH) hs.push({ i, p: highs[i] });
    if (isL) ls.push({ i, p: lows[i] });
  }
  return { hs, ls };
}

function _closest(pivots, price, off = 0) {
  if (!pivots || !pivots.length || price == null) return null;
  let best = null, bd = Infinity;
  for (const p of pivots) { const d = Math.abs(p.p - price); if (d < bd) { bd = d; best = p.i + off; } }
  return best;
}

function _mk(d, xi, xp, xl, xc, xs, xsz) {
  if (xi != null && xp) d.push({ type: "marker", x: xi, y: xp, label: xl, color: xc, shape: xs, size: xsz });
}

function _addLevels(drawings, pat, n, closes) {
  const tgt = pat.target, tgt_up = pat.target_up, tgt_down = pat.target_down;
  const inv = pat.invalidation, pt = pat.type || "neutral";
  const cp = pat.current_price || (closes.length > 0 ? closes[closes.length - 1] : null);
  const zs = Math.max(0, n - 8), ze = n - 1;
  if (tgt != null) {
    const tc = pt === "bullish" ? "#51cf66" : pt === "bearish" ? "#ff6b6b" : "#ffd700";
    drawings.push({ type: "horizontal", y: tgt, x1: zs, x2: ze, color: tc, width: 2, dash: true, label: `Target ${tgt}` });
    if (cp) {
      const zh = Math.abs(tgt - cp) * 0.06;
      drawings.push({ type: "zone", y1: tgt - zh, y2: tgt + zh, x1: zs, x2: ze, color: tc + "18", border: tc + "50" });
      drawings.push({ type: "arrow", x: ze, y1: cp, y2: tgt, color: tc, width: 2 });
    }
  }
  if (tgt_up != null) drawings.push({ type: "horizontal", y: tgt_up, x1: zs, x2: ze, color: "#51cf66", width: 2, dash: true, label: `Target Up ${tgt_up}` });
  if (tgt_down != null) drawings.push({ type: "horizontal", y: tgt_down, x1: zs, x2: ze, color: "#ff6b6b", width: 2, dash: true, label: `Target Down ${tgt_down}` });
  if (inv != null) {
    drawings.push({ type: "horizontal", y: inv, x1: zs, x2: ze, color: "#ff4444", width: 2, dash: true, label: `SL ${inv}` });
    if (cp) {
      const zh = Math.abs(inv - cp) * 0.06;
      drawings.push({ type: "zone", y1: inv - zh, y2: inv + zh, x1: zs, x2: ze, color: "#ff444420", border: "#ff444460" });
    }
  }
  if (cp) drawings.push({ type: "horizontal", y: cp, x1: Math.max(0, n - 5), x2: ze, color: "#ffffff", width: 1.5, dash: false, label: `CMP ${cp}` });
}

function _drawHS(pat, highs, lows, n) {
  const d = [], si = pat.pattern_start_idx || 0;
  const ls_p = pat.left_shoulder, hd_p = pat.head, rs_p = pat.right_shoulder;
  const nl_p = pat.dynamic_neckline || pat.neckline;
  const n1_p = pat.neckline_1, n2_p = pat.neckline_2;
  const { hs, ls } = _piv(highs.slice(si), lows.slice(si), 4);
  const ls_i = _closest(hs, ls_p, si), hd_i = _closest(hs, hd_p, si);
  const rs_i = rs_p ? _closest(hs, rs_p, si) : null;
  const t1_i = n1_p ? _closest(ls, n1_p, si) : null;
  const t2_i = n2_p ? _closest(ls, n2_p, si) : null;
  const pts = [];
  if (ls_i != null && ls_p) pts.push({ x: ls_i, y: ls_p });
  if (t1_i != null && n1_p) pts.push({ x: t1_i, y: n1_p });
  if (hd_i != null && hd_p) pts.push({ x: hd_i, y: hd_p });
  if (t2_i != null && n2_p) pts.push({ x: t2_i, y: n2_p });
  if (rs_i != null && rs_p) pts.push({ x: rs_i, y: rs_p });
  if (pts.length >= 3) d.push({ type: "polyline", points: pts, color: "#ff6b6b", width: 2.5, dash: false, label: "H&S" });
  _mk(d, ls_i, ls_p, "LS", "#ff9f43", "diamond", 7);
  _mk(d, hd_i, hd_p, "HEAD", "#ff4444", "diamond", 9);
  _mk(d, rs_i, rs_p, "RS", "#ff9f43", "diamond", 7);
  if (nl_p) {
    const ns = t1_i || ls_i || si, ne = Math.min(n - 1, (rs_i || n - 1) + 8);
    if (n1_p && n2_p && t1_i && t2_i) d.push({ type: "line", x1: t1_i, y1: n1_p, x2: ne, y2: nl_p, color: "#ffd700", width: 2.5, dash: true, label: `Neckline ${nl_p}` });
    else d.push({ type: "horizontal", y: nl_p, x1: ns, x2: ne, color: "#ffd700", width: 2.5, dash: true, label: `Neckline ${nl_p}` });
  }
  return d;
}

function _drawIHS(pat, highs, lows, n) {
  const d = [], si = pat.pattern_start_idx || 0;
  const ls_p = pat.left_shoulder, hd_p = pat.head, rs_p = pat.right_shoulder;
  const nl_p = pat.dynamic_neckline || pat.neckline;
  const n1_p = pat.neckline_1, n2_p = pat.neckline_2;
  const { hs, ls } = _piv(highs.slice(si), lows.slice(si), 4);
  const ls_i = _closest(ls, ls_p, si), hd_i = _closest(ls, hd_p, si);
  const rs_i = rs_p ? _closest(ls, rs_p, si) : null;
  const p1_i = n1_p ? _closest(hs, n1_p, si) : null;
  const p2_i = n2_p ? _closest(hs, n2_p, si) : null;
  const pts = [];
  if (ls_i != null && ls_p) pts.push({ x: ls_i, y: ls_p });
  if (p1_i != null && n1_p) pts.push({ x: p1_i, y: n1_p });
  if (hd_i != null && hd_p) pts.push({ x: hd_i, y: hd_p });
  if (p2_i != null && n2_p) pts.push({ x: p2_i, y: n2_p });
  if (rs_i != null && rs_p) pts.push({ x: rs_i, y: rs_p });
  if (pts.length >= 3) d.push({ type: "polyline", points: pts, color: "#51cf66", width: 2.5, dash: false, label: "Inv H&S" });
  _mk(d, ls_i, ls_p, "LS", "#51cf66", "diamond", 7);
  _mk(d, hd_i, hd_p, "HEAD", "#40c057", "diamond", 9);
  _mk(d, rs_i, rs_p, "RS", "#51cf66", "diamond", 7);
  if (nl_p) {
    const ns = p1_i || ls_i || si, ne = Math.min(n - 1, (rs_i || n - 1) + 8);
    if (n1_p && n2_p && p1_i && p2_i) d.push({ type: "line", x1: p1_i, y1: n1_p, x2: ne, y2: nl_p, color: "#ffd700", width: 2.5, dash: true, label: `Neckline ${nl_p}` });
    else d.push({ type: "horizontal", y: nl_p, x1: ns, x2: ne, color: "#ffd700", width: 2.5, dash: true, label: `Neckline ${nl_p}` });
  }
  return d;
}

function _drawDT(pat, highs, lows, n) {
  const d = [], si = pat.pattern_start_idx || 0;
  const p1 = pat.peak_1, p2 = pat.peak_2, nl = pat.neckline;
  const { hs, ls } = _piv(highs.slice(si), lows.slice(si), 3);
  const p1_i = _closest(hs, p1, si), p2_i = _closest(hs, p2, si), nl_i = _closest(ls, nl, si);
  const pts = [];
  if (p1_i != null && p1) pts.push({ x: p1_i, y: p1 });
  if (nl_i != null && nl) pts.push({ x: nl_i, y: nl });
  if (p2_i != null && p2) pts.push({ x: p2_i, y: p2 });
  if (pts.length >= 3) d.push({ type: "polyline", points: pts, color: "#ff6b6b", width: 2.5, dash: false, label: "Double Top" });
  _mk(d, p1_i, p1, "P1", "#ff6b6b", "triangle_down", 7);
  _mk(d, p2_i, p2, "P2", "#ff6b6b", "triangle_down", 7);
  if (p1 && p2) {
    const rl = Math.max(p1, p2), x1 = p1_i || si, x2 = Math.min(n - 1, (p2_i || n - 1) + 5);
    d.push({ type: "zone", y1: Math.min(p1, p2), y2: rl, x1, x2, color: "#ff6b6b15", border: "#ff6b6b40" });
    d.push({ type: "horizontal", y: rl, x1, x2, color: "#ff6b6b", width: 2, dash: false, label: `Resistance ${rl}` });
  }
  if (nl) {
    const x1 = nl_i || p1_i || si, x2 = Math.min(n - 1, (p2_i || n - 1) + 8);
    d.push({ type: "horizontal", y: nl, x1, x2, color: "#ffd700", width: 2.5, dash: true, label: `Neckline ${nl}` });
  }
  return d;
}

function _drawDB(pat, highs, lows, n) {
  const d = [], si = pat.pattern_start_idx || 0;
  const t1 = pat.trough_1, t2 = pat.trough_2, nl = pat.neckline;
  const { hs, ls } = _piv(highs.slice(si), lows.slice(si), 3);
  const t1_i = _closest(ls, t1, si), t2_i = _closest(ls, t2, si), nl_i = _closest(hs, nl, si);
  const pts = [];
  if (t1_i != null && t1) pts.push({ x: t1_i, y: t1 });
  if (nl_i != null && nl) pts.push({ x: nl_i, y: nl });
  if (t2_i != null && t2) pts.push({ x: t2_i, y: t2 });
  if (pts.length >= 3) d.push({ type: "polyline", points: pts, color: "#51cf66", width: 2.5, dash: false, label: "Double Bottom" });
  _mk(d, t1_i, t1, "T1", "#51cf66", "triangle_up", 7);
  _mk(d, t2_i, t2, "T2", "#51cf66", "triangle_up", 7);
  if (t1 && t2) {
    const sl = Math.min(t1, t2), x1 = t1_i || si, x2 = Math.min(n - 1, (t2_i || n - 1) + 5);
    d.push({ type: "zone", y1: sl, y2: Math.max(t1, t2), x1, x2, color: "#51cf6615", border: "#51cf6640" });
    d.push({ type: "horizontal", y: sl, x1, x2, color: "#51cf66", width: 2, dash: false, label: `Support ${sl}` });
  }
  if (nl) {
    const x1 = nl_i || t1_i || si, x2 = Math.min(n - 1, (t2_i || n - 1) + 8);
    d.push({ type: "horizontal", y: nl, x1, x2, color: "#ffd700", width: 2.5, dash: true, label: `Neckline ${nl}` });
  }
  return d;
}

function _drawAT(pat, highs, lows, n) {
  const d = [], si = pat.pattern_start_idx || 0, res = pat.resistance || pat.breakout_level;
  const { ls: lowPivots } = _piv(highs.slice(si), lows.slice(si), 3);
  if (res) d.push({ type: "horizontal", y: res, x1: si, x2: n - 1, color: "#ff6b6b", width: 2.5, dash: false, label: `Resistance ${res}` });
  if (lowPivots.length >= 2 && res) {
    const fl = lowPivots[0], ll = lowPivots[lowPivots.length - 1];
    if (ll.i !== fl.i) {
      const slope = (ll.p - fl.p) / (ll.i - fl.i), ey = fl.p + slope * (n - 1 - si - fl.i);
      const fx = fl.i + si;
      d.push({ type: "line", x1: fx, y1: fl.p, x2: n - 1, y2: ey, color: "#51cf66", width: 2.5, dash: false, label: "Rising Support" });
      d.push({ type: "polygon", points: [{ x: fx, y: fl.p }, { x: fx, y: res }, { x: n - 1, y: res }, { x: n - 1, y: ey }], color: "#51cf6612", border: "#51cf6630" });
    }
  }
  return d;
}

function _drawDTR(pat, highs, lows, n) {
  const d = [], si = pat.pattern_start_idx || 0, sup = pat.support || pat.breakout_level;
  const { hs: highPivots } = _piv(highs.slice(si), lows.slice(si), 3);
  if (sup) d.push({ type: "horizontal", y: sup, x1: si, x2: n - 1, color: "#51cf66", width: 2.5, dash: false, label: `Support ${sup}` });
  if (highPivots.length >= 2 && sup) {
    const fh = highPivots[0], lh = highPivots[highPivots.length - 1];
    if (lh.i !== fh.i) {
      const slope = (lh.p - fh.p) / (lh.i - fh.i), ey = fh.p + slope * (n - 1 - si - fh.i);
      const fx = fh.i + si;
      d.push({ type: "line", x1: fx, y1: fh.p, x2: n - 1, y2: ey, color: "#ff6b6b", width: 2.5, dash: false, label: "Falling Resistance" });
      d.push({ type: "polygon", points: [{ x: fx, y: fh.p }, { x: fx, y: sup }, { x: n - 1, y: sup }, { x: n - 1, y: ey }], color: "#ff6b6b12", border: "#ff6b6b30" });
    }
  }
  return d;
}

function _drawST(pat, highs, lows, n) {
  const d = [], si = pat.pattern_start_idx || 0;
  const { hs: hp, ls: lp } = _piv(highs.slice(si), lows.slice(si), 3);
  if (hp.length >= 2) {
    const fh = hp[0], lh = hp[hp.length - 1];
    if (lh.i !== fh.i) {
      const slope = (lh.p - fh.p) / (lh.i - fh.i), uey = fh.p + slope * (n - 1 - si - fh.i);
      d.push({ type: "line", x1: fh.i + si, y1: fh.p, x2: n - 1, y2: uey, color: "#ff6b6b", width: 2.5, dash: false, label: "Upper TL" });
    }
  }
  if (lp.length >= 2) {
    const fl = lp[0], ll = lp[lp.length - 1];
    if (ll.i !== fl.i) {
      const slope = (ll.p - fl.p) / (ll.i - fl.i), ley = fl.p + slope * (n - 1 - si - fl.i);
      d.push({ type: "line", x1: fl.i + si, y1: fl.p, x2: n - 1, y2: ley, color: "#51cf66", width: 2.5, dash: false, label: "Lower TL" });
    }
  }
  if (pat.apex) _mk(d, n - 1, pat.apex, "Apex", "#ffd700", "circle", 6);
  return d;
}

function _drawWedge(pat, highs, lows, n, rising) {
  const d = [], si = pat.pattern_start_idx || 0, lb = n - si;
  if (lb < 10) return d;
  const c = rising ? "#ff6b6b" : "#51cf66";
  // Simple: use first and last values of the slice for trendlines
  const hSlice = highs.slice(si), lSlice = lows.slice(si);
  const hy1 = hSlice[0], hy2 = hSlice[hSlice.length - 1];
  const ly1 = lSlice[0], ly2 = lSlice[lSlice.length - 1];
  d.push({ type: "line", x1: si, y1: hy1, x2: n - 1, y2: hy2, color: c, width: 2.5, dash: false, label: "Upper TL" });
  d.push({ type: "line", x1: si, y1: ly1, x2: n - 1, y2: ly2, color: c, width: 2.5, dash: false, label: "Lower TL" });
  d.push({ type: "polygon", points: [{ x: si, y: hy1 }, { x: n - 1, y: hy2 }, { x: n - 1, y: ly2 }, { x: si, y: ly1 }], color: c + "10", border: c + "30" });
  return d;
}

function _drawFlag(pat, closes, n, bullish) {
  const d = [], si = pat.pattern_start_idx || 0;
  const ft = pat.flag_top, fb = pat.flag_bottom;
  const ps = si, pe = Math.max(0, n - 10);
  if (pe > ps) {
    const pc = bullish ? "#51cf66" : "#ff6b6b";
    d.push({ type: "line", x1: ps, y1: closes[ps], x2: pe, y2: closes[pe], color: pc, width: 3, dash: false, label: "Pole" });
  }
  if (ft && fb) {
    const fx1 = Math.max(0, n - 10);
    d.push({ type: "zone", y1: fb, y2: ft, x1: fx1, x2: n - 1, color: "#ffd70020", border: "#ffd70060" });
    d.push({ type: "horizontal", y: ft, x1: fx1, x2: n - 1, color: "#ffd700", width: 1.5, dash: true, label: "Flag Top" });
    d.push({ type: "horizontal", y: fb, x1: fx1, x2: n - 1, color: "#ffd700", width: 1.5, dash: true, label: "Flag Bottom" });
  }
  return d;
}

function _drawCup(pat, highs, lows, n) {
  const d = [], si = pat.pattern_start_idx || 0;
  const lr = pat.left_rim, rr = pat.right_rim, cb = pat.cup_bottom, bo = pat.breakout_level;
  const { hs, ls } = _piv(highs.slice(si), lows.slice(si), 4);
  const lr_i = _closest(hs, lr, si), rr_i = _closest(hs, rr, si), cb_i = _closest(ls, cb, si);
  _mk(d, lr_i, lr, "L.Rim", "#51cf66", "diamond", 6);
  _mk(d, cb_i, cb, "Bottom", "#ffd700", "circle", 6);
  _mk(d, rr_i, rr, "R.Rim", "#51cf66", "diamond", 6);
  if (lr_i != null && cb_i != null && lr && cb) d.push({ type: "line", x1: lr_i, y1: lr, x2: cb_i, y2: cb, color: "#51cf6680", width: 2, dash: false });
  if (cb_i != null && rr_i != null && cb && rr) d.push({ type: "line", x1: cb_i, y1: cb, x2: rr_i, y2: rr, color: "#51cf6680", width: 2, dash: false });
  if (bo) d.push({ type: "horizontal", y: bo, x1: lr_i || si, x2: n - 1, color: "#ffd700", width: 2, dash: true, label: `Breakout ${bo}` });
  return d;
}

function _drawRange(pat, highs, lows, n) {
  const d = [], lb = Math.min(40, n), start = n - lb;
  const segH = Math.max(...highs.slice(-lb)), segL = Math.min(...lows.slice(-lb)), mid = (segH + segL) / 2;
  d.push({ type: "zone", y1: segL, y2: segH, x1: start, x2: n - 1, color: "#ffd70015", border: "#ffd70040" });
  d.push({ type: "horizontal", y: segH, x1: start, x2: n - 1, color: "#ff6b6b", width: 2, dash: true, label: `Resistance ${segH.toFixed(1)}` });
  d.push({ type: "horizontal", y: segL, x1: start, x2: n - 1, color: "#51cf66", width: 2, dash: true, label: `Support ${segL.toFixed(1)}` });
  d.push({ type: "horizontal", y: mid, x1: start, x2: n - 1, color: "#ffffff40", width: 1, dash: true, label: "Mid" });
  return d;
}

function _drawTrend(pat, closes, n) {
  const d = [];
  function ema(arr, span) { const k = 2 / (span + 1); let e = arr[0]; for (let i = 1; i < arr.length; i++) e = arr[i] * k + e * (1 - k); return e; }
  if (n >= 20) {
    const vals = [], k = 2 / 21; let e = closes[0];
    for (let i = 0; i < n; i++) { e = closes[i] * k + e * (1 - k); vals.push(e); }
    const pts = [];
    const step = Math.max(1, Math.floor(n / 40));
    for (let i = 19; i < n; i += step) pts.push({ x: i, y: Math.round(vals[i] * 100) / 100 });
    if (pts.length) d.push({ type: "polyline", points: pts, color: "#4dabf7", width: 1.5, dash: false, label: "EMA 20" });
  }
  if (n >= 50) {
    const vals = [], k = 2 / 51; let e = closes[0];
    for (let i = 0; i < n; i++) { e = closes[i] * k + e * (1 - k); vals.push(e); }
    const pts = [];
    const step = Math.max(1, Math.floor(n / 40));
    for (let i = 49; i < n; i += step) pts.push({ x: i, y: Math.round(vals[i] * 100) / 100 });
    if (pts.length) d.push({ type: "polyline", points: pts, color: "#f783ac", width: 1.5, dash: false, label: "EMA 50" });
  }
  return d;
}

/**
 * Generate pattern drawings for a detected pattern.
 * @param {Object} pattern - Pattern object from detector
 * @param {number[]} closes
 * @param {number[]} highs
 * @param {number[]} lows
 * @param {number} n - total bars
 * @returns {Array<Object>} drawing instructions
 */
export function generatePatternDrawings(pattern, closes, highs, lows, n) {
  let drawings = [];
  const name = pattern.pattern || "";
  try {
    if (name.includes("Head & Shoulders") && !name.includes("Inverse")) drawings = _drawHS(pattern, highs, lows, n);
    else if (name.includes("Inverse Head & Shoulders")) drawings = _drawIHS(pattern, highs, lows, n);
    else if (name.includes("Double Top")) drawings = _drawDT(pattern, highs, lows, n);
    else if (name.includes("Double Bottom")) drawings = _drawDB(pattern, highs, lows, n);
    else if (name.includes("Ascending Triangle")) drawings = _drawAT(pattern, highs, lows, n);
    else if (name.includes("Descending Triangle")) drawings = _drawDTR(pattern, highs, lows, n);
    else if (name.includes("Symmetrical Triangle")) drawings = _drawST(pattern, highs, lows, n);
    else if (name.includes("Rising Wedge")) drawings = _drawWedge(pattern, highs, lows, n, true);
    else if (name.includes("Falling Wedge")) drawings = _drawWedge(pattern, highs, lows, n, false);
    else if (name.includes("Bull") && name.includes("Flag")) drawings = _drawFlag(pattern, closes, n, true);
    else if (name.includes("Bear") && name.includes("Flag")) drawings = _drawFlag(pattern, closes, n, false);
    else if (name.includes("Cup")) drawings = _drawCup(pattern, highs, lows, n);
    else if (name.includes("Sideways") || name.includes("Range")) drawings = _drawRange(pattern, highs, lows, n);
    else if (name.includes("Trend")) drawings = _drawTrend(pattern, closes, n);
    _addLevels(drawings, pattern, n, closes);
  } catch (e) {
    console.warn(`Drawing error for ${name}: ${e.message}`);
  }
  return drawings;
}
