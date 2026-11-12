"""Debate API endpoint: POST /api/debate."""

import logging
from fastapi import APIRouter, HTTPException

from models.schemas import DebateRequest, DebateResponse
from services.stock_service import resolve_ticker, get_similar_tickers, fetch_stock_data
from services.debate_service import run_debate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["debate"])


@router.post("/debate", response_model=DebateResponse)
async def create_debate(request: DebateRequest):
    """
    Analyze a stock with Bull, Bear, and Judge AI agents.

    Takes a stock name, resolves it to an NSE ticker, fetches live data,
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

    # Step 2: Fetch stock data
    try:
        stock_data = await fetch_stock_data(ticker)
    except RuntimeError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Could not fetch data for {ticker}: {str(e)}",
        )

    # Extract the full stock name from data
    full_name = stock_data.pop("stock_name", stock_name)

    # Step 3: Run the debate
    try:
        debate_result = await run_debate(full_name, ticker, stock_data)
    except RuntimeError as e:
        raise HTTPException(
            status_code=503,
            detail=f"AI services unavailable: {str(e)}",
        )

    # Step 4: Build response
    return DebateResponse(
        ticker=ticker,
        stock_name=full_name,
        stock_data=stock_data,
        bullish=debate_result["bullish"],
        bearish=debate_result["bearish"],
        verdict=debate_result["verdict"],
    )
