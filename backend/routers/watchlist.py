"""Watchlist CRUD API endpoints."""

import logging
from fastapi import APIRouter, HTTPException

from models.schemas import WatchlistAddRequest
from services.alert_service import get_watchlist, add_to_watchlist, remove_from_watchlist
from services.stock_service import resolve_ticker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["watchlist"])


@router.get("/watchlist")
async def list_watchlist():
    """Get the current watchlist."""
    stocks = get_watchlist()
    return {"stocks": stocks}


@router.post("/watchlist")
async def add_stock(request: WatchlistAddRequest):
    """Add a stock to the watchlist."""
    stock_name = request.stock_name.strip()
    ticker = request.ticker

    if not ticker:
        ticker = resolve_ticker(stock_name)
        if not ticker:
            raise HTTPException(
                status_code=404,
                detail=f"Could not resolve ticker for '{stock_name}'",
            )

    item = add_to_watchlist(ticker, stock_name)
    return {"message": f"Added {stock_name} to watchlist", "item": item}


@router.delete("/watchlist/{ticker}")
async def remove_stock(ticker: str):
    """Remove a stock from the watchlist."""
    # URL-decode the ticker (e.g., AXISBANK.NS)
    removed = remove_from_watchlist(ticker)
    if not removed:
        raise HTTPException(
            status_code=404,
            detail=f"Ticker '{ticker}' not found in watchlist",
        )
    return {"message": f"Removed {ticker} from watchlist"}
