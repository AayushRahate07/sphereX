"""FastAPI Application Entry Point for SPHEREx Sky Viewer.

Serves the real-data backend vertical slice for Milestone 2.1:
- GET /api/health
- GET /api/frames
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from contextlib import asynccontextmanager
import threading
from backend.app.config import (
    DEFAULT_BAND,
    DEFAULT_FOV_DEG,
    DEFAULT_MAX_FRAMES,
    DEFAULT_RELEASE,
    FITS_CACHE_DIR,
    TAP_CACHE_DIR,
    TARGET_PRESETS,
)
from backend.app.routers import frames_router, health_router, rgb_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("spherex_backend")

# Ensure cache directories exist on startup
FITS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
TAP_CACHE_DIR.mkdir(parents=True, exist_ok=True)

def _warmup_preset_cache() -> None:
    """Background worker to pre-compute and warm in-memory frames cache for all challenge targets."""
    try:
        from backend.app.routers.frames import get_frames
        logger.info("Beginning background cache pre-warm for %d challenge presets...", len(TARGET_PRESETS))
        for preset in TARGET_PRESETS:
            try:
                get_frames(
                    ra=float(preset["ra"]),
                    dec=float(preset["dec"]),
                    size=DEFAULT_FOV_DEG,
                    band=DEFAULT_BAND,
                    release=DEFAULT_RELEASE,
                    max_frames=DEFAULT_MAX_FRAMES,
                )
                logger.info("Cached preset: %s", preset["name"])
            except Exception as exc:
                logger.warning("Failed to pre-warm preset %s: %s", preset["name"], exc)
        logger.info("All challenge presets pre-warmed successfully.")
    except Exception as exc:
        logger.warning("Preset cache pre-warming encountered an error: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Spawn background thread to warm up preset target cache without delaying server startup
    threading.Thread(target=_warmup_preset_cache, daemon=True).start()
    yield


app = FastAPI(
    title="SPHEREx Sky Viewer Backend",
    version="0.1.0",
    description="Scientific API serving multi-epoch SPHEREx Level 2 infrared spectral frames aligned to a common sky grid.",
    lifespan=lifespan,
)

# Enable CORS for frontend local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(health_router)
app.include_router(frames_router)
app.include_router(rgb_router)


@app.get("/")
def root():
    """Root redirect / information endpoint."""
    return {
        "service": "SPHEREx Sky Viewer API",
        "documentation": "/docs",
        "health": "/api/health",
        "frames": "/api/frames",
    }
