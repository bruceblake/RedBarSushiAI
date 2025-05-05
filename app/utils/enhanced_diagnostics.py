"""
Enhanced diagnostics for WebSocket connections and Twilio Media Streams.

This module provides detailed diagnostic functions to troubleshoot WebSocket
connection issues, particularly with Twilio Media Streams integration.
"""

import logging
import sys
import time
import os
import json
import traceback
import socket
import asyncio
import base64
from datetime import datetime

# psutil is optional and only used for additional diagnostics
# It's not required for the core WebSocket functionality
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logging.info("psutil module is not available. Some optional diagnostic features will be limited.")

# Set up logger
logger = logging.getLogger(__name__)

def check_x11_environment():
    """
    Check if X11 environment is properly configured and provide diagnostic information.
    Not required for server environments like Render.
    
    Returns:
        dict: X11 environment status with diagnostic information
    """
    x11_status = {
        "is_configured": False,
        "display": None,
        "headless_mode": True,  # Default to headless mode on servers
        "server_environment": True
    }
    
    try:
        # Check if we're explicitly configured for headless mode
        is_headless = os.environ.get("OPENAI_REALTIME_NO_DISPLAY") == "1" or os.environ.get("HEADLESS") == "1"
        is_render = os.environ.get("RENDER") == "true"
        
        # Automatically run in headless mode on Render
        if is_render:
            x11_status["headless_mode"] = True
            x11_status["render_environment"] = True
            # Force headless environment variables
            os.environ["OPENAI_REALTIME_NO_DISPLAY"] = "1"
            os.environ["HEADLESS"] = "1"
            logger.info("Running on Render - headless mode automatically enabled")
        elif is_headless:
            logger.info("Headless mode explicitly configured")
            x11_status["headless_mode"] = True
        else:
            # Check if DISPLAY is set for non-server environments
            display = os.environ.get("DISPLAY")
            x11_status["display"] = display
            x11_status["headless_mode"] = not display
            
            if not display:
                logger.info("No display detected, enabling headless mode")
                os.environ["OPENAI_REALTIME_NO_DISPLAY"] = "1"
                os.environ["HEADLESS"] = "1"
        
        # Log the status (only detailed info in debug mode)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"X11 Environment Check: {json.dumps(x11_status, indent=2)}")
        else:
            logger.info(f"Headless mode: {x11_status['headless_mode']}")
        
        return x11_status
        
    except Exception as e:
        logger.error(f"Error checking X11 environment: {e}")
        logger.error(traceback.format_exc())
        x11_status["errors"] = [f"Internal error in X11 check: {str(e)}"]
        return x11_status

def log_websocket_handshake(request, phase="pre-upgrade"):
    """
    Log detailed information about WebSocket handshake requests.
    
    Args:
        request: The Flask/Werkzeug request object
        phase: The handshake phase ('pre-upgrade', 'post-upgrade', 'error')
    """
    try:
        logger.critical(f"[WS_HANDSHAKE:{phase}] ========== WebSocket Handshake Details ==========")
        logger.critical(f"[WS_HANDSHAKE:{phase}] Timestamp: {datetime.now().isoformat()}")
        logger.critical(f"[WS_HANDSHAKE:{phase}] Remote addr: {request.remote_addr}")
        
        # Log headers specifically relevant to WebSocket handshakes
        ws_headers = [
            'Connection', 'Upgrade', 'Sec-WebSocket-Key', 'Sec-WebSocket-Version',
            'Sec-WebSocket-Extensions', 'Sec-WebSocket-Protocol', 'X-Forwarded-For',
            'X-Forwarded-Proto', 'X-Forwarded-Host', 'Host', 'User-Agent'
        ]
        
        logger.critical(f"[WS_HANDSHAKE:{phase}] WebSocket-specific headers:")
        for header in ws_headers:
            if header.lower() in request.headers:
                logger.critical(f"[WS_HANDSHAKE:{phase}]   {header}: {request.headers.get(header)}")
        
        # Log environment information
        logger.critical(f"[WS_HANDSHAKE:{phase}] Environment:")
        logger.critical(f"[WS_HANDSHAKE:{phase}]   FLASK_ENV: {os.environ.get('FLASK_ENV', 'not set')}")
        logger.critical(f"[WS_HANDSHAKE:{phase}]   IS_STAGING: {os.environ.get('IS_STAGING', 'not set')}")
        logger.critical(f"[WS_HANDSHAKE:{phase}]   RENDER: {os.environ.get('RENDER', 'not set')}")
        logger.critical(f"[WS_HANDSHAKE:{phase}]   RENDER_SERVICE_ID: {os.environ.get('RENDER_SERVICE_ID', 'not set')}")
        
        logger.critical(f"[WS_HANDSHAKE:{phase}] ========== End WebSocket Handshake Details ==========")
    except Exception as e:
        logger.error(f"Error logging WebSocket handshake: {e}")
        logger.error(traceback.format_exc())

async def log_websocket_message(message, direction="RECV", message_type="unknown", session_id="unknown"):
    """
    Log detailed information about WebSocket messages.
    
    Args:
        message: The WebSocket message (string or bytes)
        direction: The message direction ('RECV' or 'SEND')
        message_type: The message type (e.g., 'media', 'transcript', etc.)
        session_id: The session ID for correlation
    """
    try:
        # Determine payload type and format for logging
        if isinstance(message, str):
            try:
                # Try to parse as JSON for better formatting
                data = json.loads(message)
                payload_type = "json"
                
                # Extract message type for more specific logging
                if "event" in data:
                    message_type = data["event"]
                elif "type" in data:
                    message_type = data["type"]
                    
                # For media events, don't log the entire payload
                if message_type == "media" and "media" in data and "payload" in data["media"]:
                    payload_size = len(data["media"]["payload"])
                    data["media"]["payload"] = f"<{payload_size} bytes of data>"
                    
                formatted_message = json.dumps(data, indent=2)
            except json.JSONDecodeError:
                payload_type = "text"
                formatted_message = message
        elif isinstance(message, bytes):
            payload_type = "binary"
            # Only log size for binary data
            size = len(message)
            formatted_message = f"<{size} bytes of binary data>"
        else:
            payload_type = type(message).__name__
            formatted_message = str(message)
        
        # Log with different levels based on message type to reduce noise
        if message_type in ["media", "ping", "pong"]:
            # Log only size info for media chunks and pings/pongs
            logger.debug(f"[WS_{direction}:{session_id}] {message_type} ({payload_type}): {formatted_message if len(formatted_message) < 50 else f'<{len(formatted_message)} chars>'}")
        else:
            # Log other events with more detail
            logger.info(f"[WS_{direction}:{session_id}] {message_type} ({payload_type}):")
            if len(formatted_message) > 1000:
                # Truncate very long messages
                logger.info(f"{formatted_message[:1000]}... <truncated>")
            else:
                logger.info(f"{formatted_message}")
    except Exception as e:
        logger.error(f"Error logging WebSocket message: {e}")
        logger.error(traceback.format_exc())

async def send_heartbeat(ws, session_id="unknown", interval=15.0):
    """
    Send periodic heartbeat messages to keep the WebSocket connection alive.
    
    Args:
        ws: The WebSocket connection object
        session_id: The session ID for the connection
        interval: The interval between heartbeats in seconds
    """
    try:
        heartbeat_count = 0
        start_time = time.time()
        
        logger.info(f"[HEARTBEAT:{session_id}] Starting heartbeat task with {interval}s interval")
        
        while True:
            try:
                # Wait for the next interval
                await asyncio.sleep(interval)
                
                # Send a heartbeat message
                heartbeat_count += 1
                total_time = time.time() - start_time
                
                # Create a heartbeat message
                heartbeat = {
                    "type": "heartbeat",
                    "count": heartbeat_count,
                    "uptime": total_time,
                    "session_id": session_id,
                    "timestamp": time.time()
                }
                
                # Send the heartbeat
                await ws.send(json.dumps(heartbeat))
                
                # Log the heartbeat
                logger.debug(f"[HEARTBEAT:{session_id}] Sent heartbeat #{heartbeat_count} after {total_time:.1f}s")
                
            except asyncio.CancelledError:
                logger.info(f"[HEARTBEAT:{session_id}] Heartbeat task cancelled after {heartbeat_count} heartbeats")
                return
            except Exception as e:
                logger.error(f"[HEARTBEAT:{session_id}] Error sending heartbeat: {e}")
                # Log the error but continue sending heartbeats
    except Exception as e:
        logger.error(f"[HEARTBEAT:{session_id}] Fatal error in heartbeat task: {e}")
        logger.error(traceback.format_exc())

def log_system_status(session_id="unknown", context="general"):
    """
    Log basic system status information.
    
    Args:
        session_id: The session ID for correlation
        context: Additional context for the status check
    """
    try:
        # Start with a less noisy log level for routine status checks
        log_level = logging.INFO
        logger.log(log_level, f"[SYSTEM_STATUS:{session_id}] System Status ({context}) - {datetime.now().isoformat()}")
        
        # Basic process info available without psutil
        logger.log(log_level, f"[SYSTEM_STATUS:{session_id}] Process ID: {os.getpid()}")
        logger.log(log_level, f"[SYSTEM_STATUS:{session_id}] Start time: {datetime.fromtimestamp(time.time()).isoformat()}")
        
        # Enhanced diagnostics with psutil if available
        if PSUTIL_AVAILABLE and logger.isEnabledFor(logging.DEBUG):
            process = psutil.Process()
            logger.debug(f"[SYSTEM_STATUS:{session_id}] Process name: {process.name()}")
            logger.debug(f"[SYSTEM_STATUS:{session_id}] Process uptime: {time.time() - process.create_time():.1f}s")
            
            # CPU info
            cpu_percent = process.cpu_percent(interval=0.1)
            system_cpu_percent = psutil.cpu_percent(interval=0.1)
            logger.debug(f"[SYSTEM_STATUS:{session_id}] Process CPU: {cpu_percent:.1f}%")
            logger.debug(f"[SYSTEM_STATUS:{session_id}] System CPU: {system_cpu_percent:.1f}%")
            logger.debug(f"[SYSTEM_STATUS:{session_id}] CPU count: {psutil.cpu_count(logical=True)}")
            
            # Memory info (only if debug is enabled)
            memory_info = process.memory_info()
            system_memory = psutil.virtual_memory()
            logger.debug(f"[SYSTEM_STATUS:{session_id}] Process memory: {memory_info.rss / (1024*1024):.1f} MB (RSS)")
            logger.debug(f"[SYSTEM_STATUS:{session_id}] System memory: {system_memory.percent:.1f}%")
        
        # Asyncio task info
        try:
            tasks = asyncio.all_tasks()
            task_count = len(tasks)
            logger.log(log_level, f"[SYSTEM_STATUS:{session_id}] Asyncio tasks: {task_count}")
            
            # Only log detailed task info if debug is enabled
            if logger.isEnabledFor(logging.DEBUG):
                task_names = [task.get_name() for task in tasks]
                logger.debug(f"[SYSTEM_STATUS:{session_id}] Task names: {task_names}")
        except RuntimeError as e:
            logger.log(log_level, f"[SYSTEM_STATUS:{session_id}] Asyncio tasks: Error - {e}")
        
        # Python environment (basic info)
        logger.log(log_level, f"[SYSTEM_STATUS:{session_id}] Python version: {sys.version.split()[0]}")
        
        # Running on Render?
        if os.environ.get("RENDER") == "true":
            logger.log(log_level, f"[SYSTEM_STATUS:{session_id}] Environment: Render")
            logger.log(log_level, f"[SYSTEM_STATUS:{session_id}] Service ID: {os.environ.get('RENDER_SERVICE_ID', 'unknown')}")
        
    except Exception as e:
        logger.error(f"Error logging system status: {e}")
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(traceback.format_exc())

def log_audio_processing_stats(audio_stats, session_id="unknown"):
    """
    Log detailed statistics about audio processing.
    
    Args:
        audio_stats: Dictionary containing audio processing statistics
        session_id: The session ID for correlation
    """
    try:
        # Only log if we have meaningful stats
        if "first_chunk_time" not in audio_stats or audio_stats["first_chunk_time"] is None:
            logger.info(f"[AUDIO_STATS:{session_id}] No audio data received yet")
            return
            
        logger.info(f"[AUDIO_STATS:{session_id}] ========== Audio Processing Stats ==========")
        
        # Calculate time metrics
        now = time.time()
        if audio_stats["last_chunk_time"] is not None:
            duration = audio_stats["last_chunk_time"] - audio_stats["first_chunk_time"]
            time_since_last = now - audio_stats["last_chunk_time"]
        else:
            duration = 0
            time_since_last = 0
        
        # Basic stats
        logger.info(f"[AUDIO_STATS:{session_id}] Total chunks: {audio_stats.get('chunk_count', 0)}")
        logger.info(f"[AUDIO_STATS:{session_id}] Total audio duration: {duration:.2f}s")
        logger.info(f"[AUDIO_STATS:{session_id}] Time since last chunk: {time_since_last:.2f}s")
        
        # Size stats
        if "chunk_sizes" in audio_stats and audio_stats["chunk_sizes"]:
            logger.info(f"[AUDIO_STATS:{session_id}] Min chunk size: {audio_stats.get('min_chunk_size', 0)} bytes")
            logger.info(f"[AUDIO_STATS:{session_id}] Max chunk size: {audio_stats.get('max_chunk_size', 0)} bytes")
            logger.info(f"[AUDIO_STATS:{session_id}] Avg chunk size: {sum(audio_stats['chunk_sizes']) / len(audio_stats['chunk_sizes']):.1f} bytes")
            logger.info(f"[AUDIO_STATS:{session_id}] Total audio size: {audio_stats.get('total_audio_size', 0)} bytes")
        
        # Rate stats
        if duration > 0:
            chunks_per_second = audio_stats.get('chunk_count', 0) / duration
            bytes_per_second = audio_stats.get('total_audio_size', 0) / duration
            logger.info(f"[AUDIO_STATS:{session_id}] Chunk rate: {chunks_per_second:.1f} chunks/sec")
            logger.info(f"[AUDIO_STATS:{session_id}] Data rate: {bytes_per_second:.1f} bytes/sec ({bytes_per_second/1024:.1f} KB/sec)")
        
        # Diagnostic timing
        logger.info(f"[AUDIO_STATS:{session_id}] First chunk received at: {datetime.fromtimestamp(audio_stats['first_chunk_time']).isoformat()}")
        if audio_stats["last_chunk_time"] is not None:
            logger.info(f"[AUDIO_STATS:{session_id}] Last chunk received at: {datetime.fromtimestamp(audio_stats['last_chunk_time']).isoformat()}")
        
        # Transcript stats
        logger.info(f"[AUDIO_STATS:{session_id}] Transcripts generated: {audio_stats.get('transcripts_generated', 0)}")
        logger.info(f"[AUDIO_STATS:{session_id}] Silence events: {audio_stats.get('silence_events', 0)}")
        
        logger.info(f"[AUDIO_STATS:{session_id}] ========== End Audio Stats ==========")
    except Exception as e:
        logger.error(f"Error logging audio stats: {e}")
        logger.error(traceback.format_exc())

def log_realtime_session_details(session_config, status="starting", session_id="unknown"):
    """
    Log detailed information about the OpenAI Realtime session configuration.
    
    Args:
        session_config: The session configuration dictionary
        status: The session status ('starting', 'running', 'error', 'closed')
        session_id: The session ID for correlation
    """
    try:
        logger.info(f"[REALTIME_SESSION:{session_id}] ========== OpenAI Realtime Session ({status}) ==========")
        
        # Log config with sensitive fields redacted
        safe_config = session_config.copy() if session_config else {}
        
        # Redact any API keys or tokens
        if 'api_key' in safe_config:
            safe_config['api_key'] = f"<redacted: {safe_config['api_key'][:4]}...>"
        
        # Log model info
        logger.info(f"[REALTIME_SESSION:{session_id}] Model: {safe_config.get('model', 'unknown')}")
        
        # Log audio format info
        logger.info(f"[REALTIME_SESSION:{session_id}] Input audio format: {safe_config.get('input_audio_format', 'unknown')}")
        logger.info(f"[REALTIME_SESSION:{session_id}] Output audio format: {safe_config.get('output_audio_format', 'unknown')}")
        
        # Log VAD settings if present
        vad_settings = safe_config.get('voice_activity_detection', {})
        if vad_settings:
            logger.info(f"[REALTIME_SESSION:{session_id}] VAD enabled: True")
            logger.info(f"[REALTIME_SESSION:{session_id}] VAD mode: {vad_settings.get('mode', 'unknown')}")
            logger.info(f"[REALTIME_SESSION:{session_id}] VAD timeout: {vad_settings.get('timeout', 'unknown')}")
            logger.info(f"[REALTIME_SESSION:{session_id}] VAD speech_started_delay: {vad_settings.get('speech_started_delay', 'unknown')}")
        else:
            logger.info(f"[REALTIME_SESSION:{session_id}] VAD enabled: False")
        
        # Log tools configuration if present
        tools = safe_config.get('tools', [])
        if tools:
            logger.info(f"[REALTIME_SESSION:{session_id}] Tools enabled: {len(tools)} tools available")
            tool_names = [tool.get('name', 'unnamed') for tool in tools]
            logger.info(f"[REALTIME_SESSION:{session_id}] Tool names: {tool_names}")
        else:
            logger.info(f"[REALTIME_SESSION:{session_id}] Tools enabled: False")
        
        # Log other important settings
        logger.info(f"[REALTIME_SESSION:{session_id}] Temperature: {safe_config.get('temperature', 'default')}")
        logger.info(f"[REALTIME_SESSION:{session_id}] Timeout: {safe_config.get('timeout', 'default')}")
        
        if status == "error":
            logger.error(f"[REALTIME_SESSION:{session_id}] Error: {safe_config.get('error', 'Unknown error')}")
        
        logger.info(f"[REALTIME_SESSION:{session_id}] ========== End Realtime Session Details ==========")
    except Exception as e:
        logger.error(f"Error logging Realtime session details: {e}")
        logger.error(traceback.format_exc())

def check_redis_connection(redis_client, session_id="unknown"):
    """
    Check Redis connection health and log the results.
    
    Args:
        redis_client: The Redis client to check
        session_id: The session ID for correlation
        
    Returns:
        bool: True if Redis connection is healthy, False otherwise
    """
    try:
        logger.info(f"[REDIS_CHECK:{session_id}] Checking Redis connection health")
        
        if redis_client is None:
            logger.error(f"[REDIS_CHECK:{session_id}] Redis client is None")
            return False
        
        # Basic PING test
        ping_result = redis_client.ping()
        logger.info(f"[REDIS_CHECK:{session_id}] Redis PING result: {ping_result}")
        
        if not ping_result:
            logger.error(f"[REDIS_CHECK:{session_id}] Redis PING failed")
            return False
        
        # Test SET/GET
        test_key = f"healthcheck:{session_id}:{int(time.time())}"
        test_value = "healthy"
        
        set_result = redis_client.set(test_key, test_value, ex=60)
        logger.info(f"[REDIS_CHECK:{session_id}] Redis SET result: {set_result}")
        
        get_result = redis_client.get(test_key)
        logger.info(f"[REDIS_CHECK:{session_id}] Redis GET result: {get_result == test_value.encode('utf-8')}")
        
        # Clean up test key
        redis_client.delete(test_key)
        
        # Get Redis info for more details
        info = redis_client.info()
        
        # Log key info fields
        logger.info(f"[REDIS_CHECK:{session_id}] Redis version: {info.get('redis_version', 'unknown')}")
        logger.info(f"[REDIS_CHECK:{session_id}] Connected clients: {info.get('connected_clients', 'unknown')}")
        logger.info(f"[REDIS_CHECK:{session_id}] Used memory: {info.get('used_memory_human', 'unknown')}")
        logger.info(f"[REDIS_CHECK:{session_id}] Connection age: {info.get('uptime_in_seconds', 0)} seconds")
        
        return True
    except Exception as e:
        logger.error(f"[REDIS_CHECK:{session_id}] Redis connection error: {e}")
        logger.error(traceback.format_exc())
        return False
        
def log_connection_event(event_type, details, session_id="unknown"):
    """
    Log detailed information about connection events, particularly around greeting.
    
    Args:
        event_type: Type of connection event ('greeting_sent', 'post_greeting_silence', etc.)
        details: Additional details about the event
        session_id: The session ID for correlation
    """
    try:
        timestamp = time.time()
        formatted_time = datetime.fromtimestamp(timestamp).isoformat()
        
        logger.critical(f"[CONNECTION_EVENT:{session_id}] ========== Connection Event: {event_type} ==========")
        logger.critical(f"[CONNECTION_EVENT:{session_id}] Timestamp: {formatted_time}")
        
        # Log different details based on event type
        if event_type == "greeting_sent":
            logger.critical(f"[CONNECTION_EVENT:{session_id}] Greeting sent at: {formatted_time}")
            logger.critical(f"[CONNECTION_EVENT:{session_id}] Greeting text: {details.get('text', 'unknown')}")
            logger.critical(f"[CONNECTION_EVENT:{session_id}] Time since connection: {details.get('time_since_connection', 0):.3f}s")
            logger.critical(f"[CONNECTION_EVENT:{session_id}] Audio chunks before greeting: {details.get('audio_chunks', 0)}")
            logger.critical(f"[CONNECTION_EVENT:{session_id}] Events processed before greeting: {details.get('events_processed', 0)}")
            
        elif event_type == "post_greeting_silence":
            logger.critical(f"[CONNECTION_EVENT:{session_id}] ⚠️ SILENCE AFTER GREETING DETECTED ⚠️")
            logger.critical(f"[CONNECTION_EVENT:{session_id}] Silence detected at: {formatted_time}")
            logger.critical(f"[CONNECTION_EVENT:{session_id}] Time since greeting: {details.get('time_since_greeting', 0):.3f}s")
            logger.critical(f"[CONNECTION_EVENT:{session_id}] Total silence events: {details.get('silence_count', 0)}")
            
        elif event_type == "post_greeting_transcript":
            logger.critical(f"[CONNECTION_EVENT:{session_id}] First transcript after greeting detected")
            logger.critical(f"[CONNECTION_EVENT:{session_id}] Transcript text: {details.get('text', 'unknown')}")
            logger.critical(f"[CONNECTION_EVENT:{session_id}] Time since greeting: {details.get('time_since_greeting', 0):.3f}s")
            
        elif event_type == "disconnection":
            logger.critical(f"[CONNECTION_EVENT:{session_id}] ❌ WEBSOCKET DISCONNECTION ❌")
            logger.critical(f"[CONNECTION_EVENT:{session_id}] Disconnection reason: {details.get('reason', 'unknown')}")
            logger.critical(f"[CONNECTION_EVENT:{session_id}] Total connection duration: {details.get('total_duration', 0):.3f}s")
            logger.critical(f"[CONNECTION_EVENT:{session_id}] Time since greeting: {details.get('time_since_greeting', 0):.3f}s")
            logger.critical(f"[CONNECTION_EVENT:{session_id}] Was greeting followed by user audio: {details.get('post_greeting_audio', False)}")
            logger.critical(f"[CONNECTION_EVENT:{session_id}] Was greeting followed by user speech: {details.get('post_greeting_speech', False)}")
            
        # Log all provided details for completeness
        for key, value in details.items():
            if key not in ['text', 'time_since_connection', 'audio_chunks', 'events_processed', 
                          'time_since_greeting', 'silence_count', 'reason', 'total_duration',
                          'post_greeting_audio', 'post_greeting_speech']:
                logger.critical(f"[CONNECTION_EVENT:{session_id}] {key}: {value}")
        
        logger.critical(f"[CONNECTION_EVENT:{session_id}] ========== End Connection Event ==========")
    except Exception as e:
        logger.error(f"Error logging connection event: {e}")
        logger.error(traceback.format_exc())