"""
End-to-end tests for complete ordering flow from greeting to order submission.
Tests the entire customer journey through ConversationRelay and FSM.
"""

import pytest
import asyncio
import json
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.menu_async import MenuItem, MenuModifier, MenuModifierGroup
from app.models.order_async import Order, OrderItem
from app.agents.cart_async import AsyncCartAgent
from app.agents.guardrail_async import AsyncGuardrailAgent
from app.agents.fulfillment_async import AsyncFulfillmentAgent
from app.utils.agent_orchestration_async import AsyncAgentOrchestrator
from app.fsm.core import ConversationState, ConversationEvent


@pytest.fixture
async def setup_test_menu(db_session):
    """Set up test menu items."""
    # Create items
    items = [
        MenuItem(
            name="California Roll",
            plu="PLU_CALI",
            price=1200,
            description="Crab, avocado, cucumber",
            is_available=True
        ),
        MenuItem(
            name="Spicy Tuna Roll",
            plu="PLU_SPICY_TUNA",
            price=1400,
            description="Spicy tuna, cucumber",
            is_available=True
        ),
        MenuItem(
            name="Edamame",
            plu="PLU_EDAMAME",
            price=500,
            description="Steamed soybeans",
            is_available=True
        )
    ]
    
    # Create modifier group
    spice_group = MenuModifierGroup(
        name="Spice Level",
        plu="PLU_SPICE_GROUP",
        min_selection=0,
        max_selection=1
    )
    
    # Create modifiers
    modifiers = [
        MenuModifier(
            name="Extra Spicy",
            plu="PLU_EXTRA_SPICY",
            price_change=0,
            modifier_group_id=spice_group.id
        ),
        MenuModifier(
            name="No Spice",
            plu="PLU_NO_SPICE",
            price_change=0,
            modifier_group_id=spice_group.id
        )
    ]
    
    db_session.add_all(items + [spice_group] + modifiers)
    await db_session.commit()
    
    return {
        "items": {item.plu: item for item in items},
        "modifier_groups": {"spice": spice_group},
        "modifiers": {mod.plu: mod for mod in modifiers}
    }


@pytest.fixture
async def orchestrator():
    """Create agent orchestrator with mocked agents."""
    from app.utils.agent_orchestration_async import async_agent_orchestrator
    await async_agent_orchestrator.initialize()
    return async_agent_orchestrator


@pytest.mark.asyncio
async def test_complete_ordering_journey(orchestrator, setup_test_menu, db_session):
    """Test complete customer journey from greeting to order completion."""
    call_sid = "TEST_ORDER_FLOW_123"
    
    # Start conversation
    # Initialize FSM for new conversation
    fsm = await orchestrator.create_fsm(call_sid)
    
    # 1. GREETING - Customer provides name
    response = await orchestrator.process_voice_input(
        call_sid,
        "My name is John",
        {}
    )
    assert "John" in response["text"]
    assert response["state"] == "MAIN_MENU"
    
    # 2. MAIN_MENU - Customer wants to order
    response = await orchestrator.process_voice_input(
        call_sid,
        "I'd like to place an order",
        {}
    )
    assert response["state"] == "ORDERING"
    assert "order" in response["text"].lower()
    
    # 3. ORDERING - Add items
    response = await orchestrator.process_voice_input(
        call_sid,
        "I'll have two California rolls and one edamame",
        {}
    )
    assert "California" in response["text"]
    assert "edamame" in response["text"]
    
    # 4. ORDERING - Complete order
    response = await orchestrator.process_voice_input(
        call_sid,
        "That's all for now",
        {}
    )
    assert response["state"] in ["VALIDATION", "CONFIRMATION"]
    assert "total" in response["text"].lower() or "confirm" in response["text"].lower()
    
    # 5. CONFIRMATION - Confirm order
    response = await orchestrator.process_voice_input(
        call_sid,
        "Yes, that's correct",
        {}
    )
    assert response["state"] == "FULFILLMENT"
    assert "pickup" in response["text"].lower() or "delivery" in response["text"].lower()
    
    # 6. FULFILLMENT - Choose pickup
    with patch('app.agents.fulfillment_async.submit_order_to_deliverect') as mock_submit:
        mock_submit.return_value = {
            "status": 1,
            "_id": "ORDER123",
            "deliverect_order_id": "DLVR123"
        }
        
        response = await orchestrator.process_voice_input(
            call_sid,
            "I'll pick it up",
            {}
        )
        
        assert "order" in response["text"].lower()
        assert "ready" in response["text"].lower() or "minutes" in response["text"].lower()


@pytest.mark.asyncio
async def test_order_with_modifications(setup_test_menu, db_session):
    """Test ordering with item modifications."""
    cart_agent = AsyncCartAgent(db=db_session)
    
    # Process order with modifications
    result = await cart_agent.process_input(
        "I want a spicy tuna roll with extra spicy",
        {"call_sid": "TEST_MOD_123"}
    )
    
    assert result["handled"] is True
    assert "spicy tuna" in result["text"].lower()
    
    # Check cart contents
    cart = await cart_agent._get_cart("TEST_MOD_123")
    assert len(cart["items"]) == 1
    assert cart["items"][0]["name"] == "Spicy Tuna Roll"


@pytest.mark.asyncio
async def test_order_validation(setup_test_menu, db_session):
    """Test order validation with guardrail agent."""
    # Create cart with items
    cart_data = {
        "items": [
            {
                "name": "California Roll",
                "plu": "PLU_CALI",
                "quantity": 2,
                "price": 1200,
                "modifiers": []
            },
            {
                "name": "Edamame",
                "plu": "PLU_EDAMAME",
                "quantity": 1,
                "price": 500,
                "modifiers": []
            }
        ]
    }
    
    guardrail = AsyncGuardrailAgent(db=db_session)
    
    # Mock cart retrieval
    with patch.object(guardrail, '_get_cart', return_value=cart_data):
        result = await guardrail.validate_order("TEST_VALIDATION_123")
        
        assert result["valid"] is True
        assert result["total_price"] == 2900  # (2 * 1200) + 500
        assert len(result["order_summary"]) == 2


@pytest.mark.asyncio
async def test_order_submission(setup_test_menu, db_session):
    """Test order submission to Deliverect."""
    fulfillment = AsyncFulfillmentAgent(db=db_session)
    
    # Mock cart and customer data
    cart_data = {
        "items": [{
            "name": "California Roll",
            "plu": "PLU_CALI",
            "quantity": 1,
            "price": 1200,
            "modifiers": []
        }]
    }
    
    customer_data = {
        "name": "John Doe",
        "phone": "+1234567890",
        "order_type": "pickup"
    }
    
    with patch.object(fulfillment, '_get_cart', return_value=cart_data):
        with patch.object(fulfillment, '_get_customer_info', return_value=customer_data):
            with patch('app.agents.fulfillment_async.submit_order_to_deliverect') as mock_submit:
                mock_submit.return_value = {
                    "status": 1,
                    "_id": "ORDER123",
                    "deliverect_order_id": "DLVR123"
                }
                
                result = await fulfillment.process_order("TEST_SUBMIT_123")
                
                assert result["success"] is True
                assert result["order_id"] == "ORDER123"
                assert "ready" in result["message"]


@pytest.mark.asyncio
async def test_unavailable_item_handling(setup_test_menu, db_session):
    """Test handling of unavailable items."""
    # Make item unavailable
    item = await db_session.get(MenuItem, setup_test_menu["items"]["PLU_CALI"].id)
    item.is_available = False
    await db_session.commit()
    
    cart_agent = AsyncCartAgent(db=db_session)
    result = await cart_agent.process_input(
        "I want a California roll",
        {"call_sid": "TEST_UNAVAIL_123"}
    )
    
    assert "unavailable" in result["text"].lower() or "don't have" in result["text"].lower()


@pytest.mark.asyncio
async def test_price_calculation_with_modifiers(setup_test_menu, db_session):
    """Test accurate price calculation including modifiers."""
    # Create item with price modifier
    modifier = MenuModifier(
        name="Extra Avocado",
        plu="PLU_EXTRA_AVO",
        price_change=200  # $2.00 extra
    )
    db_session.add(modifier)
    await db_session.commit()
    
    guardrail = AsyncGuardrailAgent(db=db_session)
    
    cart_data = {
        "items": [{
            "name": "California Roll",
            "plu": "PLU_CALI",
            "quantity": 1,
            "price": 1200,
            "modifiers": [{
                "name": "Extra Avocado",
                "plu": "PLU_EXTRA_AVO",
                "price_change": 200
            }]
        }]
    }
    
    with patch.object(guardrail, '_get_cart', return_value=cart_data):
        result = await guardrail.validate_order("TEST_PRICE_123")
        
        assert result["total_price"] == 1400  # 1200 + 200


@pytest.mark.asyncio
async def test_empty_cart_handling(db_session):
    """Test handling of empty cart scenarios."""
    guardrail = AsyncGuardrailAgent(db=db_session)
    
    with patch.object(guardrail, '_get_cart', return_value={"items": []}):
        result = await guardrail.validate_order("TEST_EMPTY_123")
        
        assert result["valid"] is False
        assert "empty" in result["message"].lower()


@pytest.mark.asyncio
async def test_delivery_address_collection(db_session):
    """Test collecting delivery information."""
    fulfillment = AsyncFulfillmentAgent(db=db_session)
    
    # Process delivery address
    result = await fulfillment.process_input(
        "123 Main Street, apartment 4B",
        {
            "call_sid": "TEST_DELIVERY_123",
            "order_type": "delivery",
            "awaiting_address": True
        }
    )
    
    assert result["handled"] is True
    assert "123 Main Street" in result["text"]
    assert result.get("delivery_address") is not None


@pytest.mark.asyncio
async def test_order_cancellation_flow(orchestrator):
    """Test order cancellation at various stages."""
    call_sid = "TEST_CANCEL_123"
    
    # Start order
    fsm = await orchestrator.create_fsm(call_sid)
    
    # Move to ordering state
    fsm = await orchestrator.get_fsm(call_sid)
    await fsm.trigger(ConversationEvent.START_ORDER)
    
    # Cancel order
    response = await orchestrator.process_voice_input(
        call_sid,
        "Actually, cancel everything",
        {}
    )
    
    assert "cancel" in response["text"].lower()
    assert response["state"] in ["MAIN_MENU", "COMPLETION"]


@pytest.mark.asyncio
async def test_order_modification_flow(orchestrator, setup_test_menu):
    """Test modifying order after initial confirmation."""
    call_sid = "TEST_MODIFY_123"
    
    # Setup order in confirmation state
    fsm = await orchestrator.create_fsm(call_sid)
    fsm = await orchestrator.get_fsm(call_sid)
    fsm.current_state = ConversationState.CONFIRMATION
    
    # Request modification
    response = await orchestrator.process_voice_input(
        call_sid,
        "Actually, can I add one more item?",
        {}
    )
    
    assert response["state"] == "ORDERING"
    assert "add" in response["text"].lower() or "what" in response["text"].lower()


@pytest.mark.asyncio
async def test_multiple_quantity_parsing(setup_test_menu, db_session):
    """Test parsing orders with multiple quantities."""
    cart_agent = AsyncCartAgent(db=db_session)
    
    test_orders = [
        "Three California rolls",
        "I want 2 spicy tuna and 1 edamame",
        "Give me a couple of California rolls"
    ]
    
    for order_text in test_orders:
        # Process order text
        result = await cart_agent.process_input(
            order_text,
            {"call_sid": "TEST_QUANTITY", "cart": {"items": []}}
        )
        
        # Cart should be in the result
        assert "cart" in result or "items" in result["text"].lower()
        
        # Verify order was understood
        assert "roll" in result["text"].lower()