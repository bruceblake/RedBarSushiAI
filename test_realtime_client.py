#!/usr/bin/env python3
"""
Test script for the OpenAI Realtime client fix
"""

import asyncio
import logging
from app.utils.realtime_audio_async import (
    OpenAIRealtimeClient, 
    RealtimeConfig, 
    RealtimeEventProcessor
)

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

async def test_realtime_client():
    """Test the OpenAI Realtime client initialization."""
    try:
        # Test configuration
        config = RealtimeConfig(
            model="gpt-4o-realtime-preview-2024-10-01",
            instructions="This is a test instruction",
            voice="shimmer"
        )
        
        # Create the client
        logger.info("Creating OpenAIRealtimeClient...")
        client = OpenAIRealtimeClient(
            api_key="sk-testkey",
            config=config,
            session_id="test-session"
        )
        
        # Create the event processor with the client
        logger.info("Creating RealtimeEventProcessor...")
        processor = RealtimeEventProcessor(client=client)
        
        # Set the processor on the client
        client.event_processor = processor
        
        logger.info("OpenAIRealtimeClient initialization successful!")
        return True
    except Exception as e:
        logger.error(f"Error initializing OpenAIRealtimeClient: {e}")
        return False

if __name__ == "__main__":
    print("\n===== Testing OpenAI Realtime Client Fix =====")
    success = asyncio.run(test_realtime_client())
    print(f"\nTest result: {'PASSED' if success else 'FAILED'}")
    print("==============================================\n")