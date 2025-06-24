"""
Test to diagnose TTS issues with ConversationRelay.
"""

import asyncio
import json
import websockets
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_simple_tts():
    """Test with very simple, clear responses to isolate TTS issue."""
    
    call_sid = f"E2E_TTS_TEST_{asyncio.get_event_loop().time():.0f}"
    websocket_url = "ws://localhost:8080/api/conversation-relay"
    
    print("🔊 Testing TTS with Simple Responses")
    print("=" * 50)
    
    async with websockets.connect(websocket_url) as ws:
        # 1. Setup
        setup_msg = {
            "type": "setup",
            "callSid": call_sid,
            "from": "+1234567890",
            "direction": "inbound"
        }
        await ws.send(json.dumps(setup_msg))
        
        # 2. Get greeting - should hear this
        greeting_raw = await ws.recv()
        greeting = json.loads(greeting_raw)
        print(f"✅ GREETING (you should hear this): {greeting['text']}")
        
        # 3. Send a simple message
        print("\n🗣️ Sending: 'Hello'")
        hello_msg = {
            "type": "prompt",
            "callSid": call_sid,
            "voicePrompt": "Hello",
            "transcript": "Hello",
            "last": True
        }
        await ws.send(json.dumps(hello_msg))
        
        # 4. Get response - check if you hear this
        response_raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
        response = json.loads(response_raw)
        print(f"📨 RESPONSE (check if you hear this): {response['text']}")
        print(f"   Response type: {response.get('type')}")
        print(f"   Full response: {json.dumps(response, indent=2)}")
        
        # 5. Try another simple message
        await asyncio.sleep(2)  # Wait a bit
        
        print("\n🗣️ Sending: 'Can you hear me?'")
        test_msg = {
            "type": "prompt", 
            "callSid": call_sid,
            "voicePrompt": "Can you hear me?",
            "transcript": "Can you hear me?",
            "last": True
        }
        await ws.send(json.dumps(test_msg))
        
        # 6. Get second response
        response2_raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
        response2 = json.loads(response2_raw)
        print(f"📨 RESPONSE 2 (check if you hear this): {response2['text']}")
        
    print("\n" + "=" * 50)
    print("🏁 TTS Test Complete")
    print("\nDIAGNOSTIC QUESTIONS:")
    print("1. Did you hear the initial greeting?")
    print("2. Did you hear the responses after that?")
    print("3. Were the responses clear or garbled?")


if __name__ == "__main__":
    print("🚀 Running TTS Diagnostic Test")
    print("📡 This will help identify if TTS is working")
    print("-" * 50)
    
    asyncio.run(test_simple_tts())