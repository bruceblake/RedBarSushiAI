"""
End-to-end tests for complete voice ordering flow.
These tests run in staging environment with real services.
"""

import pytest
import os
import asyncio
from typing import Dict, Any
import httpx

from app.models.order_async import Order
from app.models.menu_async import MenuItem
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.e2e
@pytest.mark.requires_twilio
@pytest.mark.requires_openai
@pytest.mark.requires_deliverect
class TestCompleteVoiceOrderFlow:
    """Test complete voice order flow with real services in staging."""
    
    @pytest.fixture
    def staging_base_url(self):
        """Get staging environment base URL."""
        return os.getenv("STAGING_BASE_URL", "https://redbarsushi-staging.onrender.com")
    
    @pytest.fixture
    def twilio_test_number(self):
        """Get Twilio test phone number."""
        return os.getenv("TWILIO_TEST_PHONE_NUMBER", "+15005550006")
    
    @pytest.fixture
    async def staging_client(self, staging_base_url):
        """Create HTTP client for staging API."""
        async with httpx.AsyncClient(base_url=staging_base_url) as client:
            yield client
    
    async def simulate_conversation_relay_webhook(
        self, 
        client: httpx.AsyncClient,
        call_sid: str,
        sequence: int,
        prompt_text: str = None,
        is_final: bool = True
    ) -> Dict[str, Any]:
        """Simulate a ConversationRelay webhook from Twilio."""
        payload = {
            "sequenceNumber": str(sequence),
            "callSid": call_sid,
            "from": "+15551234567",
            "to": "+15559876543",
            "direction": "inbound",
            "callStatus": "in-progress"
        }
        
        if prompt_text:
            payload["prompt"] = {
                "text": prompt_text,
                "language": "en-US",
                "isFinal": is_final
            }
        
        response = await client.post("/api/conversation-relay", json=payload)
        return response.json()
    
    @pytest.mark.asyncio
    async def test_successful_order_placement_happy_path(
        self, 
        staging_client, 
        db_session: AsyncSession
    ):
        """Test complete happy path from greeting to order confirmation."""
        call_sid = f"TEST_E2E_HAPPY_{asyncio.get_event_loop().time()}"
        
        # Step 1: Initial connection (greeting)
        response = await self.simulate_conversation_relay_webhook(
            staging_client, call_sid, 0
        )
        assert "say" in response
        assert "welcome" in response["say"]["text"].lower()
        
        # Step 2: Provide name
        response = await self.simulate_conversation_relay_webhook(
            staging_client, call_sid, 1, "My name is John"
        )
        assert "John" in response["say"]["text"]
        assert response["listen"] is True
        
        # Step 3: Start order
        response = await self.simulate_conversation_relay_webhook(
            staging_client, call_sid, 2, "I'd like to order some sushi"
        )
        assert "order" in response["say"]["text"].lower()
        
        # Step 4: Order specific items
        response = await self.simulate_conversation_relay_webhook(
            staging_client, call_sid, 3, 
            "I'll have two California rolls and one spicy tuna roll"
        )
        assert "california" in response["say"]["text"].lower()
        assert response["listen"] is True
        
        # Step 5: Confirm cart
        response = await self.simulate_conversation_relay_webhook(
            staging_client, call_sid, 4, "That's all"
        )
        assert "total" in response["say"]["text"].lower() or "confirm" in response["say"]["text"].lower()
        
        # Step 6: Confirm order
        response = await self.simulate_conversation_relay_webhook(
            staging_client, call_sid, 5, "Yes, that's correct"
        )
        assert "pickup" in response["say"]["text"].lower() or "delivery" in response["say"]["text"].lower()
        
        # Step 7: Choose pickup
        response = await self.simulate_conversation_relay_webhook(
            staging_client, call_sid, 6, "Pickup please"
        )
        
        # Verify order was created in database
        await asyncio.sleep(2)  # Allow time for order processing
        
        order = await db_session.scalar(
            select(Order).where(Order.customer_phone == "+15551234567").order_by(Order.id.desc())
        )
        
        assert order is not None
        assert order.order_type == "pickup"
        assert len(order.items) >= 2  # At least 2 different items
        assert order.deliverect_channel_order_id is not None
    
    @pytest.mark.asyncio
    async def test_menu_inquiry_flow(self, staging_client):
        """Test customer asking about menu items."""
        call_sid = f"TEST_E2E_MENU_{asyncio.get_event_loop().time()}"
        
        # Initial greeting
        await self.simulate_conversation_relay_webhook(staging_client, call_sid, 0)
        
        # Skip name
        response = await self.simulate_conversation_relay_webhook(
            staging_client, call_sid, 1, "I don't want to give my name"
        )
        
        # Ask about menu
        response = await self.simulate_conversation_relay_webhook(
            staging_client, call_sid, 2, "What kind of sushi rolls do you have?"
        )
        
        # Response should contain menu items
        assert "roll" in response["say"]["text"].lower()
        assert response["listen"] is True
        
        # Ask about specific item
        response = await self.simulate_conversation_relay_webhook(
            staging_client, call_sid, 3, "Tell me more about the California roll"
        )
        
        assert "california" in response["say"]["text"].lower()
        # Should mention price or ingredients
        assert "$" in response["say"]["text"] or "crab" in response["say"]["text"].lower()
    
    @pytest.mark.asyncio
    async def test_unavailable_item_handling(self, staging_client, db_session):
        """Test ordering an unavailable item."""
        call_sid = f"TEST_E2E_UNAVAIL_{asyncio.get_event_loop().time()}"
        
        # Mark an item as unavailable
        dragon_roll = await db_session.scalar(
            select(MenuItem).where(MenuItem.name.like("%Dragon%"))
        )
        if dragon_roll:
            dragon_roll.is_available = False
            await db_session.commit()
        
        # Go through initial flow
        await self.simulate_conversation_relay_webhook(staging_client, call_sid, 0)
        await self.simulate_conversation_relay_webhook(
            staging_client, call_sid, 1, "John"
        )
        
        # Try to order unavailable item
        response = await self.simulate_conversation_relay_webhook(
            staging_client, call_sid, 2, "I want a dragon roll"
        )
        
        # Should inform about unavailability
        assert "unavailable" in response["say"]["text"].lower() or "don't have" in response["say"]["text"].lower()
        assert response["listen"] is True
    
    @pytest.mark.asyncio
    async def test_order_modification_flow(self, staging_client):
        """Test modifying an order before confirmation."""
        call_sid = f"TEST_E2E_MODIFY_{asyncio.get_event_loop().time()}"
        
        # Initial setup
        await self.simulate_conversation_relay_webhook(staging_client, call_sid, 0)
        await self.simulate_conversation_relay_webhook(staging_client, call_sid, 1, "Sarah")
        
        # Order items
        await self.simulate_conversation_relay_webhook(
            staging_client, call_sid, 2, "I want three California rolls"
        )
        
        # Change mind
        response = await self.simulate_conversation_relay_webhook(
            staging_client, call_sid, 3, "Actually, make that two California rolls"
        )
        
        assert "two" in response["say"]["text"].lower() or "2" in response["say"]["text"]
        
        # Add more items
        await self.simulate_conversation_relay_webhook(
            staging_client, call_sid, 4, "And add a spicy tuna roll"
        )
        
        # Confirm cart
        response = await self.simulate_conversation_relay_webhook(
            staging_client, call_sid, 5, "That's all"
        )
        
        # Should show correct quantities
        assert "two" in response["say"]["text"].lower() or "2" in response["say"]["text"]
        assert "spicy tuna" in response["say"]["text"].lower()
    
    @pytest.mark.asyncio
    async def test_escalation_to_human(self, staging_client):
        """Test escalation to human staff."""
        call_sid = f"TEST_E2E_ESCALATE_{asyncio.get_event_loop().time()}"
        
        # Initial greeting
        await self.simulate_conversation_relay_webhook(staging_client, call_sid, 0)
        
        # Request human immediately
        response = await self.simulate_conversation_relay_webhook(
            staging_client, call_sid, 1, "I need to speak to a person"
        )
        
        # Should acknowledge escalation
        assert any(word in response["say"]["text"].lower() for word in ["staff", "representative", "connect", "transfer"])
        
        # In real scenario, this would trigger Twilio transfer
        # For testing, we verify the escalation flag
        assert response.get("escalation_triggered") or "transfer" in response["say"]["text"].lower()
    
    @pytest.mark.asyncio
    async def test_delivery_order_with_address(self, staging_client):
        """Test delivery order with address collection."""
        call_sid = f"TEST_E2E_DELIVERY_{asyncio.get_event_loop().time()}"
        
        # Go through order flow
        await self.simulate_conversation_relay_webhook(staging_client, call_sid, 0)
        await self.simulate_conversation_relay_webhook(staging_client, call_sid, 1, "Mike")
        await self.simulate_conversation_relay_webhook(
            staging_client, call_sid, 2, "One salmon roll please"
        )
        await self.simulate_conversation_relay_webhook(staging_client, call_sid, 3, "That's it")
        await self.simulate_conversation_relay_webhook(staging_client, call_sid, 4, "Yes")
        
        # Choose delivery
        response = await self.simulate_conversation_relay_webhook(
            staging_client, call_sid, 5, "Delivery"
        )
        
        # Should ask for address
        assert "address" in response["say"]["text"].lower()
        
        # Provide address
        response = await self.simulate_conversation_relay_webhook(
            staging_client, call_sid, 6, "123 Main Street, apartment 4B"
        )
        
        # Should confirm order with address
        assert "123 main" in response["say"]["text"].lower()
    
    @pytest.mark.asyncio
    async def test_fsm_state_monitoring(self, staging_client):
        """Test FSM state monitoring endpoint."""
        call_sid = f"TEST_E2E_MONITOR_{asyncio.get_event_loop().time()}"
        
        # Start conversation
        await self.simulate_conversation_relay_webhook(staging_client, call_sid, 0)
        
        # Check FSM state
        response = await staging_client.get(f"/api/monitoring/fsm/{call_sid}")
        state_info = response.json()
        
        assert state_info["current_state"] == "GREETING"
        assert "context" in state_info
        
        # Progress conversation
        await self.simulate_conversation_relay_webhook(staging_client, call_sid, 1, "Lisa")
        
        # Check state again
        response = await staging_client.get(f"/api/monitoring/fsm/{call_sid}")
        state_info = response.json()
        
        assert state_info["current_state"] == "MAIN_MENU"
        assert state_info["context"].get("customer_name") == "Lisa"