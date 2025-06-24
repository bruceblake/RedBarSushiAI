"""
Test to see all messages from Twilio ConversationRelay.
"""

import asyncio
import json
import websockets
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_twilio_message_flow():
    """Monitor all messages from Twilio to understand the protocol."""
    
    call_sid = f"E2E_MONITOR_{asyncio.get_event_loop().time():.0f}"
    websocket_url = "ws://localhost:8080/api/conversation-relay"
    
    print("📡 Monitoring Twilio ConversationRelay Messages")
    print("=" * 50)
    
    async with websockets.connect(websocket_url) as ws:
        # 1. Send setup
        setup_msg = {
            "type": "setup",
            "callSid": call_sid,
            "from": "+1234567890",
            "direction": "inbound",
            "welcomeGreeting": "Testing. Can you hear this greeting?"
        }
        await ws.send(json.dumps(setup_msg))
        print("✅ Sent setup with welcomeGreeting")
        
        # 2. Monitor all messages for 20 seconds
        print("\n📨 Monitoring messages for 20 seconds...")
        print("(In a real call, you would hear the greeting now)")
        
        start_time = asyncio.get_event_loop().time()
        message_count = 0
        
        while asyncio.get_event_loop().time() - start_time < 20:
            try:
                # Wait for any message
                message = await asyncio.wait_for(ws.recv(), timeout=1.0)
                message_count += 1
                
                try:
                    data = json.loads(message)
                    print(f"\n📩 Message #{message_count} from Twilio:")
                    print(f"   Type: {data.get('type')}")
                    print(f"   Full: {json.dumps(data, indent=2)}")
                except json.JSONDecodeError:
                    print(f"\n📜 Non-JSON message #{message_count}: {message}")
                    
            except asyncio.TimeoutError:
                # No message received, send a test
                if message_count == 0 and asyncio.get_event_loop().time() - start_time > 5:
                    print("\n🎯 No messages from Twilio yet, sending test prompt...")
                    test_msg = {
                        "type": "prompt",
                        "callSid": call_sid,
                        "voicePrompt": "Test message",
                        "last": True
                    }
                    await ws.send(json.dumps(test_msg))
                    
                    # Now send a text response immediately
                    await asyncio.sleep(0.5)
                    text_msg = {
                        "type": "text",
                        "text": "This should be spoken by Twilio",
                        "last": True
                    }
                    await ws.send(json.dumps(text_msg))
                    print("📤 Sent text message to Twilio")
                    
        print(f"\n🏁 Monitoring complete. Total messages from Twilio: {message_count}")


if __name__ == "__main__":
    asyncio.run(test_twilio_message_flow())