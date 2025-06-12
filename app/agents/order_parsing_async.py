"""
Async order parsing agent for interpreting customer orders.
This module provides the OrderParsingAsyncAgent class which extracts structured order data from natural language.
"""

import logging
import json
import traceback
import time
from typing import Dict, List, Any, Optional
from openai import AsyncOpenAI

from app.agents.base_async import BaseAsyncAgent
from app.utils.agent_utils.logging import log_openai_request, log_openai_response
from app.utils.agent_utils.tools import find_menu_item_tool, extract_modifiers_from_item
from app.utils.menu_db_store_async import async_menu_db_store
from app.config import settings

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class OrderParsingAsyncAgent(BaseAsyncAgent):
    """
    Async agent for parsing customer orders from natural language into structured data.
    """
    
    def __init__(self, model: str = "gpt-4-0613"):
        """
        Initialize the OrderParsingAsyncAgent.
        
        Args:
            model: The OpenAI model to use
        """
        super().__init__(name="OrderParsingAgent")
        self.model = model
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.menu = None
        logger.info(f"[ORDER-PARSING-AGENT] Initialized with model {model}")
    
    async def _ensure_menu_loaded(self):
        """Ensure the menu is loaded from the database."""
        if self.menu is None:
            self.menu = await async_menu_db_store.get_menu() or {}
            logger.info(f"[ORDER-PARSING-AGENT] Loaded {len(self.menu.get('items', []))} menu items")
    
    async def parse_order(self, order_text: str) -> List[Dict[str, Any]]:
        """
        Parse a natural language order into structured items with modifiers.
        
        Args:
            order_text: The customer's order text
            
        Returns:
            List of structured order items with modifiers
        """
        logger.info(f"[ORDER-PARSING] Parsing order: '{order_text}'")
        
        # Ensure menu is loaded
        await self._ensure_menu_loaded()
        
        try:
            # Use OpenAI function calling to extract structured data
            functions = [
                {
                    "name": "extract_order_items",
                    "description": "Extract menu items and their modifiers from a customer order",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "items": {
                                "type": "array",
                                "description": "List of items in the order",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {
                                            "type": "string",
                                            "description": "Name of the menu item"
                                        },
                                        "quantity": {
                                            "type": "integer",
                                            "description": "Quantity of this item"
                                        },
                                        "modifiers": {
                                            "type": "array",
                                            "description": "Modifiers or special instructions for this item",
                                            "items": {
                                                "type": "string"
                                            }
                                        }
                                    },
                                    "required": ["name"]
                                }
                            }
                        },
                        "required": ["items"]
                    }
                }
            ]
            
            # Create a system message with menu context
            system_message = {
                "role": "system",
                "content": "You are an AI assistant for a sushi restaurant. Your task is to parse customer orders into structured data. Extract all menu items and their modifiers from the customer's order."
            }
            
            # Create the full message list
            messages = [
                system_message,
                {"role": "user", "content": order_text}
            ]
            
            # Log the request
            log_openai_request(self.model, messages, "parse_order")
            
            # Make the async API call
            start_time = time.time()
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                functions=functions,
                function_call={"name": "extract_order_items"}
            )
            elapsed_time = time.time() - start_time
            
            # Log the response
            log_openai_response(response.model_dump(), "parse_order")
            logger.info(f"[ORDER-PARSING-TIME] OpenAI call took {elapsed_time:.2f} seconds")
            
            # Extract the function call arguments
            message = response.choices[0].message
            function_call = message.function_call if hasattr(message, 'function_call') else None
            
            if not function_call or not function_call.arguments:
                logger.warning("[ORDER-PARSING-ERROR] No function call or arguments in response")
                return []
            
            # Parse the arguments JSON
            try:
                args = json.loads(function_call.arguments)
                raw_items = args.get("items", [])
                logger.info(f"[ORDER-PARSING-RESULT] Extracted {len(raw_items)} raw items")
                
                # Process the raw items to add menu references
                processed_items = []
                for item in raw_items:
                    # Look up the item in the menu
                    menu_item = find_menu_item_tool(item.get("name", ""))
                    
                    if menu_item:
                        # Create a processed item with menu data
                        processed_item = {
                            "name": menu_item.get("name"),
                            "plu": menu_item.get("plu"),
                            "price": menu_item.get("price"),
                            "quantity": item.get("quantity", 1),
                            "modifier": []
                        }
                        
                        # Process modifiers if present
                        if "modifiers" in item and item["modifiers"]:
                            for modifier_text in item["modifiers"]:
                                modifiers = extract_modifiers_from_item(menu_item, modifier_text)
                                if modifiers:
                                    processed_item["modifier"].extend(modifiers)
                        
                        processed_items.append(processed_item)
                        logger.info(f"[ORDER-PARSING-ITEM] Processed item: {processed_item['name']} with {len(processed_item['modifier'])} modifiers")
                    else:
                        logger.warning(f"[ORDER-PARSING-WARN] Could not find menu item: {item.get('name')}")
                
                return processed_items
            except json.JSONDecodeError as e:
                logger.error(f"[ORDER-PARSING-ERROR] Failed to parse function arguments: {str(e)}")
                logger.error(f"Arguments: {function_call.arguments}")
                return []
                
        except Exception as e:
            logger.error(f"[ORDER-PARSING-ERROR] Error parsing order: {str(e)}")
            logger.error(traceback.format_exc())
            return []
    
    async def process_input(self, input_text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process input for order parsing.
        
        This method wraps parse_order to conform to the BaseAsyncAgent interface.
        
        Args:
            input_text: The customer's order text
            context: Optional context (not used in this implementation)
            
        Returns:
            Dict containing the parsed order items
        """
        items = await self.parse_order(input_text)
        return {
            "items": items,
            "success": len(items) > 0,
            "message": f"Parsed {len(items)} items from order" if items else "No items could be parsed from the order"
        }