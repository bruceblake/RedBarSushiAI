"""
WebSocket handlers for Twilio media streams.

This module contains the main WebSocket handler for processing Twilio media streams,
including accepting connections, managing the session, and handling various events.
"""

import json
import logging
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
import base64
import traceback
import asyncio
import os
import sys
from typing import Dict, List, Any, Optional, Union

from app.utils.agent_orchestration_async import async_agent_orchestrator
from app.utils.fsm_async import async_fsm_manager, ConversationState, ConversationEvent
from app.dependencies import get_connection_manager, ConnectionManager
from app.config import settings

# Set up logging
logger = logging.getLogger(__name__)
# Force DEBUG level for this module specifically
logger.setLevel(logging.DEBUG)

# Add a console handler for immediate visibility
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Ensure our logs are seen even if parent loggers have higher levels
logger.propagate = False

# Create a dedicated router for WebSocket endpoints only
router = APIRouter(tags=["Voice Media Streams"])

# Initialize on startup
@router.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    await async_agent_orchestrator.initialize()
    logger.info("Voice media stream handlers initialized")

@router.websocket("/ws/media/{call_sid}")
async def handle_media_stream(
    websocket: WebSocket, 
    call_sid: str,
    connection_mgr: ConnectionManager = Depends(get_connection_manager)
):
    # CRITICAL: This must be the very first log in the function, before any other code
    logger.critical(f"❗❗❗ WEBSOCKET CONNECTION RECEIVED BY HANDLER: {call_sid} ❗❗❗")
    logger.critical(f"❗❗❗ HANDLER ROUTE: /realtime/ws/media/{call_sid} ❗❗❗")
    """
    WebSocket endpoint for handling Twilio media streams.
    
    This endpoint receives and processes real-time audio from Twilio,
    and returns AI-generated responses in real-time. Uses the FSM for conversation state management.
    
    Args:
        websocket: The WebSocket connection
        call_sid: The Twilio call SID
        connection_mgr: The WebSocket connection manager
    """
    # CRITICAL: This must be the very first log in the function, before any other code
    logger.critical(f"❗❗❗ WEBSOCKET CONNECTION ATTEMPTED: {call_sid} ❗❗❗")
    # Local references to track active tasks and resources
    openai_task = None
    transcript_queue = asyncio.Queue()
    event_queue = asyncio.Queue()
    tasks = []
    
    # Set up the WebSocket connection
    logger.critical(f"🔄 [{call_sid}] ATTEMPTING to accept WebSocket connection...")
    print(f"\n!!! DEBUG: [{call_sid}] About to accept WebSocket connection", flush=True)
    
    try:
        # First, accept the WebSocket connection
        logger.critical(f"🔄 [{call_sid}] Calling websocket.accept()...")
        await websocket.accept()
        logger.critical(f"🟢 [{call_sid}] WebSocket acceptance successful")
        print(f"\n!!! DEBUG: [{call_sid}] WebSocket.accept() successful", flush=True)
        
        # Then register with connection manager
        await connection_mgr.connect(websocket, call_sid)
        logger.critical(f"🟢 [{call_sid}] WebSocket connection fully established and registered")
        print(f"\n!!! DEBUG: [{call_sid}] WebSocket connection fully established", flush=True)
    except Exception as e:
        logger.critical(f"🔴 [{call_sid}] FAILED to accept WebSocket connection: {str(e)}")
        logger.critical(f"🔴 [{call_sid}] Error type: {type(e).__name__}")
        logger.critical(traceback.format_exc())
        print(f"\n!!! DEBUG: [{call_sid}] FAILED to accept WebSocket: {str(e)}", flush=True)
        print(f"\n!!! DEBUG: {traceback.format_exc()}", flush=True)
        raise
    
    try:
        # Process messages from the WebSocket
        async for message in websocket.iter_json():
            event = message.get("event")
            
            if event == "connected":
                # Handle connected event
                logger.info(f"[{call_sid}] Received connected event")
                await connection_mgr.update_call_data(call_sid, {"connected_at": time.time()})
                
            elif event == "start":
                # Handle start event - this is where we start processing
                logger.info(f"[{call_sid}] Received start event, stream SID: {message.get('streamSid')}")
                await connection_mgr.update_call_data(call_sid, {
                    "stream_sid": message.get("streamSid"),
                    "started_at": time.time()
                })
                
                # Start a new conversation with the FSM
                greeting_response = await async_agent_orchestrator.start_new_conversation(
                    call_sid,
                    {"first_interaction": True}
                )
                
                # Extract the greeting text
                greeting_text = greeting_response.get("text", "Welcome to Red Bar Sushi. How can I assist you today?")
                
                # Create client and processor for OpenAI
                from app.api.voice.realtime import (
                    create_openai_client, 
                    process_transcripts, 
                    process_events
                )
                
                # Initialize the OpenAI Realtime client with the configuration
                openai_client = await create_openai_client(call_sid, websocket, transcript_queue, event_queue)
                
                # Connect to OpenAI Realtime API
                logger.critical(f"🔄 [{call_sid}] ATTEMPTING to connect to OpenAI Realtime API...")
                print(f"\n!!! DEBUG: [{call_sid}] ATTEMPTING to connect to OpenAI Realtime API...", flush=True)
                try:
                    print(f"\n!!! DEBUG: [{call_sid}] About to call openai_client.connect()", flush=True)
                    connection_result = await openai_client.connect()
                    print(f"\n!!! DEBUG: [{call_sid}] openai_client.connect() returned: {connection_result}", flush=True)
                    
                    if connection_result:
                        logger.critical(f"🟢 [{call_sid}] SUCCESSFULLY connected to OpenAI Realtime API")
                        print(f"\n!!! DEBUG: [{call_sid}] CONNECTION SUCCESS", flush=True)
                    else:
                        logger.critical(f"🔴 [{call_sid}] FAILED to connect to OpenAI Realtime API")
                        print(f"\n!!! DEBUG: [{call_sid}] CONNECTION FAILED - THIS TRIGGERS 'couldn't connect' message", flush=True)
                        # This is where the "couldn't connect" message originates - triggered when connection_result is False
                        logger.critical(f"🔴 [{call_sid}] ABOUT TO SEND 'couldn't connect' message to client")
                        await websocket.send_text(json.dumps({
                            "event": "ai_error", 
                            "message": "Failed to connect to OpenAI speech services."
                        }))
                        logger.critical(f"🔴 [{call_sid}] SENT 'couldn't connect' message to client")
                except Exception as e:
                    logger.critical(f"🔴 [{call_sid}] EXCEPTION during OpenAI connection attempt: {str(e)}")
                    logger.critical(f"🔴 [{call_sid}] Exception type: {type(e).__name__}")
                    logger.critical(traceback.format_exc())
                    print(f"\n!!! DEBUG: [{call_sid}] EXCEPTION during connection: {str(e)}", flush=True)
                    print(f"\n!!! DEBUG: [{call_sid}] Exception type: {type(e).__name__}", flush=True)
                    print(f"\n!!! DEBUG: {traceback.format_exc()}", flush=True)
                    raise
                
                # Start the OpenAI WebSocket processing task
                logger.critical(f"🔄 [{call_sid}] Starting OpenAI message processing task...")
                openai_task = asyncio.create_task(openai_client.process_messages())
                
                # Start the transcript and event processing tasks
                transcript_task = asyncio.create_task(
                    process_transcripts(call_sid, transcript_queue, openai_client)
                )
                event_task = asyncio.create_task(
                    process_events(call_sid, event_queue, openai_client)
                )
                
                # Add tasks to the task list for cleanup
                tasks.extend([openai_task, transcript_task, event_task])
                
                # Send the greeting to OpenAI for TTS
                logger.critical(f"🔄 [{call_sid}] Sending greeting for TTS: \"{greeting_text}\"")
                try:
                    await openai_client.request_response(greeting_text)
                    logger.critical(f"🟢 [{call_sid}] Successfully sent greeting for TTS")
                except Exception as e:
                    logger.critical(f"🔴 [{call_sid}] FAILED to send greeting for TTS: {str(e)}")
                    logger.critical(traceback.format_exc())
            
            elif event == "media":
                # Handle media event with audio data
                media = message.get("media", {})
                payload = media.get("payload", "")
                
                # Forward the audio data to OpenAI Realtime API if connected
                if payload and openai_task and not openai_task.done():
                    # Send audio data to the OpenAI client
                    from app.api.voice.audio import forward_audio_to_openai
                    await forward_audio_to_openai(call_sid, payload, openai_task)
            
            elif event == "stop":
                # Handle stop event
                logger.info(f"[{call_sid}] Received stop event")
                await connection_mgr.update_call_data(call_sid, {"stopped_at": time.time()})
                
                # Cancel all tasks
                for task in tasks:
                    if task and not task.done():
                        task.cancel()
                
                # Disconnect
                await connection_mgr.disconnect(call_sid)
                break
            
            else:
                # Handle unknown event
                logger.warning(f"[{call_sid}] Received unknown event: {event}")
    
    except WebSocketDisconnect:
        logger.info(f"[{call_sid}] WebSocket disconnected")
    
    except Exception as e:
        logger.error(f"[{call_sid}] Error in WebSocket handler: {str(e)}")
        logger.error(traceback.format_exc())
    
    finally:
        # Clean up all tasks
        for task in tasks:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"[{call_sid}] Error cancelling task: {e}")
        
        # Disconnect the WebSocket
        try:
            await connection_mgr.disconnect(call_sid)
        except Exception as close_error:
            logger.error(f"[{call_sid}] Error closing WebSocket connection: {str(close_error)}")