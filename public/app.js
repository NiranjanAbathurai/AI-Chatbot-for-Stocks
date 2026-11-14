/**
 * Stock Debate Chat — Frontend Application
 * Sequential 3-call flow with progressive rendering.
 * Calls: /api/stock-data → /api/debate/bull → /api/debate/bear → /api/debate/judge
 */

const API_BASE = window.location.origin;
const chatMessages = document.getElementById("chatMessages");
const stockInput = document.getElementById("stockInput");
const analyzeBtn = document.getElementById("analyzeBtn");
const analysisMode = document.getElementById("analysisMode");

let isAnalyzing = false;

// Analysis mode labels for display
const MODE_LABELS = {
    swing_trading: "🔄 Swing Trading",
    option_trading: "📊 Option Trading",
    short_term: "⚡ Short Term",
    investment: "🏦 Investment",
};

// ── Initialize ─────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    checkHealth();
    stockInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !isAnalyzing) {
            handleAnalyze();
        }
    });
});

// ── Health Check ───────────────────────────────────────────────
async function checkHealth() {
    const statusDot = document.querySelector(".status-dot");
    const statusText = document.querySelector(".status-text");

    try {
        const res = await fetch(`${API_BASE}/api/health`);
        const data = await res.json();

        if (data.status === "healthy") {
            statusDot.classList.add("connected");
            statusDot.classList.remove("error");
            const providers = data.ai_providers || [];
            statusText.textContent = providers.length > 0
                ? `Connected (${providers.join(", ")})`
                : "Connected (no AI providers)";

            if (providers.length === 0) {
                statusDot.classList.add("error");
                statusDot.classList.remove("connected");
                statusText.textContent = "No AI providers configured";
            }
        }
    } catch (err) {
        statusDot.classList.add("error");
        statusDot.classList.remove("connected");
        statusText.textContent = "API unavailable";
    }
}

// ── Analyze Stock ──────────────────────────────────────────────
function handleAnalyze() {
    const stockName = stockInput.value.trim();
    if (!stockName || isAnalyzing) return;
    analyzeStock(stockName);
}

async function analyzeStock(stockName) {
    if (isAnalyzing) return;
    isAnalyzing = true;

    const mode = analysisMode ? analysisMode.value : "swing_trading";
    const modeLabel = MODE_LABELS[mode] || mode;

    // Update UI state
    stockInput.value = "";
    stockInput.disabled = true;
    analyzeBtn.disabled = true;
    if (analysisMode) analysisMode.disabled = true;

    // Add user message with mode
    addUserMessage(stockName, modeLabel);

    // ── Step 1: Fetch stock data ───────────────────────────────
    const stepTracker = addStepTracker();
    updateStep(stepTracker, 1, "active", "Fetching stock data...");

    let stockData = null;
    try {
        const res = await fetch(`${API_BASE}/api/stock-data`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ stock_name: stockName }),
        });

        if (!res.ok) {
            const error = await res.json().catch(() => ({ detail: "Unknown error" }));
            updateStep(stepTracker, 1, "error", "Stock data failed");
            addErrorMessage(error.detail || `Error ${res.status}`);
            resetUI();
            return;
        }

        stockData = await res.json();
        updateStep(stepTracker, 1, "done", "Stock data loaded");

        // Display stock data card + technical analysis
        addStockDataMessage(stockData.stock_name, stockData.ticker, stockData.stock_data);
        if (stockData.technical_data && Object.keys(stockData.technical_data).length > 0) {
            addTechnicalAnalysisMessage(stockData.technical_data, stockData.stock_data.current_price);
        }
    } catch (err) {
        updateStep(stepTracker, 1, "error", "Connection failed");
        addErrorMessage("Could not connect to the server. Please try again.");
        console.error("Stock data API error:", err);
        resetUI();
        return;
    }

    // ── Step 2: Run Bull analysis ──────────────────────────────
    updateStep(stepTracker, 2, "active", "🐂 Bull is analyzing...");
    let bullResult = null;
    try {
        const res = await fetch(`${API_BASE}/api/debate/bull`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                ticker: stockData.ticker,
                stock_name: stockData.stock_name,
                stock_data: stockData.stock_data,
                technical_data: stockData.technical_data,
                analysis_mode: mode,
            }),
        });

        if (!res.ok) {
            const error = await res.json().catch(() => ({ detail: "Bull analysis failed" }));
            updateStep(stepTracker, 2, "error", "Bull failed");
            addAgentErrorMessage("bull", "🐂 Bullish Analyst", error.detail || "Bull analysis failed");
            bullResult = { argument: "⚠️ Bull analysis unavailable.", provider: "none", providers_attempted: [], errors: {} };
        } else {
            bullResult = await res.json();
            updateStep(stepTracker, 2, "done", "Bull complete");
            addAgentMessage("bull", bullResult.agent, bullResult.argument, {
                provider: bullResult.provider,
                providers_attempted: bullResult.providers_attempted,
                errors: bullResult.errors,
            });
        }
    } catch (err) {
        updateStep(stepTracker, 2, "error", "Bull connection failed");
        addAgentErrorMessage("bull", "🐂 Bullish Analyst", "Could not connect for bull analysis.");
        bullResult = { argument: "⚠️ Bull analysis unavailable.", provider: "none", providers_attempted: [], errors: {} };
        console.error("Bull API error:", err);
    }

    // ── Step 3: Run Bear analysis ──────────────────────────────
    updateStep(stepTracker, 3, "active", "🐻 Bear is countering...");
    let bearResult = null;
    try {
        const res = await fetch(`${API_BASE}/api/debate/bear`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                ticker: stockData.ticker,
                stock_name: stockData.stock_name,
                stock_data: stockData.stock_data,
                technical_data: stockData.technical_data,
                analysis_mode: mode,
                bull_argument: bullResult.argument,
            }),
        });

        if (!res.ok) {
            const error = await res.json().catch(() => ({ detail: "Bear analysis failed" }));
            updateStep(stepTracker, 3, "error", "Bear failed");
            addAgentErrorMessage("bear", "🐻 Bearish Analyst", error.detail || "Bear analysis failed");
            bearResult = { argument: "⚠️ Bear analysis unavailable.", provider: "none", providers_attempted: [], errors: {} };
        } else {
            bearResult = await res.json();
            updateStep(stepTracker, 3, "done", "Bear complete");
            addAgentMessage("bear", bearResult.agent, bearResult.argument, {
                provider: bearResult.provider,
                providers_attempted: bearResult.providers_attempted,
                errors: bearResult.errors,
            });
        }
    } catch (err) {
        updateStep(stepTracker, 3, "error", "Bear connection failed");
        addAgentErrorMessage("bear", "🐻 Bearish Analyst", "Could not connect for bear analysis.");
        bearResult = { argument: "⚠️ Bear analysis unavailable.", provider: "none", providers_attempted: [], errors: {} };
        console.error("Bear API error:", err);
    }

    // ── Step 4: Run Judge verdict ──────────────────────────────
    updateStep(stepTracker, 4, "active", "⚖️ Judge is deliberating...");
    try {
        const res = await fetch(`${API_BASE}/api/debate/judge`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                ticker: stockData.ticker,
                stock_name: stockData.stock_name,
                stock_data: stockData.stock_data,
                technical_data: stockData.technical_data,
                analysis_mode: mode,
                bull_argument: bullResult.argument,
                bear_argument: bearResult.argument,
            }),
        });

        if (!res.ok) {
            const error = await res.json().catch(() => ({ detail: "Judge verdict failed" }));
            updateStep(stepTracker, 4, "error", "Judge failed");
            addAgentErrorMessage("judge", "⚖️ Judge", error.detail || "Judge verdict failed");
        } else {
            const judgeResult = await res.json();
            updateStep(stepTracker, 4, "done", "Verdict delivered");
            addJudgeMessage(judgeResult);
        }
    } catch (err) {
        updateStep(stepTracker, 4, "error", "Judge connection failed");
        addAgentErrorMessage("judge", "⚖️ Judge", "Could not connect for judge verdict.");
        console.error("Judge API error:", err);
    }

    // ── Disclaimer ─────────────────────────────────────────────
    addDisclaimerMessage(
        "⚠️ This is AI-generated analysis for educational purposes only. " +
        "This is NOT financial advice. Always do your own research and consult " +
        "a SEBI-registered financial advisor before making investment decisions."
    );

    // Remove step tracker after completion
    setTimeout(() => {
        if (stepTracker && stepTracker.parentNode) {
            stepTracker.classList.add("step-tracker-done");
        }
    }, 1000);

    resetUI();
}

function resetUI() {
    isAnalyzing = false;
    stockInput.disabled = false;
    analyzeBtn.disabled = false;
    if (analysisMode) analysisMode.disabled = false;
    stockInput.focus();
}

// ── Step Tracker ───────────────────────────────────────────────

function addStepTracker() {
    const tracker = document.createElement("div");
    tracker.className = "message step-tracker";
    tracker.innerHTML = `
        <div class="step-tracker-title">Analysis Progress</div>
        <div class="steps">
            <div class="step" data-step="1">
                <span class="step-icon">⏳</span>
                <span class="step-label">Stock Data</span>
            </div>
            <div class="step" data-step="2">
                <span class="step-icon">⏳</span>
                <span class="step-label">Bull Analysis</span>
            </div>
            <div class="step" data-step="3">
                <span class="step-icon">⏳</span>
                <span class="step-label">Bear Analysis</span>
            </div>
            <div class="step" data-step="4">
                <span class="step-icon">⏳</span>
                <span class="step-label">Judge Verdict</span>
            </div>
        </div>
    `;
    chatMessages.appendChild(tracker);
    scrollToBottom();
    return tracker;
}

function updateStep(tracker, stepNum, status, label) {
    if (!tracker) return;
    const step = tracker.querySelector(`[data-step="${stepNum}"]`);
    if (!step) return;

    const icon = step.querySelector(".step-icon");
    const labelEl = step.querySelector(".step-label");

    step.className = `step step-${status}`;

    if (status === "active") {
        icon.textContent = "⏳";
        step.classList.add("step-pulse");
    } else if (status === "done") {
        icon.textContent = "✅";
        step.classList.remove("step-pulse");
    } else if (status === "error") {
        icon.textContent = "❌";
        step.classList.remove("step-pulse");
    }

    if (label) labelEl.textContent = label;
    scrollToBottom();
}

// ── Message Builders ───────────────────────────────────────────

function addUserMessage(text, modeLabel) {
    const msg = document.createElement("div");
    msg.className = "message user-message";
    msg.innerHTML = `
        <div class="message-label">You</div>
        <div class="message-body">
            Analyze <strong>${escapeHtml(text)}</strong>
            <span class="mode-badge">${escapeHtml(modeLabel)}</span>
        </div>
    `;
    chatMessages.appendChild(msg);
    scrollToBottom();
}

function removeMessage(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function addErrorMessage(text) {
    const msg = document.createElement("div");
    msg.className = "message error-message";
    msg.innerHTML = `
        <div class="error-icon">❌</div>
        <div class="error-text">${escapeHtml(text)}</div>
    `;
    chatMessages.appendChild(msg);
    scrollToBottom();
}

function addAgentErrorMessage(type, agent, errorText) {
    const msg = document.createElement("div");
    msg.className = `message ${type}-message agent-error`;
    msg.innerHTML = `
        <div class="agent-label">${escapeHtml(agent)} <span class="provider-badge provider-failed"><span class="provider-icon">✗</span><span class="provider-name">failed</span></span></div>
        <div class="message-body"><p class="error-text">⚠️ ${escapeHtml(errorText)}</p></div>
    `;
    chatMessages.appendChild(msg);
    scrollToBottom();
}

function addStockDataMessage(name, ticker, data) {
    const msg = document.createElement("div");
    msg.className = "message stock-data-message";
    const dataItems = buildStockDataGrid(data);
    msg.innerHTML = `
        <div class="stock-data-header">
            <h3>📈 ${escapeHtml(name)}</h3>
            <span class="ticker">${escapeHtml(ticker)}</span>
        </div>
        <div class="stock-data-grid">${dataItems}</div>
    `;
    chatMessages.appendChild(msg);
    scrollToBottom();
}

function buildStockDataGrid(data) {
    const fields = [
        { key: "current_price", label: "Price", prefix: "₹" },
        { key: "market_cap", label: "Market Cap" },
        { key: "pe_ratio", label: "P/E Ratio" },
        { key: "pb_ratio", label: "P/B Ratio" },
        { key: "eps", label: "EPS", prefix: "₹" },
        { key: "dividend_yield", label: "Div Yield", suffix: "%" },
        { key: "52_week_high", label: "52W High", prefix: "₹" },
        { key: "52_week_low", label: "52W Low", prefix: "₹" },
        { key: "debt_to_equity", label: "D/E Ratio" },
        { key: "roe", label: "ROE" },
        { key: "revenue_growth", label: "Rev Growth", suffix: "%" },
        { key: "profit_growth", label: "Profit Growth", suffix: "%" },
        { key: "1m_return", label: "1M Return", suffix: "%", colored: true },
        { key: "3m_return", label: "3M Return", suffix: "%", colored: true },
        { key: "6m_return", label: "6M Return", suffix: "%", colored: true },
        { key: "1y_return", label: "1Y Return", suffix: "%", colored: true },
        { key: "sector", label: "Sector" },
        { key: "industry", label: "Industry" },
    ];

    return fields
        .filter((f) => data[f.key] !== null && data[f.key] !== undefined)
        .map((f) => {
            let value = data[f.key];
            let displayValue = "";
            let colorClass = "";

            if (typeof value === "number") {
                displayValue = `${f.prefix || ""}${value.toFixed(2)}${f.suffix || ""}`;
                if (f.colored) {
                    colorClass = value >= 0 ? "positive" : "negative";
                }
            } else {
                displayValue = `${f.prefix || ""}${value}${f.suffix || ""}`;
            }

            return `<div class="data-item">
                <span class="label">${f.label}</span>
                <span class="value ${colorClass}">${displayValue}</span>
            </div>`;
        })
        .join("");
}

// ── Technical Analysis Message ─────────────────────────────────
function addTechnicalAnalysisMessage(techData, currentPrice) {
    const msg = document.createElement("div");
    msg.className = "message technical-message";

    let html = `<div class="tech-header">
        <h3>📐 Technical Analysis</h3>
        <span class="tech-subtitle">Support/Resistance • Chart Patterns • Swing Indicators</span>
    </div>`;

    // Support & Resistance Section
    const sr = techData.support_resistance || {};
    if (sr.support_levels?.length || sr.resistance_levels?.length) {
        html += `<div class="tech-section">
            <h4>🎯 Support & Resistance Levels</h4>
            <div class="sr-grid">`;

        if (sr.resistance_levels?.length) {
            html += `<div class="sr-column resistance-col">
                <div class="sr-col-header resistance-header">Resistance ↑</div>`;
            sr.resistance_levels.forEach((r, i) => {
                const pct = currentPrice ? ((r.price - currentPrice) / currentPrice * 100).toFixed(1) : "?";
                html += `<div class="sr-level resistance-level">
                    <span class="sr-label">R${i + 1}</span>
                    <span class="sr-price">₹${r.price.toFixed(2)}</span>
                    <span class="sr-zone">₹${r.zone_low}–₹${r.zone_high}</span>
                    <span class="sr-strength">${"●".repeat(Math.min(r.strength, 5))}</span>
                    <span class="sr-pct">+${pct}%</span>
                </div>`;
            });
            html += `</div>`;
        }

        if (currentPrice) {
            html += `<div class="sr-current-price">
                <span>CMP</span>
                <span class="cmp-value">₹${currentPrice.toFixed(2)}</span>
            </div>`;
        }

        if (sr.support_levels?.length) {
            html += `<div class="sr-column support-col">
                <div class="sr-col-header support-header">Support ↓</div>`;
            sr.support_levels.forEach((s, i) => {
                const pct = currentPrice ? ((currentPrice - s.price) / currentPrice * 100).toFixed(1) : "?";
                html += `<div class="sr-level support-level">
                    <span class="sr-label">S${i + 1}</span>
                    <span class="sr-price">₹${s.price.toFixed(2)}</span>
                    <span class="sr-zone">₹${s.zone_low}–₹${s.zone_high}</span>
                    <span class="sr-strength">${"●".repeat(Math.min(s.strength, 5))}</span>
                    <span class="sr-pct">-${pct}%</span>
                </div>`;
            });
            html += `</div>`;
        }

        html += `</div></div>`;
    }

    // Fibonacci Levels
    if (sr.fibonacci && sr.fibonacci.swing_high) {
        const fib = sr.fibonacci;
        html += `<div class="tech-section">
            <h4>📏 Fibonacci Retracement</h4>
            <div class="fib-grid">
                <div class="fib-level"><span class="fib-pct">0%</span><span class="fib-price">₹${fib.level_0}</span></div>
                <div class="fib-level"><span class="fib-pct">23.6%</span><span class="fib-price">₹${fib.level_236}</span></div>
                <div class="fib-level"><span class="fib-pct">38.2%</span><span class="fib-price">₹${fib.level_382}</span></div>
                <div class="fib-level fib-key"><span class="fib-pct">50.0%</span><span class="fib-price">₹${fib.level_500}</span></div>
                <div class="fib-level fib-key"><span class="fib-pct">61.8%</span><span class="fib-price">₹${fib.level_618}</span></div>
                <div class="fib-level"><span class="fib-pct">78.6%</span><span class="fib-price">₹${fib.level_786}</span></div>
                <div class="fib-level"><span class="fib-pct">100%</span><span class="fib-price">₹${fib.level_100}</span></div>
            </div>
        </div>`;
    }

    // Pivot Points
    if (sr.pivot_classic && sr.pivot_classic.pivot) {
        const pv = sr.pivot_classic;
        html += `<div class="tech-section">
            <h4>🔄 Classic Pivot Points</h4>
            <div class="pivot-grid">
                <div class="pivot-item pivot-r">R3: ₹${pv.r3}</div>
                <div class="pivot-item pivot-r">R2: ₹${pv.r2}</div>
                <div class="pivot-item pivot-r">R1: ₹${pv.r1}</div>
                <div class="pivot-item pivot-p">Pivot: ₹${pv.pivot}</div>
                <div class="pivot-item pivot-s">S1: ₹${pv.s1}</div>
                <div class="pivot-item pivot-s">S2: ₹${pv.s2}</div>
                <div class="pivot-item pivot-s">S3: ₹${pv.s3}</div>
            </div>
        </div>`;
    }

    // Moving Averages
    if (sr.moving_averages && Object.keys(sr.moving_averages).length) {
        const ma = sr.moving_averages;
        html += `<div class="tech-section">
            <h4>📊 Moving Averages</h4>
            <div class="ma-grid">`;
        const maOrder = ["ema_20", "sma_20", "ema_50", "sma_50", "ema_100", "sma_100", "ema_200", "sma_200"];
        maOrder.forEach(key => {
            if (ma[key] !== undefined) {
                const label = key.toUpperCase().replace("_", " ");
                const aboveBelow = currentPrice && ma[key] < currentPrice ? "ma-above" : "ma-below";
                html += `<div class="ma-item ${aboveBelow}">
                    <span class="ma-label">${label}</span>
                    <span class="ma-price">₹${ma[key].toFixed(2)}</span>
                </div>`;
            }
        });
        html += `</div></div>`;
    }

    // Chart Patterns
    const patterns = techData.chart_patterns || [];
    if (patterns.length) {
        html += `<div class="tech-section">
            <h4>📈 Chart Patterns Detected</h4>
            <div class="patterns-list">`;
        patterns.forEach(p => {
            const typeClass = p.type === "bullish" ? "pattern-bullish" : p.type === "bearish" ? "pattern-bearish" : "pattern-neutral";
            const emoji = p.type === "bullish" ? "🟢" : p.type === "bearish" ? "🔴" : "🟡";
            html += `<div class="pattern-card ${typeClass}">
                <div class="pattern-header">
                    <span class="pattern-emoji">${emoji}</span>
                    <span class="pattern-name">${escapeHtml(p.pattern)}</span>
                    <span class="pattern-type">${p.type.toUpperCase()}</span>
                    ${p.reliability ? `<span class="pattern-reliability">${p.reliability}</span>` : ""}
                </div>
                <div class="pattern-desc">${escapeHtml(p.description || "")}</div>
                ${p.target ? `<div class="pattern-target">Target: ₹${p.target}</div>` : ""}
                ${p.implication ? `<div class="pattern-impl">${escapeHtml(p.implication)}</div>` : ""}
            </div>`;
        });
        html += `</div></div>`;
    }

    // Swing Indicators
    const swing = techData.swing_indicators || {};
    if (Object.keys(swing).length) {
        html += `<div class="tech-section">
            <h4>🔧 Swing Trading Indicators</h4>
            <div class="swing-grid">`;

        if (swing.swing_score !== undefined) {
            const scoreColor = swing.swing_score >= 60 ? "var(--accent-green)" : swing.swing_score <= 40 ? "var(--accent-red)" : "var(--accent-gold)";
            html += `<div class="swing-score-card">
                <div class="swing-score-label">Swing Score</div>
                <div class="swing-score-value" style="color: ${scoreColor}">${swing.swing_score}/100</div>
                <div class="swing-score-bias">${swing.swing_bias || "Neutral"}</div>
            </div>`;
        }

        const indicators = [
            { key: "rsi_14", label: "RSI (14)", signal: swing.rsi_signal },
            { key: "macd", label: "MACD", signal: swing.macd_trend, extra: swing.macd_crossover },
            { key: "bb_signal", label: "Bollinger", signal: swing.bb_signal },
            { key: "atr_14", label: "ATR (14)", signal: `₹${swing.atr_14} (${swing.atr_pct}%)`, prefix: "" },
            { key: "stoch_rsi", label: "Stoch RSI", signal: swing.stoch_rsi_signal },
            { key: "relative_volume", label: "Rel. Volume", signal: swing.volume_signal },
            { key: "obv_trend", label: "OBV", signal: swing.obv_trend },
        ];

        indicators.forEach(ind => {
            const val = swing[ind.key];
            if (val !== undefined && val !== null) {
                const displayVal = typeof val === "number" ? val.toFixed(2) : val;
                html += `<div class="swing-item">
                    <span class="swing-label">${ind.label}</span>
                    <span class="swing-value">${ind.prefix !== undefined ? ind.prefix : ""}${displayVal}</span>
                    ${ind.signal ? `<span class="swing-signal">${ind.signal}</span>` : ""}
                    ${ind.extra ? `<span class="swing-extra">${ind.extra}</span>` : ""}
                </div>`;
            }
        });

        if (swing.suggested_sl && swing.suggested_target) {
            html += `<div class="swing-atr-levels">
                <div class="atr-level atr-sl">SL: ₹${swing.suggested_sl.toFixed(2)}</div>
                <div class="atr-level atr-target">Target: ₹${swing.suggested_target.toFixed(2)}</div>
            </div>`;
        }

        html += `</div></div>`;
    }

    msg.innerHTML = html;
    chatMessages.appendChild(msg);
    scrollToBottom();
}

function addAgentMessage(type, agent, argument, providerInfo) {
    const msg = document.createElement("div");
    msg.className = `message ${type}-message`;
    const renderedMarkdown = renderMarkdown(argument);
    const providerBadge = buildProviderBadge(providerInfo);
    msg.innerHTML = `
        <div class="agent-label">${escapeHtml(agent)}${providerBadge}</div>
        <div class="message-body">${renderedMarkdown}</div>
    `;
    chatMessages.appendChild(msg);
    scrollToBottom();
}

function addJudgeMessage(verdict) {
    const msg = document.createElement("div");
    msg.className = "message judge-message";

    const rec = verdict.recommendation.toUpperCase();
    const badgeClass = rec === "BUY" ? "buy" : rec === "HOLD" ? "hold" : "avoid";
    const confidence = verdict.confidence;
    const confidencePercent = (confidence / 10) * 100;

    let fillColor;
    if (confidence >= 7) fillColor = "var(--accent-green)";
    else if (confidence >= 4) fillColor = "var(--accent-gold)";
    else fillColor = "var(--accent-red)";

    const renderedAnalysis = renderMarkdown(verdict.analysis);
    const providerBadge = buildProviderBadge({
        provider: verdict.provider,
        providers_attempted: verdict.providers_attempted,
        errors: verdict.errors,
    });

    msg.innerHTML = `
        <div class="agent-label">
            ${escapeHtml(verdict.agent)}
            <span class="verdict-badge ${badgeClass}">${rec}</span>
            ${providerBadge}
        </div>
        <div class="confidence-bar">
            <span>Confidence:</span>
            <div class="confidence-track">
                <div class="confidence-fill" style="width: ${confidencePercent}%; background: ${fillColor};"></div>
            </div>
            <span>${confidence}/10</span>
        </div>
        <div class="message-body">${renderedAnalysis}</div>
    `;
    chatMessages.appendChild(msg);
    scrollToBottom();
}

function addDisclaimerMessage(text) {
    const msg = document.createElement("div");
    msg.className = "message disclaimer-message";
    msg.textContent = text;
    chatMessages.appendChild(msg);
    scrollToBottom();
}

// ── Provider Badge Builder ─────────────────────────────────────

function buildProviderBadge(providerInfo) {
    if (!providerInfo) return "";

    const provider = providerInfo.provider || "none";
    const attempted = providerInfo.providers_attempted || [];
    const errors = providerInfo.errors || {};

    const isSuccess = provider !== "none";
    const badgeClass = isSuccess ? "provider-success" : "provider-failed";
    const icon = isSuccess ? "✓" : "✗";
    const label = isSuccess ? provider : "all failed";

    // Build tooltip with attempt details
    let tooltipLines = [];
    if (attempted.length > 0) {
        tooltipLines.push(`Attempted: ${attempted.join(" → ")}`);
    }
    if (isSuccess) {
        tooltipLines.push(`Responded: ${provider}`);
    }
    const errorEntries = Object.entries(errors);
    if (errorEntries.length > 0) {
        tooltipLines.push("---");
        for (const [prov, errMsg] of errorEntries) {
            const shortErr = errMsg.length > 80 ? errMsg.substring(0, 80) + "…" : errMsg;
            tooltipLines.push(`${prov}: ${shortErr}`);
        }
    }

    const tooltip = escapeHtml(tooltipLines.join("\n"));

    return `<span class="provider-badge ${badgeClass}" title="${tooltip}">
        <span class="provider-icon">${icon}</span>
        <span class="provider-name">${escapeHtml(label)}</span>
        ${!isSuccess && attempted.length > 0 ? `<span class="provider-tried">(tried: ${escapeHtml(attempted.join(", "))})</span>` : ""}
    </span>`;
}

// ── Utilities ──────────────────────────────────────────────────

function scrollToBottom() {
    const container = document.getElementById("chatContainer");
    setTimeout(() => {
        container.scrollTop = container.scrollHeight;
    }, 50);
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function renderMarkdown(text) {
    if (typeof marked !== "undefined" && marked.parse) {
        try {
            return marked.parse(text);
        } catch (e) {
            console.warn("Markdown parsing failed:", e);
        }
    }
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/\*(.*?)\*/g, "<em>$1</em>")
        .replace(/\n/g, "<br>");
}
