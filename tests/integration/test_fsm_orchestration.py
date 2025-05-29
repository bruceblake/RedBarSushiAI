"""
Integration tests for FSM and agent orchestration.
These tests mock external services but test real component interactions.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from app.fsm.core import AsyncConversationFSM, ConversationState, ConversationEvent
from app.utils.agent_orchestration_async import AsyncAgentOrchestrator
from app.agents.factory_async import AsyncAgentFactory


@pytest.fixture
async def mock_openai_client():
    """Mock OpenAI client for integration tests."""
    client = AsyncMock()
    # Mock chat completions
    client.chat.completions.create = AsyncMock()
    return client


@pytest.fixture
async def mock_deliverect_client():
    """Mock Deliverect client for integration tests."""
    client = AsyncMock()
    # Mock menu operations
    client.get_menu = AsyncMock(return_value={
        "categories": [{"name": "Sushi Rolls", "id": "cat_001"}],
        "items": [
            {
                "name": "California Roll",
                "plu": "PLU_CALI",
                "price": 1200,
                "category_id": "cat_001"
            }
        ]
    })
    # Mock order operations
    client.create_order = AsyncMock(return_value={"order_id": "TEST_ORDER_001"})
    return client


@pytest.fixture
async def orchestrator(mock_openai_client, mock_deliverect_client):
    """Create orchestrator with mocked external services."""
    with patch('app.utils.agent_orchestration_async.AsyncOpenAI', return_value=mock_openai_client):
        with patch('app.utils.agent_orchestration_async.DeliverectClient', return_value=mock_deliverect_client):
            factory = AsyncAgentFactory()
            orchestrator = AsyncAgentOrchestrator(factory)
            await orchestrator.initialize()
            return orchestrator


@pytest.mark.asyncio
async def test_greeting_to_menu_transition(orchestrator):
    """Test FSM transitions from greeting to main menu."""
    call_sid = "TEST_CALL_001"
    
    # Initialize FSM
    fsm = await orchestrator.create_fsm(call_sid)
    assert fsm.current_state == ConversationState.GREETING
    
    # Simulate user providing name
    response = await orchestrator.process_voice_input(
        call_sid=call_sid,
        transcript="My name is John",
        is_final=True
    )
    
    # Verify transition
    assert fsm.current_state == ConversationState.MAIN_MENU
    assert "John" in fsm.context.get("customer_name", "")
    assert "How can I help you" in response["text"]


@pytest.mark.asyncio
async def test_menu_inquiry_flow(orchestrator, mock_deliverect_client):
    """Test menu inquiry through FSM and menu agent."""
    call_sid = "TEST_CALL_002"
    
    # Setup FSM in main menu state
    fsm = await orchestrator.create_fsm(call_sid)
    await fsm.transition_to(ConversationState.MAIN_MENU)
    
    # Ask about menu
    response = await orchestrator.process_voice_input(
        call_sid=call_sid,
        transcript="What sushi rolls do you have?",
        is_final=True
    )
    
    # Verify menu agent was engaged
    mock_deliverect_client.get_menu.assert_called()
    assert "California Roll" in response["text"]
    assert "$12.00" in response["text"]


@pytest.mark.asyncio
async def test_order_flow_with_validation(orchestrator):
    """Test complete order flow with cart and guardrail validation."""
    call_sid = "TEST_CALL_003"
    
    # Setup FSM
    fsm = await orchestrator.create_fsm(call_sid)
    await fsm.transition_to(ConversationState.MAIN_MENU)
    
    # Start ordering
    response = await orchestrator.process_voice_input(
        call_sid=call_sid,
        transcript="I want to order two California rolls",
        is_final=True
    )
    
    assert fsm.current_state == ConversationState.ORDERING
    assert "California Roll" in response["text"]
    assert "2" in response["text"] or "two" in response["text"]
    
    # Confirm order
    await orchestrator.process_voice_input(
        call_sid=call_sid,
        transcript="Yes, that's correct",
        is_final=True
    )
    
    assert fsm.current_state == ConversationState.CONFIRMATION


@pytest.mark.asyncio
async def test_error_handling_with_fallback(orchestrator, mock_openai_client):
    """Test orchestrator handles errors gracefully."""
    call_sid = "TEST_CALL_004"
    
    # Make OpenAI fail
    mock_openai_client.chat.completions.create.side_effect = Exception("API Error")
    
    # Process input
    response = await orchestrator.process_voice_input(
        call_sid=call_sid,
        transcript="Hello",
        is_final=True
    )
    
    # Should get fallback response
    assert "having trouble" in response["text"].lower()
    assert response["requires_response"] == True


@pytest.mark.asyncio
async def test_agent_handoff(orchestrator):
    """Test handoff between agents during conversation."""
    call_sid = "TEST_CALL_005"
    
    # Setup in ordering state
    fsm = await orchestrator.create_fsm(call_sid)
    await fsm.transition_to(ConversationState.ORDERING)
    fsm.context["cart_items"] = [
        {"name": "California Roll", "quantity": 2, "plu": "PLU_CALI"}
    ]
    
    # Request human assistance
    response = await orchestrator.process_voice_input(
        call_sid=call_sid,
        transcript="I need to speak to a person",
        is_final=True
    )
    
    # Should transition to escalation
    assert fsm.current_state == ConversationState.ESCALATION
    assert "connect you" in response["text"].lower()


@pytest.mark.asyncio
async def test_fsm_persistence(orchestrator):
    """Test FSM state persistence across requests."""
    call_sid = "TEST_CALL_006"
    
    # Create and modify FSM
    fsm1 = await orchestrator.create_fsm(call_sid)
    fsm1.context["test_value"] = "preserved"
    await fsm1.transition_to(ConversationState.ORDERING)
    
    # Retrieve FSM
    fsm2 = await orchestrator.get_fsm(call_sid)
    
    assert fsm2.current_state == ConversationState.ORDERING
    assert fsm2.context["test_value"] == "preserved"
    
    # Cleanup
    await orchestrator.remove_fsm(call_sid)
    
    # Verify cleanup
    fsm3 = await orchestrator.get_fsm(call_sid)
    assert fsm3.current_state == ConversationState.GREETING  # New FSM