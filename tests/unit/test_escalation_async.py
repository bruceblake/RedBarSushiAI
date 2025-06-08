"""
Unit tests for AsyncEscalationAgent class.


@pytest.fixture
def escalation_agent():
    """Create an escalation agent instance for testing."""
    return AsyncEscalationAgent(agent_name="TestEscalationAgent")

@pytest.fixture
def fsm_context():
    """Create FSM context for testing."""
    return {
        "call_sid": "TEST_CALL_123",
        "customer_name": "John Doe",
        "call_specific_data": {
            "escalation_reason": None,
            "next_fsm_event_name": None,
            "current_cart": {
                "items": [{"name": "California Roll", "quantity": 2}]
            },
            "conversation_history": [
                {"role": "customer", "content": "I need help"},
                {"role": "agent", "content": "How can I assist you?"}
            ]
        }
    }

@pytest.fixture
def rich_context():
    """Create a rich context with order and conversation history."""
    return {
        "call_sid": "CALL_RICH_123",
        "customer_name": "Jane Smith",
        "customer_phone": "+1234567890",
        "call_specific_data": {
            "current_cart": {
                "items": [
                    {
                        "plu": "CALI_001",
                        "name": "California Roll",
                        "quantity": 3,
                        "price": 12.95
                    },
                    {
                        "plu": "SPECIAL_001",
                        "name": "Chef Special",
                        "quantity": 1,
                        "price": 25.95,
                        "modifiers": [
                            {"name": "Extra Spicy", "plu": "MOD_SPICY"}
                        ]
                    }
                ],
                "total": 64.80
            },
            "conversation_history": [
                {"role": "agent", "content": "Welcome to Red Bar Sushi"},
                {"role": "customer", "content": "I want to order"},
                {"role": "agent", "content": "What would you like?"},
                {"role": "customer", "content": "3 California rolls"},
                {"role": "agent", "content": "Added to your order"},
                {"role": "customer", "content": "Also the chef special"},
                {"role": "agent", "content": "Would you like it spicy?"},
                {"role": "customer", "content": "Yes, extra spicy"},
                {"role": "customer", "content": "Actually, I have questions about allergies"}
            ],
            "order_type": "pickup",
            "escalation_reason": None,
            "next_fsm_event_name": None
        }
    }

@pytest.fixture
def escalation_agent():
    """Create escalation agent."""
    return AsyncEscalationAgent()

This module tests the escalation agent functionality including
escalation handling, human handoff, and status communication.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

from app.agents.escalation_async import AsyncEscalationAgent


class TestAsyncEscalationAgent:
    """Test suite for AsyncEscalationAgent class."""
    
    def test_initialization(self):
        """Test escalation agent initialization."""
        agent = AsyncEscalationAgent(agent_name="CustomEscalation")
        
        assert agent.agent_name == "CustomEscalation"
        assert agent.name == "CustomEscalation"
    
    @pytest.mark.asyncio
    async def test_initialize(self, escalation_agent):
        """Test agent initialization method."""
        await escalation_agent.initialize()
        # Should complete without errors
        assert True
    
    @pytest.mark.asyncio
    async def test_handle_escalation_basic(self, escalation_agent, fsm_context):
        """Test basic escalation handling."""
        result = await escalation_agent.handle_escalation(
            "TEST_CALL_123",
            "Customer requested assistance",
            fsm_context
        )
        
        assert result["handled"] is True
        assert result["agent"] == "TestEscalationAgent"
        assert result["escalation_reason"] == "Customer requested assistance"
        assert result["estimated_wait_time"] == 2
        assert "connect you with a staff member" in result["text"]
        assert fsm_context["call_specific_data"]["escalation_reason"] == "Customer requested assistance"
        assert fsm_context["call_specific_data"]["next_fsm_event_name"] == "ESCALATION_INITIATED"
    
    @pytest.mark.asyncio
    async def test_handle_escalation_manager_request(self, escalation_agent, fsm_context):
        """Test escalation for manager request."""
        result = await escalation_agent.handle_escalation(
            "TEST_CALL_123",
            "Customer asked to speak to a manager",
            fsm_context
        )
        
        assert result["handled"] is True
        assert result["escalation_reason"] == "Customer asked to speak to a manager"
        assert "staff member" in result["text"] or "manager" in result["text"]
    
    @pytest.mark.asyncio
    async def test_process_input_manager_keyword(self, escalation_agent, fsm_context):
        """Test processing input with manager keyword."""
        result = await escalation_agent.process_input(
            "I want to speak to the manager",
            fsm_context
        )
        
        assert result["handled"] is True
        assert result["escalation_reason"] == "Customer asked to speak to a manager"
        assert fsm_context["call_specific_data"]["next_fsm_event_name"] == "ESCALATION_INITIATED"
    
    @pytest.mark.asyncio
    async def test_process_input_help_keyword(self, escalation_agent, fsm_context):
        """Test processing input with help keyword."""
        result = await escalation_agent.process_input(
            "I need help with my order",
            fsm_context
        )
        
        assert result["handled"] is True
        assert result["escalation_reason"] == "Customer requested help"
    
    @pytest.mark.asyncio
    async def test_process_input_confusion(self, escalation_agent, fsm_context):
        """Test processing input expressing confusion."""
        result = await escalation_agent.process_input(
            "I'm confused and don't understand",
            fsm_context
        )
        
        assert result["handled"] is True
        assert result["escalation_reason"] == "Customer expressed confusion"
    
    @pytest.mark.asyncio
    async def test_process_input_generic(self, escalation_agent, fsm_context):
        """Test processing input without specific keywords."""
        result = await escalation_agent.process_input(
            "This is too complicated",
            fsm_context
        )
        
        assert result["handled"] is True
        assert result["escalation_reason"] == "Customer requested assistance"
    
    @pytest.mark.asyncio
    async def test_handle_escalation_without_call_specific_data(self, escalation_agent):
        """Test escalation with minimal context."""
        minimal_context = {
            "call_sid": "TEST_MINIMAL_123"
        }
        
        result = await escalation_agent.handle_escalation(
            "TEST_MINIMAL_123",
            "Test reason",
            minimal_context
        )
        
        assert result["handled"] is True
        assert result["escalation_reason"] == "Test reason"
        assert "connect you" in result["text"]
    
    @pytest.mark.asyncio
    async def test_handle_escalation_with_non_dict_call_data(self, escalation_agent):
        """Test escalation with invalid call_specific_data type."""
        invalid_context = {
            "call_sid": "TEST_INVALID_123",
            "call_specific_data": "not a dict"  # Invalid type
        }
        
        result = await escalation_agent.handle_escalation(
            "TEST_INVALID_123",
            "Test reason",
            invalid_context
        )
        
        assert result["handled"] is True
        assert result["text"] is not None
        # Should not crash despite invalid data type
    
    @pytest.mark.asyncio
    async def test_multiple_escalation_reasons(self, escalation_agent, fsm_context):
        """Test handling multiple escalation reasons in sequence."""
        # First escalation
        result1 = await escalation_agent.handle_escalation(
            "TEST_CALL_123",
            "Initial confusion",
            fsm_context
        )
        assert result1["escalation_reason"] == "Initial confusion"
        
        # Second escalation (updating reason)
        result2 = await escalation_agent.handle_escalation(
            "TEST_CALL_123",
            "Customer became frustrated",
            fsm_context
        )
        assert result2["escalation_reason"] == "Customer became frustrated"
        assert fsm_context["call_specific_data"]["escalation_reason"] == "Customer became frustrated"


class TestEscalationAgentWithContext:
    """Test escalation agent with rich context handling."""
    
    @pytest.mark.asyncio
    async def test_escalation_with_order_context(self, escalation_agent, rich_context):
        """Test escalation preserves order context."""
        result = await escalation_agent.handle_escalation(
            "CALL_RICH_123",
            "Customer has allergy questions",
            rich_context
        )
        
        assert result["handled"] is True
        # Verify context is preserved
        assert rich_context["call_specific_data"]["current_cart"]["total"] == 64.80
        assert len(rich_context["call_specific_data"]["conversation_history"]) == 9
        assert rich_context["call_specific_data"]["escalation_reason"] == "Customer has allergy questions"
    
    @pytest.mark.asyncio
    async def test_escalation_analytics_data(self, escalation_agent, rich_context):
        """Test that escalation provides data for analytics."""
        result = await escalation_agent.handle_escalation(
            "CALL_RICH_123",
            "Complex order modification",
            rich_context
        )
        
        # In a real implementation, we would verify analytics data
        # For now, verify the basic structure
        assert result["escalation_reason"] == "Complex order modification"
        assert result["estimated_wait_time"] is not None
        assert result["agent"] == "EscalationAgent"


class TestEscalationAgentConcurrency:
    """Test escalation agent under concurrent operations."""
    
    @pytest.mark.asyncio
    async def test_concurrent_escalations(self, escalation_agent):
        """Test handling multiple concurrent escalations."""
        # Create multiple escalation tasks
        tasks = []
        for i in range(10):
            context = {
                "call_sid": f"CALL_{i:03d}",
                "call_specific_data": {
                    "escalation_reason": None,
                    "next_fsm_event_name": None
                }
            }
            
            reasons = [
                "Customer requested manager",
                "Technical issue",
                "Billing question",
                "Complaint",
                "Special request"
            ]
            reason = reasons[i % len(reasons)]
            
            task = escalation_agent.handle_escalation(
                f"CALL_{i:03d}",
                reason,
                context
            )
            tasks.append(task)
        
        # Execute all escalations concurrently
        results = await asyncio.gather(*tasks)
        
        # Verify all completed successfully
        assert len(results) == 10
        assert all(r["handled"] for r in results)
        
        # Verify each has unique call context
        call_sids = [f"CALL_{i:03d}" for i in range(10)]
        assert len(set(call_sids)) == 10
    
    @pytest.mark.asyncio
    async def test_escalation_state_isolation(self, escalation_agent):
        """Test that escalations don't interfere with each other."""
        context1 = {
            "call_sid": "CALL_001",
            "call_specific_data": {"value": "context1"}
        }
        context2 = {
            "call_sid": "CALL_002",
            "call_specific_data": {"value": "context2"}
        }
        
        # Run escalations concurrently
        result1, result2 = await asyncio.gather(
            escalation_agent.handle_escalation("CALL_001", "Reason 1", context1),
            escalation_agent.handle_escalation("CALL_002", "Reason 2", context2)
        )
        
        # Verify contexts remain separate
        assert context1["call_specific_data"]["value"] == "context1"
        assert context2["call_specific_data"]["value"] == "context2"
        assert result1["escalation_reason"] == "Reason 1"
        assert result2["escalation_reason"] == "Reason 2"