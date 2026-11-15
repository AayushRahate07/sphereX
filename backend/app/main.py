"""FastAPI Application Entry Point for SPHEREx Sky Viewer.

Serves the real-data backend vertical slice for Milestone 2.1:
- GET /api/health
- GET /api/frames
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import FITS_CACHE_DIR, TAP_CACHE_DIR
from backend.app.routers import frames_router, health_router, rgb_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("spherex_backend")

# Ensure cache directories exist on startup
FITS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
TAP_CACHE_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="SPHEREx Sky Viewer Backend",
    version="0.1.0",
    description="Scientific API serving multi-epoch SPHEREx Level 2 infrared spectral frames aligned to a common sky grid.",
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
