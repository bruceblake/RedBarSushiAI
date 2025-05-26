#!/usr/bin/env python3
"""
ConversationRelay Debug Script

This script helps debug ConversationRelay connections and audio flow.
It connects to the WebSocket endpoint and simulates Twilio events.

Usage:
    python debug_conversationrelay.py [--url ws://localhost:8000/api/conversation-relay]
"""

import asyncio
import websockets
import json
import base64
import time
import argparse
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ConversationRelayDebugger:
    def __init__(self, ws_url):
        self.ws_url = ws_url
        self.relay_id = f"debug-relay-{int(time.time())}"
        self.call_sid = f"debug-call-{int(time.time())}"
        
    async def connect_and_test(self):
        """Connect to WebSocket and run tests."""
        logger.info(f"Connecting to {self.ws_url}")
        
        try:
            async with websockets.connect(self.ws_url) as websocket:
                logger.info("✅ WebSocket connected successfully")
                
                # Start listening for messages in background
                listen_task = asyncio.create_task(self.listen_for_messages(websocket))
                
                # Run test sequence
                await self.send_start_event(websocket)
                await asyncio.sleep(2)  # Wait for greeting
                
                await self.send_test_audio(websocket, "Hello, I want to order some sushi")
                await asyncio.sleep(5)  # Wait for response
                
                await self.send_test_audio(websocket, "I'd like two California rolls please")
                await asyncio.sleep(5)  # Wait for response
                
                await self.send_stop_event(websocket)
                
                # Cancel listener
                listen_task.cancel()
                
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            raise
    
    async def listen_for_messages(self, websocket):
        """Listen for messages from the server."""
        try:
            async for message in websocket:
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                
                # Handle binary messages (audio)
                if isinstance(message, bytes):
                    logger.info(f"[{timestamp}] 🔊 Received audio: {len(message)} bytes")
                    # Optionally save to file for analysis
                    # with open(f"audio_{timestamp}.pcmu", "wb") as f:
                    #     f.write(message)
                else:
                    # Handle JSON messages
                    try:
                        data = json.loads(message)
                        event_type = data.get("event", "unknown")
                        logger.info(f"[{timestamp}] 📨 Received {event_type} event: {json.dumps(data, indent=2)}")
                    except json.JSONDecodeError:
                        logger.warning(f"[{timestamp}] ⚠️  Received non-JSON text: {message}")
                        
        except asyncio.CancelledError:
            logger.info("Message listener cancelled")
        except Exception as e:
            logger.error(f"Error in message listener: {e}")
    
    async def send_start_event(self, websocket):
        """Send start event to initialize the session."""
        start_event = {
            "event": "start",
            "relayId": self.relay_id,
            "callSid": self.call_sid,
            "streamSid": f"stream-{self.call_sid}",
            "customParameters": {
                "debug": "true",
                "test_mode": "true"
            }
        }
        
        logger.info(f"📤 Sending start event: {json.dumps(start_event, indent=2)}")
        await websocket.send(json.dumps(start_event))
        
    async def send_test_audio(self, websocket, text):
        """Send simulated audio (actually just empty audio to trigger STT simulation)."""
        # In a real test, you'd send actual PCMU audio
        # For debugging, we'll send a custom event that the handler can recognize
        
        # Generate some dummy PCMU audio (silence)
        dummy_audio = bytes([0xFF] * 160)  # 160 bytes = 20ms of PCMU
        
        media_event = {
            "event": "media",
            "media": {
                "timestamp": int(time.time() * 1000),
                "payload": base64.b64encode(dummy_audio).decode('utf-8'),
                # Add debug transcript in custom field
                "_debug_transcript": text
            }
        }
        
        logger.info(f"📤 Sending media event with debug transcript: {text}")
        await websocket.send(json.dumps(media_event))
        
    async def send_stop_event(self, websocket):
        """Send stop event to end the session."""
        stop_event = {
            "event": "stop",
            "relayId": self.relay_id,
            "callSid": self.call_sid
        }
        
        logger.info(f"📤 Sending stop event")
        await websocket.send(json.dumps(stop_event))

def main():
    parser = argparse.ArgumentParser(description="Debug ConversationRelay WebSocket")
    parser.add_argument(
        "--url",
        default="ws://localhost:8000/api/conversation-relay",
        help="WebSocket URL to connect to"
    )
    parser.add_argument(
        "--secure",
        action="store_true",
        help="Use wss:// instead of ws://"
    )
    
    args = parser.parse_args()
    
    # Update URL if secure
    if args.secure and args.url.startswith("ws://"):
        args.url = args.url.replace("ws://", "wss://")
    
    # Create debugger and run
    debugger = ConversationRelayDebugger(args.url)
    
    try:
        asyncio.run(debugger.connect_and_test())
        logger.info("✅ Debug session completed successfully")
    except KeyboardInterrupt:
        logger.info("Debug session interrupted by user")
    except Exception as e:
        logger.error(f"❌ Debug session failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())