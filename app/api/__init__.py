"""
API module for RedBarSushiAI FastAPI application.

This module contains API routers for the different components of the application.
"""

from fastapi import APIRouter

# Import routers
from app.api.realtime import router as realtime_router
from app.api.voice import router as voice_router
from app.api.voice_async import router as voice_async_router

# Create main API router
api_router = APIRouter()

# Include routers
api_router.include_router(realtime_router, prefix="/realtime")
api_router.include_router(voice_router, prefix="")  # Root path for voice routes
api_router.include_router(voice_async_router, prefix="/async")  # Async routes under /async prefix

# Export the router
__all__ = ["api_router"]