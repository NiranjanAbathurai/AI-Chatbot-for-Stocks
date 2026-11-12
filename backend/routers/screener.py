"""Screener API endpoints for stock screening and suggestions."""

import logging
from fastapi import APIRouter, HTTPException

from services.screener_service import scan_stocks, get_cached_scan

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/screener", tags=["screener"])


@router.get("/scan")
async def run_scan():
    """
    Run a full stock scan on NIFTY 50 stocks.
    Returns top BUY and SHORT candidates with scores and reasons.
    This can take 1-2 minutes as it fetches data for all stocks.
    """
    try:
        result = await scan_stocks()
        return result
    except Exception as e:
        logger.error(f"Scan failed: {e}")
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")


@router.get("/top-buys")
async def get_top_buys():
    """
    Get top BUY candidates from the last scan.
    If no scan has been run, triggers a new scan.
    """
    cached = get_cached_scan()
    if cached:
        return {"stocks": cached["buy_candidates"]}

    # No cached results, run a scan
    try:
        result = await scan_stocks()
        return {"stocks": result["buy_candidates"]}
    except Exception as e:
        logger.error(f"Scan failed: {e}")
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")


@router.get("/top-shorts")
async def get_top_shorts():
    """
    Get top SHORT/AVOID candidates from the last scan.
    If no scan has been run, triggers a new scan.
    """
    cached = get_cached_scan()
    if cached:
        return {"stocks": cached["short_candidates"]}

    try:
        result = await scan_stocks()
        return {"stocks": result["short_candidates"]}
    except Exception as e:
        logger.error(f"Scan failed: {e}")
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")
