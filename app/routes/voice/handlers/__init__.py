"""
Event handlers for the voice orchestration system.

This package contains handlers for different event types
from the OpenAI Realtime API, organized by functionality.
"""

from app.routes.voice.handlers.silence import handle_silence_event
from app.routes.voice.handlers.transcript import handle_transcript_event
from app.routes.voice.handlers.tools import handle_tool_call_event
from app.routes.voice.handlers.audio import handle_audio_event

# Export the handler functions
__all__ = [
    "handle_silence_event",
    "handle_transcript_event",
    "handle_tool_call_event",
    "handle_audio_event"
]