#!/usr/bin/env python3
"""
WebSocket test client for RedBarSushiAI.

This script tests the WebSocket connection to the media stream endpoint with proper
CallSid handling, making it compatible with the Twilio Media Streams protocol.
"""

import asyncio
import websockets
import json
import base64
import time
import os
import sys
import uuid
import logging
import argparse
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('websocket_test.log')
    ]
)
logger = logging.getLogger("websocket_test")

def format_url_with_callsid(url, call_sid):
    """Format the WebSocket URL to include the CallSid in the host part."""
    parsed = urlparse(url)
    
    # Format: wss://CALLSID@hostname/path
    if parsed.scheme in ['ws', 'wss']:
        netloc = parsed.netloc
        if '@' not in netloc:  # Only add if not already there
            netloc = f"{call_sid}@{netloc}"
        
        # Reconstruct the URL
        new_url = f"{parsed.scheme}://{netloc}{parsed.path}"
        if parsed.query:
            new_url += f"?{parsed.query}"
        
        return new_url
    
    return url

async def test_websocket_connection(url, call_sid, timeout=10):
    """
    Test the WebSocket connection with proper CallSid handling.
    
    Args:
        url: WebSocket server URL
        call_sid: Call SID to use for testing
        timeout: Timeout in seconds
    
    Returns:
        bool: True if successful, False otherwise
    """
    logger.info(f"Testing WebSocket connection to: {url}")
    logger.info(f"Using CallSid: {call_sid}")
    
    # Format URL with CallSid if needed
    formatted_url = format_url_with_callsid(url, call_sid)
    
    if formatted_url != url:
        logger.info(f"Reformatted URL with CallSid: {formatted_url}")
    
    try:
        logger.info(f"Connecting to {formatted_url}...")
        
        # Connect to WebSocket with Twilio subprotocol
        async with websockets.connect(
            formatted_url,
            subprotocols=["twilio-media-stream"]
        ) as ws:
            logger.info("✅ Connected to WebSocket server")
            
            # Send start event
            start_event = {
                "event": "start",
                "streamSid": f"MS{call_sid[:32]}",
                "callSid": call_sid,
                "accountSid": f"AC{call_sid[:32]}",
                "start": {
                    "mediaFormat": {
                        "encoding": "mulaw",
                        "sampleRate": 8000,
                        "channels": 1
                    }
                }
            }
            await ws.send(json.dumps(start_event))
            logger.info("✅ Sent start event")
            
            # Try to receive a response
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=timeout)
                logger.info(f"✅ Received response: {response[:100]}" + ("..." if len(response) > 100 else ""))
                
                # Send some test audio data
                logger.info("Sending test audio data...")
                audio_chunk = bytes([0] * 160)  # Empty 160-byte audio chunk
                audio_b64 = base64.b64encode(audio_chunk).decode('utf-8')
                
                for i in range(5):  # Send 5 chunks
                    media_event = {
                        "event": "media",
                        "streamSid": f"MS{call_sid[:32]}",
                        "media": {
                            "payload": audio_b64,
                            "track": "inbound_track"
                        }
                    }
                    await ws.send(json.dumps(media_event))
                    await asyncio.sleep(0.1)  # Small delay between chunks
                
                logger.info("✅ Sent test audio chunks")
                
                # Wait for any potential responses
                response_count = 0
                try:
                    for i in range(3):  # Try to receive up to 3 responses
                        response = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        response_count += 1
                        logger.info(f"Received additional response #{response_count}: {response[:100]}" + 
                                   ("..." if len(response) > 100 else ""))
                except asyncio.TimeoutError:
                    logger.info("No more responses received (timeout)")
                
                # Send stop event
                stop_event = {
                    "event": "stop",
                    "streamSid": f"MS{call_sid[:32]}"
                }
                await ws.send(json.dumps(stop_event))
                logger.info("✅ Sent stop event")
                
                # Wait for final response
                try:
                    final_response = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    logger.info(f"Received final response: {final_response[:100]}" + 
                               ("..." if len(final_response) > 100 else ""))
                except asyncio.TimeoutError:
                    logger.info("No final response received (timeout)")
                
                return True, response_count
                
            except asyncio.TimeoutError:
                logger.error(f"❌ No response received after {timeout} seconds")
                return False, 0
                
    except Exception as e:
        logger.error(f"❌ Error testing WebSocket connection: {e}")
        return False, 0

def main():
    parser = argparse.ArgumentParser(description="Test WebSocket connectivity for RedBarSushiAI")
    parser.add_argument("--url", default="ws://localhost:8080/ws/media", help="WebSocket URL")
    parser.add_argument("--call-sid", default=None, help="Custom Call SID (will generate one if not provided)")
    parser.add_argument("--timeout", type=int, default=10, help="Response timeout in seconds")
    args = parser.parse_args()
    
    # Generate a Call SID if not provided
    call_sid = args.call_sid or f"CA{uuid.uuid4().hex}"
    
    # Print header
    print("=" * 60)
    print(f"RedBarSushiAI WebSocket Test - {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print(f"Target URL: {args.url}")
    print(f"Call SID: {call_sid}")
    print(f"Timeout: {args.timeout} seconds")
    print("-" * 60)
    
    # Run the test
    success, response_count = asyncio.run(test_websocket_connection(args.url, call_sid, args.timeout))
    
    # Print result
    print("-" * 60)
    if success:
        print(f"✅ WebSocket test PASSED! Connection established and received {response_count} responses.")
        return 0
    else:
        print("❌ WebSocket test FAILED! Could not establish proper connection.")
        print("Check 'websocket_test.log' for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())