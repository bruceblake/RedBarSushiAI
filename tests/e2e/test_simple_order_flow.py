"""
End-to-end tests for simple order flow - Task 4.1.1.

This module tests the complete simple order flow:
greeting → menu inquiry → order → confirmation

Tests the full user journey from initial call to order completion.
"""

import pytest
import pytest_asyncio
import asyncio
import json
import uuid
from typing import Dict, Any, List, Optional
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.fsm.core import ConversationState, ConversationEvent
from app.utils.agent_orchestration_async import AsyncAgentOrchestrator
from app.utils.conversation_store_async import async_conversation_store
from app.models.menu_async import MenuItem, MenuCategory, MenuModifier, MenuModifierGroup
from app.models.order_async import Order, OrderItem


@pytest.fixture
def test_client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest_asyncio.fixture
async def orchestrator():
    """Create and initialize an agent orchestrator."""
    orchestrator = AsyncAgentOrchestrator()
    
    # Mock the agents to avoid external dependencies
    orchestrator.frontline_agent = AsyncMock()
    orchestrator.menu_agent = AsyncMock()
    orchestrator.cart_agent = AsyncMock()
    orchestrator.guardrail_agent = AsyncMock()
    orchestrator.fulfillment_agent = AsyncMock()
    orchestrator.escalation_agent = AsyncMock()
    
    return orchestrator


@pytest_asyncio.fixture
async def sample_menu_data():
    """Create sample menu data for testing."""
    return {
        "categories": [
            {
                "id": 1,
                "name": "Sushi Rolls",
                "description": "Fresh sushi rolls"
            }
        ],
        "items": [
            {
                "id": 1,
                "name": "California Roll",
                "description": "Crab, avocado, cucumber",
                "price": 12.95,
                "plu": "CALI_001",
                "category_id": 1,
                "is_available": True
            },
            {
                "id": 2,
                "name": "Spicy Tuna Roll",
                "description": "Spicy tuna, cucumber",
                "price": 13.95,
                "plu": "TUNA_001",
                "category_id": 1,
                "is_available": True
            },
            {
                "id": 3,
                "name": "Miso Soup",
                "description": "Traditional soybean soup",
                "price": 4.95,
                "plu": "SOUP_001",
                "category_id": 1,
                "is_available": True
            }
        ]
    }


@pytest_asyncio.fixture
async def mock_deliverect_client():
    """Mock Deliverect client for order submission."""
    mock_client = AsyncMock()
    mock_client.submit_order.return_value = {
        "order_id": "deliverect_12345",
        "status": "accepted",
        "estimated_time": 25
    }
    return mock_client


class TestSimpleOrderFlow:
    """Test the complete simple order flow end-to-end."""
    
    @pytest.mark.asyncio
    async def test_complete_simple_order_flow(self, orchestrator, sample_menu_data, mock_deliverect_client):
        """Test the complete simple order flow from greeting to confirmation."""
        call_sid = f"CA{uuid.uuid4().hex[:24]}"
        
        # Set up mock responses for each stage
        await self._setup_mock_responses(orchestrator, sample_menu_data)
        
        # Stage 1: Initial Greeting
        greeting_response = await self._test_greeting_stage(orchestrator, call_sid)
        assert "welcome" in greeting_response["text"].lower()
        assert greeting_response["state"] == ConversationState.GREETING.name
        
        # Stage 2: Provide Name
        name_response = await self._test_name_provision(orchestrator, call_sid)
        assert greeting_response["state"] in [ConversationState.GREETING.name, ConversationState.MAIN_MENU.name]
        
        # Stage 3: Menu Inquiry
        menu_response = await self._test_menu_inquiry(orchestrator, call_sid)
        assert any(item["name"] in menu_response["text"] for item in sample_menu_data["items"])
        
        # Stage 4: Place Order
        order_response = await self._test_place_order(orchestrator, call_sid)
        assert "california roll" in order_response["text"].lower()
        assert order_response["state"] == ConversationState.ORDERING.name
        
        # Stage 5: Order Confirmation
        confirmation_response = await self._test_order_confirmation(orchestrator, call_sid)
        assert "confirm" in confirmation_response["text"].lower()
        assert confirmation_response["state"] == ConversationState.CONFIRMATION.name
        
        # Stage 6: Final Confirmation
        final_response = await self._test_final_confirmation(orchestrator, call_sid, mock_deliverect_client)
        assert "order" in final_response["text"].lower()
        assert final_response["state"] in [ConversationState.FULFILLMENT.name, ConversationState.COMPLETION.name]
        
        # Verify conversation flow
        await self._verify_conversation_flow(call_sid)
    
    async def _setup_mock_responses(self, orchestrator, sample_menu_data):
        """Set up mock responses for different stages."""
        # Mock frontline agent responses
        orchestrator.frontline_agent.process_voice_input.side_effect = self._mock_frontline_responses
        
        # Mock menu agent responses
        orchestrator.menu_agent.process_voice_input.side_effect = self._mock_menu_responses(sample_menu_data)
        
        # Mock cart agent responses
        orchestrator.cart_agent.process_voice_input.side_effect = self._mock_cart_responses
        
        # Mock fulfillment agent responses
        orchestrator.fulfillment_agent.process_voice_input.side_effect = self._mock_fulfillment_responses
    
    async def _mock_frontline_responses(self, input_text: str, context: Dict[str, Any] = None):
        """Mock frontline agent responses."""
        context = context or {}
        
        if context.get("first_interaction"):
            return {
                "text": "Welcome to Red Bar Sushi! I'm here to help you with your order. May I have your name please?",
                "handled": True,
                "agent": "FrontlineAgent",
                "actions": ["request_name"]
            }
        elif "name" in input_text.lower() or any(word in input_text.lower() for word in ["john", "jane", "my", "i'm"]):
            return {
                "text": "Thank you! How can I help you today? Would you like to hear about our menu or place an order?",
                "handled": True,
                "agent": "FrontlineAgent", 
                "actions": ["transition_to_main_menu"]
            }
        else:
            return {
                "text": "I understand. How else can I help you today?",
                "handled": True,
                "agent": "FrontlineAgent"
            }
    
    def _mock_menu_responses(self, sample_menu_data):
        """Create mock menu agent responses."""
        async def mock_menu_agent(input_text: str, context: Dict[str, Any] = None):
            if any(word in input_text.lower() for word in ["menu", "what", "have", "available", "options"]):
                menu_text = "Here are our popular items: "
                menu_text += ", ".join([item["name"] for item in sample_menu_data["items"]])
                menu_text += ". What would you like to order?"
                
                return {
                    "text": menu_text,
                    "handled": True,
                    "agent": "MenuAgent",
                    "actions": ["show_menu"],
                    "menu_items": sample_menu_data["items"]
                }
            else:
                return {
                    "text": "I can help you with our menu. What would you like to know?",
                    "handled": True,
                    "agent": "MenuAgent"
                }
        
        return mock_menu_agent
    
    async def _mock_cart_responses(self, input_text: str, context: Dict[str, Any] = None):
        """Mock cart agent responses."""
        if any(word in input_text.lower() for word in ["california", "roll", "order", "add"]):
            return {
                "text": "Great choice! I've added one California Roll to your order. That's $12.95. Would you like anything else?",
                "handled": True,
                "agent": "CartAgent",
                "actions": ["add_item"],
                "cart_items": [
                    {
                        "name": "California Roll",
                        "price": 12.95,
                        "quantity": 1,
                        "plu": "CALI_001"
                    }
                ],
                "cart_total": 12.95
            }
        elif any(word in input_text.lower() for word in ["that's", "all", "done", "complete", "ready"]):
            return {
                "text": "Perfect! Your order is one California Roll for $12.95. Is this correct?",
                "handled": True,
                "agent": "CartAgent",
                "actions": ["review_order"]
            }
        else:
            return {
                "text": "I can help you add items to your order. What would you like?",
                "handled": True,
                "agent": "CartAgent"
            }
    
    async def _mock_fulfillment_responses(self, input_text: str, context: Dict[str, Any] = None):
        """Mock fulfillment agent responses."""
        if any(word in input_text.lower() for word in ["yes", "correct", "confirm", "that's right"]):
            return {
                "text": "Excellent! Your order has been confirmed. One California Roll for $12.95. Your order will be ready for pickup in about 15-20 minutes. Thank you for choosing Red Bar Sushi!",
                "handled": True,
                "agent": "FulfillmentAgent",
                "actions": ["submit_order", "send_confirmation"],
                "order_confirmed": True,
                "estimated_time": "15-20 minutes"
            }
        else:
            return {
                "text": "I can help finalize your order. Is everything correct?",
                "handled": True,
                "agent": "FulfillmentAgent"
            }
    
    async def _test_greeting_stage(self, orchestrator, call_sid):
        """Test the initial greeting stage."""
        response = await orchestrator.process_voice_input(
            call_sid, 
            "", 
            {"first_interaction": True}
        )
        
        assert response["handled"] is True
        assert "welcome" in response["text"].lower()
        assert "name" in response["text"].lower()
        
        return response
    
    async def _test_name_provision(self, orchestrator, call_sid):
        """Test providing name to the system."""
        response = await orchestrator.process_voice_input(
            call_sid,
            "My name is John Doe"
        )
        
        assert response["handled"] is True
        assert "thank you" in response["text"].lower() or "john" in response["text"].lower()
        
        return response
    
    async def _test_menu_inquiry(self, orchestrator, call_sid):
        """Test menu inquiry stage."""
        response = await orchestrator.process_voice_input(
            call_sid,
            "What's on the menu today?"
        )
        
        assert response["handled"] is True
        assert any(word in response["text"].lower() for word in ["california", "tuna", "soup"])
        
        return response
    
    async def _test_place_order(self, orchestrator, call_sid):
        """Test placing an order."""
        response = await orchestrator.process_voice_input(
            call_sid,
            "I'd like a California Roll please"
        )
        
        assert response["handled"] is True
        assert "california roll" in response["text"].lower()
        assert "12.95" in response["text"] or "$12.95" in response["text"]
        
        return response
    
    async def _test_order_confirmation(self, orchestrator, call_sid):
        """Test order confirmation stage."""
        response = await orchestrator.process_voice_input(
            call_sid,
            "That's all for now"
        )
        
        assert response["handled"] is True
        assert "california roll" in response["text"].lower()
        assert any(word in response["text"].lower() for word in ["correct", "confirm", "order"])
        
        return response
    
    async def _test_final_confirmation(self, orchestrator, call_sid, mock_deliverect_client):
        """Test final confirmation and order submission."""
        with patch('app.utils.deliverect_async.submit_order', return_value=mock_deliverect_client.submit_order.return_value):
            response = await orchestrator.process_voice_input(
                call_sid,
                "Yes, that's correct"
            )
        
        assert response["handled"] is True
        assert any(word in response["text"].lower() for word in ["confirmed", "order", "ready", "minutes"])
        
        return response
    
    async def _verify_conversation_flow(self, call_sid):
        """Verify the complete conversation flow was recorded."""
        # Get conversation history
        conversation = await async_conversation_store.get_conversation(call_sid)
        
        assert conversation is not None
        assert len(conversation.get("messages", [])) >= 6  # At least 6 exchanges
        
        # Verify message types
        messages = conversation["messages"]
        user_messages = [msg for msg in messages if msg["role"] == "user"]
        assistant_messages = [msg for msg in messages if msg["role"] == "assistant"]
        
        assert len(user_messages) >= 3  # Name, menu inquiry, order
        assert len(assistant_messages) >= 3  # Greeting, menu response, confirmation


class TestSimpleOrderFlowVariations:
    """Test variations of the simple order flow."""
    
    @pytest.mark.asyncio
    async def test_pickup_order_flow(self, orchestrator, sample_menu_data):
        """Test simple pickup order flow."""
        call_sid = f"CA{uuid.uuid4().hex[:24]}_pickup"
        
        # Setup mocks for pickup flow
        await self._setup_pickup_mocks(orchestrator, sample_menu_data)
        
        # Execute pickup flow
        responses = await self._execute_pickup_flow(orchestrator, call_sid)
        
        # Verify pickup-specific elements
        final_response = responses[-1]
        assert "pickup" in final_response["text"].lower() or "ready" in final_response["text"].lower()
    
    @pytest.mark.asyncio 
    async def test_delivery_order_flow(self, orchestrator, sample_menu_data):
        """Test simple delivery order flow."""
        call_sid = f"CA{uuid.uuid4().hex[:24]}_delivery"
        
        # Setup mocks for delivery flow
        await self._setup_delivery_mocks(orchestrator, sample_menu_data)
        
        # Execute delivery flow
        responses = await self._execute_delivery_flow(orchestrator, call_sid)
        
        # Verify delivery-specific elements
        address_response = responses[4]  # Address collection response
        assert "address" in address_response["text"].lower()
        
        final_response = responses[-1]
        assert "deliver" in final_response["text"].lower() or "address" in final_response["text"].lower()
    
    @pytest.mark.asyncio
    async def test_single_item_order_flow(self, orchestrator, sample_menu_data):
        """Test flow with single item order."""
        call_sid = f"CA{uuid.uuid4().hex[:24]}_single"
        
        # Setup for single item
        await self._setup_single_item_mocks(orchestrator, sample_menu_data)
        
        # Execute single item flow
        responses = await self._execute_single_item_flow(orchestrator, call_sid)
        
        # Verify single item handling
        order_response = responses[3]  # Order placement response
        assert "one" in order_response["text"].lower() or "1" in order_response["text"]
    
    @pytest.mark.asyncio
    async def test_quick_order_flow(self, orchestrator, sample_menu_data):
        """Test quick order flow (customer knows what they want)."""
        call_sid = f"CA{uuid.uuid4().hex[:24]}_quick"
        
        # Setup for quick order
        await self._setup_quick_order_mocks(orchestrator, sample_menu_data)
        
        # Execute quick order flow (skip menu inquiry)
        responses = await self._execute_quick_order_flow(orchestrator, call_sid)
        
        # Verify quick flow (should be shorter)
        assert len(responses) <= 5  # Should be fewer steps
    
    async def _setup_pickup_mocks(self, orchestrator, sample_menu_data):
        """Setup mocks for pickup order flow."""
        orchestrator.frontline_agent.process_voice_input.side_effect = self._mock_pickup_frontline
        orchestrator.menu_agent.process_voice_input.side_effect = self._mock_menu_responses(sample_menu_data)
        orchestrator.cart_agent.process_voice_input.side_effect = self._mock_pickup_cart
        orchestrator.fulfillment_agent.process_voice_input.side_effect = self._mock_pickup_fulfillment
    
    async def _mock_pickup_frontline(self, input_text: str, context: Dict[str, Any] = None):
        """Mock frontline responses for pickup."""
        context = context or {}
        
        if context.get("first_interaction"):
            return {
                "text": "Welcome to Red Bar Sushi! I'm here to help with your pickup order. What's your name?",
                "handled": True,
                "agent": "FrontlineAgent"
            }
        elif "name" in input_text.lower():
            return {
                "text": "Thanks! What would you like to order for pickup today?",
                "handled": True,
                "agent": "FrontlineAgent"
            }
        else:
            return {"text": "How can I help with your pickup order?", "handled": True, "agent": "FrontlineAgent"}
    
    async def _mock_pickup_cart(self, input_text: str, context: Dict[str, Any] = None):
        """Mock cart responses for pickup."""
        if "california" in input_text.lower():
            return {
                "text": "Perfect! One California Roll for pickup. That's $12.95. Anything else?",
                "handled": True,
                "agent": "CartAgent",
                "order_type": "pickup"
            }
        else:
            return {"text": "What would you like for pickup?", "handled": True, "agent": "CartAgent"}
    
    async def _mock_pickup_fulfillment(self, input_text: str, context: Dict[str, Any] = None):
        """Mock fulfillment responses for pickup."""
        return {
            "text": "Order confirmed for pickup! One California Roll, $12.95. Ready in 15 minutes at Red Bar Sushi.",
            "handled": True,
            "agent": "FulfillmentAgent",
            "order_type": "pickup"
        }
    
    async def _execute_pickup_flow(self, orchestrator, call_sid):
        """Execute the pickup order flow."""
        responses = []
        
        # Greeting
        responses.append(await orchestrator.process_voice_input(call_sid, "", {"first_interaction": True}))
        
        # Name
        responses.append(await orchestrator.process_voice_input(call_sid, "I'm Sarah"))
        
        # Order directly
        responses.append(await orchestrator.process_voice_input(call_sid, "I'd like a California Roll"))
        
        # Complete order
        responses.append(await orchestrator.process_voice_input(call_sid, "That's all"))
        
        # Confirm
        responses.append(await orchestrator.process_voice_input(call_sid, "Yes, correct"))
        
        return responses
    
    async def _setup_delivery_mocks(self, orchestrator, sample_menu_data):
        """Setup mocks for delivery order flow."""
        orchestrator.frontline_agent.process_voice_input.side_effect = self._mock_delivery_frontline
        orchestrator.cart_agent.process_voice_input.side_effect = self._mock_delivery_cart
        orchestrator.fulfillment_agent.process_voice_input.side_effect = self._mock_delivery_fulfillment
    
    async def _mock_delivery_frontline(self, input_text: str, context: Dict[str, Any] = None):
        """Mock frontline responses for delivery."""
        context = context or {}
        
        if context.get("first_interaction"):
            return {
                "text": "Welcome to Red Bar Sushi delivery! What's your name and delivery address?",
                "handled": True,
                "agent": "FrontlineAgent"
            }
        else:
            return {"text": "How can I help with your delivery?", "handled": True, "agent": "FrontlineAgent"}
    
    async def _mock_delivery_cart(self, input_text: str, context: Dict[str, Any] = None):
        """Mock cart responses for delivery."""
        if "address" in input_text.lower():
            return {
                "text": "Got your address. What would you like to order for delivery?",
                "handled": True,
                "agent": "CartAgent"
            }
        elif "california" in input_text.lower():
            return {
                "text": "California Roll added for delivery. $12.95 plus delivery fee. Anything else?",
                "handled": True,
                "agent": "CartAgent",
                "order_type": "delivery"
            }
        else:
            return {"text": "What would you like delivered?", "handled": True, "agent": "CartAgent"}
    
    async def _mock_delivery_fulfillment(self, input_text: str, context: Dict[str, Any] = None):
        """Mock fulfillment responses for delivery."""
        return {
            "text": "Delivery order confirmed! California Roll will be delivered to your address in 30-40 minutes.",
            "handled": True,
            "agent": "FulfillmentAgent",
            "order_type": "delivery"
        }
    
    async def _execute_delivery_flow(self, orchestrator, call_sid):
        """Execute the delivery order flow."""
        responses = []
        
        # Greeting
        responses.append(await orchestrator.process_voice_input(call_sid, "", {"first_interaction": True}))
        
        # Name and address
        responses.append(await orchestrator.process_voice_input(call_sid, "I'm Mike at 123 Main Street"))
        
        # Address confirmation
        responses.append(await orchestrator.process_voice_input(call_sid, "Yes, that's my address"))
        
        # Order
        responses.append(await orchestrator.process_voice_input(call_sid, "California Roll please"))
        
        # Complete
        responses.append(await orchestrator.process_voice_input(call_sid, "That's all"))
        
        # Confirm
        responses.append(await orchestrator.process_voice_input(call_sid, "Yes, deliver it"))
        
        return responses
    
    async def _setup_single_item_mocks(self, orchestrator, sample_menu_data):
        """Setup mocks for single item order."""
        orchestrator.cart_agent.process_voice_input.side_effect = self._mock_single_item_cart
    
    async def _mock_single_item_cart(self, input_text: str, context: Dict[str, Any] = None):
        """Mock cart for single item order."""
        return {
            "text": "Perfect! Just one California Roll. That's $12.95 total. Ready to order?",
            "handled": True,
            "agent": "CartAgent",
            "item_count": 1
        }
    
    async def _execute_single_item_flow(self, orchestrator, call_sid):
        """Execute single item order flow."""
        responses = []
        
        responses.append(await orchestrator.process_voice_input(call_sid, "", {"first_interaction": True}))
        responses.append(await orchestrator.process_voice_input(call_sid, "I'm Lisa"))
        responses.append(await orchestrator.process_voice_input(call_sid, "Just one California Roll"))
        responses.append(await orchestrator.process_voice_input(call_sid, "Yes, that's all"))
        
        return responses
    
    async def _setup_quick_order_mocks(self, orchestrator, sample_menu_data):
        """Setup mocks for quick order flow."""
        orchestrator.frontline_agent.process_voice_input.side_effect = self._mock_quick_frontline
    
    async def _mock_quick_frontline(self, input_text: str, context: Dict[str, Any] = None):
        """Mock frontline for quick order."""
        context = context or {}
        
        if context.get("first_interaction"):
            return {
                "text": "Welcome to Red Bar Sushi! Quick order?",
                "handled": True,
                "agent": "FrontlineAgent"
            }
        else:
            return {"text": "Got it! Anything else?", "handled": True, "agent": "FrontlineAgent"}
    
    async def _execute_quick_order_flow(self, orchestrator, call_sid):
        """Execute quick order flow."""
        responses = []
        
        responses.append(await orchestrator.process_voice_input(call_sid, "", {"first_interaction": True}))
        responses.append(await orchestrator.process_voice_input(call_sid, "Yes, California Roll for Tom"))
        responses.append(await orchestrator.process_voice_input(call_sid, "That's it"))
        responses.append(await orchestrator.process_voice_input(call_sid, "Confirmed"))
        
        return responses


class TestSimpleOrderFlowErrorRecovery:
    """Test error recovery in simple order flows."""
    
    @pytest.mark.asyncio
    async def test_name_clarification_flow(self, orchestrator, sample_menu_data):
        """Test flow when name needs clarification."""
        call_sid = f"CA{uuid.uuid4().hex[:24]}_name_clarify"
        
        # Setup mocks for name clarification
        await self._setup_name_clarification_mocks(orchestrator)
        
        responses = []
        
        # Initial greeting
        responses.append(await orchestrator.process_voice_input(call_sid, "", {"first_interaction": True}))
        
        # Unclear name
        responses.append(await orchestrator.process_voice_input(call_sid, "Um, it's like, uh..."))
        
        # Clarification request
        assert "name" in responses[-1]["text"].lower()
        
        # Clear name
        responses.append(await orchestrator.process_voice_input(call_sid, "Sorry, it's David"))
        
        # Should proceed normally
        assert "thank" in responses[-1]["text"].lower() or "david" in responses[-1]["text"].lower()
    
    @pytest.mark.asyncio
    async def test_menu_item_clarification_flow(self, orchestrator, sample_menu_data):
        """Test flow when menu item needs clarification."""
        call_sid = f"CA{uuid.uuid4().hex[:24]}_item_clarify"
        
        # Setup mocks for item clarification
        await self._setup_item_clarification_mocks(orchestrator, sample_menu_data)
        
        responses = []
        
        # Standard opening
        responses.append(await orchestrator.process_voice_input(call_sid, "", {"first_interaction": True}))
        responses.append(await orchestrator.process_voice_input(call_sid, "I'm Alex"))
        
        # Unclear item request
        responses.append(await orchestrator.process_voice_input(call_sid, "I want that roll thing"))
        
        # Should ask for clarification
        assert any(word in responses[-1]["text"].lower() for word in ["which", "clarify", "specific"])
        
        # Clear specification
        responses.append(await orchestrator.process_voice_input(call_sid, "The California Roll"))
        
        # Should confirm the item
        assert "california roll" in responses[-1]["text"].lower()
    
    async def _setup_name_clarification_mocks(self, orchestrator):
        """Setup mocks for name clarification testing."""
        async def mock_name_clarification(input_text: str, context: Dict[str, Any] = None):
            context = context or {}
            
            if context.get("first_interaction"):
                return {
                    "text": "Welcome! May I have your name please?",
                    "handled": True,
                    "agent": "FrontlineAgent"
                }
            elif any(word in input_text.lower() for word in ["um", "uh", "like"]) and len(input_text.split()) < 4:
                return {
                    "text": "I didn't catch that clearly. Could you please tell me your name again?",
                    "handled": True,
                    "agent": "FrontlineAgent",
                    "actions": ["request_clarification"]
                }
            elif "david" in input_text.lower():
                return {
                    "text": "Thank you, David! How can I help you today?",
                    "handled": True,
                    "agent": "FrontlineAgent"
                }
            else:
                return {"text": "How can I help?", "handled": True, "agent": "FrontlineAgent"}
        
        orchestrator.frontline_agent.process_voice_input.side_effect = mock_name_clarification
    
    async def _setup_item_clarification_mocks(self, orchestrator, sample_menu_data):
        """Setup mocks for item clarification testing."""
        async def mock_item_clarification(input_text: str, context: Dict[str, Any] = None):
            if "roll thing" in input_text.lower():
                return {
                    "text": "We have several rolls available. Which specific roll would you like? We have California Roll, Spicy Tuna Roll, and others.",
                    "handled": True,
                    "agent": "MenuAgent",
                    "actions": ["request_clarification"]
                }
            elif "california roll" in input_text.lower():
                return {
                    "text": "Perfect! One California Roll added to your order. That's $12.95.",
                    "handled": True,
                    "agent": "CartAgent",
                    "actions": ["add_item"]
                }
            else:
                return {"text": "What would you like to order?", "handled": True, "agent": "MenuAgent"}
        
        orchestrator.menu_agent.process_voice_input.side_effect = mock_item_clarification
        orchestrator.cart_agent.process_voice_input.side_effect = mock_item_clarification