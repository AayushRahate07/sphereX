"""Routers package initialization."""

from .frames import router as frames_router
from .health import router as health_router
from .rgb import router as rgb_router

__all__ = ["frames_router", "health_router", "rgb_router"]
