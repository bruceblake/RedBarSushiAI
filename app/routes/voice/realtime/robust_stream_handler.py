"""
Robust WebSocket stream handler for Realtime API integration.

This module provides an enhanced WebSocket handler with improved stability,
error recovery, and connection management for Twilio Media Streams.
"""

import asyncio
import base64
import json
import logging
import os
import time
import traceback
import uuid
from datetime import datetime
import random

# Import our enhanced connection management system
from app.routes.voice.utils.connection_manager import (
    ConnectionManager,
    ConnectionState,
    maintain_connection,
    monitor_connection_health,
    attempt_reconnection
)

# Import diagnostic utilities
from app.utils.enhanced_diagnostics import (
    log_system_status,
    log_audio_processing_stats,
    log_realtime_session_details,
    check_redis_connection
)

# Import our WebSocket logging utilities
from app.routes.voice.utils.websocket_logging import (
    log_connection_event,
    log_websocket_message_flow,
    track_timing,
    websocket_stats
)

# Import event handlers and audio processing
from app.routes.voice.realtime.audio_generator import create_audio_generator
from app.routes.voice.handlers import (
    handle_silence_event,
    handle_transcript_event,
    handle_tool_call_event,
    handle_audio_event
)

# Import VAD configuration
from app.routes.voice.utils.vad import configure_vad_for_context

# Set up logger
logger = logging.getLogger(__name__)

# Global registry for active connections
active_connections = {}

@track_timing("WebSocket media stream handling")
async def handle_robust_media_stream(ws, session_id=None):
    """
    Enhanced WebSocket handler for Twilio Media Streams with robust connection management.
    
    Args:
        ws: The WebSocket connection object
        session_id: Optional session ID (if None, a new one will be generated)
    """
    # Generate a session ID if not provided
    if session_id is None:
        session_id = str(uuid.uuid4())
    
    # Initialize connection manager
    conn_mgr = ConnectionManager(session_id)
    active_connections[session_id] = conn_mgr
    
    # Register this connection with the stats tracker
    websocket_stats.connection_opened(session_id)
    
    # Track key variables
    realtime_processor = None
    frontline = None
    audio_generator = None
    maintenance_task = None
    monitor_task = None
    twilio_task = None
    
    # Log connection details
    logger.critical(f"⚡⚡⚡ [WEBSOCKET CONNECTION] New WebSocket connection, ID: {session_id} ⚡⚡⚡")
    conn_mgr.log_health_event("CONNECT", "WebSocket connection established")
    
    # Create comprehensive log of system status
    log_system_status(session_id, "websocket_connect")
    
    # Set up enhanced logging
    log_dir = os.path.join(os.getcwd(), 'logs')
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except:
            pass
    
    # Set up session-specific logging
    session_file_handler = None
    ws_file_handler = None
    
    try:
        # Create a session-specific file handler
        session_log_file = os.path.join(log_dir, f'media_stream_{session_id}.log')
        session_file_handler = logging.FileHandler(session_log_file)
        session_file_handler.setLevel(logging.DEBUG)
        session_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
        session_file_handler.setFormatter(session_formatter)
        logger.addHandler(session_file_handler)
        
        # Also log to a common WebSocket log file
        ws_log_file = os.path.join(log_dir, 'websocket_connections.log')
        ws_file_handler = logging.FileHandler(ws_log_file)
        ws_file_handler.setLevel(logging.INFO)
        ws_file_handler.setFormatter(session_formatter)
        logger.addHandler(ws_file_handler)
        
        logger.info(f"███████████████████████████████████████████████████████████████")
        logger.info(f"████ NEW WEBSOCKET CONNECTION - SESSION ID: {session_id} ████")
        logger.info(f"███████████████████████████████████████████████████████████████")
    except Exception as log_error:
        logger.error(f"Failed to set up session-specific logging: {log_error}")
    
    # Start connection maintenance task
    try:
        logger.info(f"[WEBSOCKET:{session_id}] Starting connection maintenance task")
        maintenance_task = asyncio.create_task(maintain_connection(ws, conn_mgr))
        conn_mgr.register_task(maintenance_task, "maintain_connection")
        
        # Start health monitoring task
        monitor_task = asyncio.create_task(monitor_connection_health(ws, conn_mgr))
        conn_mgr.register_task(monitor_task, "monitor_connection_health")
    except Exception as task_error:
        logger.error(f"[WEBSOCKET:{session_id}] Error starting maintenance tasks: {task_error}")
        logger.error(traceback.format_exc())
    
    # Test the WebSocket connection with a simple echo
    try:
        # Send a test message
        logger.info(f"[WEBSOCKET:{session_id}] Sending connection test message")
        test_msg = json.dumps({
            "type": "connection_test", 
            "time": time.time(), 
            "id": session_id,
            "message": "Testing WebSocket connection"
        })
        await ws.send(test_msg)
        conn_mgr.record_message_sent("test")
        logger.info(f"[WEBSOCKET:{session_id}] ✅ Successfully sent test message")
        
        # Try to receive an initial message with a short timeout
        try:
            logger.info(f"[WEBSOCKET:{session_id}] Waiting for initial message (1s timeout)")
            initial_msg = await asyncio.wait_for(ws.receive(), timeout=1.0)
            logger.info(f"[WEBSOCKET:{session_id}] ✅ Received initial message")
            conn_mgr.record_message_received()
            
            # Log the message using the enhanced logging
            await log_websocket_message_flow(initial_msg, "RECV", ws, session_id, "initial")
        except asyncio.TimeoutError:
            logger.warning(f"[WEBSOCKET:{session_id}] ⚠️ No initial message received within 1 second timeout")
            logger.warning(f"[WEBSOCKET:{session_id}] This is normal if Twilio is waiting to send the first media chunk")
        except Exception as recv_error:
            logger.error(f"[WEBSOCKET:{session_id}] ❌ Error receiving initial message: {recv_error}")
            logger.error(traceback.format_exc())
    except Exception as test_error:
        logger.error(f"[WEBSOCKET:{session_id}] ❌ Error during WebSocket connection test: {test_error}")
        logger.error(traceback.format_exc())
        conn_mgr.connection_errors += 1
    
    # Update connection state
    conn_mgr.update_state(ConnectionState.ESTABLISHED, "connection_test_complete")
    
    # Main processing block
    try:
        logger.info(f"[MEDIA_STREAM] New media stream connection: {session_id}")
        
        # Import the required modules
        from app.utils.realtime_audio_sdk import get_realtime_processor
        from app.agents.factory_with_orchestration import enhanced_agent_factory
        from app.utils.agent_orchestration import FSMState
        from app.utils.conversation_store import redis_client
        from app.routes.voice.utils.tools_registry import ToolRegistry, register_default_tools
        
        # Initialize the Realtime processor
        logger.info(f"[REALTIME:{session_id}] Attempting to initialize OpenAI Realtime processor")
        try:
            realtime_processor = get_realtime_processor()
            logger.info(f"[REALTIME:{session_id}] ✅ Successfully initialized realtime processor")
            
            # Get and log the session configuration if available
            if hasattr(realtime_processor, 'get_config'):
                session_config = realtime_processor.get_config()
                log_realtime_session_details(session_config, "starting", session_id)
                
            # Check if we're using the optimized client or fallback
            is_fallback = False
            if hasattr(realtime_processor, 'is_fallback'):
                is_fallback = realtime_processor.is_fallback
                logger.info(f"[REALTIME:{session_id}] Using fallback WebSocket implementation: {is_fallback}")
            
            # Configure VAD for initial greeting context
            vad_config = configure_vad_for_context("greeting")
            if hasattr(realtime_processor, 'configure_vad'):
                realtime_processor.configure_vad(vad_config)
                logger.info(f"[REALTIME:{session_id}] ✅ Configured VAD for greeting context")
                logger.debug(f"[REALTIME:{session_id}] VAD config: {vad_config}")
            
        except Exception as rt_error:
            logger.error(f"[REALTIME:{session_id}] ❌ Failed to initialize Realtime processor: {rt_error}")
            logger.error(f"[REALTIME:{session_id}] Initialization error trace: {traceback.format_exc()}")
            conn_mgr.update_state(ConnectionState.ERROR, f"realtime_init_error: {str(rt_error)}")
            raise RuntimeError(f"Failed to initialize OpenAI Realtime processor: {rt_error}")
    
        # Initialize orchestrated agents
        try:
            logger.info(f"[AGENT:{session_id}] Getting orchestrated agent components")
            # Get components from global registry
            from app.routes.voice import get_global_component
            frontline = get_global_component('frontline_agent')
            fsm_orchestrator = get_global_component('fsm_orchestrator')
            tool_registry = get_global_component('tool_registry')
            
            # Verify we have all required components
            if not frontline or not fsm_orchestrator or not tool_registry:
                logger.error(f"[AGENT:{session_id}] Missing required components: "
                            f"frontline={frontline is not None}, "
                            f"fsm={fsm_orchestrator is not None}, "
                            f"tools={tool_registry is not None}")
                conn_mgr.update_state(ConnectionState.ERROR, "missing_agent_components")
                raise RuntimeError("Missing required agent components")
                
            logger.info(f"[AGENT:{session_id}] ✅ Agent components loaded successfully")
            
            # Check Redis connection health
            if redis_client:
                redis_health = check_redis_connection(redis_client, session_id)
                logger.info(f"[AGENT:{session_id}] Redis connection health check: {'✅ Healthy' if redis_health else '❌ Unhealthy'}")
            
            # Send connection confirmation to client
            confirm_msg = {
                "type": "connected",
                "session_id": session_id,
                "timestamp": time.time(),
                "message": "Connected to Red Bar Sushi AI system"
            }
            logger.info(f"[WEBSOCKET:{session_id}] Sending connection confirmation")
            await ws.send(json.dumps(confirm_msg))
            conn_mgr.record_message_sent("connected")
            
            # Update connection state
            conn_mgr.update_state(ConnectionState.AUTHENTICATED, "connection_confirmed")
            
        except Exception as e:
            logger.error(f"[AGENT:{session_id}] ❌ Failed to initialize agents: {str(e)}")
            logger.error(f"[AGENT:{session_id}] Agent initialization error trace: {traceback.format_exc()}")
            conn_mgr.update_state(ConnectionState.ERROR, f"agent_init_error: {str(e)}")
            
            # Send detailed error info to client
            await ws.send(json.dumps({
                "type": "error",
                "error": f"Failed to initialize agents: {str(e)}",
                "timestamp": time.time(),
                "details": traceback.format_exc(),
                "session_id": session_id
            }))
            conn_mgr.record_message_sent("error")
            return
        
        # Store messages from Twilio in a queue
        incoming_audio_queue = asyncio.Queue()
        
        # Define task for processing Twilio messages
        async def process_twilio_messages():
            try:
                logger.info(f"[TWILIO:{session_id}] Starting Twilio message processor")
                message_count = 0
                
                # Save the time of key events for diagnostic purposes
                diagnostic_events = {
                    "first_audio_received": None,
                    "first_transcript_received": None,
                    "greeting_sent": None
                }
            
                while True:
                    try:
                        message = await asyncio.wait_for(ws.receive(), timeout=20.0)
                        message_count += 1
                        conn_mgr.record_message_received()
                        
                        # Handle different message types from Twilio
                        if isinstance(message, str):
                            try:
                                data = json.loads(message)
                                event_type = data.get("event", "unknown")
                                
                                # Log the received message with appropriate detail level
                                if event_type == "media":
                                    # For media events, just log that we received one to reduce noise
                                    if message_count % 50 == 0:  # Log only every 50th media message to reduce noise
                                        logger.debug(f"[TWILIO:{session_id}] Received media event #{message_count}")
                                else:
                                    # For non-media events, log the full event
                                    logger.info(f"[TWILIO:{session_id}] Received Twilio event: {event_type}")
                                    logger.debug(f"[TWILIO:{session_id}] Full event data: {data}")
                            
                                # Handle specific event types
                                if event_type == "start":
                                    logger.info(f"[TWILIO:{session_id}] Media stream started: {data}")
                                    
                                    # Extract and store call and stream SIDs
                                    if "streamSid" in data:
                                        conn_mgr.stream_sid = data["streamSid"]
                                    if "callSid" in data:
                                        conn_mgr.call_sid = data["callSid"]
                                    
                                    # Log media format for debugging
                                    if "start" in data:
                                        media_format = data["start"].get("mediaFormat", {})
                                        logger.info(f"[TWILIO:{session_id}] Media format: {media_format}")
                                    
                                    # Initialize FSM state
                                    logger.info(f"[FSM:{session_id}] Setting initial FSM state: GREETING")
                                    fsm_orchestrator.set_state(session_id, FSMState.GREETING)
                                    
                                    # Update connection state
                                    conn_mgr.update_state(ConnectionState.GREETING, "start_received")
                                    
                                elif event_type == "stop":
                                    logger.info(f"[TWILIO:{session_id}] Media stream stopped: {data}")
                                    logger.info(f"[TWILIO:{session_id}] Twilio requested stream stop")
                                    
                                    # Update connection state
                                    conn_mgr.update_state(ConnectionState.CLOSING, "stop_received")
                                    break
                                    
                                elif event_type == "media":
                                    # Process media chunk
                                    payload = data.get("media", {}).get("payload")
                                    if payload:
                                        try:
                                            # Decode base64 audio
                                            audio_chunk = base64.b64decode(payload)
                                            chunk_size = len(audio_chunk)
                                            conn_mgr.media_count += 1
                                            
                                            # Add to queue for processing
                                            await incoming_audio_queue.put(audio_chunk)
                                            
                                            # Every 50th chunk, send a heartbeat
                                            if conn_mgr.media_count % 50 == 0:
                                                try:
                                                    audio_heartbeat = {
                                                        "type": "audio_heartbeat",
                                                        "chunk_count": conn_mgr.media_count,
                                                        "session_id": session_id,
                                                        "timestamp": time.time()
                                                    }
                                                    await ws.send(json.dumps(audio_heartbeat))
                                                    conn_mgr.record_message_sent("audio_heartbeat")
                                                except Exception as hb_error:
                                                    logger.warning(f"[TWILIO:{session_id}] Could not send audio heartbeat: {hb_error}")
                                            
                                            # Track diagnostic events
                                            if diagnostic_events["first_audio_received"] is None:
                                                diagnostic_events["first_audio_received"] = time.time() - conn_mgr.connection_start_time
                                                logger.info(f"[TWILIO:{session_id}] First audio received after {diagnostic_events['first_audio_received']:.3f}s")
                                            
                                        except Exception as decode_error:
                                            logger.error(f"[TWILIO:{session_id}] Error decoding audio: {decode_error}")
                                    else:
                                        logger.warning(f"[TWILIO:{session_id}] Received media event with empty payload")
                                
                                elif event_type == "mark":
                                    # Handle mark events (Twilio control events)
                                    logger.info(f"[TWILIO:{session_id}] Mark event: {data}")
                                
                            except json.JSONDecodeError as e:
                                logger.warning(f"[TWILIO:{session_id}] Failed to parse JSON message: {e}")
                                logger.warning(f"[TWILIO:{session_id}] Message content (truncated): {message[:100]}")
                        
                        elif isinstance(message, bytes):
                            # Handle raw audio data
                            chunk_size = len(message)
                            conn_mgr.media_count += 1
                            
                            # Add to queue for processing
                            await incoming_audio_queue.put(message)
                            
                            # Log periodically to avoid flooding 
                            if conn_mgr.media_count % 100 == 0:
                                logger.debug(f"[TWILIO:{session_id}] Processed {conn_mgr.media_count} raw audio chunks")
                        else:
                            # Unknown message type
                            logger.warning(f"[TWILIO:{session_id}] Received unknown message type: {type(message)}")
                        
                    except asyncio.TimeoutError:
                        # No messages for 20 seconds
                        elapsed = time.time() - conn_mgr.last_received_time
                        logger.warning(f"[TWILIO:{session_id}] No messages received for {elapsed:.1f} seconds")
                        
                        # Check if we should exit due to inactivity
                        if elapsed > 30:  # Exit after 30 seconds of no activity (reduced from 60)
                            logger.warning(f"[TWILIO:{session_id}] Exiting due to inactivity (30+ seconds)")
                            conn_mgr.update_state(ConnectionState.CLOSING, "inactivity_timeout")
                            break
                        
                        # Send a ping to check connection
                        try:
                            ping_msg = {
                                "type": "ping",
                                "timestamp": time.time(),
                                "session_id": session_id
                            }
                            await ws.send(json.dumps(ping_msg))
                            conn_mgr.record_message_sent("ping")
                            logger.info(f"[TWILIO:{session_id}] Sent ping after {elapsed:.1f}s of inactivity")
                        except Exception as ping_error:
                            logger.error(f"[TWILIO:{session_id}] Failed to send ping: {ping_error}")
                            # Continue waiting
                        
                        # Continue waiting
                        continue
                        
            except Exception as message_error:
                logger.error(f"[TWILIO:{session_id}] Error processing Twilio message: {message_error}")
                logger.error(f"[TWILIO:{session_id}] Message error trace: {traceback.format_exc()}")
                conn_mgr.update_state(ConnectionState.ERROR, f"twilio_message_error: {str(message_error)}")
            
            logger.info(f"[TWILIO:{session_id}] Twilio message processing completed after {message_count} messages")
        
        # Start processing Twilio messages
        logger.info(f"[TWILIO:{session_id}] Starting Twilio message processing task")
        try:
            twilio_task = asyncio.create_task(process_twilio_messages())
            conn_mgr.register_task(twilio_task, "process_twilio_messages")
        except Exception as task_error:
            logger.error(f"[TWILIO:{session_id}] Error creating Twilio task: {str(task_error)}")
            logger.error(f"[TWILIO:{session_id}] Task creation error trace: {traceback.format_exc()}")
            conn_mgr.update_state(ConnectionState.ERROR, f"twilio_task_error: {str(task_error)}")
        
        # Initialize state tracking variables
        greeting_sent = False
        greeting_timestamp = None
        
        # Create an async generator for audio processing
        audio_generator = await create_audio_generator(incoming_audio_queue, session_id, twilio_task)
        
        # Start the Realtime stream
        logger.info(f"[STREAM:{session_id}] Starting Realtime media stream processing")
        
        # Track detailed events for debugging
        event_counts = {}
        processed_events = 0
        stream_start_time = time.time()
        last_event_time = time.time()
        
        # Structure to track timing of key events for diagnostics
        event_timing = {
            "stream_start": stream_start_time,
            "first_event": None,
            "first_transcript": None,
            "first_silence": None,
            "first_tool_call": None,
            "greeting_sent": None,
            "post_greeting_silence": None,
            "post_greeting_transcript": None,
        }
        
        # Process the media stream
        async for event in realtime_processor.process_media_stream(audio_generator, session_id):
            # Track event timing
            current_time = time.time()
            time_since_last = current_time - last_event_time
            last_event_time = current_time
            
            # Record first event timing
            if event_timing["first_event"] is None:
                event_timing["first_event"] = current_time
                elapsed = current_time - stream_start_time
                logger.info(f"[STREAM:{session_id}] ✅ First event received after {elapsed:.3f}s")
            
            # Update metrics
            processed_events += 1
            conn_mgr.record_message_received()
            
            # Handle different event types
            event_type = event.get("type", "")
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
            
            # Set event type-specific timing metrics
            if event_type == "transcript_complete" and event_timing["first_transcript"] is None:
                event_timing["first_transcript"] = current_time
                elapsed = current_time - stream_start_time
                logger.info(f"[STREAM:{session_id}] ✅ First transcript received after {elapsed:.3f}s")
                
                # Record post-greeting transcript if greeting was already sent
                if greeting_sent and event_timing["post_greeting_transcript"] is None:
                    event_timing["post_greeting_transcript"] = current_time
                    time_after_greeting = current_time - greeting_timestamp
                    logger.info(f"[STREAM:{session_id}] ✅ First transcript after greeting received {time_after_greeting:.3f}s after greeting")
            
            elif event_type == "silence_detected" and event_timing["first_silence"] is None:
                event_timing["first_silence"] = current_time
                elapsed = current_time - stream_start_time
                logger.info(f"[STREAM:{session_id}] ✅ First silence event received after {elapsed:.3f}s")
                
                # Record post-greeting silence if greeting was already sent
                if greeting_sent and event_timing["post_greeting_silence"] is None:
                    event_timing["post_greeting_silence"] = current_time
                    time_after_greeting = current_time - greeting_timestamp
                    logger.critical(f"[STREAM:{session_id}] ✅ CRITICAL: First silence after greeting detected {time_after_greeting:.3f}s after greeting")
            
            elif event_type == "tool_call" and event_timing["first_tool_call"] is None:
                event_timing["first_tool_call"] = current_time
                elapsed = current_time - stream_start_time
                logger.info(f"[STREAM:{session_id}] ✅ First tool call received after {elapsed:.3f}s")
            
            # Log events with appropriate level of detail
            if processed_events <= 10 or processed_events % 20 == 0 or event_type not in ["audio", "ping", "pong"]:
                log_level = logging.INFO
                # Use WARNING for silence events to make them stand out
                if event_type == "silence_detected":
                    log_level = logging.WARNING
                
                # Format event counts nicely
                event_counts_str = ", ".join([f"{k}: {v}" for k, v in event_counts.items()])
                
                # Calculate timing info
                elapsed_total = current_time - stream_start_time
                event_rate = processed_events / elapsed_total if elapsed_total > 0 else 0
                
                logger.log(log_level, f"[STREAM:{session_id}] Event #{processed_events}: type={event_type}, " +
                                     f"time_since_last={time_since_last:.3f}s, " +
                                     f"elapsed={elapsed_total:.1f}s, rate={event_rate:.1f}/s")
                
            # Handle specific event types using the dedicated handlers
            if event_type == "transcript_complete":
                await handle_transcript_event(ws, session_id, frontline, event, {}, event_timing)
                conn_mgr.record_message_sent("transcript_response")
                
            elif event_type == "tool_call":
                await handle_tool_call_event(ws, session_id, tool_registry, event, {})
                conn_mgr.record_message_sent("tool_response")
                
            elif event_type == "silence_detected":
                greeting_sent, greeting_timestamp = await handle_silence_event(
                    ws, session_id, frontline, fsm_orchestrator, event_timing, 
                    greeting_sent, greeting_timestamp, {}
                )
                
                # If greeting was just sent, update connection manager
                if greeting_sent and not conn_mgr.greeting_time:
                    conn_mgr.greeting_time = greeting_timestamp
                    conn_mgr.log_health_event("GREETING", "Greeting sent to user")
                    
                    # After greeting, update VAD config to be more patient
                    if hasattr(realtime_processor, 'configure_vad'):
                        # Get current FSM state
                        current_state = fsm_orchestrator.get_current_state(session_id)
                        state_name = current_state.name if hasattr(current_state, 'name') else str(current_state)
                        
                        # Map FSM state to VAD context
                        vad_context = "normal"
                        if state_name == "GREETING":
                            vad_context = "greeting"
                        elif state_name == "ORDERING":
                            vad_context = "ordering"
                        elif state_name == "CONFIRMATION":
                            vad_context = "confirmation"
                        
                        # Configure VAD with the appropriate context
                        vad_config = configure_vad_for_context(vad_context)
                        realtime_processor.configure_vad(vad_config)
                        logger.info(f"[REALTIME:{session_id}] ✅ Updated VAD for {vad_context} context")
                
                conn_mgr.record_message_sent("silence_response")
                
            elif event_type == "audio":
                await handle_audio_event(ws, session_id, event, {})
                conn_mgr.record_message_sent("audio")
                
            elif event_type == "error":
                # Handle error events
                error_msg = event.get("error", "Unknown error")
                logger.error(f"[STREAM:{session_id}] Received error event: {error_msg}")
                conn_mgr.log_health_event("ERROR", f"Error from Realtime API: {error_msg}")
                
                # Forward error to client
                await ws.send(json.dumps({
                    "event": "error",
                    "text": error_msg,
                    "timestamp": time.time()
                }))
                conn_mgr.record_message_sent("error")
        
        logger.info(f"[STREAM:{session_id}] Media stream processing complete after {processed_events} events")
        
    except Exception as e:
        logger.error(f"[MEDIA_STREAM] ❌ Error in media stream processing: {str(e)}")
        logger.error(f"[MEDIA_STREAM] Processing error trace: {traceback.format_exc()}")
        
        # Update connection state
        conn_mgr.update_state(ConnectionState.ERROR, f"media_stream_error: {str(e)}")
        
        # Try to send error to client
        try:
            await ws.send(json.dumps({
                "event": "error",
                "text": f"System error: {str(e)}",
                "timestamp": time.time()
            }))
            conn_mgr.record_message_sent("error")
        except:
            pass
    
    # Clean up and summarize connection
    finally:
        try:
            # Update connection state
            conn_mgr.update_state(ConnectionState.CLOSING, "finalizing")
            
            # Clean up tasks associated with this connection
            conn_mgr.cleanup_tasks()
            
            # Send final status to client
            try:
                goodbye_msg = {
                    "type": "goodbye",
                    "session_id": session_id,
                    "timestamp": time.time(),
                    "message": "WebSocket connection closed"
                }
                await ws.send(json.dumps(goodbye_msg))
                conn_mgr.record_message_sent("goodbye")
            except Exception as goodbye_error:
                logger.error(f"[WEBSOCKET:{session_id}] Error sending goodbye message: {goodbye_error}")
                
            # Log connection summary
            connection_duration = time.time() - conn_mgr.connection_start_time
            
            logger.info(f"[WEBSOCKET:{session_id}] Connection summary:")
            logger.info(f"[WEBSOCKET:{session_id}] • Duration: {connection_duration:.2f}s")
            logger.info(f"[WEBSOCKET:{session_id}] • Messages received: {conn_mgr.messages_received}")
            logger.info(f"[WEBSOCKET:{session_id}] • Messages sent: {conn_mgr.messages_sent}")
            logger.info(f"[WEBSOCKET:{session_id}] • Media chunks: {conn_mgr.media_count}")
            logger.info(f"[WEBSOCKET:{session_id}] • Keep-alives sent: {conn_mgr.keep_alives_sent}")
            
            # Calculate session quality metrics
            if conn_mgr.greeting_time:
                greeting_delay = conn_mgr.greeting_time - conn_mgr.connection_start_time
                post_greeting_duration = time.time() - conn_mgr.greeting_time
                logger.info(f"[WEBSOCKET:{session_id}] • Time to greeting: {greeting_delay:.2f}s")
                logger.info(f"[WEBSOCKET:{session_id}] • Post-greeting duration: {post_greeting_duration:.2f}s")
            
            # Log final events and update connection state
            conn_mgr.log_health_event("CLOSE", f"WebSocket connection closed after {connection_duration:.2f}s")
            conn_mgr.update_state(ConnectionState.CLOSED, "normal_close")
            
            # Update the WebSocket stats
            websocket_stats.connection_closed(
                duration=connection_duration,
                msgs_received=conn_mgr.messages_received,
                msgs_sent=conn_mgr.messages_sent,
                session_id=session_id
            )
            
            # Remove from active connections
            if session_id in active_connections:
                del active_connections[session_id]
                
            logger.info(f"[WEBSOCKET:{session_id}] Connection tracking removed, active connections: {len(active_connections)}")
            
        except Exception as cleanup_error:
            logger.error(f"[WEBSOCKET:{session_id}] Error during connection cleanup: {cleanup_error}")
            logger.error(traceback.format_exc())
        
        # Clean up session-specific logging
        finally:
            try:
                if session_file_handler:
                    logger.removeHandler(session_file_handler)
                if ws_file_handler:
                    logger.removeHandler(ws_file_handler)
            except:
                pass