"""
Simple E2E test for WebSocket conversation flow.
Tests the actual /api/conversation-relay endpoint.
"""

import asyncio
import json
import pytest
import websockets
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_simple_websocket_conversation():
    """Test a simple conversation flow through the WebSocket endpoint."""
    
    # Mock OpenAI to return predictable responses
    mock_openai_response = AsyncMock()
    
    with patch('openai.AsyncOpenAI') as mock_openai_class:
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        # Mock intent detection
        mock_client.chat.completions.create.side_effect = [
            # First call: intent detection for name
            AsyncMock(choices=[AsyncMock(message=AsyncMock(content="PROVIDE_NAME"))]),
            # Second call: intent detection for menu request  
            AsyncMock(choices=[AsyncMock(message=AsyncMock(content="REQUEST_MENU"))]),
            # Third call: menu agent response
            AsyncMock(choices=[AsyncMock(message=AsyncMock(content=json.dumps({
                "response": "We have California Roll ($12.95), Spicy Tuna Roll ($14.95), and Miso Soup ($4.95). What would you like?",
                "requires_response": True,
                "confidence": 0.95
            })))]),
        ]
        
        # Connect to WebSocket
        uri = "ws://localhost:8000/api/conversation-relay"
        
        try:
            async with websockets.connect(uri) as websocket:
                # Wait for connection
                await asyncio.sleep(0.1)
                
                # Send initial connection message
                await websocket.send(json.dumps({
                    "type": "setup",
                    "CallSid": "TEST123",
                    "From": "+1234567890"
                }))
                
                # Wait for and verify greeting
                greeting = await websocket.recv()
                greeting_data = json.loads(greeting)
                print(f"Greeting: {greeting_data}")
                assert "response" in greeting_data
                assert "welcome" in greeting_data["response"].lower()
                
                # Send name
                await websocket.send(json.dumps({
                    "type": "prompt", 
                    "CallSid": "TEST123",
                    "transcript": "My name is John"
                }))
                
                # Wait for acknowledgment
                ack = await websocket.recv()
                ack_data = json.loads(ack)
                print(f"Name acknowledgment: {ack_data}")
                assert "response" in ack_data
                
                # Ask about menu
                await websocket.send(json.dumps({
                    "type": "prompt",
                    "CallSid": "TEST123", 
                    "transcript": "What's on the menu?"
                }))
                
                # Wait for menu response
                menu = await websocket.recv()
                menu_data = json.loads(menu)
                print(f"Menu response: {menu_data}")
                assert "response" in menu_data
                assert any(item in menu_data["response"] for item in ["California", "Tuna", "Soup"])
                
                print("✅ E2E WebSocket test passed!")
                
        except Exception as e:
            print(f"❌ WebSocket test failed: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(test_simple_websocket_conversation())