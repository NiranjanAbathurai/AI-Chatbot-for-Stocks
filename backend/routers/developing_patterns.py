"""API endpoints for Developing Pattern Scanner (Early Pattern Detection)."""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from services.developing_scanner_service import (
    scan_developing_patterns,
    get_cached_developing_scan,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/developing-patterns", tags=["developing-patterns"])


@router.get("/scan")
async def run_developing_scan(
    timeframe: str = Query("1d", description="Timeframe: 15m, 1h, 4h, 1d"),
    pattern: Optional[str] = Query(None, description="Filter by pattern name"),
    type: Optional[str] = Query(None, description="Filter: bullish, bearish, neutral"),
    stage: Optional[str] = Query(None, description="Filter by stage (e.g. 'Stage 1')"),
    min_confidence: float = Query(0.0, description="Minimum structure confidence (0-100)"),
    refresh: bool = Query(False, description="Force fresh scan"),
):
    """Scan NIFTY 50 stocks for developing chart patterns.

    Detects patterns at all stages of formation:
    - Stage 1: Early Formation
    - Stage 2: Pattern Developing
    - Stage 3: Almost Complete
    - Stage 4: Breakout Pending
    - Stage 5: Confirmed
    - Invalidated

    Patterns: Inverse H&S, H&S, Double Top/Bottom, Ascending/Descending/
    Symmetrical Triangle, Rising/Falling Wedge, Bull/Bear Flag, Cup & Handle.

    Each pattern includes:
    - Pattern Structure Confidence (0-100)
    - Breakout Confirmation Strength (0-100)
    - Key price levels (neckline, breakout, target, invalidation)
    - Development stage

    Supports timeframes: 15m, 1h, 4h, 1d
    """
    valid_timeframes = {"15m", "1h", "4h", "1d"}
    if timeframe not in valid_timeframes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe '{timeframe}'. Valid: {', '.join(valid_timeframes)}"
        )

    valid_types = {None, "bullish", "bearish", "neutral"}
    if type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid type '{type}'. Valid: bullish, bearish, neutral"
        )

    try:
        result = await scan_developing_patterns(
            timeframe=timeframe,
            pattern_filter=pattern,
            type_filter=type,
            stage_filter=stage,
            min_confidence=min_confidence,
            refresh=refresh,
        )
        return result
    except Exception as e:
        logger.error(f"Developing pattern scan failed: {e}")
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")


@router.get("/cached")
async def get_cached():
    """Return the last cached developing pattern scan results."""
    cached = get_cached_developing_scan()
    if cached:
        return {**cached, "cached": True}
    return {"results": [], "cached": False, "message": "No cached scan available. Run a scan first."}
