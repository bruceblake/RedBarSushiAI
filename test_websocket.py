#!/usr/bin/env python
"""
Simple test for WebSocket functionality with the OpenAI API.
This script tests direct connectivity to OpenAI's Realtime API
without requiring Docker.
"""

import os
import sys
import asyncio
import json
import logging
import time
import websockets

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("websocket_test")

async def test_openai_realtime_api(api_key):
    """Test direct connection to OpenAI's Realtime API."""
    if not api_key or api_key == "your_openai_api_key_here":
        logger.error("❌ No valid OpenAI API key provided")
        return False
        
    logger.info(f"Testing OpenAI Realtime API with key starting with: {api_key[:5]}...")
    
    # OpenAI Realtime API URL
    url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
    
    try:
        # Connect to OpenAI Realtime API
        async with websockets.connect(
            url,
            extra_headers={
                "Authorization": f"Bearer {api_key}",
                "OpenAI-Beta": "realtime=v1"
            }
        ) as websocket:
            logger.info("✅ Successfully connected to OpenAI Realtime API")
            
            # Configure the session
            session_config = {
                "type": "session.update",
                "speech_recognition": {
                    "enabled": True
                },
                "text_to_speech": {
                    "enabled": True,
                    "voice": "shimmer"
                }
            }
            
            # Send session config
            await websocket.send(json.dumps(session_config))
            logger.info("✅ Successfully sent session config")
            
            # Wait for a response with timeout
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                logger.info(f"✅ Received response: {response[:100]}")
                response_data = json.loads(response)
                if response_data.get("type") == "session.update.response":
                    logger.info("✅ Session update successful")
                    return True
                else:
                    logger.warning(f"⚠️ Unexpected response type: {response_data.get('type')}")
                    return False
                    
            except asyncio.TimeoutError:
                logger.error("❌ Timeout waiting for response from OpenAI")
                return False
                
    except Exception as e:
        logger.error(f"❌ Error connecting to OpenAI Realtime API: {str(e)}")
        return False
        
    return True

def get_openai_api_key():
    """Get OpenAI API key from environment or .env file."""
    # Try to get from environment
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        return api_key
        
    # Try to get from .env.development file
    env_file = ".env.development"
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            for line in f:
                if line.startswith("OPENAI_API_KEY="):
                    api_key = line.strip().split("=", 1)[1]
                    # Remove any quotes
                    api_key = api_key.strip("'\"")
                    return api_key
                    
    return None

async def main():
    """Main entry point."""
    logger.info("===== Testing WebSocket Connectivity =====")
    
    # Get API key
    api_key = get_openai_api_key()
    if not api_key:
        logger.error("❌ No OpenAI API key found in environment or .env.development file")
        sys.exit(1)
        
    # Test OpenAI connection
    success = await test_openai_realtime_api(api_key)
    
    if success:
        logger.info("✅ WebSocket test passed! OpenAI Realtime API is accessible")
        sys.exit(0)
    else:
        logger.error("❌ WebSocket test failed! Check logs for details")
        sys.exit(1)

if __name__ == "__main__":
    try:
        # Make sure websockets library is installed
        try:
            import websockets
        except ImportError:
            logger.error("❌ websockets library not installed. Run: pip install websockets")
            sys.exit(1)
            
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Error during test: {str(e)}")
        sys.exit(1)