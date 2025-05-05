"""
Order parsing agent for interpreting customer orders.
This module provides the OrderParsingAgent class which extracts structured order data from natural language.
"""

import logging
import json
import traceback
import time
import openai
from typing import Dict, List, Any, Optional

# Local imports
from app.utils.agent_utils.logging import log_openai_request, log_openai_response
from app.utils.agent_utils.tools import find_menu_item_tool, extract_modifiers_from_item
from app.utils.menu_db_store import menu_db_store

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class OrderParsingAgent:
    """
    Agent for parsing customer orders from natural language into structured data.
    """
    
    def __init__(self, model: str = "gpt-4-0613"):
        """
        Initialize the OrderParsingAgent.
        
        Args:
            model: The OpenAI model to use
        """
        self.model = model
        self.menu = menu_db_store.get_menu() or {}
        logger.info(f"[ORDER-PARSING-AGENT] Initialized with {len(self.menu.get('items', []))} menu items")
    
    def parse_order(self, order_text: str) -> List[Dict[str, Any]]:
        """
        Parse a natural language order into structured items with modifiers.
        
        Args:
            order_text: The customer's order text
            
        Returns:
            List of structured order items with modifiers
        """
        logger.info(f"[ORDER-PARSING] Parsing order: '{order_text}'")
        
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
            
            # Make the API call
            start_time = time.time()
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=messages,
                functions=functions,
                function_call={"name": "extract_order_items"}
            )
            elapsed_time = time.time() - start_time
            
            # Log the response
            log_openai_response(response, "parse_order")
            logger.info(f"[ORDER-PARSING-TIME] OpenAI call took {elapsed_time:.2f} seconds")
            
            # Extract the function call arguments
            function_call = response.choices[0].message.get("function_call", {})
            if not function_call or not function_call.get("arguments"):
                logger.warning("[ORDER-PARSING-ERROR] No function call or arguments in response")
                return []
            
            # Parse the arguments JSON
            try:
                args = json.loads(function_call.get("arguments", "{}"))
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
                logger.error(f"Arguments: {function_call.get('arguments')}")
                return []
                
        except Exception as e:
            logger.error(f"[ORDER-PARSING-ERROR] Error parsing order: {str(e)}")
            logger.error(traceback.format_exc())
            return []