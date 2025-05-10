"""
Voice API module for handling Twilio voice calls and WebSocket connections.

This package contains modules for handling voice interactions with Twilio,
including WebSocket connections for real-time audio streaming, and integration
with OpenAI's Realtime API for speech-to-text and text-to-speech.
"""

from fastapi import APIRouter

from app.api.voice.handlers import handle_media_stream
from app.api.voice.twiml import receive_call
from app.api.voice.testing import (
    process_voice_input, 
    execute_tool, 
    get_session_state, 
    trigger_fsm_event, 
    get_fsm_state, 
    cleanup_session
)

# Create the router
router = APIRouter(prefix="/voice", tags=["voice"])

# Register the TwiML generation route
router.add_api_route("/", receive_call, methods=["POST"])
router.add_api_route("/voice", receive_call, methods=["POST"])
router.add_api_route("/webhook/voice", receive_call, methods=["POST"])

# Register the WebSocket route
# This WebSocket route is mounted at /realtime prefix in app/api/__init__.py,
# resulting in the path /realtime/ws/media/{call_sid} which matches
# the WebSocket URL generated in the TwiML
router.add_websocket_route("/ws/media/{call_sid}", handle_media_stream)

# Register testing and debugging routes
router.add_api_route("/process", process_voice_input, methods=["POST"])
router.add_api_route("/tool", execute_tool, methods=["POST"])
router.add_api_route("/sessions/{call_sid}", get_session_state, methods=["GET"])
router.add_api_route("/fsm/{call_sid}/event", trigger_fsm_event, methods=["POST"])
router.add_api_route("/fsm/{call_sid}", get_fsm_state, methods=["GET"])
router.add_api_route("/sessions/{call_sid}", cleanup_session, methods=["DELETE"])

# Initialize on startup
@router.on_event("startup")
async def startup_event():
    """Initialize the voice routes on startup."""
    from app.utils.agent_orchestration_async import async_agent_orchestrator
    import logging
    
    logger = logging.getLogger(__name__)
    await async_agent_orchestrator.initialize()
    logger.info("Voice routes initialized")