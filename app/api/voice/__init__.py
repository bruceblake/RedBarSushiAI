"""
Voice API module for handling Twilio voice calls and WebSocket connections.

This package contains modules for handling voice interactions with Twilio,
including WebSocket connections for real-time audio streaming, and integration
with OpenAI's Realtime API for speech-to-text and text-to-speech.
"""

from fastapi import APIRouter

# Import the dedicated routers
from app.api.voice.handlers import router as media_stream_router
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

# Export the routers
__all__ = ["http_twiml_router", "media_stream_router", "testing_router"]