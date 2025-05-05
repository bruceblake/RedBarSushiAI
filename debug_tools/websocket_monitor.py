#!/usr/bin/env python3
"""
WebSocket Connection Monitor for RedBarSushiAI.

This script creates a WebSocket client that connects to your voice media endpoint,
monitors all messages, and logs detailed diagnostics to help debug connection issues.
It specifically focuses on the post-greeting disconnection problem.

Usage:
    python websocket_monitor.py --url wss://redbarsushiai-staging.onrender.com/ws/voice/media
"""

import asyncio
import websockets
import json
import time
import argparse
import logging
import traceback
import sys
import base64
import ssl
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('websocket_monitor.log')
    ]
)
logger = logging.getLogger("websocket_monitor")

# Connection statistics
connection_stats = {
    "connection_time": None,
    "last_message_time": None,
    "messages_sent": 0,
    "messages_received": 0,
    "heartbeats_sent": 0,
    "greeting_detected": False,
    "greeting_time": None,
    "post_greeting_messages": 0
}

# Message log
message_log = []

async def send_heartbeat(websocket):
    """Send a heartbeat message to keep the connection alive."""
    try:
        heartbeat = {
            "type": "heartbeat",
            "timestamp": time.time(),
            "client_id": "debug_monitor"
        }
        await websocket.send(json.dumps(heartbeat))
        connection_stats["heartbeats_sent"] += 1
        connection_stats["messages_sent"] += 1
        connection_stats["last_message_time"] = time.time()
        logger.info(f"✓ SENT HEARTBEAT #{connection_stats['heartbeats_sent']}")
        return True
    except Exception as e:
        logger.error(f"✗ HEARTBEAT ERROR: {str(e)}")
        
        # Try an alternative format
        try:
            alt_heartbeat = {
                "event": "ping",
                "timestamp": time.time()
            }
            await websocket.send(json.dumps(alt_heartbeat))
            connection_stats["messages_sent"] += 1
            connection_stats["last_message_time"] = time.time()
            logger.info(f"✓ SENT ALT PING")
            return True
        except Exception as alt_e:
            logger.error(f"✗ ALT PING ERROR: {str(alt_e)}")
            return False

async def send_connection_keep_alive(websocket):
    """Send a keep-alive message with a different format."""
    try:
        keep_alive = {
            "type": "connection_keep_alive",
            "message": "Keeping connection alive",
            "timestamp": time.time()
        }
        await websocket.send(json.dumps(keep_alive))
        connection_stats["messages_sent"] += 1
        connection_stats["last_message_time"] = time.time()
        logger.info(f"✓ SENT KEEP-ALIVE")
        return True
    except Exception as e:
        logger.error(f"✗ KEEP-ALIVE ERROR: {str(e)}")
        return False

async def simulate_user_response(websocket):
    """Simulate a user response after greeting."""
    try:
        user_response = {
            "event": "user_input",
            "text": "I'd like to order some sushi please",
            "timestamp": time.time()
        }
        await websocket.send(json.dumps(user_response))
        connection_stats["messages_sent"] += 1
        connection_stats["last_message_time"] = time.time()
        logger.info(f"✓ SENT USER RESPONSE: {user_response['text']}")
        return True
    except Exception as e:
        logger.error(f"✗ USER RESPONSE ERROR: {str(e)}")
        return False

def log_message(direction, message_type, data):
    """Log a message with standard formatting."""
    timestamp = datetime.now().isoformat()
    
    # Format data for logging
    if isinstance(data, bytes):
        formatted_data = f"<{len(data)} bytes of binary data>"
    elif isinstance(data, str):
        try:
            parsed = json.loads(data)
            formatted_data = json.dumps(parsed, indent=2)
        except:
            formatted_data = data
    else:
        try:
            formatted_data = json.dumps(data, indent=2)
        except:
            formatted_data = str(data)
    
    # Log with appropriate arrow
    arrow = "→" if direction == "SENT" else "←"
    logger.info(f"{arrow} {message_type}: {formatted_data}")
    
    # Add to message log
    message_log.append({
        "timestamp": timestamp,
        "direction": direction,
        "type": message_type,
        "data": data
    })
    
    # Check for greeting messages
    if not connection_stats["greeting_detected"] and message_type in ["agent_response", "speech"] and direction == "RECEIVED":
        # Look for greeting indicators
        is_greeting = False
        if isinstance(data, dict):
            is_greeting = data.get("is_greeting", False)
            if not is_greeting and data.get("text", "").lower().startswith("welcome"):
                is_greeting = True
        elif isinstance(data, str):
            lower_data = data.lower()
            if "welcome" in lower_data or "greeting" in lower_data:
                is_greeting = True
                
        if is_greeting:
            connection_stats["greeting_detected"] = True
            connection_stats["greeting_time"] = time.time()
            logger.info(f"★ GREETING DETECTED at {timestamp}")

def calculate_time_since(timestamp):
    """Calculate human-readable time since a timestamp."""
    if not timestamp:
        return "never"
    
    seconds = time.time() - timestamp
    if seconds < 60:
        return f"{seconds:.1f} seconds ago"
    minutes = seconds / 60
    return f"{minutes:.1f} minutes ago"

async def monitor_connection(url, heartbeat_interval=5.0):
    """
    Monitor a WebSocket connection to the specified URL.
    
    Args:
        url: The WebSocket URL to connect to
        heartbeat_interval: Interval in seconds between heartbeats
    """
    # Set up SSL context (don't verify for testing)
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    try:
        logger.info(f"Connecting to {url}")
        
        # Connect to the WebSocket
        logger.critical(f"Attempting connection with debug tracing enabled...")
        
        # Add subprotocols to match what the server might expect
        possible_subprotocols = ["twilio-media-stream", "json", "text"]
        logger.critical(f"Trying with subprotocols: {possible_subprotocols}")
        
        # Create connection options based on websockets version
        connect_kwargs = {
            "ssl": ssl_context,
            "subprotocols": possible_subprotocols
        }
        
        # Try to establish connection with proper options
        async with websockets.connect(url, **connect_kwargs) as websocket:
            logger.critical(f"✓ CONNECTED to {url}")
            connection_stats["connection_time"] = time.time()
            connection_stats["last_message_time"] = time.time()
            
            # Get and log connection attributes
            try:
                subprotocol = getattr(websocket, "subprotocol", None)
                logger.critical(f"Connection attributes: subprotocol={subprotocol}")
            except Exception as e:
                logger.critical(f"Error getting connection attributes: {e}")
            
            # Wait for initial messages from server
            logger.critical(f"Waiting for initial server messages (if any)...")
            try:
                # Try to receive with a short timeout - we may get an initial message
                initial_msg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                logger.critical(f"RECEIVED INITIAL MESSAGE: {initial_msg[:500]}")
            except asyncio.TimeoutError:
                logger.critical(f"No initial message received (2s timeout) - this is normal if server expects client to send first")
            except Exception as e:
                logger.critical(f"Error receiving initial message: {e}")
                
            # Try different message formats to see which one works
            logger.critical(f"Testing different message formats...")
            
            # First try a simple text message
            try:
                logger.critical(f"Sending plain text message...")
                await websocket.send("hello")
                logger.critical(f"✓ Plain text message sent")
                
                # Try to receive a response
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    logger.critical(f"RECEIVED RESPONSE TO TEXT: {response[:500]}")
                except asyncio.TimeoutError:
                    logger.critical(f"No response to plain text message (2s timeout)")
                except Exception as e:
                    logger.critical(f"Error receiving response to text: {e}")
            except Exception as e:
                logger.critical(f"✗ Failed to send plain text: {e}")
                
            # Then try a JSON message with Twilio-like structure
            try:
                logger.critical(f"Sending Twilio-like JSON message...")
                twilio_msg = {
                    "event": "start",
                    "streamSid": "MT" + "".join([str(i) for i in range(32)]),
                    "accountSid": "AC" + "".join([str(i) for i in range(32)]),
                    "callSid": "CA" + "".join([str(i) for i in range(32)])
                }
                await websocket.send(json.dumps(twilio_msg))
                logger.critical(f"✓ Twilio-like JSON message sent")
                
                # Try to receive a response
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    logger.critical(f"RECEIVED RESPONSE TO TWILIO JSON: {response[:500]}")
                except asyncio.TimeoutError:
                    logger.critical(f"No response to Twilio JSON (2s timeout)")
                except Exception as e:
                    logger.critical(f"Error receiving response to Twilio JSON: {e}")
            except Exception as e:
                logger.critical(f"✗ Failed to send Twilio JSON: {e}")
            
            # Now try sending a standard heartbeat
            await send_heartbeat(websocket)
            
            # Main monitoring loop
            heartbeat_count = 1
            last_heartbeat_time = time.time()
            last_status_time = time.time()
            post_greeting_keep_alive_sent = False
            simulated_response_sent = False
            
            while True:
                try:
                    # Set up two tasks:
                    # 1. Receive messages
                    # 2. Check if we need to send a heartbeat
                    receive_task = asyncio.create_task(websocket.recv())
                    
                    # Wait for either a message or the heartbeat interval
                    done, pending = await asyncio.wait(
                        [receive_task],
                        timeout=1.0,  # Check every second for timeouts and status updates
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    
                    current_time = time.time()
                    
                    if receive_task in done:
                        # We received a message
                        message = receive_task.result()
                        connection_stats["messages_received"] += 1
                        connection_stats["last_message_time"] = current_time
                        
                        # Try to determine message type
                        message_type = "unknown"
                        message_data = message
                        
                        try:
                            # Parse JSON messages
                            if isinstance(message, str):
                                data = json.loads(message)
                                message_data = data
                                message_type = data.get("type") or data.get("event", "unknown")
                                
                                # If this is a greeting response
                                if connection_stats["greeting_detected"]:
                                    connection_stats["post_greeting_messages"] += 1
                        except:
                            # Not JSON, just use as is
                            pass
                            
                        # Log the received message
                        log_message("RECEIVED", message_type, message_data)
                        
                        # After greeting detection, track messages
                        if connection_stats["greeting_detected"] and not post_greeting_keep_alive_sent:
                            logger.info(f"★ First message after greeting detected")
                            
                            # Send a keep-alive message after greeting
                            post_greeting_keep_alive_sent = True
                            await send_connection_keep_alive(websocket)
                            
                            # Schedule another keep-alive in 2 seconds
                            asyncio.create_task(
                                send_delayed_keep_alive(websocket, 2.0)
                            )
                            
                        # If we detected greeting and haven't sent simulated response
                        if connection_stats["greeting_detected"] and not simulated_response_sent:
                            # Wait a moment before responding
                            await asyncio.sleep(1.0)
                            simulated_response_sent = True
                            await simulate_user_response(websocket)
                    
                    else:
                        # No message received, cancel the receive task
                        receive_task.cancel()
                        
                        # Check if it's time for heartbeat
                        time_since_heartbeat = current_time - last_heartbeat_time
                        if time_since_heartbeat >= heartbeat_interval:
                            await send_heartbeat(websocket)
                            last_heartbeat_time = current_time
                            heartbeat_count += 1
                        
                        # Check if it's time for status update (every 5 seconds)
                        time_since_status = current_time - last_status_time
                        if time_since_status >= 5.0:
                            # Print connection status
                            time_connected = current_time - connection_stats["connection_time"]
                            logger.info(f"STATUS after {time_connected:.1f}s:")
                            logger.info(f"  • Last message: {calculate_time_since(connection_stats['last_message_time'])}")
                            logger.info(f"  • Messages received: {connection_stats['messages_received']}")
                            logger.info(f"  • Messages sent: {connection_stats['messages_sent']}")
                            logger.info(f"  • Heartbeats sent: {connection_stats['heartbeats_sent']}")
                            
                            if connection_stats["greeting_detected"]:
                                time_since_greeting = current_time - connection_stats["greeting_time"]
                                logger.info(f"  • Greeting detected: {time_since_greeting:.1f}s ago")
                                logger.info(f"  • Post-greeting messages: {connection_stats['post_greeting_messages']}")
                            else:
                                logger.info(f"  • Greeting detected: No")
                            
                            last_status_time = current_time
                        
                        # Check for connection timeout (30 seconds without messages)
                        time_since_last_message = current_time - connection_stats["last_message_time"]
                        if time_since_last_message > 30.0:
                            logger.warning(f"⚠ No messages for {time_since_last_message:.1f} seconds!")
                            
                            # Try to send a keep-alive
                            if await send_connection_keep_alive(websocket):
                                logger.info("✓ Sent emergency keep-alive")
                            else:
                                logger.error("✗ Failed to send emergency keep-alive, connection may be dead")
                    
                except asyncio.CancelledError:
                    logger.info("☒ Connection monitoring cancelled")
                    break
                    
                except websockets.exceptions.ConnectionClosedError as e:
                    logger.error(f"☒ Connection closed with error: {e.code} - {e.reason}")
                    
                    # Log connection stats at time of closure
                    final_stats = connection_stats.copy()
                    final_stats["disconnection_time"] = time.time()
                    if connection_stats["connection_time"]:
                        final_stats["connection_duration"] = final_stats["disconnection_time"] - connection_stats["connection_time"]
                    
                    if connection_stats["greeting_time"]:
                        final_stats["time_from_greeting_to_disconnection"] = final_stats["disconnection_time"] - connection_stats["greeting_time"]
                    
                    logger.info(f"FINAL STATS: {json.dumps(final_stats, indent=2)}")
                    break
                    
                except websockets.exceptions.ConnectionClosedOK:
                    logger.info("☒ Connection closed normally")
                    break
                    
                except Exception as e:
                    logger.error(f"☒ Error in connection monitoring: {str(e)}")
                    logger.error(traceback.format_exc())
                    break
                    
    except Exception as e:
        logger.error(f"☒ Failed to connect: {str(e)}")
        logger.error(traceback.format_exc())

async def send_delayed_keep_alive(websocket, delay):
    """Send a keep-alive message after delay seconds."""
    await asyncio.sleep(delay)
    await send_connection_keep_alive(websocket)
    logger.info(f"✓ SENT DELAYED KEEP-ALIVE after {delay}s")
    
    # Schedule additional keep-alives to maintain connection
    for i in range(1, 5):  # Send 4 more keep-alives
        await asyncio.sleep(2.0)  # Every 2 seconds
        try:
            await send_connection_keep_alive(websocket)
            logger.info(f"✓ SENT FOLLOW-UP KEEP-ALIVE #{i}")
        except Exception as e:
            logger.error(f"✗ FOLLOW-UP KEEP-ALIVE ERROR: {str(e)}")

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="WebSocket Connection Monitor for RedBarSushiAI")
    parser.add_argument("--url", type=str, default="wss://redbarsushiai-staging.onrender.com/ws/voice/media",
                       help="WebSocket URL to monitor")
    parser.add_argument("--heartbeat-interval", type=float, default=5.0,
                       help="Interval in seconds between heartbeats")
    parser.add_argument("--verbose", action="store_true",
                       help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        
    logger.info("Starting WebSocket Connection Monitor")
    logger.info(f"Target URL: {args.url}")
    logger.info(f"Heartbeat interval: {args.heartbeat_interval}s")
    
    try:
        # Run the async monitor
        asyncio.run(monitor_connection(args.url, args.heartbeat_interval))
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        logger.error(traceback.format_exc())
    
    logger.info("WebSocket Connection Monitor exited")

if __name__ == "__main__":
    main()