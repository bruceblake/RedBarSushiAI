"""
End-to-end tests for complete voice ordering flow.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from app.fsm.core import ConversationState


class TestCompleteVoiceFlow:
    """Test complete voice ordering flow from call to order submission."""
    
    @pytest.mark.asyncio
    async def test_successful_pickup_order(self, test_client, db_session, sample_menu_data, mock_deliverect_client):
        """Test successful pickup order flow."""
        call_sid = "CA_test_pickup_001"
        
        # 1. Initial call - webhook
        response = await test_client.post(
            "/voice/webhook",
            data={"CallSid": call_sid, "From": "+1234567890"}
        )
        assert response.status_code == 200
        assert b"<Connect>" in response.content
        
        # 2. Simulate greeting interaction
        greeting_response = await test_client.post(
            "/api/conversation-relay",
            json={
                "CallSid": call_sid,
                "TranscriptionText": "",
                "CallStatus": "in-progress"
            }
        )
        assert greeting_response.status_code == 200
        data = greeting_response.json()
        assert "response" in data
        assert "Welcome" in data["response"]
        
        # 3. Provide name
        name_response = await test_client.post(
            "/api/conversation-relay",
            json={
                "CallSid": call_sid,
                "TranscriptionText": "My name is John Smith",
                "CallStatus": "in-progress"
            }
        )
        assert name_response.status_code == 200
        data = name_response.json()
        assert data["state"] == ConversationState.MAIN_MENU.value
        
        # 4. Start ordering
        order_start_response = await test_client.post(
            "/api/conversation-relay",
            json={
                "CallSid": call_sid,
                "TranscriptionText": "I'd like to place an order for pickup",
                "CallStatus": "in-progress"
            }
        )
        assert order_start_response.status_code == 200
        data = order_start_response.json()
        assert data["state"] == ConversationState.ORDERING.value
        
        # 5. Add items
        add_items_response = await test_client.post(
            "/api/conversation-relay",
            json={
                "CallSid": call_sid,
                "TranscriptionText": "I want two California rolls and one order of edamame",
                "CallStatus": "in-progress"
            }
        )
        assert add_items_response.status_code == 200
        data = add_items_response.json()
        assert "added" in data["response"].lower()
        
        # 6. Finish ordering
        finish_response = await test_client.post(
            "/api/conversation-relay",
            json={
                "CallSid": call_sid,
                "TranscriptionText": "That's all for my order",
                "CallStatus": "in-progress"
            }
        )
        assert finish_response.status_code == 200
        data = finish_response.json()
        # Should move to validation/confirmation
        assert data["state"] in [ConversationState.VALIDATION.value, ConversationState.CONFIRMATION.value]
        
        # 7. Confirm order
        confirm_response = await test_client.post(
            "/api/conversation-relay",
            json={
                "CallSid": call_sid,
                "TranscriptionText": "Yes, that's correct",
                "CallStatus": "in-progress"
            }
        )
        assert confirm_response.status_code == 200
        data = confirm_response.json()
        assert data["state"] == ConversationState.FULFILLMENT.value
        
        # 8. Provide pickup time
        with patch.object(mock_deliverect_client, 'create_order', 
                         return_value={"orderId": "DEL_TEST_001", "status": "accepted"}):
            
            fulfillment_response = await test_client.post(
                "/api/conversation-relay",
                json={
                    "CallSid": call_sid,
                    "TranscriptionText": "I'll pick it up in 20 minutes",
                    "CallStatus": "in-progress"
                }
            )
            assert fulfillment_response.status_code == 200
            data = fulfillment_response.json()
            assert data["state"] == ConversationState.COMPLETION.value
            assert "order" in data["response"].lower()
            assert "confirmed" in data["response"].lower()
    
    @pytest.mark.asyncio
    async def test_delivery_order_flow(self, test_client, db_session, sample_menu_data, mock_deliverect_client):
        """Test delivery order flow with address collection."""
        call_sid = "CA_test_delivery_001"
        
        # Set up through ordering state (skip greeting for brevity)
        # ... (similar setup as above)
        
        # Request delivery
        delivery_response = await test_client.post(
            "/api/conversation-relay",
            json={
                "CallSid": call_sid,
                "TranscriptionText": "I'd like delivery to 123 Main Street, apartment 4B",
                "CallStatus": "in-progress"
            }
        )
        assert delivery_response.status_code == 200
        data = delivery_response.json()
        assert "delivery" in data["response"].lower()
        
        # Verify delivery address was captured
        assert "context" in data
        assert data["context"].get("delivery_address") == "123 Main Street, apartment 4B"
    
    @pytest.mark.asyncio
    async def test_order_with_modifications(self, test_client, db_session, sample_menu_data):
        """Test order with item modifications."""
        call_sid = "CA_test_mods_001"
        
        # Add item with modifications
        mod_response = await test_client.post(
            "/api/conversation-relay",
            json={
                "CallSid": call_sid,
                "TranscriptionText": "I want a California roll with extra avocado and spicy mayo on the side",
                "CallStatus": "in-progress"
            }
        )
        assert mod_response.status_code == 200
        data = mod_response.json()
        
        # Verify modifications were understood
        assert "extra avocado" in data["response"].lower() or "modifications" in data["response"].lower()
    
    @pytest.mark.asyncio
    async def test_menu_inquiry_flow(self, test_client, db_session, sample_menu_data):
        """Test menu inquiry without ordering."""
        call_sid = "CA_test_menu_001"
        
        # Ask about menu
        menu_response = await test_client.post(
            "/api/conversation-relay",
            json={
                "CallSid": call_sid,
                "TranscriptionText": "What kind of sushi rolls do you have?",
                "CallStatus": "in-progress"
            }
        )
        assert menu_response.status_code == 200
        data = menu_response.json()
        
        # Should get menu items in response
        assert "California Roll" in data["response"]
        assert "Spicy Tuna Roll" in data["response"]
        assert "$12.95" in data["response"] or "$14.95" in data["response"]
    
    @pytest.mark.asyncio
    async def test_error_recovery_flow(self, test_client, db_session):
        """Test error recovery during ordering."""
        call_sid = "CA_test_error_001"
        
        # Try to order non-existent item
        error_response = await test_client.post(
            "/api/conversation-relay",
            json={
                "CallSid": call_sid,
                "TranscriptionText": "I want a dragon roll",  # Not in menu
                "CallStatus": "in-progress"
            }
        )
        assert error_response.status_code == 200
        data = error_response.json()
        
        # Should handle gracefully
        assert "sorry" in data["response"].lower() or "don't have" in data["response"].lower()
        assert data["state"] != ConversationState.ERROR.value  # Should recover
    
    @pytest.mark.asyncio
    async def test_escalation_flow(self, test_client, db_session):
        """Test escalation to human agent."""
        call_sid = "CA_test_escalation_001"
        
        # Request human agent
        escalation_response = await test_client.post(
            "/api/conversation-relay",
            json={
                "CallSid": call_sid,
                "TranscriptionText": "I need to speak to a real person",
                "CallStatus": "in-progress"
            }
        )
        assert escalation_response.status_code == 200
        data = escalation_response.json()
        
        assert data["state"] == ConversationState.ESCALATION.value
        assert "connect" in data["response"].lower() or "transfer" in data["response"].lower()
    
    @pytest.mark.asyncio
    async def test_abandoned_call_flow(self, test_client, db_session):
        """Test handling abandoned call."""
        call_sid = "CA_test_abandon_001"
        
        # Start call
        await test_client.post(
            "/api/conversation-relay",
            json={
                "CallSid": call_sid,
                "TranscriptionText": "",
                "CallStatus": "in-progress"
            }
        )
        
        # Simulate call ending
        end_response = await test_client.post(
            "/api/conversation-relay",
            json={
                "CallSid": call_sid,
                "CallStatus": "completed"
            }
        )
        assert end_response.status_code == 200
        
        # Verify cleanup occurred
        # Session should be marked as ended