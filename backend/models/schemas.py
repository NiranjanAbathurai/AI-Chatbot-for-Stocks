"""Pydantic request/response models for the Stock Debate Chat API."""

from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional


# ── Analysis Mode Enum ──────────────────────────────────────────

class AnalysisMode(str, Enum):
    """Trading analysis mode that determines prompt focus."""
    swing_trading = "swing_trading"
    option_trading = "option_trading"
    short_term = "short_term"
    investment = "investment"


# ── Request Models ──────────────────────────────────────────────

class DebateRequest(BaseModel):
    """Request body for the legacy combined debate endpoint."""
    stock_name: str = Field(..., min_length=1, max_length=100, description="Stock name or ticker symbol")
    analysis_mode: AnalysisMode = Field(default=AnalysisMode.swing_trading, description="Analysis mode")


class StockDataRequest(BaseModel):
    """Request body for the stock data fetch endpoint."""
    stock_name: str = Field(..., min_length=1, max_length=100, description="Stock name or ticker symbol")


class BullRequest(BaseModel):
    """Request body for the bull analysis endpoint."""
    ticker: str
    stock_name: str
    stock_data: dict
    technical_data: dict = {}
    analysis_mode: AnalysisMode = Field(default=AnalysisMode.swing_trading)


class BearRequest(BaseModel):
    """Request body for the bear analysis endpoint."""
    ticker: str
    stock_name: str
    stock_data: dict
    technical_data: dict = {}
    analysis_mode: AnalysisMode = Field(default=AnalysisMode.swing_trading)
    bull_argument: str = Field(..., description="The bull analyst's argument to counter")


class JudgeRequest(BaseModel):
    """Request body for the judge verdict endpoint."""
    ticker: str
    stock_name: str
    stock_data: dict
    technical_data: dict = {}
    analysis_mode: AnalysisMode = Field(default=AnalysisMode.swing_trading)
    bull_argument: str = Field(..., description="The bull analyst's argument")
    bear_argument: str = Field(..., description="The bear analyst's argument")


class WatchlistAddRequest(BaseModel):
    """Request body for adding a stock to the watchlist."""
    stock_name: str = Field(..., min_length=1, max_length=100)
    ticker: Optional[str] = None


# ── Stock Data Models ───────────────────────────────────────────

class StockData(BaseModel):
    """Comprehensive stock data fetched from yfinance."""
    current_price: Optional[float] = None
    market_cap: Optional[str] = None
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    eps: Optional[float] = None
    dividend_yield: Optional[float] = None
    week_52_high: Optional[float] = Field(None, alias="52_week_high")
    week_52_low: Optional[float] = Field(None, alias="52_week_low")
    debt_to_equity: Optional[float] = None
    roe: Optional[float] = None
    revenue_growth: Optional[float] = None
    profit_growth: Optional[float] = None
    promoter_holding: Optional[float] = None
    return_1m: Optional[float] = Field(None, alias="1m_return")
    return_3m: Optional[float] = Field(None, alias="3m_return")
    return_6m: Optional[float] = Field(None, alias="6m_return")
    return_1y: Optional[float] = Field(None, alias="1y_return")
    volume: Optional[int] = None
    avg_volume: Optional[int] = None
    sector: Optional[str] = None
    industry: Optional[str] = None

    model_config = {"populate_by_name": True}


# ── Response Models ─────────────────────────────────────────────

class StockDataResponse(BaseModel):
    """Response from the stock data fetch endpoint."""
    ticker: str
    stock_name: str
    stock_data: dict
    technical_data: dict = {}


class BullResponse(BaseModel):
    """Response from the bull analysis endpoint."""
    agent: str = "🐂 Bullish Analyst"
    argument: str
    provider: Optional[str] = None
    providers_attempted: Optional[list[str]] = None
    errors: Optional[dict[str, str]] = None


class BearResponse(BaseModel):
    """Response from the bear analysis endpoint."""
    agent: str = "🐻 Bearish Analyst"
    argument: str
    provider: Optional[str] = None
    providers_attempted: Optional[list[str]] = None
    errors: Optional[dict[str, str]] = None


class JudgeResponse(BaseModel):
    """Response from the judge verdict endpoint."""
    agent: str = "⚖️ Judge"
    recommendation: str  # BUY / HOLD / AVOID
    confidence: int = Field(..., ge=1, le=10)
    analysis: str
    provider: Optional[str] = None
    providers_attempted: Optional[list[str]] = None
    errors: Optional[dict[str, str]] = None


# ── Agent Response Models (legacy compat) ───────────────────────

class AgentArgument(BaseModel):
    """Response from a Bull or Bear agent."""
    agent: str
    argument: str
    provider: Optional[str] = None
    providers_attempted: Optional[list[str]] = None
    errors: Optional[dict[str, str]] = None


class VerdictResponse(BaseModel):
    """Response from the Judge agent."""
    agent: str = "⚖️ Judge"
    recommendation: str  # BUY / HOLD / AVOID
    confidence: int = Field(..., ge=1, le=10)
    analysis: str
    provider: Optional[str] = None
    providers_attempted: Optional[list[str]] = None
    errors: Optional[dict[str, str]] = None


# ── Full Debate Response ────────────────────────────────────────

class DebateResponse(BaseModel):
    """Complete debate response sent to the frontend."""
    ticker: str
    stock_name: str
    stock_data: dict
    technical_data: dict = {}
    bullish: AgentArgument
    bearish: AgentArgument
    verdict: VerdictResponse
    disclaimer: str = (
        "⚠️ This is AI-generated analysis for educational purposes only. "
        "This is NOT financial advice. Always do your own research and consult "
        "a SEBI-registered financial advisor before making investment decisions."
    )


# ── Screener Models (Phase 2) ──────────────────────────────────

class ScreenerStock(BaseModel):
    """A single stock from the screener results."""
    name: str
    ticker: str
    score: float
    reasons: list[str]


class ScreenerResponse(BaseModel):
    """Screener scan results."""
    last_scan: Optional[str] = None
    buy_candidates: list[ScreenerStock] = []
    short_candidates: list[ScreenerStock] = []


# ── Alert Models (Phase 3) ──────────────────────────────────────

class Alert(BaseModel):
    """A single alert notification."""
    ticker: str
    stock_name: str
    trigger: str
    message: str
    priority: str  # high, medium, low
    timestamp: str


class WatchlistItem(BaseModel):
    """A stock in the user's watchlist."""
    ticker: str
    stock_name: str
    added_at: str


class WatchlistResponse(BaseModel):
    """Current watchlist."""
    stocks: list[WatchlistItem] = []


class AlertsResponse(BaseModel):
    """Recent alerts."""
    alerts: list[Alert] = []
