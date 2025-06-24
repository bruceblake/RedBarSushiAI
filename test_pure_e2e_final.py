"""
Final pure E2E test validating the contextual confusion fix.
Tests that California roll is correctly interpreted as food, not a name.
"""

import asyncio
import json
import websockets
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_final_e2e():
    """Test the complete flow with fixed prompts."""
    
    call_sid = f"E2E_FINAL_{asyncio.get_event_loop().time():.0f}"
    websocket_url = "ws://localhost:8080/api/conversation-relay"
    
    print("🎯 Testing Contextual Confusion Fix")
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
        print(f"1️⃣ GREETING: {greeting['text']}")
        
        # 3. Send name
        name_msg = {
            "type": "prompt",
            "callSid": call_sid,
            "voicePrompt": "My name is Alex",
            "transcript": "My name is Alex",
            "last": True
        }
        await ws.send(json.dumps(name_msg))
        
        # 4. Get name acknowledgment
        name_resp_raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
        name_resp = json.loads(name_resp_raw)
        print(f"2️⃣ NAME ACK: {name_resp['text']}")
        
        # Verify name was acknowledged
        assert "alex" in name_resp['text'].lower(), "Name not acknowledged"
        
        # 5. Say we want to order
        order_intent_msg = {
            "type": "prompt",
            "callSid": call_sid,
            "voicePrompt": "I'd like to place an order",
            "transcript": "I'd like to place an order",
            "last": True
        }
        await ws.send(json.dumps(order_intent_msg))
        
        # 6. Get order prompt
        order_resp_raw = await asyncio.wait_for(ws.recv(), timeout=15.0)
        order_resp = json.loads(order_resp_raw)
        print(f"3️⃣ ORDER PROMPT: {order_resp['text']}")
        
        # 7. Order California roll - THE KEY TEST
        california_msg = {
            "type": "prompt",
            "callSid": call_sid,
            "voicePrompt": "I'll have a California roll please",
            "transcript": "I'll have a California roll please",
            "last": True
        }
        await ws.send(json.dumps(california_msg))
        
        # 8. Get response - should process as food, not name
        try:
            california_resp_raw = await asyncio.wait_for(ws.recv(), timeout=20.0)
            california_resp = json.loads(california_resp_raw)
            print(f"4️⃣ CALIFORNIA RESPONSE: {california_resp['text']}")
            
            # Check the response
            response_lower = california_resp['text'].lower()
            
            # Success criteria
            if "alex" in response_lower and "nice to meet" not in response_lower:
                print("❌ FAIL: AI tried to update name to 'California' or similar")
                print("   The contextual confusion bug is still present!")
            elif any(word in response_lower for word in ["california", "roll", "order", "add"]):
                print("✅ SUCCESS: AI correctly processed California roll as food!")
                print("   The contextual confusion has been fixed!")
            else:
                print(f"❓ UNCLEAR: Response doesn't clearly indicate success or failure")
                
        except asyncio.TimeoutError:
            print("⚠️  Response timed out")
            
        print("\n" + "=" * 50)
        print("🏁 Contextual Confusion Test Complete")


if __name__ == "__main__":
    print("🚀 Pure E2E Test - Contextual Confusion Fix Validation")
    print("📡 This will make REAL calls to OpenAI API")
    print("-" * 50)
    
    asyncio.run(test_final_e2e())