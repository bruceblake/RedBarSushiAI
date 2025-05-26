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

# Create a router for testing/debug endpoints
testing_router = APIRouter(tags=["Voice Testing"])

# Import testing utilities
from app.api.voice.testing import (
    process_voice_input, 
    execute_tool, 
    get_session_state, 
    trigger_fsm_event, 
    get_fsm_state, 
    cleanup_session
)

# Register testing and debugging routes
testing_router.add_api_route("/process", process_voice_input, methods=["POST"])
testing_router.add_api_route("/tool", execute_tool, methods=["POST"])
testing_router.add_api_route("/sessions/{call_sid}", get_session_state, methods=["GET"])
testing_router.add_api_route("/fsm/{call_sid}/event", trigger_fsm_event, methods=["POST"])
testing_router.add_api_route("/fsm/{call_sid}", get_fsm_state, methods=["GET"])
testing_router.add_api_route("/sessions/{call_sid}", cleanup_session, methods=["DELETE"])

# Export only the active routers
__all__ = ["http_twiml_router", "testing_router"]