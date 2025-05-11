"""
API module for RedBarSushiAI FastAPI application.

This module contains API routers for the different components of the application.
"""

from fastapi import APIRouter

# Import routers
from app.api.voice import router as voice_router
from app.api.order import order_router
from app.api.menu import menu_router

# Create main API router
api_router = APIRouter()

# Include routers
api_router.include_router(voice_router, prefix="")  # Root path for voice routes
api_router.include_router(order_router, prefix="/order")  # Order routes
api_router.include_router(menu_router, prefix="/menu")  # Menu routes

# Mount the refactored voice router at /realtime to match the TwiML URL
# This router contains the WebSocket endpoint for media streams
api_router.include_router(voice_router, prefix="/realtime")

# Export the router
__all__ = ["api_router"]