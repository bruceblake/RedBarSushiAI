#!/usr/bin/env python3
"""
WebSocket Stability Test Client for RedBarSushiAI

This script tests the stability of WebSocket connections, particularly focusing
on the post-greeting phase where disconnections have been occurring. It connects
to a local test server, simulates a Twilio client, and monitors for disconnections.

Usage:
    python websocket_stability_client.py [--url URL] [--duration SECONDS]
"""

import asyncio
import websockets
import json
import time
import argparse
import logging
import sys
import ssl
import uuid
import signal
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('websocket_stability_client.log')
    ]
)
logger = logging.getLogger("websocket_stability_client")

# Connection statistics
connection_stats = {
    "connection_time": None,
    "last_message_time": None,
    "messages_sent": 0,
    "messages_received": 0,
    "keep_alives_sent": 0,
    "greeting_detected": False,
    "greeting_time": None,
    "post_greeting_messages": 0,
    "disconnection_time": None,
    "disconnection_reason": None,
    "connection_id": None
}

# Status flags
should_exit = False

def handle_interrupt(signum, frame):
    """Handle keyboard interrupt for graceful shutdown."""
    global should_exit
    logger.info("Received interrupt signal - scheduling shutdown")
    should_exit = True

# Set up signal handler
signal.signal(signal.SIGINT, handle_interrupt)

async def send_keep_alive(websocket, session_id):
    """Send a keep-alive message to the WebSocket."""
    try:
        keep_alive = {
            "type": "keep_alive",
            "timestamp": time.time(),
            "client_session_id": session_id,
            "test_id": str(uuid.uuid4())[:8]
        }
        await websocket.send(json.dumps(keep_alive))
        connection_stats["keep_alives_sent"] += 1
        connection_stats["messages_sent"] += 1
        connection_stats["last_message_time"] = time.time()
        logger.info(f"✅ Sent keep-alive #{connection_stats['keep_alives_sent']}")
        return True
    except Exception as e:
        logger.error(f"❌ Keep-alive error: {str(e)}")
        return False

async def send_twilio_start(websocket, session_id):
    """Send a Twilio start message to initiate the session."""
    try:
        start_msg = {
            "event": "start",
            "streamSid": f"MT{session_id}123456789012345678901234",
            "accountSid": f"AC{session_id}123456789012345678901234",
            "callSid": f"CA{session_id}123456789012345678901234",
            "tracks": ["inbound_track", "both_tracks"],
            "mediaFormat": {
                "encoding": "audio/x-mulaw",
                "sampleRate": 8000,
                "channels": 1
            }
        }
        
        logger.info(f"Sending Twilio start message with call SID: CA{session_id}...")
        await websocket.send(json.dumps(start_msg))
        connection_stats["messages_sent"] += 1
        connection_stats["last_message_time"] = time.time()
        logger.info(f"✅ Twilio start message sent")
        return True
    except Exception as e:
        logger.error(f"❌ Twilio start message error: {str(e)}")
        return False

async def simulate_audio_data(websocket, session_id):
    """Send simulated audio data to the WebSocket."""
    try:
        # Create dummy audio data - 20ms of silence
        audio_data = "AAAAAAAAAAAAAAAAAAAAAA=="
        
        media_msg = {
            "event": "media",
            "streamSid": f"MT{session_id}123456789012345678901234",
            "trackSid": "inbound_track",
            "chunk": {
                "timestamp": time.time() * 1000  # ms since epoch
            },
            "media": {
                "payload": audio_data,
                "track": "inbound_track"
            }
        }
        
        await websocket.send(json.dumps(media_msg))
        connection_stats["messages_sent"] += 1
        connection_stats["last_message_time"] = time.time()
        return True
    except Exception as e:
        logger.error(f"❌ Audio data error: {str(e)}")
        return False

async def simulate_user_response(websocket, session_id, message="I'd like to order some sushi please"):
    """Simulate a user response after greeting."""
    try:
        user_response = {
            "event": "user_input",
            "text": message,
            "timestamp": time.time(),
            "client_session_id": session_id
        }
        await websocket.send(json.dumps(user_response))
        connection_stats["messages_sent"] += 1
        connection_stats["last_message_time"] = time.time()
        logger.info(f"✅ Sent user response: {message}")
        return True
    except Exception as e:
        logger.error(f"❌ User response error: {str(e)}")
        return False

async def test_connection(url, duration=300):
    """
    Test WebSocket connection stability.
    
    Args:
        url: The WebSocket URL to connect to
        duration: Test duration in seconds
    """
    global should_exit
    
    session_id = str(uuid.uuid4())[:12]
    logger.info(f"Starting WebSocket stability test for {duration}s")
    logger.info(f"Test session ID: {session_id}")
    logger.info(f"Target URL: {url}")
    
    # Set up SSL context for secure WebSockets
    ssl_context = None
    if url.startswith("wss://"):
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
    
    try:
        # Connect to the WebSocket
        logger.info(f"Connecting to {url}...")
        
        connect_kwargs = {
            "subprotocols": ["twilio-media-stream"]
        }
        
        if ssl_context:
            connect_kwargs["ssl"] = ssl_context
        
        async with websockets.connect(url, **connect_kwargs) as websocket:
            logger.info(f"✅ Connected successfully")
            connection_stats["connection_time"] = time.time()
            connection_stats["last_message_time"] = time.time()
            
            # Time tracking
            start_time = time.time()
            last_keep_alive = start_time
            last_status = start_time
            last_audio = start_time
            greeting_responded = False
            audio_sequence_count = 0
            
            # Send initial Twilio start message
            if not await send_twilio_start(websocket, session_id):
                logger.error("Failed to send initial Twilio start message, aborting test")
                return False
            
            # Main test loop
            while time.time() - start_time < duration and not should_exit:
                try:
                    # Try to receive a message with timeout
                    receive_task = asyncio.create_task(websocket.recv())
                    try:
                        done, pending = await asyncio.wait(
                            [receive_task],
                            timeout=1.0,
                            return_when=asyncio.FIRST_COMPLETED
                        )
                        
                        current_time = time.time()
                        
                        if receive_task in done:
                            # Message received
                            message = receive_task.result()
                            connection_stats["messages_received"] += 1
                            connection_stats["last_message_time"] = current_time
                            
                            # Try to parse JSON message
                            try:
                                data = json.loads(message)
                                message_type = data.get("type") or data.get("event", "unknown")
                                
                                # Check for connection ID in welcome message
                                if message_type == "connected" and "connection_id" in data:
                                    connection_stats["connection_id"] = data["connection_id"]
                                    logger.info(f"✅ Connection established with ID: {connection_stats['connection_id']}")
                                
                                # Check for greeting
                                is_greeting = False
                                if "text" in data:
                                    text = data.get("text", "").lower()
                                    is_greeting = (
                                        data.get("is_greeting", False) or
                                        "welcome" in text or
                                        "how can i help" in text
                                    )
                                
                                if is_greeting and not connection_stats["greeting_detected"]:
                                    connection_stats["greeting_detected"] = True
                                    connection_stats["greeting_time"] = current_time
                                    logger.info(f"🎉 GREETING DETECTED: '{data.get('text', '')}'")
                                    logger.info(f"Time since connection: {current_time - start_time:.2f}s")
                                    
                                    # Schedule a user response to the greeting after a short delay
                                    await asyncio.sleep(1.0)  # Wait a moment before responding
                                    greeting_responded = True
                                    await simulate_user_response(websocket, session_id)
                                
                                # Track post-greeting messages
                                if connection_stats["greeting_detected"]:
                                    connection_stats["post_greeting_messages"] += 1
                                    
                                # Log received message (limit frequency)
                                if connection_stats["messages_received"] % 10 == 0 or message_type != "heartbeat":
                                    message_preview = str(data)[:100] + "..." if len(str(data)) > 100 else str(data)
                                    logger.info(f"📥 Received {message_type}: {message_preview}")
                            except json.JSONDecodeError:
                                # Not JSON, log as raw
                                message_preview = message[:100] + "..." if len(message) > 100 else message
                                logger.info(f"📥 Received raw message: {message_preview}")
                        else:
                            # No message received, cancel the task
                            for task in pending:
                                task.cancel()
                            
                            # Check if we need to send keep-alive (every 5 seconds)
                            if current_time - last_keep_alive >= 5.0:
                                await send_keep_alive(websocket, session_id)
                                last_keep_alive = current_time
                            
                            # Send periodic audio data (every 200ms to simulate real-time audio)
                            if current_time - last_audio >= 0.2:
                                # Only send audio if we've received a greeting and responded to it
                                if connection_stats["greeting_detected"] and greeting_responded:
                                    await simulate_audio_data(websocket, session_id)
                                    last_audio = current_time
                                    audio_sequence_count += 1
                                    
                                    # After sending several audio chunks, send another user message
                                    if audio_sequence_count >= 15:  # After about 3 seconds of audio
                                        await simulate_user_response(websocket, session_id, 
                                                                    "I'd like to order a California roll and some miso soup")
                                        audio_sequence_count = 0
                            
                            # Print status update every 10 seconds
                            if current_time - last_status >= 10.0:
                                elapsed = current_time - start_time
                                logger.info(f"⏱️ STATUS at {elapsed:.1f}s:")
                                logger.info(f"  • Connection ID: {connection_stats['connection_id'] or 'unknown'}")
                                logger.info(f"  • Messages received: {connection_stats['messages_received']}")
                                logger.info(f"  • Messages sent: {connection_stats['messages_sent']}")
                                logger.info(f"  • Keep-alives sent: {connection_stats['keep_alives_sent']}")
                                
                                if connection_stats["greeting_detected"]:
                                    greeting_age = current_time - connection_stats["greeting_time"]
                                    logger.info(f"  • Time since greeting: {greeting_age:.1f}s")
                                    logger.info(f"  • Post-greeting messages: {connection_stats['post_greeting_messages']}")
                                
                                # Calculate approximate remaining time
                                remaining = duration - elapsed
                                logger.info(f"  • Test will complete in approximately {remaining:.1f}s")
                                
                                last_status = current_time
                                
                            # Check for connection timeout (10 seconds without messages)
                            time_since_last_message = current_time - connection_stats["last_message_time"]
                            if time_since_last_message > 10.0:
                                logger.warning(f"⚠️ No messages received for {time_since_last_message:.1f}s!")
                    
                    except asyncio.TimeoutError:
                        # This is expected - we use the timeout to check if we need to do other things
                        pass
                
                except asyncio.CancelledError:
                    logger.info("Test cancelled by user")
                    break
                
                except websockets.exceptions.ConnectionClosedError as e:
                    connection_stats["disconnection_time"] = time.time()
                    connection_stats["disconnection_reason"] = f"Code: {e.code}, Reason: {e.reason}"
                    logger.error(f"❌ Connection closed with error: {e.code} - {e.reason}")
                    break
                
                except websockets.exceptions.ConnectionClosedOK:
                    connection_stats["disconnection_time"] = time.time()
                    connection_stats["disconnection_reason"] = "Normal closure"
                    logger.info("Connection closed normally")
                    break
                
                except Exception as e:
                    logger.error(f"Error during test: {str(e)}")
                    logger.error(traceback.format_exc())
                    continue
            
            # Test completed successfully!
            if time.time() - start_time >= duration:
                logger.info(f"✅ Test completed successfully after {duration}s")
            elif should_exit:
                logger.info("Test interrupted by user")
            
    except Exception as e:
        logger.error(f"❌ Connection failed: {str(e)}")
        logger.error(traceback.format_exc())
        connection_stats["disconnection_reason"] = f"Connection attempt failed: {str(e)}"
    
    # Calculate final statistics
    connection_time = connection_stats.get("connection_time")
    disconnection_time = connection_stats.get("disconnection_time") or time.time()
    
    if connection_time:
        connection_stats["connection_duration"] = disconnection_time - connection_time
        logger.info(f"Connection duration: {connection_stats['connection_duration']:.2f}s")
    
    greeting_time = connection_stats.get("greeting_time")
    if greeting_time:
        time_to_greeting = greeting_time - connection_time
        connection_stats["time_to_greeting"] = time_to_greeting
        logger.info(f"Time until greeting: {time_to_greeting:.2f}s")
        
        post_greeting_duration = disconnection_time - greeting_time
        connection_stats["post_greeting_duration"] = post_greeting_duration
        logger.info(f"Post-greeting duration: {post_greeting_duration:.2f}s")
    
    # Final report
    logger.info("\n=== FINAL REPORT ===")
    logger.info(f"Test completed at:    {datetime.now().isoformat()}")
    logger.info(f"Total test duration:  {disconnection_time - start_time:.2f}s")
    logger.info(f"Connection success:   {'Yes' if connection_time else 'No'}")
    
    if connection_time:
        logger.info(f"Connection duration:  {connection_stats['connection_duration']:.2f}s")
        logger.info(f"Messages received:    {connection_stats['messages_received']}")
        logger.info(f"Messages sent:        {connection_stats['messages_sent']}")
        logger.info(f"Keep-alives sent:     {connection_stats['keep_alives_sent']}")
        logger.info(f"Greeting detected:    {'Yes' if connection_stats['greeting_detected'] else 'No'}")
        
        if connection_stats["greeting_detected"]:
            logger.info(f"Time to greeting:     {connection_stats['time_to_greeting']:.2f}s")
            logger.info(f"Post-greeting msgs:   {connection_stats['post_greeting_messages']}")
            logger.info(f"Post-greeting time:   {connection_stats['post_greeting_duration']:.2f}s")
        
        logger.info(f"Disconnection reason: {connection_stats['disconnection_reason'] or 'Test completed'}")
    
    # Overall test result
    if connection_time and connection_stats.get("greeting_detected") and connection_stats.get("post_greeting_duration", 0) > 10:
        logger.info("\n✅ TEST PASSED: Connection remained stable after greeting")
        return True
    elif connection_time and not connection_stats.get("greeting_detected") and connection_stats.get("connection_duration", 0) > duration * 0.9:
        logger.info("\n⚠️ TEST INCONCLUSIVE: Connection stable but no greeting detected")
        return None
    else:
        logger.info("\n❌ TEST FAILED: Connection did not remain stable after greeting")
        return False

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="WebSocket Stability Test Client for RedBarSushiAI")
    parser.add_argument("--url", type=str, default="ws://localhost:5000/ws/voice/media",
                       help="WebSocket URL to test")
    parser.add_argument("--duration", type=int, default=60,
                       help="Test duration in seconds")
    parser.add_argument("--verbose", action="store_true",
                       help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        
    try:
        # Run the async connection test
        result = asyncio.run(test_connection(args.url, args.duration))
        sys.exit(0 if result is True else 1 if result is False else 2)  # 2 = inconclusive
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        sys.exit(130)  # Standard exit code for SIGINT
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()