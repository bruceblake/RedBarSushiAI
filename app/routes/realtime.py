"""
WebSocket routes for realtime audio processing with OpenAI Agents SDK.
This module provides the WebSocket endpoints for handling realtime audio streams.
"""

from flask import Blueprint, request, jsonify, current_app
import logging
import json
import time
import os
import traceback
import base64
import uuid
import websocket  # Import websocket for WebSocketConnectionClosedException handling
from typing import Dict, List, Any, Optional, Tuple, Union
import gevent
from gevent import Greenlet
from gevent.queue import Queue, Empty
from gevent.event import Event
import datetime

from app import sock
from app.utils.realtime_audio_sdk import realtime_processor
from app.utils.conversation_store_sdk import agents_conversation_store

# Configure enhanced logging
logger = logging.getLogger(__name__)

# Create a formatter that includes milliseconds in the timestamp
# This will be used for timestamp logging in debug messages
def get_timestamp_str():
    """Get current timestamp with millisecond precision as a string"""
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

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

# Create blueprint
realtime_bp = Blueprint("realtime", __name__)

@sock.route("/ws/media/<call_sid>")
def handle_media_realtime(ws, call_sid):
    """
    WebSocket endpoint for handling media streams from Twilio.
    
    This function handles bidirectional audio streaming between
    Twilio's Media Streams and OpenAI's Realtime API. It receives audio from Twilio,
    forwards it to OpenAI, and returns synthesized responses back to Twilio.
    
    Uses gevent greenlets for concurrency to work with gevent worker.
    
    Args:
        ws: The WebSocket connection from Twilio
        call_sid: Call SID passed in URL path
    """
    import websocket  # gevent-compatible websocket-client library

    # Log connection with timestamp
    start_time = time.time()
    timestamp = get_timestamp_str()
    logger.critical(f"[{call_sid}] WebSocket connection established at {timestamp} (Gevent Handler)")
    
    # Log structured connection event
    log_entry = {
        "event": "CONNECTION_ESTABLISHED",
        "call_sid": call_sid,
        "timestamp": timestamp,
        "handler_type": "gevent"
    }
    logger.critical(f"STRUCTURED_LOG: {json.dumps(log_entry)}")
    
    stream_sid = None  # Will be set later
    openai_ws = None  # Define here for finally block
    
    # --- 1. Initial Setup ---
    try:
        # Get Config
        logger.debug(f"[{call_sid}] Getting configuration at {get_timestamp_str()}")
        openai_api_key = current_app.config.get('OPENAI_API_KEY', os.environ.get("OPENAI_API_KEY"))
        if not openai_api_key:
            # Last resort fallback for development
            try:
                logger.debug(f"[{call_sid}] Attempting to import OPENAI_API_KEY from agent_utils at {get_timestamp_str()}")
                from app.utils.agent_utils import OPENAI_API_KEY
                openai_api_key = OPENAI_API_KEY
                logger.debug(f"[{call_sid}] Successfully imported OPENAI_API_KEY at {get_timestamp_str()}")
            except Exception as e:
                logger.error(f"[{call_sid}] Error importing OPENAI_API_KEY at {get_timestamp_str()}: {e}")
                return
        
        openai_ws_url = "wss://api.openai.com/v1/realtime"
        openai_model = current_app.config.get('OPENAI_REALTIME_MODEL', "gpt-4o-realtime-preview-2024-10-01")
        openai_voice = current_app.config.get('OPENAI_REALTIME_VOICE', "shimmer")
        system_instructions = current_app.config.get('OPENAI_REALTIME_INSTRUCTIONS', """
        You are an AI assistant for a sushi restaurant named Red Bar Sushi. Your role is to help customers with their 
        orders and menu questions in a friendly, efficient manner. Speak with a helpful, welcoming tone appropriate 
        for a high-end sushi restaurant.
        """)
        
        logger.debug(f"[{call_sid}] Configuration loaded at {get_timestamp_str()}: Model={openai_model}, Voice={openai_voice}")

        # Handle initial Twilio messages ('connected', 'start') - SYNCHRONOUSLY
        logger.info(f"[{call_sid}] Waiting for initial Twilio messages at {get_timestamp_str()}...")
        connected_received = False
        for attempt in range(2):  # Try receiving twice to get connected then start
            try:
                logger.debug(f"[{call_sid}] Attempt {attempt+1} to receive initial message from Twilio at {get_timestamp_str()}")
                receive_start_time = time.time()
                msg_str = ws.receive(timeout=10)  # Blocking receive with timeout
                receive_end_time = time.time()
                receive_duration_ms = (receive_end_time - receive_start_time) * 1000
                
                if msg_str is None:  # Timeout or clean close
                    logger.warning(f"[{call_sid}] Did not receive expected message from Twilio after {receive_duration_ms:.2f}ms at {get_timestamp_str()}")
                    return
                
                # Log received message
                logger.debug(f"[{call_sid}] Received message from Twilio at {get_timestamp_str()} (took {receive_duration_ms:.2f}ms): {msg_str}")
                log_ws_event(call_sid, "RECV", "twilio_initial", msg_str, receive_duration_ms)
                
                message = json.loads(msg_str)
                event = message.get("event")
                logger.info(f"[{call_sid}] Received initial message: {event} at {get_timestamp_str()}")

                if event == "connected":
                    connected_received = True
                    logger.info(f"[{call_sid}] Received 'connected' event from Twilio at {get_timestamp_str()}")
                elif event == "start":
                    stream_sid = message.get("start", {}).get("streamSid")
                    if not stream_sid:
                        logger.error(f"[{call_sid}] 'start' event missing streamSid at {get_timestamp_str()}")
                        return
                    logger.info(f"[{call_sid}] Twilio media stream started at {get_timestamp_str()}. Stream SID: {stream_sid}")
                    break  # Got start, proceed
                else:
                    logger.warning(f"[{call_sid}] Received unexpected initial message type: {event} at {get_timestamp_str()}")

            except TimeoutError:  # Check exact exception from ws.receive timeout
                logger.error(f"[{call_sid}] Timeout waiting for initial message from Twilio at {get_timestamp_str()}")
                return
            except json.JSONDecodeError:
                logger.error(f"[{call_sid}] Failed to decode initial JSON from Twilio at {get_timestamp_str()}: {msg_str}", exc_info=True)
                return
            except Exception as e:  # Catch WebSocket closed errors specifically if possible
                logger.error(f"[{call_sid}] Error receiving initial message at {get_timestamp_str()}: {e}", exc_info=True)
                return

        if not stream_sid:
            logger.error(f"[{call_sid}] Failed to get Stream SID from initial Twilio messages at {get_timestamp_str()}")
            return  # Close handled in finally

        # Send Welcome
        welcome_msg = {"type": "connected", "message": "Connected to RedBarSushi AI (Gevent)", 
                      "call_sid": call_sid, "stream_sid": stream_sid}
        welcome_str = json.dumps(welcome_msg)
        logger.debug(f"[{call_sid}] Sending welcome message at {get_timestamp_str()}: {welcome_str}")
        
        send_start_time = time.time()
        ws.send(welcome_str)
        send_end_time = time.time()
        send_duration_ms = (send_end_time - send_start_time) * 1000
        
        logger.info(f"[{call_sid}] Sent welcome message at {get_timestamp_str()} (took {send_duration_ms:.2f}ms)")
        log_ws_event(call_sid, "SEND", "twilio_welcome", welcome_msg, send_duration_ms)

        # Initialize Agent
        try:
            # If agent factory needs app context, push one temporarily
            agent_start_time = time.time()
            logger.debug(f"[{call_sid}] Initializing agent at {get_timestamp_str()}")
            from app.agents.factory_with_orchestration import enhanced_agent_factory
            frontline_agent = enhanced_agent_factory.create_agents()
            agent_end_time = time.time()
            agent_init_duration_ms = (agent_end_time - agent_start_time) * 1000
            logger.info(f"[{call_sid}] Successfully initialized agent at {get_timestamp_str()} (took {agent_init_duration_ms:.2f}ms)")
        except Exception as agent_error:
            logger.error(f"[{call_sid}] Failed to initialize agent at {get_timestamp_str()}: {agent_error}", exc_info=True)
            frontline_agent = None  # Handle gracefully later

        # --- 2. Connect to OpenAI (Using websocket-client) ---
        openai_connect_url = f"{openai_ws_url}?model={openai_model}"  # Model in URL as per docs
        openai_headers = [
            f"Authorization: Bearer {openai_api_key}",
            "OpenAI-Beta: realtime=v1"
        ]
        logger.info(f"[{call_sid}] Connecting to OpenAI at {get_timestamp_str()}: {openai_connect_url}")
        
        # Use websocket-client's create_connection (blocking, suitable for gevent)
        # Add timeout for connection attempt itself
        connect_start_time = time.time()
        logger.debug(f"[{call_sid}] Starting OpenAI WebSocket connection attempt at {get_timestamp_str()}")
        openai_ws = websocket.create_connection(openai_connect_url, header=openai_headers, timeout=10)
        connect_end_time = time.time()
        connect_duration_ms = (connect_end_time - connect_start_time) * 1000
        
        # Set timeout for subsequent recv calls
        openai_ws.settimeout(15)  # Example: 15 second timeout for receiving messages
        logger.info(f"[{call_sid}] Successfully connected to OpenAI at {get_timestamp_str()} (took {connect_duration_ms:.2f}ms)")
        
        # Log the OpenAI connection event
        log_entry = {
            "event": "OPENAI_CONNECTED",
            "call_sid": call_sid,
            "timestamp": get_timestamp_str(),
            "model": openai_model,
            "voice": openai_voice,
            "duration_ms": connect_duration_ms
        }
        logger.info(f"STRUCTURED_LOG: {json.dumps(log_entry)}")

        # --- 3. Send Session Config ---
        logger.debug(f"[{call_sid}] Sending OpenAI session configuration at {get_timestamp_str()}")
        # Send initial session configuration without tools
        # The function returns the saved tools for the second update
        pending_tools = send_openai_session_configuration_sync(openai_ws, call_sid, openai_model, openai_voice, system_instructions)

        # --- 4. Start Concurrent Greenlets ---
        logger.info(f"[{call_sid}] Spawning Greenlets at {get_timestamp_str()}...")
        
        # Pass mutable list for stream_sid if needed, though it's likely set now
        stream_sid_container = [stream_sid] 

        # Context object for agents/tools
        # Include pending_tools for the second session.update that will be sent after session.created/updated event
        run_context_data = {
            'call_sid': call_sid, 
            'stream_sid': stream_sid,
            'pending_tools': pending_tools  # Will be sent in second session.update
        } 

        # Spawn greenlets
        logger.debug(f"[{call_sid}] Spawning Twilio->OpenAI forwarding greenlet at {get_timestamp_str()}")
        fwd_greenlet = gevent.spawn(
            receive_from_twilio_and_forward_to_openai_sync, 
            ws, openai_ws, call_sid, stream_sid_container
        )
        
        logger.debug(f"[{call_sid}] Spawning OpenAI->Twilio processing greenlet at {get_timestamp_str()}")
        proc_greenlet = gevent.spawn(
            process_openai_responses_and_interact_sync, 
            openai_ws, ws, call_sid, stream_sid_container, frontline_agent, run_context_data
        )
        
        logger.debug(f"[{call_sid}] Spawning heartbeat greenlet at {get_timestamp_str()}")
        hb_greenlet = gevent.spawn(
            send_heartbeats_sync, 
            ws, call_sid
        )
        
        # Log all greenlets spawned
        log_entry = {
            "event": "GREENLETS_SPAWNED",
            "call_sid": call_sid,
            "timestamp": get_timestamp_str(),
            "greenlets": ["twilio_to_openai", "openai_to_twilio", "heartbeat"]
        }
        logger.info(f"STRUCTURED_LOG: {json.dumps(log_entry)}")

        # Wait for any of them to finish
        logger.info(f"[{call_sid}] Joining Greenlets at {get_timestamp_str()}...")
        # joinall waits for all specified greenlets, raise_error=False prevents one dying from killing the join immediately
        join_start_time = time.time()
        gevent.joinall([fwd_greenlet, proc_greenlet, hb_greenlet], raise_error=False) 
        join_end_time = time.time()
        join_duration_ms = (join_end_time - join_start_time) * 1000
        
        logger.info(f"[{call_sid}] Greenlets joined/completed at {get_timestamp_str()} (after {join_duration_ms:.2f}ms)")
        
        # Log greenlet join completion
        log_entry = {
            "event": "GREENLETS_COMPLETED",
            "call_sid": call_sid,
            "timestamp": get_timestamp_str(),
            "duration_ms": join_duration_ms,
            "fwd_alive": not fwd_greenlet.dead,
            "proc_alive": not proc_greenlet.dead,
            "hb_alive": not hb_greenlet.dead
        }
        logger.info(f"STRUCTURED_LOG: {json.dumps(log_entry)}")

    except websocket.WebSocketTimeoutException:
        logger.error(f"[{call_sid}] Timeout during OpenAI WebSocket operation at {get_timestamp_str()}")
    except websocket.WebSocketException as e:
        logger.error(f"[{call_sid}] OpenAI WebSocket Error at {get_timestamp_str()}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"[{call_sid}] Error in main handler at {get_timestamp_str()}: {e}", exc_info=True)
    finally:
        finally_start_time = time.time()
        logger.info(f"[{call_sid}] Cleaning up main handler at {get_timestamp_str()}...")
        
        # Log entering finally block
        log_entry = {
            "event": "CLEANUP_STARTED",
            "call_sid": call_sid,
            "timestamp": get_timestamp_str()
        }
        logger.info(f"STRUCTURED_LOG: {json.dumps(log_entry)}")
        
        # Cleanly close OpenAI connection
        if openai_ws and hasattr(openai_ws, 'connected') and openai_ws.connected:
            try:
                logger.info(f"[{call_sid}] Closing OpenAI WebSocket at {get_timestamp_str()}")
                # Log before close
                log_entry = {
                    "event": "OPENAI_WS_CLOSING",
                    "call_sid": call_sid,
                    "timestamp": get_timestamp_str()
                }
                logger.info(f"STRUCTURED_LOG: {json.dumps(log_entry)}")
                
                openai_close_start = time.time()
                # websocket-client's close() method doesn't accept code/reason parameters
                openai_ws.close()  # No arguments for websocket-client
                openai_close_end = time.time()
                openai_close_duration_ms = (openai_close_end - openai_close_start) * 1000
                
                # Log after close
                log_entry = {
                    "event": "OPENAI_WS_CLOSED",
                    "call_sid": call_sid,
                    "timestamp": get_timestamp_str(),
                    "duration_ms": openai_close_duration_ms
                }
                logger.info(f"STRUCTURED_LOG: {json.dumps(log_entry)}")
                logger.info(f"[{call_sid}] OpenAI WebSocket closed at {get_timestamp_str()} (took {openai_close_duration_ms:.2f}ms)")
            except Exception as close_err:
                logger.error(f"[{call_sid}] Error closing OpenAI WS at {get_timestamp_str()}: {close_err}")
        else:
            logger.info(f"[{call_sid}] OpenAI WS already closed or not established at {get_timestamp_str()}")

        # Cleanly close Twilio connection
        # Use the correct close method for Flask-Sock/simple-websocket ws object
        if ws and hasattr(ws, 'connected') and ws.connected:
            try:
                logger.info(f"[{call_sid}] Closing Twilio WebSocket at {get_timestamp_str()}")
                # Log before close
                log_entry = {
                    "event": "TWILIO_WS_CLOSING",
                    "call_sid": call_sid,
                    "timestamp": get_timestamp_str()
                }
                logger.info(f"STRUCTURED_LOG: {json.dumps(log_entry)}")
                
                twilio_close_start = time.time()
                try:
                    # Use standard WebSocket close code 1000 (Normal Closure)
                    # This indicates a successful, clean disconnection
                    ws.close(1000, "Call completed normally")
                except TypeError:
                    # Fallback if the ws implementation doesn't accept arguments
                    logger.info(f"[{call_sid}] Using no-argument close fallback for Twilio WS")
                    ws.close()  # No arguments as fallback
                twilio_close_end = time.time()
                twilio_close_duration_ms = (twilio_close_end - twilio_close_start) * 1000
                
                # Log after close
                log_entry = {
                    "event": "TWILIO_WS_CLOSED",
                    "call_sid": call_sid,
                    "timestamp": get_timestamp_str(),
                    "duration_ms": twilio_close_duration_ms
                }
                logger.info(f"STRUCTURED_LOG: {json.dumps(log_entry)}")
                logger.info(f"[{call_sid}] Twilio WebSocket closed at {get_timestamp_str()} (took {twilio_close_duration_ms:.2f}ms)")
            except Exception as close_err:
                logger.error(f"[{call_sid}] Error closing Twilio WS at {get_timestamp_str()}: {close_err}")
        else:
            logger.info(f"[{call_sid}] Twilio WS already closed or not established at {get_timestamp_str()}")
        
        # Total duration of the handler
        finally_end_time = time.time()
        cleanup_duration_ms = (finally_end_time - finally_start_time) * 1000
        total_duration_ms = (finally_end_time - start_time) * 1000
        
        log_entry = {
            "event": "HANDLER_FINISHED",
            "call_sid": call_sid,
            "timestamp": get_timestamp_str(),
            "cleanup_duration_ms": cleanup_duration_ms,
            "total_duration_ms": total_duration_ms
        }
        logger.critical(f"STRUCTURED_LOG: {json.dumps(log_entry)}")
        logger.critical(f"[{call_sid}] WebSocket handler finished at {get_timestamp_str()} (total duration: {total_duration_ms:.2f}ms)")


def send_openai_session_configuration_sync(openai_ws, call_sid, openai_model, openai_voice, system_instructions):
    """
    Constructs and sends the session.update message SYNCHRONOUSLY.
    
    Args:
        openai_ws: WebSocket connection to OpenAI
        call_sid: The Twilio call SID
        openai_model: The OpenAI model to use
        openai_voice: The voice to use for TTS
        system_instructions: The system instructions for the assistant
    """
    config_start_time = time.time()
    timestamp = get_timestamp_str()
    logger.info(f"[{call_sid}] Preparing session.update payload at {timestamp} (sync)")
    
    # Log structured event
    log_entry = {
        "event": "SESSION_CONFIG_PREPARING",
        "call_sid": call_sid,
        "timestamp": timestamp,
        "model": openai_model,
        "voice": openai_voice
    }
    logger.info(f"STRUCTURED_LOG: {json.dumps(log_entry)}")
    
    # ENHANCED VAD configuration based on OpenAI documentation
    # These settings are CRITICAL for proper interruption handling
    
    # Get VAD silence duration from environment or use a shorter value than before
    vad_silence_ms = int(os.environ.get("OPENAI_REALTIME_VAD_SILENCE_MS", 1000))
    
    turn_detection_config = {
        "type": "server_vad",
        "silence_duration_ms": vad_silence_ms,  # Reduced from 2000ms to 1000ms for faster turn detection
        "create_response": True,                # Auto-generate response on silence detection
        "interrupt_response": True              # CRITICAL: Allow interrupting the assistant while speaking
    }
    
    # Log interruption settings specifically to verify correct configuration
    logger.info(f"[{call_sid}] INTERRUPT CONFIGURATION at {get_timestamp_str()}: interrupt_response=true, silence_threshold={turn_detection_config.get('silence_duration_ms')}ms")
    
    # Log structured VAD configuration
    vad_log = {
        "event": "VAD_CONFIGURATION",
        "call_sid": call_sid,
        "timestamp": get_timestamp_str(),
        "vad_type": turn_detection_config.get("type"),
        "silence_duration_ms": turn_detection_config.get("silence_duration_ms"),
        "create_response": turn_detection_config.get("create_response"),
        "interrupt_response": turn_detection_config.get("interrupt_response")
    }
    logger.info(f"STRUCTURED_LOG: {json.dumps(vad_log)}")
    
    # TEMPORARILY DISABLED TOOLS as requested by user
    tools_start_time = time.time()
    tools = []
    
    # Log that tools are disabled
    logger.info(f"[{call_sid}] Tools are DISABLED as requested by user")
    
    # Log structured tool configuration showing disabled
    tools_log = {
        "event": "TOOLS_CONFIGURATION",
        "call_sid": call_sid,
        "timestamp": get_timestamp_str(),
        "tool_count": 0,
        "tools": [],
        "disabled": True,
        "reason": "User requested to disable tools due to API issues"
    }
    logger.info(f"STRUCTURED_LOG: {json.dumps(tools_log)}")
    
    # Main session configuration - INITIAL UPDATE (no tools)
    # Following the OpenAI documentation pattern: send initial config first without tools
    session_update_payload = {
        "type": "session.update",
        "session": {
            "model": openai_model,
            "voice": openai_voice,
            "instructions": system_instructions,
            "input_audio_format": "g711_ulaw",  # Format for Twilio μ-law audio
            "output_audio_format": "g711_ulaw", # Format for Twilio μ-law audio
            "modalities": ["text", "audio"],    # Both modalities required for audio+text
            "turn_detection": turn_detection_config
        }
    }
    
    # Important: For initial session.update DO NOT include tools
    # According to OpenAI Realtime API documentation, it's better to send:
    # 1. First session.update with basic config (model, voice, etc)
    # 2. Second session.update with just tools after receiving session.created/updated
    logger.info(f"[{call_sid}] Preparing INITIAL session.update WITHOUT tools at {get_timestamp_str()}")
    
    # TEMPORARILY DISABLED: Not saving tools for second session.update
    saved_tools = None  # Force to None to prevent any second update with tools
    
    # Log and send the exact payload
    payload_str = json.dumps(session_update_payload)
    logger.debug(f"[{call_sid}] Session update JSON BEFORE send at {get_timestamp_str()}: {payload_str}")
    
    # Log structured session update payload
    config_log = {
        "event": "SESSION_UPDATE_PAYLOAD",
        "call_sid": call_sid,
        "timestamp": get_timestamp_str(),
        "has_tools": bool(tools),
        "tool_count": len(tools) if tools else 0,
        "model": openai_model,
        "voice": openai_voice,
        "modalities": session_update_payload["session"]["modalities"],
        "vad_config": turn_detection_config
    }
    logger.info(f"STRUCTURED_LOG: {json.dumps(config_log)}")
    
    # Log with appropriate message based on whether tools are included
    if tools:
        logger.info(f"[{call_sid}] Sending session.update at {get_timestamp_str()} (sync) - Configuration with 1 tool")
    else:
        logger.info(f"[{call_sid}] Sending session.update at {get_timestamp_str()} (sync) - Minimal configuration without tools")
    
    try:
        # Log before sending
        send_log = {
            "event": "SESSION_UPDATE_SENDING",
            "call_sid": call_sid,
            "timestamp": get_timestamp_str(),
            "payload_size": len(payload_str)
        }
        logger.info(f"STRUCTURED_LOG: {json.dumps(send_log)}")
        
        # Send the session configuration to OpenAI
        send_start_time = time.time()
        openai_ws.send(payload_str)  # Blocking send
        send_end_time = time.time()
        send_duration_ms = (send_end_time - send_start_time) * 1000
        
        # Log successful send with timing information
        log_ws_event(call_sid, "SEND", "session.update", session_update_payload, send_duration_ms, "info")
        
        logger.debug(f"[{call_sid}] JSON string AFTER successful send at {get_timestamp_str()}: {payload_str}")
        logger.info(f"[{call_sid}] Session.update sent successfully at {get_timestamp_str()} (took {send_duration_ms:.2f}ms)")
        
        # Log structured successful send
        success_log = {
            "event": "SESSION_UPDATE_SENT",
            "call_sid": call_sid,
            "timestamp": get_timestamp_str(),
            "duration_ms": send_duration_ms
        }
        logger.info(f"STRUCTURED_LOG: {json.dumps(success_log)}")
        
        # Additional verification step - wait briefly for potential error response
        logger.debug(f"[{call_sid}] Waiting briefly for potential error response at {get_timestamp_str()}")
        gevent.sleep(0.1)  # Short delay to check for immediate error response
        
        # Log confirmation of interrupt settings
        logger.info(f"[{call_sid}] VERIFIED SETTINGS at {get_timestamp_str()}: Interruption handling enabled with interrupt_response={turn_detection_config.get('interrupt_response', True)}, " + 
                   f"silence_duration={turn_detection_config.get('silence_duration_ms')}ms")
        
        # Total duration of configuration
        config_end_time = time.time()
        config_duration_ms = (config_end_time - config_start_time) * 1000
        
        # Final structured log for complete configuration process
        complete_log = {
            "event": "SESSION_CONFIG_COMPLETE",
            "call_sid": call_sid,
            "timestamp": get_timestamp_str(),
            "total_duration_ms": config_duration_ms,
            "send_duration_ms": send_duration_ms,
            "initial_update": True,  # This indicates first update without tools
            "tools_pending": bool(saved_tools)  # Indicates if we have tools to send in second update
        }
        logger.info(f"STRUCTURED_LOG: {json.dumps(complete_log)}")
        
        # Return the saved_tools so the second session.update can be sent later
        return saved_tools
                   
    except Exception as e:
        error_time = get_timestamp_str()
        logger.error(f"[{call_sid}] Failed to send session.update at {error_time} (sync): {e}", exc_info=True)
        return None  # Return None to indicate failure
        
        # Log structured error
        error_log = {
            "event": "SESSION_UPDATE_ERROR",
            "call_sid": call_sid,
            "timestamp": error_time,
            "error": str(e)
        }
        logger.error(f"STRUCTURED_LOG: {json.dumps(error_log)}")
        return None

def send_openai_tools_configuration_sync(openai_ws, call_sid, tools):
    """
    Sends a second session.update focused only on tools configuration.
    This follows the OpenAI Realtime API documentation best practice to send tools
    in a separate session.update after the initial configuration is confirmed.
    
    Args:
        openai_ws: WebSocket connection to OpenAI
        call_sid: The Twilio call SID
        tools: List of tool definitions to send
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not tools:
        logger.info(f"[{call_sid}] No tools to send in second session.update at {get_timestamp_str()}")
        return True  # Nothing to do, but not an error
    
    # Start timing
    start_time = time.time()
    timestamp = get_timestamp_str()
    logger.info(f"[{call_sid}] Preparing SECOND session.update (TOOLS ONLY) at {timestamp}")
    
    # Log structured event start
    log_entry = {
        "event": "TOOLS_UPDATE_PREPARING",
        "call_sid": call_sid,
        "timestamp": timestamp,
        "tool_count": len(tools)
    }
    logger.info(f"STRUCTURED_LOG: {json.dumps(log_entry)}")
    
    # Create a minimal session.update with ONLY tools configuration
    # This follows the OpenAI documentation pattern for proper tools setup
    tools_update_payload = {
        "type": "session.update",
        "session": {
            "tools": tools,
            "tool_choice": "auto"
        }
    }
    
    # Log and send the exact payload
    payload_str = json.dumps(tools_update_payload)
    logger.debug(f"[{call_sid}] Tools update JSON BEFORE send at {get_timestamp_str()}: {payload_str}")
    
    # Log structured payload details
    tools_log = {
        "event": "TOOLS_UPDATE_PAYLOAD",
        "call_sid": call_sid,
        "timestamp": get_timestamp_str(),
        "tool_count": len(tools),
        "tool_names": [t.get("function", {}).get("name", "unknown") for t in tools if t.get("type") == "function"]
    }
    logger.info(f"STRUCTURED_LOG: {json.dumps(tools_log)}")
    
    try:
        # Send the tools update to OpenAI
        send_start_time = time.time()
        openai_ws.send(payload_str)  # Blocking send
        send_end_time = time.time()
        send_duration_ms = (send_end_time - send_start_time) * 1000
        
        # Log successful send with timing information
        log_ws_event(call_sid, "SEND", "session.update.tools", tools_update_payload, send_duration_ms, "info")
        
        logger.info(f"[{call_sid}] Tools update sent successfully at {get_timestamp_str()} (took {send_duration_ms:.2f}ms)")
        
        # Final structured log for tools update
        complete_log = {
            "event": "TOOLS_UPDATE_COMPLETE",
            "call_sid": call_sid,
            "timestamp": get_timestamp_str(),
            "total_duration_ms": (time.time() - start_time) * 1000,
            "send_duration_ms": send_duration_ms,
            "tool_count": len(tools)
        }
        logger.info(f"STRUCTURED_LOG: {json.dumps(complete_log)}")
        
        return True
    
    except Exception as e:
        error_time = get_timestamp_str()
        logger.error(f"[{call_sid}] Failed to send tools update at {error_time}: {e}", exc_info=True)
        
        # Log structured error
        error_log = {
            "event": "TOOLS_UPDATE_ERROR",
            "call_sid": call_sid,
            "timestamp": error_time,
            "error": str(e)
        }
        logger.error(f"STRUCTURED_LOG: {json.dumps(error_log)}")
        
        return False

def receive_from_twilio_and_forward_to_openai_sync(twilio_ws, openai_ws, call_sid, stream_sid_container):
    """
    Receives from Twilio (sync), forwards audio to OpenAI (sync). Runs in a greenlet.
    
    Args:
        twilio_ws: The WebSocket connection from Twilio
        openai_ws: The WebSocket connection to OpenAI
        call_sid: The Twilio call SID
        stream_sid_container: Mutable list containing the stream SID
    """
    # Track start time and log with timestamp
    greenlet_start_time = time.time()
    timestamp = get_timestamp_str()
    logger.info(f"[{call_sid}] Starting Twilio->OpenAI forwarding greenlet at {timestamp}")
    
    # Structured log for greenlet start
    start_log = {
        "event": "TWILIO_TO_OPENAI_STARTED",
        "call_sid": call_sid,
        "timestamp": timestamp,
        "greenlet_type": "twilio_to_openai"
    }
    logger.info(f"STRUCTURED_LOG: {json.dumps(start_log)}")
    
    try:
        # Track consecutive media packets to yield periodically
        media_packet_count = 0
        speech_packet_count = 0
        silence_packet_count = 0
        last_log_time = time.time()
        
        # Structured statistics log interval (in seconds)
        stats_interval = 5.0
        
        logger.debug(f"[{call_sid}] Entering Twilio->OpenAI forwarding loop at {get_timestamp_str()}")
        
        while True:
            # Log beginning of iteration occasionally
            if media_packet_count % 500 == 0:
                logger.debug(f"[{call_sid}] Twilio->OpenAI Loop - Iteration #{media_packet_count} at {get_timestamp_str()}")
            
            # Log statistics periodically
            current_time = time.time()
            if current_time - last_log_time > stats_interval:
                stats_duration = current_time - last_log_time
                stats_log = {
                    "event": "AUDIO_FORWARDING_STATS",
                    "call_sid": call_sid,
                    "timestamp": get_timestamp_str(),
                    "interval_seconds": stats_duration,
                    "total_packets": media_packet_count,
                    "speech_packets": speech_packet_count,
                    "silence_packets": silence_packet_count,
                    "packets_per_second": round(media_packet_count / (current_time - greenlet_start_time), 2)
                }
                logger.info(f"STRUCTURED_LOG: {json.dumps(stats_log)}")
                last_log_time = current_time
            
            # Check if OpenAI connection is still alive before receiving
            if not openai_ws or not hasattr(openai_ws, 'connected') or not openai_ws.connected:
                 logger.warning(f"[{call_sid}] OpenAI WS no longer connected at {get_timestamp_str()}. Stopping Twilio forwarder.")
                 
                 # Structured log for connection lost
                 disconnect_log = {
                     "event": "OPENAI_WS_DISCONNECTED",
                     "call_sid": call_sid,
                     "timestamp": get_timestamp_str(),
                     "total_processed_packets": media_packet_count
                 }
                 logger.warning(f"STRUCTURED_LOG: {json.dumps(disconnect_log)}")
                 
                 break
                 
            try:
                # Log before receiving
                logger.debug(f"[{call_sid}] Waiting for message from Twilio at {get_timestamp_str()}")
                
                # Blocking receive with timeout (gevent compatible)
                receive_start_time = time.time()
                message_str = twilio_ws.receive(timeout=5)  # Adjust timeout as needed
                receive_end_time = time.time()
                receive_duration_ms = (receive_end_time - receive_start_time) * 1000
                
                # If timeout occurred, loop again
                if message_str is None:
                    logger.debug(f"[{call_sid}] No message received from Twilio after {receive_duration_ms:.2f}ms (timeout) at {get_timestamp_str()}")
                    gevent.sleep(0.01)  # Yield control
                    continue

                # Log the received message (abbreviated for audio)
                if len(message_str) > 200:
                    logger.debug(f"[{call_sid}] Received message from Twilio at {get_timestamp_str()} (took {receive_duration_ms:.2f}ms): <{len(message_str)} bytes>")
                else:
                    logger.debug(f"[{call_sid}] Received message from Twilio at {get_timestamp_str()} (took {receive_duration_ms:.2f}ms): {message_str}")
                
                # Parse the message
                parse_start_time = time.time()
                message = json.loads(message_str)
                event = message.get("event")
                parse_end_time = time.time()
                parse_duration_ms = (parse_end_time - parse_start_time) * 1000
                
                logger.debug(f"[{call_sid}] Parsed Twilio message type '{event}' at {get_timestamp_str()} (took {parse_duration_ms:.2f}ms)")

                if event == "start":
                    # Log structured event
                    log_ws_event(call_sid, "RECV", "twilio_start", message, receive_duration_ms, "info")
                    
                    # Already handled mostly, but update just in case
                    new_sid = message.get("start", {}).get("streamSid")
                    if new_sid and stream_sid_container[0] != new_sid:
                         logger.info(f"[{call_sid}] Received Stream SID at {get_timestamp_str()}: {new_sid}")
                         stream_sid_container[0] = new_sid
                         
                         # Structured log for new stream SID
                         stream_log = {
                             "event": "STREAM_SID_UPDATED",
                             "call_sid": call_sid,
                             "timestamp": get_timestamp_str(),
                             "stream_sid": new_sid
                         }
                         logger.info(f"STRUCTURED_LOG: {json.dumps(stream_log)}")
                         
                elif event == "media":
                    # Don't log every media event at info level (too verbose)
                    # Only log structured event at debug level
                    log_ws_event(call_sid, "RECV", "twilio_media", message, receive_duration_ms, "debug")
                    
                    # Process the audio payload
                    audio_payload = message.get("media", {}).get("payload")
                    if audio_payload:
                        payload_size = len(audio_payload)
                        # Track if payload is empty (silence) or non-empty (speech)
                        # For Twilio, empty payload may still be a string with content
                        is_speech = payload_size > 0
                        
                        # Log occasionally for debugging
                        if media_packet_count % 500 == 0:
                            logger.debug(f"[{call_sid}] Processing Twilio audio packet #{media_packet_count} at {get_timestamp_str()}: size={payload_size}, is_speech={is_speech}")
                        
                        # ---- TOKEN BUCKET RATE LIMITING ----
                        # Enforce strict rate limiting to avoid overwhelming OpenAI API
                        
                        # Config for token bucket rate limiter
                        max_tokens = 5       # Maximum tokens in the bucket
                        token_rate = 2.0     # Tokens per second (conservative rate)
                        
                        # Initialize token bucket variables if not already set
                        if not hasattr(receive_from_twilio_and_forward_to_openai_sync, "_tokens"):
                            receive_from_twilio_and_forward_to_openai_sync._tokens = max_tokens
                            receive_from_twilio_and_forward_to_openai_sync._last_token_time = time.time()
                            logger.info(f"[{call_sid}] RATE LIMITER: Initialized token bucket with {max_tokens} tokens")
                        
                        # Add tokens based on elapsed time
                        current_time = time.time()
                        elapsed = current_time - receive_from_twilio_and_forward_to_openai_sync._last_token_time
                        receive_from_twilio_and_forward_to_openai_sync._last_token_time = current_time
                        
                        # Add tokens based on elapsed time
                        new_tokens = elapsed * token_rate
                        receive_from_twilio_and_forward_to_openai_sync._tokens = min(
                            max_tokens, 
                            receive_from_twilio_and_forward_to_openai_sync._tokens + new_tokens
                        )
                        
                        # Check if we have enough tokens
                        if receive_from_twilio_and_forward_to_openai_sync._tokens < 1.0:
                            # Not enough tokens, need to wait
                            wait_time = (1.0 - receive_from_twilio_and_forward_to_openai_sync._tokens) / token_rate
                            # Log wait time only occasionally to avoid log spam
                            if media_packet_count % 10 == 0:
                                logger.debug(f"[{call_sid}] RATE LIMITER: Waiting {wait_time*1000:.0f}ms for token replenishment")
                            # Sleep to wait for token replenishment
                            gevent.sleep(wait_time)
                            # Replenish token to exactly 1.0 after waiting
                            receive_from_twilio_and_forward_to_openai_sync._tokens = 1.0
                        
                        # Consume one token
                        receive_from_twilio_and_forward_to_openai_sync._tokens -= 1.0
                        
                        # Log token consumption occasionally
                        if media_packet_count % 20 == 0:
                            logger.debug(f"[{call_sid}] RATE LIMITER: Used token, {receive_from_twilio_and_forward_to_openai_sync._tokens:.2f} tokens remaining")
                        
                        # Create audio message to send to OpenAI
                        openai_audio_message = {
                            "type": "input_audio_buffer.append",
                            "audio": audio_payload
                        }
                        
                        # Log before sending to OpenAI
                        send_start_time = time.time()
                        logger.debug(f"[{call_sid}] Sending audio to OpenAI at {get_timestamp_str()}")
                        
                        # CRITICAL: Send audio to OpenAI immediately to enable interruption detection
                        openai_ws.send(json.dumps(openai_audio_message))  # Blocking send
                        
                        # Log after sending to OpenAI
                        send_end_time = time.time()
                        send_duration_ms = (send_end_time - send_start_time) * 1000
                        
                        # Only log every 100th audio packet at debug level to reduce volume
                        if media_packet_count % 100 == 0:
                            logger.debug(f"[{call_sid}] Sent audio to OpenAI at {get_timestamp_str()} (took {send_duration_ms:.2f}ms)")
                            log_ws_event(call_sid, "SEND", "openai_audio", {"type": "input_audio_buffer.append", "audio_size": payload_size}, send_duration_ms, "debug")
                        
                        # Increment counters
                        media_packet_count += 1
                        if is_speech:
                            speech_packet_count += 1
                        else:
                            silence_packet_count += 1
                        
                        # IMPORTANT: Add SEVERE rate limiting to prevent overwhelming OpenAI API
                        # This drastically slows down packet sending to ensure the system doesn't crash
                        # Add a substantial delay after EVERY packet
                        
                        # Add a base delay after every packet
                        base_delay = 0.05  # 50ms base delay for every packet
                        
                        # Every 5 packets, add an even longer delay 
                        if media_packet_count % 5 == 0:
                            extended_delay = 0.15  # 150ms extended delay every 5 packets
                            logger.debug(f"[{call_sid}] Adding EXTENDED delay of {extended_delay*1000}ms after packet #{media_packet_count} at {get_timestamp_str()}")
                            gevent.sleep(extended_delay)
                        # Every 20 packets, add a very long pause
                        elif media_packet_count % 20 == 0:
                            long_delay = 0.3  # 300ms long delay every 20 packets
                            logger.debug(f"[{call_sid}] Adding LONG delay of {long_delay*1000}ms after packet #{media_packet_count} at {get_timestamp_str()}")
                            gevent.sleep(long_delay)
                        
                        # Log and apply the base delay
                        if media_packet_count % 10 == 0:
                            logger.debug(f"[{call_sid}] Adding base delay of {base_delay*1000}ms after packet #{media_packet_count} at {get_timestamp_str()}")
                        gevent.sleep(base_delay)  # Base delay for every packet
                        
                        # Additional sleep depending on packet type
                        if is_speech:
                            if speech_packet_count % 10 == 0:
                                logger.debug(f"[{call_sid}] Yielding after speech packet at {get_timestamp_str()} (packet #{media_packet_count})")
                            gevent.sleep(0.025)  # Additional 25ms for speech packets
                        else:
                            gevent.sleep(0.01)   # Additional 10ms for silence packets
                    else:
                        logger.warning(f"[{call_sid}] Twilio 'media' event with no payload at {get_timestamp_str()}")
                        
                        # Structured log for empty payload
                        empty_log = {
                            "event": "EMPTY_MEDIA_PAYLOAD",
                            "call_sid": call_sid,
                            "timestamp": get_timestamp_str()
                        }
                        logger.warning(f"STRUCTURED_LOG: {json.dumps(empty_log)}")
                        
                elif event == "stop":
                    logger.info(f"[{call_sid}] Twilio 'stop' event received at {get_timestamp_str()}. Stopping audio forwarding.")
                    
                    # Structured log for stop event
                    stop_log = {
                        "event": "TWILIO_STOP_RECEIVED",
                        "call_sid": call_sid,
                        "timestamp": get_timestamp_str(),
                        "total_processed_packets": media_packet_count,
                        "speech_packets": speech_packet_count,
                        "silence_packets": silence_packet_count
                    }
                    logger.info(f"STRUCTURED_LOG: {json.dumps(stop_log)}")
                    
                    # No need to send commit/finalize with default server VAD
                    break
                    
                # Handle 'mark' if needed
                elif event == "mark":
                    mark_name = message.get("mark", {}).get("name", "")
                    logger.info(f"[{call_sid}] Received mark event at {get_timestamp_str()}: {mark_name}")
                    
                    # Structured log for mark event
                    mark_log = {
                        "event": "TWILIO_MARK_RECEIVED",
                        "call_sid": call_sid,
                        "timestamp": get_timestamp_str(),
                        "mark_name": mark_name
                    }
                    logger.info(f"STRUCTURED_LOG: {json.dumps(mark_log)}")
                    
                else:
                    logger.debug(f"[{call_sid}] Unhandled Twilio event at {get_timestamp_str()}: {event}")
                
                # Yield at the end of each loop iteration
                gevent.sleep(0)

            except TimeoutError:  # Or specific timeout exception for ws.receive
                 # No message received in timeout window, continue loop
                 logger.debug(f"[{call_sid}] Timeout receiving from Twilio at {get_timestamp_str()}")
                 gevent.sleep(0.01)
                 continue
            except json.JSONDecodeError:
                logger.error(f"[{call_sid}] Error decoding JSON from Twilio at {get_timestamp_str()}: {message_str}", exc_info=True)
                
                # Structured log for JSON error
                json_error_log = {
                    "event": "JSON_DECODE_ERROR",
                    "call_sid": call_sid,
                    "timestamp": get_timestamp_str(),
                    "message_length": len(message_str) if message_str else 0
                }
                logger.error(f"STRUCTURED_LOG: {json.dumps(json_error_log)}")
                
            except websocket.WebSocketConnectionClosedException:  # Error sending to OpenAI
                 logger.warning(f"[{call_sid}] OpenAI WS connection closed during send at {get_timestamp_str()}. Stopping forwarder.")
                 
                 # Structured log for connection closed
                 closed_log = {
                     "event": "OPENAI_WS_CLOSED",
                     "call_sid": call_sid,
                     "timestamp": get_timestamp_str(),
                     "total_processed_packets": media_packet_count
                 }
                 logger.warning(f"STRUCTURED_LOG: {json.dumps(closed_log)}")
                 
                 break
            except Exception as e:  # Catch errors from ws.receive or ws.send
                 if "closed" in str(e).lower():  # Crude check for closed connection on twilio_ws
                      logger.info(f"[{call_sid}] Twilio WS connection closed at {get_timestamp_str()}")
                      
                      # Structured log for connection closed
                      closed_log = {
                          "event": "TWILIO_WS_CLOSED",
                          "call_sid": call_sid,
                          "timestamp": get_timestamp_str(),
                          "total_processed_packets": media_packet_count
                      }
                      logger.info(f"STRUCTURED_LOG: {json.dumps(closed_log)}")
                      
                 else:
                      logger.error(f"[{call_sid}] Error in Twilio->OpenAI greenlet at {get_timestamp_str()}: {e}", exc_info=True)
                      
                      # Structured log for error
                      error_log = {
                          "event": "TWILIO_TO_OPENAI_ERROR",
                          "call_sid": call_sid,
                          "timestamp": get_timestamp_str(),
                          "error": str(e)
                      }
                      logger.error(f"STRUCTURED_LOG: {json.dumps(error_log)}")
                      
                 break  # Exit loop on significant errors

    except Exception as e:  # Catch errors in the greenlet's outer loop
        logger.error(f"[{call_sid}] Unhandled error in Twilio->OpenAI greenlet at {get_timestamp_str()}: {e}", exc_info=True)
        
        # Structured log for unhandled error
        error_log = {
            "event": "TWILIO_TO_OPENAI_UNHANDLED_ERROR",
            "call_sid": call_sid,
            "timestamp": get_timestamp_str(),
            "error": str(e)
        }
        logger.error(f"STRUCTURED_LOG: {json.dumps(error_log)}")
        
    finally:
        # Calculate total duration
        greenlet_end_time = time.time()
        greenlet_duration_ms = (greenlet_end_time - greenlet_start_time) * 1000
        
        logger.info(f"[{call_sid}] Twilio->OpenAI forwarding greenlet finished at {get_timestamp_str()} (total duration: {greenlet_duration_ms:.2f}ms)")
        
        # Structured log for greenlet completion
        completion_log = {
            "event": "TWILIO_TO_OPENAI_COMPLETED",
            "call_sid": call_sid,
            "timestamp": get_timestamp_str(),
            "total_duration_ms": greenlet_duration_ms,
            "total_processed_packets": media_packet_count,
            "speech_packets": speech_packet_count,
            "silence_packets": silence_packet_count
        }
        logger.info(f"STRUCTURED_LOG: {json.dumps(completion_log)}")


def process_openai_responses_and_interact_sync(openai_ws, twilio_ws, call_sid, stream_sid_container, frontline_agent, run_context_data):
    """
    Receives from OpenAI (sync), forwards audio to Twilio (sync), interacts with Agent (sync).
    Runs in a greenlet.
    
    Args:
        openai_ws: WebSocket connection to OpenAI
        twilio_ws: WebSocket connection to Twilio
        call_sid: The Twilio call SID
        stream_sid_container: Mutable list containing the stream SID
        frontline_agent: The frontline agent instance
        run_context_data: Context data for tools and agent
    """
    # websocket module is now imported at the top level
    logger.info(f"[{call_sid}] Starting OpenAI->Twilio/Agent processing greenlet")
    
    # Define event types to log with different verbosity
    LOG_EVENT_TYPES = [
        # Session events
        'session.created', 'session.updated', 'session.error', 'session.success',
        
        # Speech and silence events
        'speech.started', 'speech.finished', 'speech.segmentation', 'silence_detected',
        
        # Voice Activity Detection (VAD) events
        'input_audio_buffer.speech_started', 'input_audio_buffer.speech_stopped',
        
        # Turn-taking and interruption events
        'turn.yielded', 'session.interrupted', 'session.event',
        
        # New events to watch for
        'response.interrupted', 'turn.interrupt', 'speech.interrupted',
        'interrupted', 'interrupt'
    ]
    
    # Flag to track if we've already sent a greeting
    greeting_sent = False
    
    try:
        while True:
            try:
                # Check if Twilio connection is still alive before receiving
                if not twilio_ws or not hasattr(twilio_ws, 'connected') or not twilio_ws.connected:
                     logger.warning(f"[{call_sid}] Twilio WS no longer connected at {get_timestamp_str()}. Stopping OpenAI processor.")
                     break

                # Blocking receive from OpenAI with timeout - add timing
                receive_start_time = time.time()
                receive_start_timestamp = get_timestamp_str()
                
                # Log that we're about to receive (occasionally for high volume messages)
                if not hasattr(process_openai_responses_and_interact_sync, "_receive_count"):
                    process_openai_responses_and_interact_sync._receive_count = 0
                process_openai_responses_and_interact_sync._receive_count += 1
                
                if process_openai_responses_and_interact_sync._receive_count % 50 == 0:
                    logger.debug(f"[{call_sid}] About to receive from OpenAI WS at {receive_start_timestamp} (#{process_openai_responses_and_interact_sync._receive_count})")
                
                # Perform the blocking receive
                message_str = openai_ws.recv()  # websocket-client uses settimeout for recv
                
                # Calculate time spent in blocking receive
                receive_end_time = time.time()
                receive_duration_ms = (receive_end_time - receive_start_time) * 1000
                
                # Log receive timing occasionally
                if process_openai_responses_and_interact_sync._receive_count % 50 == 0:
                    logger.debug(f"[{call_sid}] OpenAI WS receive took {receive_duration_ms:.2f}ms")
                
                if not message_str:  # Connection likely closed cleanly
                    logger.info(f"[{call_sid}] OpenAI WS recv returned empty at {get_timestamp_str()}, likely closed.")
                    break

                # Process received message with timing
                process_start_time = time.time()
                payload = json.loads(message_str)
                event_type = payload.get("type")
                
                # Enhanced logging for all event types
                if event_type not in ["response.audio.delta", "transcript.delta"]:
                    # These events are less frequent, so log them all with timestamps
                    logger.info(f"[{call_sid}] OpenAI Event Received - Type: '{event_type}' at {get_timestamp_str()}")
                    
                    # Add structured logging for non-audio events
                    try:
                        event_log = {
                            "event": "OPENAI_EVENT",
                            "call_sid": call_sid,
                            "timestamp": time.time(),
                            "timestamp_str": get_timestamp_str(),
                            "event_type": event_type,
                            "receive_duration_ms": receive_duration_ms
                        }
                        logger.info(f"STRUCTURED_LOG: {json.dumps(event_log)}")
                    except Exception as log_err:
                        logger.error(f"[{call_sid}] Error creating structured log: {log_err}")
                else:
                    # For high-volume events, just log occasionally
                    if event_type == "response.audio.delta" and process_openai_responses_and_interact_sync._audio_chunk_count % 50 == 0:
                        logger.debug(f"[{call_sid}] Audio delta received #{process_openai_responses_and_interact_sync._audio_chunk_count}")
                    elif event_type == "transcript.delta" and process_openai_responses_and_interact_sync._receive_count % 20 == 0:
                        logger.debug(f"[{call_sid}] Transcript delta received (#{process_openai_responses_and_interact_sync._receive_count})")
                
                # Detect session creation/update to:
                # 1. Send second session update with tools only (if needed)
                # 2. Trigger proactive greeting
                if (event_type == "session.created" or event_type == "session.updated"):
                    logger.info(f"[{call_sid}] Session established event '{event_type}' received at {get_timestamp_str()}")
                    
                    # TEMPORARILY DISABLED: Skipping second session.update with tools
                    # This section would normally send tools in a second update after session is established
                    pending_tools = None  # Force to None to disable tools
                    
                    # Log that we're skipping tools intentionally
                    logger.info(f"[{call_sid}] SKIPPING second session.update with tools (disabled by user request)")
                    
                    # Add structured log entry for debugging
                    skip_tools_log = {
                        "event": "TOOLS_UPDATE_SKIPPED",
                        "call_sid": call_sid,
                        "timestamp": get_timestamp_str(),
                        "reason": "User requested to disable tools due to API issues"
                    }
                    logger.info(f"STRUCTURED_LOG: {json.dumps(skip_tools_log)}")
                    
                    # Make sure there are no pending tools in context
                    if "pending_tools" in run_context_data:
                        run_context_data["pending_tools"] = None
                            
                    # Proceed with greeting if not sent yet
                    if not greeting_sent:
                        logger.info(f"[{call_sid}] Proceeding with initial greeting.")
                    
                    try:
                        # Define greeting text
                        greeting_text = "Hello! Welcome to Red Bar Sushi. My name is Shimmer. How can I help you today?"
                        logger.info(f"[{call_sid}] Sending initial greeting text for TTS: '{greeting_text}'")
                        
                        # Step 1: Create conversation item with greeting text
                        greeting_item_payload = {
                            "type": "conversation.item.create",
                            "item": {
                                "type": "message",
                                "role": "assistant",
                                "content": [{"type": "text", "text": greeting_text}]
                            }
                        }
                        openai_ws.send(json.dumps(greeting_item_payload))
                        
                        # Step 2: Create response to trigger TTS
                        greeting_response_payload = {
                            "type": "response.create",
                            "response": {"modalities": ["audio", "text"]}
                        }
                        openai_ws.send(json.dumps(greeting_response_payload))
                        
                        # Mark greeting as sent
                        greeting_sent = True
                        logger.info(f"[{call_sid}] Initial greeting TTS triggered successfully.")
                    except Exception as greeting_err:
                        logger.error(f"[{call_sid}] Error sending initial greeting: {greeting_err}", exc_info=True)
                        
                    # Yield control to allow other greenlets to run
                    gevent.sleep(0)

                # 1. Handle Audio Output from OpenAI (TTS)
                if event_type == "response.audio.delta" and payload.get("delta"):
                    # Quick yield before audio handling to allow speech detection to run
                    # This is critical for better interruption detection
                    gevent.sleep(0)
                    
                    if stream_sid_container[0]:
                         # Log audio chunk for debugging and track stream state
                         audio_start_time = time.time()
                         
                         # Initialize or increment audio chunk counter
                         if hasattr(process_openai_responses_and_interact_sync, "_audio_chunk_count"):
                             process_openai_responses_and_interact_sync._audio_chunk_count += 1
                         else:
                             process_openai_responses_and_interact_sync._audio_chunk_count = 1
                             # Log the first chunk with high visibility
                             logger.info(f"[{call_sid}] 🔊 AUDIO STREAM STARTED: First chunk at {get_timestamp_str()}")
                         
                         chunk_num = process_openai_responses_and_interact_sync._audio_chunk_count
                         
                         # Log more frequently for better visibility of audio streaming
                         if chunk_num % 20 == 0:
                             logger.info(f"[{call_sid}] 🔊 Sending audio chunk #{chunk_num} at {get_timestamp_str()}")
                         
                         # Log every chunk during debugging (but at DEBUG level to avoid log floods)
                         logger.debug(f"[{call_sid}] Audio chunk #{chunk_num} processing started")
                             
                         # Create and send the Twilio media message
                         twilio_media_message = {
                             "event": "media",
                             "streamSid": stream_sid_container[0],
                             "media": {"payload": payload["delta"]}
                         }
                         
                         # Send audio chunk to Twilio with timing
                         send_start = time.time()
                         twilio_ws.send(json.dumps(twilio_media_message))  # Blocking send
                         send_duration_ms = (time.time() - send_start) * 1000
                         
                         # Log timing info for audio chunks occasionally (helps identify slow sends)
                         if chunk_num % 50 == 0:
                             logger.info(f"[{call_sid}] Audio chunk #{chunk_num} sent in {send_duration_ms:.2f}ms")
                             
                             # Add structured logging for audio chunk statistics
                             try:
                                 audio_stats = {
                                     "event": "AUDIO_CHUNK_STATS",
                                     "call_sid": call_sid,
                                     "timestamp": time.time(),
                                     "timestamp_str": get_timestamp_str(),
                                     "chunk_number": chunk_num,
                                     "send_duration_ms": send_duration_ms
                                 }
                                 logger.info(f"STRUCTURED_LOG: {json.dumps(audio_stats)}")
                             except Exception as log_err:
                                 logger.error(f"[{call_sid}] Error creating structured log: {log_err}")
                         
                         # CRITICAL: Yield control after EVERY audio chunk to allow interrupt detection
                         # Use longer sleep duration (0.002s) for better cooperative multitasking
                         # This gives enough time for interrupt detection without noticeable delay
                         yield_start = time.time()
                         gevent.sleep(0.002)
                         
                         # Log yields periodically to verify cooperative multitasking
                         if chunk_num % 20 == 0:
                             logger.debug(f"[{call_sid}] Yielded for {(time.time() - yield_start) * 1000:.2f}ms after chunk #{chunk_num}")
                         
                         # Add extra yields every X chunks to ensure responsiveness
                         if chunk_num % 10 == 0:
                             # Log before longer yield
                             if chunk_num % 20 == 0:
                                 logger.debug(f"[{call_sid}] Extra yield at chunk #{chunk_num}")
                             # Longer yield every 10 chunks
                             gevent.sleep(0.005)
                         
                         # Track overall processing time for this audio chunk
                         total_chunk_time = (time.time() - audio_start_time) * 1000
                         if chunk_num % 50 == 0:
                             logger.info(f"[{call_sid}] Total processing time for chunk #{chunk_num}: {total_chunk_time:.2f}ms")
                    else:
                         timestamp_str = get_timestamp_str()
                         logger.warning(f"[{call_sid}] ❌ Stream SID not available for sending audio delta at {timestamp_str}")
                         
                         # Add structured logging for the error
                         try:
                             error_log = {
                                 "event": "AUDIO_STREAM_ERROR",
                                 "call_sid": call_sid,
                                 "timestamp": time.time(),
                                 "timestamp_str": timestamp_str,
                                 "error": "Missing stream_sid"
                             }
                             logger.warning(f"STRUCTURED_LOG: {json.dumps(error_log)}")
                         except Exception as log_err:
                             logger.error(f"[{call_sid}] Error creating structured log: {log_err}")

                # 2. Handle Final User Transcript 
                elif event_type == "conversation.item.input_audio_transcription.completed":  # Verified type
                    transcript = payload.get("transcript", "")
                    logger.info(f"[{call_sid}] Final User Transcript: '{transcript}'")
                    
                    # ENHANCED STRUCTURED LOGGING - Conversation Turn (User)
                    try:
                        conversation_log = {
                            "event": "CONVERSATION_TURN",
                            "call_sid": call_sid,
                            "timestamp": time.time(),
                            "speaker": "USER",
                            "transcript": transcript,
                            "transcript_length": len(transcript) if transcript else 0
                        }
                        logger.info(f"STRUCTURED_LOG: {json.dumps(conversation_log)}")
                    except Exception as log_err:
                        logger.error(f"[{call_sid}] Error creating structured log: {log_err}")
                    
                    if transcript and frontline_agent:
                        try:
                            # --- AGENT INTEGRATION (SYNCHRONOUS) ---
                            logger.info(f"[{call_sid}] Processing transcript with agent...")
                            # Assuming process_voice_input is now synchronous or gevent-compatible
                            agent_response_text = frontline_agent.process_voice_input(call_sid, transcript, context=run_context_data) 
                            logger.info(f"[{call_sid}] Agent response: '{agent_response_text}'")
                            
                            # ENHANCED STRUCTURED LOGGING - Conversation Turn (Assistant)
                            try:
                                # Get current FSM state if possible for context
                                current_state = "unknown"
                                try:
                                    if hasattr(frontline_agent, "fsm_orchestrator") and frontline_agent.fsm_orchestrator:
                                        fsm_state = frontline_agent.fsm_orchestrator.get_current_state(call_sid)
                                        current_state = fsm_state.value if hasattr(fsm_state, "value") else str(fsm_state)
                                except Exception as state_err:
                                    logger.debug(f"[{call_sid}] Could not get FSM state: {state_err}")
                                
                                assistant_log = {
                                    "event": "CONVERSATION_TURN",
                                    "call_sid": call_sid,
                                    "timestamp": time.time(),
                                    "speaker": "ASSISTANT",
                                    "text_response": agent_response_text,
                                    "response_length": len(agent_response_text) if agent_response_text else 0,
                                    "fsm_state": current_state
                                }
                                logger.info(f"STRUCTURED_LOG: {json.dumps(assistant_log)}")
                            except Exception as log_err:
                                logger.error(f"[{call_sid}] Error creating structured log: {log_err}")

                            if agent_response_text:
                                # --- TTS Trigger (SYNCHRONOUS) ---
                                # Step 1: Create conversation item
                                tts_item_payload = {
                                    "type": "conversation.item.create",
                                    "item": {
                                        "type": "message",
                                        "role": "assistant",
                                        "content": [{"type": "text", "text": agent_response_text}]  # Updated type as per API error message
                                    }
                                }
                                logger.info(f"[{call_sid}] Sending TTS item to OpenAI")
                                openai_ws.send(json.dumps(tts_item_payload))

                                # Step 2: Create response
                                tts_response_payload = {
                                    "type": "response.create",
                                    "response": {"modalities": ["audio", "text"]}
                                }
                                logger.info(f"[{call_sid}] Sending response.create for TTS")
                                openai_ws.send(json.dumps(tts_response_payload))

                        except Exception as agent_err:
                             logger.error(f"[{call_sid}] Error processing transcript with agent: {agent_err}", exc_info=True)
                             # Send TTS error message to user
                             try:
                                error_message = "I'm sorry, I'm having trouble understanding. Could you please try again?"
                                openai_ws.send(json.dumps({
                                    "type": "conversation.item.create",
                                    "item": {
                                        "type": "message",
                                        "role": "assistant",
                                        "content": [{"type": "text", "text": error_message}]
                                    }
                                }))
                                openai_ws.send(json.dumps({
                                    "type": "response.create",
                                    "response": {"modalities": ["audio", "text"]}
                                }))
                             except Exception as recovery_err:
                                logger.error(f"[{call_sid}] Failed to send error message: {recovery_err}")

                # 3. Handle Tool Calls
                elif event_type == "tool_calls":  # Verified type
                    tool_calls_data = payload.get("tool_calls", [])
                    logger.info(f"[{call_sid}] Received tool_calls: {tool_calls_data}")
                    tool_outputs = []
                    
                    for tc in tool_calls_data:
                        tool_call_id = tc["id"]
                        function_name = tc["function"]["name"]
                        arguments_raw = tc["function"]["arguments"]
                        
                        # ENHANCED STRUCTURED LOGGING - Tool Call Requested
                        try:
                            tool_request_log = {
                                "event": "TOOL_CALL_REQUESTED",
                                "call_sid": call_sid,
                                "timestamp": time.time(),
                                "tool_call_id": tool_call_id,
                                "tool_name": function_name,
                                "tool_arguments_raw": arguments_raw
                            }
                            logger.info(f"STRUCTURED_LOG: {json.dumps(tool_request_log)}")
                        except Exception as log_err:
                            logger.error(f"[{call_sid}] Error creating structured log: {log_err}")
                        
                        try:
                             function_args = json.loads(arguments_raw)
                        except json.JSONDecodeError:
                             logger.error(f"[{call_sid}] Failed to parse tool args for {function_name}: {arguments_raw}")
                             error_output = {"error": "Invalid arguments JSON"}
                             tool_outputs.append({"tool_call_id": tool_call_id, "output": json.dumps(error_output)})
                             
                             # Log tool execution error
                             try:
                                 tool_error_log = {
                                     "event": "TOOL_CALL_EXECUTED",
                                     "call_sid": call_sid,
                                     "timestamp": time.time(),
                                     "tool_call_id": tool_call_id,
                                     "tool_name": function_name,
                                     "status": "error",
                                     "error": "Invalid arguments JSON",
                                     "tool_result": error_output
                                 }
                                 logger.info(f"STRUCTURED_LOG: {json.dumps(tool_error_log)}")
                             except Exception as log_err:
                                 logger.error(f"[{call_sid}] Error creating structured log: {log_err}")
                                 
                             continue

                        logger.info(f"[{call_sid}] Executing tool '{function_name}' with args: {function_args}")
                        try:
                             start_time = time.time()
                             # --- TOOL EXECUTION (SYNCHRONOUS) ---
                             tool_result = execute_rbs_tool_sync(function_name, function_args, run_context_data) 
                             duration_ms = (time.time() - start_time) * 1000
                             
                             # Add tool output for OpenAI
                             tool_outputs.append({"tool_call_id": tool_call_id, "output": json.dumps(tool_result)})
                             
                             # ENHANCED STRUCTURED LOGGING - Tool Call Executed Successfully
                             try:
                                 # Create a safe result for logging (potentially truncate large results)
                                 safe_result = tool_result
                                 result_str = json.dumps(tool_result)
                                 if len(result_str) > 1000:  # If result is too large
                                     # Truncate and indicate truncation
                                     safe_result = {"_truncated_for_logging": True, 
                                                    "original_size": len(result_str),
                                                    "summary": str(tool_result)[:500] + "..."}
                                 
                                 tool_success_log = {
                                     "event": "TOOL_CALL_EXECUTED",
                                     "call_sid": call_sid,
                                     "timestamp": time.time(),
                                     "tool_call_id": tool_call_id,
                                     "tool_name": function_name,
                                     "status": "success",
                                     "duration_ms": duration_ms,
                                     "tool_arguments": function_args,
                                     "tool_result": safe_result
                                 }
                                 logger.info(f"STRUCTURED_LOG: {json.dumps(tool_success_log)}")
                             except Exception as log_err:
                                 logger.error(f"[{call_sid}] Error creating structured log: {log_err}")
                                 
                        except Exception as tool_exec_err:
                             logger.error(f"[{call_sid}] Error executing tool {function_name}: {tool_exec_err}", exc_info=True)
                             error_output = {"error": str(tool_exec_err)}
                             tool_outputs.append({"tool_call_id": tool_call_id, "output": json.dumps(error_output)})
                             
                             # ENHANCED STRUCTURED LOGGING - Tool Call Execution Failed
                             try:
                                 tool_error_log = {
                                     "event": "TOOL_CALL_EXECUTED",
                                     "call_sid": call_sid,
                                     "timestamp": time.time(),
                                     "tool_call_id": tool_call_id,
                                     "tool_name": function_name,
                                     "status": "error",
                                     "error": str(tool_exec_err),
                                     "tool_arguments": function_args,
                                     "tool_result": error_output
                                 }
                                 logger.info(f"STRUCTURED_LOG: {json.dumps(tool_error_log)}")
                             except Exception as log_err:
                                 logger.error(f"[{call_sid}] Error creating structured log: {log_err}")

                    if tool_outputs:
                        # Send results back (Step 1 of Tool Flow Part 2)
                        for tool_output in tool_outputs:
                            # Each tool result needs its own conversation.item.create event
                            tool_results_item = {
                                "type": "conversation.item.create", 
                                "item": {
                                    "type": "function_call_output", 
                                    "call_id": tool_output["tool_call_id"],
                                    "output": tool_output["output"] 
                                }
                            }
                            logger.info(f"[{call_sid}] Sending tool result for {tool_output['tool_call_id']}")
                            openai_ws.send(json.dumps(tool_results_item))
                        
                        # Request a single response after all tool results
                        response_trigger = {
                            "type": "response.create",
                            "response": {"modalities": ["audio", "text"]}
                        }
                        logger.info(f"[{call_sid}] Sending response.create after tool results")
                        openai_ws.send(json.dumps(response_trigger))

                # 4. Handle Session Errors
                elif event_type == "error" or event_type == "session.error" or "error" in payload:
                     error_details = payload.get("error", payload)
                     logger.error(f"[{call_sid}] OpenAI Session Error Received: {error_details}")
                     # Send TTS error message to user
                     try:
                        error_message = "I'm sorry, I'm experiencing technical difficulties. Please try again in a moment."
                        openai_ws.send(json.dumps({
                            "type": "conversation.item.create",
                            "item": {
                                "type": "message",
                                "role": "assistant",
                                "content": [{"type": "text", "text": error_message}]
                            }
                        }))
                        openai_ws.send(json.dumps({
                            "type": "response.create",
                            "response": {"modalities": ["audio", "text"]}
                        }))
                        # Give TTS time to complete
                        gevent.sleep(3)
                     except Exception as e:
                        logger.error(f"[{call_sid}] Failed to send error message: {e}")
                     
                     try:
                        if twilio_ws.connected:
                            # Use no-argument close to avoid state errors
                            twilio_ws.close()
                     except Exception as close_err:
                          logger.error(f"[{call_sid}] Error closing Twilio WS after OpenAI error: {close_err}")
                     break # Exit loop

                # Log other events for debugging
                elif event_type in LOG_EVENT_TYPES:
                     logger.info(f"[{call_sid}] OpenAI Event Logged - Type: '{event_type}'")
                
                # For VAD detection events - this is CRITICAL for interruption handling
                # When we detect speech during TTS, we need to:
                # 1. Clear the Twilio media buffer immediately (stop audio playback)
                # 2. Tell OpenAI to cancel its current response generation
                # 3. Allow the new speech to be processed
                # This provides the most responsive interruption experience
                elif event_type == "input_audio_buffer.speech_started":
                    # Use CRITICAL level for high visibility of speech detection events
                    timestamp_str = get_timestamp_str()
                    logger.critical(f"[{call_sid}] 🔴 VAD DETECTION: Speech start detected at {timestamp_str}")
                    
                    # ENHANCED STRUCTURED LOGGING - VAD Speech Start - Use CRITICAL level for maximum visibility
                    try:
                        is_during_tts = hasattr(process_openai_responses_and_interact_sync, "_audio_chunk_count")
                        chunk_count = process_openai_responses_and_interact_sync._audio_chunk_count if is_during_tts else 0
                        
                        vad_log = {
                            "event": "VAD_DETECTION",
                            "call_sid": call_sid,
                            "timestamp": time.time(),
                            "timestamp_str": timestamp_str,
                            "vad_type": "speech_started",
                            "is_during_tts": is_during_tts,
                            "audio_chunk_count": chunk_count if is_during_tts else None
                        }
                        logger.critical(f"STRUCTURED_LOG: {json.dumps(vad_log)}")
                    except Exception as log_err:
                        logger.error(f"[{call_sid}] Error creating structured log: {log_err}")
                    
                    # 1. Log interruption detection
                    if hasattr(process_openai_responses_and_interact_sync, "_audio_chunk_count"):
                        interrupt_detect_time = time.time()
                        interrupt_detect_timestamp = get_timestamp_str()
                        logger.critical(f"[{call_sid}] 🚨 INTERRUPTION DETECTED: Speech during TTS at {interrupt_detect_timestamp} " +
                                     f"(audio chunk #{process_openai_responses_and_interact_sync._audio_chunk_count})")
                        
                        # ENHANCED STRUCTURED LOGGING - Interruption Detected - Use CRITICAL level
                        try:
                            interruption_log = {
                                "event": "INTERRUPTION_DETECTED",
                                "call_sid": call_sid,
                                "timestamp": interrupt_detect_time,
                                "timestamp_str": interrupt_detect_timestamp,
                                "audio_chunk_count": process_openai_responses_and_interact_sync._audio_chunk_count
                            }
                            logger.critical(f"STRUCTURED_LOG: {json.dumps(interruption_log)}")
                        except Exception as log_err:
                            logger.error(f"[{call_sid}] Error creating structured log: {log_err}")
                        
                        # 2. Immediately clear Twilio's audio buffer
                        if stream_sid_container[0]:
                            before_clear_time = time.time()
                            before_clear_timestamp = get_timestamp_str()
                            logger.critical(f"[{call_sid}] ⏳ BEFORE TWILIO CLEAR: About to send 'clear' at {before_clear_timestamp}")
                            
                            # Log before sending clear
                            try:
                                before_clear_log = {
                                    "event": "INTERRUPTION_ACTION_START",
                                    "call_sid": call_sid,
                                    "timestamp": before_clear_time,
                                    "timestamp_str": before_clear_timestamp,
                                    "action": "twilio_clear_start",
                                    "stream_sid": stream_sid_container[0]
                                }
                                logger.critical(f"STRUCTURED_LOG: {json.dumps(before_clear_log)}")
                            except Exception as log_err:
                                logger.error(f"[{call_sid}] Error creating structured log: {log_err}")
                                
                            clear_twilio_payload = {
                                "event": "clear", 
                                "streamSid": stream_sid_container[0]
                            }
                            
                            try:
                                # Send the clear message and time it
                                clear_send_start = time.time()
                                twilio_ws.send(json.dumps(clear_twilio_payload))
                                clear_send_end = time.time()
                                clear_duration_ms = (clear_send_end - clear_send_start) * 1000
                                
                                # Critical: Yield here to allow other operations to proceed
                                # This small sleep significantly improves cooperative multitasking
                                # during the interruption sequence
                                gevent.sleep(0.001)
                                
                                after_clear_timestamp = get_timestamp_str()
                                logger.critical(f"[{call_sid}] ✅ AFTER TWILIO CLEAR: Sent 'clear' at {after_clear_timestamp} (took {clear_duration_ms:.2f}ms)")
                                
                                # ENHANCED STRUCTURED LOGGING - Clear Event Sent - Use CRITICAL level
                                try:
                                    clear_log = {
                                        "event": "INTERRUPTION_ACTION_COMPLETE",
                                        "call_sid": call_sid,
                                        "timestamp": clear_send_end,
                                        "timestamp_str": after_clear_timestamp,
                                        "action": "twilio_clear_complete",
                                        "success": True,
                                        "duration_ms": clear_duration_ms,
                                        "stream_sid": stream_sid_container[0]
                                    }
                                    logger.critical(f"STRUCTURED_LOG: {json.dumps(clear_log)}")
                                except Exception as log_err:
                                    logger.error(f"[{call_sid}] Error creating structured log: {log_err}")
                            except Exception as e:
                                after_clear_timestamp = get_timestamp_str()
                                logger.error(f"[{call_sid}] ❌ TWILIO CLEAR FAILED: Error at {after_clear_timestamp}: {e}")
                                
                                # Log failure with CRITICAL level
                                try:
                                    clear_failure_log = {
                                        "event": "INTERRUPTION_ACTION_FAILED",
                                        "call_sid": call_sid,
                                        "timestamp": time.time(),
                                        "timestamp_str": after_clear_timestamp,
                                        "action": "twilio_clear_failed",
                                        "success": False,
                                        "error": str(e)
                                    }
                                    logger.critical(f"STRUCTURED_LOG: {json.dumps(clear_failure_log)}")
                                except Exception as log_err:
                                    logger.error(f"[{call_sid}] Error creating structured log: {log_err}")
                        
                        # 3. Cancel OpenAI response generation 
                        cancel_openai_payload = {
                            "type": "response.cancel"
                            # No response_id needed as we're canceling the current response
                        }
                        
                        before_cancel_time = time.time()
                        before_cancel_timestamp = get_timestamp_str()
                        logger.critical(f"[{call_sid}] ⏳ BEFORE OPENAI CANCEL: About to send 'response.cancel' at {before_cancel_timestamp}")
                        
                        # Log before sending cancel
                        try:
                            before_cancel_log = {
                                "event": "INTERRUPTION_ACTION_START",
                                "call_sid": call_sid,
                                "timestamp": before_cancel_time,
                                "timestamp_str": before_cancel_timestamp,
                                "action": "openai_cancel_start"
                            }
                            logger.critical(f"STRUCTURED_LOG: {json.dumps(before_cancel_log)}")
                        except Exception as log_err:
                            logger.error(f"[{call_sid}] Error creating structured log: {log_err}")
                            
                        try:
                            if openai_ws and hasattr(openai_ws, 'connected') and openai_ws.connected:
                                # Send the cancel message and time it
                                cancel_send_start = time.time()
                                openai_ws.send(json.dumps(cancel_openai_payload))
                                cancel_send_end = time.time()
                                cancel_duration_ms = (cancel_send_end - cancel_send_start) * 1000
                                
                                # Critical: Yield again after sending cancel
                                # This helps ensure that the interruption handling
                                # doesn't block other parts of the system
                                gevent.sleep(0.001)
                                
                                after_cancel_timestamp = get_timestamp_str()
                                logger.critical(f"[{call_sid}] ✅ AFTER OPENAI CANCEL: Sent 'response.cancel' at {after_cancel_timestamp} (took {cancel_duration_ms:.2f}ms)")
                                
                                # Reset audio chunk counter and other tracking state
                                # IMPORTANT: Ensure ALL state variables related to TTS are reset
                                process_openai_responses_and_interact_sync._audio_chunk_count = 0
                                if hasattr(process_openai_responses_and_interact_sync, "_is_speaking"):
                                    process_openai_responses_and_interact_sync._is_speaking = False
                                    
                                # Reset any additional VAD state variables that might exist
                                for attr_name in ['_speaking_state', '_vad_state', '_speech_active']:
                                    if hasattr(process_openai_responses_and_interact_sync, attr_name):
                                        setattr(process_openai_responses_and_interact_sync, attr_name, False)
                                        logger.debug(f"[{call_sid}] Reset speech state variable {attr_name}")
                                
                                # ENHANCED STRUCTURED LOGGING - Cancel Event Sent - Use CRITICAL level
                                try:
                                    cancel_log = {
                                        "event": "INTERRUPTION_ACTION_COMPLETE",
                                        "call_sid": call_sid,
                                        "timestamp": cancel_send_end,
                                        "timestamp_str": after_cancel_timestamp,
                                        "action": "openai_cancel_complete",
                                        "success": True,
                                        "duration_ms": cancel_duration_ms
                                    }
                                    logger.critical(f"STRUCTURED_LOG: {json.dumps(cancel_log)}")
                                except Exception as log_err:
                                    logger.error(f"[{call_sid}] Error creating structured log: {log_err}")
                        except Exception as e:
                            after_cancel_timestamp = get_timestamp_str()
                            logger.error(f"[{call_sid}] ❌ OPENAI CANCEL FAILED: Error at {after_cancel_timestamp}: {e}")
                            
                            # Log failure with CRITICAL level
                            try:
                                cancel_failure_log = {
                                    "event": "INTERRUPTION_ACTION_FAILED",
                                    "call_sid": call_sid,
                                    "timestamp": time.time(),
                                    "timestamp_str": after_cancel_timestamp,
                                    "action": "openai_cancel_failed",
                                    "success": False,
                                    "error": str(e)
                                }
                                logger.critical(f"STRUCTURED_LOG: {json.dumps(cancel_failure_log)}")
                            except Exception as log_err:
                                logger.error(f"[{call_sid}] Error creating structured log: {log_err}")
                                
                        # Add summary of complete interruption sequence with timing information
                        interruption_total_time = time.time() - interrupt_detect_time
                        logger.critical(f"[{call_sid}] 🔄 INTERRUPTION SEQUENCE COMPLETE: Total time {interruption_total_time*1000:.2f}ms")
                        
                        try:
                            interruption_summary = {
                                "event": "INTERRUPTION_SEQUENCE_COMPLETE",
                                "call_sid": call_sid,
                                "timestamp": time.time(),
                                "timestamp_str": get_timestamp_str(),
                                "total_duration_ms": interruption_total_time * 1000,
                                "detection_timestamp": interrupt_detect_timestamp
                            }
                            logger.critical(f"STRUCTURED_LOG: {json.dumps(interruption_summary)}")
                        except Exception as log_err:
                            logger.error(f"[{call_sid}] Error creating structured log: {log_err}")
                    
                elif event_type == "input_audio_buffer.speech_stopped":
                    timestamp_str = get_timestamp_str()
                    logger.warning(f"[{call_sid}] 🟢 VAD DETECTION: Speech stop detected at {timestamp_str}")
                    
                    # ENHANCED STRUCTURED LOGGING - VAD Speech Stop - Use WARNING level for consistency
                    try:
                        # Include detailed timing information
                        vad_log = {
                            "event": "VAD_DETECTION",
                            "call_sid": call_sid,
                            "timestamp": time.time(),
                            "timestamp_str": timestamp_str,
                            "vad_type": "speech_stopped"
                        }
                        logger.warning(f"STRUCTURED_LOG: {json.dumps(vad_log)}")
                    except Exception as log_err:
                        logger.error(f"[{call_sid}] Error creating structured log: {log_err}")
                # Check for turn-taking indicators - Use WARNING level for better visibility
                elif event_type == "turn.yielded":
                    timestamp_str = get_timestamp_str()
                    logger.warning(f"[{call_sid}] 🔄 TURN YIELDED: OpenAI yielded turn at {timestamp_str}")
                    
                    # Add structured logging for turn yielding
                    try:
                        turn_log = {
                            "event": "TURN_TAKING",
                            "call_sid": call_sid,
                            "timestamp": time.time(),
                            "timestamp_str": timestamp_str,
                            "action": "turn_yielded"
                        }
                        logger.warning(f"STRUCTURED_LOG: {json.dumps(turn_log)}")
                    except Exception as log_err:
                        logger.error(f"[{call_sid}] Error creating structured log: {log_err}")
                        
                elif event_type == "session.interrupted" or (event_type == "session.event" and payload.get("event", {}).get("type") == "interrupted"):
                    timestamp_str = get_timestamp_str()
                    logger.warning(f"[{call_sid}] 🛑 SESSION INTERRUPTED: OpenAI acknowledged interruption at {timestamp_str}")
                    
                    # Add structured logging for session interruption
                    try:
                        interrupt_log = {
                            "event": "SESSION_INTERRUPTED",
                            "call_sid": call_sid,
                            "timestamp": time.time(),
                            "timestamp_str": timestamp_str,
                            "event_type": event_type
                        }
                        logger.warning(f"STRUCTURED_LOG: {json.dumps(interrupt_log)}")
                    except Exception as log_err:
                        logger.error(f"[{call_sid}] Error creating structured log: {log_err}")
                    
                    # Reset audio chunk counter when interrupted
                    process_openai_responses_and_interact_sync._audio_chunk_count = 0
                    logger.warning(f"[{call_sid}] ✅ Reset audio chunk counter after interruption acknowledgment")

                # Enhanced yielding at the end of each loop iteration 
                # This ensures better cooperative multitasking between greenlets
                # A slightly longer sleep duration provides better interrupt handling
                # while still maintaining responsive performance
                gevent.sleep(0.001)

            except websocket.WebSocketTimeoutException:
                 # Expected during inactivity, just continue loop
                 current_time = time.time()
                 # Log timeouts occasionally to show the connection is still active
                 if not hasattr(process_openai_responses_and_interact_sync, "_timeout_count"):
                     process_openai_responses_and_interact_sync._timeout_count = 0
                 
                 process_openai_responses_and_interact_sync._timeout_count += 1
                 if process_openai_responses_and_interact_sync._timeout_count % 100 == 0:
                     logger.debug(f"[{call_sid}] WS timeout #{process_openai_responses_and_interact_sync._timeout_count} at {get_timestamp_str()} (normal)")
                 
                 # Add structured timeout logging periodically
                 if process_openai_responses_and_interact_sync._timeout_count % 500 == 0:
                     try:
                         timeout_log = {
                             "event": "WEBSOCKET_TIMEOUT",
                             "call_sid": call_sid,
                             "timestamp": current_time,
                             "timestamp_str": get_timestamp_str(),
                             "timeout_count": process_openai_responses_and_interact_sync._timeout_count
                         }
                         logger.debug(f"STRUCTURED_LOG: {json.dumps(timeout_log)}")
                     except Exception as log_err:
                         logger.error(f"[{call_sid}] Error creating structured log: {log_err}")
                 
                 # Yield control but continue processing
                 gevent.sleep(0.01)
                 continue
                 
            except json.JSONDecodeError:
                error_timestamp = get_timestamp_str()
                logger.error(f"[{call_sid}] Error decoding JSON from OpenAI at {error_timestamp}: {message_str}", exc_info=True)
                
                # Add structured logging for JSON decode errors
                try:
                    error_log = {
                        "event": "JSON_DECODE_ERROR",
                        "call_sid": call_sid,
                        "timestamp": time.time(),
                        "timestamp_str": error_timestamp,
                        "payload_length": len(message_str) if message_str else 0,
                        "payload_preview": message_str[:100] if message_str else "None"
                    }
                    logger.error(f"STRUCTURED_LOG: {json.dumps(error_log)}")
                except Exception as log_err:
                    logger.error(f"[{call_sid}] Error creating structured log: {log_err}")
                    
                # This isn't fatal - continue processing
                gevent.sleep(0.01)
                continue
                
            except websocket.WebSocketConnectionClosedException:
                 close_timestamp = get_timestamp_str()
                 logger.info(f"[{call_sid}] OpenAI WS connection closed at {close_timestamp}.")
                 
                 # Add structured logging for connection closure
                 try:
                     close_log = {
                         "event": "CONNECTION_CLOSED",
                         "call_sid": call_sid,
                         "timestamp": time.time(),
                         "timestamp_str": close_timestamp,
                         "connection": "openai",
                         "close_code": "WebSocketConnectionClosedException"
                     }
                     logger.info(f"STRUCTURED_LOG: {json.dumps(close_log)}")
                 except Exception as log_err:
                     logger.error(f"[{call_sid}] Error creating structured log: {log_err}")
                 
                 # This is fatal - exit the loop
                 break
                 
            except websocket.WebSocketException as ws_err:
                 # Handle other WebSocket-specific errors
                 error_timestamp = get_timestamp_str()
                 logger.warning(f"[{call_sid}] WebSocket error at {error_timestamp}: {ws_err}")
                 
                 # Add structured logging for general WebSocket errors
                 try:
                     error_log = {
                         "event": "WEBSOCKET_ERROR",
                         "call_sid": call_sid,
                         "timestamp": time.time(),
                         "timestamp_str": error_timestamp,
                         "error": str(ws_err),
                         "error_type": type(ws_err).__name__
                     }
                     logger.warning(f"STRUCTURED_LOG: {json.dumps(error_log)}")
                 except Exception as log_err:
                     logger.error(f"[{call_sid}] Error creating structured log: {log_err}")
                 
                 # Most WebSocket exceptions should be considered fatal
                 break
                 
            except Exception as e:  # Catch errors sending to twilio_ws or other processing
                 error_timestamp = get_timestamp_str()
                 if "closed" in str(e).lower():  # Crude check for connection closed
                      logger.info(f"[{call_sid}] Twilio WS connection closed during processing at {error_timestamp}.")
                      
                      # Add structured logging for connection closure
                      try:
                          close_log = {
                              "event": "CONNECTION_CLOSED",
                              "call_sid": call_sid,
                              "timestamp": time.time(),
                              "timestamp_str": error_timestamp,
                              "connection": "twilio",
                              "error_message": str(e)
                          }
                          logger.info(f"STRUCTURED_LOG: {json.dumps(close_log)}")
                      except Exception as log_err:
                          logger.error(f"[{call_sid}] Error creating structured log: {log_err}")
                          
                      # Connection closed is fatal
                      break
                      
                 elif "timeout" in str(e).lower():  # Handle timeout-like errors differently
                      logger.warning(f"[{call_sid}] Possible timeout error at {error_timestamp}: {e}")
                      
                      # Add structured logging for timeout errors
                      try:
                          timeout_error_log = {
                              "event": "TIMEOUT_ERROR",
                              "call_sid": call_sid,
                              "timestamp": time.time(),
                              "timestamp_str": error_timestamp,
                              "error": str(e),
                              "error_type": type(e).__name__
                          }
                          logger.warning(f"STRUCTURED_LOG: {json.dumps(timeout_error_log)}")
                      except Exception as log_err:
                          logger.error(f"[{call_sid}] Error creating structured log: {log_err}")
                      
                      # Timeout errors might be transient, try to continue
                      gevent.sleep(0.1)  # Slightly longer sleep
                      continue
                      
                 else:
                      # General processing error
                      logger.error(f"[{call_sid}] Error processing OpenAI message at {error_timestamp}: {e}", exc_info=True)
                      
                      # Add structured logging for general errors
                      try:
                          error_log = {
                              "event": "PROCESSING_ERROR",
                              "call_sid": call_sid,
                              "timestamp": time.time(),
                              "timestamp_str": error_timestamp,
                              "error": str(e),
                              "error_type": type(e).__name__
                          }
                          logger.error(f"STRUCTURED_LOG: {json.dumps(error_log)}")
                      except Exception as log_err:
                          logger.error(f"[{call_sid}] Error creating structured log: {log_err}")
                      
                      # Check if it seems like a fatal error or if we should continue
                      if "memory" in str(e).lower() or "critical" in str(e).lower() or "fatal" in str(e).lower():
                          logger.critical(f"[{call_sid}] FATAL ERROR detected at {error_timestamp}, terminating processing")
                          break
                      else:
                          # Try to continue for non-fatal errors
                          logger.warning(f"[{call_sid}] Attempting to continue after error at {error_timestamp}")
                          gevent.sleep(0.1)  # Longer sleep
                          continue
                 
                 # Fall through to here means we're breaking the loop
                 logger.warning(f"[{call_sid}] Exiting processing loop due to error at {error_timestamp}")
                 break

    except Exception as e:  # Catch errors in the greenlet's outer loop
        error_timestamp = get_timestamp_str()
        logger.error(f"[{call_sid}] Unhandled error in OpenAI->Twilio/Agent greenlet at {error_timestamp}: {e}", exc_info=True)
        
        # Add structured logging for fatal errors
        try:
            fatal_error_log = {
                "event": "FATAL_ERROR",
                "call_sid": call_sid,
                "timestamp": time.time(),
                "timestamp_str": error_timestamp,
                "error": str(e),
                "error_type": type(e).__name__
            }
            logger.error(f"STRUCTURED_LOG: {json.dumps(fatal_error_log)}")
        except Exception as log_err:
            logger.error(f"[{call_sid}] Error creating structured log: {log_err}")
    finally:
        end_timestamp = get_timestamp_str()
        logger.info(f"[{call_sid}] OpenAI->Twilio/Agent processing greenlet finished at {end_timestamp}.")
        
        # Log final statistics if available
        try:
            stats = {
                "event": "GREENLET_FINISHED",
                "call_sid": call_sid,
                "timestamp": time.time(),
                "timestamp_str": end_timestamp,
                "audio_chunks_processed": getattr(process_openai_responses_and_interact_sync, "_audio_chunk_count", 0),
                "receive_count": getattr(process_openai_responses_and_interact_sync, "_receive_count", 0),
                "timeout_count": getattr(process_openai_responses_and_interact_sync, "_timeout_count", 0)
            }
            logger.info(f"STRUCTURED_LOG: {json.dumps(stats)}")
        except Exception as log_err:
            logger.error(f"[{call_sid}] Error creating final statistics log: {log_err}")

def execute_rbs_tool_sync(function_name, args, run_context_data):
    """
    Executes the appropriate RedBarSushiAI tool SYNCHRONOUSLY.
    
    Args:
        function_name: The name of the function to execute
        args: The arguments to pass to the function
        run_context_data: Context data for the tool
        
    Returns:
        The result of the tool execution
    """
    call_sid = run_context_data.get('call_sid', 'unknown')
    logger.info(f"[{call_sid}] Attempting SYNC execution: Tool='{function_name}', Args={args}")

    try:
        # Import the tools registry if available
        try:
            from app.routes.voice.utils.tools_registry import execute_tool
            # Use the registry's execute_tool function if available
            return execute_tool(function_name, args, call_sid=call_sid)
        except ImportError:
            logger.warning(f"[{call_sid}] Tools registry not available, falling back to direct execution")
            
        # --- Direct Dispatch Method ---
        # Import agent factory to get specialized agents
        from app.agents.factory_with_orchestration import enhanced_agent_factory
            
        if function_name == "lookup_menu_item":
            menu_agent = enhanced_agent_factory.get_menu_agent()
            if not menu_agent:
                return {"error": "Menu agent not available"}
            return menu_agent.lookup_menu_item(item_name=args.get("item_name"))
            
        elif function_name == "add_item_to_cart":
            cart_agent = enhanced_agent_factory.get_cart_agent()
            if not cart_agent:
                return {"error": "Cart agent not available"}
            return cart_agent.add_to_cart(
                item_plu=args.get("plu"), 
                quantity=args.get("quantity", 1),
                modifiers=args.get("modifiers", [])
            )
            
        elif function_name == "get_current_cart":
            cart_agent = enhanced_agent_factory.get_cart_agent()
            if not cart_agent:
                return {"error": "Cart agent not available"}
            return cart_agent.get_cart(session_id=call_sid)
            
        elif function_name == "get_restaurant_info":
            # This could be handled directly if not requiring a specialized agent
            info_type = args.get("query", "general")
            # Sample restaurant information
            info = {
                "hours": "Monday-Friday: 11am-10pm, Saturday-Sunday: 12pm-11pm",
                "location": "123 Main Street, Anytown, USA",
                "phone": "(555) 123-4567",
                "delivery": "Available within 5 miles, $3.99 fee"
            }
            return {"info_type": info_type, "information": info.get(info_type, "Information not available")}
            
        else:
            logger.error(f"[{call_sid}] Unknown tool requested: {function_name}")
            return {"error": f"Unknown tool: {function_name}"}
            
    except Exception as e:
        logger.error(f"[{call_sid}] Error executing tool '{function_name}': {e}", exc_info=True)
        return {"error": f"Tool execution failed: {str(e)}"}

def send_heartbeats_sync(twilio_ws, call_sid):
    """
    Sends heartbeats to Twilio periodically. Runs in a greenlet.
    
    Args:
        twilio_ws: WebSocket connection to Twilio
        call_sid: The Twilio call SID
    """
    logger.info(f"[{call_sid}] Starting heartbeat greenlet.")
    count = 0
    try:
        while True:
            gevent.sleep(10)  # Wait 10 seconds
            count += 1
            if not twilio_ws or not hasattr(twilio_ws, 'connected') or not twilio_ws.connected:
                logger.info(f"[{call_sid}] Twilio WS closed. Stopping heartbeats.")
                break
            try:
                heartbeat = {"type": "heartbeat", "count": count, "timestamp": time.time()}
                twilio_ws.send(json.dumps(heartbeat))  # Blocking send
                # logger.debug(f"[{call_sid}] Sent heartbeat #{count}")
            except Exception as e:
                 logger.error(f"[{call_sid}] Error sending heartbeat: {e}")
                 break  # Stop on error
    except Exception as e:
         logger.error(f"[{call_sid}] Unhandled error in heartbeat greenlet: {e}", exc_info=True)
    finally:
        logger.info(f"[{call_sid}] Heartbeat greenlet finished.")

def get_tool_definitions_for_openai():
    """
    Return the tool definitions for OpenAI Realtime API in the proper format.
    
    This function defines the schema for tools that can be called by OpenAI's model.
    Enhanced descriptions to guide tool selection.
    
    Returns:
        List of tool definitions in the format expected by OpenAI
    """
    # Temporarily returning only one simple tool for testing
    return [
        {
            "type": "function",
            "function": {
                "name": "get_restaurant_info",
                "description": "Get information about the restaurant such as hours, location, or policies.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The specific information being requested (e.g., 'hours', 'location', 'phone', 'delivery')"
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    ]
    
    # Original full tool definitions - commented out for testing
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "lookup_menu_item",
                "description": "Use this tool only when a customer asks about a specific menu item's details (price, description, ingredients, availability). Input the customer's phrasing of the item name.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item_name": {
                            "type": "string",
                            "description": "The exact name or phrase the customer used to refer to the menu item"
                        }
                    },
                    "required": ["item_name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "add_item_to_cart",
                "description": "Use this tool only to add a confirmed item, quantity, and selected modifiers (identified by their PLUs) to the current order. Do not use this for inquiries or before confirming the item with the customer.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "plu": {
                            "type": "string",
                            "description": "The exact PLU code of the menu item (obtained from lookup_menu_item)"
                        },
                        "quantity": {
                            "type": "integer",
                            "description": "The quantity of the item to add (default: 1)",
                            "default": 1
                        },
                        "modifiers": {
                            "type": "array",
                            "description": "Modifiers to apply to the item (if any)",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "plu": {
                                        "type": "string",
                                        "description": "The exact PLU code of the modifier (obtained from lookup_menu_item)"
                                    },
                                    "quantity": {
                                        "type": "integer",
                                        "description": "The quantity of the modifier (default: 1)",
                                        "default": 1
                                    }
                                },
                                "required": ["plu"]
                            }
                        }
                    },
                    "required": ["plu"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_current_cart",
                "description": "Use this tool to retrieve the current contents and total price of the order, typically for summarization before confirmation or when the customer asks what's in their cart.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_restaurant_info",
                "description": "Use this tool to answer general questions about the restaurant like operating hours, address, phone number, or delivery policies. Do not use for menu-specific questions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The specific information being requested (e.g., 'hours', 'location', 'phone', 'delivery')"
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    ]
    """


def send_heartbeats(ws, call_sid, shutdown_event):
    """
    Sends periodic heartbeat messages to keep the WebSocket connection alive.
    """
    logger.info(f"[{call_sid}] Starting heartbeat greenlet")
    count = 0
    
    try:
        while not shutdown_event.is_set():
            gevent.sleep(10)  # Send heartbeat every 10 seconds
            if shutdown_event.is_set():
                break
                
            count += 1
            try:
                heartbeat = {
                    "type": "heartbeat",
                    "count": count,
                    "timestamp": time.time()
                }
                ws.send(json.dumps(heartbeat))
                logger.debug(f"[{call_sid}] Sent heartbeat #{count}")
            except Exception as e:
                logger.error(f"[{call_sid}] Heartbeat error: {e}")
                shutdown_event.set()
                break
                
    except Exception as e:
        logger.error(f"[{call_sid}] Error in heartbeat greenlet: {e}")
        logger.error(traceback.format_exc())
        shutdown_event.set()
    finally:
        logger.info(f"[{call_sid}] Heartbeat greenlet ended")


# Legacy route removed - all connections should now use /ws/media/<call_sid>
# TwiML must include the call_sid in the path parameter


@sock.route("/ws/realtime")
def handle_realtime(ws):
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
        ws.send(json.dumps({"error": "No CallSid provided"}))
        return
    
    logger.info(f"[{call_sid}] Starting realtime AI for call")
    
    # Send initial message
    ws.send(json.dumps({
        "type": "connected",
        "message": "Connected to realtime AI processor",
        "call_sid": call_sid
    }))
    
    # Audio processing queue and stop event
    audio_queue = Queue()
    stop_event = Event()
    
    # Audio receiver greenlet
    def receive_audio():
        while not stop_event.is_set():
            try:
                data = ws.receive(timeout=0.5)
                
                # If no data received, just continue
                if not data:
                    gevent.sleep(0.01)
                    continue
                
                # Check if it's a control message
                if isinstance(data, str):
                    try:
                        control = json.loads(data)
                        if control.get("type") == "end":
                            logger.info(f"[{call_sid}] Received end message for call")
                            stop_event.set()
                            break
                    except json.JSONDecodeError:
                        # Not JSON, treat as binary audio data
                        pass
                
                # Put data in queue for processing
                audio_queue.put(data)
            except TimeoutError:
                # Normal timeout during polling, continue
                continue
            except Exception as e:
                logger.error(f"[{call_sid}] Error receiving WebSocket message: {str(e)}")
                stop_event.set()
                break
    
    # Result sender greenlet
    def process_and_send_results():
        audio_chunks = []
        
        def get_next_audio_chunk():
            """Generator that yields audio chunks from the queue"""
            while not stop_event.is_set():
                try:
                    # Get data with timeout to regularly check stop_event
                    chunk = audio_queue.get(timeout=0.5)
                    yield chunk
                except Empty:
                    # No data available yet
                    if stop_event.is_set() and len(audio_chunks) == 0:
                        # If stopped and no more audio, break
                        break
                    gevent.sleep(0.01)
                    continue
                except Exception as e:
                    logger.error(f"[{call_sid}] Error getting audio chunk: {e}")
                    if stop_event.is_set():
                        break
        
        try:
            # Process audio chunks with the realtime processor
            for result in realtime_processor.process_realtime_session_sync(
                call_sid, get_next_audio_chunk()
            ):
                if stop_event.is_set():
                    break
                    
                ws.send(json.dumps(result))
                
                # If this is a final result, we can reset
                if result.get("type") == "final":
                    audio_chunks = []
        except Exception as e:
            logger.error(f"[{call_sid}] Error processing realtime session: {str(e)}")
            logger.error(traceback.format_exc())
            try:
                ws.send(json.dumps({"type": "error", "message": str(e)}))
            except:
                pass
            finally:
                stop_event.set()
    
    # Start greenlets
    receiver = gevent.spawn(receive_audio)
    processor = gevent.spawn(process_and_send_results)
    
    # Wait for either to finish
    gevent.joinall([receiver, processor], count=1)
    
    # Signal all greenlets to stop
    stop_event.set()
    
    # Wait for cleanup
    gevent.sleep(0.5)
    
    # Kill any remaining greenlets
    if not receiver.dead:
        receiver.kill()
    if not processor.dead:
        processor.kill()
    
    logger.info(f"[{call_sid}] Realtime AI session ended")


@realtime_bp.route("/capabilities", methods=["GET"])
def get_capabilities():
    """
    Get the realtime capabilities of the system.
    
    Returns:
        JSON response with capabilities
    """
    # Get configuration from app config with fallbacks
    openai_model = current_app.config.get('OPENAI_REALTIME_MODEL', "gpt-4o-realtime-preview-2024-10-01") if hasattr(current_app, 'config') else "gpt-4o-realtime-preview-2024-10-01"
    
    # Determine what capabilities are available
    capabilities = {
        "websockets_available": True,
        "realtime_audio": True,
        "speech_to_text": True,
        "text_to_speech": True,
        "model": openai_model,
        "supported_audio_formats": ["g711_ulaw", "pcm16"],
        "supported_sample_rates": [8000, 16000],
        "supported_voices": ["alloy", "nova", "shimmer", "echo", "fable", "onyx"],
        "bidirectional_streaming": True,
        "tool_support": True,
        "messages": {
            "session.update": "Initial configuration",
            "input_audio_buffer.append": "Send audio to model",
            "input_audio_buffer.finalize": "Mark end of audio input",
            "conversation.item.create": "Send text for TTS",
            "response.audio.delta": "Audio response from model",
            "transcript.delta": "Interim transcription",
            "transcript.final": "Final transcription",
            "tool_calls": "Model requests tools",
            "tool_results": "Tool response to model"
        },
        "endpoints": {
            "media": "/ws/media/<call_sid>",
            "realtime": "/ws/realtime",
            "capabilities": "/realtime/capabilities",
            "healthcheck": "/realtime/healthcheck"
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
    
    # Try to import agent components to check if they're available
    agent_status = "unknown"
    try:
        from app.agents.factory_with_orchestration import enhanced_agent_factory
        agent_status = "ok"
    except ImportError:
        agent_status = "error"
    except Exception:
        agent_status = "error"
    
    # Check for tools registry
    tools_status = "unknown"
    try:
        from app.routes.voice.utils.tools_registry import execute_tool
        tools_status = "ok"
    except ImportError:
        tools_status = "error"
    except Exception:
        tools_status = "error"
    
    return jsonify({
        "status": "ok",
        "service": "realtime",
        "openai_status": openai_status,
        "agent_status": agent_status,
        "tools_status": tools_status,
        "websocket_available": True,
        "timestamp": time.time()
    })


# This function has been moved to the top - DELETE THIS COMMENT AFTER MERGING