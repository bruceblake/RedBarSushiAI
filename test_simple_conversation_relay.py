"""
Test a very simple ConversationRelay interaction to isolate the TTS issue.
"""

import asyncio
import json
import websockets
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_simple_conversation():
    """Test with the simplest possible conversation flow."""
    
    call_sid = f"E2E_SIMPLE_{asyncio.get_event_loop().time():.0f}"
    websocket_url = "ws://localhost:8080/api/conversation-relay"
    
    print("🎯 Testing Simple ConversationRelay Flow")
    print("=" * 50)
    
    async with websockets.connect(websocket_url) as ws:
        # 1. Send setup with welcomeGreeting (which we know works)
        setup_msg = {
            "type": "setup",
            "callSid": call_sid,
            "from": "+1234567890",
            "direction": "inbound",
            "welcomeGreeting": "Hello! This is a test. Can you hear me?"
        }
        await ws.send(json.dumps(setup_msg))
        print("✅ Sent setup with welcomeGreeting")
        print("   (You should hear: 'Hello! This is a test. Can you hear me?')")
        
        # 2. Wait a bit to ensure greeting is played
        await asyncio.sleep(3)
        
        # 3. Simulate user saying "yes"
        print("\n🗣️ Simulating user saying 'yes'...")
        yes_msg = {
            "type": "prompt",
            "callSid": call_sid,
            "voicePrompt": "yes",
            "transcript": "yes", 
            "last": True
        }
        await ws.send(json.dumps(yes_msg))
        
        # 4. Monitor responses
        print("\n📡 Monitoring for system response...")
        messages = []
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < 10:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                data = json.loads(msg)
                messages.append(data)
                
                print(f"\n📨 Message received:")
                print(f"   Type: {data.get('type')}")
                if data.get('type') == 'text':
                    print(f"   Text: '{data.get('text')}'")
                    print(f"   Last: {data.get('last')}")
                    print("   ❓ CHECK: Can you hear this being spoken?")
                else:
                    print(f"   Full: {json.dumps(data, indent=2)}")
                    
            except asyncio.TimeoutError:
                continue
                
        # 5. Now try sending a text message ourselves (won't work but good for debugging)
        print("\n🔬 Testing direct text send (for debugging)...")
        test_text = {
            "type": "text",
            "text": "If you hear this, something is very wrong.",
            "last": True
        }
        await ws.send(json.dumps(test_text))
        print("   (You should NOT hear this - we're not Twilio)")
        
        await asyncio.sleep(2)
        
    print("\n" + "=" * 50)
    print(f"🏁 Test Complete - Received {len(messages)} messages")
    print("\nQuestions:")
    print("1. Did you hear the welcome greeting?")
    print("2. Did you hear any response after 'yes'?")
    print("3. Were there any error messages in the console?")


if __name__ == "__main__":
    asyncio.run(test_simple_conversation())