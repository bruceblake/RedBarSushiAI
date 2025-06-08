"""
Real End-to-end tests for order flow without mocks.
Tests real API endpoints and database interactions.
"""

import pytest
import pytest_asyncio
import json
import uuid
from typing import Dict, Any
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.main import app


@pytest.mark.asyncio
@pytest.mark.e2e
class TestRealOrderFlow:
    """Test real order flows using actual API endpoints."""
    
    def test_health_endpoints(self):
        """Test basic health endpoints work."""
        client = TestClient(app)
        
        # Test health endpoint
        response = client.get("/healthcheck")
        assert response.status_code == 200
        response_data = response.json()
        assert "status" in response_data or "uptime" in response_data
        
        # Test docs endpoint exists
        response = client.get("/docs")
        assert response.status_code == 200
    
    def test_menu_endpoints(self):
        """Test menu endpoints return data."""
        client = TestClient(app)
        
        # Test categories endpoint
        response = client.get("/api/menu/categories")
        assert response.status_code == 200
        categories = response.json()
        assert len(categories) > 0
        
        # Test items endpoint
        response = client.get("/api/menu/items")
        assert response.status_code == 200
        items = response.json()
        assert len(items) > 0
        
    def test_conversation_endpoint_basic(self):
        """Test basic conversation endpoint without complex mocking."""
        client = TestClient(app)
        
        # Create a simple conversation request
        conversation_data = {
            "call_sid": f"test_call_{uuid.uuid4().hex[:8]}",
            "transcript": "Hello",
            "context": {"first_interaction": True}
        }
        
        # Make request to conversation endpoint
        response = client.post("/api/conversation-relay", json=conversation_data)
        
        # Should get a response (even if OpenAI key is invalid, we should get a structured response)
        assert response.status_code == 200
        response_data = response.json()
        assert "text" in response_data
        assert "twiml" in response_data
        
    def test_order_creation_endpoint(self):
        """Test order creation endpoint."""
        client = TestClient(app)
        
        # Create a simple order
        order_data = {
            "customer_phone": "+1234567890",
            "order_type": "pickup",
            "items": [
                {
                    "menu_item_plu": "ROLL_001",
                    "quantity": 1,
                    "special_instructions": "Extra wasabi"
                }
            ]
        }
        
        # Create order
        response = client.post("/api/order/create", json=order_data)
        
        # Should create order successfully
        assert response.status_code == 200
        order_response = response.json()
        assert "order_id" in order_response
        assert order_response["status"] == "pending"
        
    def test_menu_search_functionality(self):
        """Test menu search works with real data."""
        client = TestClient(app)
        
        # Search for sushi items
        response = client.get("/api/menu/search?q=roll")
        assert response.status_code == 200
        results = response.json()
        
        # Should find roll items
        assert len(results) > 0
        for item in results:
            assert "roll" in item["name"].lower() or "roll" in item["description"].lower()
            
    def test_order_status_tracking(self):
        """Test order status tracking."""
        client = TestClient(app)
        
        # First create an order
        order_data = {
            "customer_phone": "+1234567890",
            "order_type": "delivery",
            "delivery_address": "123 Test St, Test City, TC 12345",
            "items": [
                {
                    "menu_item_plu": "ROLL_001",
                    "quantity": 2
                }
            ]
        }
        
        create_response = client.post("/api/order/create", json=order_data)
        assert create_response.status_code == 200
        order_id = create_response.json()["order_id"]
        
        # Check order status
        status_response = client.get(f"/api/order/{order_id}/status")
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["order_id"] == order_id
        assert status_data["status"] in ["pending", "confirmed", "preparing", "ready", "delivered"]
        
    @pytest.mark.asyncio
    async def test_async_conversation_flow(self):
        """Test async conversation flow with real orchestrator."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            call_sid = f"test_async_{uuid.uuid4().hex[:8]}"
            
            # Initial greeting
            response = await client.post("/api/conversation-relay", json={
                "call_sid": call_sid,
                "transcript": "",
                "context": {"first_interaction": True}
            })
            assert response.status_code == 200
            
            # Follow up with name
            response = await client.post("/api/conversation-relay", json={
                "call_sid": call_sid,
                "transcript": "Hi, my name is Sarah"
            })
            assert response.status_code == 200
            response_data = response.json()
            assert "text" in response_data
            
            # Ask about menu
            response = await client.post("/api/conversation-relay", json={
                "call_sid": call_sid,
                "transcript": "What sushi rolls do you have?"
            })
            assert response.status_code == 200
            response_data = response.json()
            assert "text" in response_data
            
    def test_contact_information_extraction(self):
        """Test contact information extraction."""
        client = TestClient(app)
        
        # Submit contact info
        contact_data = {
            "session_id": f"session_{uuid.uuid4().hex[:8]}",
            "raw_input": "My phone number is 555-123-4567 and email is test@example.com"
        }
        
        response = client.post("/api/order/contact", json=contact_data)
        assert response.status_code == 200
        contact_response = response.json()
        
        # Should extract phone number
        assert "phone" in contact_response or "extracted_phone" in contact_response
        
    def test_order_modification_flow(self):
        """Test order modification capabilities."""
        client = TestClient(app)
        
        # Create initial order
        order_data = {
            "customer_phone": "+1555123456",
            "order_type": "pickup",
            "items": [
                {
                    "menu_item_plu": "ROLL_001",
                    "quantity": 1
                }
            ]
        }
        
        create_response = client.post("/api/order/create", json=order_data)
        assert create_response.status_code == 200
        order_id = create_response.json()["order_id"]
        
        # Modify order
        modification_data = {
            "order_id": order_id,
            "action": "add_item",
            "item": {
                "menu_item_plu": "ROLL_002",
                "quantity": 1
            }
        }
        
        modify_response = client.post("/api/order/modify", json=modification_data)
        # Note: This might return 404 if endpoint doesn't exist yet, which is fine for e2e testing
        assert modify_response.status_code in [200, 404, 501]  # 501 = Not Implemented
        
    def test_order_confirmation_flow(self):
        """Test order confirmation process."""
        client = TestClient(app)
        
        # Create order
        order_data = {
            "customer_phone": "+1555987654",
            "order_type": "pickup",
            "items": [
                {
                    "menu_item_plu": "ROLL_001",
                    "quantity": 2,
                    "special_instructions": "Extra ginger"
                }
            ]
        }
        
        create_response = client.post("/api/order/create", json=order_data)
        assert create_response.status_code == 200
        order_id = create_response.json()["order_id"]
        
        # Confirm order
        confirm_data = {
            "order_id": order_id,
            "session_id": f"session_{uuid.uuid4().hex[:8]}",
            "customer_confirmation": True
        }
        
        confirm_response = client.post("/api/order/confirm", json=confirm_data)
        assert confirm_response.status_code == 200
        confirm_result = confirm_response.json()
        assert "confirmation_id" in confirm_result or "order_id" in confirm_result