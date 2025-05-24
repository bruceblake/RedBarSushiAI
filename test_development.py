#!/usr/bin/env python3
"""
Test script for development environment
"""

import asyncio
import websockets
import json
import sys


async def test_websocket():
    """Test WebSocket connection to the FastAPI server"""
    print("Testing WebSocket connection...")
    
    try:
        uri = "ws://localhost:8080/ws/media/test-call-sid"
        
        async with websockets.connect(uri) as websocket:
            print(f"✅ Connected to {uri}")
            
            # Send a test message
            test_message = {
                "event": "start",
                "streamSid": "test-stream",
                "start": {
                    "streamSid": "test-stream",
                    "callSid": "test-call-sid",
                    "tracks": ["inbound"]
                }
            }
            
            await websocket.send(json.dumps(test_message))
            print(f"📤 Sent: {test_message['event']} event")
            
            # Try to receive a response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"📥 Received: {response}")
            except asyncio.TimeoutError:
                print("⏱️  No response received (timeout)")
            
            # Close the connection
            await websocket.close()
            print("✅ WebSocket test completed")
            
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        return False
    
    return True


async def test_api_endpoints():
    """Test REST API endpoints"""
    import httpx
    
    print("\nTesting API endpoints...")
    
    endpoints = [
        ("/healthcheck", "GET"),
        ("/docs", "GET"),
        ("/api/v1/menu/categories", "GET"),
    ]
    
    async with httpx.AsyncClient() as client:
        for endpoint, method in endpoints:
            try:
                url = f"http://localhost:8080{endpoint}"
                response = await client.request(method, url)
                status_symbol = "✅" if response.status_code < 400 else "❌"
                print(f"{status_symbol} {method} {endpoint}: {response.status_code}")
            except Exception as e:
                print(f"❌ {method} {endpoint}: {e}")


async def main():
    """Run all tests"""
    print("=== RedBarSushiAI Development Environment Test ===\n")
    
    # Test API endpoints
    await test_api_endpoints()
    
    # Test WebSocket
    await test_websocket()
    
    print("\n✅ Development environment test completed!")


if __name__ == "__main__":
    asyncio.run(main())