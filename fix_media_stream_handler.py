#!/usr/bin/env python3
"""
This script enhances error handling and logging for the WebSocket media stream handler
in the RedBarSushiAI application to diagnose why calls are hanging up after greeting.

The issue:
- WebSocket connections are being established successfully
- The initial greeting is playing 
- But the call is hanging up immediately after
- The cause may be in the media stream processing logic

This script will:
1. Add comprehensive error handling around key areas in the media stream processor
2. Implement detailed logging for all WebSocket events
3. Add timeout protection for critical operations
4. Create a diagnostic mode for detailed troubleshooting
"""

import os
import re
import sys
import traceback

# Define the files to modify
VOICE_REALTIME_FILE = 'app/routes/voice_orchestrated_realtime.py'
REALTIME_AUDIO_FILE = 'app/utils/realtime_audio_sdk.py'

def add_enhanced_error_handling():
    """
    Add enhanced error handling to the media stream handler in 
    voice_orchestrated_realtime.py to catch and log any exceptions.
    """
    if not os.path.exists(VOICE_REALTIME_FILE):
        print(f"Error: {VOICE_REALTIME_FILE} does not exist")
        return False
    
    # Read the file content
    with open(VOICE_REALTIME_FILE, 'r') as f:
        content = f.read()
    
    # Create a backup of the original file
    backup_file = f"{VOICE_REALTIME_FILE}.bak"
    with open(backup_file, 'w') as f:
        f.write(content)
    print(f"Created backup of original file at {backup_file}")
    
    # Identify the media_stream function
    media_stream_pattern = r'@sock\.route\("\/ws\/voice\/media"\)[^@]*?async def media_stream\(ws\):[^}]*?}[^}]*?}[^}]*?}[^}]*?}[^}]*?}'
    
    # Check if function exists
    if not re.search(media_stream_pattern, content, re.DOTALL):
        print("Could not find the media_stream function in the file")
        return False
    
    # Pattern to match the try/except block in media_stream function
    try_except_pattern = r'(async def media_stream\(ws\):.*?try:)(.*?)(except Exception as e:.*?finally:.*?})'
    
    # Prepare the enhanced error handling and improved logging
    enhanced_exception_handling = r'''\1\2except asyncio.TimeoutError as te:
        session_id = "unknown" if 'session_id' not in locals() else session_id
        logger.error(f"[MEDIA_STREAM] ❌ CRITICAL: Timeout error in media stream for session {session_id}: {str(te)}")
        logger.error(f"[MEDIA_STREAM] Timeout stack trace: {traceback.format_exc()}")
        
        # Log detailed environment information
        logger.error(f"[MEDIA_STREAM] Environment information: Python {sys.version}, OS: {sys.platform}")
        logger.error(f"[MEDIA_STREAM] Available environment vars: {[k for k in os.environ.keys() if not any(secret in k.lower() for secret in ['key', 'token', 'secret', 'password'])]}")
        
        # Try to send diagnostic info to client
        try:
            await ws.send(json.dumps({
                "event": "error",
                "error_type": "timeout",
                "text": f"System timeout error: {str(te)}",
                "timestamp": time.time()
            }))
        except:
            logger.error("[MEDIA_STREAM] Could not send timeout error to client")
            
        # Try to perform an emergency cleanup
        try:
            logger.warning("[MEDIA_STREAM] Attempting emergency cleanup after timeout...")
            # Try to cancel any pending tasks
            if 'twilio_task' in locals() and not twilio_task.done():
                twilio_task.cancel()
            
            # Try to log connection summary
            if 'log_connection_summary' in locals():
                log_connection_summary("timeout_error")
        except Exception as cleanup_error:
            logger.error(f"[MEDIA_STREAM] Error during timeout cleanup: {cleanup_error}")
            
    except ConnectionError as ce:
        session_id = "unknown" if 'session_id' not in locals() else session_id
        logger.error(f"[MEDIA_STREAM] ❌ CRITICAL: Connection error in media stream for session {session_id}: {str(ce)}")
        logger.error(f"[MEDIA_STREAM] Connection error trace: {traceback.format_exc()}")
        
        # Try to send diagnostic info to client
        try:
            await ws.send(json.dumps({
                "event": "error",
                "error_type": "connection",
                "text": f"Connection error: {str(ce)}",
                "timestamp": time.time()
            }))
        except:
            pass
            
    except json.JSONDecodeError as je:
        session_id = "unknown" if 'session_id' not in locals() else session_id
        logger.error(f"[MEDIA_STREAM] ❌ JSON decode error in media stream for session {session_id}: {str(je)}")
        logger.error(f"[MEDIA_STREAM] JSON error data: {je.doc[:100]}...")
        logger.error(f"[MEDIA_STREAM] JSON error position: {je.pos}")
        logger.error(f"[MEDIA_STREAM] JSON error trace: {traceback.format_exc()}")
        
        # Try to send diagnostic info to client
        try:
            await ws.send(json.dumps({
                "event": "error",
                "error_type": "json_error",
                "text": f"JSON parsing error: {str(je)}",
                "timestamp": time.time()
            }))
        except:
            pass
            
    \3'''
    
    # Apply the enhanced error handling
    modified_content = re.sub(try_except_pattern, enhanced_exception_handling, content, flags=re.DOTALL)
    
    # Add import for sys module at the top of the file if not already there
    if "import sys" not in modified_content:
        modified_content = modified_content.replace("import os", "import os\nimport sys")
    
    # Add diagnostic info to receive_data function in the main WebSocket handler
    receive_data_pattern = r'(async def receive_data\(ws\):.*?try:)(.*?)(except.*?})'
    enhanced_receive_data = r'''\1
        logger.info("[MEDIA_STREAM] Starting to receive data from WebSocket")
        start_time = time.time()
        last_activity = start_time
        silence_timeout = 20.0  # 20 seconds of silence before logging a warning
        
        # Setup heartbeat for connection monitoring
        heartbeat_interval = 5.0  # 5 seconds between heartbeats
        last_heartbeat = start_time
        \2
        # Update last activity timestamp
        last_activity = time.time()
        
        # Check if we should log a heartbeat
        current_time = time.time()
        if current_time - last_heartbeat >= heartbeat_interval:
            elapsed = current_time - start_time
            logger.info(f"[MEDIA_STREAM] WebSocket receive heartbeat: Connection active for {elapsed:.1f}s")
            last_heartbeat = current_time
            
        # Check for long periods of silence
        if current_time - last_activity >= silence_timeout:
            logger.warning(f"[MEDIA_STREAM] No data received for {silence_timeout:.1f}s - possible connection issue")
            last_activity = current_time  # Reset to avoid spam
        \3'''
    
    modified_content = re.sub(receive_data_pattern, enhanced_receive_data, modified_content, flags=re.DOTALL)
    
    # Add more detailed logging in the process_event function
    process_event_pattern = r'(async def process_events\(ws, event_processor, session_id\):.*?try:)(.*?)(except.*?})'
    enhanced_process_events = r'''\1
        logger.info(f"[MEDIA_STREAM] Starting event processing for session {session_id}")
        event_count = 0
        start_time = time.time()
        last_event_time = start_time
        
        # Track different event types for diagnostics
        event_type_counts = {}
        \2
        # Count this event
        event_count += 1
        event_type = event.get("type", "unknown")
        event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
        
        # Log the event at debug level
        event_size = len(json.dumps(event))
        logger.debug(f"[MEDIA_STREAM] Processing event #{event_count}: type={event_type}, size={event_size}B, t+{time.time()-start_time:.3f}s")
        
        # Update last event time
        last_event_time = time.time()
        
        # Periodically log stats
        if event_count % 50 == 0:
            elapsed = time.time() - start_time
            rate = event_count / elapsed if elapsed > 0 else 0
            logger.info(f"[MEDIA_STREAM] Event processing stats: {event_count} events, {elapsed:.1f}s, {rate:.1f} events/sec")
            logger.info(f"[MEDIA_STREAM] Event type distribution: {event_type_counts}")
        \3'''
    
    modified_content = re.sub(process_event_pattern, enhanced_process_events, modified_content, flags=re.DOTALL)
    
    # Add periodic checks and improved diagnostics in the twilio message handler
    twilio_message_pattern = r'(async def process_twilio_messages\(.*?\):.*?try:)(.*?)(except.*?})'
    enhanced_twilio_handler = r'''\1
        logger.info(f"[MEDIA_STREAM] Starting Twilio message processor")
        twilio_start_time = time.time()
        message_count = 0
        
        # Save the time of key events for diagnostic purposes
        diagnostic_events = {
            "first_audio_received": None,
            "first_transcript_received": None,
            "greeting_sent": None
        }
        \2
        # Count this message
        message_count += 1
        
        # Track key diagnostic events
        if message.get("event") == "media" and diagnostic_events["first_audio_received"] is None:
            diagnostic_events["first_audio_received"] = time.time() - twilio_start_time
            logger.info(f"[MEDIA_STREAM] First audio received after {diagnostic_events['first_audio_received']:.3f}s")
            
        if message.get("event") == "transcript" and diagnostic_events["first_transcript_received"] is None:
            diagnostic_events["first_transcript_received"] = time.time() - twilio_start_time
            logger.info(f"[MEDIA_STREAM] First transcript received after {diagnostic_events['first_transcript_received']:.3f}s")
        
        # Periodically log status
        if message_count % 20 == 0:
            elapsed = time.time() - twilio_start_time
            rate = message_count / elapsed if elapsed > 0 else 0
            logger.info(f"[MEDIA_STREAM] Twilio message stats: {message_count} messages, {elapsed:.1f}s, {rate:.1f} msg/sec")
        \3'''
    
    modified_content = re.sub(twilio_message_pattern, enhanced_twilio_handler, modified_content, flags=re.DOTALL)
    
    # Add a diagnostic keep-alive timer in the main media_stream function
    # to ensure the WebSocket doesn't time out
    keepalive_pattern = r'(async def media_stream\(ws\):.*?# Initialize metrics.*?})'
    enhanced_keepalive = r'''\1
    
    # Setup diagnostic keep-alive timer to prevent timeouts
    async def send_keepalive():
        """Send periodic keep-alive messages to prevent timeouts."""
        keepalive_count = 0
        try:
            while True:
                # Send a keep-alive every 15 seconds
                await asyncio.sleep(15)
                keepalive_count += 1
                logger.debug(f"[MEDIA_STREAM] Sending keep-alive #{keepalive_count}")
                
                try:
                    await ws.send(json.dumps({
                        "event": "keepalive",
                        "count": keepalive_count,
                        "timestamp": time.time()
                    }))
                except Exception as e:
                    logger.warning(f"[MEDIA_STREAM] Failed to send keep-alive #{keepalive_count}: {e}")
                    # If we can't send a keep-alive, the connection might be closed
                    break
        except asyncio.CancelledError:
            logger.debug("[MEDIA_STREAM] Keep-alive task cancelled")
        except Exception as e:
            logger.error(f"[MEDIA_STREAM] Error in keep-alive task: {e}")
    
    # Start the keep-alive timer
    keepalive_task = asyncio.create_task(send_keepalive())
    '''
    
    modified_content = re.sub(keepalive_pattern, enhanced_keepalive, modified_content, flags=re.DOTALL)
    
    # Add cleanup for the keepalive_task in the finally block
    finally_pattern = r'(finally:.*?# Clean up and summarize connection)'
    enhanced_finally = r'''\1
        
        # Cancel keep-alive task if it's running
        if 'keepalive_task' in locals() and not keepalive_task.done():
            logger.info("[MEDIA_STREAM] Cancelling keep-alive task")
            keepalive_task.cancel()
            try:
                await keepalive_task
            except asyncio.CancelledError:
                pass
        '''
    
    modified_content = re.sub(finally_pattern, enhanced_finally, modified_content, flags=re.DOTALL)
    
    # Add debug function to output diagnostic information at runtime
    debug_function = '''

# Add diagnostic debugging function
def diagnostics_output(session_id, context="general"):
    """Output comprehensive diagnostics for troubleshooting."""
    import platform
    import socket
    import psutil
    
    try:
        logger.critical(f"========== VOICE MEDIA DIAGNOSTICS [{context}] ==========")
        logger.critical(f"Session ID: {session_id}")
        logger.critical(f"Timestamp: {time.time()}")
        
        # System info
        logger.critical(f"Python version: {sys.version}")
        logger.critical(f"Platform: {platform.platform()}")
        logger.critical(f"Hostname: {socket.gethostname()}")
        
        # Process info
        process = psutil.Process()
        logger.critical(f"Process ID: {process.pid}")
        logger.critical(f"Process CPU: {process.cpu_percent()}%")
        logger.critical(f"Process memory: {process.memory_info().rss / (1024 * 1024):.1f} MB")
        
        # Network info
        net_connections = process.connections()
        logger.critical(f"Active network connections: {len(net_connections)}")
        
        # Redis connectivity
        try:
            from app.utils.conversation_store import redis_client
            if redis_client and redis_client.ping():
                logger.critical(f"Redis connectivity: OK")
            else:
                logger.critical(f"Redis connectivity: FAILED")
        except Exception as e:
            logger.critical(f"Redis connectivity check error: {e}")
        
        # Database connectivity
        try:
            from app.db import db
            db_ok = False
            with db.engine.connect() as conn:
                result = conn.execute("SELECT 1")
                db_ok = result.scalar() == 1
            logger.critical(f"Database connectivity: {'OK' if db_ok else 'FAILED'}")
        except Exception as e:
            logger.critical(f"Database connectivity check error: {e}")
        
        # Thread info
        import threading
        logger.critical(f"Active threads: {threading.active_count()}")
        
        # Asyncio task info
        try:
            tasks = asyncio.all_tasks()
            logger.critical(f"Active asyncio tasks: {len(tasks)}")
        except Exception as e:
            logger.critical(f"Asyncio task check error: {e}")
        
        logger.critical(f"========== END DIAGNOSTICS ==========")
    except Exception as e:
        logger.error(f"Error generating diagnostics: {e}")
'''
    
    # Add the diagnostics function near the end of the file (before any module-level code)
    if "def diagnostics_output(" not in modified_content:
        last_function_match = re.search(r'^def [^(]+\([^)]+\):', modified_content, re.MULTILINE)
        if last_function_match:
            last_function_pos = modified_content.rindex(last_function_match.group(0))
            # Find the end of this function
            next_def_match = re.search(r'^def [^(]+\([^)]+\):', modified_content[last_function_pos+1:], re.MULTILINE)
            if next_def_match:
                insert_pos = last_function_pos + 1 + next_def_match.start() - 1
            else:
                # No more functions, add before any module-level code at the end
                insert_pos = len(modified_content) - 1
            
            # Insert the diagnostics function
            modified_content = modified_content[:insert_pos] + debug_function + modified_content[insert_pos:]
    
    # Add import for psutil at the top of the file
    if "import psutil" not in modified_content:
        imports_section_end = modified_content.find("# Set up logger")
        if imports_section_end == -1:
            imports_section_end = modified_content.find("# Create Blueprint")
        
        if imports_section_end != -1:
            imports_to_add = "\n# Import for diagnostics\ntry:\n    import psutil\nexcept ImportError:\n    # If psutil is not available, we'll handle it in the diagnostics function\n    pass\n"
            modified_content = modified_content[:imports_section_end] + imports_to_add + modified_content[imports_section_end:]
    
    # Call diagnostics at key points in the media stream handler
    # 1. At the start of the handler
    media_stream_start_pattern = r'(async def media_stream\(ws\):.*?# Initialize metrics.*?})'
    diagnostics_at_start = r'\1\n    # Output diagnostic information at start\n    diagnostics_output("startup", "media_stream_start")\n'
    modified_content = re.sub(media_stream_start_pattern, diagnostics_at_start, modified_content, flags=re.DOTALL)
    
    # 2. Just before processing events
    before_processing_pattern = r'(# Start processing events.*?await process_events)'
    diagnostics_before_processing = r'    # Output diagnostic information before processing\n    diagnostics_output(session_id, "before_processing")\n\1'
    modified_content = re.sub(before_processing_pattern, diagnostics_before_processing, modified_content, flags=re.DOTALL)
    
    # 3. In the exception handler
    exception_pattern = r'(except Exception as e:.*?logger\.error\(f"\[MEDIA_STREAM\] ❌ Error in media stream processing:)'
    diagnostics_in_exception = r'\1\n            # Output diagnostic information on error\n            diagnostics_output("error" if "session_id" not in locals() else session_id, "exception")'
    modified_content = re.sub(exception_pattern, diagnostics_in_exception, modified_content, flags=re.DOTALL)
    
    # Write the modified content back to the file
    with open(VOICE_REALTIME_FILE, 'w') as f:
        f.write(modified_content)
    
    print(f"Enhanced error handling added to {VOICE_REALTIME_FILE}")
    return True

def enhance_realtime_audio_sdk():
    """
    Add improved error handling and logging to the realtime audio SDK.
    """
    if not os.path.exists(REALTIME_AUDIO_FILE):
        print(f"Error: {REALTIME_AUDIO_FILE} does not exist")
        return False
    
    # Read the file content
    with open(REALTIME_AUDIO_FILE, 'r') as f:
        content = f.read()
    
    # Create a backup of the original file
    backup_file = f"{REALTIME_AUDIO_FILE}.bak"
    with open(backup_file, 'w') as f:
        f.write(content)
    print(f"Created backup of original file at {backup_file}")
    
    # Add error handling around the initialization of the real-time processor
    init_pattern = r'(def get_realtime_processor\(.*?\):.*?try:)(.*?)(except Exception as e:.*?})'
    enhanced_init = r'''\1\2except ImportError as ie:
        logger.error(f"❌ CRITICAL: Failed to import OpenAI Realtime dependency: {str(ie)}")
        logger.error(f"Import error traceback: {traceback.format_exc()}")
        logger.error("This may indicate a missing or incompatible package required for real-time audio")
        return None
    except OSError as oe:
        logger.error(f"❌ CRITICAL: OS error initializing OpenAI Realtime client: {str(oe)}")
        logger.error(f"OS error traceback: {traceback.format_exc()}")
        logger.error("This often indicates X11 display server issues in the environment")
        # Print environment information to help diagnose
        logger.error(f"DISPLAY env var: {os.environ.get('DISPLAY', 'Not set')}")
        logger.error(f"HEADLESS env var: {os.environ.get('HEADLESS', 'Not set')}")
        logger.error(f"NO_X11 env var: {os.environ.get('NO_X11', 'Not set')}")
        logger.error(f"OPENAI_REALTIME_NO_DISPLAY env var: {os.environ.get('OPENAI_REALTIME_NO_DISPLAY', 'Not set')}")
        return None
    \3'''
    
    modified_content = re.sub(init_pattern, enhanced_init, content, re.DOTALL)
    
    # Enhance error handling around the DirectWebSocketHandler class
    websocket_handler_pattern = r'(class DirectWebSocketHandler:.*?def __init__\(self.*?\):)(.*?)(def start_session\(self.*?\):)'
    enhanced_websocket_handler = r'''\1\2
    def _log_connection_error(self, e, context="unknown"):
        """Log detailed connection error information."""
        logger.error(f"❌ WebSocket connection error in {context}: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error traceback: {traceback.format_exc()}")
        # Log network environment info
        try:
            import socket
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            logger.error(f"Network info - hostname: {hostname}, IP: {local_ip}")
        except Exception as network_error:
            logger.error(f"Could not get network info: {str(network_error)}")
    
    \3'''
    
    modified_content = re.sub(websocket_handler_pattern, enhanced_websocket_handler, modified_content, re.DOTALL)
    
    # Enhance error handling in the start_session method
    start_session_pattern = r'(async def start_session\(self.*?\):.*?try:)(.*?)(except Exception as e:.*?})'
    enhanced_start_session = r'''\1\2except aiohttp.ClientError as ce:
            logger.error(f"❌ CRITICAL: WebSocket client connection error: {str(ce)}")
            logger.error(f"Client error traceback: {traceback.format_exc()}")
            self._log_connection_error(ce, "start_session:aiohttp")
            return None
        except asyncio.TimeoutError as te:
            logger.error(f"❌ CRITICAL: WebSocket connection timeout: {str(te)}")
            logger.error(f"Timeout traceback: {traceback.format_exc()}")
            self._log_connection_error(te, "start_session:timeout")
            return None
        except ConnectionRefusedError as cre:
            logger.error(f"❌ CRITICAL: WebSocket connection refused: {str(cre)}")
            logger.error(f"Connection refused traceback: {traceback.format_exc()}")
            self._log_connection_error(cre, "start_session:refused")
            return None
        \3'''
    
    modified_content = re.sub(start_session_pattern, enhanced_start_session, modified_content, re.DOTALL)
    
    # Add import for traceback and aiohttp at the top of the file if not already there
    if "import traceback" not in modified_content:
        modified_content = modified_content.replace("import sys", "import sys\nimport traceback")
    
    if "import aiohttp" not in modified_content:
        modified_content = modified_content.replace("import asyncio", "import asyncio\nimport aiohttp")
    
    # Write the modified content back to the file
    with open(REALTIME_AUDIO_FILE, 'w') as f:
        f.write(modified_content)
    
    print(f"Enhanced error handling added to {REALTIME_AUDIO_FILE}")
    return True

def create_endpoint_test_script():
    """
    Create a script to test WebSocket endpoints to verify connectivity.
    """
    test_script_file = 'test_websocket_endpoints.py'
    
    test_script_content = '''#!/usr/bin/env python3
"""
Test script to verify WebSocket connectivity to the RedBarSushiAI API.

This script tests both the media stream WebSocket endpoint and the debug WebSocket
endpoint to diagnose connection issues.
"""

import asyncio
import websockets
import json
import argparse
import sys
import logging
import time
import ssl
import traceback

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

async def test_websocket_endpoint(url, timeout=15, send_data=True, duration=30):
    """
    Test a WebSocket connection to the specified URL.
    
    Args:
        url: The WebSocket URL to connect to
        timeout: Connection timeout in seconds
        send_data: Whether to send test data on the connection
        duration: How long to keep the connection open (in seconds)
        
    Returns:
        True if connection succeeded, False otherwise
    """
    logger.info(f"Attempting to connect to WebSocket at: {url}")
    logger.info(f"Will test for {duration} seconds with {timeout}s connection timeout")
    
    start_time = time.time()
    
    # Disable SSL certificate verification for testing
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    try:
        # Connect with timeout
        async with asyncio.timeout(timeout):
            async with websockets.connect(url, ssl=ssl_context) as websocket:
                logger.info("✅ WebSocket connection established!")
                
                # Track messages
                messages_sent = 0
                messages_received = 0
                
                # Start task to receive messages
                async def receive_messages():
                    nonlocal messages_received
                    while True:
                        try:
                            response = await websocket.recv()
                            messages_received += 1
                            logger.info(f"Received response #{messages_received}")
                            try:
                                parsed = json.loads(response)
                                event_type = parsed.get("event", "unknown")
                                logger.info(f"Event type: {event_type}")
                            except:
                                logger.info(f"Raw message: {response[:100]}{'...' if len(response) > 100 else ''}")
                        except asyncio.TimeoutError:
                            logger.warning("Timeout waiting for message")
                        except Exception as e:
                            logger.error(f"Error receiving message: {e}")
                            break
                
                # Start the receive task
                receive_task = asyncio.create_task(receive_messages())
                
                # Keep sending messages periodically if requested
                if send_data:
                    message_interval = 3  # seconds between messages
                    last_sent = 0
                    
                    while time.time() - start_time < duration:
                        current_time = time.time()
                        
                        # Send a message every few seconds
                        if current_time - last_sent >= message_interval:
                            try:
                                message = {
                                    "type": "test",
                                    "message": f"Test message #{messages_sent+1}",
                                    "timestamp": current_time
                                }
                                await websocket.send(json.dumps(message))
                                messages_sent += 1
                                logger.info(f"Sent message #{messages_sent}")
                                last_sent = current_time
                            except Exception as e:
                                logger.error(f"Error sending message: {e}")
                                break
                        
                        # Sleep a bit to avoid tight loop
                        await asyncio.sleep(0.5)
                else:
                    # Just keep the connection open for the requested duration
                    logger.info(f"Keeping connection open for {duration} seconds")
                    await asyncio.sleep(duration)
                
                # Cancel the receive task
                receive_task.cancel()
                try:
                    await receive_task
                except asyncio.CancelledError:
                    pass
                
                # Report results
                elapsed = time.time() - start_time
                logger.info(f"Test completed after {elapsed:.1f} seconds")
                logger.info(f"Messages sent: {messages_sent}")
                logger.info(f"Messages received: {messages_received}")
                
                return True
                
    except asyncio.TimeoutError:
        logger.error(f"❌ Connection timed out after {timeout} seconds")
        return False
    except ConnectionRefusedError:
        logger.error("❌ Connection refused - server may not be running or port is incorrect")
        return False
    except websockets.exceptions.InvalidStatusCode as e:
        logger.error(f"❌ Invalid status code: {e}")
        if "403" in str(e):
            logger.error("Received 403 Forbidden - this often indicates WebSocket connection was rejected")
        elif "404" in str(e):
            logger.error("Received 404 Not Found - the WebSocket endpoint URL was not found")
        elif "426" in str(e):
            logger.error("Received 426 Upgrade Required - this endpoint requires a WebSocket upgrade")
        elif "401" in str(e):
            logger.error("Received 401 Unauthorized - authentication required")
        return False
    except Exception as e:
        logger.error(f"❌ Error connecting to WebSocket: {e}")
        logger.error(f"Error trace: {traceback.format_exc()}")
        return False

async def test_media_stream(media_url, debug_url=None, timeout=15, duration=30):
    """Test both normal and debug WebSocket endpoints."""
    # First try the debug endpoint if provided
    if debug_url:
        logger.info("===== TESTING DEBUG WEBSOCKET ENDPOINT =====")
        debug_success = await test_websocket_endpoint(debug_url, timeout, True, duration)
        logger.info(f"Debug endpoint test result: {'SUCCESS' if debug_success else 'FAILED'}")
    
    # Then try the media stream endpoint
    logger.info("===== TESTING MEDIA STREAM WEBSOCKET ENDPOINT =====")
    media_success = await test_websocket_endpoint(media_url, timeout, True, duration)
    logger.info(f"Media stream endpoint test result: {'SUCCESS' if media_success else 'FAILED'}")
    
    return debug_url is None or debug_success, media_success

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Test WebSocket connectivity for RedBarSushiAI")
    parser.add_argument("--url", default="wss://redbarsushiai-staging.onrender.com/ws/voice/media", 
                      help="Media stream WebSocket URL to test")
    parser.add_argument("--debug-url", default="wss://redbarsushiai-staging.onrender.com/ws/voice/debug",
                      help="Debug WebSocket URL to test (optional)")
    parser.add_argument("--timeout", type=int, default=15,
                      help="Connection timeout in seconds")
    parser.add_argument("--duration", type=int, default=30,
                      help="How long to keep the connection open (in seconds)")
    parser.add_argument("--no-debug", action="store_true",
                      help="Skip testing the debug endpoint")
    
    args = parser.parse_args()
    
    debug_url = None if args.no_debug else args.debug_url
    
    # Run the tests
    debug_result, media_result = asyncio.run(
        test_media_stream(args.url, debug_url, args.timeout, args.duration)
    )
    
    # Exit with appropriate status code
    if debug_url is None:
        # Only checking media endpoint
        sys.exit(0 if media_result else 1)
    else:
        # Checking both endpoints
        sys.exit(0 if debug_result and media_result else 1)

if __name__ == "__main__":
    main()
'''
    
    with open(test_script_file, 'w') as f:
        f.write(test_script_content)
    
    # Make the script executable
    os.chmod(test_script_file, 0o755)
    
    print(f"Created WebSocket endpoint test script: {test_script_file}")
    return True

if __name__ == "__main__":
    print("Enhancing error handling for RedBarSushiAI WebSocket media stream...")
    
    # Apply fixes
    voice_realtime_fixed = add_enhanced_error_handling()
    audio_sdk_fixed = enhance_realtime_audio_sdk()
    test_script_created = create_endpoint_test_script()
    
    if voice_realtime_fixed and audio_sdk_fixed and test_script_created:
        print("\nSuccessfully enhanced error handling and diagnostics!")
        print("\nNext steps:")
        print("1. Commit these changes with: git add app/routes/voice_orchestrated_realtime.py app/utils/realtime_audio_sdk.py test_websocket_endpoints.py && git commit -m 'Add enhanced error handling for WebSocket media stream'")
        print("2. Push the changes to the staging branch: git push origin staging")
        print("3. Wait for the changes to deploy, then call the staging number and check logs")
        print("4. Run the test script to verify WebSocket connectivity: ./test_websocket_endpoints.py")
        sys.exit(0)
    else:
        print("\nFailed to apply some enhancements. Please check the errors above.")
        sys.exit(1)