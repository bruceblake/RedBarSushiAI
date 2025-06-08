"""
Unit tests for AsyncGuardrailAgent class.


@pytest.fixture
def guardrail_agent():
    """Create a guardrail agent instance for testing."""
    return AsyncGuardrailAgent(agent_name="TestGuardrailAgent")

@pytest.fixture
def valid_order():
    """Create a valid order for testing."""
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
                "modifiers": [
                    {
                        "group_name": "Spice Level",
                        "selections": [{"plu": "MILD", "name": "Mild"}]
                    }
                ]
            }
        ],
        "customer_name": "John Doe",
        "order_type": "pickup"
    }

@pytest.fixture
def invalid_order():
    """Create an invalid order for testing."""
    return {
        "items": [
            {
                "plu": "CALI_001",
                "name": "California Roll",
                "quantity": 0,  # Invalid quantity
                "price": 12.95
            },
            {
                "plu": "UNKNOWN",
                "name": "Unknown Item",
                "quantity": -1,  # Negative quantity
                "price": 0
            }
        ]
    }

@pytest.fixture
def fsm_context():
    """Create FSM context for testing."""
    return {
        "call_sid": "TEST_CALL_123",
        "call_specific_data": {
            "current_cart": {},
            "next_fsm_event_name": None
        }
    }

@pytest.fixture
def mock_db_session():
    """Create mock database session."""
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session

@pytest.fixture
def guardrail_with_db(mock_db_session):
    """Create guardrail agent with database."""
    agent = AsyncGuardrailAgent()
    agent._db_session = mock_db_session
    return agent

This module tests the guardrail agent functionality including
order validation, modifier checking, and business rule enforcement.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List

from app.agents.guardrail_async import AsyncGuardrailAgent


class TestAsyncGuardrailAgent:
    """Test suite for AsyncGuardrailAgent class."""
    
    def test_initialization(self):
        """Test guardrail agent initialization."""
        agent = AsyncGuardrailAgent(agent_name="CustomGuardrail")
        
        assert agent.agent_name == "CustomGuardrail"
        assert agent.name == "CustomGuardrail"
        assert agent._db_session is None
    
    @pytest.mark.asyncio
    async def test_initialize(self, guardrail_agent):
        """Test agent initialization method."""
        await guardrail_agent.initialize()
        # Should complete without errors
        assert True
    
    @pytest.mark.asyncio
    async def test_validate_order_valid(self, guardrail_agent, valid_order, fsm_context):
        """Test validating a valid order."""
        result = await guardrail_agent.validate_order(
            "TEST_CALL_123",
            valid_order,
            fsm_context
        )
        
        assert result["is_valid"] is True
        assert result["handled"] is True
        assert result["agent"] == "TestGuardrailAgent"
        assert len(result["issues"]) == 0
        assert "validated" in result["text"].lower()
        assert fsm_context["call_specific_data"]["next_fsm_event_name"] == "ORDER_VALID"
    
    @pytest.mark.asyncio
    async def test_validate_order_empty(self, guardrail_agent, fsm_context):
        """Test validating an empty order."""
        empty_order = {"items": []}
        
        result = await guardrail_agent.validate_order(
            "TEST_CALL_123",
            empty_order,
            fsm_context
        )
        
        assert result["is_valid"] is False
        assert result["handled"] is True
        assert len(result["issues"]) > 0
        assert "empty" in result["issues"][0].lower()
        assert fsm_context["call_specific_data"]["next_fsm_event_name"] == "ORDER_INVALID"
    
    @pytest.mark.asyncio
    async def test_validate_order_invalid_quantities(self, guardrail_agent, invalid_order, fsm_context):
        """Test validating order with invalid quantities."""
        result = await guardrail_agent.validate_order(
            "TEST_CALL_123",
            invalid_order,
            fsm_context
        )
        
        assert result["is_valid"] is False
        assert len(result["issues"]) >= 2  # At least 2 quantity issues
        assert any("invalid quantity" in issue.lower() for issue in result["issues"])
        assert fsm_context["call_specific_data"]["next_fsm_event_name"] == "ORDER_INVALID"
    
    @pytest.mark.asyncio
    async def test_validate_order_no_items_key(self, guardrail_agent, fsm_context):
        """Test validating order without items key."""
        malformed_order = {"customer_name": "John"}
        
        result = await guardrail_agent.validate_order(
            "TEST_CALL_123",
            malformed_order,
            fsm_context
        )
        
        assert result["is_valid"] is False
        assert "empty" in result["text"].lower()
    
    @pytest.mark.asyncio
    async def test_validate_modifiers(self, guardrail_agent):
        """Test modifier validation."""
        item = {
            "plu": "CALI_001",
            "name": "California Roll",
            "modifiers": [
                {
                    "group_name": "Add-ons",
                    "selections": [
                        {"plu": "EXTRA_AVO", "name": "Extra Avocado"}
                    ]
                }
            ]
        }
        
        errors = await guardrail_agent.validate_modifiers(item)
        
        # Current implementation returns empty list (all valid)
        assert errors == []
    
    @pytest.mark.asyncio
    async def test_process_input(self, guardrail_agent, valid_order, fsm_context):
        """Test processing input in validation state."""
        # Set up context with order
        fsm_context["call_specific_data"]["current_cart"] = valid_order
        
        result = await guardrail_agent.process_input(
            "Check my order",
            fsm_context
        )
        
        assert result["is_valid"] is True
        assert result["handled"] is True
        assert result["agent"] == "TestGuardrailAgent"
    
    @pytest.mark.asyncio
    async def test_complex_order_validation(self, guardrail_agent, fsm_context):
        """Test validating a complex order with multiple items and modifiers."""
        complex_order = {
            "items": [
                {
                    "plu": "COMBO_001",
                    "name": "Sushi Combo A",
                    "quantity": 1,
                    "price": 24.95,
                    "modifiers": [
                        {
                            "group_name": "Soup Choice",
                            "selections": [{"plu": "MISO", "name": "Miso Soup"}]
                        },
                        {
                            "group_name": "Rice",
                            "selections": [{"plu": "BROWN", "name": "Brown Rice"}]
                        }
                    ]
                },
                {
                    "plu": "SASHIMI_001",
                    "name": "Salmon Sashimi",
                    "quantity": 2,
                    "price": 15.95,
                    "modifiers": []
                },
                {
                    "plu": "APP_001",
                    "name": "Edamame",
                    "quantity": 1,
                    "price": 5.95,
                    "modifiers": [
                        {
                            "group_name": "Preparation",
                            "selections": [{"plu": "SPICY", "name": "Spicy"}]
                        }
                    ]
                }
            ],
            "customer_name": "Jane Smith",
            "order_type": "delivery",
            "delivery_address": "123 Main St"
        }
        
        result = await guardrail_agent.validate_order(
            "TEST_CALL_123",
            complex_order,
            fsm_context
        )
        
        assert result["is_valid"] is True
        assert len(result["issues"]) == 0
        assert fsm_context["call_specific_data"]["next_fsm_event_name"] == "ORDER_VALID"


class TestGuardrailAgentWithDatabase:
    """Test guardrail agent with database integration."""
    
    @pytest.mark.asyncio
    async def test_future_database_validation(self, guardrail_with_db):
        """Test placeholder for future database validation."""
        # This test demonstrates where database validation would be added
        # Currently, the agent doesn't implement DB checks, but this shows
        # how we would test it when implemented
        
        # Mock database query for item availability
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = {
            "available": True,
            "snoozed": False
        }
        guardrail_with_db._db_session.execute.return_value = mock_result
        
        # When DB validation is implemented, we would test like this:
        # result = await guardrail_with_db.check_item_availability("CALI_001")
        # assert result["available"] is True
        
        # For now, just verify the mock is set up correctly
        assert guardrail_with_db._db_session is not None


class TestGuardrailAgentEdgeCases:
    """Test edge cases and error scenarios."""
    
    @pytest.mark.asyncio
    async def test_validate_order_with_special_characters(self, guardrail_agent, fsm_context):
        """Test validating order with special characters in item names."""
        order = {
            "items": [
                {
                    "plu": "SPECIAL_001",
                    "name": "Chef's Special Roll (Spicy!)",
                    "quantity": 1,
                    "price": 18.95
                }
            ]
        }
        
        result = await guardrail_agent.validate_order(
            "TEST_CALL_123",
            order,
            fsm_context
        )
        
        assert result["is_valid"] is True
    
    @pytest.mark.asyncio
    async def test_validate_order_missing_fsm_context_data(self, guardrail_agent):
        """Test handling missing FSM context data."""
        order = {"items": [{"plu": "TEST", "quantity": 1}]}
        minimal_context = {"call_sid": "TEST"}
        
        # Should handle gracefully without raising exception
        result = await guardrail_agent.validate_order(
            "TEST_CALL_123",
            order,
            minimal_context
        )
        
        assert "text" in result
        assert "is_valid" in result
    
    @pytest.mark.asyncio
    async def test_concurrent_validations(self, guardrail_agent, valid_order, fsm_context):
        """Test handling concurrent order validations."""
        # Create multiple validation tasks
        tasks = []
        for i in range(5):
            context = {
                "call_sid": f"CALL_{i}",
                "call_specific_data": {
                    "current_cart": valid_order.copy(),
                    "next_fsm_event_name": None
                }
            }
            task = guardrail_agent.validate_order(
                f"CALL_{i}",
                valid_order,
                context
            )
            tasks.append(task)
        
        # Execute concurrently
        results = await asyncio.gather(*tasks)
        
        # All should validate successfully
        assert all(r["is_valid"] for r in results)
        assert len(results) == 5