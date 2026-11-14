"""Health Check Endpoint for SPHEREx Sky Viewer."""

from datetime import datetime, timezone
from typing import Any, Dict
from fastapi import APIRouter

from backend.app.config import FITS_CACHE_DIR, SUPPORTED_BANDS, TAP_CACHE_DIR

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=Dict[str, Any])
def get_health_status() -> Dict[str, Any]:
    """Return backend operational status, supported bands, and disk cache statistics."""
    fits_count = len(list(FITS_CACHE_DIR.glob("*.fits"))) if FITS_CACHE_DIR.exists() else 0
    tap_count = len(list(TAP_CACHE_DIR.glob("*.json"))) if TAP_CACHE_DIR.exists() else 0

    return {
        "status": "ok",
        "service": "SPHEREx Sky Viewer Real-Data Backend",
        "version": "0.1.0",
        "timestampUtc": datetime.now(timezone.utc).isoformat(),
        "supportedBands": list(SUPPORTED_BANDS),
        "cache": {
            "cachedFitsFiles": fits_count,
            "cachedTapQueries": tap_count,
        },
    }
