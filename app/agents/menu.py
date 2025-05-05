"""
Menu Agent for RedBarSushiAI.
This module provides the menu specialist agent that answers questions about the menu.
"""

import os
import json
import logging
import time
from typing import Dict, List, Any, Optional, Union
from app.utils.agents_sdk import tool
from app.utils.openai_compat import Tool

from app.agents.base import BaseAgent
from app.utils.menu_matcher_cache import cached_menu_matcher as menu_matcher
from app.utils.menu_db_store import menu_db_store
from app.utils.menu_cache_sdk import menu_cache
from app.utils.agents_sdk import guardrail
from app.utils.conversation_store import conversation_store

logger = logging.getLogger(__name__)

class MenuAgent(BaseAgent):
    """
    Menu Agent that answers questions about the restaurant's menu.
    Handles inquiries about items, prices, ingredients, and recommendations.
    """
    
    def __init__(
        self,
        name: str = "Menu Agent",
        model: str = "gpt-4.1-mini",
        agent_id: Optional[str] = None
    ):
        """Initialize the Menu Agent."""
        
        instructions = """
        You are a menu specialist for Red Bar Sushi restaurant, answering customer questions about our menu.
        Your primary responsibilities are:
        
        1. Answer factual questions about menu items, prices, and ingredients
        2. Provide recommendations based on customer preferences
        3. Explain dishes and ingredients in detail when requested
        4. Inform customers about allergens and dietary restrictions
        5. Only use information from our actual menu - never make up dishes or ingredients
        
        COMMUNICATION STYLE:
        - Be knowledgeable but conversational
        - Keep responses concise but informative
        - Show enthusiasm for our food
        - Respond appropriately to preferences and restrictions
        
        IMPORTANT RULES:
        - ONLY reference items that actually exist in our menu database
        - NEVER make up menu items, prices, or ingredients
        - Always use the lookup_menu_item tool to verify items before discussing them
        - Be honest when you don't know something
        - Do not reference any food items that aren't in our database
        - Use list_categories to help when recommending general options
        - Use get_restaurant_info for questions about the restaurant itself
        
        You will receive customer menu questions and should respond with factual information 
        based EXCLUSIVELY on our actual menu data.
        """
        
        # Define the tools this agent can use
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "lookup_menu_item",
                    "description": "Look up a specific menu item by name",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_name": {
                                "type": "string",
                                "description": "The name of the menu item to look up"
                            }
                        },
                        "required": ["item_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_categories",
                    "description": "List all menu categories",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_items_by_category",
                    "description": "Get all items in a specific category",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category_name": {
                                "type": "string",
                                "description": "The name of the category"
                            }
                        },
                        "required": ["category_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_restaurant_info",
                    "description": "Get information about the restaurant",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "info_type": {
                                "type": "string",
                                "description": "The type of information to retrieve",
                                "enum": ["hours", "location", "contact", "reservations", "delivery", "general"]
                            }
                        },
                        "required": ["info_type"]
                    }
                }
            }
        ]
        
        # Initialize the agent
        super().__init__(
            name=name,
            instructions=instructions,
            model=model,
            description="Menu specialist agent for Red Bar Sushi",
            tools=tools,
            agent_id=agent_id
        )
    
    @tool
    def lookup_menu_item(self, item_name: str) -> Dict[str, Any]:
        """
        Look up a specific menu item by name.
        
        Args:
            item_name: The name of the menu item to look up
            
        Returns:
            Details about the menu item if found
        """
        logger.info(f"Looking up menu item: {item_name}")
        
        # Use the existing menu matcher to find the item
        menu_item = menu_matcher.find_menu_item(item_name)
        
        if not menu_item:
            logger.info(f"Menu item not found: {item_name}")
            return {
                "found": False,
                "search_term": item_name,
                "message": "This item doesn't appear to be on our menu."
            }
        
        # Format the price for display
        price = menu_item.get("price", 0)
        price_str = f"${price/100:.2f}" if isinstance(price, (int, float)) else "Price unavailable"
        
        # Check if the item is available
        is_available = menu_item.get("available", True) and not menu_item.get("snoozed", False)
        
        # Get modifiers for this item
        modifiers = []
        for mod_group_id in menu_item.get("modifierGroups", []):
            group = menu_db_store.get_modifier_group(mod_group_id)
            if group:
                mod_list = []
                for mod_id in group.get("modifierIds", []):
                    modifier = menu_db_store.get_modifier(mod_id)
                    if modifier and modifier.get("available", True):
                        mod_price = modifier.get("price", 0)
                        mod_price_str = f"${mod_price/100:.2f}" if mod_price else ""
                        mod_list.append({
                            "name": modifier.get("name", ""),
                            "price": mod_price_str
                        })
                
                if mod_list:
                    modifiers.append({
                        "group_name": group.get("name", ""),
                        "modifiers": mod_list
                    })
        
        # Return formatted item details
        return {
            "found": True,
            "name": menu_item.get("name", ""),
            "price": price_str,
            "description": menu_item.get("description", ""),
            "category": menu_item.get("category", ""),
            "is_available": is_available,
            "modifiers": modifiers,
            "vegetarian": menu_item.get("vegetarian", False),
            "vegan": menu_item.get("vegan", False),
            "gluten_free": menu_item.get("gluten_free", False),
            "spicy": menu_item.get("spicy", False)
        }
    
    @tool
    def list_categories(self) -> Dict[str, List[str]]:
        """
        List all menu categories.
        
        Returns:
            List of menu categories
        """
        logger.info("Listing menu categories")
        
        # Get all categories from the menu store
        categories = menu_db_store.get_categories()
        
        # Return formatted categories
        return {
            "categories": [cat.get("name", "") for cat in categories]
        }
    
    @tool
    def get_items_by_category(self, category_name: str) -> Dict[str, Any]:
        """
        Get all items in a specific category.
        
        Args:
            category_name: The name of the category
            
        Returns:
            List of items in the category
        """
        logger.info(f"Getting items for category: {category_name}")
        
        # Get all items in the category
        items = menu_db_store.get_items_by_category(category_name)
        
        if not items:
            logger.info(f"Category not found or empty: {category_name}")
            return {
                "found": False,
                "category": category_name,
                "message": "This category doesn't exist or has no items."
            }
        
        # Format the items for display
        formatted_items = []
        for item in items:
            # Only include available items
            if item.get("available", True) and not item.get("snoozed", False):
                price = item.get("price", 0)
                price_str = f"${price/100:.2f}" if isinstance(price, (int, float)) else "Price unavailable"
                
                formatted_items.append({
                    "name": item.get("name", ""),
                    "price": price_str,
                    "description": item.get("description", "")
                })
        
        return {
            "found": True,
            "category": category_name,
            "items": formatted_items
        }
    
    @tool
    def get_restaurant_info(self, info_type: str) -> Dict[str, Any]:
        """
        Get information about the restaurant.
        
        Args:
            info_type: The type of information to retrieve
            
        Returns:
            Information about the restaurant
        """
        # Restaurant information (same as in FrontlineVoiceAgent)
        restaurant_info = {
            "hours": {
                "monday": "11:00 AM - 10:00 PM",
                "tuesday": "11:00 AM - 10:00 PM",
                "wednesday": "11:00 AM - 10:00 PM",
                "thursday": "11:00 AM - 10:00 PM",
                "friday": "11:00 AM - 11:00 PM",
                "saturday": "11:00 AM - 11:00 PM",
                "sunday": "12:00 PM - 9:00 PM"
            },
            "location": {
                "address": "123 Main Street, Anytown, USA",
                "directions": "Located in the Main Street Shopping Center, next to City Park",
                "parking": "Free parking available in the shopping center lot"
            },
            "contact": {
                "phone": "(555) 123-4567",
                "email": "info@redbarsushi.com",
                "website": "https://www.redbarsushi.com"
            },
            "reservations": {
                "policy": "Reservations recommended for parties of 5 or more",
                "methods": "Call us or book online through our website"
            },
            "delivery": {
                "availability": "Available within a 5-mile radius",
                "platforms": "Order through our website or popular delivery apps",
                "minimum": "$20 minimum order for delivery"
            },
            "general": {
                "about": "Red Bar Sushi offers authentic Japanese cuisine with a modern twist. Our expert chefs prepare fresh sushi, sashimi, and cooked dishes daily.",
                "specialties": "Known for our signature Red Bar Roll and fresh daily fish selections",
                "atmosphere": "Modern, casual dining with both indoor and outdoor seating options"
            }
        }
        
        # Return the requested information
        if info_type in restaurant_info:
            return {
                "info_type": info_type,
                "data": restaurant_info[info_type]
            }
        
        # Default to general information
        return {
            "info_type": "general",
            "data": restaurant_info["general"]
        }
    
    def process_menu_question(self, call_sid: str, question: str) -> str:
        """
        Process a menu-related question from a customer.
        This is a wrapper around process_message that handles conversation store.
        
        Args:
            call_sid: The Twilio call SID
            question: The customer's question
            
        Returns:
            The agent's response
        """
        # Store the question in the conversation store
        conversation_store.add_message(call_sid, "user", question)
        
        # Process the question
        response = self.process_message(call_sid, question)
        
        # Default response if processing fails
        if not response:
            response = "I'm sorry, I don't have that information. Would you like me to check on something else on our menu?"
        
        # Store the response in the conversation store
        conversation_store.add_message(call_sid, "assistant", response)
        
        return response