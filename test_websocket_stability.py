#!/usr/bin/env python3
"""
WebSocket Stability Test for RedBarSushiAI.

This script tests the stability of WebSocket connections, particularly focusing
on the post-greeting phase where disconnections have been occurring.

Usage:
    python test_websocket_stability.py [--url URL] [--duration SECONDS]
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
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('websocket_stability_test.log')
    ]
)
logger = logging.getLogger("websocket_stability_test")

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
    "disconnection_reason": None
}

async def send_keep_alive(websocket, session_id):
    """Send a keep-alive message to the WebSocket."""
    try:
        keep_alive = {
            "type": "keep_alive",
            "timestamp": time.time(),
            "session_id": session_id,
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

async def test_connection(url, duration=300):
    """
    Test WebSocket connection stability.
    
    Args:
        url: The WebSocket URL to connect to
        duration: Test duration in seconds
    """
    session_id = str(uuid.uuid4())[:12]
    logger.info(f"Starting WebSocket stability test for {duration}s")
    logger.info(f"Test session ID: {session_id}")
    logger.info(f"Target URL: {url}")
    
    # Set up SSL context that doesn't verify for testing
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    try:
        # Connect to the WebSocket
        logger.info(f"Connecting to {url}...")
        
        async with websockets.connect(
            url,
            ssl=ssl_context,
            subprotocols=["twilio-media-stream"]
        ) as websocket:
            logger.info(f"✅ Connected successfully")
            connection_stats["connection_time"] = time.time()
            connection_stats["last_message_time"] = time.time()
            
            # Send initial message to simulate Twilio connection
            initial_message = {
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
            
            logger.info(f"Sending initial connection message...")
            await websocket.send(json.dumps(initial_message))
            connection_stats["messages_sent"] += 1
            
            # Time tracking
            start_time = time.time()
            last_keep_alive = start_time
            last_status = start_time
            
            # Main test loop
            while time.time() - start_time < duration:
                try:
                    # Try to receive a message with timeout
                    receive_task = asyncio.create_task(websocket.recv())
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
                            
                            # Check for greeting
                            text = data.get("text", "").lower()
                            is_greeting = (
                                data.get("is_greeting", False) or
                                "welcome" in text or
                                "greeting" in text
                            )
                            
                            if is_greeting and not connection_stats["greeting_detected"]:
                                connection_stats["greeting_detected"] = True
                                connection_stats["greeting_time"] = current_time
                                logger.info(f"🎉 GREETING DETECTED: '{text}'")
                                logger.info(f"Time since connection: {current_time - start_time:.2f}s")
                            
                            # Track post-greeting messages
                            if connection_stats["greeting_detected"]:
                                connection_stats["post_greeting_messages"] += 1
                                
                            # Log received message
                            if message_type != "heartbeat":
                                logger.info(f"📥 Received {message_type}: {message[:100]}...")
                        except:
                            # Not JSON, log as raw
                            logger.info(f"📥 Received raw message: {message[:100]}...")
                    else:
                        # No message received, cancel the task
                        receive_task.cancel()
                        
                        # Check if it's time to send keep-alive (every 5 seconds)
                        if current_time - last_keep_alive >= 5.0:
                            await send_keep_alive(websocket, session_id)
                            last_keep_alive = current_time
                        
                        # Print status update every 10 seconds
                        if current_time - last_status >= 10.0:
                            elapsed = current_time - start_time
                            logger.info(f"⏱️ STATUS at {elapsed:.1f}s:")
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
                    continue
            
            # Test completed successfully!
            if time.time() - start_time >= duration:
                logger.info(f"✅ Test completed successfully after {duration}s")
            
    except Exception as e:
        logger.error(f"❌ Connection failed: {str(e)}")
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
    parser = argparse.ArgumentParser(description="WebSocket Stability Test for RedBarSushiAI")
    parser.add_argument("--url", type=str, default="wss://redbarsushiai-staging.onrender.com/ws/voice/media",
                       help="WebSocket URL to test")
    parser.add_argument("--duration", type=int, default=300,
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
        sys.exit(1)

if __name__ == "__main__":
    main()