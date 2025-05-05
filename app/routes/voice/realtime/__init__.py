"""
Realtime audio processing module for RedBarSushiAI voice system.

This package contains components for integrating with OpenAI's Realtime API,
providing streaming audio processing, transcription, and TTS capabilities.
"""

from app.routes.voice.realtime.audio_generator import create_audio_generator
from app.routes.voice.realtime.stream_handler import handle_media_stream

# Export the public API
__all__ = [
    "create_audio_generator",
    "handle_media_stream"
]