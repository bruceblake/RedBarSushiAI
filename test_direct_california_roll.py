"""
Direct test for California roll ordering without cached responses.
"""

import asyncio
import json
import websockets
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_direct_order():
    """Test ordering California roll directly after greeting."""
    
    call_sid = f"E2E_DIRECT_{asyncio.get_event_loop().time():.0f}"
    websocket_url = "ws://localhost:8080/api/conversation-relay"
    
    logger.info(f"Starting direct order test with call ID: {call_sid}")
    
    async with websockets.connect(websocket_url) as ws:
        # 1. Send setup
        setup_msg = {
            "type": "setup",
            "callSid": call_sid,
            "from": "+1234567890",
            "direction": "inbound"
        }
        await ws.send(json.dumps(setup_msg))
        logger.info("✅ Sent setup message")
        
        # 2. Get greeting
        greeting_raw = await ws.recv()
        greeting = json.loads(greeting_raw)
        logger.info(f"Received: {greeting}")
        print(f"✅ GREETING: {greeting['text']}")
        
        # 3. Send name and order in one message
        name_and_order_msg = {
            "type": "prompt",
            "callSid": call_sid,
            "voicePrompt": "Hi, my name is Sarah and I'd like to order a California roll",
            "transcript": "Hi, my name is Sarah and I'd like to order a California roll",
            "last": True
        }
        await ws.send(json.dumps(name_and_order_msg))
        logger.info("✅ Sent name AND order together")
        
        # 4. Get response - should acknowledge both name and order
        try:
            response_raw = await asyncio.wait_for(ws.recv(), timeout=20.0)
            response = json.loads(response_raw)
            logger.info(f"Received response: {response}")
            print(f"✅ RESPONSE: {response['text']}")
            
            # Check what the AI said
            response_text_lower = response['text'].lower()
            if "sarah" in response_text_lower:
                print("✅ AI acknowledged the name!")
            if "california" in response_text_lower or "roll" in response_text_lower:
                print("✅ AI acknowledged the California roll!")
            
            # If AI asks for more info or confirmation, send confirmation
            if any(word in response_text_lower for word in ["else", "more", "confirm", "anything"]):
                confirm_msg = {
                    "type": "prompt",
                    "callSid": call_sid,
                    "voicePrompt": "That's all, thanks",
                    "transcript": "That's all, thanks",
                    "last": True
                }
                await ws.send(json.dumps(confirm_msg))
                
                # Get final response
                final_raw = await asyncio.wait_for(ws.recv(), timeout=15.0)
                final = json.loads(final_raw)
                print(f"✅ FINAL: {final['text']}")
                
        except asyncio.TimeoutError:
            logger.error("Timeout waiting for response")
            print("⚠️  Response timed out - check app logs")
            
        print("\n🎉 Direct order test completed!")


if __name__ == "__main__":
    print("🚀 Running Direct California Roll Order Test")
    print("📡 This will make REAL calls to OpenAI API")
    print("-" * 50)
    
    asyncio.run(test_direct_order())