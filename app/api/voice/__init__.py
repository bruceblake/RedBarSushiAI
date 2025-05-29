"""
Voice API module for handling Twilio voice calls.

This package contains modules for handling voice interactions with Twilio,
supporting both ConversationRelay and legacy Media Streams approaches.
"""

from fastapi import APIRouter
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Import the TwiML router (always needed for both paths)
from app.api.voice.twiml import router as http_twiml_router

# Testing routes removed for production

# Create WebSocket router for media streams
websocket_router = APIRouter(tags=["Voice WebSocket"])

# Import WebSocket handler
from app.api.voice.websocket import handle_media_stream

# Register WebSocket endpoint
@websocket_router.websocket("/realtime/ws/media/{call_sid}")
async def websocket_endpoint(websocket, call_sid: str, client: str = "twilio", time: str = ""):
    """WebSocket endpoint for Twilio Media Streams."""
    await handle_media_stream(websocket, call_sid, False, client, time)

# Export all routers
__all__ = ["http_twiml_router", "websocket_router"]