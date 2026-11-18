/**
 * Pattern Chart Viewer — Interactive Candlestick + Pattern Drawings
 * Supports: pan (drag), zoom (scroll), polygon, arrow, polyline, markers
 */

var chartLoading = false;

function openPatternChart(ticker, stockName, detector) {
    if (chartLoading) return;
    var modal = document.getElementById("chartModal");
    if (!modal) return;
    var titleEl = document.getElementById("chartModalTitle");
    var bodyEl = document.getElementById("chartModalBody");
    var tfSelect = document.getElementById("chartTimeframe");
    var tf = tfSelect ? tfSelect.value : "1d";
    titleEl.textContent = "\uD83D\uDCCA " + stockName + " \u2014 Pattern Chart";
    bodyEl.innerHTML = '<div class="chart-loading"><div class="chart-spinner"></div><span>Loading chart data...</span></div>';
    modal.classList.add("visible");
    document.body.style.overflow = "hidden";
    modal.dataset.ticker = ticker;
    modal.dataset.stockName = stockName;
    modal.dataset.detector = detector || "developing";
    _fetchAndRenderChart(ticker, stockName, tf, detector || "developing");
}

function _fetchAndRenderChart(ticker, stockName, timeframe, detector) {
    chartLoading = true;
    var bodyEl = document.getElementById("chartModalBody");
    fetch(API_BASE + "/api/chart/pattern-chart?ticker=" + encodeURIComponent(ticker) + "&timeframe=" + encodeURIComponent(timeframe) + "&max_bars=80&detector=" + encodeURIComponent(detector))
        .then(function(res) {
            if (!res.ok) return res.json().then(function(e) { throw new Error(e.detail || "Failed to load chart"); });
            return res.json();
        })
        .then(function(data) {
            chartLoading = false;
            if (!data.ohlc || data.ohlc.length === 0) {
                bodyEl.innerHTML = '<div class="chart-error">No chart data available for ' + escapeHtml(stockName) + '</div>';
                return;
            }
            _renderChartCanvas(data, bodyEl);
        })
        .catch(function(err) {
            chartLoading = false;
            bodyEl.innerHTML = '<div class="chart-error">\u274C ' + escapeHtml(err.message) + '</div>';
        });
}

function changeChartTimeframe() {
    var modal = document.getElementById("chartModal");
    if (!modal) return;
    var tfSelect = document.getElementById("chartTimeframe");
    var tf = tfSelect ? tfSelect.value : "1d";
    var ticker = modal.dataset.ticker;
    var stockName = modal.dataset.stockName;
    var detector = modal.dataset.detector;
    if (!ticker) return;
    var bodyEl = document.getElementById("chartModalBody");
    bodyEl.innerHTML = '<div class="chart-loading"><div class="chart-spinner"></div><span>Loading ' + tf + ' chart...</span></div>';
    _fetchAndRenderChart(ticker, stockName, tf, detector);
}

function closeChartModal() {
    var modal = document.getElementById("chartModal");
    if (modal) { modal.classList.remove("visible"); document.body.style.overflow = ""; }
}

function _renderChartCanvas(data, container) {
    var ohlc = data.ohlc, patterns = data.patterns || [], n = ohlc.length;

    // Pattern info badges
    var patternInfo = "";
    if (patterns.length > 0) {
        patternInfo = '<div class="chart-patterns-info">';
        for (var pi = 0; pi < patterns.length; pi++) {
            var pat = patterns[pi];
            var pEmoji = pat.type === "bullish" ? "\uD83D\uDFE2" : pat.type === "bearish" ? "\uD83D\uDD34" : "\uD83D\uDFE1";
            var stageStr = pat.stage ? ' <span class="chart-pat-stage">' + escapeHtml(pat.stage) + '</span>' : '';
            var confStr = pat.structure_confidence ? ' <span class="chart-pat-conf">' + pat.structure_confidence + '%</span>' : '';
            patternInfo += '<div class="chart-pat-badge ' + (pat.type || "neutral") + '">' + pEmoji + ' ' + escapeHtml(pat.pattern) + stageStr + confStr + '</div>';
        }
        patternInfo += '</div>';
    }

    container.innerHTML = patternInfo +
        '<div class="chart-canvas-wrapper" style="position:relative;overflow:hidden;cursor:crosshair;touch-action:none;"><canvas id="patternChartCanvas"></canvas></div>' +
        '<div class="chart-legend" id="chartLegend"></div>' +
        '<div class="chart-price-info" id="chartPriceInfo">CMP: \u20B9' + (data.current_price || "N/A") + '</div>' +
        '<div style="text-align:center;font-size:10px;color:#686880;margin-top:2px;">Scroll to zoom \u2022 Drag to pan \u2022 Hover for OHLC</div>';

    var canvas = document.getElementById("patternChartCanvas");
    if (!canvas) return;

    var wrapper = canvas.parentElement;
    var dpr = window.devicePixelRatio || 1;
    var displayWidth = wrapper.clientWidth;
    var displayHeight = Math.min(450, Math.max(300, displayWidth * 0.55));
    canvas.style.width = displayWidth + "px";
    canvas.style.height = displayHeight + "px";
    canvas.width = displayWidth * dpr;
    canvas.height = displayHeight * dpr;

    // Pan/Zoom state
    var viewStart = 0, viewEnd = n;
    var isDragging = false, dragStartX = 0, dragStartVS = 0;

    function draw() {
        var ctx = canvas.getContext("2d");
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        var W = displayWidth, H = displayHeight;
        var pL = 65, pR = 20, pT = 18, pB = 32;
        var cW = W - pL - pR, cH = H - pT - pB;
        var vn = Math.max(1, viewEnd - viewStart);
        var vs = Math.max(0, Math.floor(viewStart)), ve = Math.min(n, Math.ceil(viewEnd));

        // Price range
        var minP = Infinity, maxP = -Infinity;
        for (var i = vs; i < ve; i++) {
            if (ohlc[i].l !== null && ohlc[i].l < minP) minP = ohlc[i].l;
            if (ohlc[i].h !== null && ohlc[i].h > maxP) maxP = ohlc[i].h;
        }
        for (var pi2 = 0; pi2 < patterns.length; pi2++) {
            var dws = patterns[pi2].drawings || [];
            for (var di = 0; di < dws.length; di++) {
                var dd = dws[di];
                if (dd.y != null) { minP = Math.min(minP, dd.y); maxP = Math.max(maxP, dd.y); }
                if (dd.y1 != null) { minP = Math.min(minP, dd.y1); maxP = Math.max(maxP, dd.y1); }
                if (dd.y2 != null) { minP = Math.min(minP, dd.y2); maxP = Math.max(maxP, dd.y2); }
                if (dd.points) for (var pp = 0; pp < dd.points.length; pp++) { minP = Math.min(minP, dd.points[pp].y); maxP = Math.max(maxP, dd.points[pp].y); }
            }
        }
        var pRange = maxP - minP;
        minP -= pRange * 0.06; maxP += pRange * 0.06; pRange = maxP - minP;

        function xP(idx) { return pL + ((idx - viewStart) + 0.5) * (cW / vn); }
        function yP(price) { return pT + cH - ((price - minP) / pRange) * cH; }
        var bW = Math.max(2, Math.min(14, (cW / vn) * 0.7));

        // Background
        ctx.fillStyle = "#0f0f14"; ctx.fillRect(0, 0, W, H);

        // Grid
        ctx.strokeStyle = "#ffffff0a"; ctx.lineWidth = 0.5;
        for (var g = 0; g <= 6; g++) {
            var gy = pT + (cH / 6) * g;
            ctx.beginPath(); ctx.moveTo(pL, gy); ctx.lineTo(W - pR, gy); ctx.stroke();
            ctx.fillStyle = "#6868808c"; ctx.font = "10px 'Segoe UI',sans-serif"; ctx.textAlign = "right";
            ctx.fillText("\u20B9" + (maxP - (pRange / 6) * g).toFixed(1), pL - 5, gy + 3);
        }

        // X-axis dates
        ctx.fillStyle = "#6868808c"; ctx.font = "9px 'Segoe UI',sans-serif"; ctx.textAlign = "center";
        var lbl = Math.max(1, Math.floor(vn / 8));
        for (var xi = vs; xi < ve; xi += lbl) {
            if (ohlc[xi] && ohlc[xi].t) {
                try { var ds = new Date(ohlc[xi].t).toLocaleDateString("en-IN", {day:"numeric",month:"short"}); ctx.fillText(ds, xP(xi), H - pB + 18); } catch(e) {}
            }
        }

        // Pattern overlays (behind candles)
        var legend = [];
        for (var pi3 = 0; pi3 < patterns.length; pi3++) {
            var pDraw = patterns[pi3].drawings || [];
            for (var dj = 0; dj < pDraw.length; dj++) _drawOv(ctx, pDraw[dj], xP, yP, n, bW, legend, pL, W - pR);
        }

        // Candlesticks
        for (var ci = vs; ci < ve; ci++) {
            var bar = ohlc[ci];
            if (bar.o === null || bar.c === null) continue;
            var gr = bar.c >= bar.o;
            var cx = xP(ci);
            if (bar.h !== null && bar.l !== null) {
                ctx.strokeStyle = gr ? "#00d26a90" : "#ff475790"; ctx.lineWidth = 1;
                ctx.beginPath(); ctx.moveTo(cx, yP(bar.h)); ctx.lineTo(cx, yP(bar.l)); ctx.stroke();
            }
            var bTop = yP(Math.max(bar.o, bar.c)), bBot = yP(Math.min(bar.o, bar.c));
            ctx.fillStyle = gr ? "#00d26a" : "#ff4757";
            ctx.fillRect(cx - bW/2, bTop, bW, Math.max(1, bBot - bTop));
        }

        // Legend
        var lEl = document.getElementById("chartLegend");
        if (lEl && legend.length > 0) {
            var seen = {}, lH = "";
            for (var li = 0; li < legend.length; li++) {
                if (!legend[li].label || seen[legend[li].label]) continue;
                seen[legend[li].label] = true;
                lH += '<span class="chart-legend-item"><span class="chart-legend-color" style="background:' + legend[li].color + '"></span>' + escapeHtml(legend[li].label) + '</span>';
            }
            lEl.innerHTML = lH;
        }
    }

    draw();

    // Zoom (scroll)
    canvas.addEventListener("wheel", function(e) {
        e.preventDefault();
        var zf = e.deltaY > 0 ? 1.15 : 0.87;
        var rect = canvas.getBoundingClientRect();
        var mx = e.clientX - rect.left;
        var ratio = Math.max(0, Math.min(1, (mx - 65) / (displayWidth - 85)));
        var vn = viewEnd - viewStart;
        var newVn = Math.max(10, Math.min(n, vn * zf));
        var center = viewStart + vn * ratio;
        viewStart = Math.max(0, center - newVn * ratio);
        viewEnd = Math.min(n, viewStart + newVn);
        if (viewStart < 0) { viewEnd -= viewStart; viewStart = 0; }
        if (viewEnd > n) { viewStart -= (viewEnd - n); viewEnd = n; }
        viewStart = Math.max(0, viewStart);
        draw();
    }, {passive: false});

    // Pan (drag)
    canvas.addEventListener("mousedown", function(e) { isDragging = true; dragStartX = e.clientX; dragStartVS = viewStart; canvas.style.cursor = "grabbing"; });
    canvas.addEventListener("mousemove", function(e) {
        var rect = canvas.getBoundingClientRect(), mx = e.clientX - rect.left;
        var cW = displayWidth - 85, vn = viewEnd - viewStart;
        if (isDragging) {
            var dx = e.clientX - dragStartX;
            var bp = -(dx / cW) * vn;
            var ns = Math.max(0, Math.min(n - vn, dragStartVS + bp));
            viewStart = ns; viewEnd = ns + vn; draw();
        }
        var barIdx = Math.floor(((mx - 65) / cW) * vn + viewStart);
        if (barIdx >= 0 && barIdx < n) {
            var b2 = ohlc[barIdx], infoEl = document.getElementById("chartPriceInfo");
            if (infoEl && b2 && b2.c !== null) {
                var di = ""; if (b2.t) { try { di = new Date(b2.t).toLocaleDateString("en-IN",{day:"numeric",month:"short",year:"numeric"}); } catch(e2) { di = b2.t; } }
                infoEl.innerHTML = di + " | O: \u20B9" + (b2.o||0).toFixed(2) + " H: \u20B9" + (b2.h||0).toFixed(2) + " L: \u20B9" + (b2.l||0).toFixed(2) + " C: \u20B9" + (b2.c||0).toFixed(2);
            }
        }
    });
    canvas.addEventListener("mouseup", function() { isDragging = false; canvas.style.cursor = "crosshair"; });
    canvas.addEventListener("mouseleave", function() { isDragging = false; canvas.style.cursor = "crosshair"; });

    // Touch pan
    var tSX = 0, tVS = 0;
    canvas.addEventListener("touchstart", function(e) { if (e.touches.length === 1) { tSX = e.touches[0].clientX; tVS = viewStart; } }, {passive:true});
    canvas.addEventListener("touchmove", function(e) {
        if (e.touches.length === 1) {
            var dx = e.touches[0].clientX - tSX, cW = displayWidth - 85, vn = viewEnd - viewStart;
            var ns = Math.max(0, Math.min(n - vn, tVS - (dx / cW) * vn));
            viewStart = ns; viewEnd = ns + vn; draw();
        }
    }, {passive:true});
}

function _drawOv(ctx, d, xP, yP, n, bW, legend, clipL, clipR) {
    if (!d || !d.type) return;
    ctx.save();

    if (d.type === "line") {
        var x1 = xP(d.x1), x2 = xP(d.x2);
        ctx.strokeStyle = d.color || "#ffd700"; ctx.lineWidth = d.width || 1.5;
        if (d.dash) ctx.setLineDash([6, 4]);
        ctx.beginPath(); ctx.moveTo(x1, yP(d.y1)); ctx.lineTo(x2, yP(d.y2)); ctx.stroke();
        ctx.setLineDash([]);
        if (d.label) { _drawLabel(ctx, d.label, x2 + 4, yP(d.y2), d.color || "#ffd700"); legend.push({label: d.label, color: d.color || "#ffd700"}); }
    }

    else if (d.type === "horizontal") {
        var hx1 = xP(d.x1 != null ? d.x1 : 0), hx2 = xP(d.x2 != null ? d.x2 : n-1);
        var hy = yP(d.y);
        ctx.strokeStyle = d.color || "#ffd700"; ctx.lineWidth = d.width || 1;
        if (d.dash) ctx.setLineDash([5, 3]);
        ctx.beginPath(); ctx.moveTo(hx1, hy); ctx.lineTo(hx2, hy); ctx.stroke();
        ctx.setLineDash([]);
        if (d.label) { _drawLabel(ctx, d.label, hx2 + 4, hy - 1, d.color || "#ffd700"); legend.push({label: d.label, color: d.color || "#ffd700"}); }
    }

    else if (d.type === "zone") {
        var zx1 = xP(d.x1 != null ? d.x1 : 0) - bW;
        var zx2 = xP(d.x2 != null ? d.x2 : n-1) + bW;
        var zy1 = yP(d.y2), zy2 = yP(d.y1);
        ctx.fillStyle = d.color || "rgba(255,215,0,0.08)";
        ctx.fillRect(zx1, zy1, zx2 - zx1, zy2 - zy1);
        if (d.border) { ctx.strokeStyle = d.border; ctx.lineWidth = 0.5; ctx.strokeRect(zx1, zy1, zx2 - zx1, zy2 - zy1); }
    }

    else if (d.type === "marker") {
        var mx = xP(d.x), my = yP(d.y);
        var sz = d.size || 5;
        ctx.fillStyle = d.color || "#ffd700";
        if (d.shape === "diamond") {
            ctx.beginPath(); ctx.moveTo(mx, my-sz); ctx.lineTo(mx+sz, my); ctx.lineTo(mx, my+sz); ctx.lineTo(mx-sz, my); ctx.closePath(); ctx.fill();
        } else if (d.shape === "triangle_up") {
            ctx.beginPath(); ctx.moveTo(mx, my-sz); ctx.lineTo(mx+sz, my+sz); ctx.lineTo(mx-sz, my+sz); ctx.closePath(); ctx.fill();
        } else if (d.shape === "triangle_down") {
            ctx.beginPath(); ctx.moveTo(mx, my+sz); ctx.lineTo(mx+sz, my-sz); ctx.lineTo(mx-sz, my-sz); ctx.closePath(); ctx.fill();
        } else {
            ctx.beginPath(); ctx.arc(mx, my, sz, 0, Math.PI*2); ctx.fill();
        }
        if (d.label) { _drawLabel(ctx, d.label, mx, my - sz - 5, d.color || "#ffd700", "center"); legend.push({label: d.label, color: d.color || "#ffd700"}); }
    }

    else if (d.type === "polyline") {
        var pts = d.points || [];
        if (pts.length < 2) { ctx.restore(); return; }
        ctx.strokeStyle = d.color || "#4dabf7"; ctx.lineWidth = d.width || 1.5;
        if (d.dash) ctx.setLineDash([4, 3]);
        ctx.beginPath();
        var started = false;
        for (var i = 0; i < pts.length; i++) {
            var px = xP(pts[i].x), py = yP(pts[i].y);
            if (!started) { ctx.moveTo(px, py); started = true; } else ctx.lineTo(px, py);
        }
        ctx.stroke(); ctx.setLineDash([]);
        if (d.label) legend.push({label: d.label, color: d.color || "#4dabf7"});
    }

    else if (d.type === "polygon") {
        var pp = d.points || [];
        if (pp.length < 3) { ctx.restore(); return; }
        ctx.fillStyle = d.color || "rgba(255,215,0,0.05)";
        ctx.beginPath();
        ctx.moveTo(xP(pp[0].x), yP(pp[0].y));
        for (var j = 1; j < pp.length; j++) ctx.lineTo(xP(pp[j].x), yP(pp[j].y));
        ctx.closePath(); ctx.fill();
        if (d.border) { ctx.strokeStyle = d.border; ctx.lineWidth = 0.8; ctx.stroke(); }
    }

    else if (d.type === "arrow") {
        var ax = xP(d.x), ay1 = yP(d.y1), ay2 = yP(d.y2);
        ctx.strokeStyle = d.color || "#51cf66"; ctx.lineWidth = d.width || 2;
        ctx.setLineDash([4, 3]);
        ctx.beginPath(); ctx.moveTo(ax, ay1); ctx.lineTo(ax, ay2); ctx.stroke();
        ctx.setLineDash([]);
        // Arrowhead
        var dir = ay2 < ay1 ? -1 : 1;
        ctx.fillStyle = d.color || "#51cf66";
        ctx.beginPath();
        ctx.moveTo(ax, ay2);
        ctx.lineTo(ax - 5, ay2 - dir * 8);
        ctx.lineTo(ax + 5, ay2 - dir * 8);
        ctx.closePath(); ctx.fill();
    }

    ctx.restore();
}

function _drawLabel(ctx, text, x, y, color, align) {
    ctx.font = "bold 9px 'Segoe UI',sans-serif";
    var w = ctx.measureText(text).width + 6;
    var h = 13;
    ctx.fillStyle = "#0f0f14cc";
    var ax = (align === "center") ? x - w/2 : x;
    ctx.fillRect(ax - 1, y - h + 2, w, h);
    ctx.fillStyle = color || "#ffd700";
    ctx.textAlign = align || "left";
    ctx.fillText(text, (align === "center") ? x : x + 2, y);
}
