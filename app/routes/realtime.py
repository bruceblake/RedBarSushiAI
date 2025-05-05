"""
WebSocket routes for realtime audio processing with OpenAI Agents SDK.
This module provides the WebSocket endpoints for handling realtime audio streams.
"""

from flask import Blueprint, request, jsonify
import logging
import json
import time
import os
import traceback
import base64
import asyncio
from typing import Dict, List, Any, Optional, AsyncGenerator, Tuple, Union

from app import sock
from app.utils.realtime_audio_sdk import realtime_processor
from app.utils.conversation_store_sdk import agents_conversation_store

logger = logging.getLogger(__name__)

# Create blueprint
realtime_bp = Blueprint("realtime", __name__)

@sock.route("/ws/media")
async def handle_media(ws):
    """
    WebSocket endpoint for handling media streams from Twilio.
    
    Args:
        ws: The WebSocket connection
    """
    logger.info("WebSocket connection established for media")
    
    # Get the call SID from query parameters or headers
    call_sid = request.args.get("CallSid") or request.headers.get("X-Twilio-CallSid")
    
    if not call_sid:
        logger.error("No CallSid provided")
        await ws.send(json.dumps({"error": "No CallSid provided"}))
        return
    
    logger.info(f"Processing media for call {call_sid}")
    
    # Validate Twilio signature in production
    # For now, skip validation in development
    if os.environ.get("FLASK_ENV") == "production":
        # Placeholder for Twilio signature validation
        pass
    
    # Send initial message
    await ws.send(json.dumps({
        "type": "connected",
        "message": "Connected to realtime audio processor",
        "call_sid": call_sid
    }))
    
    # Define an async generator to receive media chunks
    async def receive_media():
        while True:
            try:
                data = await ws.receive()
                yield data
            except Exception as e:
                logger.error(f"Error receiving WebSocket message: {str(e)}")
                break
    
    # Process the media stream
    try:
        async for result in realtime_processor.process_media_stream(call_sid, receive_media()):
            # If result is a dict, convert to JSON string
            if isinstance(result, dict):
                await ws.send(json.dumps(result))
            # If result is binary data, send as is
            elif isinstance(result, bytes):
                await ws.send(result)
            else:
                # Convert other types to JSON string
                await ws.send(json.dumps({"type": "data", "content": str(result)}))
    except Exception as e:
        logger.error(f"Error processing media stream: {str(e)}")
        logger.error(traceback.format_exc())
        await ws.send(json.dumps({"type": "error", "message": str(e)}))

@sock.route("/ws/realtime")
async def handle_realtime(ws):
    """
    WebSocket endpoint for realtime AI conversation.
    
    Args:
        ws: The WebSocket connection
    """
    logger.info("WebSocket connection established for realtime AI")
    
    # Get the call SID from query parameters or headers
    call_sid = request.args.get("CallSid") or request.headers.get("X-Twilio-CallSid")
    
    if not call_sid:
        logger.error("No CallSid provided")
        await ws.send(json.dumps({"error": "No CallSid provided"}))
        return
    
    logger.info(f"Starting realtime AI for call {call_sid}")
    
    # Send initial message
    await ws.send(json.dumps({
        "type": "connected",
        "message": "Connected to realtime AI processor",
        "call_sid": call_sid
    }))
    
    # Define an async generator to receive audio chunks
    async def receive_audio():
        while True:
            try:
                data = await ws.receive()
                
                # Check if it's a control message
                if isinstance(data, str):
                    try:
                        control = json.loads(data)
                        if control.get("type") == "end":
                            logger.info(f"Received end message for call {call_sid}")
                            break
                    except json.JSONDecodeError:
                        pass
                
                yield data
            except Exception as e:
                logger.error(f"Error receiving WebSocket message: {str(e)}")
                break
    
    # Process the realtime session
    try:
        async for result in realtime_processor.process_realtime_session(call_sid, receive_audio()):
            await ws.send(json.dumps(result))
    except Exception as e:
        logger.error(f"Error processing realtime session: {str(e)}")
        logger.error(traceback.format_exc())
        await ws.send(json.dumps({"type": "error", "message": str(e)}))

@realtime_bp.route("/capabilities", methods=["GET"])
def get_capabilities():
    """
    Get the realtime capabilities of the system.
    
    Returns:
        JSON response with capabilities
    """
    # Determine what capabilities are available
    capabilities = {
        "websockets_available": True,
        "realtime_audio": True,
        "speech_to_text": True,
        "text_to_speech": True,
        "model": "gpt-4.1-mini",
        "supported_audio_formats": ["ulaw", "pcm"],
        "supported_sample_rates": [8000, 16000],
        "supported_voices": ["alloy", "nova", "shimmer", "echo", "fable", "onyx"],
        "endpoints": {
            "media": "/ws/media",
            "realtime": "/ws/realtime",
            "capabilities": "/realtime/capabilities"
        }
    }
    
    return jsonify(capabilities)

@realtime_bp.route("/healthcheck", methods=["GET"])
def healthcheck():
    """
    Health check endpoint for the realtime service.
    
    Returns:
        JSON response with health status
    """
    # Check if the OpenAI client is available
    openai_status = "ok" if realtime_processor.openai_client else "error"
    
    return jsonify({
        "status": "ok",
        "service": "realtime",
        "openai_status": openai_status,
        "websocket_available": True
    })