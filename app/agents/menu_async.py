"""
Async Menu Agent for RedBarSushiAI.
This module provides the async menu specialist agent that answers questions about the menu.
"""

import os
import json
import logging
import time
from typing import Dict, List, Any, Optional, Union, Callable

from app.agents.base_async import BaseAsyncAgent
from app.utils.menu_matcher_cache_async import get_cached_async_menu_matcher
from app.utils.menu_db_store import menu_db_store
from app.utils.menu_cache_sdk import menu_cache
from app.utils.agents_sdk import guardrail
from app.utils.conversation_store_async import async_conversation_store
from app.config import settings

# Set up logging
logger = logging.getLogger(__name__)

class AsyncMenuAgent(BaseAsyncAgent):
    """
    Async Menu Agent that answers questions about the restaurant's menu.
    Handles inquiries about items, prices, ingredients, and recommendations.
    """
    
    def __init__(
        self,
        agent_id: Optional[str] = None,
        db: Optional[Any] = None
    ):
        """
        Initialize the Async Menu Agent.
        
        Args:
            agent_id: Optional ID for the agent (used with OpenAI Assistants API)
            db: Optional database session for async operations
        """
        super().__init__(agent_id=agent_id, name="Menu")
        self.db = db
        
        # Define the tools this agent can use
        self.tools = [
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
        
        # Set agent instructions
        self.instructions = """
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
    
    async def process_input(self, input_text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a text input and generate a response.
        
        Args:
            input_text: The text input to process
            context: Optional context information
            
        Returns:
            Dict[str, Any]: The agent's response
        """
        context = context or {}
        self.update_context(context)
        
        # Log the input
        logger.info(f"[{self.name}] Processing menu question: {input_text}")
        
        # Process the menu question using the appropriate model
        response_text = await self._generate_menu_response(input_text)
        
        # Format the response
        response = {
            "text": response_text,
            "agent": self.name,
            "handled": True,
            "actions": []
        }
        
        return response
    
    async def _generate_menu_response(self, question: str) -> str:
        """
        Generate a response to a menu question using language model.
        
        Args:
            question: The customer's menu question
            
        Returns:
            str: The response text
        """
        # Here we would connect to OpenAI or other model using async
        # For now we implement a simpler version based on item lookup
        
        # Basic intent detection
        if "category" in question.lower() or "categories" in question.lower():
            categories = await self.execute_tool("list_categories", {})
            category_names = categories.get("categories", [])
            
            return f"We have the following categories on our menu: {', '.join(category_names)}. What would you like to know more about?"
            
        # Check for general restaurant questions
        restaurant_terms = ["hours", "open", "close", "located", "location", "address", "reservation", "directions"]
        for term in restaurant_terms:
            if term in question.lower():
                info = await self.execute_tool("get_restaurant_info", {"info_type": "general"})
                hours = await self.execute_tool("get_restaurant_info", {"info_type": "hours"})
                location = await self.execute_tool("get_restaurant_info", {"info_type": "location"})
                
                about = info.get("data", {}).get("about", "")
                hours_monday = hours.get("data", {}).get("monday", "")
                address = location.get("data", {}).get("address", "")
                
                return f"{about} We're located at {address}. Our hours on Monday are {hours_monday}. How can I help you with our menu today?"
        
        # Extract potential menu items from the question
        # This is a simple approach - in production, you would use more sophisticated NLP
        question_words = question.lower().split()
        potential_menu_items = []
        
        for i in range(len(question_words)):
            for j in range(i + 1, min(i + 5, len(question_words) + 1)):
                potential_item = " ".join(question_words[i:j])
                if len(potential_item) > 3:  # Avoid checking very short terms
                    potential_menu_items.append(potential_item)
        
        # Look up each potential menu item
        for item_name in potential_menu_items:
            item_result = await self.execute_tool("lookup_menu_item", {"item_name": item_name})
            
            if item_result.get("found", False):
                name = item_result.get("name", "")
                price = item_result.get("price", "")
                description = item_result.get("description", "")
                is_available = item_result.get("is_available", True)
                
                # Generate an appropriate response based on availability
                if is_available:
                    return f"Our {name} is {price} and it's {description}. Would you like to know more about it or any other items?"
                else:
                    return f"Unfortunately, our {name} is currently unavailable. Can I suggest something else from our menu?"
        
        # If no specific items found, provide a general response with categories
        categories = await self.execute_tool("list_categories", {})
        category_names = categories.get("categories", [])
        
        if category_names:
            # Pick the first category to provide examples
            first_category = category_names[0]
            category_items = await self.execute_tool("get_items_by_category", {"category_name": first_category})
            
            items = category_items.get("items", [])
            item_names = [item.get("name", "") for item in items[:3]]
            
            # Format the response
            category_list = ", ".join(category_names[:5])
            if len(category_names) > 5:
                category_list += f", and {len(category_names) - 5} more categories"
                
            item_list = ", ".join(item_names)
            
            return f"I'd be happy to help you with our menu. We have {category_list}. For example, in our {first_category} category, we have {item_list}. What would you like to know more about?"
        
        # Fallback response
        return "I'd be happy to tell you about our menu. What specifically would you like to know about our dishes, prices, or specialties?"
    
    async def process_menu_question(self, call_sid: str, question: str) -> str:
        """
        Process a menu-related question from a customer.
        This is a wrapper around process_input that handles conversation store.
        
        Args:
            call_sid: The Twilio call SID
            question: The customer's question
            
        Returns:
            The agent's response
        """
        # Store the question in the conversation store
        await async_conversation_store.add_message(call_sid, "user", question)
        
        # Process the question
        response = await self.process_input(question, {"call_sid": call_sid})
        
        # Get the response text
        response_text = response.get("text", "")
        
        # Default response if processing fails
        if not response_text:
            response_text = "I'm sorry, I don't have that information. Would you like me to check on something else on our menu?"
        
        # Store the response in the conversation store
        await async_conversation_store.add_message(call_sid, "assistant", response_text)
        
        return response_text
    
    async def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool owned by this agent.
        
        Args:
            tool_name: The name of the tool to execute
            args: Arguments for the tool
            
        Returns:
            Dict[str, Any]: The tool's result
        """
        logger.info(f"[{self.name}] Executing tool: {tool_name} with args: {args}")
        
        if tool_name == "lookup_menu_item":
            return await self._lookup_menu_item(args.get("item_name", ""))
        elif tool_name == "list_categories":
            return await self._list_categories()
        elif tool_name == "get_items_by_category":
            return await self._get_items_by_category(args.get("category_name", ""))
        elif tool_name == "get_restaurant_info":
            return await self._get_restaurant_info(args.get("info_type", "general"))
        else:
            logger.warning(f"[{self.name}] Unknown tool: {tool_name}")
            return {
                "status": "error",
                "message": f"Tool '{tool_name}' not implemented"
            }
    
    async def _lookup_menu_item(self, item_name: str) -> Dict[str, Any]:
        """
        Look up a specific menu item by name.
        
        Args:
            item_name: The name of the menu item to look up
            
        Returns:
            Details about the menu item if found
        """
        logger.info(f"Looking up menu item: {item_name}")
        
        # Use the async menu matcher to find the item
        async_matcher = await get_cached_async_menu_matcher(self.db)
        item_result, score = await async_matcher.match_item(item_name)
        menu_item = item_result
        
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
    
    async def _list_categories(self) -> Dict[str, List[str]]:
        """
        List all menu categories.
        
        Returns:
            List of menu categories
        """
        logger.info("Listing menu categories")
        
        # Get all categories from the menu store
        # Note: This uses synchronous API for now
        categories = menu_db_store.get_categories()
        
        # Return formatted categories
        return {
            "categories": [cat.get("name", "") for cat in categories]
        }
    
    async def _get_items_by_category(self, category_name: str) -> Dict[str, Any]:
        """
        Get all items in a specific category.
        
        Args:
            category_name: The name of the category
            
        Returns:
            List of items in the category
        """
        logger.info(f"Getting items for category: {category_name}")
        
        # Get all items in the category
        # Note: This uses synchronous API for now
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
    
    async def _get_restaurant_info(self, info_type: str) -> Dict[str, Any]:
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
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Get the tools supported by this agent.
        
        Returns:
            List[Dict[str, Any]]: List of tool definitions
        """
        return self.tools