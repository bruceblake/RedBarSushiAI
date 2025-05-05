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
import psutil
import traceback
import socket
import asyncio
import base64
from datetime import datetime

# Set up logger
logger = logging.getLogger(__name__)

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
    Log detailed system status information.
    
    Args:
        session_id: The session ID for correlation
        context: Additional context for the status check
    """
    try:
        logger.critical(f"[SYSTEM_STATUS:{session_id}] ========== System Status ({context}) ==========")
        logger.critical(f"[SYSTEM_STATUS:{session_id}] Timestamp: {datetime.now().isoformat()}")
        
        # Process info
        process = psutil.Process()
        logger.critical(f"[SYSTEM_STATUS:{session_id}] Process ID: {process.pid}")
        logger.critical(f"[SYSTEM_STATUS:{session_id}] Process name: {process.name()}")
        logger.critical(f"[SYSTEM_STATUS:{session_id}] Process uptime: {time.time() - process.create_time():.1f}s")
        
        # CPU info
        cpu_percent = process.cpu_percent(interval=1.0)
        system_cpu_percent = psutil.cpu_percent(interval=0.5)
        logger.critical(f"[SYSTEM_STATUS:{session_id}] Process CPU: {cpu_percent:.1f}%")
        logger.critical(f"[SYSTEM_STATUS:{session_id}] System CPU: {system_cpu_percent:.1f}%")
        logger.critical(f"[SYSTEM_STATUS:{session_id}] CPU count: {psutil.cpu_count(logical=True)}")
        
        # Memory info
        memory_info = process.memory_info()
        system_memory = psutil.virtual_memory()
        logger.critical(f"[SYSTEM_STATUS:{session_id}] Process memory: {memory_info.rss / (1024*1024):.1f} MB (RSS)")
        logger.critical(f"[SYSTEM_STATUS:{session_id}] System memory: {system_memory.used / (1024*1024*1024):.1f} GB used of {system_memory.total / (1024*1024*1024):.1f} GB")
        logger.critical(f"[SYSTEM_STATUS:{session_id}] Memory percent: {system_memory.percent:.1f}%")
        
        # Disk info
        disk = psutil.disk_usage('/')
        logger.critical(f"[SYSTEM_STATUS:{session_id}] Disk usage: {disk.used / (1024*1024*1024):.1f} GB used of {disk.total / (1024*1024*1024):.1f} GB ({disk.percent:.1f}%)")
        
        # Network info
        net_connections = process.connections()
        logger.critical(f"[SYSTEM_STATUS:{session_id}] Network connections: {len(net_connections)}")
        
        # Thread info
        logger.critical(f"[SYSTEM_STATUS:{session_id}] Thread count: {process.num_threads()}")
        
        # Asyncio task info
        try:
            tasks = asyncio.all_tasks()
            logger.critical(f"[SYSTEM_STATUS:{session_id}] Asyncio tasks: {len(tasks)}")
            
            # Log task names for debugging
            task_names = [task.get_name() for task in tasks]
            logger.critical(f"[SYSTEM_STATUS:{session_id}] Task names: {task_names}")
        except RuntimeError as e:
            logger.critical(f"[SYSTEM_STATUS:{session_id}] Asyncio tasks: Error - {e}")
        
        # Python environment
        logger.critical(f"[SYSTEM_STATUS:{session_id}] Python version: {sys.version}")
        logger.critical(f"[SYSTEM_STATUS:{session_id}] Platform: {sys.platform}")
        
        # Log environment variables (excluding sensitive ones)
        env_keys = [k for k in os.environ.keys() if not any(secret in k.lower() for secret in ['key', 'token', 'secret', 'password'])]
        logger.critical(f"[SYSTEM_STATUS:{session_id}] Environment variables: {sorted(env_keys)}")
        
        logger.critical(f"[SYSTEM_STATUS:{session_id}] ========== End System Status ==========")
    except Exception as e:
        logger.error(f"Error logging system status: {e}")
        logger.error(traceback.format_exc())

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