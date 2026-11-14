/**
 * Stock Debate Chat — Frontend Application
 * 3-Tab layout: Pattern Scanner | Stock Analyzer | Active Trading Scanner
 * Input at TOP, results flow below. Verdict as bullet points.
 */

const API_BASE = window.location.origin;
const chatMessages = document.getElementById("chatMessages");
const stockInput = document.getElementById("stockInput");
const analyzeBtn = document.getElementById("analyzeBtn");
const analysisMode = document.getElementById("analysisMode");

let isAnalyzing = false;
const MODE_LABELS = {
    swing_trading: "\u{1F504} Swing Trading",
    option_trading: "\u{1F4CA} Option Trading",
    short_term: "\u26A1 Short Term",
    investment: "\u{1F3E6} Investment",
};

// ── Stock Dropdown State ───────────────────────────────────────
let allStocks = [], allCategories = [], filteredStocks = [];
let selectedCategory = "all", highlightedIndex = -1, dropdownVisible = false, stocksLoaded = false;
let activeTab = "pattern-scanner";

// ── Initialize ─────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    checkHealth();
    loadStockList();
    initStockDropdown();
    registerServiceWorker();
});

function registerServiceWorker() {
    if ("serviceWorker" in navigator) {
        navigator.serviceWorker.register("/sw.js").then(r => console.log("SW registered:", r.scope)).catch(e => console.warn("SW failed:", e));
    }
}

// ── Tab Switching ──────────────────────────────────────────────
function switchTab(tabId) {
    activeTab = tabId;
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.toggle("active", b.dataset.tab === tabId));
    document.getElementById("patternScannerTab").classList.toggle("hidden", tabId !== "pattern-scanner");
    document.getElementById("stockAnalyzerTab").classList.toggle("hidden", tabId !== "stock-analyzer");
    document.getElementById("activeTradingTab").classList.toggle("hidden", tabId !== "active-trading");
    if (tabId === "stock-analyzer" && stockInput && !isAnalyzing) setTimeout(() => stockInput.focus(), 100);
}

// ── Health Check ───────────────────────────────────────────────
async function checkHealth() {
    const dot = document.querySelector(".status-dot"), txt = document.querySelector(".status-text");
    try {
        const res = await fetch(`${API_BASE}/api/health`);
        const data = await res.json();
        if (data.status === "healthy") {
            dot.classList.add("connected"); dot.classList.remove("error");
            const p = data.ai_providers || [];
            txt.textContent = p.length > 0 ? `Connected (${p.join(", ")})` : "Connected (no AI providers)";
            if (p.length === 0) { dot.classList.add("error"); dot.classList.remove("connected"); txt.textContent = "No AI providers configured"; }
        }
    } catch { dot.classList.add("error"); dot.classList.remove("connected"); txt.textContent = "API unavailable"; }
}

// ── Stock List Loader ──────────────────────────────────────────
async function loadStockList() {
    try {
        const res = await fetch(`${API_BASE}/api/stocks`);
        const data = await res.json();
        allStocks = data.stocks || []; allCategories = data.categories || [];
        stocksLoaded = true; buildCategoryPills(); updateStockCount(allStocks.length);
        filteredStocks = allStocks; renderDropdownList(filteredStocks);
    } catch (err) {
        console.error("Failed to load stock list:", err);
        const dl = document.getElementById("dropdownList");
        if (dl) dl.innerHTML = '<div class="dropdown-empty">\u26A0\uFE0F Could not load stocks. Type a name manually.</div>';
    }
}

// ── Stock Dropdown ─────────────────────────────────────────────
function initStockDropdown() {
    const wrapper = document.getElementById("stockSearchWrapper");
    stockInput.addEventListener("focus", () => { if (!isAnalyzing) showDropdown(); });
    stockInput.addEventListener("input", () => { highlightedIndex = -1; filterStocks(); });
    stockInput.addEventListener("keydown", (e) => {
        if (!dropdownVisible) { if (e.key === "Enter" && !isAnalyzing) handleAnalyze(); return; }
        switch (e.key) {
            case "ArrowDown": e.preventDefault(); highlightedIndex = Math.min(highlightedIndex + 1, filteredStocks.length - 1); updateHighlight(); break;
            case "ArrowUp": e.preventDefault(); highlightedIndex = Math.max(highlightedIndex - 1, -1); updateHighlight(); break;
            case "Enter": e.preventDefault();
                if (highlightedIndex >= 0 && highlightedIndex < filteredStocks.length) selectStock(filteredStocks[highlightedIndex]);
                else if (stockInput.value.trim()) { hideDropdown(); handleAnalyze(); } break;
            case "Escape": case "Tab": hideDropdown(); break;
        }
    });
    document.addEventListener("click", (e) => { if (wrapper && !wrapper.contains(e.target)) hideDropdown(); });
}

function showDropdown() { const d = document.getElementById("stockDropdown"); if (d && stocksLoaded) { d.classList.add("visible"); dropdownVisible = true; filterStocks(); } }
function hideDropdown() { const d = document.getElementById("stockDropdown"); if (d) { d.classList.remove("visible"); dropdownVisible = false; highlightedIndex = -1; } }

function buildCategoryPills() {
    const c = document.getElementById("categoryPills"); if (!c) return;
    let h = '<button class="cat-pill active" data-category="all">All</button>';
    for (const cat of allCategories) h += `<button class="cat-pill" data-category="${escapeHtml(cat)}">${escapeHtml(cat)}</button>`;
    c.innerHTML = h;
    c.querySelectorAll(".cat-pill").forEach(pill => {
        pill.addEventListener("click", () => {
            c.querySelectorAll(".cat-pill").forEach(p => p.classList.remove("active"));
            pill.classList.add("active"); selectedCategory = pill.dataset.category; highlightedIndex = -1; filterStocks();
        });
    });
}

function filterStocks() {
    const q = stockInput.value.trim().toLowerCase();
    filteredStocks = allStocks.filter(s => {
        if (selectedCategory !== "all" && s.category !== selectedCategory) return false;
        if (q) return s.name.toLowerCase().includes(q) || s.ticker.toLowerCase().includes(q) || s.category.toLowerCase().includes(q);
        return true;
    });
    renderDropdownList(filteredStocks); updateStockCount(filteredStocks.length);
}

function renderDropdownList(stocks) {
    const c = document.getElementById("dropdownList"); if (!c) return;
    if (stocks.length === 0) { c.innerHTML = '<div class="dropdown-empty">No stocks found. Type any stock name and press Enter.</div>'; return; }
    const grouped = {}; for (const s of stocks) { if (!grouped[s.category]) grouped[s.category] = []; grouped[s.category].push(s); }
    let html = "", gi = 0; const q = stockInput.value.trim().toLowerCase();
    for (const [cat, cs] of Object.entries(grouped)) {
        html += `<div class="dropdown-category-header">${escapeHtml(cat)}</div>`;
        for (const s of cs) {
            const hl = gi === highlightedIndex, nm = q ? highlightMatch(s.name, q) : escapeHtml(s.name);
            const td = s.ticker.replace(".NS","").replace("^",""), th = q ? highlightMatch(td, q) : escapeHtml(td);
            html += `<div class="dropdown-item ${hl?"highlighted":""}" data-index="${gi}" data-name="${escapeHtml(s.name)}" data-ticker="${escapeHtml(s.ticker)}"><span class="dropdown-item-name">${nm}</span><span class="dropdown-item-ticker">${th}</span></div>`;
            gi++;
        }
    }
    c.innerHTML = html;
    c.querySelectorAll(".dropdown-item").forEach(item => {
        item.addEventListener("click", () => { const i = parseInt(item.dataset.index, 10); if (i >= 0 && i < filteredStocks.length) selectStock(filteredStocks[i]); });
        item.addEventListener("mouseenter", () => { highlightedIndex = parseInt(item.dataset.index, 10); updateHighlight(); });
    });
}

function highlightMatch(text, query) {
    if (!query) return escapeHtml(text);
    const e = escapeHtml(text), r = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi");
    return e.replace(r, '<mark class="search-highlight">$1</mark>');
}

function updateHighlight() {
    const c = document.getElementById("dropdownList"); if (!c) return;
    c.querySelectorAll(".dropdown-item").forEach(i => i.classList.toggle("highlighted", parseInt(i.dataset.index, 10) === highlightedIndex));
    const h = c.querySelector(".dropdown-item.highlighted"); if (h) h.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function selectStock(stock) { stockInput.value = stock.name; hideDropdown(); if (!isAnalyzing) handleAnalyze(); }
function updateStockCount(count) { const e = document.getElementById("stockCount"); if (e) e.textContent = `${count} stock${count !== 1 ? "s" : ""}`; }

// ── Analyze Stock ──────────────────────────────────────────────
function handleAnalyze() { const n = stockInput.value.trim(); if (!n || isAnalyzing) return; hideDropdown(); analyzeStock(n); }

async function analyzeStock(stockName) {
    if (isAnalyzing) return; isAnalyzing = true;
    switchTab("stock-analyzer");
    const mode = analysisMode ? analysisMode.value : "swing_trading", modeLabel = MODE_LABELS[mode] || mode;
    stockInput.value = ""; stockInput.disabled = true; analyzeBtn.disabled = true;
    if (analysisMode) analysisMode.disabled = true;
    addUserMessage(stockName, modeLabel);

    const stepTracker = addStepTracker();
    updateStep(stepTracker, 1, "active", "Fetching stock data...");

    let stockData = null;
    try {
        const res = await fetch(`${API_BASE}/api/stock-data`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ stock_name: stockName }) });
        if (!res.ok) { const e = await res.json().catch(() => ({ detail: "Unknown error" })); updateStep(stepTracker, 1, "error", "Stock data failed"); addErrorMessage(e.detail || `Error ${res.status}`); resetUI(); return; }
        stockData = await res.json(); updateStep(stepTracker, 1, "done", "Stock data loaded");
        addStockDataMessage(stockData.stock_name, stockData.ticker, stockData.stock_data);
        if (stockData.technical_data && Object.keys(stockData.technical_data).length > 0) addTechnicalAnalysisMessage(stockData.technical_data, stockData.stock_data.current_price);
    } catch (err) { updateStep(stepTracker, 1, "error", "Connection failed"); addErrorMessage("Could not connect to the server."); console.error(err); resetUI(); return; }

    updateStep(stepTracker, 2, "active", "\u{1F402} Bull is analyzing...");
    let bullResult = null;
    try {
        const res = await fetch(`${API_BASE}/api/debate/bull`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ticker: stockData.ticker, stock_name: stockData.stock_name, stock_data: stockData.stock_data, technical_data: stockData.technical_data, analysis_mode: mode }) });
        if (!res.ok) { const e = await res.json().catch(() => ({ detail: "Bull analysis failed" })); updateStep(stepTracker, 2, "error", "Bull failed"); addAgentErrorMessage("bull", "\u{1F402} Bullish Analyst", e.detail || "Bull analysis failed"); bullResult = { argument: "\u26A0\uFE0F Bull analysis unavailable.", provider: "none", providers_attempted: [], errors: {} }; }
        else { bullResult = await res.json(); updateStep(stepTracker, 2, "done", "Bull complete"); addAgentMessage("bull", bullResult.agent, bullResult.argument, { provider: bullResult.provider, providers_attempted: bullResult.providers_attempted, errors: bullResult.errors }); }
    } catch (err) { updateStep(stepTracker, 2, "error", "Bull connection failed"); addAgentErrorMessage("bull", "\u{1F402} Bullish Analyst", "Could not connect."); bullResult = { argument: "\u26A0\uFE0F Bull analysis unavailable.", provider: "none", providers_attempted: [], errors: {} }; console.error(err); }

    updateStep(stepTracker, 3, "active", "\u{1F43B} Bear is countering...");
    let bearResult = null;
    try {
        const res = await fetch(`${API_BASE}/api/debate/bear`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ticker: stockData.ticker, stock_name: stockData.stock_name, stock_data: stockData.stock_data, technical_data: stockData.technical_data, analysis_mode: mode, bull_argument: bullResult.argument }) });
        if (!res.ok) { const e = await res.json().catch(() => ({ detail: "Bear analysis failed" })); updateStep(stepTracker, 3, "error", "Bear failed"); addAgentErrorMessage("bear", "\u{1F43B} Bearish Analyst", e.detail || "Bear analysis failed"); bearResult = { argument: "\u26A0\uFE0F Bear analysis unavailable.", provider: "none", providers_attempted: [], errors: {} }; }
        else { bearResult = await res.json(); updateStep(stepTracker, 3, "done", "Bear complete"); addAgentMessage("bear", bearResult.agent, bearResult.argument, { provider: bearResult.provider, providers_attempted: bearResult.providers_attempted, errors: bearResult.errors }); }
    } catch (err) { updateStep(stepTracker, 3, "error", "Bear connection failed"); addAgentErrorMessage("bear", "\u{1F43B} Bearish Analyst", "Could not connect."); bearResult = { argument: "\u26A0\uFE0F Bear analysis unavailable.", provider: "none", providers_attempted: [], errors: {} }; console.error(err); }

    updateStep(stepTracker, 4, "active", "\u2696\uFE0F Judge is deliberating...");
    try {
        const res = await fetch(`${API_BASE}/api/debate/judge`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ticker: stockData.ticker, stock_name: stockData.stock_name, stock_data: stockData.stock_data, technical_data: stockData.technical_data, analysis_mode: mode, bull_argument: bullResult.argument, bear_argument: bearResult.argument }) });
        if (!res.ok) { const e = await res.json().catch(() => ({ detail: "Judge verdict failed" })); updateStep(stepTracker, 4, "error", "Judge failed"); addAgentErrorMessage("judge", "\u2696\uFE0F Judge", e.detail || "Judge verdict failed"); }
        else { const judgeResult = await res.json(); updateStep(stepTracker, 4, "done", "Verdict delivered"); addJudgeMessage(judgeResult); }
    } catch (err) { updateStep(stepTracker, 4, "error", "Judge connection failed"); addAgentErrorMessage("judge", "\u2696\uFE0F Judge", "Could not connect."); console.error(err); }

    addDisclaimerMessage("\u26A0\uFE0F This is AI-generated analysis for educational purposes only. This is NOT financial advice. Always do your own research and consult a SEBI-registered financial advisor before making investment decisions.");
    setTimeout(() => { if (stepTracker && stepTracker.parentNode) stepTracker.classList.add("step-tracker-done"); }, 1000);
    resetUI();
}

function resetUI() { isAnalyzing = false; stockInput.disabled = false; analyzeBtn.disabled = false; if (analysisMode) analysisMode.disabled = false; stockInput.focus(); }

// ── Step Tracker ───────────────────────────────────────────────
function addStepTracker() {
    const t = document.createElement("div"); t.className = "message step-tracker";
    t.innerHTML = `<div class="step-tracker-title">Analysis Progress</div><div class="steps">
        <div class="step" data-step="1"><span class="step-icon">\u23F3</span><span class="step-label">Stock Data</span></div>
        <div class="step" data-step="2"><span class="step-icon">\u23F3</span><span class="step-label">Bull Analysis</span></div>
        <div class="step" data-step="3"><span class="step-icon">\u23F3</span><span class="step-label">Bear Analysis</span></div>
        <div class="step" data-step="4"><span class="step-icon">\u23F3</span><span class="step-label">Judge Verdict</span></div>
    </div>`;
    chatMessages.appendChild(t); scrollToBottom(); return t;
}

function updateStep(tracker, stepNum, status, label) {
    if (!tracker) return; const step = tracker.querySelector(`[data-step="${stepNum}"]`); if (!step) return;
    const icon = step.querySelector(".step-icon"), labelEl = step.querySelector(".step-label");
    step.className = `step step-${status}`;
    if (status === "active") { icon.textContent = "\u23F3"; step.classList.add("step-pulse"); }
    else if (status === "done") { icon.textContent = "\u2705"; step.classList.remove("step-pulse"); }
    else if (status === "error") { icon.textContent = "\u274C"; step.classList.remove("step-pulse"); }
    if (label) labelEl.textContent = label; scrollToBottom();
}

// ── Summary / Detail Parsing ───────────────────────────────────
function parseSummaryAndDetails(text) {
    const m = text.match(/<!-- SUMMARY_START -->([\s\S]*?)<!-- SUMMARY_END -->/);
    if (m) return { summary: m[1].trim(), details: text.replace(m[0], '').trim(), hasSummary: true };
    const fp = text.split('\n\n')[0];
    return { summary: fp.substring(0, 250) + (fp.length > 250 ? '...' : ''), details: text, hasSummary: false };
}

// ── Verdict Section Parser — Extract bullet points ─────────────
function parseVerdictSections(analysisText) {
    const sections = [];
    const patterns = [
        { regex: /###\s*\u2705\s*Strongest Bull Point\s*\n([\s\S]*?)(?=###|$)/i, type: "bull-point", icon: "\u2705", title: "Strongest Bull Point" },
        { regex: /###\s*\u274C\s*Strongest Bear Point\s*\n([\s\S]*?)(?=###|$)/i, type: "bear-point", icon: "\u274C", title: "Strongest Bear Point" },
        { regex: /###\s*\u{1F4D0}\s*(?:Technical Verdict|Quick Technical Verdict|Volatility.*Technical Verdict|Fundamental Verdict)\s*\n([\s\S]*?)(?=###|$)/iu, type: "tech-point", icon: "\u{1F4D0}", title: "Technical Verdict" },
        { regex: /###\s*\u{1F4B0}\s*(?:Swing Trade Action Plan|Quick Trade Setup|Investment Action Plan)\s*\n([\s\S]*?)(?=###|$)/iu, type: "trade-point", icon: "\u{1F4B0}", title: "Trade Action Plan" },
        { regex: /###\s*\u{1F4CB}\s*(?:Options Strategy|Recommended Options Strategy)\s*\n([\s\S]*?)(?=###|$)/iu, type: "trade-point", icon: "\u{1F4CB}", title: "Options Strategy" },
        { regex: /###\s*\u{1F4A1}\s*Final Recommendation\s*\n([\s\S]*?)(?=###|$)/iu, type: "final-point", icon: "\u{1F4A1}", title: "Final Recommendation" },
        { regex: /###\s*\u{1F4C8}\s*Key Levels to Watch\s*\n([\s\S]*?)(?=###|$)/iu, type: "tech-point", icon: "\u{1F4C8}", title: "Key Levels" },
    ];
    for (const p of patterns) {
        const m = analysisText.match(p.regex);
        if (m && m[1].trim().length > 10) sections.push({ type: p.type, icon: p.icon, title: p.title, content: m[1].trim() });
    }
    return sections;
}

function buildVerdictBullets(sections) {
    if (sections.length === 0) return "";
    let html = '<ul class="verdict-bullets">';
    for (const s of sections) {
        const truncated = s.content.length > 300 ? s.content.substring(0, 300) + "..." : s.content;
        html += `<li class="verdict-bullet ${s.type}"><span class="verdict-bullet-icon">${s.icon}</span><div class="verdict-bullet-content"><div class="verdict-bullet-title">${escapeHtml(s.title)}</div><div class="verdict-bullet-text">${renderMarkdown(truncated)}</div></div></li>`;
    }
    return html + '</ul>';
}

// ── Detail Modal ───────────────────────────────────────────────
function openDetailModal(title, fullMarkdown) {
    const o = document.getElementById("detailModal"), mt = document.getElementById("modalTitle"), mb = document.getElementById("modalBody");
    if (!o) return; mt.textContent = title; mb.innerHTML = renderMarkdown(fullMarkdown);
    o.classList.add("visible"); document.body.style.overflow = "hidden";
}
function closeDetailModal() { const o = document.getElementById("detailModal"); if (o) { o.classList.remove("visible"); document.body.style.overflow = ""; } }
document.addEventListener("click", (e) => { if (e.target.classList.contains("detail-modal-overlay")) closeDetailModal(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDetailModal(); });

// ── Message Builders ───────────────────────────────────────────
function addUserMessage(text, modeLabel) {
    const m = document.createElement("div"); m.className = "message user-message";
    m.innerHTML = `<div class="message-label">You</div><div class="message-body">Analyze <strong>${escapeHtml(text)}</strong> <span class="mode-badge">${escapeHtml(modeLabel)}</span></div>`;
    chatMessages.appendChild(m); scrollToBottom();
}

function addErrorMessage(text) {
    const m = document.createElement("div"); m.className = "message error-message";
    m.innerHTML = `<div class="error-icon">\u274C</div><div class="error-text">${escapeHtml(text)}</div>`;
    chatMessages.appendChild(m); scrollToBottom();
}

function addAgentErrorMessage(type, agent, errorText) {
    const m = document.createElement("div"); m.className = `message ${type}-message agent-error`;
    m.innerHTML = `<div class="agent-label">${escapeHtml(agent)} <span class="provider-badge provider-failed"><span class="provider-icon">\u2717</span><span class="provider-name">failed</span></span></div><div class="message-body"><p class="error-text">\u26A0\uFE0F ${escapeHtml(errorText)}</p></div>`;
    chatMessages.appendChild(m); scrollToBottom();
}

function addAgentMessage(type, agent, argument, providerInfo) {
    const m = document.createElement("div"); m.className = `message ${type}-message summary-card`;
    const pb = buildProviderBadge(providerInfo), parsed = parseSummaryAndDetails(argument);
    const detailId = `detail_${Date.now()}_${type}`; window[detailId] = argument;
    const agentTitle = type === "bull" ? "\u{1F402} Bullish Analyst" : "\u{1F43B} Bearish Analyst";
    m.innerHTML = `<div class="agent-label">${escapeHtml(agent)}${pb}</div><div class="summary-text">${renderMarkdown(parsed.summary)}</div><button class="show-details-btn" onclick="openDetailModal('${escapeHtml(agentTitle)}', window['${detailId}'])">Show Details \u2192</button>`;
    chatMessages.appendChild(m); scrollToBottom();
}

function addJudgeMessage(verdict) {
    const m = document.createElement("div"); m.className = "message judge-message summary-card";
    const rec = verdict.recommendation.toUpperCase();
    const badgeClass = rec === "BUY" ? "buy" : rec === "HOLD" ? "hold" : "avoid";
    const confidence = verdict.confidence, confidencePercent = (confidence / 10) * 100;
    let fillColor = confidence >= 7 ? "var(--accent-green)" : confidence >= 4 ? "var(--accent-gold)" : "var(--accent-red)";
    const pb = buildProviderBadge({ provider: verdict.provider, providers_attempted: verdict.providers_attempted, errors: verdict.errors });
    const parsed = parseSummaryAndDetails(verdict.analysis);
    const verdictSections = parseVerdictSections(verdict.analysis);
    const bulletHtml = buildVerdictBullets(verdictSections);
    const detailId = `detail_${Date.now()}_judge`; window[detailId] = verdict.analysis;
    let summaryContent = parsed.hasSummary ? `<div class="summary-text">${renderMarkdown(parsed.summary)}</div>` : "";

    m.innerHTML = `<div class="agent-label">${escapeHtml(verdict.agent)}<span class="verdict-badge ${badgeClass}">${rec}</span>${pb}</div>
        <div class="confidence-bar"><span>Confidence:</span><div class="confidence-track"><div class="confidence-fill" style="width:${confidencePercent}%;background:${fillColor};"></div></div><span>${confidence}/10</span></div>
        ${summaryContent}${bulletHtml}
        <button class="show-details-btn" onclick="openDetailModal('\u2696\uFE0F Judge Verdict', window['${detailId}'])">Show Full Analysis \u2192</button>`;
    chatMessages.appendChild(m); scrollToBottom();
}

function addDisclaimerMessage(text) {
    const m = document.createElement("div"); m.className = "message disclaimer-message"; m.textContent = text;
    chatMessages.appendChild(m); scrollToBottom();
}

// ── Stock Data Message ─────────────────────────────────────────
function addStockDataMessage(name, ticker, data) {
    const m = document.createElement("div"); m.className = "message stock-data-message";
    m.innerHTML = `<div class="stock-data-header"><h3>\u{1F4C8} ${escapeHtml(name)}</h3><span class="ticker">${escapeHtml(ticker)}</span></div><div class="stock-data-grid">${buildStockDataGrid(data)}</div>`;
    chatMessages.appendChild(m); scrollToBottom();
}

function buildStockDataGrid(data) {
    const fields = [
        { key: "current_price", label: "Price", prefix: "\u20B9" }, { key: "market_cap", label: "Market Cap" },
        { key: "pe_ratio", label: "P/E Ratio" }, { key: "pb_ratio", label: "P/B Ratio" },
        { key: "eps", label: "EPS", prefix: "\u20B9" }, { key: "dividend_yield", label: "Div Yield", suffix: "%" },
        { key: "52_week_high", label: "52W High", prefix: "\u20B9" }, { key: "52_week_low", label: "52W Low", prefix: "\u20B9" },
        { key: "debt_to_equity", label: "D/E Ratio" }, { key: "roe", label: "ROE" },
        { key: "revenue_growth", label: "Rev Growth", suffix: "%" }, { key: "profit_growth", label: "Profit Growth", suffix: "%" },
        { key: "1m_return", label: "1M Return", suffix: "%", colored: true }, { key: "3m_return", label: "3M Return", suffix: "%", colored: true },
        { key: "6m_return", label: "6M Return", suffix: "%", colored: true }, { key: "1y_return", label: "1Y Return", suffix: "%", colored: true },
        { key: "sector", label: "Sector" }, { key: "industry", label: "Industry" },
    ];
    return fields.filter(f => data[f.key] != null).map(f => {
        let v = data[f.key], dv = "", cc = "";
        if (typeof v === "number") { dv = `${f.prefix||""}${v.toFixed(2)}${f.suffix||""}`; if (f.colored) cc = v >= 0 ? "positive" : "negative"; }
        else dv = `${f.prefix||""}${v}${f.suffix||""}`;
        return `<div class="data-item"><span class="label">${f.label}</span><span class="value ${cc}">${dv}</span></div>`;
    }).join("");
}

// ── Technical Analysis Message ─────────────────────────────────
function addTechnicalAnalysisMessage(techData, currentPrice) {
    const m = document.createElement("div"); m.className = "message technical-message";
    let html = '<div class="tech-header"><h3>📐 Technical Analysis</h3><span class="tech-subtitle">Support/Resistance • Chart Patterns • Swing Indicators</span></div>';

    const sr = techData.support_resistance || {};
    if (sr.support_levels?.length || sr.resistance_levels?.length) {
        html += '<div class="tech-section"><h4>🎯 Support & Resistance Levels</h4><div class="sr-grid">';
        if (sr.resistance_levels?.length) {
            html += '<div class="sr-column resistance-col"><div class="sr-col-header resistance-header">Resistance ↑</div>';
            sr.resistance_levels.forEach((r, i) => {
                const pct = currentPrice ? ((r.price - currentPrice) / currentPrice * 100).toFixed(1) : "?";
                html += '<div class="sr-level resistance-level"><span class="sr-label">R' + (i+1) + '</span><span class="sr-price">₹' + r.price.toFixed(2) + '</span><span class="sr-zone">₹' + r.zone_low + '–₹' + r.zone_high + '</span><span class="sr-strength">' + "●".repeat(Math.min(r.strength, 5)) + '</span><span class="sr-pct">+' + pct + '%</span></div>';
            });
            html += '</div>';
        }
        if (currentPrice) html += '<div class="sr-current-price"><span>CMP</span><span class="cmp-value">₹' + currentPrice.toFixed(2) + '</span></div>';
        if (sr.support_levels?.length) {
            html += '<div class="sr-column support-col"><div class="sr-col-header support-header">Support ↓</div>';
            sr.support_levels.forEach((s, i) => {
                const pct = currentPrice ? ((currentPrice - s.price) / currentPrice * 100).toFixed(1) : "?";
                html += '<div class="sr-level support-level"><span class="sr-label">S' + (i+1) + '</span><span class="sr-price">₹' + s.price.toFixed(2) + '</span><span class="sr-zone">₹' + s.zone_low + '–₹' + s.zone_high + '</span><span class="sr-strength">' + "●".repeat(Math.min(s.strength, 5)) + '</span><span class="sr-pct">-' + pct + '%</span></div>';
            });
            html += '</div>';
        }
        html += '</div></div>';
    }

    if (sr.fibonacci && sr.fibonacci.swing_high) {
        const f = sr.fibonacci;
        html += '<div class="tech-section"><h4>📏 Fibonacci Retracement</h4><div class="fib-grid">';
        html += '<div class="fib-level"><span class="fib-pct">0%</span><span class="fib-price">₹' + f.level_0 + '</span></div>';
        html += '<div class="fib-level"><span class="fib-pct">23.6%</span><span class="fib-price">₹' + f.level_236 + '</span></div>';
        html += '<div class="fib-level"><span class="fib-pct">38.2%</span><span class="fib-price">₹' + f.level_382 + '</span></div>';
        html += '<div class="fib-level fib-key"><span class="fib-pct">50.0%</span><span class="fib-price">₹' + f.level_500 + '</span></div>';
        html += '<div class="fib-level fib-key"><span class="fib-pct">61.8%</span><span class="fib-price">₹' + f.level_618 + '</span></div>';
        html += '<div class="fib-level"><span class="fib-pct">78.6%</span><span class="fib-price">₹' + f.level_786 + '</span></div>';
        html += '<div class="fib-level"><span class="fib-pct">100%</span><span class="fib-price">₹' + f.level_100 + '</span></div>';
        html += '</div></div>';
    }

    if (sr.pivot_classic && sr.pivot_classic.pivot) {
        const pv = sr.pivot_classic;
        html += '<div class="tech-section"><h4>🔄 Classic Pivot Points</h4><div class="pivot-grid">';
        html += '<div class="pivot-item pivot-r">R3: ₹' + pv.r3 + '</div><div class="pivot-item pivot-r">R2: ₹' + pv.r2 + '</div>';
        html += '<div class="pivot-item pivot-r">R1: ₹' + pv.r1 + '</div><div class="pivot-item pivot-p">Pivot: ₹' + pv.pivot + '</div>';
        html += '<div class="pivot-item pivot-s">S1: ₹' + pv.s1 + '</div><div class="pivot-item pivot-s">S2: ₹' + pv.s2 + '</div>';
        html += '<div class="pivot-item pivot-s">S3: ₹' + pv.s3 + '</div>';
        html += '</div></div>';
    }

    if (sr.moving_averages && Object.keys(sr.moving_averages).length) {
        const ma = sr.moving_averages;
        html += '<div class="tech-section"><h4>📊 Moving Averages</h4><div class="ma-grid">';
        ["ema_20","sma_20","ema_50","sma_50","ema_100","sma_100","ema_200","sma_200"].forEach(key => {
            if (ma[key] !== undefined) {
                const label = key.toUpperCase().replace("_", " ");
                const ab = currentPrice && ma[key] < currentPrice ? "ma-above" : "ma-below";
                html += '<div class="ma-item ' + ab + '"><span class="ma-label">' + label + '</span><span class="ma-price">₹' + ma[key].toFixed(2) + '</span></div>';
            }
        });
        html += '</div></div>';
    }

    const patterns = techData.chart_patterns || [];
    if (patterns.length) {
        html += '<div class="tech-section"><h4>📈 Chart Patterns Detected</h4><div class="patterns-list">';
        patterns.forEach(p => {
            const tc = p.type === "bullish" ? "pattern-bullish" : p.type === "bearish" ? "pattern-bearish" : "pattern-neutral";
            const em = p.type === "bullish" ? "🟢" : p.type === "bearish" ? "🔴" : "🟡";
            html += '<div class="pattern-card ' + tc + '"><div class="pattern-header"><span class="pattern-emoji">' + em + '</span><span class="pattern-name">' + escapeHtml(p.pattern) + '</span><span class="pattern-type">' + p.type.toUpperCase() + '</span>';
            if (p.reliability) html += '<span class="pattern-reliability">' + p.reliability + '</span>';
            html += '</div><div class="pattern-desc">' + escapeHtml(p.description || "") + '</div>';
            if (p.target) html += '<div class="pattern-target">Target: ₹' + p.target + '</div>';
            if (p.implication) html += '<div class="pattern-impl">' + escapeHtml(p.implication) + '</div>';
            html += '</div>';
        });
        html += '</div></div>';
    }

    const swing = techData.swing_indicators || {};
    if (Object.keys(swing).length) {
        html += '<div class="tech-section"><h4>🔧 Swing Trading Indicators</h4><div class="swing-grid">';
        if (swing.swing_score !== undefined) {
            const sc = swing.swing_score >= 60 ? "var(--accent-green)" : swing.swing_score <= 40 ? "var(--accent-red)" : "var(--accent-gold)";
            html += '<div class="swing-score-card"><div class="swing-score-label">Swing Score</div><div class="swing-score-value" style="color:' + sc + '">' + swing.swing_score + '/100</div><div class="swing-score-bias">' + (swing.swing_bias || "Neutral") + '</div></div>';
        }
        var indicators = [
            { key: "rsi_14", label: "RSI (14)", signal: swing.rsi_signal },
            { key: "macd", label: "MACD", signal: swing.macd_trend, extra: swing.macd_crossover },
            { key: "bb_signal", label: "Bollinger", signal: swing.bb_signal },
            { key: "atr_14", label: "ATR (14)", signal: "₹" + swing.atr_14 + " (" + swing.atr_pct + "%)", prefix: "" },
            { key: "stoch_rsi", label: "Stoch RSI", signal: swing.stoch_rsi_signal },
            { key: "relative_volume", label: "Rel. Volume", signal: swing.volume_signal },
            { key: "obv_trend", label: "OBV", signal: swing.obv_trend },
        ];
        indicators.forEach(function(ind) {
            var val = swing[ind.key];
            if (val !== undefined && val !== null) {
                var dv = typeof val === "number" ? val.toFixed(2) : val;
                html += '<div class="swing-item"><span class="swing-label">' + ind.label + '</span><span class="swing-value">' + (ind.prefix !== undefined ? ind.prefix : "") + dv + '</span>';
                if (ind.signal) html += '<span class="swing-signal">' + ind.signal + '</span>';
                if (ind.extra) html += '<span class="swing-extra">' + ind.extra + '</span>';
                html += '</div>';
            }
        });
        if (swing.suggested_sl && swing.suggested_target) {
            html += '<div class="swing-atr-levels"><div class="atr-level atr-sl">SL: ₹' + swing.suggested_sl.toFixed(2) + '</div><div class="atr-level atr-target">Target: ₹' + swing.suggested_target.toFixed(2) + '</div></div>';
        }
        html += '</div></div>';
    }

    m.innerHTML = html;
    chatMessages.appendChild(m); scrollToBottom();
}

// ── Provider Badge Builder ─────────────────────────────────────
function buildProviderBadge(providerInfo) {
    if (!providerInfo) return "";
    var provider = providerInfo.provider || "none", attempted = providerInfo.providers_attempted || [], errors = providerInfo.errors || {};
    var isSuccess = provider !== "none", badgeClass = isSuccess ? "provider-success" : "provider-failed";
    var icon = isSuccess ? "✓" : "✗", label = isSuccess ? provider : "all failed";
    var tooltipLines = [];
    if (attempted.length > 0) tooltipLines.push("Attempted: " + attempted.join(" → "));
    if (isSuccess) tooltipLines.push("Responded: " + provider);
    var errorEntries = Object.entries(errors);
    if (errorEntries.length > 0) { tooltipLines.push("---"); for (var [prov, errMsg] of errorEntries) { tooltipLines.push(prov + ": " + (errMsg.length > 80 ? errMsg.substring(0, 80) + "…" : errMsg)); } }
    var tooltip = escapeHtml(tooltipLines.join("\n"));
    return '<span class="provider-badge ' + badgeClass + '" title="' + tooltip + '"><span class="provider-icon">' + icon + '</span><span class="provider-name">' + escapeHtml(label) + '</span>' + (!isSuccess && attempted.length > 0 ? '<span class="provider-tried">(tried: ' + escapeHtml(attempted.join(", ")) + ')</span>' : '') + '</span>';
}

// ── Utilities ──────────────────────────────────────────────────
function scrollToBottom() { var c = document.getElementById("chatContainer"); if (c) setTimeout(function() { c.scrollTop = c.scrollHeight; }, 50); }
function escapeHtml(text) { var d = document.createElement("div"); d.textContent = text; return d.innerHTML; }
function renderMarkdown(text) {
    if (typeof marked !== "undefined" && marked.parse) { try { return marked.parse(text); } catch (e) { console.warn("Markdown parsing failed:", e); } }
    return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>").replace(/\*(.*?)\*/g, "<em>$1</em>").replace(/\n/g, "<br>");
}

// ── Pattern Scanner ────────────────────────────────────────────
var isScanning = false;
async function runPatternScan(forceRefresh) {
    if (isScanning) return; isScanning = true;
    var scanBtn = document.getElementById("scanPatternsBtn"), refreshBtn = document.getElementById("refreshPatternsBtn");
    var statusEl = document.getElementById("scannerStatus"), resultsEl = document.getElementById("scannerResults");
    if (scanBtn) { scanBtn.disabled = true; scanBtn.innerHTML = "⏳ Scanning..."; }
    if (refreshBtn) refreshBtn.disabled = true;
    if (statusEl) { statusEl.innerHTML = '<div class="scanner-progress"><div class="scanner-progress-bar"><div class="scanner-progress-fill"></div></div><span>Scanning stocks for chart patterns...</span></div>'; statusEl.style.display = "block"; }
    try {
        var typeFilter = (document.getElementById("patternTypeFilter") || {}).value || "";
        var url = API_BASE + "/api/screener/patterns?refresh=" + forceRefresh;
        if (typeFilter) url += "&type=" + encodeURIComponent(typeFilter);
        var res = await fetch(url);
        if (!res.ok) { var error = await res.json().catch(function() { return { detail: "Scan failed" }; }); throw new Error(error.detail || "Error " + res.status); }
        renderPatternResults(await res.json(), resultsEl, statusEl);
    } catch (err) { if (statusEl) statusEl.innerHTML = '<div class="scanner-error">❌ ' + escapeHtml(err.message) + '</div>'; console.error(err); }
    finally { isScanning = false; if (scanBtn) { scanBtn.disabled = false; scanBtn.innerHTML = "🔍 Scan Now"; } if (refreshBtn) refreshBtn.disabled = false; }
}

function renderPatternResults(data, resultsEl, statusEl) {
    if (!resultsEl) return;
    if (statusEl) {
        var scanTime = data.last_scan ? new Date(data.last_scan + "Z").toLocaleString() : "N/A";
        var cachedBadge = data.cached ? '<span class="scanner-cached-badge">cached</span>' : '<span class="scanner-fresh-badge">fresh</span>';
        statusEl.innerHTML = '<div class="scanner-status-info"><span>Scanned: <strong>' + data.total_scanned + '</strong> stocks</span><span>Found: <strong>' + data.stocks_with_patterns + '</strong> with patterns</span><span>Last scan: ' + scanTime + ' ' + cachedBadge + '</span></div>';
        statusEl.style.display = "block";
    }
    if (!data.results || data.results.length === 0) { resultsEl.innerHTML = '<div class="scanner-empty"><p>No chart patterns found matching your filters.</p></div>'; return; }
    var html = "";
    for (var stock of data.results) {
        var priceStr = stock.price ? "₹" + stock.price.toFixed(2) : "", tickerDisplay = stock.ticker.replace(".NS", "");
        html += '<div class="scanner-stock-card"><div class="scanner-stock-header"><div class="scanner-stock-info"><span class="scanner-stock-name">' + escapeHtml(stock.name) + '</span><span class="scanner-stock-ticker">' + escapeHtml(tickerDisplay) + '</span>' + (priceStr ? '<span class="scanner-stock-price">' + priceStr + '</span>' : '') + '</div><button class="scanner-analyze-btn" onclick="analyzeFromScanner(\'' + escapeHtml(stock.name) + '\')">Analyze →</button></div><div class="scanner-patterns-list">';
        for (var p of stock.patterns) {
            var typeClass = p.type === "bullish" ? "pattern-bullish" : p.type === "bearish" ? "pattern-bearish" : (p.type === "sideways" ? "pattern-sideways" : "pattern-neutral");
            var emoji = p.type === "bullish" ? "🟢" : p.type === "bearish" ? "🔴" : "🟡";
            html += '<div class="scanner-pattern-item ' + typeClass + '"><div class="scanner-pattern-top"><span class="scanner-pattern-emoji">' + emoji + '</span><span class="scanner-pattern-name">' + escapeHtml(p.pattern) + '</span><span class="scanner-pattern-type">' + (p.type || "neutral").toUpperCase() + '</span>' + (p.reliability ? '<span class="scanner-pattern-reliability">' + p.reliability + '</span>' : '') + '</div><div class="scanner-pattern-desc">' + escapeHtml(p.description || "") + '</div>' + (p.target ? '<div class="scanner-pattern-target">Target: ₹' + p.target + '</div>' : '') + (p.implication ? '<div class="scanner-pattern-impl">' + escapeHtml(p.implication) + '</div>' : '') + '</div>';
        }
        html += '</div></div>';
    }
    resultsEl.innerHTML = html;
}

function analyzeFromScanner(stockName) { stockInput.value = stockName; switchTab("stock-analyzer"); if (!isAnalyzing) handleAnalyze(); }

// ── Active Trading / Volatile Scanner ──────────────────────────
var isVolatileScanning = false;
async function runVolatileScan(forceRefresh) {
    if (isVolatileScanning) return; isVolatileScanning = true;
    var scanBtn = document.getElementById("scanVolatileBtn"), refreshBtn = document.getElementById("refreshVolatileBtn");
    var statusEl = document.getElementById("volatileStatus"), resultsEl = document.getElementById("volatileResults");
    if (scanBtn) { scanBtn.disabled = true; scanBtn.innerHTML = "⏳ Scanning..."; }
    if (refreshBtn) refreshBtn.disabled = true;
    if (statusEl) { statusEl.innerHTML = '<div class="scanner-progress"><div class="scanner-progress-bar"><div class="scanner-progress-fill"></div></div><span>Scanning for high volatility & volume stocks...</span></div>'; statusEl.style.display = "block"; }
    try {
        var sortBy = (document.getElementById("volatileSortBy") || {}).value || "volatility_score";
        var url = API_BASE + "/api/screener/volatile-active?refresh=" + forceRefresh + "&sort_by=" + encodeURIComponent(sortBy);
        var res = await fetch(url);
        if (!res.ok) { var error = await res.json().catch(function() { return { detail: "Scan failed" }; }); throw new Error(error.detail || "Error " + res.status); }
        renderVolatileResults(await res.json(), resultsEl, statusEl);
    } catch (err) { if (statusEl) statusEl.innerHTML = '<div class="scanner-error">❌ ' + escapeHtml(err.message) + '</div>'; console.error(err); }
    finally { isVolatileScanning = false; if (scanBtn) { scanBtn.disabled = false; scanBtn.innerHTML = "🔍 Scan Now"; } if (refreshBtn) refreshBtn.disabled = false; }
}

function renderVolatileResults(data, resultsEl, statusEl) {
    if (!resultsEl) return;
    if (statusEl) {
        var scanTime = data.last_scan ? new Date(data.last_scan + "Z").toLocaleString() : "N/A";
        var cachedBadge = data.cached ? '<span class="scanner-cached-badge">cached</span>' : '<span class="scanner-fresh-badge">fresh</span>';
        statusEl.innerHTML = '<div class="scanner-status-info"><span>Scanned: <strong>' + (data.total_scanned || 0) + '</strong> stocks</span><span>Results: <strong>' + (data.results || []).length + '</strong> volatile stocks</span><span>Last scan: ' + scanTime + ' ' + cachedBadge + '</span></div>';
        statusEl.style.display = "block";
    }
    if (!data.results || data.results.length === 0) { resultsEl.innerHTML = '<div class="scanner-empty"><p>No high volatility stocks found.</p></div>'; return; }
    var html = "";
    for (var stock of data.results) {
        var priceStr = stock.price ? "₹" + stock.price.toFixed(2) : "";
        var tickerDisplay = (stock.ticker || "").replace(".NS", "");
        var score = stock.volatility_score || 0;
        var scoreClass = score >= 70 ? "volatile-score-high" : score >= 50 ? "volatile-score-medium" : "volatile-score-low";
        var returnVal = stock["1m_return"] || 0;
        var returnClass = returnVal >= 0 ? "positive" : "negative";
        var returnStr = returnVal >= 0 ? "+" + returnVal.toFixed(1) + "%" : returnVal.toFixed(1) + "%";
        var tagsHtml = "";
        for (var tag of (stock.tags || [])) {
            var tagClass = "tag-volatility";
            if (tag.toLowerCase().includes("volume")) tagClass = "tag-volume";
            else if (tag.toLowerCase().includes("range")) tagClass = "tag-range";
            else if (tag.toLowerCase().includes("spike")) tagClass = "tag-spike";
            tagsHtml += '<span class="volatile-tag ' + tagClass + '">' + escapeHtml(tag) + '</span>';
        }
        html += '<div class="volatile-stock-card"><div class="volatile-stock-header"><div class="volatile-stock-info"><span class="volatile-stock-name">' + escapeHtml(stock.name || tickerDisplay) + '</span><span class="volatile-stock-ticker">' + escapeHtml(tickerDisplay) + '</span>' + (priceStr ? '<span class="volatile-stock-price">' + priceStr + '</span>' : '') + '</div><div class="volatile-score"><span class="volatile-score-value ' + scoreClass + '">' + score.toFixed(0) + '</span><span class="volatile-score-label">Score</span></div></div>';
        html += '<div class="volatile-metrics"><div class="volatile-metric"><span class="metric-label">Monthly Vol</span><span class="metric-value">' + (stock.monthly_volatility || 0).toFixed(1) + '%</span></div><div class="volatile-metric"><span class="metric-label">ATR %</span><span class="metric-value">' + (stock.atr_pct || 0).toFixed(1) + '%</span></div><div class="volatile-metric"><span class="metric-label">Vol Ratio</span><span class="metric-value ' + ((stock.volume_ratio || 0) >= 1.5 ? 'high' : '') + '">' + (stock.volume_ratio || 0).toFixed(1) + 'x</span></div><div class="volatile-metric"><span class="metric-label">Price Range</span><span class="metric-value">' + (stock.price_range_pct || 0).toFixed(1) + '%</span></div><div class="volatile-metric"><span class="metric-label">Vol Spikes</span><span class="metric-value">' + (stock.volume_spike_days || 0) + ' days</span></div><div class="volatile-metric"><span class="metric-label">Avg Volume</span><span class="metric-value">' + formatVolume(stock.avg_daily_volume || 0) + '</span></div></div>';
        if (tagsHtml) html += '<div class="volatile-tags">' + tagsHtml + '</div>';
        html += '<div class="volatile-card-footer"><span class="volatile-return ' + returnClass + '">1M: ' + returnStr + '</span><button class="volatile-analyze-btn" onclick="analyzeFromScanner(\'' + escapeHtml(stock.name || tickerDisplay) + '\')">Analyze →</button></div></div>';
    }
    resultsEl.innerHTML = html;
}

function formatVolume(vol) {
    if (vol >= 10000000) return (vol / 10000000).toFixed(1) + " Cr";
    if (vol >= 100000) return (vol / 100000).toFixed(1) + " L";
    if (vol >= 1000) return (vol / 1000).toFixed(1) + " K";
    return vol.toString();
}
