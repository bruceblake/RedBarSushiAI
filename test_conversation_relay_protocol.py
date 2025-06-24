"""
Test ConversationRelay protocol to debug TTS issues.
"""

import asyncio
import json
import websockets
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_conversation_relay_messages():
    """Test different message types and timing to debug TTS."""
    
    call_sid = f"E2E_PROTOCOL_{asyncio.get_event_loop().time():.0f}"
    websocket_url = "ws://localhost:8080/api/conversation-relay"
    
    print("🔍 Testing ConversationRelay Protocol")
    print("=" * 50)
    
    async with websockets.connect(websocket_url) as ws:
        # Track all messages
        messages_received = []
        
        # 1. Send setup without welcomeGreeting to test direct text sending
        setup_msg = {
            "type": "setup",
            "callSid": call_sid,
            "from": "+1234567890",
            "direction": "inbound"
            # Deliberately not including welcomeGreeting
        }
        await ws.send(json.dumps(setup_msg))
        print("📤 Sent setup (no welcomeGreeting)")
        
        # 2. Wait for any response from the system
        try:
            # The system should send us a greeting via text message
            greeting = await asyncio.wait_for(ws.recv(), timeout=5.0)
            greeting_data = json.loads(greeting)
            messages_received.append(greeting_data)
            print(f"📨 Received: {json.dumps(greeting_data, indent=2)}")
            
            # Check if this is being spoken
            if greeting_data.get('type') == 'text':
                print(f"✅ System sent text message: '{greeting_data.get('text')}'")
                print("❓ CHECK: Did you hear this greeting?")
        except asyncio.TimeoutError:
            print("⏱️ No greeting received within 5 seconds")
            
        # 3. Wait a bit then send a test message
        await asyncio.sleep(2)
        
        print("\n🗣️ Sending test prompt...")
        test_msg = {
            "type": "prompt",
            "callSid": call_sid,
            "voicePrompt": "Testing, testing, one two three",
            "transcript": "Testing, testing, one two three",
            "last": True
        }
        await ws.send(json.dumps(test_msg))
        
        # 4. Collect any responses
        print("\n📡 Waiting for responses...")
        timeout_count = 0
        while timeout_count < 3:
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=3.0)
                response_data = json.loads(response)
                messages_received.append(response_data)
                print(f"📨 Message {len(messages_received)}: {json.dumps(response_data, indent=2)}")
                
                if response_data.get('type') == 'text':
                    print(f"💬 Text to be spoken: '{response_data.get('text')}'")
                    
            except asyncio.TimeoutError:
                timeout_count += 1
                print(f"⏱️ Timeout {timeout_count}/3")
                
        # 5. Try sending a text message directly
        print("\n🎯 Testing direct text message...")
        test_text_msg = {
            "type": "text",
            "text": "This is a test. Can you hear me now?",
            "last": True
        }
        await ws.send(json.dumps(test_text_msg))
        print("📤 Sent direct text message (should hear nothing - we're not Twilio)")
        
        await asyncio.sleep(2)
        
    print("\n" + "=" * 50)
    print("🏁 Protocol Test Complete")
    print(f"\nTotal messages received: {len(messages_received)}")
    print("\nSummary of message types:")
    for i, msg in enumerate(messages_received):
        print(f"  {i+1}. Type: {msg.get('type')}, Text: {msg.get('text', 'N/A')[:50]}...")


if __name__ == "__main__":
    print("🚀 Running ConversationRelay Protocol Test")
    print("📡 This test will help identify where TTS is failing")
    print("-" * 50)
    
    asyncio.run(test_conversation_relay_messages())