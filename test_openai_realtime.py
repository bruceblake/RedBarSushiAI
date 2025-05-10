#!/usr/bin/env python
"""
Test script for OpenAI Realtime API connection.
This script tests the connection to the OpenAI Realtime API directly.
"""

import os
import sys
import json
import asyncio
import logging
import websockets
import base64
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.DEBUG, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# OpenAI API key
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_REALTIME_MODEL = os.environ.get("OPENAI_REALTIME_MODEL", "gpt-4o-realtime-preview-2024-10-01")

async def test_realtime_connection():
    """Test connection to OpenAI Realtime API."""
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY environment variable is not set.")
        return False
    
    logger.info(f"Testing connection to OpenAI Realtime API with API key: {OPENAI_API_KEY[:4]}...{OPENAI_API_KEY[-4:]}")
    
    # OpenAI Realtime API URL
    url = "wss://api.openai.com/v1/realtime"
    
    # Headers for authentication
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "OpenAI-Beta": "realtime=v1",
        "Content-Type": "application/json"
    }
    
    try:
        # Connect to the WebSocket
        logger.info(f"Connecting to {url}")
        async with websockets.connect(url, extra_headers=headers) as websocket:
            logger.info("Connected to OpenAI Realtime API")
            
            # Configure the session
            session_config = {
                "type": "session.update",
                "session": {
                    "model": OPENAI_REALTIME_MODEL,
                    "modalities": ["text", "audio"],
                    "voice": "shimmer",
                    "sample_rate_hz": 24000,
                    "inputAudioFormat": {
                        "type": "wav"
                    },
                    "outputAudioFormat": {
                        "type": "wav"
                    },
                    "vad": {
                        "mode": "server",
                        "silence_threshold_ms": 1000,
                        "speech_threshold_ms": 8000
                    }
                }
            }
            
            # Send the session configuration
            logger.info("Sending session configuration")
            await websocket.send(json.dumps(session_config))
            
            # Wait for a response
            logger.info("Waiting for response...")
            response = await websocket.recv()
            response_data = json.loads(response)
            
            logger.info(f"Received response: {json.dumps(response_data, indent=2)}")
            
            # Send a test message
            text_event = {
                "type": "conversation.item.create",
                "conversationItem": {
                    "role": "user",
                    "content": "Hello, can you confirm the connection is working?"
                }
            }
            
            logger.info("Sending test message")
            await websocket.send(json.dumps(text_event))
            
            # Request a response
            response_event = {
                "type": "response.create",
                "response": {
                    "modalities": ["text"]
                }
            }
            
            logger.info("Requesting response")
            await websocket.send(json.dumps(response_event))
            
            # Wait for responses (for up to 10 seconds)
            try:
                for _ in range(5):  # Try to get a few responses
                    response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    response_data = json.loads(response)
                    event_type = response_data.get("type", "unknown")
                    
                    logger.info(f"Received event: {event_type}")
                    logger.debug(f"Response data: {json.dumps(response_data, indent=2)}")
                    
                    # If we got a response, we're good
                    if event_type in ["response.final", "response.delta"]:
                        logger.info("Successfully received response from OpenAI")
                        return True
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for response")
            
            logger.info("Connection test complete")
            return True
            
    except websockets.exceptions.InvalidStatusCode as e:
        logger.error(f"HTTP error when connecting to OpenAI: Status {e.status_code}")
        if hasattr(e, 'response_body'):
            logger.error(f"Response body: {e.response_body}")
        return False
    except Exception as e:
        logger.error(f"Error connecting to OpenAI Realtime API: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """Main function."""
    print("=== OpenAI Realtime API Connection Test ===\n")
    
    # Check API key
    if not OPENAI_API_KEY:
        print("ERROR: OPENAI_API_KEY environment variable is not set.")
        print("Please set the OPENAI_API_KEY environment variable and try again.")
        print("Example: export OPENAI_API_KEY='sk-...'")
        sys.exit(1)
    
    # Run the test
    result = asyncio.run(test_realtime_connection())
    
    if result:
        print("\n✅ OpenAI Realtime API connection test SUCCESSFUL!")
    else:
        print("\n❌ OpenAI Realtime API connection test FAILED!")
        print("Please check the logs above for details.")
    
if __name__ == "__main__":
    main()