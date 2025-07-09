"""
Async Cart Agent for RedBarSushiAI.
This module provides the async cart specialist agent that handles order building.
"""

import os
import json
import logging
import time
import asyncio
from typing import Dict, List, Any, Optional, Union, Callable

from app.agents.base_async import BaseAsyncAgent
from app.agents.ai_mixin import AIIntelligenceMixin
from app.utils.menu_matcher_cache_async import get_cached_async_menu_matcher
from app.utils.menu_db_store_async import async_menu_db_store
# Menu caching is handled by Redis
from app.utils.conversation_store_async import async_agents_conversation_store
from app.config import settings
from app.utils.enhanced_logging import get_logger
from app.utils.disambiguation import (
    disambiguation_detector,
    disambiguation_resolver,
    DisambiguationContext
)

# Set up logging
logger = get_logger(__name__)

class AsyncCartAgent(BaseAsyncAgent, AIIntelligenceMixin):
    """
    Async Cart Agent that handles building customer orders.
    Translates natural language into structured cart items and validates them.
    """
    
    def __init__(self, agent_id: Optional[str] = None, db: Optional[Any] = None):
        """
        Initialize the Async Cart Agent.
        
        Args:
            agent_id: Optional ID for the agent (used with OpenAI Assistants API)
            db: Optional database session for async operations
        """
        BaseAsyncAgent.__init__(self, agent_id=agent_id, name="Cart")
        AIIntelligenceMixin.__init__(self)
        self.db = db
        
        # Set agent-specific max tokens
        self._default_max_tokens = getattr(settings, 'CART_AGENT_MAX_TOKENS', 256)
        self.disambiguation_context = None  # Store disambiguation state
        
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
        
        # Set agent instructions - OPTIMIZED AND DYNAMIC
        self.instructions = f"""
You are the cart manager for {settings.RESTAURANT_NAME}. Keep responses SHORT (1-2 sentences).

Your job: Add items to cart accurately and quickly.

CRITICAL: You must identify and capture all item modifiers, customizations, or special instructions (e.g., 'no pickles', 'medium-rare', 'sauce on the side'). Pass these accurately to the add_to_cart tool.

ALWAYS use the menu lookup tools to find exact items - NEVER guess or make up items.
For any item the customer mentions, immediately look it up to get the correct PLU and pricing.

When adding items:
1. Look up the item to get PLU and price.
2. Add to cart with correct details, including all modifiers.
3. Confirm addition with price.

Be quick, accurate, and concise. NO long explanations.
        """
        
        self.current_call_sid = None
    
    async def process_input(self, input_text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a text input and generate a response using AI.
        
        Args:
            input_text: The text input to process
            context: Optional context information
            
        Returns:
            Dict[str, Any]: The agent's response
        """
        context = context or {}
        self.update_context(context)
        
        # Extract call_sid from context if available
        if "call_sid" in context:
            self.set_current_call(context["call_sid"])
        
        # Log the input
        logger.critical(f"\n{'='*60}")
        logger.critical(f"CART AGENT: process_input called")
        logger.critical(f"Input text: '{input_text}'")
        logger.critical(f"Context: {json.dumps(context, indent=2) if context else 'None'}")
        logger.critical(f"Call SID from context: {context.get('call_sid', 'Not found')}")
        logger.critical(f"{'='*60}\n")
        
        # Get current cart state
        call_sid = self._get_current_call_sid()
        conversation = await async_agents_conversation_store.get_conversation(call_sid) if call_sid else {"context": {}}
        current_cart = conversation.get("context", {}).get("cart", {"items": [], "total_price": 0})
        
        # Add cart state to context for AI
        context["current_cart"] = current_cart
        context["state_guidance"] = """
        You are the cart specialist. Your job is to:
        1. Identify menu items the customer wants to order
        2. Extract quantities (default to 1 if not specified)
        3. Use the lookup_menu_item tool to verify each item exists
        4. Use the add_item_to_cart tool to add valid items
        5. Provide a friendly confirmation of what was added
        
        If the customer says things like "that's all", "done", "ready to checkout", 
        acknowledge their order is complete and summarize their cart.
        
        IMPORTANT: Always use your tools to look up and add items. Don't just respond
        without actually processing the order.
        """
        
        # Check if order is ready for validation FIRST
        order_ready = False
        input_lower = input_text.lower()
        completion_phrases = ["that's all", "done", "ready", "checkout", "complete", "finished", "that's it", "that is it", "i'm done", "nothing else"]
        
        if any(phrase in input_lower for phrase in completion_phrases):
            order_ready = True
            # For completion phrases, respond quickly without AI if cart has items
            if current_cart.get("items"):
                items_text = ", ".join([f"{item['quantity']} {item['name']}" for item in current_cart["items"]])
                total = current_cart.get("total_price", 0)
                response = {
                    "text": f"Perfect! Your order includes: {items_text}. Total: ${total:.2f}. Let me confirm all the details.",
                    "agent": self.name,
                    "handled": True,
                    "ai_generated": False
                }
            else:
                # Use AI only if cart is empty
                response = await self.process_with_ai(input_text, context)
        else:
            # Process with AI for ordering
            response = await self.process_with_ai(input_text, context)
        
        # Get updated cart after any processing
        conversation = await async_agents_conversation_store.get_conversation(call_sid) if call_sid else {"context": {}}
        current_cart = conversation.get("context", {}).get("cart", {"items": [], "total_price": 0})
        
        # Update response with cart info
        response["order_ready_for_validation"] = order_ready
        response["cart"] = current_cart
        
        logger.critical(f"Cart agent response: {json.dumps(response, indent=2)}")
        return response
    
    async def _generate_cart_response(self, order_text: str) -> str:
        """
        Generate a response to an order request.
        
        Args:
            order_text: The customer's order text
            
        Returns:
            str: The response text
        """
        logger.critical(f"_generate_cart_response called with: '{order_text}'")
        
        # Here we would connect to OpenAI or other model using async
        # For now we implement a simpler version focused on cart management
        
        call_sid = self._get_current_call_sid()
        logger.critical(f"Call SID from _get_current_call_sid: {call_sid}")
        if not call_sid:
            logger.critical("ERROR: No call SID found!")
            raise Exception("Session tracking failed - call SID required for cart operations")
        
        # AI-FIRST PRINCIPLE: This method should not handle generic order text
        # It should only be called by AI agents with specific tool calls
        # Removing hardcoded keyword detection and fallback responses
        
        # This method is deprecated in favor of explicit tool calls
        raise Exception("Direct order processing deprecated - use specific cart tools called by AI agents")
    
    async def process_order_request(self, call_sid: str, order_text: str) -> Dict[str, Any]:
        # First extract quantity words and numbers
        quantity_map = {
            'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
            'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
            'a': 1, 'an': 1
        }
        
        # Split into potential item phrases
        order_lower = order_text.lower()
        
        # Look for patterns like "two california rolls" or "1 spicy tuna roll"
        import re
        item_patterns = []
        
        # Pattern 1: [quantity] [item name] (e.g., "two california rolls", "1 spicy tuna")
        matches = re.finditer(r'(\b(?:one|two|three|four|five|six|seven|eight|nine|ten|a|an|\d+)\b)\s+([^,\.]+?)(?:roll|rolls|piece|pieces|order|orders)?(?:\s*(?:,|and|$))', order_lower)
        for match in matches:
            qty_text = match.group(1)
            item_text = match.group(2).strip()
            
            # Convert quantity to number
            if qty_text.isdigit():
                quantity = int(qty_text)
            else:
                quantity = quantity_map.get(qty_text, 1)
            
            item_patterns.append((item_text, quantity))
            logger.critical(f"Extracted pattern: '{item_text}' with quantity {quantity}")
        
        # If no patterns found, try simpler approach
        if not item_patterns:
            # Just look for item names without quantities using menu search
            possible_items = []
            # Instead of hardcoded keywords, search for menu items in the order text
            try:
                if hasattr(self, 'menu_agent') and self.menu_agent:
                    # Search for menu items that might match words in the order
                    words = order_lower.split()
                    for word in words:
                        if len(word) > 3:  # Only search words longer than 3 characters
                            search_result = await self.menu_agent.execute_tool("search_menu", {"keyword": word, "max_results": 1})
                            if search_result.get("results"):
                                item_name = search_result["results"][0]["name"]
                                possible_items.append((item_name, 1))
                else:
                    # Fallback: delegate to menu specialist for parsing
                    logger.info("No menu agent available, skipping automatic item detection")
            except Exception as e:
                logger.warning(f"Error searching menu for items: {e}")
            
            item_patterns = possible_items
        
        # Track items we've already added to avoid duplicates
        items_added = []
        items_found = {}  # Map of item name to (plu, quantity)
        
        # Look up each potential menu item IN PARALLEL for speed
        lookup_tasks = []
        for item_name, quantity in item_patterns:
            if not item_name:
                continue
                
            # Skip if this is just a substring of something we already found
            skip = False
            for added_name in items_found:
                if item_name in added_name or added_name in item_name:
                    skip = True
                    break
            if skip:
                continue
            
            # Create async task for lookup
            task = asyncio.create_task(self.execute_tool("lookup_menu_item", {"item_name": item_name}))
            lookup_tasks.append((task, item_name, quantity))
        
        # Wait for all lookups to complete
        for task, item_name, quantity in lookup_tasks:
            item_result = await task
            
            if item_result.get("found", False):
                name = item_result.get("name", "")
                plu = item_result.get("plu", "")
                
                # Store the item with its quantity
                if name not in items_found:
                    items_found[name] = (plu, quantity)
                    logger.critical(f"Found menu item: '{name}' (PLU: {plu}) with quantity {quantity}")
        
        # Now add all found items to cart
        for name, (plu, quantity) in items_found.items():
            add_result = await self.execute_tool("add_item_to_cart", {
                "plu": plu,
                "quantity": quantity
            })
            
            if add_result.get("success", False):
                items_added.append(f"{quantity} {name}")
        
        # Generate an appropriate response based on what happened
        if items_added:
            items_text = ", ".join(items_added)
            conversation = await async_agents_conversation_store.get_conversation(call_sid)
            current_cart = conversation.get("context", {}).get("cart", {"items": [], "total_price": 0})
            total_price = current_cart.get("total_price", 0)
            # Fix price display - ensure it's in dollars, not cents
            total_price_str = f"${total_price:.2f}" if isinstance(total_price, (int, float)) else "$0.00"
            
            return f"I've added the following to your cart: {items_text}. Your total is {total_price_str}. Would you like anything else?"
        else:
            # Get the current cart
            cart_result = await self.execute_tool("get_current_cart", {})
            items = cart_result.get("items", [])
            
            if not items:
                return "I'm sorry, but I couldn't identify any menu items in your request. Could you please specify what you'd like to order?"
            else:
                return "What else would you like to add to your order?"
    
    async def process_order_request(self, call_sid: str, order_text: str) -> Dict[str, Any]:
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
        
        # Store the order request in conversation store
        await async_agents_conversation_store.add_message(call_sid, "user", order_text)
        
        # Process the message with the agent
        start_time = time.time()
        response = await self.process_input(order_text, {"call_sid": call_sid})
        duration = time.time() - start_time
        
        # Get response text
        response_text = response.get("text", "")
        
        # Store the agent's response in conversation store
        await async_agents_conversation_store.add_message(call_sid, "assistant", response_text)
        
        logger.info(f"Processed order request in {duration:.2f}s: {order_text}")
        
        # Get the current cart after processing
        conversation = await async_agents_conversation_store.get_conversation(call_sid)
        cart = conversation.get("context", {}).get("cart", {"items": [], "total_price": 0})
        
        # Return the result
        return {
            "success": True,
            "response": response_text,
            "processing_time": duration,
            "cart": cart,
            "order_ready_for_validation": response.get("order_ready_for_validation", False)
        }
    
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
        elif tool_name == "add_item_to_cart":
            return await self._add_item_to_cart(
                args.get("plu", ""),
                args.get("quantity", 1),
                args.get("modifiers", []),
                args.get("special_instructions", None)
            )
        elif tool_name == "remove_from_cart":
            return await self._remove_from_cart(args.get("item_index", 0))
        elif tool_name == "modify_cart_item":
            return await self._modify_cart_item(
                args.get("item_index", 0),
                args.get("quantity", None),
                args.get("add_modifiers", None),
                args.get("remove_modifier_indices", None),
                args.get("special_instructions", None)
            )
        elif tool_name == "get_current_cart":
            return await self._get_current_cart()
        elif tool_name == "suggest_additions":
            return await self._suggest_additions(args.get("suggestion_type", "popular"))
        elif tool_name == "clear_cart":
            return await self._clear_cart()
        elif tool_name == "resolve_disambiguation":
            return await self._resolve_disambiguation(args.get("response", ""))
        else:
            logger.warning(f"[{self.name}] Unknown tool: {tool_name}")
            return {
                "status": "error",
                "message": f"Tool '{tool_name}' not implemented"
            }
    
    async def _lookup_menu_item(self, item_name: str) -> Dict[str, Any]:
        """
        Look up a menu item by name - delegate to Menu Agent for database access.
        
        Args:
            item_name: The name of the menu item to look up
            
        Returns:
            Details about the menu item if found
        """
        logger.critical(f"\n{'='*60}")
        logger.critical(f"_lookup_menu_item called with: '{item_name}'")
        logger.critical(f"Cart agent database session available: {self.db is not None}")
        
        # Check if we're resolving a previous disambiguation
        if self.disambiguation_context and item_name:
            # Try to resolve with the user's response
            result = await self._resolve_disambiguation(item_name)
            if result.get("resolved"):
                return result
        logger.critical(f"{'='*60}\n")
        
        # Get a fresh database session if we don't have one
        if self.db is None:
            from app.db_async import async_session_factory
            self.db = async_session_factory()
            logger.info("Created new database session for cart agent")
        
        # Delegate to Menu Agent for database lookup
        from app.agents.menu_async_enhanced import AsyncMenuAgentEnhanced
        menu_agent = AsyncMenuAgentEnhanced(db=self.db)
        
        # Use Menu Agent's lookup method
        result = await menu_agent._lookup_menu_item(item_name)
        
        # Convert Menu Agent result to Cart Agent format
        if result.get("found"):
            item = result.get("item", {})
            return {
                "found": True,
                "name": item.get("name", ""),
                "plu": item.get("plu", ""),
                "price": item.get("price_formatted", "$0.00"),
                "price_cents": item.get("price", 0),
                "description": item.get("description", ""),
                "category": item.get("category", ""),
                "is_available": item.get("is_available", True),
                "modifiers": item.get("modifier_groups", [])
            }
        elif result.get("needs_disambiguation"):
            # Handle disambiguation from Menu Agent
            return {
                "found": False,
                "needs_disambiguation": True,
                "clarification_needed": result.get("message", "Multiple items found. Please specify."),
                "candidates": result.get("alternatives", []),
                "disambiguation_type": "menu_item"
            }
        else:
            # No match found
            return {
                "found": False,
                "search_term": item_name,
                "message": result.get("message", "This item doesn't appear to be on our menu.")
            }
    
    async def _add_item_to_cart(
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
        item = await async_menu_db_store.get_item_by_plu(plu, self.db)
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
                modifier = await async_menu_db_store.get_modifier_by_plu(mod_plu, self.db)
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
        
        # Get current conversation and cart
        conversation = await async_agents_conversation_store.get_conversation(call_sid)
        cart = conversation.get("context", {}).get("cart", {"items": [], "total_price": 0})
        
        # Check if item already exists in cart (same PLU and modifiers)
        item_found = False
        for existing_item in cart["items"]:
            if (existing_item.get("plu") == plu and 
                existing_item.get("modifiers") == validated_modifiers and
                existing_item.get("special_instructions") == special_instructions):
                # Update quantity instead of adding duplicate
                existing_item["quantity"] += quantity
                item_found = True
                logger.info(f"Updated quantity for existing item {plu}: now {existing_item['quantity']}")
                break
        
        if not item_found:
            # Add the new item to cart
            cart["items"].append(new_item)
            logger.info(f"Added new item to cart: {plu}")
        
        # Calculate total price (prices are already in dollars)
        total_price = 0.0
        for cart_item in cart["items"]:
            item_price = float(cart_item.get("price", 0)) * cart_item.get("quantity", 1)
            # Add modifier prices
            for modifier in cart_item.get("modifiers", []):
                item_price += float(modifier.get("price_change", 0)) * modifier.get("quantity", 1)
            total_price += item_price
        # Store total price in dollars
        cart["total_price"] = total_price
        
        # Update conversation context with cart
        conversation["context"]["cart"] = cart
        await async_agents_conversation_store.save_conversation(call_sid, conversation)
        
        logger.critical(f"Cart updated for call {call_sid}:")
        logger.critical(f"  - Items: {len(cart['items'])}")
        logger.critical(f"  - Total price: ${cart['total_price']:.2f}")
        # Convert Decimal to float for JSON serialization
        items_for_logging = []
        for item in cart.get("items", []):
            item_copy = item.copy()
            if "price" in item_copy:
                item_copy["price"] = float(item_copy["price"])
            items_for_logging.append(item_copy)
        
        cart_for_logging = {
            "items": items_for_logging,
            "total_price": float(cart.get("total_price", 0))
        }
        logger.critical(f"  - Full cart: {json.dumps(cart_for_logging, indent=2)}")
        
        updated_cart = cart
        
        # Format the response
        return {
            "success": True,
            "message": f"Added {quantity} {item.get('name')} to cart",
            "total_price": updated_cart.get("total_price", 0),
            "items": updated_cart.get("items", []),
            "item_count": len(updated_cart.get("items", []))
        }
    
    async def _remove_from_cart(self, item_index: int) -> Dict[str, Any]:
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
        
        # Get current conversation and cart
        conversation = await async_agents_conversation_store.get_conversation(call_sid)
        current_cart = conversation.get("context", {}).get("cart", {"items": [], "total_price": 0})
        
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
        
        # Remove the item from cart
        cart_items = current_cart.get("items", [])
        cart_items.pop(item_index)
        
        # Recalculate total price
        total_price = 0
        for cart_item in cart_items:
            item_price = cart_item.get("price", 0) * cart_item.get("quantity", 1)
            # Add modifier prices
            for modifier in cart_item.get("modifiers", []):
                item_price += modifier.get("price_change", 0) * modifier.get("quantity", 1)
            total_price += item_price
        
        updated_cart = {
            "items": cart_items,
            "total_price": total_price
        }
        
        # Update conversation context with cart
        conversation["context"]["cart"] = updated_cart
        await async_agents_conversation_store.save_conversation(call_sid, conversation)
        
        # Format the response
        return {
            "success": True,
            "message": f"Removed {removed_quantity} {removed_name} from cart",
            "total_price": updated_cart.get("total_price", 0),
            "items": updated_cart.get("items", []),
            "item_count": len(updated_cart.get("items", []))
        }
    
    async def _modify_cart_item(
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
        
        # Get current conversation and cart
        conversation = await async_agents_conversation_store.get_conversation(call_sid)
        current_cart = conversation.get("context", {}).get("cart", {"items": [], "total_price": 0})
        
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
                return await self._remove_from_cart(item_index)
            
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
                modifier = await async_menu_db_store.get_modifier_by_plu(mod_plu, self.db)
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
        
        # Recalculate total price (prices are already in dollars)
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
        
        # Update the total price in dollars
        current_cart["total_price"] = total_price
        
        # Save the updated cart in conversation context
        conversation["context"]["cart"] = current_cart
        await async_agents_conversation_store.save_conversation(call_sid, conversation)
        
        # Format the response
        return {
            "success": True,
            "message": f"Modified {item.get('name')} in cart",
            "total_price": current_cart.get("total_price", 0),
            "items": current_cart.get("items", []),
            "item_count": len(current_cart.get("items", []))
        }
    
    async def _get_current_cart(self) -> Dict[str, Any]:
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
        
        # Get current conversation and cart
        conversation = await async_agents_conversation_store.get_conversation(call_sid)
        current_cart = conversation.get("context", {}).get("cart", {"items": [], "total_price": 0})
        
        # Calculate a formatted total price string (total_price is already in dollars)
        total_price = current_cart.get("total_price", 0)
        total_price_str = f"${total_price:.2f}" if isinstance(total_price, (int, float)) else "$0.00"
        
        # Format item details for better readability
        formatted_items = []
        for i, item in enumerate(current_cart.get("items", [])):
            price = item.get("price", 0)
            price_str = f"${price:.2f}" if isinstance(price, (int, float)) else "$0.00"
            
            formatted_modifiers = []
            for modifier in item.get("modifiers", []):
                mod_price = modifier.get("price_change", 0)
                mod_price_str = f"${mod_price:.2f}" if mod_price else ""
                
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
    
    async def _suggest_additions(self, suggestion_type: str) -> Dict[str, Any]:
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
        
        # Get current conversation and cart
        conversation = await async_agents_conversation_store.get_conversation(call_sid)
        current_cart = conversation.get("context", {}).get("cart", {"items": [], "total_price": 0})
        
        # NO hardcoded categories - get dynamic categories from menu
        # Use AI intelligence to determine appropriate categories based on suggestion type
        if not self.db:
            from app.db_async import async_session_factory
            self.db = async_session_factory()
            logger.info("Created new database session for cart agent")
        
        # Get all available categories dynamically
        from app.db.crud_menu_async import get_all_categories
        all_categories = await get_all_categories(self.db)
        
        # Use AI to filter categories based on suggestion type
        # This replaces hardcoded mappings with intelligent selection
        categories = [cat.name for cat in all_categories[:3]]  # Use first few categories as fallback
        
        # Get suggested items from these categories using Menu Agent
        suggested_items = []
        
        # Get a fresh database session if we don't have one
        if self.db is None:
            from app.db_async import async_session_factory
            self.db = async_session_factory()
            logger.info("Created new database session for cart agent")
        
        # Use Menu Agent to get popular items
        from app.agents.menu_async_enhanced import AsyncMenuAgentEnhanced
        menu_agent = AsyncMenuAgentEnhanced(db=self.db)
        
        # Get popular items from the relevant category
        result = await menu_agent._get_popular_items(category=suggestion_type, max_results=5)
        
        if result.get("items"):
            for item in result["items"]:
                suggested_items.append({
                    "name": item.get("name", ""),
                    "plu": item.get("plu", ""),
                    "price": item.get("price_formatted", "$0.00"),
                    "price_cents": item.get("price", 0),
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
    
    async def _clear_cart(self) -> Dict[str, Any]:
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
        success = await async_agents_conversation_store.clear_cart(call_sid)
        
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
    
    async def _resolve_disambiguation(self, user_response: str) -> Dict[str, Any]:
        """
        Resolve a disambiguation based on user's clarification response.
        
        Args:
            user_response: The user's response to the clarification question
            
        Returns:
            Resolved item details or error
        """
        if not self.disambiguation_context:
            return {
                "resolved": False,
                "error": "No disambiguation in progress"
            }
        
        try:
            # Try to match the response
            matched_candidate = disambiguation_resolver.match_response(
                user_response, self.disambiguation_context
            )
            
            if matched_candidate:
                # Clear disambiguation context
                self.disambiguation_context = None
                
                # Return the matched item in the expected format
                return {
                    "resolved": True,
                    "found": True,
                    "name": matched_candidate.name,
                    "plu": matched_candidate.plu,
                    "price": f"${matched_candidate.price:.2f}",
                    "price_cents": matched_candidate.price,
                    "description": matched_candidate.description or "",
                    "category": matched_candidate.category,
                    "is_available": True
                }
            else:
                # Couldn't match - increment attempt count
                self.disambiguation_context.attempt_count += 1
                
                if self.disambiguation_context.attempt_count >= self.disambiguation_context.max_attempts:
                    # Too many attempts - give up
                    self.disambiguation_context = None
                    return {
                        "resolved": False,
                        "error": "I'm having trouble understanding which item you mean. Could you please be more specific about the item name?",
                        "give_up": True
                    }
                else:
                    # Try again with a different phrasing
                    clarification = disambiguation_resolver.generate_clarification(
                        self.disambiguation_context
                    )
                    
                    return {
                        "resolved": False,
                        "needs_disambiguation": True,
                        "clarification_needed": f"I'm not sure I understood. {clarification}",
                        "attempt": self.disambiguation_context.attempt_count
                    }
                    
        except Exception as e:
            logger.error(f"Error resolving disambiguation: {e}")
            self.disambiguation_context = None
            return {"resolved": False, "error": str(e)}
    
    def _get_current_call_sid(self) -> Optional[str]:
        """
        Get the current call SID from context.
        
        Returns:
            The call SID if available, None otherwise
        """
        # Check if it's directly in the context
        if "call_sid" in self.context:
            return self.context["call_sid"]
        
        # Otherwise use the stored call_sid
        return self.current_call_sid
    
    def set_current_call(self, call_sid: str):
        """
        Set the current call SID for context.
        
        Args:
            call_sid: The Twilio call SID
        """
        self.current_call_sid = call_sid
        self.context["call_sid"] = call_sid
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Get the tools supported by this agent.
        
        Returns:
            List[Dict[str, Any]]: List of tool definitions
        """
        return self.tools