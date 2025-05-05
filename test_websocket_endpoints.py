#!/usr/bin/env python3
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
