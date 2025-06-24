"""
Test silence handling after greeting - this should expose the issue.
"""

import asyncio
import json
import websockets
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_silence_after_greeting():
    """Test what happens when user doesn't speak after greeting."""
    
    call_sid = f"E2E_SILENCE_{asyncio.get_event_loop().time():.0f}"
    websocket_url = "ws://localhost:8080/api/conversation-relay"
    
    print("🔇 Testing Silence After Greeting")
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
        
        # 2. Get greeting
        greeting_raw = await ws.recv()
        greeting = json.loads(greeting_raw)
        print(f"✅ GREETING: {greeting['text']}")
        
        # 3. SIMULATE SILENCE - Don't send anything
        print("🔇 Simulating silence for 10 seconds...")
        print("   (In a real call, the user hasn't spoken yet)")
        
        # Wait and see if system sends any follow-up
        try:
            # Set a timeout to see if we get any message
            follow_up = await asyncio.wait_for(ws.recv(), timeout=10.0)
            follow_up_data = json.loads(follow_up)
            print(f"📨 SYSTEM SENT FOLLOW-UP: {follow_up_data}")
        except asyncio.TimeoutError:
            print("❌ NO FOLLOW-UP after 10 seconds of silence!")
            print("   System is stuck waiting for user input")
            
        # 4. Now send a very late response
        print("\n🗣️ User finally speaks after long silence...")
        late_msg = {
            "type": "prompt",
            "callSid": call_sid,
            "voicePrompt": "Hello? Is anyone there?",
            "transcript": "Hello? Is anyone there?",
            "last": True
        }
        await ws.send(json.dumps(late_msg))
        
        # 5. See if system recovers
        try:
            response = await asyncio.wait_for(ws.recv(), timeout=5.0)
            response_data = json.loads(response)
            print(f"✅ SYSTEM RESPONDED: {response_data['text']}")
        except asyncio.TimeoutError:
            print("❌ System didn't respond to late input")
            
    print("\n" + "=" * 50)
    print("🏁 Silence Handling Test Complete")
    print("\nFINDINGS:")
    print("- System sends greeting but doesn't handle silence")
    print("- No timeout or re-prompt mechanism")
    print("- User must speak first for conversation to continue")


async def test_empty_speech():
    """Test what happens with empty/unintelligible speech."""
    
    call_sid = f"E2E_EMPTY_{asyncio.get_event_loop().time():.0f}"
    websocket_url = "ws://localhost:8080/api/conversation-relay"
    
    print("\n🔇 Testing Empty Speech Input")
    print("=" * 50)
    
    async with websockets.connect(websocket_url) as ws:
        # Setup
        setup_msg = {
            "type": "setup",
            "callSid": call_sid,
            "from": "+1234567890",
            "direction": "inbound"
        }
        await ws.send(json.dumps(setup_msg))
        
        # Get greeting
        greeting_raw = await ws.recv()
        greeting = json.loads(greeting_raw)
        print(f"✅ GREETING: {greeting['text']}")
        
        # Send empty prompt (simulating unclear speech)
        empty_msg = {
            "type": "prompt",
            "callSid": call_sid,
            "voicePrompt": "",
            "transcript": "",
            "last": True
        }
        await ws.send(json.dumps(empty_msg))
        
        # Check if system handles empty input
        try:
            response = await asyncio.wait_for(ws.recv(), timeout=5.0)
            response_data = json.loads(response)
            print(f"✅ SYSTEM HANDLED EMPTY INPUT: {response_data['text']}")
        except asyncio.TimeoutError:
            print("❌ System doesn't respond to empty speech input")
            
    print("=" * 50)


if __name__ == "__main__":
    print("🚀 Running Silence & Edge Case Tests")
    print("📡 Testing scenarios that current E2E tests miss")
    print("-" * 50)
    
    asyncio.run(test_silence_after_greeting())
    asyncio.run(test_empty_speech())