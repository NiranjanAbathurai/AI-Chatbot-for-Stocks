"""API endpoint for stock chart data with pattern drawing overlays."""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from services.developing_scanner_service import _fetch_yahoo_chart, TIMEFRAME_CONFIG
from services.developing_patterns import detect_developing_patterns
from services.technical_analysis import detect_chart_patterns
from services.chart_drawings import generate_pattern_drawings, prepare_ohlc_for_chart
from services.pattern_image_generator import generate_pattern_image, clear_image_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chart", tags=["chart"])


@router.get("/pattern-chart")
async def get_pattern_chart(
    ticker: str = Query(..., description="NSE ticker (e.g. RELIANCE.NS)"),
    timeframe: str = Query("1d", description="Timeframe: 15m, 1h, 4h, 1d"),
    max_bars: int = Query(80, description="Max OHLC bars to return"),
    detector: str = Query("developing", description="Pattern detector: 'developing' or 'basic'"),
):
    """Fetch OHLC chart data + detected pattern drawings for a stock.

    Returns:
        - ohlc: Array of {o, h, l, c, v, t} bars
        - patterns: Array of detected patterns with drawing instructions
        - ticker, timeframe metadata

    The frontend uses this to render a candlestick chart with pattern
    annotations drawn as overlays (trendlines, necklines, markers, zones).
    """
    import asyncio

    valid_timeframes = {"15m", "1h", "4h", "1d"}
    if timeframe not in valid_timeframes:
        raise HTTPException(400, f"Invalid timeframe. Valid: {', '.join(valid_timeframes)}")

    tf_config = TIMEFRAME_CONFIG.get(timeframe, TIMEFRAME_CONFIG["1d"])

    # Ensure ticker has .NS suffix for NSE stocks
    if not ticker.endswith(".NS") and not ticker.startswith("^"):
        ticker = ticker + ".NS"

    try:
        loop = asyncio.get_event_loop()
        df, price, last_ts = await loop.run_in_executor(
            None,
            lambda: _fetch_yahoo_chart(ticker, tf_config["period"], tf_config["interval"])
        )
    except Exception as e:
        raise HTTPException(500, f"Failed to fetch chart data: {e}")

    if df is None or df.empty or len(df) < 20:
        raise HTTPException(404, f"Insufficient chart data for {ticker}")

    if not price:
        price = float(df["Close"].iloc[-1])

    # Detect patterns
    patterns_with_drawings = []

    if detector == "developing":
        raw_patterns = detect_developing_patterns(df, price)
    else:
        raw_patterns = detect_chart_patterns(df)

    for pat in raw_patterns:
        drawings = generate_pattern_drawings(pat, df)
        # Adjust drawing indices relative to the chart window
        n = len(df)
        chart_start = max(0, n - max_bars)

        adjusted_drawings = []
        for d in drawings:
            ad = dict(d)
            # Adjust x coordinates to be relative to the chart window
            if "x" in ad:
                ad["x"] = ad["x"] - chart_start
            if "x1" in ad:
                ad["x1"] = ad["x1"] - chart_start
            if "x2" in ad:
                ad["x2"] = ad["x2"] - chart_start
            if "points" in ad:
                ad["points"] = [{"x": p["x"] - chart_start, "y": p["y"]} for p in ad["points"]]

            # Skip drawings that are entirely outside the chart window
            if "x1" in ad and "x2" in ad:
                if ad["x2"] < 0:
                    continue
                ad["x1"] = max(0, ad["x1"])
            if "x" in ad and ad["x"] < 0:
                continue

            adjusted_drawings.append(ad)

        patterns_with_drawings.append({
            **pat,
            "drawings": adjusted_drawings,
        })

    # Prepare OHLC data
    ohlc = prepare_ohlc_for_chart(df, max_bars)

    return {
        "ticker": ticker,
        "timeframe": timeframe,
        "current_price": round(price, 2),
        "last_candle_time": last_ts,
        "total_bars": len(ohlc),
        "ohlc": ohlc,
        "patterns": patterns_with_drawings,
    }


@router.get("/pattern-image")
async def get_pattern_image(
    ticker: str = Query(..., description="NSE ticker (e.g. RELIANCE.NS)"),
    timeframe: str = Query("1d", description="Timeframe: 15m, 1h, 4h, 1d"),
    max_bars: int = Query(80, description="Max OHLC bars"),
    detector: str = Query("developing", description="Pattern detector: 'developing' or 'basic'"),
    pattern_index: int = Query(0, description="Which pattern to render (0 = first/best)"),
    width: int = Query(1200, description="Image width in pixels"),
    height: int = Query(650, description="Image height in pixels"),
):
    """Generate a PNG chart image with pattern annotations overlaid on candlesticks.

    Returns a PNG image (Content-Type: image/png) showing the candlestick chart
    with the detected pattern drawn on top — similar to educational chart pattern
    diagrams with labeled key points, trendlines, necklines, targets, and zones.

    Supports all pattern types: Double Top/Bottom, Head & Shoulders, Inverse H&S,
    Ascending/Descending/Symmetrical Triangle, Rising/Falling Wedge, Bull/Bear Flag,
    Cup & Handle, Parallel Channel, Sideways Range.
    """
    import asyncio

    valid_timeframes = {"15m", "1h", "4h", "1d"}
    if timeframe not in valid_timeframes:
        raise HTTPException(400, f"Invalid timeframe. Valid: {', '.join(valid_timeframes)}")

    tf_config = TIMEFRAME_CONFIG.get(timeframe, TIMEFRAME_CONFIG["1d"])

    if not ticker.endswith(".NS") and not ticker.startswith("^"):
        ticker = ticker + ".NS"

    try:
        loop = asyncio.get_event_loop()
        df, price, last_ts = await loop.run_in_executor(
            None,
            lambda: _fetch_yahoo_chart(ticker, tf_config["period"], tf_config["interval"])
        )
    except Exception as e:
        raise HTTPException(500, f"Failed to fetch chart data: {e}")

    if df is None or df.empty or len(df) < 20:
        raise HTTPException(404, f"Insufficient chart data for {ticker}")

    if not price:
        price = float(df["Close"].iloc[-1])

    # Detect patterns
    if detector == "developing":
        raw_patterns = detect_developing_patterns(df, price)
    else:
        raw_patterns = detect_chart_patterns(df)

    if not raw_patterns:
        raise HTTPException(404, f"No patterns detected for {ticker}")

    # Select the requested pattern
    idx = min(pattern_index, len(raw_patterns) - 1)
    pattern = raw_patterns[idx]

    # Generate the image
    try:
        img_bytes = await loop.run_in_executor(
            None,
            lambda: generate_pattern_image(
                df, pattern, ticker=ticker, timeframe=timeframe,
                max_bars=max_bars, width=width, height=height
            )
        )
    except Exception as e:
        logger.error(f"Image generation error: {e}")
        raise HTTPException(500, f"Failed to generate chart image: {e}")

    return Response(
        content=img_bytes,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=300",
            "X-Pattern-Name": pattern.get("pattern", "Unknown"),
            "X-Pattern-Type": pattern.get("type", "neutral"),
        }
    )


@router.get("/pattern-image-all")
async def get_all_pattern_images(
    ticker: str = Query(..., description="NSE ticker (e.g. RELIANCE.NS)"),
    timeframe: str = Query("1d", description="Timeframe: 15m, 1h, 4h, 1d"),
    max_bars: int = Query(80, description="Max OHLC bars"),
    detector: str = Query("developing", description="Pattern detector"),
):
    """Return metadata for all detected patterns with image URLs.

    Returns JSON with pattern info and URLs to fetch each pattern image.
    """
    import asyncio

    valid_timeframes = {"15m", "1h", "4h", "1d"}
    if timeframe not in valid_timeframes:
        raise HTTPException(400, f"Invalid timeframe. Valid: {', '.join(valid_timeframes)}")

    tf_config = TIMEFRAME_CONFIG.get(timeframe, TIMEFRAME_CONFIG["1d"])

    if not ticker.endswith(".NS") and not ticker.startswith("^"):
        ticker = ticker + ".NS"

    try:
        loop = asyncio.get_event_loop()
        df, price, last_ts = await loop.run_in_executor(
            None,
            lambda: _fetch_yahoo_chart(ticker, tf_config["period"], tf_config["interval"])
        )
    except Exception as e:
        raise HTTPException(500, f"Failed to fetch chart data: {e}")

    if df is None or df.empty or len(df) < 20:
        raise HTTPException(404, f"Insufficient chart data for {ticker}")

    if not price:
        price = float(df["Close"].iloc[-1])

    if detector == "developing":
        raw_patterns = detect_developing_patterns(df, price)
    else:
        raw_patterns = detect_chart_patterns(df)

    results = []
    for i, pat in enumerate(raw_patterns):
        img_url = (
            f"/api/chart/pattern-image?ticker={ticker}&timeframe={timeframe}"
            f"&max_bars={max_bars}&detector={detector}&pattern_index={i}"
        )
        results.append({
            "index": i,
            "pattern": pat.get("pattern", "Unknown"),
            "type": pat.get("type", "neutral"),
            "stage": pat.get("stage", ""),
            "structure_confidence": pat.get("structure_confidence"),
            "description": pat.get("description", ""),
            "target": pat.get("target"),
            "invalidation": pat.get("invalidation"),
            "image_url": img_url,
        })

    return {
        "ticker": ticker,
        "timeframe": timeframe,
        "current_price": round(price, 2),
        "pattern_count": len(results),
        "patterns": results,
    }
