"""
Test name recognition in voice flow.
"""
import pytest
import asyncio
import json
import websockets
import os

BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8080")
WS_BASE_URL = BASE_URL.replace("http://", "ws://").replace("https://", "wss://")


class TestNameRecognition:
    """Test name recognition functionality."""
    
    @pytest.mark.asyncio
    async def test_simple_name_recognition(self):
        """Test recognizing a simple name like 'Bruce'."""
        ws_url = f"{WS_BASE_URL}/api/conversation-relay"
        
        async with websockets.connect(ws_url) as websocket:
            # Send setup
            setup_msg = {
                "type": "setup",
                "sessionId": "session_test_bruce",
                "callSid": "CAtest_bruce_001",
                "from": "+15551234567",
                "to": "+17036467799",
                "callStatus": "in-progress"
            }
            await websocket.send(json.dumps(setup_msg))
            
            # Get greeting
            greeting_msg = await websocket.recv()
            greeting = json.loads(greeting_msg)
            print(f"\n🤖 AI Greeting: {greeting.get('token', '')}")
            assert "name" in greeting.get("token", "").lower()
            
            # Send name
            name_msg = {
                "type": "prompt",
                "voicePrompt": "Bruce.",
                "lang": "en-US",
                "last": True
            }
            await websocket.send(json.dumps(name_msg))
            print(f"\n💬 User says: Bruce.")
            
            # Get response
            response_msg = await websocket.recv()
            response = json.loads(response_msg)
            ai_response = response.get("token", "")
            print(f"\n🤖 AI Response: {ai_response}")
            
            # Check that Bruce is mentioned in the response
            assert "bruce" in ai_response.lower(), f"Name 'Bruce' not found in response: {ai_response}"
            assert ("nice to meet you" in ai_response.lower() or 
                   "hello bruce" in ai_response.lower() or
                   "hi bruce" in ai_response.lower()), "Expected greeting with name"
            
    @pytest.mark.asyncio
    async def test_full_name_recognition(self):
        """Test recognizing a full name."""
        ws_url = f"{WS_BASE_URL}/api/conversation-relay"
        
        async with websockets.connect(ws_url) as websocket:
            # Send setup
            setup_msg = {
                "type": "setup",
                "sessionId": "session_test_fullname",
                "callSid": "CAtest_fullname_001",
                "from": "+15551234567",
                "to": "+17036467799",
                "callStatus": "in-progress"
            }
            await websocket.send(json.dumps(setup_msg))
            
            # Get greeting
            greeting_msg = await websocket.recv()
            greeting = json.loads(greeting_msg)
            print(f"\n🤖 AI Greeting: {greeting.get('token', '')}")
            
            # Send full name
            name_msg = {
                "type": "prompt",
                "voicePrompt": "My name is Sarah Johnson",
                "lang": "en-US",
                "last": True
            }
            await websocket.send(json.dumps(name_msg))
            print(f"\n💬 User says: My name is Sarah Johnson")
            
            # Get response
            response_msg = await websocket.recv()
            response = json.loads(response_msg)
            ai_response = response.get("token", "")
            print(f"\n🤖 AI Response: {ai_response}")
            
            # Check that name is mentioned
            assert ("sarah" in ai_response.lower() or "johnson" in ai_response.lower()), \
                f"Name not found in response: {ai_response}"
            
    @pytest.mark.asyncio
    async def test_name_then_order(self):
        """Test name recognition followed by order placement."""
        ws_url = f"{WS_BASE_URL}/api/conversation-relay"
        
        async with websockets.connect(ws_url) as websocket:
            # Send setup
            setup_msg = {
                "type": "setup",
                "sessionId": "session_test_order",
                "callSid": "CAtest_order_001",
                "from": "+15551234567",
                "to": "+17036467799",
                "callStatus": "in-progress"
            }
            await websocket.send(json.dumps(setup_msg))
            
            # Get greeting
            greeting_msg = await websocket.recv()
            print(f"\n🤖 AI: {json.loads(greeting_msg).get('token', '')}")
            
            # Send name
            name_msg = {
                "type": "prompt",
                "voicePrompt": "Hi, I'm Alex",
                "lang": "en-US",
                "last": True
            }
            await websocket.send(json.dumps(name_msg))
            print(f"\n💬 User: Hi, I'm Alex")
            
            # Get response with name
            response_msg = await websocket.recv()
            response = json.loads(response_msg)
            print(f"\n🤖 AI: {response.get('token', '')}")
            assert "alex" in response.get("token", "").lower()
            
            # Now place an order
            order_msg = {
                "type": "prompt",
                "voicePrompt": "I'd like to order a California roll for pickup",
                "lang": "en-US",
                "last": True
            }
            await websocket.send(json.dumps(order_msg))
            print(f"\n💬 User: I'd like to order a California roll for pickup")
            
            # Get order response
            order_response_msg = await websocket.recv()
            order_response = json.loads(order_response_msg)
            print(f"\n🤖 AI: {order_response.get('token', '')}")
            
            # Should acknowledge the order
            response_text = order_response.get("token", "").lower()
            assert any(word in response_text for word in ["california", "order", "pickup"]), \
                f"Order not acknowledged in: {order_response.get('token', '')}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])