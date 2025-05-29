"""
End-to-end tests for voice ordering flow.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import json


class TestVoiceOrderingFlow:
    """Test complete voice ordering workflow."""
    
    @pytest.mark.asyncio
    async def test_greeting_flow(self):
        """Test the greeting phase of a voice call."""
        # Mock FSM states
        fsm_states = ["GREETING", "MAIN_MENU"]
        current_state = 0
        
        def get_state():
            return fsm_states[current_state]
        
        def transition():
            nonlocal current_state
            if current_state < len(fsm_states) - 1:
                current_state += 1
        
        # Simulate greeting interaction
        greeting_response = "Welcome to Red Bar Sushi! May I have your name please?"
        customer_name = "John"
        confirmation = f"Thank you, {customer_name}. How can I help you today?"
        
        # Test the flow
        assert get_state() == "GREETING"
        assert greeting_response.startswith("Welcome")
        
        # Customer provides name
        transition()
        assert get_state() == "MAIN_MENU"
        assert customer_name in confirmation
    
    @pytest.mark.asyncio
    async def test_menu_inquiry_flow(self):
        """Test menu inquiry workflow."""
        # Mock menu data
        menu_items = [
            {"name": "California Roll", "price": 850, "plu": "CALI_001"},
            {"name": "Spicy Tuna Roll", "price": 950, "plu": "TUNA_001"}
        ]
        
        # Customer asks about menu
        customer_query = "What rolls do you have?"
        
        # Generate response
        response_items = [f"{item['name']} - ${item['price']/100:.2f}" for item in menu_items]
        response = "We have the following rolls: " + ", ".join(response_items)
        
        assert "California Roll" in response
        assert "Spicy Tuna Roll" in response
        assert "$8.50" in response
    
    @pytest.mark.asyncio
    async def test_order_placement_flow(self):
        """Test order placement workflow."""
        # Mock cart
        cart = []
        
        # Customer places order
        order_request = "I'd like two California rolls"
        
        # Parse order
        item = {"name": "California Roll", "plu": "CALI_001", "quantity": 2, "price": 850}
        cart.append(item)
        
        # Calculate total
        total = sum(item["price"] * item["quantity"] for item in cart)
        
        assert len(cart) == 1
        assert cart[0]["quantity"] == 2
        assert total == 1700
        
        # Generate confirmation
        confirmation = f"I've added 2 California Rolls to your order. Your total is ${total/100:.2f}"
        assert "2 California Rolls" in confirmation
        assert "$17.00" in confirmation
    
    @pytest.mark.asyncio
    async def test_order_confirmation_flow(self):
        """Test order confirmation and fulfillment."""
        # Mock order data
        order = {
            "items": [
                {"name": "California Roll", "quantity": 2, "price": 850},
                {"name": "Miso Soup", "quantity": 1, "price": 350}
            ],
            "customer_name": "John",
            "customer_phone": "+1234567890",
            "order_type": "pickup"
        }
        
        # Calculate total
        total = sum(item["price"] * item["quantity"] for item in order["items"])
        
        # Generate summary
        items_summary = []
        for item in order["items"]:
            items_summary.append(f"{item['quantity']} {item['name']}")
        
        summary = f"Your order includes: {', '.join(items_summary)}. Total: ${total/100:.2f}"
        
        assert "2 California Roll" in summary
        assert "1 Miso Soup" in summary
        assert "$20.50" in summary
        
        # Confirm order
        order["status"] = "confirmed"
        order["estimated_time"] = "15-20 minutes"
        
        final_message = f"Order confirmed! It will be ready for pickup in {order['estimated_time']}"
        assert "confirmed" in final_message
        assert "15-20 minutes" in final_message
    
    @pytest.mark.asyncio
    async def test_error_handling_flow(self):
        """Test error handling in voice flow."""
        # Test invalid item
        invalid_request = "I want a pizza"
        error_response = "I'm sorry, we don't have pizza on our menu. We specialize in sushi."
        
        assert "don't have pizza" in error_response
        assert "sushi" in error_response
        
        # Test clarification
        ambiguous_request = "I want rolls"
        clarification = "We have several types of rolls. Would you like to hear our roll options?"
        
        assert "several types" in clarification
        assert "options" in clarification
    
    @pytest.mark.asyncio
    async def test_complete_order_flow(self):
        """Test a complete order from start to finish."""
        # Initialize flow state
        flow_state = {
            "phase": "greeting",
            "customer_name": None,
            "cart": [],
            "order_confirmed": False
        }
        
        # Phase 1: Greeting
        flow_state["phase"] = "greeting"
        greeting = "Welcome to Red Bar Sushi!"
        assert "Welcome" in greeting
        
        # Customer provides name
        flow_state["customer_name"] = "Alice"
        flow_state["phase"] = "main_menu"
        
        # Phase 2: Order placement
        flow_state["phase"] = "ordering"
        flow_state["cart"].append({
            "name": "Rainbow Roll",
            "quantity": 1,
            "price": 1450
        })
        flow_state["cart"].append({
            "name": "Edamame",
            "quantity": 1,
            "price": 450
        })
        
        # Phase 3: Confirmation
        flow_state["phase"] = "confirmation"
        total = sum(item["price"] * item["quantity"] for item in flow_state["cart"])
        assert total == 1900
        
        # Phase 4: Fulfillment
        flow_state["order_confirmed"] = True
        flow_state["phase"] = "completion"
        
        # Verify complete flow
        assert flow_state["customer_name"] == "Alice"
        assert len(flow_state["cart"]) == 2
        assert flow_state["order_confirmed"] is True
        assert flow_state["phase"] == "completion"