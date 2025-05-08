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
import uuid  # Added for session ID generation
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
    
    This is a bidirectional proxy between Twilio's Media Streams and OpenAI's Realtime API.
    It forwards audio from Twilio to OpenAI and sends synthesized responses back to Twilio.
    
    Args:
        ws: The WebSocket connection from Twilio
    """
    import websockets
    from app.utils.realtime_audio_sdk import get_openai_key
    import asyncio
    import base64
    
    # Log connection
    logger.critical(f"⚡⚡⚡ CRITICAL: WebSocket connection established from Twilio at {time.time()} ⚡⚡⚡")
    
    # Get the call SID from query parameters
    call_sid = request.args.get("CallSid")
    if not call_sid:
        logger.error("No CallSid provided in WebSocket connection")
        return
    
    logger.critical(f"Processing media stream for call {call_sid}")
    
    # Get OpenAI API key
    openai_api_key = get_openai_key()
    if not openai_api_key:
        logger.error("No OpenAI API key available")
        return
    
    # Track Twilio stream SID
    stream_sid = None
    
    try:
        # Connect to OpenAI Realtime API
        logger.info(f"Connecting to OpenAI Realtime API for call {call_sid}")
        openai_ws_url = 'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01'
        
        # Configure for voice interaction
        session_config = {
            "type": "session.update",
            "speech_recognition": {
                "enabled": True
            },
            "text_to_speech": {
                "enabled": True,
                "voice": "shimmer"
            }
        }
        
        # Send a welcome message to Twilio to confirm connection
        await ws.send(json.dumps({
            "type": "connected",
            "message": "Connected to RedBarSushi AI",
            "call_sid": call_sid,
            "timestamp": time.time()
        }))
        
        async with websockets.connect(
            openai_ws_url,
            extra_headers={
                "Authorization": f"Bearer {openai_api_key}",
                "OpenAI-Beta": "realtime=v1"
            }
        ) as openai_ws:
            # Configure the OpenAI session
            await openai_ws.send(json.dumps(session_config))
            logger.info(f"Connected to OpenAI and sent session config for call {call_sid}")
            
            # Set up concurrent tasks for bidirectional communication
            async def receive_from_twilio():
                """Receive audio data from Twilio and send it to OpenAI."""
                nonlocal stream_sid
                try:
                    async for message in ws:
                        if isinstance(message, str):
                            data = json.loads(message)
                            event_type = data.get('event')
                            
                            # Handle start event
                            if event_type == 'start':
                                stream_sid = data.get('streamSid')
                                logger.info(f"Twilio stream started: SID={stream_sid}")
                                
                            # Forward audio to OpenAI
                            elif event_type == 'media' and 'media' in data and 'payload' in data['media']:
                                audio_payload = data['media']['payload']
                                audio_append = {
                                    "type": "input_audio_buffer.append",
                                    "audio": audio_payload  # Already base64 encoded from Twilio
                                }
                                await openai_ws.send(json.dumps(audio_append))
                                
                            # Handle stop event
                            elif event_type == 'stop':
                                logger.info(f"Twilio stream stopped: SID={stream_sid}")
                                return
                except Exception as e:
                    logger.error(f"Error receiving from Twilio: {str(e)}")
                    logger.error(traceback.format_exc())
            
            async def send_to_twilio():
                """Receive events from OpenAI and send audio back to Twilio."""
                nonlocal stream_sid
                try:
                    async for openai_message in openai_ws:
                        response = json.loads(openai_message)
                        event_type = response.get('type')
                        
                        # Log non-audio events at debug level
                        if event_type != 'response.audio.delta':
                            logger.debug(f"OpenAI event: {event_type}")
                        
                        # Handle audio from OpenAI to send back to Twilio
                        if event_type == 'response.audio.delta' and response.get('delta'):
                            try:
                                # OpenAI audio needs to be formatted for Twilio
                                audio_payload = response['delta']
                                
                                # Send to Twilio in the expected format
                                audio_message = {
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {
                                        "payload": audio_payload
                                    }
                                }
                                await ws.send(json.dumps(audio_message))
                            except Exception as audio_error:
                                logger.error(f"Error sending audio to Twilio: {str(audio_error)}")
                except Exception as e:
                    logger.error(f"Error in OpenAI communication: {str(e)}")
                    logger.error(traceback.format_exc())
            
            # Create a simple heartbeat task
            async def send_heartbeats():
                """Send periodic heartbeats to keep the connection alive."""
                count = 0
                try:
                    while True:
                        await asyncio.sleep(10)  # Every 10 seconds
                        count += 1
                        try:
                            heartbeat = {
                                "type": "heartbeat",
                                "count": count,
                                "timestamp": time.time()
                            }
                            await ws.send(json.dumps(heartbeat))
                            logger.debug(f"Sent heartbeat #{count}")
                        except Exception:
                            break
                except asyncio.CancelledError:
                    pass
            
            # Start all tasks concurrently
            heartbeat_task = asyncio.create_task(send_heartbeats())
            try:
                # Run both communication channels concurrently until one completes
                await asyncio.gather(
                    receive_from_twilio(),
                    send_to_twilio()
                )
            finally:
                # Clean up
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
                logger.info(f"WebSocket session ended for call {call_sid}")
    
    except Exception as e:
        logger.error(f"Error in WebSocket handler: {str(e)}")
        logger.error(traceback.format_exc())

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
