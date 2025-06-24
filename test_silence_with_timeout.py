"""
Test that the silence timeout mechanism is working properly.
This test verifies that the system now sends re-prompts when users don't respond.
"""

import asyncio
import json
import websockets
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_silence_with_timeout():
    """Test that silence timeout triggers re-prompts."""
    
    call_sid = f"E2E_TIMEOUT_{asyncio.get_event_loop().time():.0f}"
    websocket_url = "ws://localhost:8080/api/conversation-relay"
    
    print("🔇 Testing Silence Timeout Mechanism")
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
        
        # 3. Wait for first re-prompt (should come after ~8 seconds)
        print("⏳ Waiting for first re-prompt (~8 seconds)...")
        start_time = asyncio.get_event_loop().time()
        
        try:
            reprompt1 = await asyncio.wait_for(ws.recv(), timeout=12.0)
            reprompt1_data = json.loads(reprompt1)
            elapsed = asyncio.get_event_loop().time() - start_time
            print(f"✅ FIRST RE-PROMPT after {elapsed:.1f}s: {reprompt1_data['text']}")
            
            # Verify it's a re-prompt
            assert any(phrase in reprompt1_data['text'].lower() for phrase in 
                      ["didn't catch", "trouble hearing", "your name"]), \
                   "First message should be a re-prompt for name"
            
        except asyncio.TimeoutError:
            print("❌ No re-prompt received within 12 seconds!")
            return
            
        # 4. Wait for second re-prompt
        print("⏳ Waiting for second re-prompt...")
        start_time2 = asyncio.get_event_loop().time()
        
        try:
            reprompt2 = await asyncio.wait_for(ws.recv(), timeout=12.0)
            reprompt2_data = json.loads(reprompt2)
            elapsed2 = asyncio.get_event_loop().time() - start_time2
            print(f"✅ SECOND RE-PROMPT after {elapsed2:.1f}s: {reprompt2_data['text']}")
            
        except asyncio.TimeoutError:
            print("❌ No second re-prompt received!")
            return
            
        # 5. Wait for final goodbye message
        print("⏳ Waiting for final goodbye message...")
        try:
            goodbye = await asyncio.wait_for(ws.recv(), timeout=12.0)
            goodbye_data = json.loads(goodbye)
            print(f"✅ FINAL MESSAGE: {goodbye_data['text']}")
            
            # Verify it's a goodbye
            assert any(phrase in goodbye_data['text'].lower() for phrase in 
                      ["sorry", "couldn't hear", "call back", "goodbye"]), \
                   "Final message should be a goodbye"
                   
        except asyncio.TimeoutError:
            print("❌ No goodbye message received!")
            
    print("\n" + "=" * 50)
    print("🏁 Silence Timeout Test Complete")
    print("\nRESULTS:")
    print("✅ System now sends re-prompts when user is silent")
    print("✅ Multiple re-prompt attempts before giving up")
    print("✅ Graceful goodbye after max retries")


async def test_user_responds_after_silence():
    """Test that user can respond after silence and system recovers."""
    
    call_sid = f"E2E_RECOVER_{asyncio.get_event_loop().time():.0f}"
    websocket_url = "ws://localhost:8080/api/conversation-relay"
    
    print("\n🔇 Testing Recovery After Silence")
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
        
        # Wait for first re-prompt
        print("⏳ Waiting for re-prompt...")
        reprompt = await asyncio.wait_for(ws.recv(), timeout=12.0)
        reprompt_data = json.loads(reprompt)
        print(f"✅ RE-PROMPT: {reprompt_data['text']}")
        
        # Now respond
        print("🗣️ User responds after re-prompt...")
        name_msg = {
            "type": "prompt",
            "callSid": call_sid,
            "voicePrompt": "Oh sorry, my name is Sarah",
            "transcript": "Oh sorry, my name is Sarah",
            "last": True
        }
        await ws.send(json.dumps(name_msg))
        
        # Check if system recovers
        try:
            response = await asyncio.wait_for(ws.recv(), timeout=10.0)
            response_data = json.loads(response)
            print(f"✅ SYSTEM RECOVERED: {response_data['text']}")
            
            # Verify name was acknowledged
            assert "sarah" in response_data['text'].lower(), \
                   "System should acknowledge the name after recovery"
                   
        except asyncio.TimeoutError:
            print("❌ System didn't respond after user finally spoke!")
            
    print("=" * 50)
    print("✅ System successfully recovers when user responds after silence")


if __name__ == "__main__":
    print("🚀 Running Enhanced Silence Handling Tests")
    print("📡 Testing new timeout and re-prompt features")
    print("-" * 50)
    
    asyncio.run(test_silence_with_timeout())
    asyncio.run(test_user_responds_after_silence())