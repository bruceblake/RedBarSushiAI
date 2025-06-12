"""
Async Cart Agent for RedBarSushiAI.
This module provides the async cart specialist agent that handles order building.
"""

import logging
import time
from typing import Dict, List, Any, Optional  # Callable removed

from app.agents.base_async import BaseAsyncAgent
from app.utils.menu_matcher_cache_async import get_cached_async_menu_matcher
from app.utils.menu_db_store_async import async_menu_db_store

# Menu caching is handled by Redis
from app.utils.conversation_store_async import async_agents_conversation_store
from app.db.crud_menu_async import (
    get_item_by_plu,
    get_modifier_by_plu,
    get_items_by_category as get_items_by_category_crud, # Alias to avoid conflict if method name is same
    get_category # Import get_category to find category_id by name for _suggest_additions
)


# Set up logging
logger = logging.getLogger(__name__)


class AsyncCartAgent(BaseAsyncAgent):
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
        super().__init__(agent_id=agent_id, name="Cart")
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
                                "description": "The name of the menu item to look up",
                            }
                        },
                        "required": ["item_name"],
                    },
                },
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
                                "description": "The PLU code of the menu item",
                            },
                            "quantity": {
                                "type": "integer",
                                "description": "The quantity of this item",
                            },
                            "modifiers": {
                                "type": "array",
                                "description": "Optional list of modifiers to add to this item",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "plu": {
                                            "type": "string",
                                            "description": "The PLU code of the modifier",
                                        },
                                        "quantity": {
                                            "type": "integer",
                                            "description": "The quantity of this modifier",
                                        },
                                    },
                                    "required": ["plu", "quantity"],
                                },
                            },
                            "special_instructions": {
                                "type": "string",
                                "description": "Optional special instructions for this item",
                            },
                        },
                        "required": ["plu", "quantity"],
                    },
                },
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
                                "description": "The index of the item to remove (0-based)",
                            }
                        },
                        "required": ["item_index"],
                    },
                },
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
                                "description": "The index of the item to modify (0-based)",
                            },
                            "quantity": {
                                "type": "integer",
                                "description": "The new quantity of this item",
                            },
                            "add_modifiers": {
                                "type": "array",
                                "description": "Optional list of modifiers to add to this item",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "plu": {
                                            "type": "string",
                                            "description": "The PLU code of the modifier",
                                        },
                                        "quantity": {
                                            "type": "integer",
                                            "description": "The quantity of this modifier",
                                        },
                                    },
                                    "required": ["plu", "quantity"],
                                },
                            },
                            "remove_modifier_indices": {
                                "type": "array",
                                "description": "Optional list of modifier indices to remove (0-based)",
                                "items": {"type": "integer"},
                            },
                            "special_instructions": {
                                "type": "string",
                                "description": "Optional new special instructions for this item",
                            },
                        },
                        "required": ["item_index"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_current_cart",
                    "description": "Get the current state of the customer's cart",
                    "parameters": {"type": "object", "properties": {}},
                },
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
                                "enum": [
                                    "drinks",
                                    "sides",
                                    "desserts",
                                    "popular",
                                    "combos",
                                ],
                            }
                        },
                        "required": ["suggestion_type"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "clear_cart",
                    "description": "Clear the entire cart",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
        ]

        # Set agent instructions
        self.instructions = """
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

        self.current_call_sid = None

    async def process_input(
        self, input_text: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
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

        # Extract call_sid from context if available
        if "call_sid" in context:
            self.set_current_call(context["call_sid"])

        # Log the input
        logger.info(f"[{self.name}] Processing order text: {input_text}")

        # Process the order text
        response_text = await self._generate_cart_response(input_text)

        # Check if order is ready for validation
        order_ready = False
        if (
            "ready" in input_text.lower()
            or "checkout" in input_text.lower()
            or "done" in input_text.lower()
        ):
            order_ready = True

        # Get the current cart
        call_sid = self._get_current_call_sid()
        current_cart = (
            await async_agents_conversation_store.get_cart(call_sid)
            if call_sid
            else {"items": [], "total_price": 0}
        )

        # Check if cart has items (another indicator that order might be ready)
        if len(current_cart.get("items", [])) > 0 and (
            "that's it" in input_text.lower() or "that is it" in input_text.lower()
        ):
            order_ready = True

        # Format the response
        response = {
            "text": response_text,
            "agent": self.name,
            "handled": True,
            "actions": [],
            "order_ready_for_validation": order_ready,
        }

        # Include the cart information
        response["cart"] = current_cart

        return response

    async def _generate_cart_response(self, order_text: str) -> str:
        """
        Generate a response to an order request.

        Args:
            order_text: The customer's order text

        Returns:
            str: The response text
        """
        # Here we would connect to OpenAI or other model using async
        # For now we implement a simpler version focused on cart management

        call_sid = self._get_current_call_sid()
        if not call_sid:
            return "I'm sorry, but I'm having trouble tracking your order session. Could you please try again?"

        # Check if it's a clear cart request
        if "clear" in order_text.lower() and (
            "cart" in order_text.lower() or "order" in order_text.lower()
        ):
            await self.execute_tool("clear_cart", {})
            return "I've cleared your cart. What would you like to order?"

        # Check if it's a get cart request
        if ("what" in order_text.lower() or "show" in order_text.lower()) and (
            "cart" in order_text.lower() or "order" in order_text.lower()
        ):
            cart_result = await self.execute_tool("get_current_cart", {})
            items = cart_result.get("items", [])
            total = cart_result.get("formatted_total", "$0.00")

            if not items:
                return "Your cart is empty. What would you like to order?"

            cart_summary = "Here's what you have so far: "
            for item in items:
                name = item.get("name", "")
                qty = item.get("quantity", 1)
                cart_summary += f"{qty} {name}, "

            cart_summary = cart_summary[:-2]  # Remove trailing comma and space
            cart_summary += (
                f". Your total is {total}. Would you like to add anything else?"
            )

            return cart_summary

        # Extract potential menu items from the order text
        # This is a simple approach - in production, you would use more sophisticated NLP
        order_words = order_text.lower().split()
        potential_menu_items = []

        for i in range(len(order_words)):
            for j in range(i + 1, min(i + 5, len(order_words) + 1)):
                potential_item = " ".join(order_words[i:j])
                if len(potential_item) > 3:  # Avoid checking very short terms
                    potential_menu_items.append(potential_item)

        # Look up each potential menu item
        items_added = []
        for item_name in potential_menu_items:
            item_result = await self.execute_tool(
                "lookup_menu_item", {"item_name": item_name}
            )

            if item_result.get("found", False):
                name = item_result.get("name", "")
                plu = item_result.get("plu", "")

                # Skip if we've already added this item
                if name in items_added:
                    continue

                # Detect quantity from order text
                # Simple digit detection for quantities
                quantity = 1
                for word in order_words:
                    if word.isdigit() and int(word) > 0 and int(word) < 10:
                        quantity = int(word)
                        break

                # Add the item to the cart
                add_result = await self.execute_tool(
                    "add_item_to_cart", {"plu": plu, "quantity": quantity}
                )

                if add_result.get("success", False):
                    items_added.append(name)

        # Generate an appropriate response based on what happened
        if items_added:
            items_text = ", ".join(items_added)
            current_cart = await async_agents_conversation_store.get_cart(call_sid)
            total_price = current_cart.get("total_price", 0)
            total_price_str = (
                f"${total_price / 100:.2f}"
                if isinstance(total_price, (int, float))
                else "$0.00"
            )

            if len(items_added) == 1:
                return f"I've added {quantity} {items_text} to your cart. Your total is {total_price_str}. Anything else you'd like to add?"
            else:
                return f"I've added the following to your cart: {items_text}. Your total is {total_price_str}. Would you like anything else?"
        else:
            # Get the current cart
            cart_result = await self.execute_tool("get_current_cart", {})
            items = cart_result.get("items", [])

            if not items:
                return "I'm sorry, but I couldn't identify any menu items in your request. Could you please specify what you'd like to order?"
            else:
                return "What else would you like to add to your order?"

    async def process_order_request(
        self, call_sid: str, order_text: str
    ) -> Dict[str, Any]:
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
        await async_agents_conversation_store.add_message(
            call_sid, "assistant", response_text
        )

        logger.info(f"Processed order request in {duration:.2f}s: {order_text}")

        # Get the current cart after processing
        cart = await async_agents_conversation_store.get_cart(call_sid)

        # Return the result
        return {
            "success": True,
            "response": response_text,
            "processing_time": duration,
            "cart": cart,
            "order_ready_for_validation": response.get(
                "order_ready_for_validation", False
            ),
        }

    # process_order_request method removed as it was flagged as unused by Vulture

    async def execute_tool(
        self, tool_name: str, args: Dict[str, Any]
    ) -> Dict[str, Any]:
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
                args.get("special_instructions", None),
            )
        elif tool_name == "remove_from_cart":
            return await self._remove_from_cart(args.get("item_index", 0))
        elif tool_name == "modify_cart_item":
            return await self._modify_cart_item(
                args.get("item_index", 0),
                args.get("quantity", None),
                args.get("add_modifiers", None),
                args.get("remove_modifier_indices", None),
                args.get("special_instructions", None),
            )
        elif tool_name == "get_current_cart":
            return await self._get_current_cart()
        elif tool_name == "suggest_additions":
            return await self._suggest_additions(args.get("suggestion_type", "popular"))
        elif tool_name == "clear_cart":
            return await self._clear_cart()
        else:
            logger.warning(f"[{self.name}] Unknown tool: {tool_name}")
            return {"status": "error", "message": f"Tool '{tool_name}' not implemented"}

    async def _lookup_menu_item(self, item_name: str) -> Dict[str, Any]:
        """
        Look up a menu item by name.

        Args:
            item_name: The name of the menu item to look up

        Returns:
            Details about the menu item if found
        """
        logger.info(f"Looking up menu item: {item_name}")
        logger.info(f"Cart agent database session available: {self.db is not None}")

        # Get a fresh database session if we don't have one
        if self.db is None:
            from app.db_async import async_session_factory

            self.db = async_session_factory()
            logger.info("Created new database session for cart agent")

        # Use the async menu matcher to find the item
        async_matcher = await get_cached_async_menu_matcher(self.db)
        menu_item, score = await async_matcher.match_item(item_name)

        if not menu_item:
            logger.info(f"Menu item not found: {item_name}")
            return {
                "found": False,
                "search_term": item_name,
                "message": "This item doesn't appear to be on our menu.",
            }

        # Format the price for display
        price = menu_item.get("price", 0)
        price_str = (
            f"${price / 100:.2f}"
            if isinstance(price, (int, float))
            else "Price unavailable"
        )

        # Check if the item is available
        is_available = menu_item.get("available", True) and not menu_item.get(
            "snoozed", False
        )

        # Get modifiers for this item
        modifiers = []
        for mod_group_id in menu_item.get("modifierGroups", []):
            group = await async_menu_db_store.get_modifier_group(self.db, mod_group_id)
            if group:
                mod_list = []
                for mod_id in group.get("modifierIds", []):
                    modifier = await async_menu_db_store.get_modifier(self.db, mod_id)
                    if modifier and modifier.get("available", True):
                        mod_price = modifier.get("price", 0)
                        mod_price_str = f"${mod_price / 100:.2f}" if mod_price else ""
                        mod_list.append(
                            {
                                "name": modifier.get("name", ""),
                                "plu": modifier.get("plu", ""),
                                "price": mod_price_str,
                                "price_cents": mod_price or 0,
                            }
                        )

                if mod_list:
                    modifiers.append(
                        {
                            "group_name": group.get("name", ""),
                            "min_selection": group.get("minAllowed", 0),
                            "max_selection": group.get("maxAllowed", 0),
                            "modifiers": mod_list,
                        }
                    )

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
            "modifiers": modifiers,
        }

    async def _add_item_to_cart(
        self,
        plu: str,
        quantity: int = 1,
        modifiers: Optional[List[Dict[str, Any]]] = None,
        special_instructions: Optional[str] = None,
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
                "items": [],
            }

        logger.info(f"Adding item {plu} (qty: {quantity}) to cart for call {call_sid}")

        # Validate the item exists
        item_obj = await get_item_by_plu(self.db, plu)  # Changed to async call
        if not item_obj:
            logger.error(f"Item with PLU {plu} not found")
            return {
                "success": False,
                "message": f"Item with PLU {plu} not found",
                "total_price": 0,
                "items": [],
            }

        # Validate modifiers if provided
        validated_modifiers = []
        if modifiers:
            for mod in modifiers:
                mod_plu = mod.get("plu")
                mod_quantity = mod.get("quantity", 1)

                # Validate the modifier exists
                modifier_obj = await get_modifier_by_plu(self.db, mod_plu)  # Changed to async call
                if not modifier_obj:
                    logger.warning(f"Modifier with PLU {mod_plu} not found")
                    continue

                # Add to validated modifiers
                validated_modifiers.append(
                    {
                        "plu": mod_plu,
                        "name": modifier_obj.name,  # Direct attribute access
                        "quantity": mod_quantity,
                        "price_change": modifier_obj.price_change,  # Direct attribute access
                    }
                )

        # Create the new item entry
        new_item = {
            "plu": plu,
            "name": item_obj.name,  # Direct attribute access
            "price": item_obj.price,  # Direct attribute access
            "quantity": quantity,
            "modifiers": validated_modifiers,
            "special_instructions": special_instructions,
        }

        # Add to cart using the conversation store
        updated_cart = await async_agents_conversation_store.add_to_cart(
            call_sid, new_item
        )

        # Format the response
        return {
            "success": True,
            "message": f"Added {quantity} {item.get('name')} to cart",
            "total_price": updated_cart.get("total_price", 0),
            "items": updated_cart.get("items", []),
            "item_count": len(updated_cart.get("items", [])),
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
                "items": [],
            }

        logger.info(
            f"Removing item at index {item_index} from cart for call {call_sid}"
        )

        # Get the current cart
        current_cart = await async_agents_conversation_store.get_cart(call_sid)

        # Check if the index is valid
        if item_index < 0 or item_index >= len(current_cart.get("items", [])):
            logger.error(
                f"Invalid item index {item_index} for cart with {len(current_cart.get('items', []))} items"
            )
            return {
                "success": False,
                "message": f"Invalid item index {item_index}",
                "total_price": current_cart.get("total_price", 0),
                "items": current_cart.get("items", []),
            }

        # Get the item being removed for the response message
        removed_item = current_cart.get("items", [])[item_index]
        removed_name = removed_item.get("name", "item")
        removed_quantity = removed_item.get("quantity", 1)

        # Remove the item
        updated_cart = await async_agents_conversation_store.remove_from_cart(
            call_sid, item_index
        )

        # Format the response
        return {
            "success": True,
            "message": f"Removed {removed_quantity} {removed_name} from cart",
            "total_price": updated_cart.get("total_price", 0),
            "items": updated_cart.get("items", []),
            "item_count": len(updated_cart.get("items", [])),
        }

    async def _modify_cart_item(
        self,
        item_index: int,
        quantity: Optional[int] = None,
        add_modifiers: Optional[List[Dict[str, Any]]] = None,
        remove_modifier_indices: Optional[List[int]] = None,
        special_instructions: Optional[str] = None,
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
                "items": [],
            }

        logger.info(f"Modifying item at index {item_index} in cart for call {call_sid}")

        # Get the current cart
        current_cart = await async_agents_conversation_store.get_cart(call_sid)

        # Check if the index is valid
        if item_index < 0 or item_index >= len(current_cart.get("items", [])):
            logger.error(
                f"Invalid item index {item_index} for cart with {len(current_cart.get('items', []))} items"
            )
            return {
                "success": False,
                "message": f"Invalid item index {item_index}",
                "total_price": current_cart.get("total_price", 0),
                "items": current_cart.get("items", []),
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
                modifier_obj = await get_modifier_by_plu(self.db, mod_plu)  # Changed to async call
                if not modifier_obj:
                    logger.warning(f"Modifier with PLU {mod_plu} not found")
                    continue

                # Add to modifiers
                item["modifiers"].append(
                    {
                        "plu": mod_plu,
                        "name": modifier_obj.name,  # Direct attribute access
                        "quantity": mod_quantity,
                        "price_change": modifier_obj.price_change,  # Direct attribute access
                    }
                )

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
        await async_agents_conversation_store.update_cart(call_sid, current_cart)

        # Format the response
        return {
            "success": True,
            "message": f"Modified {item.get('name')} in cart",
            "total_price": current_cart.get("total_price", 0),
            "items": current_cart.get("items", []),
            "item_count": len(current_cart.get("items", [])),
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
                "items": [],
            }

        # Get the current cart
        current_cart = await async_agents_conversation_store.get_cart(call_sid)

        # Calculate a formatted total price string
        total_price_cents = current_cart.get("total_price", 0)
        total_price_str = (
            f"${total_price_cents / 100:.2f}"
            if isinstance(total_price_cents, (int, float))
            else "$0.00"
        )

        # Format item details for better readability
        formatted_items = []
        for i, item in enumerate(current_cart.get("items", [])):
            price_cents = item.get("price", 0)
            price_str = (
                f"${price_cents / 100:.2f}"
                if isinstance(price_cents, (int, float))
                else "$0.00"
            )

            formatted_modifiers = []
            for modifier in item.get("modifiers", []):
                mod_price = modifier.get("price_change", 0)
                mod_price_str = f"${mod_price / 100:.2f}" if mod_price else ""

                formatted_modifiers.append(
                    {
                        "name": modifier.get("name", ""),
                        "quantity": modifier.get("quantity", 1),
                        "price": mod_price_str,
                    }
                )

            formatted_items.append(
                {
                    "index": i,
                    "name": item.get("name", ""),
                    "quantity": item.get("quantity", 1),
                    "price": price_str,
                    "modifiers": formatted_modifiers,
                    "special_instructions": item.get("special_instructions"),
                }
            )

        # Return the formatted cart
        return {
            "success": True,
            "item_count": len(current_cart.get("items", [])),
            "total_price": current_cart.get("total_price", 0),
            "formatted_total": total_price_str,
            "items": formatted_items,
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
                "suggestions": [],
            }

        # Get the current cart
        current_cart = await async_agents_conversation_store.get_cart(call_sid)

        # Get categories based on suggestion type
        category_map = {
            "drinks": ["Beverages", "Drinks", "Sodas"],
            "sides": ["Sides", "Appetizers"],
            "desserts": ["Desserts", "Sweets"],
            "popular": ["Popular", "Specials", "Featured"],
            "combos": ["Combos", "Sets", "Specials"],
        }

        categories = category_map.get(suggestion_type, ["Popular"])

        # Get suggested items from these categories
        suggested_items = []

        # Check what categories are already in the cart
        cart_categories = set()
        for item_data in current_cart.get("items", []): # item renamed to item_data
            # Get the item by PLU to find its category
            db_item_obj = await get_item_by_plu(self.db, item_data.get("plu", "")) # Changed to async call, item to item_data
            if db_item_obj: # Renamed db_item to db_item_obj
                if hasattr(db_item_obj, 'category') and db_item_obj.category:
                    cart_categories.add(db_item_obj.category.name)
                # If category is just an ID, you might need to fetch category name
                # elif hasattr(db_item_obj, 'category_id') and db_item_obj.category_id:
                #     cat = await get_category(self.db, db_item_obj.category_id)
                #     if cat:
                #         cart_categories.add(cat.name)


        # Get items from related categories
        for category_name_str in categories: # category renamed to category_name_str
            # First, get the category ID from its name
            # This assumes category names are unique or we take the first match.
            # A more robust system might need a category slug or specific ID.
            category_obj = await self.db.execute(select(MenuCategory).filter(MenuCategory.name.ilike(category_name_str)))
            category_obj = category_obj.scalars().first()

            if category_obj:
                items_from_db = await get_items_by_category_crud(self.db, category_obj.id) # Changed to async call with ID
                # Only add available items
                for item_obj in items_from_db: # item renamed to item_obj
                    if item_obj.is_available and not (item_obj.snoozed_until and item_obj.snoozed_until > datetime.now()): # ORM attribute access
                        # Format price
                        price = item_obj.price # ORM attribute access
                        price_str = (
                            f"${price / 100:.2f}"
                            if isinstance(price, (int, float))
                            else "Price unavailable"
                        )

                        suggested_items.append(
                            {
                                "name": item_obj.name, # ORM attribute access
                                "plu": item_obj.plu, # ORM attribute access
                                "price": price_str,
                                "price_cents": price,
                                "description": item_obj.description, # ORM attribute access
                                "category": category_obj.name, # Use the fetched category name
                            }
                        )
            else:
                logger.warning(f"Category '{category_name_str}' not found for suggestions.")


        # Limit to 5 suggestions
        suggested_items = suggested_items[:5]

        return {
            "success": True,
            "suggestion_type": suggestion_type,
            "suggestions": suggested_items,
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
                "message": "Could not identify the current session",
            }

        # Clear the cart
        success = await async_agents_conversation_store.clear_cart(call_sid)

        if success:
            return {
                "success": True,
                "message": "Cart cleared successfully",
                "total_price": 0,
                "items": [],
            }
        else:
            return {"success": False, "message": "Failed to clear cart"}

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

    # get_tools method removed as it was flagged as unused by Vulture
