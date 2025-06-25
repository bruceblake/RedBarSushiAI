"""
Manual test script for Twilio Media Streams WebSocket implementation.

This script helps test the WebSocket voice gateway with Twilio using ngrok.

Setup Instructions:
1. Install ngrok: https://ngrok.com/download
2. Start your FastAPI app: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
3. In another terminal, run: ngrok http 8000
4. Copy the HTTPS URL from ngrok (e.g., https://abc123.ngrok.io)
5. Update your Twilio phone number webhook to: https://abc123.ngrok.io/voice/webhook
6. Make a test call to your Twilio number
7. Monitor the logs in both terminals
"""

import asyncio
import json
import websockets
from datetime import datetime


async def test_websocket_client():
    """
    Simple WebSocket client to test the Media Streams endpoint locally.
    """
    # Local WebSocket URL for testing
    ws_url = "ws://localhost:8000/ws/voice/test-call-123"
    
    print(f"[{datetime.now()}] Connecting to {ws_url}")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            print(f"[{datetime.now()}] Connected!")
            
            # Send a connected event (simulating Twilio)
            connected_msg = {
                "event": "connected",
                "protocol": "Call",
                "version": "1.0.0"
            }
            await websocket.send(json.dumps(connected_msg))
            print(f"[{datetime.now()}] Sent 'connected' event")
            
            # Send a start event
            start_msg = {
                "event": "start",
                "streamSid": "MZ123456789",
                "accountSid": "AC123456789",
                "callSid": "CA123456789",
                "mediaFormat": {
                    "encoding": "audio/x-mulaw",
                    "sampleRate": 8000,
                    "channels": 1
                }
            }
            await websocket.send(json.dumps(start_msg))
            print(f"[{datetime.now()}] Sent 'start' event")
            
            # Simulate sending some audio (base64 encoded silence)
            import base64
            silence_mulaw = bytes([0x7F] * 160)  # 20ms of mulaw silence
            
            for i in range(5):  # Send 5 chunks
                media_msg = {
                    "event": "media",
                    "streamSid": "MZ123456789",
                    "media": {
                        "timestamp": str(i * 20),
                        "payload": base64.b64encode(silence_mulaw).decode('utf-8')
                    }
                }
                await websocket.send(json.dumps(media_msg))
                print(f"[{datetime.now()}] Sent media chunk {i+1}")
                await asyncio.sleep(0.02)  # 20ms between chunks
            
            # Send stop event
            stop_msg = {
                "event": "stop",
                "streamSid": "MZ123456789"
            }
            await websocket.send(json.dumps(stop_msg))
            print(f"[{datetime.now()}] Sent 'stop' event")
            
            # Wait a bit for any responses
            await asyncio.sleep(1)
            
    except Exception as e:
        print(f"[{datetime.now()}] Error: {e}")
    
    print(f"[{datetime.now()}] Test completed")


def print_testing_instructions():
    """Print instructions for testing with Twilio and ngrok."""
    print("\n" + "="*60)
    print("TWILIO MEDIA STREAMS TESTING INSTRUCTIONS")
    print("="*60)
    print("\n1. SETUP NGROK:")
    print("   - Install ngrok: https://ngrok.com/download")
    print("   - Run: ngrok http 8000")
    print("   - Copy the HTTPS URL (e.g., https://abc123.ngrok.io)")
    print("\n2. UPDATE TWILIO:")
    print("   - Go to your Twilio Console")
    print("   - Find your phone number")
    print("   - Set the Voice webhook to: https://YOUR_NGROK_URL/voice/webhook")
    print("   - Method: POST")
    print("\n3. TEST:")
    print("   - Call your Twilio number")
    print("   - Watch the FastAPI logs")
    print("   - Check ngrok web interface at: http://127.0.0.1:4040")
    print("\n4. DEBUGGING:")
    print("   - Check /routes endpoint to verify WebSocket routes")
    print("   - Check /health endpoint to verify app is running")
    print("   - Enable debug logging: export LOG_LEVEL=DEBUG")
    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    print_testing_instructions()
    
    # Optionally run the local WebSocket test
    user_input = input("Run local WebSocket test? (y/n): ")
    if user_input.lower() == 'y':
        asyncio.run(test_websocket_client())