"""
Enhanced WebSocket stream handler for voice processing.

This module provides an improved handler for WebSocket connections from Twilio Media Streams
with extensive debugging and connection maintenance features.
"""

import asyncio
import json
import logging
import time
import traceback
import uuid
from datetime import datetime

# Set up logger
logger = logging.getLogger(__name__)

# Global tracking for all active WebSocket connections
active_connections = {}

# Global task registry to prevent garbage collection
if not hasattr(asyncio, '_keepalive_tasks'):
    asyncio._keepalive_tasks = set()

def add_task_to_registry(task):
    """Add a task to the registry to prevent garbage collection."""
    asyncio._keepalive_tasks.add(task)
    
    # Set up callback to remove task when done
    def cleanup_task(task):
        try:
            asyncio._keepalive_tasks.discard(task)
            logger.debug(f"Task removed from registry: {task}")
        except Exception as e:
            logger.error(f"Error removing task from registry: {e}")
    
    task.add_done_callback(cleanup_task)
    return task

async def send_keep_alive(ws, session_id, keep_alive_count=0):
    """Send a keep-alive message to maintain the WebSocket connection."""
    try:
        keep_alive = {
            "type": "keep_alive",
            "count": keep_alive_count,
            "timestamp": time.time(),
            "session_id": session_id,
            "message": "Connection is alive"
        }
        await ws.send(json.dumps(keep_alive))
        logger.info(f"[WS:{session_id}] Sent keep-alive #{keep_alive_count}")
        return True
    except Exception as e:
        logger.error(f"[WS:{session_id}] Error sending keep-alive #{keep_alive_count}: {e}")
        
        # Try with alternative format
        try:
            alt_keep_alive = {
                "event": "ping",
                "timestamp": time.time(),
                "session_id": session_id
            }
            await ws.send(json.dumps(alt_keep_alive))
            logger.info(f"[WS:{session_id}] Sent alternative keep-alive #{keep_alive_count}")
            return True
        except Exception as alt_e:
            logger.error(f"[WS:{session_id}] Alternative keep-alive also failed: {alt_e}")
            return False

async def maintain_connection(ws, session_id):
    """Maintain the WebSocket connection with periodic keep-alive messages."""
    keep_alive_count = 0
    keep_alive_interval = 5.0  # seconds
    
    try:
        logger.info(f"[WS:{session_id}] Starting connection maintenance task")
        
        while True:
            # Send keep-alive message
            keep_alive_count += 1
            success = await send_keep_alive(ws, session_id, keep_alive_count)
            
            if not success:
                logger.error(f"[WS:{session_id}] Failed to send keep-alive #{keep_alive_count}, connection may be dead")
                break
            
            # Wait for the next interval
            logger.debug(f"[WS:{session_id}] Waiting {keep_alive_interval}s until next keep-alive")
            await asyncio.sleep(keep_alive_interval)
    
    except asyncio.CancelledError:
        logger.info(f"[WS:{session_id}] Connection maintenance task cancelled after {keep_alive_count} keep-alives")
    except Exception as e:
        logger.error(f"[WS:{session_id}] Error in connection maintenance: {e}")
        logger.error(traceback.format_exc())

async def greeting_sequence(ws, session_id):
    """Send a greeting audio and keep-alive messages to establish the connection."""
    try:
        logger.info(f"[WS:{session_id}] Starting greeting sequence for bidirectional stream")
        
        # For bidirectional Media Streams, we need to send actual audio back to Twilio
        # This example demonstrates how to send a media message to Twilio
        
        # Here we would normally encode "Welcome to Red Bar Sushi!" as μ-law audio
        # For simplicity, we're using a placeholder media message structure
        # In a real implementation, this would be actual base64 encoded μ-law audio at 8000 Hz
        
        # Send a media message to Twilio
        media_message = {
            "event": "media",
            "streamSid": active_connections[session_id].get("stream_sid", "unknown"),
            "media": {
                "payload": "base64_encoded_audio_would_go_here",
                "track": "outbound"  # This would be real audio to send to the caller
            }
        }
        
        # Send multiple keep-alive messages immediately after connection
        for i in range(5):
            keep_alive = {
                "event": "heartbeat", 
                "message": f"Keeping connection alive ({i+1}/5)",
                "timestamp": time.time(),
                "session_id": session_id
            }
            await asyncio.sleep(0.2)  # Small delay between messages
            await ws.send(json.dumps(keep_alive))
            logger.info(f"[WS:{session_id}] Sent keep-alive #{i+1} after connection")
        
        logger.info(f"[WS:{session_id}] Completed initial keep-alive sequence")
        
        # Mark message to track media events
        mark_message = {
            "event": "mark",
            "streamSid": active_connections[session_id].get("stream_sid", "unknown"),
            "mark": {
                "name": "greeting_complete"
            }
        }
        
        # In a real implementation, we would:
        # 1. Receive audio from caller through media events
        # 2. Process that audio through speech recognition
        # 3. Generate response audio (TTS)
        # 4. Send that audio back to Twilio as media messages with base64 encoded payload
        # 5. Use mark messages to track playback progress
        
        # The key points for bidirectional streams:
        # - Media messages need "event": "media" format
        # - Audio must be μ-law encoded at 8000 Hz
        # - Audio must be base64 encoded in the payload field
        # - Mark messages can track playback positions
        # - Bidirectional keeps the connection open indefinitely
        
        logger.info(f"[WS:{session_id}] Completed greeting sequence setup")
        
    except Exception as e:
        logger.error(f"[WS:{session_id}] Error in greeting sequence: {e}")
        logger.error(traceback.format_exc())

async def process_twilio_message(ws, session_id, message):
    """Process a message from Twilio Media Streams."""
    try:
        # Parse the message
        data = json.loads(message)
        event_type = data.get("event")
        
        logger.debug(f"[WS:{session_id}] Received event '{event_type}' from Twilio")
        
        # Handle different event types
        if event_type == "start":
            # Connection start event
            stream_sid = data.get("streamSid", "unknown")
            call_sid = data.get("callSid", "unknown")
            
            # Important metadata from the start event
            media_format = data.get("media", {}).get("format", {})
            sample_rate = media_format.get("sampleRate", 8000)
            channels = media_format.get("channels", 1)
            
            logger.info(f"[WS:{session_id}] Received Twilio start event")
            logger.info(f"[WS:{session_id}] Call SID: {call_sid}")
            logger.info(f"[WS:{session_id}] Stream SID: {stream_sid}")
            logger.info(f"[WS:{session_id}] Media format: {sample_rate}Hz, {channels} channel(s)")
            
            # Store call info in connection tracking
            active_connections[session_id]["call_sid"] = call_sid
            active_connections[session_id]["stream_sid"] = stream_sid
            active_connections[session_id]["sample_rate"] = sample_rate
            active_connections[session_id]["channels"] = channels
            active_connections[session_id]["protocol_version"] = data.get("protocol", "1.0.0")
            
            # Send welcome response for bidirectional streams
            welcome = {
                "event": "connected",
                "message": "WebSocket connection established for bidirectional Media Streams",
                "timestamp": time.time(),
                "session_id": session_id
            }
            await ws.send(json.dumps(welcome))
            logger.info(f"[WS:{session_id}] Sent welcome message")
            
            # Start greeting sequence as a separate task
            greeting_task = asyncio.create_task(greeting_sequence(ws, session_id))
            add_task_to_registry(greeting_task)
            logger.info(f"[WS:{session_id}] Started greeting sequence task")
            
        elif event_type == "media":
            # Media event (audio data)
            track = data.get("media", {}).get("track", "inbound_track")
            chunk_ts = data.get("chunk", {}).get("timestamp", 0)
            payload = data.get("chunk", {}).get("payload", "")
            
            # For bidirectional streams, we receive audio from the caller
            # Process audio data (in real implementation, this would go to a speech recognition system)
            
            # Log media events only occasionally to avoid flooding
            if active_connections[session_id]["media_count"] % 50 == 0:
                logger.debug(f"[WS:{session_id}] Received media chunk on track '{track}' (count: {active_connections[session_id]['media_count']})")
            
            active_connections[session_id]["media_count"] += 1
            active_connections[session_id]["last_media_time"] = time.time()
            
        elif event_type == "mark":
            # Mark event - for tracking media playback in bidirectional streams
            mark_name = data.get("mark", {}).get("name", "unknown")
            logger.debug(f"[WS:{session_id}] Received mark event: {mark_name}")
            
        elif event_type == "stop":
            # Stream stop event
            logger.info(f"[WS:{session_id}] Received stop event from Twilio")
            
        elif event_type == "dtmf":
            # DTMF event - when the user presses keys on their phone
            digit = data.get("dtmf", {}).get("digit", "")
            logger.info(f"[WS:{session_id}] Received DTMF: {digit}")
            
        else:
            # Other event types
            logger.info(f"[WS:{session_id}] Received other event type: {event_type}")
            logger.debug(f"[WS:{session_id}] Event data: {data}")
    
    except json.JSONDecodeError:
        # Not JSON, handle as text
        logger.info(f"[WS:{session_id}] Received non-JSON message: {message[:100]}")
        
    except Exception as e:
        logger.error(f"[WS:{session_id}] Error processing message: {e}")
        logger.error(traceback.format_exc())

async def handle_enhanced_media_stream(ws):
    """
    Enhanced WebSocket handler for Twilio Media Streams with robust connection maintenance.
    
    Args:
        ws: The WebSocket connection
    """
    # Generate a unique session ID for this connection
    session_id = str(uuid.uuid4())[:8]
    connection_start_time = time.time()
    
    # Initialize connection tracking
    active_connections[session_id] = {
        "id": session_id,
        "connected_at": connection_start_time,
        "messages_received": 0,
        "messages_sent": 0,
        "media_count": 0,
        "last_activity_time": connection_start_time,
        "last_media_time": None,
        "call_sid": None,
        "stream_sid": None
    }
    
    logger.info(f"[WS:{session_id}] WebSocket connection established")
    logger.info(f"[WS:{session_id}] Connection ID: {session_id}")
    logger.info(f"[WS:{session_id}] Active connections: {len(active_connections)}")
    
    try:
        # Send initial welcome message
        welcome_msg = json.dumps({
            "type": "connected", 
            "message": "WebSocket connection established",
            "timestamp": time.time(),
            "session_id": session_id
        })
        await ws.send(welcome_msg)
        active_connections[session_id]["messages_sent"] += 1
        logger.info(f"[WS:{session_id}] Sent initial welcome message")
        
        # Start connection maintenance task
        maintenance_task = asyncio.create_task(maintain_connection(ws, session_id))
        add_task_to_registry(maintenance_task)
        logger.info(f"[WS:{session_id}] Started connection maintenance task")
        
        # Main message processing loop
        while True:
            try:
                # Receive message with timeout
                message = await asyncio.wait_for(ws.receive(), timeout=10.0)
                
                # Update activity tracking
                active_connections[session_id]["messages_received"] += 1
                active_connections[session_id]["last_activity_time"] = time.time()
                
                # Process the message
                await process_twilio_message(ws, session_id, message)
                
            except asyncio.TimeoutError:
                # No message received within timeout, send keep-alive
                logger.debug(f"[WS:{session_id}] No message received for 10s, checking connection")
                
                # Check if connection is still active
                try:
                    await send_keep_alive(ws, session_id, active_connections[session_id]["messages_sent"])
                    active_connections[session_id]["messages_sent"] += 1
                except Exception as e:
                    logger.error(f"[WS:{session_id}] Failed to send keep-alive: {e}")
                    break
                
            except Exception as e:
                logger.error(f"[WS:{session_id}] Error receiving message: {e}")
                logger.error(traceback.format_exc())
                break
    
    except Exception as e:
        logger.error(f"[WS:{session_id}] Error in WebSocket handler: {e}")
        logger.error(traceback.format_exc())
    
    finally:
        # Calculate connection duration and log statistics
        connection_duration = time.time() - connection_start_time
        
        logger.info(f"[WS:{session_id}] WebSocket connection closed after {connection_duration:.2f}s")
        logger.info(f"[WS:{session_id}] Messages received: {active_connections[session_id]['messages_received']}")
        logger.info(f"[WS:{session_id}] Messages sent: {active_connections[session_id]['messages_sent']}")
        logger.info(f"[WS:{session_id}] Media chunks: {active_connections[session_id]['media_count']}")
        
        # Clean up connection tracking
        if session_id in active_connections:
            del active_connections[session_id]
        
        logger.info(f"[WS:{session_id}] Connection tracking removed, active connections: {len(active_connections)}")