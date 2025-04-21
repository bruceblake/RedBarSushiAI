"""
Test script for menu matcher functionality.
This script demonstrates and validates the AI-powered menu item matching capabilities.
"""

import sys
import os
import json
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger(__name__)

# Add the project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Import the app to ensure everything is initialized
from app import create_app
app = create_app()

# Import the menu matcher
from app.utils.menu_matcher import menu_matcher, find_menu_item_ai

def test_menu_matcher():
    """Test the menu matcher with various inputs."""
    print("Testing Menu Matcher")
    print("-------------------")
    
    # Test exact match
    test_exact_match("Veggie Burger")
    
    # Test close matches
    test_ai_match("cheese burger", "I want a burger with cheese")
    test_ai_match("fries", "I'd like some french fries")
    test_ai_match("coke", "I want a cola")
    
    # Test interactive order resolution
    test_interactive_resolution("I want a burger with fries and a drink")
    
    print("\nTests completed!")

def test_exact_match(item_name):
    """Test exact matching."""
    print(f"\nTesting exact match for: '{item_name}'")
    
    with app.app_context():
        item = menu_matcher.find_menu_item(item_name)
        
        if item:
            print(f"✅ Found exact match: {item.get('name')} (${item.get('price', 0.0):.2f})")
        else:
            print(f"❌ No exact match found")

def test_ai_match(item_name, context_text=None):
    """Test AI-based matching."""
    print(f"\nTesting AI match for: '{item_name}'")
    if context_text:
        print(f"Context: '{context_text}'")
    
    context = {"conversation": context_text} if context_text else None
    
    with app.app_context():
        item = find_menu_item_ai(item_name, context=context)
        
        if item:
            print(f"✅ Found AI match: {item.get('name')} (${item.get('price', 0.0):.2f})")
        else:
            print(f"❌ No AI match found")

def test_interactive_resolution(customer_request):
    """Test the interactive order resolution flow."""
    print(f"\nTesting interactive resolution for: '{customer_request}'")
    
    with app.app_context():
        # Start the order resolution
        order_state = menu_matcher.interactive_order_resolution(customer_request)
        
        print(f"Initial clarification: {order_state.get('clarification_dialog')}")
        
        # Simulate customer responses
        responses = [
            "I'd like a cheeseburger, large fries, and a coke",
            "That's correct, thank you"
        ]
        
        for i, response in enumerate(responses):
            print(f"\nCustomer response {i+1}: '{response}'")
            
            # Add the response to the conversation
            if "conversation" not in order_state:
                order_state["conversation"] = []
            order_state["conversation"].append({"role": "user", "content": response})
            
            # Process the response
            order_state = menu_matcher.process_customer_response(order_state, response)
            
            print(f"AI response: {order_state.get('clarification_dialog')}")
            
            if order_state.get("resolved", False):
                print("\nOrder resolved!")
                print("Final items:")
                for item in order_state.get("items", []):
                    print(f"- {item.get('quantity', 1)}x {item.get('name')} (${item.get('price', 0.0):.2f})")
                break

if __name__ == "__main__":
    test_menu_matcher()