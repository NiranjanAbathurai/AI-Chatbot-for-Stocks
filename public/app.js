/**
 * Stock Debate Chat — Frontend Application
 * Handles API calls, message rendering, and UI interactions.
 * Enhanced with Technical Analysis display (S/R, Patterns, Swing Indicators).
 */

const API_BASE = window.location.origin;
const chatMessages = document.getElementById("chatMessages");
const stockInput = document.getElementById("stockInput");
const analyzeBtn = document.getElementById("analyzeBtn");

let isAnalyzing = false;

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

    stockInput.value = "";
    stockInput.disabled = true;
    analyzeBtn.disabled = true;

    addUserMessage(stockName);
    const loadingId = addLoadingMessage();

    try {
        const res = await fetch(`${API_BASE}/api/debate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ stock_name: stockName }),
        });

        removeMessage(loadingId);

        if (!res.ok) {
            const error = await res.json().catch(() => ({ detail: "Unknown error" }));
            addErrorMessage(error.detail || `Error ${res.status}`);
            return;
        }

        const data = await res.json();
        renderDebateResult(data);

    } catch (err) {
        removeMessage(loadingId);
        addErrorMessage("Could not connect to the server. Please try again.");
        console.error("Debate API error:", err);
    } finally {
        isAnalyzing = false;
        stockInput.disabled = false;
        analyzeBtn.disabled = false;
        stockInput.focus();
    }
}

// ── Render Debate Result ───────────────────────────────────────
function renderDebateResult(data) {
    // 1. Stock data card
    addStockDataMessage(data.stock_name, data.ticker, data.stock_data);

    // 2. Technical Analysis card (S/R, Patterns, Indicators)
    setTimeout(() => {
        if (data.technical_data && Object.keys(data.technical_data).length > 0) {
            addTechnicalAnalysisMessage(data.technical_data, data.stock_data.current_price);
        }
    }, 150);

    // 3. Bull argument
    setTimeout(() => {
        addAgentMessage("bull", data.bullish.agent, data.bullish.argument);
    }, 300);

    // 4. Bear argument
    setTimeout(() => {
        addAgentMessage("bear", data.bearish.agent, data.bearish.argument);
    }, 500);

    // 5. Judge verdict
    setTimeout(() => {
        addJudgeMessage(data.verdict);
    }, 700);

    // 6. Disclaimer
    setTimeout(() => {
        addDisclaimerMessage(data.disclaimer);
    }, 900);
}

// ── Message Builders ───────────────────────────────────────────

function addUserMessage(text) {
    const msg = document.createElement("div");
    msg.className = "message user-message";
    msg.innerHTML = `
        <div class="message-label">You</div>
        <div class="message-body">Analyze <strong>${escapeHtml(text)}</strong></div>
    `;
    chatMessages.appendChild(msg);
    scrollToBottom();
}

function addLoadingMessage() {
    const id = "loading-" + Date.now();
    const msg = document.createElement("div");
    msg.className = "message loading-message";
    msg.id = id;
    msg.innerHTML = `
        <div class="loading-text">🤖 AI agents are analyzing...</div>
        <div class="loading-stage">Fetching data → Computing S/R & Patterns → Running Bull & Bear → Awaiting verdict</div>
        <div class="loading-dots">
            <span></span><span></span><span></span>
        </div>
    `;
    chatMessages.appendChild(msg);
    scrollToBottom();
    return id;
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

        // Swing Score
        if (swing.swing_score !== undefined) {
            const scoreColor = swing.swing_score >= 60 ? "var(--accent-green)" : swing.swing_score <= 40 ? "var(--accent-red)" : "var(--accent-gold)";
            html += `<div class="swing-score-card">
                <div class="swing-score-label">Swing Score</div>
                <div class="swing-score-value" style="color: ${scoreColor}">${swing.swing_score}/100</div>
                <div class="swing-score-bias">${swing.swing_bias || "Neutral"}</div>
            </div>`;
        }

        // Indicator items
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

        // ATR-based levels
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

function addAgentMessage(type, agent, argument) {
    const msg = document.createElement("div");
    msg.className = `message ${type}-message`;
    const renderedMarkdown = renderMarkdown(argument);
    msg.innerHTML = `
        <div class="agent-label">${escapeHtml(agent)}</div>
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

    msg.innerHTML = `
        <div class="agent-label">
            ${escapeHtml(verdict.agent)}
            <span class="verdict-badge ${badgeClass}">${rec}</span>
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
