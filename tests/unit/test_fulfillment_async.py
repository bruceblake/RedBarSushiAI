"""
Unit tests for AsyncFulfillmentAgent class.


@pytest.fixture
def fulfillment_agent():
    """Create a fulfillment agent instance for testing."""
    return AsyncFulfillmentAgent(agent_name="TestFulfillmentAgent")

@pytest.fixture
def valid_order():
    """Create a valid order for submission."""
    return {
        "items": [
            {
                "plu": "CALI_001",
                "name": "California Roll",
                "quantity": 2,
                "price": 12.95,
                "modifiers": []
            },
            {
                "plu": "TUNA_001",
                "name": "Spicy Tuna Roll",
                "quantity": 1,
                "price": 13.95,
                "modifiers": []
            }
        ],
        "customer_name": "John Doe",
        "customer_phone": "+1234567890",
        "order_type": "pickup",
        "total": 39.85,
        "tax": 3.19,
        "subtotal": 36.66
    }

@pytest.fixture
def fsm_context():
    """Create FSM context for testing."""
    return {
        "call_sid": "TEST_CALL_123",
        "call_specific_data": {
            "validated_cart": {},
            "next_fsm_event_name": None,
            "order_id": None,
            "estimated_time": None
        }
    }

@pytest.fixture
def mock_deliverect_client():
    """Mock Deliverect client."""
    with patch('app.agents.fulfillment_async.deliverect_client') as mock_client:
        mock_client.submit_order = AsyncMock(return_value={
            "success": True,
            "order_id": "DEL_12345",
            "estimated_time": 25
        })
        yield mock_client

@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = MagicMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session

@pytest.fixture
def fulfillment_with_integrations(mock_db_session, mock_deliverect_client):
    """Create fulfillment agent with mocked integrations."""
    agent = AsyncFulfillmentAgent()
    agent._db_session = mock_db_session
    return agent

This module tests the fulfillment agent functionality including
order submission, confirmation handling, and notification processing.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

from app.agents.fulfillment_async import AsyncFulfillmentAgent


class TestAsyncFulfillmentAgent:
    """Test suite for AsyncFulfillmentAgent class."""
    
    def test_initialization(self):
        """Test fulfillment agent initialization."""
        agent = AsyncFulfillmentAgent(agent_name="CustomFulfillment")
        
        assert agent.agent_name == "CustomFulfillment"
        assert agent.name == "CustomFulfillment"
        assert agent._db_session is None
    
    @pytest.mark.asyncio
    async def test_initialize(self, fulfillment_agent):
        """Test agent initialization method."""
        await fulfillment_agent.initialize()
        # Should complete without errors
        assert True
    
    @pytest.mark.asyncio
    async def test_submit_order_success(self, fulfillment_agent, valid_order, fsm_context):
        """Test successful order submission."""
        result = await fulfillment_agent.submit_order(
            "TEST_CALL_123",
            valid_order,
            fsm_context
        )
        
        assert result["success"] is True
        assert result["handled"] is True
        assert result["agent"] == "TestFulfillmentAgent"
        assert result["order_id"] is not None
        assert result["order_id"].startswith("ORD-")
        assert result["estimated_time"] == 20
        assert len(result["errors"]) == 0
        assert "successfully" in result["text"]
        assert fsm_context["call_specific_data"]["next_fsm_event_name"] == "ORDER_SUBMITTED"
        assert fsm_context["call_specific_data"]["order_id"] == result["order_id"]
        assert fsm_context["call_specific_data"]["estimated_time"] == 20
    
    @pytest.mark.asyncio
    async def test_submit_order_empty(self, fulfillment_agent, fsm_context):
        """Test submitting an empty order."""
        empty_order = {"items": []}
        
        result = await fulfillment_agent.submit_order(
            "TEST_CALL_123",
            empty_order,
            fsm_context
        )
        
        assert result["success"] is False
        assert result["handled"] is True
        assert result["order_id"] is None
        assert len(result["errors"]) > 0
        assert "empty order" in result["errors"][0].lower()
        assert "issue" in result["text"].lower()
        assert fsm_context["call_specific_data"]["next_fsm_event_name"] == "ORDER_SUBMISSION_FAILED"
    
    @pytest.mark.asyncio
    async def test_submit_order_no_items_key(self, fulfillment_agent, fsm_context):
        """Test submitting order without items key."""
        malformed_order = {"customer_name": "John", "total": 50.00}
        
        result = await fulfillment_agent.submit_order(
            "TEST_CALL_123",
            malformed_order,
            fsm_context
        )
        
        assert result["success"] is False
        assert "empty order" in result["text"].lower()
    
    @pytest.mark.asyncio
    async def test_process_input(self, fulfillment_agent, valid_order, fsm_context):
        """Test processing input in fulfillment state."""
        # Set up context with validated order
        fsm_context["call_specific_data"]["validated_cart"] = valid_order
        
        result = await fulfillment_agent.process_input(
            "Submit my order",
            fsm_context
        )
        
        assert result["success"] is True
        assert result["handled"] is True
        assert result["agent"] == "TestFulfillmentAgent"
        assert result["order_id"] is not None
    
    @pytest.mark.asyncio
    async def test_order_id_generation(self, fulfillment_agent, valid_order, fsm_context):
        """Test order ID generation based on call SID."""
        # Test with different call SIDs
        call_sids = ["CALL_ABC123", "CALL_XYZ789", "CALL_123456"]
        
        for call_sid in call_sids:
            result = await fulfillment_agent.submit_order(
                call_sid,
                valid_order,
                fsm_context
            )
            
            # Order ID should contain last 6 chars of call SID
            expected_suffix = call_sid[-6:]
            assert result["order_id"] == f"ORD-{expected_suffix}"
    
    @pytest.mark.asyncio
    async def test_delivery_order_submission(self, fulfillment_agent, fsm_context):
        """Test submitting a delivery order."""
        delivery_order = {
            "items": [
                {
                    "plu": "SUSHI_001",
                    "name": "Sushi Platter",
                    "quantity": 1,
                    "price": 45.95
                }
            ],
            "customer_name": "Jane Smith",
            "customer_phone": "+1987654321",
            "order_type": "delivery",
            "delivery_address": "123 Main St, City, State 12345",
            "delivery_instructions": "Ring doorbell twice",
            "total": 52.50,
            "delivery_fee": 5.00
        }
        
        result = await fulfillment_agent.submit_order(
            "TEST_DELIVERY_123",
            delivery_order,
            fsm_context
        )
        
        assert result["success"] is True
        assert result["order_id"] is not None
        assert "ready" in result["text"] or "delivered" in result["text"]


class TestFulfillmentAgentWithIntegrations:
    """Test fulfillment agent with external integrations."""
    
    @pytest.mark.asyncio
    async def test_future_deliverect_integration(self, fulfillment_with_integrations, valid_order, fsm_context):
        """Test placeholder for future Deliverect integration."""
        # This test demonstrates where Deliverect integration would be tested
        # Currently, the agent uses placeholder logic, but this shows
        # how we would test it when implemented
        
        result = await fulfillment_with_integrations.submit_order(
            "TEST_CALL_123",
            valid_order,
            fsm_context
        )
        
        # When Deliverect is integrated, we would verify:
        # mock_deliverect_client.submit_order.assert_called_once()
        # assert result["order_id"] == "DEL_12345"
        
        # For now, just verify current behavior
        assert result["success"] is True
        assert result["order_id"].startswith("ORD-")
    
    @pytest.mark.asyncio
    async def test_future_notification_handling(self, fulfillment_with_integrations):
        """Test placeholder for future notification features."""
        # This would test SMS/email notifications when implemented
        with patch('app.agents.fulfillment_async.send_sms_notification') as mock_sms:
            mock_sms.return_value = AsyncMock(return_value=True)
            
            # When implemented, notifications would be sent after successful submission
            # await fulfillment_with_integrations.send_order_confirmation("+1234567890", "ORD-123")
            # mock_sms.assert_called_once()
            
            # For now, just verify the mock is set up
            assert mock_sms is not None


class TestFulfillmentAgentErrorHandling:
    """Test error handling scenarios."""
    
    @pytest.mark.asyncio
    async def test_handle_missing_customer_info(self, fulfillment_agent, fsm_context):
        """Test handling orders with missing customer information."""
        incomplete_order = {
            "items": [{"plu": "TEST", "quantity": 1, "price": 10.00}],
            # Missing customer_name and customer_phone
            "order_type": "pickup"
        }
        
        result = await fulfillment_agent.submit_order(
            "TEST_CALL_123",
            incomplete_order,
            fsm_context
        )
        
        # Current implementation doesn't validate customer info,
        # but this test is ready for when it does
        assert "text" in result
        assert "handled" in result
    
    @pytest.mark.asyncio
    async def test_concurrent_order_submissions(self, fulfillment_agent, valid_order):
        """Test handling concurrent order submissions."""
        # Create multiple submission tasks
        tasks = []
        for i in range(5):
            context = {
                "call_sid": f"CALL_{i:06d}",
                "call_specific_data": {
                    "validated_cart": valid_order.copy(),
                    "next_fsm_event_name": None
                }
            }
            task = fulfillment_agent.submit_order(
                f"CALL_{i:06d}",
                valid_order,
                context
            )
            tasks.append(task)
        
        # Execute concurrently
        results = await asyncio.gather(*tasks)
        
        # All should submit successfully with unique order IDs
        assert all(r["success"] for r in results)
        order_ids = [r["order_id"] for r in results]
        assert len(set(order_ids)) == 5  # All unique
    
    @pytest.mark.asyncio
    async def test_order_with_special_instructions(self, fulfillment_agent, fsm_context):
        """Test order with special instructions and notes."""
        order_with_notes = {
            "items": [
                {
                    "plu": "BENTO_001",
                    "name": "Chicken Bento Box",
                    "quantity": 1,
                    "price": 15.95,
                    "special_instructions": "No pickles, extra teriyaki sauce"
                }
            ],
            "customer_name": "Bob Wilson",
            "order_type": "pickup",
            "order_notes": "Allergic to sesame seeds",
            "pickup_time": "12:30 PM"
        }
        
        result = await fulfillment_agent.submit_order(
            "TEST_SPECIAL_123",
            order_with_notes,
            fsm_context
        )
        
        assert result["success"] is True
        assert result["order_id"] is not None