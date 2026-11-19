"""Batch Swing Scanner API endpoints.

Provides endpoints to:
- Trigger a full batch scan of all stocks
- Get cached/persisted scan results
- Check scan status
- Filter results by direction, confidence, category
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from services.batch_scanner_service import (
    run_batch_swing_scan,
    get_cached_batch_scan,
    is_scan_in_progress,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/batch-scanner", tags=["batch-scanner"])


@router.get("/scan")
async def trigger_batch_scan(
    min_score: float = Query(0.0, description="Minimum swing score to include"),
    direction: Optional[str] = Query(None, description="Filter: LONG, SHORT, or all"),
    refresh: bool = Query(False, description="Force fresh scan (ignores cache)"),
):
    """
    Trigger a batch swing trading scan on all NIFTY stocks.

    This scans 50+ stocks with full technical analysis:
    - Chart patterns (Double Top/Bottom, H&S, Triangles, Flags, Wedges)
    - Swing indicators (RSI, MACD, Bollinger Bands, ATR, Stochastic RSI)
    - Support/Resistance levels (pivot points, volume profile, Fibonacci)
    - Volume analysis (OBV, relative volume)

    Each stock gets a swing score (0-100) and direction (LONG/SHORT/NEUTRAL).

    Takes 1-3 minutes on first run. Results are cached and persisted to disk.
    Designed to auto-run daily at 4:00 PM IST after market close.
    """
    # Return cached results if available and not forcing refresh
    if not refresh:
        cached = get_cached_batch_scan()
        if cached and not cached.get("error"):
            # Apply runtime filters on cached data
            result = dict(cached)
            if min_score > 0:
                result["all_results"] = [r for r in result.get("all_results", []) if r["swing_score"] >= min_score]
                result["high_conviction"] = [r for r in result.get("high_conviction", []) if r["swing_score"] >= min_score]
                result["medium_conviction"] = [r for r in result.get("medium_conviction", []) if r["swing_score"] >= min_score]
            if direction:
                d = direction.upper()
                result["all_results"] = [r for r in result.get("all_results", []) if r["direction"] == d]
                if d == "LONG":
                    result["short_opportunities"] = []
                elif d == "SHORT":
                    result["long_opportunities"] = []
            result["cached"] = True
            return result

    # Check if scan is already running
    if is_scan_in_progress():
        return {
            "status": "in_progress",
            "message": "A batch scan is already running. Please wait 1-3 minutes.",
        }

    try:
        result = await run_batch_swing_scan(
            min_score=min_score,
            direction_filter=direction,
        )
        if result.get("error"):
            raise HTTPException(status_code=409, detail=result["error"])
        result["cached"] = False
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch scan failed: {e}")
        raise HTTPException(status_code=500, detail=f"Batch scan failed: {str(e)}")


@router.get("/results")
async def get_scan_results(
    min_score: float = Query(0.0, description="Minimum swing score"),
    direction: Optional[str] = Query(None, description="Filter: LONG, SHORT"),
    confidence: Optional[str] = Query(None, description="Filter: High, Medium, Low"),
    sort_by: str = Query("swing_score", description="Sort by: swing_score, risk_reward, 1m_return, atr_pct"),
    limit: int = Query(50, description="Max results to return"),
):
    """
    Get the latest batch scan results with filtering and sorting.

    Returns cached results without triggering a new scan.
    Use /scan endpoint to trigger a fresh scan.
    """
    cached = get_cached_batch_scan()
    if not cached:
        return {
            "status": "no_data",
            "message": "No batch scan results available. Run a scan first via /api/batch-scanner/scan",
        }

    results = list(cached.get("all_results", []))

    # Apply filters
    if min_score > 0:
        results = [r for r in results if r["swing_score"] >= min_score]
    if direction:
        results = [r for r in results if r["direction"] == direction.upper()]
    if confidence:
        results = [r for r in results if r["confidence"] == confidence.capitalize()]

    # Apply sorting
    valid_sorts = {"swing_score", "risk_reward", "1m_return", "1w_return", "atr_pct", "volume_ratio", "rsi"}
    sort_key = sort_by if sort_by in valid_sorts else "swing_score"

    # Handle None values in sorting
    def _sort_val(item):
        val = item.get(sort_key)
        return val if val is not None else -999

    reverse = sort_key != "rsi"  # Lower RSI = more oversold = better for longs
    results.sort(key=_sort_val, reverse=reverse)

    # Apply limit
    results = results[:limit]

    return {
        "scan_time": cached.get("scan_time"),
        "scan_date": cached.get("scan_date"),
        "scan_time_display": cached.get("scan_time_display"),
        "total_results": len(results),
        "filters_applied": {
            "min_score": min_score,
            "direction": direction,
            "confidence": confidence,
            "sort_by": sort_key,
        },
        "results": results,
    }


@router.get("/status")
async def get_scan_status():
    """
    Check the status of the batch scanner.

    Returns whether a scan is in progress, and when the last scan was run.
    """
    cached = get_cached_batch_scan()
    return {
        "in_progress": is_scan_in_progress(),
        "last_scan_time": cached.get("scan_time") if cached else None,
        "last_scan_date": cached.get("scan_date") if cached else None,
        "last_scan_display": cached.get("scan_time_display") if cached else None,
        "stocks_scanned": cached.get("stocks_scanned") if cached else 0,
        "opportunities_found": cached.get("stocks_with_opportunities") if cached else 0,
        "summary": cached.get("summary") if cached else None,
        "has_results": cached is not None,
    }


@router.get("/top-opportunities")
async def get_top_opportunities(
    count: int = Query(10, description="Number of top opportunities to return"),
):
    """
    Quick endpoint to get the top swing trading opportunities.

    Returns the highest-scored LONG and SHORT opportunities from the last scan.
    """
    cached = get_cached_batch_scan()
    if not cached:
        return {
            "status": "no_data",
            "message": "No scan results. Run /api/batch-scanner/scan first.",
        }

    return {
        "scan_time": cached.get("scan_time"),
        "scan_date": cached.get("scan_date"),
        "top_longs": cached.get("long_opportunities", [])[:count],
        "top_shorts": cached.get("short_opportunities", [])[:count],
        "high_conviction": cached.get("high_conviction", [])[:count],
        "summary": cached.get("summary"),
    }
