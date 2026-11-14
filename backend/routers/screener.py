"""Screener API endpoints for stock screening and suggestions."""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from services.screener_service import (
    scan_stocks,
    get_cached_scan,
    scan_chart_patterns,
    get_cached_pattern_scan,
    scan_volatile_active_stocks,
    get_cached_volatile_scan,
)

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


@router.get("/patterns")
async def scan_patterns(
    pattern: Optional[str] = Query(None, description="Filter by pattern name (e.g. 'Double Bottom')"),
    type: Optional[str] = Query(None, description="Filter by type: 'bullish' or 'bearish'"),
    refresh: bool = Query(False, description="Force a fresh scan (ignores cache)"),
):
    """
    Scan NIFTY 50 stocks for active chart patterns.

    Returns stocks that currently show recognizable chart patterns like
    Double Top/Bottom, Head & Shoulders, Triangles, Flags, Wedges, etc.

    This can take 1-2 minutes on first run as it fetches 6 months of
    historical data for each stock. Results are cached.
    """
    # Return cached results if available and not forcing refresh
    if not refresh:
        cached = get_cached_pattern_scan()
        if cached:
            results = cached["results"]
            # Apply filters on cached data
            if type:
                # Handle "sideways" filter: match both "sideways" and "neutral" types
                if type == "sideways":
                    match_types = {"sideways", "neutral"}
                else:
                    match_types = {type}
                results = [
                    {**r, "patterns": [p for p in r["patterns"] if p.get("type") in match_types]}
                    for r in results
                ]
                results = [r for r in results if r["patterns"]]
            if pattern:
                results = [
                    {**r, "patterns": [p for p in r["patterns"] if pattern.lower() in p.get("pattern", "").lower()]}
                    for r in results
                ]
                results = [r for r in results if r["patterns"]]

            return {
                "last_scan": cached["last_scan"],
                "total_scanned": cached["total_scanned"],
                "stocks_with_patterns": len(results),
                "results": results,
                "cached": True,
            }

    try:
        result = await scan_chart_patterns(
            pattern_filter=pattern,
            type_filter=type,
        )
        result["cached"] = False
        return result
    except Exception as e:
        logger.error(f"Pattern scan failed: {e}")
        raise HTTPException(status_code=500, detail=f"Pattern scan failed: {str(e)}")


@router.get("/volatile-active")
async def scan_volatile_active(
    sort_by: str = Query("volatility_score", description="Sort by: volatility_score, volume_ratio, atr_pct, price_range_pct"),
    min_score: float = Query(0.0, description="Minimum volatility score"),
    refresh: bool = Query(False, description="Force a fresh scan (ignores cache)"),
):
    """
    Scan NIFTY 50 for high volatility and high volume stocks.

    Returns stocks ranked by volatility score, volume ratio, ATR %, etc.
    Useful for finding active/swing trading candidates.
    """
    # Return cached results if available and not forcing refresh
    if not refresh:
        cached = get_cached_volatile_scan()
        if cached:
            results = cached.get("results", [])
            # Apply min_score filter
            if min_score > 0:
                results = [r for r in results if r.get("volatility_score", 0) >= min_score]
            # Apply sorting
            valid_sorts = {"volatility_score", "volume_ratio", "atr_pct", "price_range_pct"}
            if sort_by in valid_sorts:
                results.sort(key=lambda x: x.get(sort_by, 0), reverse=True)
            return {
                "last_scan": cached["last_scan"],
                "total_scanned": cached["total_scanned"],
                "results": results,
                "cached": True,
            }

    try:
        result = await scan_volatile_active_stocks(
            sort_by=sort_by,
            min_score=min_score,
        )
        result["cached"] = False
        return result
    except Exception as e:
        logger.error(f"Volatile scan failed: {e}")
        raise HTTPException(status_code=500, detail=f"Volatile scan failed: {str(e)}")
