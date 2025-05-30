"""
Async menu agent for handling menu-related queries.
"""
import logging
from typing import Dict, Any, Optional, List

from app.agents.base_async import BaseAsyncAgent

logger = logging.getLogger(__name__)


class AsyncMenuAgent(BaseAsyncAgent):
    """Agent responsible for menu-related queries and operations."""
    
    def __init__(self, **kwargs):
        """Initialize the menu agent."""
        super().__init__(name="menu_agent", **kwargs)
        self.tools = ["get_menu_items", "check_availability", "get_item_details"]
    
    async def process(self, message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process menu-related queries."""
        context = context or {}
        
        # Simple menu query handling
        message_lower = message.lower()
        
        if "menu" in message_lower or "what do you have" in message_lower:
            return {
                "response": "We have a variety of sushi rolls, nigiri, sashimi, and appetizers. Would you like to hear about a specific category?",
                "suggestions": ["rolls", "nigiri", "appetizers"],
                "type": "menu_inquiry"
            }
        
        if "roll" in message_lower:
            return {
                "response": "Our popular rolls include California Roll, Spicy Tuna Roll, Rainbow Roll, and Dragon Roll. Would you like to know more about any of these?",
                "items": ["California Roll", "Spicy Tuna Roll", "Rainbow Roll", "Dragon Roll"],
                "type": "category_listing"
            }
        
        if "price" in message_lower:
            return {
                "response": "I can help you with pricing. Which item would you like to know the price for?",
                "type": "price_inquiry"
            }
        
        return {
            "response": "I can help you explore our menu. What type of food are you interested in?",
            "type": "general_menu_help"
        }
    
    async def get_menu_items(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get menu items, optionally filtered by category."""
        # This would normally query the database
        # For now, return mock data
        items = [
            {"name": "California Roll", "price": 850, "category": "rolls"},
            {"name": "Spicy Tuna Roll", "price": 950, "category": "rolls"},
            {"name": "Salmon Nigiri", "price": 450, "category": "nigiri"},
            {"name": "Edamame", "price": 450, "category": "appetizers"}
        ]
        
        if category:
            items = [item for item in items if item["category"] == category.lower()]
        
        return items
    
    async def check_availability(self, item_name: str) -> bool:
        """Check if an item is available."""
        # This would normally check the database
        # For now, assume all items are available
        return True
    
    async def get_item_details(self, item_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a menu item."""
        # This would normally query the database
        # For now, return mock data
        items = {
            "california roll": {
                "name": "California Roll",
                "description": "Crab, avocado, and cucumber",
                "price": 850,
                "allergens": ["shellfish"]
            },
            "spicy tuna roll": {
                "name": "Spicy Tuna Roll", 
                "description": "Spicy tuna with cucumber",
                "price": 950,
                "allergens": ["fish"],
                "spicy_level": "medium"
            }
        }
        
        return items.get(item_name.lower())