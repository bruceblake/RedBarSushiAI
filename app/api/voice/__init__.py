"""
Voice API module for handling Twilio voice calls.

This package contains modules for handling voice interactions with Twilio
using ConversationRelay for AI-powered conversations.
"""

from fastapi import APIRouter
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Import the TwiML router for handling initial call webhooks
from app.api.voice.twiml import router as http_twiml_router

# Import the ConversationRelay WebSocket router
from app.api.voice.conversation_relay import router as conversation_relay_router

# Export all routers
__all__ = ["http_twiml_router", "conversation_relay_router"]