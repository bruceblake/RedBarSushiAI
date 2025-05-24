#!/usr/bin/env python3
"""
Test WebSocket connectivity for RedBarSushiAI.
This script verifies that WebSocket connections work properly.
"""

import asyncio
import json
import base64
import websockets
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_websocket_connection(url: str = "ws://localhost:8000/realtime/ws/media/test-call-123"):
    """Test WebSocket connection to the FastAPI server."""
    logger.info(f"Connecting to: {url}")
    
    try:
        async with websockets.connect(url) as websocket:
            logger.info("✓ WebSocket connected successfully")
            
            # Send connected event
            connected_msg = {
                "event": "connected",
                "protocol": "Call",
                "version": "1.0.0"
            }
            await websocket.send(json.dumps(connected_msg))
            logger.info("✓ Sent 'connected' event")
            
            # Send start event
            start_msg = {
                "event": "start",
                "streamSid": "MZtest123456789",
                "start": {
                    "streamSid": "MZtest123456789",
                    "accountSid": "ACtest123456789",
                    "callSid": "test-call-123",
                    "tracks": ["inbound_track"],
                    "mediaFormat": {
                        "encoding": "audio/x-mulaw",
                        "sampleRate": 8000,
                        "channels": 1
                    }
                }
            }
            await websocket.send(json.dumps(start_msg))
            logger.info("✓ Sent 'start' event")
            
            # Send some audio data
            for i in range(3):
                # Create dummy audio (20ms of mulaw silence)
                audio_data = base64.b64encode(b'\xff' * 160).decode()
                media_msg = {
                    "event": "media",
                    "streamSid": "MZtest123456789",
                    "media": {
                        "track": "inbound_track",
                        "chunk": str(i),
                        "timestamp": str(i * 20),
                        "payload": audio_data
                    }
                }
                await websocket.send(json.dumps(media_msg))
                logger.info(f"✓ Sent audio chunk {i}")
                
                # Listen for any responses
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=0.5)
                    logger.info(f"Received: {response[:100]}...")
                except asyncio.TimeoutError:
                    pass
            
            # Send stop event
            stop_msg = {
                "event": "stop",
                "streamSid": "MZtest123456789"
            }
            await websocket.send(json.dumps(stop_msg))
            logger.info("✓ Sent 'stop' event")
            
            # Close connection
            await websocket.close()
            logger.info("✓ WebSocket connection closed")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ WebSocket test failed: {e}")
        return False


async def test_health_endpoint(base_url: str = "http://localhost:8000"):
    """Test the health endpoint."""
    import aiohttp
    
    url = f"{base_url}/health"
    logger.info(f"Testing health endpoint: {url}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
                logger.info(f"✓ Health check response: {data}")
                return response.status == 200
    except Exception as e:
        logger.error(f"❌ Health check failed: {e}")
        return False


async def main():
    """Run WebSocket tests."""
    # Parse command line arguments
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost:8000"
    
    # Determine protocol
    if host.startswith("http"):
        base_url = host
        ws_protocol = "wss" if "https" in host else "ws"
        host = host.replace("https://", "").replace("http://", "")
    else:
        base_url = f"http://{host}"
        ws_protocol = "ws"
    
    ws_url = f"{ws_protocol}://{host}/realtime/ws/media/test-call-123"
    
    logger.info("=" * 60)
    logger.info("RedBarSushiAI WebSocket Test")
    logger.info("=" * 60)
    logger.info(f"Base URL: {base_url}")
    logger.info(f"WebSocket URL: {ws_url}")
    logger.info("")
    
    # Test health endpoint
    health_ok = await test_health_endpoint(base_url)
    
    # Test WebSocket
    ws_ok = await test_websocket_connection(ws_url)
    
    logger.info("")
    logger.info("=" * 60)
    if health_ok and ws_ok:
        logger.info("✅ All tests passed!")
    else:
        logger.info("❌ Some tests failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())