"""
Simple E2E test for conversation flow using TestClient.
Tests the actual conversation through HTTP endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
import json


@pytest.mark.asyncio
async def test_simple_conversation_flow():
    """Test a simple conversation flow through HTTP endpoints."""
    from app.main import app
    
    client = TestClient(app)
    call_sid = "TEST_E2E_123"
    
    # Mock OpenAI responses for predictable behavior
    with patch('openai.AsyncOpenAI') as mock_openai_class:
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        # Configure mock responses
        mock_client.chat.completions.create.side_effect = [
            # Intent detection for empty input (greeting)
            AsyncMock(choices=[AsyncMock(message=AsyncMock(content="REQUEST_GREETING"))]),
            # Intent detection for name
            AsyncMock(choices=[AsyncMock(message=AsyncMock(content="PROVIDE_NAME"))]),
            # Intent detection for menu request  
            AsyncMock(choices=[AsyncMock(message=AsyncMock(content="REQUEST_MENU"))]),
            # Menu agent response
            AsyncMock(choices=[AsyncMock(message=AsyncMock(content=json.dumps({
                "response": "We have California Roll ($12.95), Spicy Tuna Roll ($14.95), and Miso Soup ($4.95). What would you like?",
                "requires_response": True,
                "confidence": 0.95
            })))]),
        ]
        
        # Test 1: Initial webhook call
        print("\n1. Testing initial webhook...")
        webhook_response = client.post(
            "/voice/webhook",
            data={"CallSid": call_sid, "From": "+1234567890"}
        )
        assert webhook_response.status_code == 200
        assert b"<Connect>" in webhook_response.content
        print("✅ Webhook returned TwiML with Connect")
        
        # Test 2: Test conversation relay endpoint exists
        print("\n2. Testing conversation relay endpoint...")
        test_response = client.get("/api/test")
        print(f"Test endpoint status: {test_response.status_code}")
        if test_response.status_code != 200:
            print(f"Test endpoint response: {test_response.text}")
        assert test_response.status_code == 200
        print("✅ Conversation relay endpoint is accessible")
        
        # Test 3: Simulate a conversation using the debug webhook
        print("\n3. Testing conversation flow via debug webhook...")
        
        # Initial greeting
        greeting_response = client.post(
            "/api/debug-webhook",
            json={
                "CallSid": call_sid,
                "transcript": "",
                "type": "setup"
            }
        )
        print(f"Debug webhook status: {greeting_response.status_code}")
        if greeting_response.status_code != 200:
            print(f"Debug webhook error: {greeting_response.text}")
        assert greeting_response.status_code == 200
        greeting_data = greeting_response.json()
        print(f"Greeting: {greeting_data.get('response', 'No response')}")
        assert "response" in greeting_data
        
        # Provide name
        name_response = client.post(
            "/api/debug-webhook",
            json={
                "CallSid": call_sid,
                "transcript": "My name is John",
                "type": "prompt"
            }
        )
        assert name_response.status_code == 200
        name_data = name_response.json()
        print(f"Name response: {name_data.get('response', 'No response')}")
        
        # Ask about menu
        menu_response = client.post(
            "/api/debug-webhook",
            json={
                "CallSid": call_sid,
                "transcript": "What's on the menu?",
                "type": "prompt"
            }
        )
        assert menu_response.status_code == 200
        menu_data = menu_response.json()
        print(f"Menu response: {menu_data.get('response', 'No response')}")
        
        print("\n✅ E2E conversation test passed!")
        return True


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_simple_conversation_flow())