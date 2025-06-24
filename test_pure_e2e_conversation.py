"""
Pure E2E test for RedBarSushiAI using live external services.
Simulates Twilio ConversationRelay messages over WebSocket.
"""

import asyncio
import json
import websockets
import logging
from datetime import datetime
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConversationRelayE2EClient:
    """E2E test client that simulates Twilio ConversationRelay messages."""
    
    def __init__(self, websocket_url: str, call_sid: str):
        self.websocket_url = websocket_url
        self.call_sid = call_sid
        self.websocket = None
        self.conversation_log = []
        
    async def connect(self):
        """Connect to the WebSocket endpoint."""
        logger.info(f"Connecting to {self.websocket_url}")
        self.websocket = await websockets.connect(self.websocket_url)
        logger.info("WebSocket connected")
        
    async def send_setup(self):
        """Send initial setup message as ConversationRelay would."""
        setup_msg = {
            "type": "setup",
            "callSid": self.call_sid,
            "from": "+1234567890",  # Test phone number
            "to": "+19876543210",    # Restaurant number
            "direction": "inbound",
            "callStatus": "in-progress",
            "accountSid": "TEST_ACCOUNT",
            "applicationSid": "TEST_APP",
            "conversationSid": f"CONV_{self.call_sid}",
            "streamSid": f"STREAM_{self.call_sid}"
        }
        
        logger.info("Sending setup message")
        await self.websocket.send(json.dumps(setup_msg))
        self.conversation_log.append({"type": "sent", "message": setup_msg})
        
    async def send_prompt(self, transcript: str):
        """Send a user prompt as ConversationRelay would."""
        prompt_msg = {
            "type": "prompt",
            "callSid": self.call_sid,
            "transcript": transcript,
            "voicePrompt": transcript,
            "last": True,
            "confidence": 0.95
        }
        
        logger.info(f"Sending prompt: {transcript}")
        await self.websocket.send(json.dumps(prompt_msg))
        self.conversation_log.append({"type": "sent", "message": prompt_msg})
        
    async def receive_response(self, timeout: float = 30.0):
        """Receive and parse response from the server."""
        try:
            response = await asyncio.wait_for(
                self.websocket.recv(),
                timeout=timeout
            )
            
            data = json.loads(response)
            logger.info(f"Received: {data}")
            self.conversation_log.append({"type": "received", "message": data})
            return data
            
        except asyncio.TimeoutError:
            logger.error(f"Timeout waiting for response after {timeout}s")
            raise
        except Exception as e:
            logger.error(f"Error receiving response: {e}")
            raise
            
    async def close(self):
        """Close the WebSocket connection."""
        if self.websocket:
            await self.websocket.close()
            logger.info("WebSocket closed")


async def test_pure_e2e_happy_path():
    """
    Test a simple happy path order with live external services.
    This test will make real calls to OpenAI, Deliverect, etc.
    """
    
    # Use a unique call SID for this test run
    call_sid = f"E2E_TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # WebSocket URL - adjust based on your environment
    # For local Docker: ws://localhost:8000/api/conversation-relay
    # For container-to-container: ws://redbarsushi-app:8080/api/conversation-relay
    # When running inside the same container: ws://localhost:8080/api/conversation-relay
    websocket_url = "ws://localhost:8080/api/conversation-relay"
    
    client = ConversationRelayE2EClient(websocket_url, call_sid)
    
    try:
        # Connect to WebSocket
        await client.connect()
        
        # Send setup message
        await client.send_setup()
        
        # Expect greeting response
        greeting = await client.receive_response()
        assert "text" in greeting or "response" in greeting
        greeting_text = greeting.get("text", greeting.get("response", ""))
        assert any(word in greeting_text.lower() for word in ["welcome", "hello", "hi"]), \
            f"Expected greeting, got: {greeting_text}"
        print(f"✅ Greeting received: {greeting_text[:100]}...")
        
        # Provide name
        await client.send_prompt("My name is John Test")
        name_response = await client.receive_response()
        assert "text" in name_response or "response" in name_response
        name_text = name_response.get("text", name_response.get("response", ""))
        # Flexible assertion - LLM might acknowledge name differently
        assert any(word in name_text.lower() for word in ["john", "thank", "nice", "help"]), \
            f"Expected name acknowledgment, got: {name_text}"
        print(f"✅ Name acknowledged: {name_text[:100]}...")
        
        # Ask about menu (this will trigger real OpenAI call for intent detection)
        await client.send_prompt("What sushi rolls do you have?")
        menu_response = await client.receive_response()
        assert "text" in menu_response or "response" in menu_response
        menu_text = menu_response.get("text", menu_response.get("response", "")).lower()
        # Check for menu items - be flexible as exact items may vary
        assert any(word in menu_text for word in ["roll", "sushi", "california", "tuna", "salmon"]), \
            f"Expected menu items, got: {menu_text}"
        print(f"✅ Menu received: {menu_text[:200]}...")
        
        # Place a simple order
        await client.send_prompt("I'll have one California roll please")
        order_response = await client.receive_response()
        assert "text" in order_response or "response" in order_response
        order_text = order_response.get("text", order_response.get("response", "")).lower()
        # Check for order confirmation elements
        assert any(word in order_text for word in ["california", "added", "order", "anything"]), \
            f"Expected order confirmation, got: {order_text}"
        print(f"✅ Order acknowledged: {order_text[:100]}...")
        
        # Complete order for pickup
        await client.send_prompt("That's all, I'll pick it up")
        complete_response = await client.receive_response()
        assert "text" in complete_response or "response" in complete_response
        complete_text = complete_response.get("text", complete_response.get("response", "")).lower()
        # Check for completion elements
        assert any(word in complete_text for word in ["total", "pickup", "ready", "confirm"]), \
            f"Expected order completion, got: {complete_text}"
        print(f"✅ Order completion: {complete_text[:100]}...")
        
        # If asked for phone number, provide it
        if "phone" in complete_text:
            await client.send_prompt("My phone number is 555-0123")
            phone_response = await client.receive_response()
            phone_text = phone_response.get("text", phone_response.get("response", ""))
            print(f"✅ Phone provided: {phone_text[:100]}...")
        
        print("\n🎉 Pure E2E test completed successfully!")
        print(f"Conversation included {len(client.conversation_log)} messages")
        
        # Log full conversation for debugging
        print("\n📝 Full conversation log:")
        for i, entry in enumerate(client.conversation_log):
            direction = "→" if entry["type"] == "sent" else "←"
            msg = entry["message"]
            if entry["type"] == "sent" and "transcript" in msg:
                print(f"{i+1}. {direction} User: {msg['transcript']}")
            elif entry["type"] == "received":
                response_text = msg.get("text", msg.get("response", ""))
                if response_text:
                    print(f"{i+1}. {direction} AI: {response_text[:200]}...")
                
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise
        
    finally:
        await client.close()


if __name__ == "__main__":
    print("🚀 Starting Pure E2E Test with Live External Services")
    print("⚠️  This test will make real API calls to:")
    print("   - OpenAI (for intent detection and responses)")
    print("   - Deliverect (if order submission is reached)")
    print("   - Possibly Twilio (for SMS, if enabled)")
    print()
    
    asyncio.run(test_pure_e2e_happy_path())