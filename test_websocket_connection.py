#!/usr/bin/env python3
"""
Test script to verify WebSocket connectivity to the RedBarSushiAI API.

This script attempts to connect to the WebSocket endpoint and verifies 
that the connection is successful. It can test both local and staging environments.
"""

import asyncio
import websockets
import json
import argparse
import sys
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

async def test_websocket_connection(url, timeout=5):
    """
    Test a WebSocket connection to the specified URL.
    
    Args:
        url: The WebSocket URL to connect to
        timeout: Connection timeout in seconds
        
    Returns:
        True if connection succeeded, False otherwise
    """
    logger.info(f"Attempting to connect to WebSocket at: {url}")
    
    try:
        # Connect with timeout
        async with asyncio.timeout(timeout):
            async with websockets.connect(url) as websocket:
                logger.info("✅ WebSocket connection established!")
                
                # Send a simple message
                message = {"type": "test", "message": "Hello from test client"}
                await websocket.send(json.dumps(message))
                logger.info(f"Sent message: {message}")
                
                # Wait for a response with timeout
                try:
                    async with asyncio.timeout(timeout):
                        response = await websocket.recv()
                        logger.info(f"Received response: {response}")
                        return True
                except asyncio.TimeoutError:
                    logger.warning("No response received within timeout, but connection was established")
                    return True
                
    except asyncio.TimeoutError:
        logger.error(f"❌ Connection timed out after {timeout} seconds")
        return False
    except ConnectionRefusedError:
        logger.error("❌ Connection refused - server may not be running or port is incorrect")
        return False
    except websockets.exceptions.InvalidStatusCode as e:
        logger.error(f"❌ Invalid status code: {e}")
        if "404" in str(e):
            logger.error("The WebSocket endpoint URL was not found (404)")
        return False
    except Exception as e:
        logger.error(f"❌ Error connecting to WebSocket: {e}")
        return False

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Test WebSocket connectivity")
    parser.add_argument("--url", default="ws://localhost:5000/ws/voice/debug", 
                        help="WebSocket URL to test")
    parser.add_argument("--staging", action="store_true",
                        help="Test staging environment instead of local")
    parser.add_argument("--timeout", type=int, default=5,
                        help="Connection timeout in seconds")
    
    args = parser.parse_args()
    
    # If staging flag is set, use the staging URL
    if args.staging:
        url = "wss://redbarsushiai-staging.onrender.com/ws/voice/debug"
    else:
        url = args.url
    
    # Run the test
    result = asyncio.run(test_websocket_connection(url, args.timeout))
    
    # Exit with appropriate status code
    if result:
        logger.info("WebSocket test completed successfully!")
        sys.exit(0)
    else:
        logger.error("WebSocket test failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()