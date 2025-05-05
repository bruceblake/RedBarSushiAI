"""
WebSocket stream handler for Realtime API integration.

This module provides the main WebSocket handler for the Twilio Media Streams
integration with OpenAI's Realtime API.
"""

import asyncio
import base64
import json
import logging
import os
import time
import traceback
import uuid

from app.utils.enhanced_diagnostics import (
    log_websocket_handshake,
    log_system_status,
    log_audio_processing_stats,
    log_realtime_session_details,
    check_redis_connection
)

# Import our new enhanced WebSocket logging utilities
from app.routes.voice.utils.websocket_logging import (
    log_connection_event,
    log_websocket_message_flow,
    track_timing,
    websocket_stats,
    send_heartbeat
)

from app.routes.voice.realtime.audio_generator import create_audio_generator
from app.routes.voice.handlers import (
    handle_silence_event,
    handle_transcript_event,
    handle_tool_call_event,
    handle_audio_event
)

# Set up logger
logger = logging.getLogger(__name__)

@track_timing("WebSocket media stream handling")
async def handle_media_stream(ws, session_id=None):
    """
    WebSocket handler for Twilio Media Streams API integration with OpenAI Realtime.
    
    Args:
        ws: The WebSocket connection object
        session_id: Optional session ID (if None, a new one will be generated)
    """
    # Register this connection with the stats tracker
    websocket_stats.connection_opened(session_id)
    # Track key variables
    realtime_processor = None
    keepalive_task = None
    twilio_task = None
    frontline = None
    
    # Generate a session ID if not provided
    if session_id is None:
        session_id = str(uuid.uuid4())
    
    # Log connection details
    connection_time = time.time()
    logger.critical(f"⚡⚡⚡ [WEBSOCKET CONNECTION] New WebSocket connection at {connection_time}, ID: {session_id} ⚡⚡⚡")
    
    # Create immediately a comprehensive log of system status
    log_system_status(session_id, "websocket_connect")
    
    # Set up enhanced logging for this session
    log_dir = os.path.join(os.getcwd(), 'logs')
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except:
            pass  # If we can't create the dir, we'll fallback to default logging
    
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
    
    # Log WebSocket handshake details
    try:
        if hasattr(ws, 'request'):
            log_websocket_handshake(ws.request, "post-upgrade")
    except Exception as handshake_error:
        logger.error(f"[WEBSOCKET DEBUG] Error logging handshake details: {handshake_error}")
        logger.error(traceback.format_exc())
    
    # Start the keep-alive task to prevent connection timeouts
    try:
        logger.info(f"[WEBSOCKET:{session_id}] Starting keep-alive task")
        # Use a shorter interval of 5 seconds to prevent timeouts
        keepalive_task = asyncio.create_task(
            send_heartbeat(ws, session_id, interval=5.0),  # Send heartbeat every 5 seconds
            name=f"heartbeat-{session_id}"
        )
        logger.info(f"[WEBSOCKET:{session_id}] Keep-alive task started with 5-second interval")
        
        # Add task to a global set to prevent it from being garbage collected
        if not hasattr(asyncio, '_keepalive_tasks'):
            asyncio._keepalive_tasks = set()
        asyncio._keepalive_tasks.add(keepalive_task)
        
        # Set up a callback to remove the task when it's done
        def cleanup_task(task):
            asyncio._keepalive_tasks.discard(task)
            
        keepalive_task.add_done_callback(cleanup_task)
    except Exception as task_error:
        logger.error(f"[WEBSOCKET:{session_id}] Error starting keep-alive task: {task_error}")
        logger.error(traceback.format_exc())
    
    # Test the WebSocket connection with a simple echo
    try:
        # Send a test message
        logger.critical(f"[WEBSOCKET:{session_id}] Sending connection test message")
        test_msg = json.dumps({
            "type": "connection_test", 
            "time": time.time(), 
            "id": session_id,
            "message": "Testing WebSocket connection"
        })
        await ws.send(test_msg)
        logger.critical(f"[WEBSOCKET:{session_id}] ✅ Successfully sent test message")
        
        # Try to receive an initial message with a short timeout
        try:
            logger.critical(f"[WEBSOCKET:{session_id}] Waiting for initial message (1s timeout)")
            initial_msg = await asyncio.wait_for(ws.receive(), timeout=1.0)
            logger.critical(f"[WEBSOCKET:{session_id}] ✅ Received initial message")
            
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
    
    # Now initialize the main WebSocket handling
    try:
        # Track detailed metrics and events
        ws_events = []
        
        # Connection stats 
        metrics = {
            "connection_start_time": time.time(),
            "audio_chunks_received": 0,
            "events_processed": 0,
            "events_sent": 0,
            "silence_events": 0,
            "tool_calls": 0,
            "transcripts_processed": 0,
            "last_activity_time": time.time(),
        }
        
        # Track detailed stats about audio chunks
        audio_stats = {
            "first_chunk_time": None,
            "last_chunk_time": None,
            "min_chunk_size": float('inf'),
            "max_chunk_size": 0,
            "total_audio_size": 0,
            "chunk_count": 0,
            "chunk_sizes": [],
            "transcripts_generated": 0,
            "silence_events": 0
        }
        
        # Function to log the connection summary when it ends
        def log_connection_summary(reason="normal_close"):
            end_time = time.time()
            duration = end_time - metrics["connection_start_time"]
            logger.info("==== WEBSOCKET CONNECTION SUMMARY ====")
            logger.info(f"Session ID: {session_id}")
            logger.info(f"Connection duration: {duration:.2f} seconds")
            logger.info(f"Audio chunks received: {metrics['audio_chunks_received']}")
            logger.info(f"Events processed: {metrics['events_processed']}")
            logger.info(f"Events sent: {metrics['events_sent']}")
            logger.info(f"Silence events: {metrics['silence_events']}")
            logger.info(f"Tool calls: {metrics['tool_calls']}")
            logger.info(f"Transcripts processed: {metrics['transcripts_processed']}")
            logger.info(f"Close reason: {reason}")
            logger.info("==== END WEBSOCKET CONNECTION SUMMARY ====")
            logger.info(f"███████████████████████████████████████████████████████████████")
            logger.info(f"████ WEBSOCKET CONNECTION CLOSED - SESSION ID: {session_id} ████")
            logger.info(f"███████████████████████████████████████████████████████████████")
            
            # Enhanced disconnection logging
            try:
                from app.utils.enhanced_diagnostics import log_connection_event
                # Determine if we had any activity after greeting
                post_greeting_audio = False
                post_greeting_speech = False
                greeting_timestamp = event_timing.get("greeting_sent")
                
                if greeting_timestamp and event_timing.get("first_transcript") and event_timing["first_transcript"] > greeting_timestamp:
                    post_greeting_speech = True
                
                if greeting_timestamp and metrics["audio_chunks_received"] > 0:
                    # Calculate approximate time of last audio based on first chunk and rate
                    if audio_stats.get("last_chunk_time") and audio_stats["last_chunk_time"] > greeting_timestamp:
                        post_greeting_audio = True
                
                # Log disconnection with detailed analysis
                log_connection_event(
                    "disconnection",
                    {
                        "reason": reason,
                        "total_duration": duration,
                        "time_since_greeting": (end_time - greeting_timestamp) if greeting_timestamp else None,
                        "post_greeting_audio": post_greeting_audio,
                        "post_greeting_speech": post_greeting_speech,
                        "audio_chunks": metrics["audio_chunks_received"],
                        "transcripts": metrics["transcripts_processed"],
                        "silence_events": metrics["silence_events"],
                        "events_processed": metrics["events_processed"],
                        "greeting_time": greeting_timestamp,
                        "start_time": metrics["connection_start_time"],
                        "end_time": end_time
                    },
                    session_id
                )
            except Exception as e:
                logger.error(f"Error logging disconnection event: {e}")

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
                    logger.critical(f"[REALTIME:{session_id}] Using fallback WebSocket implementation: {is_fallback}")
                
                # If using fallback, log warning and more details
                if is_fallback:
                    logger.warning(f"[REALTIME:{session_id}] ⚠️ USING FALLBACK WEBSOCKET IMPLEMENTATION")
                    logger.warning(f"[REALTIME:{session_id}] The optimized OpenAI Realtime client is not available")
                    logger.warning(f"[REALTIME:{session_id}] This may cause issues with audio processing and VAD")
                    
                    # Log platform details to help diagnose why optimized client isn't available
                    import platform
                    logger.warning(f"[REALTIME:{session_id}] Platform details: {platform.platform()}")
                    logger.warning(f"[REALTIME:{session_id}] Python architecture: {platform.architecture()}")
                    logger.warning(f"[REALTIME:{session_id}] Machine: {platform.machine()}")
                    logger.warning(f"[REALTIME:{session_id}] Python implementation: {platform.python_implementation()}")
                    
            except Exception as rt_error:
                logger.error(f"[REALTIME:{session_id}] ❌ Failed to initialize Realtime processor: {rt_error}")
                logger.error(f"[REALTIME:{session_id}] Initialization error trace: {traceback.format_exc()}")
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
                metrics["events_sent"] += 1
            except Exception as e:
                logger.error(f"[AGENT:{session_id}] ❌ Failed to initialize agents: {str(e)}")
                logger.error(f"[AGENT:{session_id}] Agent initialization error trace: {traceback.format_exc()}")
                
                # Send detailed error info to client
                await ws.send(json.dumps({
                    "type": "error",
                    "error": f"Failed to initialize agents: {str(e)}",
                    "timestamp": time.time(),
                    "details": traceback.format_exc(),
                    "session_id": session_id
                }))
                log_connection_summary("agent_initialization_failed")
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
                
                    message_count = 0
                    while True:
                        try:
                            message = await asyncio.wait_for(ws.receive(), timeout=30.0)
                            message_count += 1
                            metrics["last_activity_time"] = time.time()
                            
                            # Handle different message types from Twilio
                            if isinstance(message, str):
                                try:
                                    data = json.loads(message)
                                    event_type = data.get("event", "unknown")
                                    
                                    # Log the received message with appropriate detail level
                                    if event_type == "media":
                                        # For media events, just log that we received one to reduce noise
                                        if message_count % 20 == 0:  # Log only every 20th media message
                                            logger.debug(f"[TWILIO:{session_id}] Received media event #{message_count}")
                                    else:
                                        # For non-media events, log the full event
                                        logger.info(f"[TWILIO:{session_id}] Received Twilio event: {event_type}")
                                        logger.debug(f"[TWILIO:{session_id}] Full event data: {data}")
                                
                                    # Handle specific event types
                                    if event_type == "start":
                                        logger.info(f"[TWILIO:{session_id}] Media stream started: {data}")
                                        # Log media format for debugging
                                        if "start" in data:
                                            media_format = data["start"].get("mediaFormat", {})
                                            logger.info(f"[TWILIO:{session_id}] Media format: {media_format}")
                                        
                                        # Initialize FSM state
                                        logger.info(f"[FSM:{session_id}] Setting initial FSM state: GREETING")
                                        fsm_orchestrator.set_state(session_id, FSMState.GREETING)
                                        
                                    elif event_type == "stop":
                                        logger.info(f"[TWILIO:{session_id}] Media stream stopped: {data}")
                                        logger.info(f"[TWILIO:{session_id}] Twilio requested stream stop")
                                        break
                                        
                                    elif event_type == "media":
                                        # Process media chunk
                                        payload = data.get("media", {}).get("payload")
                                        if payload:
                                            try:
                                                # Decode base64 audio
                                                audio_chunk = base64.b64decode(payload)
                                                chunk_size = len(audio_chunk)
                                                metrics["audio_chunks_received"] += 1
                                                audio_stats["chunk_count"] += 1
                                                
                                                # Track audio stats
                                                now = time.time()
                                                if audio_stats["first_chunk_time"] is None:
                                                    audio_stats["first_chunk_time"] = now
                                                audio_stats["last_chunk_time"] = now
                                                audio_stats["min_chunk_size"] = min(audio_stats["min_chunk_size"], chunk_size)
                                                audio_stats["max_chunk_size"] = max(audio_stats["max_chunk_size"], chunk_size)
                                                audio_stats["total_audio_size"] += chunk_size
                                                audio_stats["chunk_sizes"].append(chunk_size)
                                                
                                                # Add to queue for processing
                                                await incoming_audio_queue.put(audio_chunk)
                                                
                                                # Every 20th chunk, send a heartbeat
                                                if metrics["audio_chunks_received"] % 20 == 0:
                                                    try:
                                                        audio_heartbeat = {
                                                            "type": "audio_heartbeat",
                                                            "chunk_count": metrics["audio_chunks_received"],
                                                            "session_id": session_id,
                                                            "timestamp": time.time()
                                                        }
                                                        await ws.send(json.dumps(audio_heartbeat))
                                                    except Exception as hb_error:
                                                        logger.warning(f"[TWILIO:{session_id}] Could not send audio heartbeat: {hb_error}")
                                                
                                                # Log audio stats periodically
                                                if metrics["audio_chunks_received"] % 100 == 0:
                                                    # Calculate average chunk size from the last 100 chunks
                                                    recent_chunks = audio_stats["chunk_sizes"][-100:]
                                                    avg_chunk_size = sum(recent_chunks) / len(recent_chunks)
                                                    
                                                    # Calculate audio rate
                                                    audio_duration = audio_stats["last_chunk_time"] - audio_stats["first_chunk_time"]
                                                    if audio_duration > 0:
                                                        chunks_per_second = metrics["audio_chunks_received"] / audio_duration
                                                        bytes_per_second = audio_stats["total_audio_size"] / audio_duration
                                                        
                                                        logger.info(f"[AUDIO:{session_id}] Stats: {metrics['audio_chunks_received']} chunks, " 
                                                                    f"avg size: {avg_chunk_size:.1f} bytes, "
                                                                    f"rate: {chunks_per_second:.1f} chunks/sec, "
                                                                    f"{bytes_per_second:.1f} bytes/sec")
                                                        
                                                        # Every 500 chunks, log comprehensive audio stats
                                                        if metrics["audio_chunks_received"] % 500 == 0:
                                                            log_audio_processing_stats(audio_stats, session_id)
                                                
                                                # Count this message
                                                message_count += 1
                                                
                                                # Track key diagnostic events
                                                if data.get("event") == "media" and diagnostic_events["first_audio_received"] is None:
                                                    diagnostic_events["first_audio_received"] = time.time() - metrics["connection_start_time"]
                                                    logger.info(f"[TWILIO:{session_id}] First audio received after {diagnostic_events['first_audio_received']:.3f}s")
                                                    
                                                if data.get("event") == "transcript" and diagnostic_events["first_transcript_received"] is None:
                                                    diagnostic_events["first_transcript_received"] = time.time() - metrics["connection_start_time"]
                                                    logger.info(f"[TWILIO:{session_id}] First transcript received after {diagnostic_events['first_transcript_received']:.3f}s")
                                                
                                                # Periodically log status
                                                if message_count % 20 == 0:
                                                    elapsed = time.time() - metrics["connection_start_time"]
                                                    rate = message_count / elapsed if elapsed > 0 else 0
                                                    logger.info(f"[TWILIO:{session_id}] Message stats: {message_count} messages, {elapsed:.1f}s, {rate:.1f} msg/sec")
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
                                metrics["audio_chunks_received"] += 1
                                audio_stats["chunk_count"] += 1
                                
                                # Update audio stats
                                now = time.time()
                                if audio_stats["first_chunk_time"] is None:
                                    audio_stats["first_chunk_time"] = now
                                audio_stats["last_chunk_time"] = now
                                audio_stats["min_chunk_size"] = min(audio_stats["min_chunk_size"], chunk_size)
                                audio_stats["max_chunk_size"] = max(audio_stats["max_chunk_size"], chunk_size)
                                audio_stats["total_audio_size"] += chunk_size
                                audio_stats["chunk_sizes"].append(chunk_size)
                                
                                # Add to queue for processing
                                await incoming_audio_queue.put(message)
                                
                                # Log periodically to avoid flooding 
                                if metrics["audio_chunks_received"] % 100 == 0:
                                    logger.debug(f"[TWILIO:{session_id}] Processed {metrics['audio_chunks_received']} raw audio chunks")
                            else:
                                # Unknown message type
                                logger.warning(f"[TWILIO:{session_id}] Received unknown message type: {type(message)}")
                            
                        except asyncio.TimeoutError:
                            # No messages for 30 seconds
                            elapsed = time.time() - metrics["last_activity_time"]
                            logger.warning(f"[TWILIO:{session_id}] No messages received for {elapsed:.1f} seconds")
                            
                            # Check if we should exit due to inactivity
                            if elapsed > 60:  # Exit after 60 seconds of no activity
                                logger.warning(f"[TWILIO:{session_id}] Exiting due to inactivity (60+ seconds)")
                                break
                            # Otherwise continue waiting
                            continue
                            
                except Exception as message_error:
                    logger.error(f"[TWILIO:{session_id}] Error processing Twilio message: {message_error}")
                    logger.error(f"[TWILIO:{session_id}] Message error trace: {traceback.format_exc()}")
                
                logger.info(f"[TWILIO:{session_id}] Twilio message processing completed after {message_count} messages")
            
            # Start processing Twilio messages
            logger.info(f"[TWILIO:{session_id}] Starting Twilio message processing task")
            try:
                twilio_task = asyncio.create_task(process_twilio_messages())
            except Exception as task_error:
                logger.error(f"[TWILIO:{session_id}] Error creating Twilio task: {str(task_error)}")
                logger.error(f"[TWILIO:{session_id}] Task creation error trace: {traceback.format_exc()}")
            
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
                metrics["events_processed"] += 1
                processed_events += 1
                metrics["last_activity_time"] = current_time
                
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
                    
                # Record the event for debugging
                ws_events.append({
                    "time": current_time,
                    "type": event_type,
                    "event_count": processed_events,
                    "time_since_start": current_time - stream_start_time,
                    "time_since_last": time_since_last
                })
                
                # Log detailed event counts periodically
                if processed_events % 50 == 0 or (event_type in ["silence_detected", "transcript_complete"] and processed_events > 10):
                    logger.info(f"[STREAM:{session_id}] Processed {processed_events} events: {event_counts_str}")
                
                # Handle specific event types using the dedicated handlers
                if event_type == "transcript_complete":
                    await handle_transcript_event(ws, session_id, frontline, event, metrics, event_timing)
                    
                elif event_type == "tool_call":
                    await handle_tool_call_event(ws, session_id, tool_registry, event, metrics)
                    
                elif event_type == "silence_detected":
                    greeting_sent, greeting_timestamp = await handle_silence_event(
                        ws, session_id, frontline, fsm_orchestrator, event_timing, 
                        greeting_sent, greeting_timestamp, metrics
                    )
                    
                elif event_type == "audio":
                    await handle_audio_event(ws, session_id, event, metrics)
                    
                elif event_type == "error":
                    # Handle error events
                    error_msg = event.get("error", "Unknown error")
                    logger.error(f"[STREAM:{session_id}] Received error event: {error_msg}")
                    
                    # Forward error to client
                    await ws.send(json.dumps({
                        "event": "error",
                        "text": error_msg,
                        "timestamp": time.time()
                    }))
                    metrics["events_sent"] += 1
            
            logger.info(f"[STREAM:{session_id}] Media stream processing complete after {processed_events} events")
            
        except Exception as e:
            logger.error(f"[MEDIA_STREAM] ❌ Error in media stream processing: {str(e)}")
            logger.error(f"[MEDIA_STREAM] Processing error trace: {traceback.format_exc()}")
            
            # Try to send error to client
            try:
                await ws.send(json.dumps({
                    "event": "error",
                    "text": f"System error: {str(e)}",
                    "timestamp": time.time()
                }))
            except:
                pass
        
        # Clean up and summarize connection
        try:
            # Cancel keep-alive task if it's running
            if keepalive_task and not keepalive_task.done():
                logger.info(f"[WEBSOCKET:{session_id}] Cancelling keep-alive task")
                keepalive_task.cancel()
                try:
                    await keepalive_task
                except asyncio.CancelledError:
                    pass
            
            # Cancel Twilio task if still running
            if twilio_task and not twilio_task.done():
                logger.info(f"[WEBSOCKET:{session_id}] Cancelling Twilio message processing task")
                twilio_task.cancel()
                try:
                    await twilio_task
                except asyncio.CancelledError:
                    pass
                
            logger.info(f"[WEBSOCKET:{session_id}] WebSocket session complete")
            log_connection_summary("normal_close")
            
        except Exception as cleanup_error:
            logger.error(f"[WEBSOCKET:{session_id}] Error during connection cleanup: {cleanup_error}")
    
    except Exception as e:
        logger.error(f"[WEBSOCKET:{session_id}] ❌ Unhandled error in media stream: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Try to send error to client
        try:
            await ws.send(json.dumps({
                "event": "error",
                "text": f"System error: {str(e)}",
                "timestamp": time.time(),
                "session_id": session_id
            }))
        except:
            pass
            
    finally:
        # Update the WebSocket stats
        try:
            # Calculate the connection duration
            duration = time.time() - metrics.get("connection_start_time", time.time())
            # Record the connection stats
            websocket_stats.connection_closed(
                duration=duration,
                msgs_received=metrics.get("audio_chunks_received", 0) + metrics.get("events_processed", 0),
                msgs_sent=metrics.get("events_sent", 0),
                session_id=session_id
            )
            
            # Log detailed connection stats
            logger.info(f"[WEBSOCKET:{session_id}] Connection stats: "
                      f"duration={duration:.2f}s, "
                      f"messages_received={metrics.get('audio_chunks_received', 0)}, "
                      f"events_processed={metrics.get('events_processed', 0)}, "
                      f"events_sent={metrics.get('events_sent', 0)}")
        except Exception as stats_error:
            logger.error(f"[WEBSOCKET:{session_id}] Error recording stats: {stats_error}")
            
        # Clean up session-specific logging
        try:
            if 'session_file_handler' in locals():
                logger.removeHandler(session_file_handler)
            if 'ws_file_handler' in locals():
                logger.removeHandler(ws_file_handler)
        except:
            pass