"""FastAPI application entry point with CORS, static files, and background scheduler."""

import ssl_fix 

import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import settings
from routers import debate, screener, alerts, watchlist

# ── Logging Setup ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── FastAPI App ─────────────────────────────────────────────────
app = FastAPI(
    title="Stock Debate Chat",
    description="AI-powered stock analysis with Bull, Bear, and Judge agents",
    version="1.0.0",
)

# ── CORS Middleware ─────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register Routers ───────────────────────────────────────────
# Phase 1: Core Debate
app.include_router(debate.router)

# Phase 2: Stock Screener
app.include_router(screener.router)

# Phase 3: Alerts & Watchlist
app.include_router(alerts.router)
app.include_router(watchlist.router)

# ── Serve Frontend Static Files ─────────────────────────────────
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

    @app.get("/")
    async def serve_frontend():
        """Serve the frontend index.html."""
        return FileResponse(str(frontend_dir / "index.html"))
else:
    @app.get("/")
    async def root():
        """API root when frontend is not available."""
        return {
            "message": "Stock Debate Chat API",
            "docs": "/docs",
            "version": "1.0.0",
        }

# ── Health Check ────────────────────────────────────────────────
@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    from services.ai_service import ai_service
    return {
        "status": "healthy",
        "ai_providers": ai_service.available_providers,
    }


# ── Background Scheduler (Phase 3) ─────────────────────────────
scheduler = None


def _setup_scheduler():
    """Set up APScheduler for periodic alert scans."""
    global scheduler
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from services.alert_service import run_alert_scan

        scheduler = AsyncIOScheduler()

        # Schedule alert scan every N hours
        scheduler.add_job(
            run_alert_scan,
            "interval",
            hours=settings.ALERT_SCAN_INTERVAL_HOURS,
            id="alert_scan",
            name="Periodic Alert Scan",
            replace_existing=True,
        )

        scheduler.start()
        logger.info(
            f"Background scheduler started — alert scan every "
            f"{settings.ALERT_SCAN_INTERVAL_HOURS} hours"
        )
    except ImportError:
        logger.warning("APScheduler not installed — background alerts disabled")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")


# ── Startup Event ──────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    """Log startup information and start background tasks."""
    from services.ai_service import ai_service

    logger.info("=" * 60)
    logger.info("Stock Debate Chat API starting up...")
    logger.info(f"Available AI providers: {ai_service.available_providers}")

    if not ai_service.available_providers:
        logger.warning(
            "No AI providers configured! "
            "Please set at least one API key in .env file."
        )

    # Start background scheduler for alerts
    _setup_scheduler()

    logger.info(f"API docs: http://localhost:{settings.BACKEND_PORT}/docs")
    logger.info(f"Frontend:  http://localhost:{settings.BACKEND_PORT}/")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    global scheduler
    if scheduler:
        scheduler.shutdown(wait=False)
        logger.info("Background scheduler stopped")
    logger.info("Stock Debate Chat API shutting down...")


# ── Run with Uvicorn ────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.BACKEND_PORT,
        reload=True,
    )
