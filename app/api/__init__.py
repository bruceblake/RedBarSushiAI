"""
API module for RedBarSushiAI FastAPI application.

This module contains API routers for the different components of the application.
"""

from fastapi import APIRouter

# Import routers
from app.api.voice import http_twiml_router, media_stream_router, testing_router
from app.api.order import order_router
from app.api.menu import menu_router

# Create main API router
api_router = APIRouter()

# Include core routers for orders and menu
api_router.include_router(order_router, prefix="/order")  # Order routes
api_router.include_router(menu_router, prefix="/menu")  # Menu routes

# Mount TwiML HTTP endpoint router at /voice
api_router.include_router(http_twiml_router, prefix="/voice", tags=["Voice (TwiML Webhooks)"])
# This makes your TwiML endpoint:
# POST https://<host>/voice/ and POST https://<host>/voice/webhook
# Ensure Twilio console points to this exact URL.

# Mount WebSocket media endpoint router at /realtime
api_router.include_router(media_stream_router, prefix="/realtime", tags=["Voice (Realtime Media Stream)"])
# This makes your WebSocket endpoint:
# wss://<host>/realtime/ws/media/{call_sid}
# Ensure your TwiML generation creates this exact URL for the <Stream> tag.

# Mount testing endpoints
api_router.include_router(testing_router, prefix="/voice/test", tags=["Voice Testing"])

# Export the router
__all__ = ["api_router"]