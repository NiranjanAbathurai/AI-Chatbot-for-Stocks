"""Debate API endpoint: POST /api/debate."""

import logging
import pandas as pd
from fastapi import APIRouter, HTTPException

from models.schemas import DebateRequest, DebateResponse
from services.stock_service import resolve_ticker, get_similar_tickers, fetch_stock_data
from services.debate_service import run_debate
from services.technical_analysis import run_full_technical_analysis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["debate"])


@router.post("/debate", response_model=DebateResponse)
async def create_debate(request: DebateRequest):
    """
    Analyze a stock with Bull, Bear, and Judge AI agents.

    Takes a stock name, resolves it to an NSE ticker, fetches live data,
    runs technical analysis (S/R, patterns, swing indicators),
    and runs a three-agent debate.
    """
    stock_name = request.stock_name.strip()
    logger.info(f"Debate requested for: {stock_name}")

    # Step 1: Resolve ticker
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

    # Step 2: Fetch stock data (with graceful degradation)
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

    # Extract the full stock name from data
    full_name = stock_data.pop("stock_name", stock_name)

    # Step 3: Run technical analysis
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

    # Step 4: Run the debate
    try:
        debate_result = await run_debate(
            full_name, ticker, stock_data, technical_data, stock_data_error
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=503,
            detail=f"AI services unavailable: {str(e)}",
        )

    # Step 5: Build response
    return DebateResponse(
        ticker=ticker,
        stock_name=full_name,
        stock_data=stock_data,
        technical_data=technical_data,
        bullish=debate_result["bullish"],
        bearish=debate_result["bearish"],
        verdict=debate_result["verdict"],
    )
