"""
WebSocket handler for Twilio Media Streams.

This module handles real-time audio streaming between Twilio and OpenAI.
"""

import os
import json
import base64
import logging
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect, Query
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)

# WebSocket handler for media streams
async def handle_media_stream(
    websocket: WebSocket,
    call_sid: str,
    debug: bool = Query(False),
    client: str = Query("twilio"),
    time: str = Query("")
):
    """
    Handle WebSocket connection for Twilio Media Streams.
    
    Args:
        websocket: FastAPI WebSocket instance
        call_sid: Twilio call SID
        debug: Enable debug logging
        client: Client type (twilio)
        time: Timestamp from TwiML
    """
    logger.info(f"WebSocket connection attempt for call {call_sid}")
    logger.info(f"Debug: {debug}, Client: {client}, Time: {time}")
    logger.info(f"Headers: {dict(websocket.headers)}")
    
    try:
        # Accept the WebSocket connection
        await websocket.accept()
        logger.info(f"WebSocket connection accepted for call {call_sid}")
        
        # Initialize OpenAI connection and handlers
        openai_ws = None
        tasks = []
        
        try:
            # Import the voice handler based on configuration
            voice_handler = os.environ.get("VOICE_HANDLER", "media_streams")
            
            if voice_handler == "conversation_relay":
                # Use ConversationRelay handler
                from app.api.conversation_relay.handler import handle_conversation_relay
                logger.info(f"Using ConversationRelay handler for call {call_sid}")
                await handle_conversation_relay(websocket, call_sid)
            else:
                # Use media streams handler (OpenAI Realtime)
                logger.info(f"Using Media Streams handler for call {call_sid}")
                
                # For now, just handle the basic Twilio protocol
                # Full OpenAI integration would go here
                await handle_twilio_media_stream(websocket, call_sid)
                
        except Exception as e:
            logger.error(f"Error in WebSocket handler: {e}", exc_info=True)
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for call {call_sid}")
    except Exception as e:
        logger.error(f"WebSocket error for call {call_sid}: {e}", exc_info=True)
    finally:
        # Clean up
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()
        logger.info(f"WebSocket handler completed for call {call_sid}")


async def handle_twilio_media_stream(websocket: WebSocket, call_sid: str):
    """
    Handle basic Twilio Media Stream protocol.
    
    This is a simplified handler that accepts Twilio messages
    and responds appropriately to keep the connection alive.
    """
    try:
        while True:
            # Receive message from Twilio
            message = await websocket.receive_text()
            data = json.loads(message)
            
            event_type = data.get("event")
            
            if event_type == "connected":
                logger.info(f"Twilio connected for call {call_sid}")
                logger.info(f"Protocol: {data.get('protocol')}")
                logger.info(f"Version: {data.get('version')}")
                
            elif event_type == "start":
                logger.info(f"Media stream started for call {call_sid}")
                logger.info(f"Stream SID: {data.get('streamSid')}")
                logger.info(f"Account SID: {data.get('accountSid')}")
                logger.info(f"Custom parameters: {data.get('customParameters', {})}")
                
                # Send a simple acknowledgment
                await websocket.send_json({
                    "event": "connected",
                    "protocol": "Call",
                    "version": "1.0.0"
                })
                
            elif event_type == "media":
                # Audio data from Twilio
                payload = data.get("media", {})
                audio_data = payload.get("payload")
                
                if debug:
                    logger.debug(f"Received audio chunk: {len(audio_data) if audio_data else 0} bytes")
                
                # In a full implementation, forward this to OpenAI
                
            elif event_type == "stop":
                logger.info(f"Media stream stopped for call {call_sid}")
                break
                
    except WebSocketDisconnect:
        logger.info(f"Twilio disconnected for call {call_sid}")
    except Exception as e:
        logger.error(f"Error handling Twilio stream: {e}", exc_info=True)


# Export the handler
__all__ = ["handle_media_stream"]