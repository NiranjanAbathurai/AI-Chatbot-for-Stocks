"""Alert API endpoints."""

import logging
from fastapi import APIRouter, HTTPException

from services.alert_service import get_alerts_history, run_alert_scan

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["alerts"])


@router.get("/alerts")
async def get_alerts():
    """Get recent alert history."""
    alerts = get_alerts_history(limit=50)
    return {"alerts": alerts}


@router.post("/alerts/scan-now")
async def trigger_scan():
    """Trigger an immediate alert scan on watchlist stocks."""
    try:
        alerts = await run_alert_scan()
        return {
            "message": f"Scan complete. {len(alerts)} alerts triggered.",
            "alerts": alerts,
        }
    except Exception as e:
        logger.error(f"Alert scan failed: {e}")
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")
