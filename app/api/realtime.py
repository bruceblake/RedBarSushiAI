"""
FastAPI WebSocket endpoints for real-time audio processing.

This module provides WebSocket endpoints for handling Twilio Media Streams
and integrating with OpenAI's Realtime API for voice interactions.
"""

import logging
import json
import time
import base64
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List, Set, Tuple, Union

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from app.dependencies import connection_manager, get_connection_manager, ConnectionManager
from app.models.api import (
    WebSocketMessage, TwilioConnectedEvent, TwilioStartEvent, 
    TwilioMediaEvent, TwilioStopEvent, WelcomeResponse
)
from app.config import settings

# Set up logging
logger = logging.getLogger(__name__)

# Create a formatter that includes milliseconds in the timestamp
def get_timestamp_str():
    """Get current timestamp with millisecond precision as a string"""
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

# Helper for structured logging of events
def log_ws_event(call_sid, direction, event_type, data=None, duration_ms=None, level="debug"):
    """
    Log a WebSocket event with structured format.
    
    Args:
        call_sid: The Twilio call SID
        direction: 'SEND' or 'RECV'
        event_type: Type of event
        data: Optional event data (will be sanitized for logging)
        duration_ms: Optional duration in milliseconds
        level: Log level to use
    """
    timestamp = get_timestamp_str()
    
    # Create structured log entry
    log_entry = {
        "event": "WEBSOCKET_EVENT",
        "call_sid": call_sid,
        "timestamp": timestamp,
        "direction": direction,
        "event_type": event_type
    }
    
    if duration_ms is not None:
        log_entry["duration_ms"] = round(duration_ms, 2)
    
    # Sanitize data if provided
    if data is not None:
        # For audio data, just log the length, not the content
        if isinstance(data, dict):
            sanitized_data = data.copy()
            # Handle media payload
            if 'media' in sanitized_data and 'payload' in sanitized_data['media']:
                payload_len = len(sanitized_data['media']['payload'])
                sanitized_data['media']['payload'] = f"<{payload_len} bytes>"
            # Handle audio payload
            if 'audio' in sanitized_data:
                if isinstance(sanitized_data['audio'], str):
                    audio_len = len(sanitized_data['audio'])
                    sanitized_data['audio'] = f"<{audio_len} bytes>"
                elif isinstance(sanitized_data['audio'], dict) and 'delta' in sanitized_data['audio']:
                    delta_len = len(sanitized_data['audio']['delta'])
                    sanitized_data['audio']['delta'] = f"<{delta_len} bytes>"
            log_entry["data"] = sanitized_data
        else:
            # For string data, truncate if too long
            if isinstance(data, str) and len(data) > 200:
                log_entry["data"] = data[:200] + "... [truncated]"
            else:
                log_entry["data"] = data
    
    # Log with the appropriate level
    log_method = getattr(logger, level, logger.debug)
    
    # Format as JSON string for structured logging
    structured_log = f"STRUCTURED_LOG: {json.dumps(log_entry)}"
    
    # Also log in human-readable format
    formatted_msg = f"[{call_sid}] {direction} {event_type}"
    if duration_ms is not None:
        formatted_msg += f" (took {duration_ms:.2f}ms)"
    
    log_method(structured_log)
    log_method(formatted_msg)

# Create router
router = APIRouter(prefix="/ws", tags=["WebSockets"])

# The main WebSocket endpoint for handling Twilio Media Streams
@router.websocket("/media/{call_sid}")
async def handle_media_realtime(
    websocket: WebSocket, 
    call_sid: str,
    connection_mgr: ConnectionManager = Depends(get_connection_manager)
):
    """
    WebSocket endpoint for handling media streams from Twilio.
    
    This function handles bidirectional audio streaming between
    Twilio's Media Streams and OpenAI's Realtime API. It receives audio from Twilio,
    forwards it to OpenAI, and returns synthesized responses back to Twilio.
    
    Args:
        websocket: The WebSocket connection from Twilio
        call_sid: Call SID passed in URL path
        connection_mgr: The WebSocket connection manager dependency
    """
    # Log connection with timestamp
    start_time = time.time()
    timestamp = get_timestamp_str()
    logger.critical(f"[{call_sid}] WebSocket connection established at {timestamp} (FastAPI Handler)")
    
    # Log structured connection event
    log_entry = {
        "event": "CONNECTION_ESTABLISHED",
        "call_sid": call_sid,
        "timestamp": timestamp,
        "handler_type": "fastapi"
    }
    logger.critical(f"STRUCTURED_LOG: {json.dumps(log_entry)}")
    
    # Initialize variables
    stream_sid = None  # Will be set after receiving 'start' event
    openai_session = None  # Will be set up after successful start
    
    try:
        # 1. Accept the WebSocket connection from Twilio
        await connection_mgr.connect(websocket, call_sid)
        
        # 2. Wait for Twilio 'connected' and 'start' events
        # Handle 'connected' event
        message_str = await websocket.receive_text()
        log_ws_event(call_sid, "RECV", "twilio_initial", message_str)
        
        try:
            message = json.loads(message_str)
            event_type = message.get("event")
            
            if event_type != "connected":
                logger.warning(f"[{call_sid}] Expected 'connected' event, got: {event_type}")
                return
                
            logger.info(f"[{call_sid}] Received 'connected' event from Twilio")
        except json.JSONDecodeError:
            logger.error(f"[{call_sid}] Failed to decode 'connected' event JSON: {message_str}")
            return
            
        # Handle 'start' event
        message_str = await websocket.receive_text()
        log_ws_event(call_sid, "RECV", "twilio_start", message_str)
        
        try:
            message = json.loads(message_str)
            event_type = message.get("event")
            
            if event_type != "start":
                logger.warning(f"[{call_sid}] Expected 'start' event, got: {event_type}")
                return
                
            # Extract stream SID from start event
            start_data = message.get("start", {})
            stream_sid = start_data.get("streamSid")
            
            if not stream_sid:
                logger.error(f"[{call_sid}] 'start' event missing streamSid")
                return
                
            logger.info(f"[{call_sid}] Twilio media stream started. Stream SID: {stream_sid}")
        except json.JSONDecodeError:
            logger.error(f"[{call_sid}] Failed to decode 'start' event JSON: {message_str}")
            return
            
        # 3. Send welcome message to confirm connection
        welcome_msg = WelcomeResponse(
            call_sid=call_sid,
            stream_sid=stream_sid
        )
        welcome_str = welcome_msg.model_dump_json()
        
        await websocket.send_text(welcome_str)
        logger.info(f"[{call_sid}] Sent welcome message")
        log_ws_event(call_sid, "SEND", "twilio_welcome", welcome_msg.model_dump())
        
        # 4. Initialize the OpenAI Realtime session
        # This would be implemented in the OpenAI Realtime connection function
        # async def connect_to_openai_realtime(call_sid: str, stream_sid: str)
        
        # 5. Begin processing the WebSocket messages
        await process_media_stream(websocket, call_sid, stream_sid)
        
    except WebSocketDisconnect:
        logger.warning(f"[{call_sid}] WebSocket disconnected by client")
    except Exception as e:
        logger.error(f"[{call_sid}] Error in WebSocket handler: {e}", exc_info=True)
    finally:
        # Clean up any resources
        connection_mgr.disconnect(call_sid)
        logger.info(f"[{call_sid}] WebSocket connection closed")

async def process_media_stream(websocket: WebSocket, call_sid: str, stream_sid: str):
    """
    Process the media stream from Twilio.
    
    This function handles the main event loop for processing audio streams between
    Twilio and OpenAI's Realtime API. It creates multiple tasks for:
    - Processing audio from Twilio -> OpenAI
    - Processing responses from OpenAI -> Twilio
    - Handling heartbeats to keep the connection alive
    
    Args:
        websocket: The WebSocket connection from Twilio
        call_sid: The Twilio call SID
        stream_sid: The Twilio stream SID
    """
    logger.info(f"[{call_sid}] Starting media stream processing")
    
    # Import the async OpenAI Realtime client
    from app.utils.realtime_audio_async import realtime_client
    
    # Set up queues for communicating between tasks
    twilio_to_openai_queue = asyncio.Queue()  # For audio from Twilio to OpenAI
    openai_to_twilio_queue = asyncio.Queue()  # For audio from OpenAI to Twilio
    
    # For tracking if processing should continue
    should_continue = {"value": True}
    
    # Task functions
    
    async def handle_twilio_to_openai():
        """Task to receive audio from Twilio and forward to OpenAI."""
        try:
            logger.info(f"[{call_sid}] Starting Twilio -> OpenAI audio forwarding task")
            media_packet_count = 0
            
            while should_continue["value"]:
                try:
                    # Get audio data from the queue
                    audio_data = await twilio_to_openai_queue.get()
                    
                    # Send to OpenAI
                    await realtime_client.send_audio(audio_data)
                    
                    # Track packet count
                    media_packet_count += 1
                    
                    # Log periodically
                    if media_packet_count % 500 == 0:
                        logger.debug(f"[{call_sid}] Forwarded {media_packet_count} audio packets to OpenAI")
                        
                    # Small yield to prevent blocking
                    await asyncio.sleep(0.001)
                    
                except asyncio.CancelledError:
                    logger.info(f"[{call_sid}] Twilio -> OpenAI task cancelled")
                    break
                except Exception as e:
                    logger.error(f"[{call_sid}] Error in Twilio -> OpenAI task: {e}")
                    await asyncio.sleep(0.1)  # Brief pause on error
                
        except Exception as e:
            logger.error(f"[{call_sid}] Fatal error in Twilio -> OpenAI task: {e}", exc_info=True)
        finally:
            logger.info(f"[{call_sid}] Twilio -> OpenAI task ended")
    
    async def handle_openai_to_twilio():
        """Task to send audio from OpenAI to Twilio."""
        try:
            logger.info(f"[{call_sid}] Starting OpenAI -> Twilio audio forwarding task")
            audio_packet_count = 0
            
            while should_continue["value"]:
                try:
                    # Get audio data from the queue
                    audio_data = await openai_to_twilio_queue.get()
                    
                    # Encode audio as base64 for Twilio
                    audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                    
                    # Create media message
                    media_message = {
                        "event": "media",
                        "streamSid": stream_sid,
                        "media": {
                            "payload": audio_base64
                        }
                    }
                    
                    # Send to Twilio
                    await websocket.send_json(media_message)
                    
                    # Track packet count
                    audio_packet_count += 1
                    
                    # Log periodically
                    if audio_packet_count % 100 == 0:
                        logger.debug(f"[{call_sid}] Sent {audio_packet_count} audio packets to Twilio")
                        
                    # Small yield to prevent blocking
                    await asyncio.sleep(0.001)
                    
                except asyncio.CancelledError:
                    logger.info(f"[{call_sid}] OpenAI -> Twilio task cancelled")
                    break
                except Exception as e:
                    logger.error(f"[{call_sid}] Error in OpenAI -> Twilio task: {e}")
                    await asyncio.sleep(0.1)  # Brief pause on error
                
        except Exception as e:
            logger.error(f"[{call_sid}] Fatal error in OpenAI -> Twilio task: {e}", exc_info=True)
        finally:
            logger.info(f"[{call_sid}] OpenAI -> Twilio task ended")
    
    async def send_heartbeats():
        """Task to send heartbeat messages to keep the connection alive."""
        try:
            logger.info(f"[{call_sid}] Starting heartbeat task")
            heartbeat_count = 0
            
            while should_continue["value"]:
                try:
                    # Send heartbeat every 5 seconds
                    await asyncio.sleep(5)
                    
                    # Create heartbeat message
                    heartbeat_message = {
                        "event": "heartbeat",
                        "streamSid": stream_sid
                    }
                    
                    # Send to Twilio
                    await websocket.send_json(heartbeat_message)
                    
                    # Track heartbeat count
                    heartbeat_count += 1
                    
                    # Log periodically
                    if heartbeat_count % 12 == 0:  # Log every ~60 seconds
                        logger.debug(f"[{call_sid}] Sent {heartbeat_count} heartbeats")
                        
                except asyncio.CancelledError:
                    logger.info(f"[{call_sid}] Heartbeat task cancelled")
                    break
                except Exception as e:
                    logger.error(f"[{call_sid}] Error in heartbeat task: {e}")
                    await asyncio.sleep(1)  # Longer pause on error
                
        except Exception as e:
            logger.error(f"[{call_sid}] Fatal error in heartbeat task: {e}", exc_info=True)
        finally:
            logger.info(f"[{call_sid}] Heartbeat task ended")
    
    async def handle_openai_events():
        """Task to process events from OpenAI."""
        try:
            logger.info(f"[{call_sid}] Starting OpenAI event processing task")
            
            # Define handler functions for OpenAI events
            
            async def handle_transcript(text, is_final):
                """Handle transcript events from OpenAI."""
                logger.info(f"[{call_sid}] {'Final' if is_final else 'Partial'} transcript: {text}")
                
                # In a complete implementation, we would process the transcript
                # with the agent system here and generate responses
                if is_final and text:
                    # For now, just echo back what the user said
                    response_text = f"I heard you say: {text}"
                    logger.info(f"[{call_sid}] Synthesizing response: {response_text}")
                    
                    # Use OpenAI to synthesize speech
                    await realtime_client.send_text_input(response_text)
                    await realtime_client.request_response("text_and_audio")
            
            async def handle_audio(audio_data):
                """Handle audio events from OpenAI."""
                # Add to the queue for sending to Twilio
                await openai_to_twilio_queue.put(audio_data)
            
            async def handle_tool_call(tool_call):
                """Handle tool call events from OpenAI."""
                logger.info(f"[{call_sid}] Tool call: {tool_call}")
                
                # In a complete implementation, we would handle tools here
                # For now, just return a dummy result
                tool_id = tool_call.get("id")
                function = tool_call.get("function", {})
                function_name = function.get("name", "unknown")
                
                # Return dummy result
                result = {"status": "success", "message": f"Executed {function_name}"}
                await realtime_client.send_function_result(tool_id, result)
                
                # Request a new response after the tool call
                await realtime_client.request_response("text_and_audio")
            
            # Start the OpenAI client's listen loop
            await realtime_client.listen(
                transcript_handler=handle_transcript,
                audio_handler=handle_audio,
                tool_call_handler=handle_tool_call
            )
            
        except Exception as e:
            logger.error(f"[{call_sid}] Fatal error in OpenAI event processing task: {e}", exc_info=True)
        finally:
            logger.info(f"[{call_sid}] OpenAI event processing task ended")
            # When this task ends, signal other tasks to stop
            should_continue["value"] = False
    
    # Try to connect to OpenAI Realtime API
    try:
        # Connect to OpenAI
        connected = await realtime_client.connect()
        if not connected:
            logger.error(f"[{call_sid}] Failed to connect to OpenAI Realtime API")
            return
            
        # Configure the session
        configured = await realtime_client.configure_session()
        if not configured:
            logger.error(f"[{call_sid}] Failed to configure OpenAI Realtime session")
            await realtime_client.disconnect()
            return
            
        # Start tasks
        tasks = [
            asyncio.create_task(handle_twilio_to_openai()),
            asyncio.create_task(handle_openai_to_twilio()),
            asyncio.create_task(send_heartbeats()),
            asyncio.create_task(handle_openai_events())
        ]
        
        # Send welcome message through TTS
        welcome_text = "Welcome to Red Bar Sushi. How can I help you today?"
        logger.info(f"[{call_sid}] Sending welcome message: {welcome_text}")
        await realtime_client.send_text_input(welcome_text)
        await realtime_client.request_response("text_and_audio")
        
        # Main event loop - process messages from Twilio
        try:
            while should_continue["value"]:
                # Receive message from Twilio
                message_str = await websocket.receive_text()
                
                try:
                    message = json.loads(message_str)
                    event_type = message.get("event")
                    
                    if event_type == "media":
                        # This is an audio packet, extract and queue it
                        media_data = message.get("media", {})
                        track = media_data.get("track")
                        chunk = media_data.get("chunk")
                        payload = media_data.get("payload")
                        
                        # Only process inbound audio
                        if track == "inbound":
                            # Decode base64 audio data
                            audio_data = base64.b64decode(payload)
                            
                            # Add to the queue for processing
                            await twilio_to_openai_queue.put(audio_data)
                            
                    elif event_type == "stop":
                        # Stream stopped, exit loop
                        logger.info(f"[{call_sid}] Received 'stop' event from Twilio")
                        break
                        
                    else:
                        # Unknown event type
                        logger.debug(f"[{call_sid}] Received event type: {event_type}")
                        
                except json.JSONDecodeError:
                    logger.error(f"[{call_sid}] Failed to decode message JSON: {message_str}")
                    
                # Small yield to prevent blocking
                await asyncio.sleep(0.001)
                
        except WebSocketDisconnect:
            logger.warning(f"[{call_sid}] WebSocket disconnected by client")
        except Exception as e:
            logger.error(f"[{call_sid}] Error in main event loop: {e}", exc_info=True)
        finally:
            # Signal tasks to stop
            should_continue["value"] = False
            
            # Cancel all tasks
            for task in tasks:
                task.cancel()
                
            # Wait for tasks to complete
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Disconnect from OpenAI
            await realtime_client.disconnect()
            
    except Exception as e:
        logger.error(f"[{call_sid}] Error setting up media stream processing: {e}", exc_info=True)

# Route for checking realtime service status
@router.get("/health")
async def realtime_health():
    """Health check endpoint for the realtime service."""
    return {
        "status": "ok",
        "service": "realtime",
        "timestamp": datetime.now().isoformat(),
        "connections": len(connection_manager.active_connections)
    }