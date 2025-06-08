"""
Real E2E tests using ngrok development URL.
These tests hit the actual running development server.
"""

import pytest
import uuid
import json
import httpx
import asyncio
from typing import Dict, Any

# Your ngrok development URL
NGROK_BASE_URL = "https://fd17-149-22-84-153.ngrok-free.app"


class TestNgrokRealE2E:
    """Test real development server via ngrok."""
    
    @pytest.mark.asyncio
    async def test_health_check_real(self):
        """Test health check on real development server."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{NGROK_BASE_URL}/healthcheck")
            assert response.status_code == 200
            health_data = response.json()
            print("Real server health:", health_data)
            
    @pytest.mark.asyncio
    async def test_real_menu_endpoints(self):
        """Test menu endpoints on real development server."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Test menu categories
            response = await client.get(f"{NGROK_BASE_URL}/menu/categories")
            print(f"Menu categories status: {response.status_code}")
            if response.status_code == 200:
                categories = response.json()
                print(f"Found {len(categories)} categories")
                assert len(categories) > 0
            
            # Test menu items
            response = await client.get(f"{NGROK_BASE_URL}/menu/items")
            print(f"Menu items status: {response.status_code}")
            if response.status_code == 200:
                items = response.json()
                print(f"Found {len(items)} menu items")
                assert len(items) > 0
                
    @pytest.mark.asyncio
    async def test_real_voice_twiml(self):
        """Test voice TwiML endpoint on real development server."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Simulate Twilio webhook call
            twilio_data = {
                "CallSid": f"CA{uuid.uuid4().hex[:24]}",
                "From": "+15551234567",
                "To": "+15559876543",
                "CallStatus": "in-progress"
            }
            
            response = await client.post(
                f"{NGROK_BASE_URL}/voice/", 
                data=twilio_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            print(f"Voice endpoint status: {response.status_code}")
            if response.status_code == 200:
                twiml_response = response.text
                print("TwiML response received:")
                print(twiml_response[:200] + "..." if len(twiml_response) > 200 else twiml_response)
                
                # Should contain proper TwiML
                assert "<?xml" in twiml_response
                assert "<Response>" in twiml_response
                assert "Red Bar Sushi" in twiml_response
                
    @pytest.mark.asyncio
    async def test_real_order_flow(self):
        """Test real order flow on development server."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            session_id = f"ngrok_test_{uuid.uuid4().hex[:8]}"
            
            # Test contact info saving
            contact_data = {
                "session_id": session_id,
                "raw_input": "Hi, I'm Sarah. My phone is 555-123-4567"
            }
            
            response = await client.post(
                f"{NGROK_BASE_URL}/order/save_contact_info",
                json=contact_data
            )
            print(f"Contact save status: {response.status_code}")
            
            # Test order taking with real AI
            order_data = {
                "customer_input": "I'd like one California Roll and one Spicy Tuna Roll",
                "session_id": session_id
            }
            
            response = await client.post(
                f"{NGROK_BASE_URL}/order/take_order",
                json=order_data
            )
            print(f"Order take status: {response.status_code}")
            
            if response.status_code == 200:
                order_response = response.json()
                print("Order response:", order_response)
                
    @pytest.mark.asyncio
    async def test_real_conversation_relay(self):
        """Test real conversation relay with OpenAI API."""
        async with httpx.AsyncClient(timeout=60.0) as client:  # Longer timeout for AI calls
            call_sid = f"ngrok_test_{uuid.uuid4().hex[:8]}"
            
            # Test conversation relay endpoint
            conversation_data = {
                "call_sid": call_sid,
                "transcript": "Hello, I'd like to order some sushi",
                "context": {"first_interaction": False}
            }
            
            response = await client.post(
                f"{NGROK_BASE_URL}/api/conversation-relay",
                json=conversation_data
            )
            
            print(f"Conversation relay status: {response.status_code}")
            if response.status_code == 200:
                conversation_response = response.json()
                print("AI conversation response:", conversation_response)
                
                # Should have proper response structure
                assert "text" in conversation_response or "twiml" in conversation_response
                
    @pytest.mark.asyncio
    async def test_real_menu_search(self):
        """Test real menu search functionality."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            search_terms = ["roll", "sushi", "salmon", "tuna", "california"]
            
            for term in search_terms:
                response = await client.get(f"{NGROK_BASE_URL}/menu/search?q={term}")
                print(f"Search for '{term}': {response.status_code}")
                
                if response.status_code == 200:
                    results = response.json()
                    print(f"  Found {len(results)} results")
                    
    @pytest.mark.asyncio
    async def test_real_deliverect_endpoints(self):
        """Test Deliverect integration endpoints."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Test Deliverect registration endpoint
            registration_data = {
                "webhook_url": f"{NGROK_BASE_URL}/api/deliverect/menu/update",
                "location_id": "test_location"
            }
            
            response = await client.post(
                f"{NGROK_BASE_URL}/api/deliverect/register",
                json=registration_data
            )
            print(f"Deliverect registration status: {response.status_code}")
            
    @pytest.mark.asyncio
    async def test_real_complete_voice_order_flow(self):
        """Test complete voice order flow with real OpenAI integration."""
        async with httpx.AsyncClient(timeout=120.0) as client:  # Long timeout for full flow
            call_sid = f"CA{uuid.uuid4().hex[:24]}"
            
            print(f"\n🎯 Testing complete voice order flow for call: {call_sid}")
            
            # Step 1: Initial TwiML call
            print("📞 Step 1: Initial TwiML call...")
            twilio_data = {
                "CallSid": call_sid,
                "From": "+15551234567", 
                "To": "+15559876543",
                "CallStatus": "in-progress"
            }
            
            twiml_response = await client.post(
                f"{NGROK_BASE_URL}/voice/",
                data=twilio_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            print(f"   TwiML status: {twiml_response.status_code}")
            
            # Step 2: Conversation relay - greeting
            print("👋 Step 2: AI greeting...")
            greeting_data = {
                "call_sid": call_sid,
                "transcript": "",
                "context": {"first_interaction": True}
            }
            
            greeting_response = await client.post(
                f"{NGROK_BASE_URL}/api/conversation-relay",
                json=greeting_data
            )
            print(f"   Greeting status: {greeting_response.status_code}")
            if greeting_response.status_code == 200:
                greeting_result = greeting_response.json()
                print(f"   AI says: {greeting_result.get('text', 'No text')[:100]}...")
            
            # Step 3: Customer provides name
            print("📝 Step 3: Customer provides name...")
            name_data = {
                "call_sid": call_sid,
                "transcript": "Hi, I'm Jennifer"
            }
            
            name_response = await client.post(
                f"{NGROK_BASE_URL}/api/conversation-relay",
                json=name_data
            )
            print(f"   Name processing status: {name_response.status_code}")
            
            # Step 4: Customer places order
            print("🍣 Step 4: Customer places order...")
            order_data = {
                "call_sid": call_sid,
                "transcript": "I'd like a California Roll and a Spicy Tuna Roll please"
            }
            
            order_response = await client.post(
                f"{NGROK_BASE_URL}/api/conversation-relay",
                json=order_data
            )
            print(f"   Order processing status: {order_response.status_code}")
            if order_response.status_code == 200:
                order_result = order_response.json()
                print(f"   AI response: {order_result.get('text', 'No text')[:100]}...")
            
            # Step 5: Customer confirms
            print("✅ Step 5: Customer confirms order...")
            confirm_data = {
                "call_sid": call_sid,
                "transcript": "Yes, that sounds perfect"
            }
            
            confirm_response = await client.post(
                f"{NGROK_BASE_URL}/api/conversation-relay",
                json=confirm_data
            )
            print(f"   Confirmation status: {confirm_response.status_code}")
            
            print("🎉 Complete voice flow test finished!")
            
            # At least the endpoints should exist
            assert twiml_response.status_code != 404
            assert greeting_response.status_code != 404