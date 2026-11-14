"""Debate API endpoints: stock-data, bull, bear, judge, stock list, and legacy combined debate."""

import logging
import pandas as pd
from fastapi import APIRouter, HTTPException

from models.schemas import (
    DebateRequest, DebateResponse,
    StockDataRequest, StockDataResponse,
    BullRequest, BullResponse,
    BearRequest, BearResponse,
    JudgeRequest, JudgeResponse,
)
from services.stock_service import resolve_ticker, get_similar_tickers, fetch_stock_data
from services.debate_service import run_debate, run_bull, run_bear, run_judge
from services.technical_analysis import run_full_technical_analysis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["debate"])


# ── Helper: resolve ticker + fetch data ─────────────────────────

async def _resolve_and_fetch(stock_name: str) -> tuple:
    """
    Resolve ticker, fetch stock data and history, run technical analysis.
    Returns (ticker, full_name, stock_data, technical_data).
    Raises HTTPException on failure.
    """
    ticker = resolve_ticker(stock_name)
    if not ticker:
        suggestions = get_similar_tickers(stock_name)
        suggestion_text = ""
        if suggestions:
            suggestion_text = f" Did you mean: {', '.join(suggestions)}?"
        raise HTTPException(
            status_code=404,
            detail=f"Could not find stock '{stock_name}'.{suggestion_text}",
        )

    # Fetch stock data (with graceful degradation)
    stock_data_error = None
    hist = pd.DataFrame()
    try:
        stock_data, hist = await fetch_stock_data(ticker)
    except RuntimeError as e:
        stock_data_error = str(e)
        logger.warning(f"Stock data fetch failed for {ticker}: {e}")
        stock_data = {
            "stock_name": ticker.replace(".NS", "").replace(".BO", ""),
            "current_price": None, "market_cap": None, "pe_ratio": None,
            "pb_ratio": None, "eps": None, "dividend_yield": None,
            "52_week_high": None, "52_week_low": None,
            "debt_to_equity": None, "roe": None, "revenue_growth": None,
            "profit_growth": None, "promoter_holding": None,
            "1m_return": None, "3m_return": None,
            "6m_return": None, "1y_return": None,
            "volume": None, "avg_volume": None, "sector": None, "industry": None,
        }

    full_name = stock_data.pop("stock_name", stock_name)

    # Run technical analysis
    technical_data = {}
    current_price = stock_data.get("current_price")
    if current_price and hist is not None and not hist.empty:
        try:
            technical_data = run_full_technical_analysis(hist, current_price)
            logger.info(f"Technical analysis complete for {ticker}: "
                        f"{len(technical_data.get('chart_patterns', []))} patterns, "
                        f"{len(technical_data.get('support_resistance', {}).get('support_levels', []))} supports, "
                        f"{len(technical_data.get('support_resistance', {}).get('resistance_levels', []))} resistances")
        except Exception as e:
            logger.warning(f"Technical analysis failed for {ticker}: {e}")

    return ticker, full_name, stock_data, technical_data


# ── GET /api/stocks (searchable dropdown) ───────────────────────

@router.get("/stocks")
async def get_stock_list():
    """Return categorized list of NSE stocks for the search dropdown.

    Fetches live data from NSE India APIs (cached for 6 hours).
    Falls back to a hardcoded list if the API is unreachable.
    """
    from services.nifty_stocks import get_all_stocks, get_stock_categories
    stocks = await get_all_stocks()
    categories = await get_stock_categories()
    return {
        "stocks": stocks,
        "categories": categories,
        "count": len(stocks),
    }


# ── POST /api/stock-data ────────────────────────────────────────

@router.post("/stock-data", response_model=StockDataResponse)
async def get_stock_data(request: StockDataRequest):
    """
    Fetch stock data + technical analysis for a given stock name.
    This is Step 1 of the sequential debate flow.
    """
    stock_name = request.stock_name.strip()
    logger.info(f"Stock data requested for: {stock_name}")

    ticker, full_name, stock_data, technical_data = await _resolve_and_fetch(stock_name)

    return StockDataResponse(
        ticker=ticker,
        stock_name=full_name,
        stock_data=stock_data,
        technical_data=technical_data,
    )


# ── POST /api/debate/bull ───────────────────────────────────────

@router.post("/debate/bull", response_model=BullResponse)
async def create_bull_analysis(request: BullRequest):
    """
    Run the Bull analyst independently.
    This is Step 2 of the sequential debate flow.
    """
    logger.info(f"Bull analysis requested for: {request.stock_name} ({request.ticker}) mode={request.analysis_mode}")

    try:
        result = await run_bull(
            stock_name=request.stock_name,
            ticker=request.ticker,
            stock_data=request.stock_data,
            technical_data=request.technical_data,
            analysis_mode=request.analysis_mode.value,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"AI services unavailable: {str(e)}")

    return BullResponse(
        agent=result["agent"],
        argument=result["argument"],
        provider=result["provider"],
        providers_attempted=result["providers_attempted"],
        errors=result["errors"],
    )


# ── POST /api/debate/bear ───────────────────────────────────────

@router.post("/debate/bear", response_model=BearResponse)
async def create_bear_analysis(request: BearRequest):
    """
    Run the Bear analyst independently with bull context.
    This is Step 3 of the sequential debate flow.
    """
    logger.info(f"Bear analysis requested for: {request.stock_name} ({request.ticker}) mode={request.analysis_mode}")

    try:
        result = await run_bear(
            stock_name=request.stock_name,
            ticker=request.ticker,
            stock_data=request.stock_data,
            technical_data=request.technical_data,
            analysis_mode=request.analysis_mode.value,
            bull_argument=request.bull_argument,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"AI services unavailable: {str(e)}")

    return BearResponse(
        agent=result["agent"],
        argument=result["argument"],
        provider=result["provider"],
        providers_attempted=result["providers_attempted"],
        errors=result["errors"],
    )


# ── POST /api/debate/judge ──────────────────────────────────────

@router.post("/debate/judge", response_model=JudgeResponse)
async def create_judge_verdict(request: JudgeRequest):
    """
    Run the Judge with both bull and bear arguments.
    This is Step 4 of the sequential debate flow.
    """
    logger.info(f"Judge verdict requested for: {request.stock_name} ({request.ticker}) mode={request.analysis_mode}")

    try:
        result = await run_judge(
            stock_name=request.stock_name,
            ticker=request.ticker,
            stock_data=request.stock_data,
            technical_data=request.technical_data,
            analysis_mode=request.analysis_mode.value,
            bull_argument=request.bull_argument,
            bear_argument=request.bear_argument,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"AI services unavailable: {str(e)}")

    return JudgeResponse(
        agent=result["agent"],
        recommendation=result["recommendation"],
        confidence=result["confidence"],
        analysis=result["analysis"],
        provider=result["provider"],
        providers_attempted=result["providers_attempted"],
        errors=result["errors"],
    )


# ── POST /api/debate (legacy combined endpoint) ────────────────

@router.post("/debate", response_model=DebateResponse)
async def create_debate(request: DebateRequest):
    """
    Analyze a stock with Bull, Bear, and Judge AI agents (combined endpoint).

    Takes a stock name, resolves it to an NSE ticker, fetches live data,
    runs technical analysis (S/R, patterns, swing indicators),
    and runs a three-agent debate.

    This is the legacy combined endpoint. For progressive rendering,
    use the individual endpoints: /api/stock-data, /api/debate/bull,
    /api/debate/bear, /api/debate/judge.
    """
    stock_name = request.stock_name.strip()
    logger.info(f"Debate requested for: {stock_name} mode={request.analysis_mode}")

    ticker, full_name, stock_data, technical_data = await _resolve_and_fetch(stock_name)

    # Run the debate
    try:
        debate_result = await run_debate(
            full_name, ticker, stock_data, technical_data,
            analysis_mode=request.analysis_mode.value,
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=503,
            detail=f"AI services unavailable: {str(e)}",
        )

    return DebateResponse(
        ticker=ticker,
        stock_name=full_name,
        stock_data=stock_data,
        technical_data=technical_data,
        bullish=debate_result["bullish"],
        bearish=debate_result["bearish"],
        verdict=debate_result["verdict"],
    )
