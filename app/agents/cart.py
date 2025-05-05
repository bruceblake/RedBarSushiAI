"""
Cart Agent for RedBarSushiAI.
This module provides the cart specialist agent that handles order building.
"""

import os
import json
import logging
import time
from typing import Dict, List, Any, Optional, Union
from app.utils.agents_sdk import tool
from app.utils.agents_sdk import Tool

from app.agents.base import BaseAgent
from app.utils.menu_matcher_cache import cached_menu_matcher as menu_matcher
from app.utils.menu_db_store import menu_db_store
from app.utils.menu_cache_sdk import menu_cache
from app.utils.conversation_store_sdk import agents_conversation_store
from app.utils.agents_sdk import guardrail

logger = logging.getLogger(__name__)

class CartAgent(BaseAgent):
    """
    Cart Agent that handles building customer orders.
    Translates natural language into structured cart items and validates them.
    """
    
    def __init__(
        self,
        name: str = "Cart Agent",
        model: str = "gpt-4.1-mini",
        agent_id: Optional[str] = None
    ):
        """Initialize the Cart Agent."""
        
        instructions = """
        You are a cart-building specialist for Red Bar Sushi restaurant.
        Your primary responsibilities are:
        
        1. Convert customers' natural language orders into validated cart items
        2. Add items with their modifiers to the cart
        3. Maintain the cart state and calculate accurate prices
        4. Suggest add-ons and upsells when appropriate
        5. Help with removing or modifying items in the cart
        
        COMMUNICATION STYLE:
        - Be conversational but efficient
        - Confirm additions to the cart in a natural way
        - Suggest relevant modifiers or add-ons
        - Summarize the cart when appropriate
        
        IMPORTANT RULES:
        - ONLY add items that actually exist in our menu database
        - Verify all menu items using the lookup_menu_item tool before adding to cart
        - Track modifiers correctly with their parent items
        - Calculate accurate prices including modifiers
        - Ensure the total price never exceeds $300 without explicit confirmation
        - Handle quantity changes and item removals correctly
        
        CART BUILDING PROCESS:
        1. When a customer mentions an item, verify it exists using lookup_menu_item
        2. Add the item to the cart with add_item_to_cart
        3. If the customer mentions modifiers, verify and add them too
        4. Keep track of the current state with get_current_cart
        5. Allow modifications with modify_cart_item and remove_from_cart
        6. Always suggest relevant add-ons (drinks with food, etc.)
        
        You will receive natural language order requests and should convert them
        into structured cart items while maintaining an accurate representation
        of the customer's order.
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
                    "name": "add_item_to_cart",
                    "description": "Add an item to the customer's cart",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "plu": {
                                "type": "string",
                                "description": "The PLU code of the menu item"
                            },
                            "quantity": {
                                "type": "integer",
                                "description": "The quantity of this item"
                            },
                            "modifiers": {
                                "type": "array",
                                "description": "Optional list of modifiers to add to this item",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "plu": {
                                            "type": "string",
                                            "description": "The PLU code of the modifier"
                                        },
                                        "quantity": {
                                            "type": "integer",
                                            "description": "The quantity of this modifier"
                                        }
                                    },
                                    "required": ["plu", "quantity"]
                                }
                            },
                            "special_instructions": {
                                "type": "string",
                                "description": "Optional special instructions for this item"
                            }
                        },
                        "required": ["plu", "quantity"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "remove_from_cart",
                    "description": "Remove an item from the customer's cart",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_index": {
                                "type": "integer",
                                "description": "The index of the item to remove (0-based)"
                            }
                        },
                        "required": ["item_index"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "modify_cart_item",
                    "description": "Modify an item in the customer's cart",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_index": {
                                "type": "integer",
                                "description": "The index of the item to modify (0-based)"
                            },
                            "quantity": {
                                "type": "integer",
                                "description": "The new quantity of this item"
                            },
                            "add_modifiers": {
                                "type": "array",
                                "description": "Optional list of modifiers to add to this item",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "plu": {
                                            "type": "string",
                                            "description": "The PLU code of the modifier"
                                        },
                                        "quantity": {
                                            "type": "integer",
                                            "description": "The quantity of this modifier"
                                        }
                                    },
                                    "required": ["plu", "quantity"]
                                }
                            },
                            "remove_modifier_indices": {
                                "type": "array",
                                "description": "Optional list of modifier indices to remove (0-based)",
                                "items": {
                                    "type": "integer"
                                }
                            },
                            "special_instructions": {
                                "type": "string",
                                "description": "Optional new special instructions for this item"
                            }
                        },
                        "required": ["item_index"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_current_cart",
                    "description": "Get the current state of the customer's cart",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "suggest_additions",
                    "description": "Suggest items to add to the cart based on what's already there",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "suggestion_type": {
                                "type": "string",
                                "description": "The type of suggestion to make",
                                "enum": ["drinks", "sides", "desserts", "popular", "combos"]
                            }
                        },
                        "required": ["suggestion_type"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "clear_cart",
                    "description": "Clear the entire cart",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            }
        ]
        
        # Initialize the agent
        super().__init__(
            name=name,
            instructions=instructions,
            model=model,
            description="Cart specialist agent for Red Bar Sushi",
            tools=tools,
            agent_id=agent_id
        )
    
    @tool
    def lookup_menu_item(self, item_name: str) -> Dict[str, Any]:
        """
        Look up a menu item by name.
        
        Args:
            item_name: The name of the menu item to look up
            
        Returns:
            Details about the menu item if found
        """
        logger.info(f"Looking up menu item: {item_name}")
        
        # Use the cached menu matcher to find the item
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
                            "plu": modifier.get("plu", ""),
                            "price": mod_price_str,
                            "price_cents": mod_price or 0
                        })
                
                if mod_list:
                    modifiers.append({
                        "group_name": group.get("name", ""),
                        "min_selection": group.get("minAllowed", 0),
                        "max_selection": group.get("maxAllowed", 0),
                        "modifiers": mod_list
                    })
        
        # Return formatted item details
        return {
            "found": True,
            "name": menu_item.get("name", ""),
            "plu": menu_item.get("plu", ""),
            "price": price_str,
            "price_cents": price,
            "description": menu_item.get("description", ""),
            "category": menu_item.get("category", ""),
            "is_available": is_available,
            "modifiers": modifiers
        }
    
    @tool
    @guardrail(
        on="tool_response",
        check=lambda result, **_: result.get("total_price", 0) <= 30000,
        on_fail="retry",
        max_retries=2,
        message="Order total exceeds maximum allowable amount ($300)"
    )
    def add_item_to_cart(
        self, 
        plu: str, 
        quantity: int = 1, 
        modifiers: Optional[List[Dict[str, Any]]] = None, 
        special_instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add an item to the customer's cart.
        
        Args:
            plu: The PLU code of the menu item
            quantity: The quantity of this item
            modifiers: Optional list of modifiers to add
            special_instructions: Optional special instructions
            
        Returns:
            The updated cart
        """
        # Get the current call SID from context
        call_sid = self._get_current_call_sid()
        if not call_sid:
            logger.error("No call SID found in context")
            return {
                "success": False,
                "message": "Could not identify the current session",
                "total_price": 0,
                "items": []
            }
        
        logger.info(f"Adding item {plu} (qty: {quantity}) to cart for call {call_sid}")
        
        # Validate the item exists
        item = menu_db_store.get_item_by_plu(plu)
        if not item:
            logger.error(f"Item with PLU {plu} not found")
            return {
                "success": False,
                "message": f"Item with PLU {plu} not found",
                "total_price": 0,
                "items": []
            }
        
        # Validate modifiers if provided
        validated_modifiers = []
        if modifiers:
            for mod in modifiers:
                mod_plu = mod.get("plu")
                mod_quantity = mod.get("quantity", 1)
                
                # Validate the modifier exists
                modifier = menu_db_store.get_modifier_by_plu(mod_plu)
                if not modifier:
                    logger.warning(f"Modifier with PLU {mod_plu} not found")
                    continue
                
                # Add to validated modifiers
                validated_modifiers.append({
                    "plu": mod_plu,
                    "name": modifier.get("name", ""),
                    "quantity": mod_quantity,
                    "price_change": modifier.get("price", 0)
                })
        
        # Create the new item entry
        new_item = {
            "plu": plu,
            "name": item.get("name", ""),
            "price": item.get("price", 0),
            "quantity": quantity,
            "modifiers": validated_modifiers,
            "special_instructions": special_instructions
        }
        
        # Add to cart using the conversation store
        updated_cart = agents_conversation_store.add_to_cart(call_sid, new_item)
        
        # Format the response
        return {
            "success": True,
            "message": f"Added {quantity} {item.get('name')} to cart",
            "total_price": updated_cart.get("total_price", 0),
            "items": updated_cart.get("items", []),
            "item_count": len(updated_cart.get("items", []))
        }
    
    @tool
    def remove_from_cart(self, item_index: int) -> Dict[str, Any]:
        """
        Remove an item from the customer's cart.
        
        Args:
            item_index: The index of the item to remove (0-based)
            
        Returns:
            The updated cart
        """
        # Get the current call SID from context
        call_sid = self._get_current_call_sid()
        if not call_sid:
            logger.error("No call SID found in context")
            return {
                "success": False,
                "message": "Could not identify the current session",
                "total_price": 0,
                "items": []
            }
        
        logger.info(f"Removing item at index {item_index} from cart for call {call_sid}")
        
        # Get the current cart
        current_cart = agents_conversation_store.get_cart(call_sid)
        
        # Check if the index is valid
        if item_index < 0 or item_index >= len(current_cart.get("items", [])):
            logger.error(f"Invalid item index {item_index} for cart with {len(current_cart.get('items', []))} items")
            return {
                "success": False,
                "message": f"Invalid item index {item_index}",
                "total_price": current_cart.get("total_price", 0),
                "items": current_cart.get("items", [])
            }
        
        # Get the item being removed for the response message
        removed_item = current_cart.get("items", [])[item_index]
        removed_name = removed_item.get("name", "item")
        removed_quantity = removed_item.get("quantity", 1)
        
        # Remove the item
        updated_cart = agents_conversation_store.remove_from_cart(call_sid, item_index)
        
        # Format the response
        return {
            "success": True,
            "message": f"Removed {removed_quantity} {removed_name} from cart",
            "total_price": updated_cart.get("total_price", 0),
            "items": updated_cart.get("items", []),
            "item_count": len(updated_cart.get("items", []))
        }
    
    @tool
    @guardrail(
        on="tool_response",
        check=lambda result, **_: result.get("total_price", 0) <= 30000,
        on_fail="retry",
        max_retries=2,
        message="Order total exceeds maximum allowable amount ($300)"
    )
    def modify_cart_item(
        self,
        item_index: int,
        quantity: Optional[int] = None,
        add_modifiers: Optional[List[Dict[str, Any]]] = None,
        remove_modifier_indices: Optional[List[int]] = None,
        special_instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Modify an item in the customer's cart.
        
        Args:
            item_index: The index of the item to modify (0-based)
            quantity: Optional new quantity
            add_modifiers: Optional modifiers to add
            remove_modifier_indices: Optional modifier indices to remove
            special_instructions: Optional new special instructions
            
        Returns:
            The updated cart
        """
        # Get the current call SID from context
        call_sid = self._get_current_call_sid()
        if not call_sid:
            logger.error("No call SID found in context")
            return {
                "success": False,
                "message": "Could not identify the current session",
                "total_price": 0,
                "items": []
            }
        
        logger.info(f"Modifying item at index {item_index} in cart for call {call_sid}")
        
        # Get the current cart
        current_cart = agents_conversation_store.get_cart(call_sid)
        
        # Check if the index is valid
        if item_index < 0 or item_index >= len(current_cart.get("items", [])):
            logger.error(f"Invalid item index {item_index} for cart with {len(current_cart.get('items', []))} items")
            return {
                "success": False,
                "message": f"Invalid item index {item_index}",
                "total_price": current_cart.get("total_price", 0),
                "items": current_cart.get("items", [])
            }
        
        # Get the item to modify
        items = current_cart.get("items", [])
        item = items[item_index]
        
        # Update quantity if provided
        if quantity is not None:
            if quantity <= 0:
                # Remove the item if quantity is 0 or negative
                return self.remove_from_cart(item_index)
            
            item["quantity"] = quantity
        
        # Update special instructions if provided
        if special_instructions is not None:
            item["special_instructions"] = special_instructions
        
        # Remove modifiers if specified
        if remove_modifier_indices:
            # Sort indices in descending order to avoid index shifting
            for idx in sorted(remove_modifier_indices, reverse=True):
                if 0 <= idx < len(item.get("modifiers", [])):
                    item["modifiers"].pop(idx)
        
        # Add new modifiers if specified
        if add_modifiers:
            # Initialize modifiers list if not present
            if "modifiers" not in item:
                item["modifiers"] = []
            
            # Validate and add new modifiers
            for mod in add_modifiers:
                mod_plu = mod.get("plu")
                mod_quantity = mod.get("quantity", 1)
                
                # Validate the modifier exists
                modifier = menu_db_store.get_modifier_by_plu(mod_plu)
                if not modifier:
                    logger.warning(f"Modifier with PLU {mod_plu} not found")
                    continue
                
                # Add to modifiers
                item["modifiers"].append({
                    "plu": mod_plu,
                    "name": modifier.get("name", ""),
                    "quantity": mod_quantity,
                    "price_change": modifier.get("price", 0)
                })
        
        # Update the cart
        current_cart["items"][item_index] = item
        
        # Recalculate total price
        total_price = 0
        for cart_item in current_cart["items"]:
            # Get the item price and quantity
            item_price = cart_item.get("price", 0)
            item_quantity = cart_item.get("quantity", 1)
            
            # Add to total
            total_price += item_price * item_quantity
            
            # Add modifier prices
            for modifier in cart_item.get("modifiers", []):
                mod_price = modifier.get("price_change", 0)
                mod_quantity = modifier.get("quantity", 1)
                total_price += mod_price * mod_quantity
        
        # Update the total price
        current_cart["total_price"] = total_price
        
        # Save the updated cart
        agents_conversation_store.update_cart(call_sid, current_cart)
        
        # Format the response
        return {
            "success": True,
            "message": f"Modified {item.get('name')} in cart",
            "total_price": current_cart.get("total_price", 0),
            "items": current_cart.get("items", []),
            "item_count": len(current_cart.get("items", []))
        }
    
    @tool
    def get_current_cart(self) -> Dict[str, Any]:
        """
        Get the current state of the customer's cart.
        
        Returns:
            The current cart
        """
        # Get the current call SID from context
        call_sid = self._get_current_call_sid()
        if not call_sid:
            logger.error("No call SID found in context")
            return {
                "success": False,
                "message": "Could not identify the current session",
                "total_price": 0,
                "items": []
            }
        
        # Get the current cart
        current_cart = agents_conversation_store.get_cart(call_sid)
        
        # Calculate a formatted total price string
        total_price_cents = current_cart.get("total_price", 0)
        total_price_str = f"${total_price_cents/100:.2f}" if isinstance(total_price_cents, (int, float)) else "$0.00"
        
        # Format item details for better readability
        formatted_items = []
        for i, item in enumerate(current_cart.get("items", [])):
            price_cents = item.get("price", 0)
            price_str = f"${price_cents/100:.2f}" if isinstance(price_cents, (int, float)) else "$0.00"
            
            formatted_modifiers = []
            for modifier in item.get("modifiers", []):
                mod_price = modifier.get("price_change", 0)
                mod_price_str = f"${mod_price/100:.2f}" if mod_price else ""
                
                formatted_modifiers.append({
                    "name": modifier.get("name", ""),
                    "quantity": modifier.get("quantity", 1),
                    "price": mod_price_str
                })
            
            formatted_items.append({
                "index": i,
                "name": item.get("name", ""),
                "quantity": item.get("quantity", 1),
                "price": price_str,
                "modifiers": formatted_modifiers,
                "special_instructions": item.get("special_instructions")
            })
        
        # Return the formatted cart
        return {
            "success": True,
            "item_count": len(current_cart.get("items", [])),
            "total_price": current_cart.get("total_price", 0),
            "formatted_total": total_price_str,
            "items": formatted_items
        }
    
    @tool
    def suggest_additions(self, suggestion_type: str) -> Dict[str, Any]:
        """
        Suggest items to add to the cart based on what's already there.
        
        Args:
            suggestion_type: The type of suggestion to make
            
        Returns:
            List of suggested items
        """
        # Get the current call SID from context
        call_sid = self._get_current_call_sid()
        if not call_sid:
            logger.error("No call SID found in context")
            return {
                "success": False,
                "message": "Could not identify the current session",
                "suggestions": []
            }
        
        # Get the current cart
        current_cart = agents_conversation_store.get_cart(call_sid)
        
        # Get categories based on suggestion type
        category_map = {
            "drinks": ["Beverages", "Drinks", "Sodas"],
            "sides": ["Sides", "Appetizers"],
            "desserts": ["Desserts", "Sweets"],
            "popular": ["Popular", "Specials", "Featured"],
            "combos": ["Combos", "Sets", "Specials"]
        }
        
        categories = category_map.get(suggestion_type, ["Popular"])
        
        # Get suggested items from these categories
        suggested_items = []
        
        # Check what categories are already in the cart
        cart_categories = set()
        for item in current_cart.get("items", []):
            # Get the item by PLU to find its category
            db_item = menu_db_store.get_item_by_plu(item.get("plu", ""))
            if db_item:
                cart_categories.add(db_item.get("category", ""))
        
        # Get items from related categories
        for category in categories:
            items = menu_db_store.get_items_by_category(category)
            # Only add available items
            for item in items:
                if item.get("available", True) and not item.get("snoozed", False):
                    # Format price
                    price = item.get("price", 0)
                    price_str = f"${price/100:.2f}" if isinstance(price, (int, float)) else "Price unavailable"
                    
                    suggested_items.append({
                        "name": item.get("name", ""),
                        "plu": item.get("plu", ""),
                        "price": price_str,
                        "price_cents": price,
                        "description": item.get("description", ""),
                        "category": item.get("category", "")
                    })
        
        # Limit to 5 suggestions
        suggested_items = suggested_items[:5]
        
        return {
            "success": True,
            "suggestion_type": suggestion_type,
            "suggestions": suggested_items
        }
    
    @tool
    def clear_cart(self) -> Dict[str, Any]:
        """
        Clear the entire cart.
        
        Returns:
            Success message
        """
        # Get the current call SID from context
        call_sid = self._get_current_call_sid()
        if not call_sid:
            logger.error("No call SID found in context")
            return {
                "success": False,
                "message": "Could not identify the current session"
            }
        
        # Clear the cart
        success = agents_conversation_store.clear_cart(call_sid)
        
        if success:
            return {
                "success": True,
                "message": "Cart cleared successfully",
                "total_price": 0,
                "items": []
            }
        else:
            return {
                "success": False,
                "message": "Failed to clear cart"
            }
    
    def _get_current_call_sid(self) -> Optional[str]:
        """
        Get the current call SID from context.
        In a real implementation, this would be passed from the voice controller.
        
        Returns:
            The call SID if available, None otherwise
        """
        # This is a placeholder that will be replaced with actual implementation
        # when integrating with the voice controller
        return getattr(self, "current_call_sid", None)
    
    def set_current_call(self, call_sid: str):
        """
        Set the current call SID for context.
        
        Args:
            call_sid: The Twilio call SID
        """
        self.current_call_sid = call_sid
    
    def process_order_request(self, call_sid: str, order_text: str) -> Dict[str, Any]:
        """
        Process an order request from a customer.
        
        Args:
            call_sid: The Twilio call SID
            order_text: The natural language order text
            
        Returns:
            The processing result including the updated cart
        """
        # Set the current call for context
        self.set_current_call(call_sid)
        
        # Process the message with the agent
        start_time = time.time()
        response = self.process_message(call_sid, order_text)
        duration = time.time() - start_time
        
        logger.info(f"Processed order request in {duration:.2f}s: {order_text}")
        
        # Get the current cart after processing
        cart = agents_conversation_store.get_cart(call_sid)
        
        # Return the result
        return {
            "success": True,
            "response": response,
            "processing_time": duration,
            "cart": cart
        }