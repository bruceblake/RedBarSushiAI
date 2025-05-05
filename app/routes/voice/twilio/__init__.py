"""
Twilio integration for RedBarSushiAI voice system.

This package provides integration with Twilio's Programmable Voice
and Media Streams APIs for real-time voice processing.
"""

from app.routes.voice.twilio.twiml import (
    generate_media_streams_twiml,
    get_environment_name,
    get_host_for_ws
)

# Export the public API
__all__ = [
    "generate_media_streams_twiml",
    "get_environment_name",
    "get_host_for_ws"
]