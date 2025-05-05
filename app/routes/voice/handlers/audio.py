"""
Handlers for audio events in the voice workflow.

This module contains functions for processing audio events
from the OpenAI Realtime API and sending them to the client.
"""

import logging
import json

# Set up logger
logger = logging.getLogger(__name__)

async def handle_audio_event(ws, session_id, event, metrics):
    """
    Handle an audio event from the Realtime API.
    
    Args:
        ws: The WebSocket connection
        session_id: Session identifier
        event: The audio event from the Realtime API
        metrics: Connection metrics dictionary
    """
    # Handle audio data for TTS response
    audio_data = event.get("data", "")
    if audio_data:
        logger.debug(f"[AUDIO:{session_id}] Received TTS audio data ({len(audio_data)} chars)")
        try:
            # Forward audio to Twilio
            await ws.send(json.dumps({
                "event": "media",
                "streamSid": session_id,
                "media": {
                    "payload": audio_data
                }
            }))
            metrics["events_sent"] += 1
        except Exception as audio_error:
            logger.error(f"[AUDIO:{session_id}] ❌ Error sending audio data: {audio_error}")
    else:
        logger.warning(f"[AUDIO:{session_id}] Received empty audio data")