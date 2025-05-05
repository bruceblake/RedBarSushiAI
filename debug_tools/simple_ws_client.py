#!/usr/bin/env python3
"""
Simple WebSocket client for testing WebSocket connectivity.

This script tests WebSocket connectivity with different client libraries
to determine which approach works best with the RedBarSushi server.
"""

import asyncio
import websockets
import ssl
import json
import logging
import sys
import traceback
import time

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ws_client")

async def test_websockets_library(url):
    """Test connection using websockets library."""
    logger.info(f"Attempting connection with websockets library to {url}")
    
    # Create SSL context (don't verify for testing)
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    try:
        # Try with twilio-media-stream subprotocol
        logger.info("Trying with twilio-media-stream subprotocol")
        async with websockets.connect(
            url,
            ssl=ssl_context,
            subprotocols=["twilio-media-stream"]
        ) as ws:
            logger.info("✓ Connected successfully with twilio-media-stream")
            try:
                # Try to send a message
                logger.info("Sending test message")
                await ws.send("test")
                logger.info("✓ Test message sent")
                
                # Wait for a response with timeout
                logger.info("Waiting for response (2s timeout)")
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    logger.info(f"Received response: {response}")
                except asyncio.TimeoutError:
                    logger.info("No response received (timeout)")
                
                # Wait briefly before disconnecting
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error during communication: {e}")
            logger.info("Connection closed normally")
    except Exception as e:
        logger.error(f"Connection failed with twilio-media-stream: {e}")
        logger.error(traceback.format_exc())
    
    # Try without subprotocol
    try:
        logger.info("Trying without subprotocol")
        async with websockets.connect(
            url,
            ssl=ssl_context
        ) as ws:
            logger.info("✓ Connected successfully without subprotocol")
            try:
                # Try to send a message
                logger.info("Sending test message")
                await ws.send("test")
                logger.info("✓ Test message sent")
                
                # Wait for a response with timeout
                logger.info("Waiting for response (2s timeout)")
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    logger.info(f"Received response: {response}")
                except asyncio.TimeoutError:
                    logger.info("No response received (timeout)")
                
                # Wait briefly before disconnecting
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error during communication: {e}")
            logger.info("Connection closed normally")
    except Exception as e:
        logger.error(f"Connection failed without subprotocol: {e}")
        logger.error(traceback.format_exc())
    
    # Try with Twilio message format
    try:
        logger.info("Trying with Twilio message format")
        async with websockets.connect(
            url,
            ssl=ssl_context
        ) as ws:
            logger.info("✓ Connected successfully for Twilio format test")
            try:
                # Try to send a Twilio-like start message
                start_msg = {
                    "event": "start",
                    "streamSid": "MT123456789012345678901234567890",
                    "accountSid": "AC123456789012345678901234567890",
                    "callSid": "CA123456789012345678901234567890"
                }
                logger.info("Sending Twilio start message")
                await ws.send(json.dumps(start_msg))
                logger.info("✓ Twilio start message sent")
                
                # Wait for a response with timeout
                logger.info("Waiting for response (2s timeout)")
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    logger.info(f"Received response: {response}")
                except asyncio.TimeoutError:
                    logger.info("No response received (timeout)")
                
                # Wait briefly before disconnecting
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error during Twilio format communication: {e}")
            logger.info("Connection closed normally")
    except Exception as e:
        logger.error(f"Connection failed for Twilio format test: {e}")
        logger.error(traceback.format_exc())

async def main():
    """Main entry point."""
    url = "wss://redbarsushiai-staging.onrender.com/ws/voice/media"
    if len(sys.argv) > 1:
        url = sys.argv[1]
    
    logger.info(f"Testing WebSocket connectivity to {url}")
    
    try:
        await test_websockets_library(url)
    except Exception as e:
        logger.error(f"Test failed: {e}")
        logger.error(traceback.format_exc())
    
    logger.info("All tests completed")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        logger.error(traceback.format_exc())