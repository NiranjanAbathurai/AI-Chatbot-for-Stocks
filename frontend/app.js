/**
 * Stock Debate Chat — Frontend Application
 * Handles API calls, message rendering, and UI interactions.
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

    // Update UI state
    stockInput.value = "";
    stockInput.disabled = true;
    analyzeBtn.disabled = true;

    // Add user message
    addUserMessage(stockName);

    // Add loading message
    const loadingId = addLoadingMessage();

    try {
        const res = await fetch(`${API_BASE}/api/debate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ stock_name: stockName }),
        });

        // Remove loading message
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

    // 2. Bull argument (with slight delay for animation)
    setTimeout(() => {
        addAgentMessage("bull", data.bullish.agent, data.bullish.argument);
    }, 200);

    // 3. Bear argument
    setTimeout(() => {
        addAgentMessage("bear", data.bearish.agent, data.bearish.argument);
    }, 400);

    // 4. Judge verdict
    setTimeout(() => {
        addJudgeMessage(data.verdict);
    }, 600);

    // 5. Disclaimer
    setTimeout(() => {
        addDisclaimerMessage(data.disclaimer);
    }, 800);
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
        <div class="loading-stage">Fetching stock data → Running Bull & Bear → Awaiting verdict</div>
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
    // Fallback: basic formatting
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/\*(.*?)\*/g, "<em>$1</em>")
        .replace(/\n/g, "<br>");
}
