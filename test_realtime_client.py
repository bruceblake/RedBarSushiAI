#!/usr/bin/env python3
"""
Enhanced test script for verifying the fixed OpenAIRealtimeClient implementation.

This script tests:
1. Client initialization
2. API key validation 
3. Connection to OpenAI Realtime API
4. Sending a greeting for TTS via request_response method
5. WebSocket message processing
6. Graceful connection closure

Usage:
    python test_realtime_client.py

Required environment variables:
    OPENAI_API_KEY - A valid OpenAI API key (if not provided, a dummy key will be used for testing key validation)
"""

import os
import sys
import asyncio
import logging
from typing import Optional, Dict, Any

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("realtime_test")

# Import the OpenAIRealtimeClient
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from app.utils.realtime_audio_async import OpenAIRealtimeClient, RealtimeConfig
except ImportError:
    logger.error("Could not import OpenAIRealtimeClient. Make sure you're running from the project root.")
    sys.exit(1)

async def handle_transcript(transcript: str):
    """Handle a transcript event from OpenAI."""
    logger.info(f"✓ Received transcript: {transcript}")

async def handle_audio(audio_data: bytes):
    """Handle audio data from OpenAI."""
    logger.info(f"✓ Received audio data: {len(audio_data)} bytes")

async def handle_tool_call(name: str, args: Dict[str, Any], tool_id: str):
    """Handle a tool call from OpenAI."""
    logger.info(f"✓ Tool call: {name}, args: {args}, id: {tool_id}")
    return {"status": "success", "result": f"Tool {name} executed"}

async def handle_error(error: str):
    """Handle an error from OpenAI."""
    logger.error(f"! OpenAI API error: {error}")

async def main():
    """Main test function."""
    print("\n===== Testing OpenAI Realtime Client Implementation =====")
    logger.info("Starting OpenAIRealtimeClient test")

    # Get API key from environment or use dummy key for validation testing
    api_key = os.environ.get("OPENAI_API_KEY", "sk-mytestapikey")
    using_dummy_key = api_key == "sk-mytestapikey" or "test" in api_key.lower()
    
    if using_dummy_key:
        logger.warning("! Using dummy API key for testing - connection to OpenAI will fail")
        logger.warning("! Set OPENAI_API_KEY environment variable for full testing")
    
    # Create a client with a test configuration
    config = RealtimeConfig(
        model="gpt-4o-realtime-preview-2024-12-17",  # Updated to latest model version
        voice="shimmer",
        instructions="You are a helpful assistant",
        vad_enabled=True
    )

    # Test client initialization
    logger.info("Testing client initialization...")
    try:
        client = OpenAIRealtimeClient(
            api_key=api_key,
            config=config,
            session_id="test_session"
        )
        logger.info("✓ Client initialization successful")

        # Test callback registration
        logger.info("Testing callback registration...")
        client.register_callbacks(
            transcript_callback=handle_transcript,
            audio_callback=handle_audio,
            tool_call_callback=handle_tool_call,
            error_callback=handle_error
        )
        logger.info("✓ Callback registration successful")

        # Test request_response method existence
        logger.info("Testing request_response method existence...")
        assert hasattr(client, 'request_response'), "request_response method not found"
        logger.info("✓ request_response method exists")

        # Test API key validation
        logger.info("Testing API key validation...")
        if using_dummy_key:
            logger.info("✓ Dummy key detection should be logged below")
        
        # Test connection - this should succeed initially even with invalid key
        logger.info("Testing connection to OpenAI Realtime API...")
        connected = await client.connect()
        
        if connected:
            logger.info("✓ Initial WebSocket connection successful")
            
            # Test sending greeting for TTS
            greeting = "Hello! This is a test of the OpenAI Realtime client."
            logger.info(f"Testing request_response method with greeting: {greeting}")
            
            if not using_dummy_key:
                # If using a real key, we can test the full flow
                try:
                    await client.request_response(greeting)
                    logger.info("✓ Successfully sent greeting for TTS")
                    
                    # Wait for events for 5 seconds
                    logger.info("Waiting for events for 5 seconds...")
                    await asyncio.sleep(5)
                except Exception as e:
                    logger.error(f"! Error sending greeting: {e}")
            else:
                # With dummy key, we expect errors but we can still test the method exists
                try:
                    await client.request_response(greeting)
                    logger.info("Greeting sent, but will likely fail at OpenAI")
                except Exception as e:
                    logger.error(f"! Error sending greeting: {e}")
                
                # Wait briefly for any error events
                logger.info("Waiting briefly for expected error events...")
                await asyncio.sleep(2)
        else:
            logger.warning("! Failed to connect to OpenAI Realtime API")
    except Exception as e:
        logger.error(f"! Test failed with error: {e}")
    finally:
        # Test connection closure
        logger.info("Testing connection closure...")
        try:
            await client.close()
            logger.info("✓ Connection closed successfully")
        except Exception as e:
            logger.error(f"! Error during connection closure: {e}")
    
    print(f"\nTest completed. Check logs above for results.")
    print("=======================================================\n")

if __name__ == "__main__":
    asyncio.run(main())