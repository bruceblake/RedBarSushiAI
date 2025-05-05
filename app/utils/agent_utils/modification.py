"""
Order modification agent for processing order changes.
This module provides the OrderModificationAgent class which processes modifications to existing orders.
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

class OrderModificationAgent:
    """
    Agent for processing modifications to existing orders.
    """
    
    def __init__(self, model: str = "gpt-4-0613"):
        """
        Initialize the OrderModificationAgent.
        
        Args:
            model: The OpenAI model to use
        """
        self.model = model
        self.menu = menu_db_store.get_menu() or {}
        logger.info(f"[ORDER-MOD-AGENT] Initialized with {len(self.menu.get('items', []))} menu items")
    
    def modify_order(self, current_order: Dict[str, Any], modification_text: str) -> Dict[str, Any]:
        """
        Process a modification request for an existing order.
        
        Args:
            current_order: The current order structure
            modification_text: The customer's modification request
            
        Returns:
            A dictionary with additions, removals, and modifications
        """
        logger.info(f"[ORDER-MOD] Processing modification: '{modification_text}'")
        logger.info(f"[ORDER-MOD] Current order has {len(current_order.get('items', []))} items")
        
        try:
            # Use OpenAI function calling to extract structured modifications
            functions = [
                {
                    "name": "process_order_modifications",
                    "description": "Process modifications to an existing order",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "additions": {
                                "type": "array",
                                "description": "New items to add to the order",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {
                                            "type": "string",
                                            "description": "Name of the menu item to add"
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
                            },
                            "removals": {
                                "type": "array",
                                "description": "Items to remove from the order",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {
                                            "type": "string",
                                            "description": "Name of the menu item to remove"
                                        },
                                        "quantity": {
                                            "type": "integer",
                                            "description": "Quantity to remove (default is all)"
                                        }
                                    },
                                    "required": ["name"]
                                }
                            },
                            "modifications": {
                                "type": "array",
                                "description": "Modifications to existing items",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {
                                            "type": "string",
                                            "description": "Name of the menu item to modify"
                                        },
                                        "add_modifiers": {
                                            "type": "array",
                                            "description": "Modifiers to add to this item",
                                            "items": {
                                                "type": "string"
                                            }
                                        },
                                        "remove_modifiers": {
                                            "type": "array",
                                            "description": "Modifiers to remove from this item",
                                            "items": {
                                                "type": "string"
                                            }
                                        },
                                        "change_quantity": {
                                            "type": "integer",
                                            "description": "New quantity for this item"
                                        }
                                    },
                                    "required": ["name"]
                                }
                            }
                        }
                    }
                }
            ]
            
            # Prepare the current order summary for context
            order_context = "Current order:\n"
            for item in current_order.get("items", []):
                item_name = item.get("name", "Unknown item")
                quantity = item.get("quantity", 1)
                modifiers = [mod.get("name", "Unknown modifier") for mod in item.get("modifier", [])]
                
                order_context += f"- {quantity}x {item_name}"
                if modifiers:
                    order_context += f" with {', '.join(modifiers)}"
                order_context += "\n"
            
            # Create a system message with menu context
            system_message = {
                "role": "system",
                "content": "You are an AI assistant for a sushi restaurant. Your task is to process modifications to an existing order. Extract all additions, removals, and modifications from the customer's request."
            }
            
            # Create the full message list
            messages = [
                system_message,
                {"role": "user", "content": f"{order_context}\n\nCustomer wants to modify their order: {modification_text}"}
            ]
            
            # Log the request
            log_openai_request(self.model, messages, "modify_order")
            
            # Make the API call
            start_time = time.time()
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=messages,
                functions=functions,
                function_call={"name": "process_order_modifications"}
            )
            elapsed_time = time.time() - start_time
            
            # Log the response
            log_openai_response(response, "modify_order")
            logger.info(f"[ORDER-MOD-TIME] OpenAI call took {elapsed_time:.2f} seconds")
            
            # Extract the function call arguments
            function_call = response.choices[0].message.get("function_call", {})
            if not function_call or not function_call.get("arguments"):
                logger.warning("[ORDER-MOD-ERROR] No function call or arguments in response")
                return {"additions": [], "removals": [], "modifications": []}
            
            # Parse the arguments JSON
            try:
                mods = json.loads(function_call.get("arguments", "{}"))
                logger.info(f"[ORDER-MOD-RESULT] Extracted {len(mods.get('additions', []))} additions, {len(mods.get('removals', []))} removals, {len(mods.get('modifications', []))} modifications")
                
                # Process additions to add menu references
                processed_additions = []
                for item in mods.get("additions", []):
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
                        
                        processed_additions.append(processed_item)
                        logger.info(f"[ORDER-MOD-ADDITION] Processed addition: {processed_item['name']} with {len(processed_item['modifier'])} modifiers")
                    else:
                        logger.warning(f"[ORDER-MOD-WARN] Could not find menu item for addition: {item.get('name')}")
                
                # Return the processed modifications
                return {
                    "additions": processed_additions,
                    "removals": mods.get("removals", []),
                    "modifications": mods.get("modifications", [])
                }
                
            except json.JSONDecodeError as e:
                logger.error(f"[ORDER-MOD-ERROR] Failed to parse function arguments: {str(e)}")
                logger.error(f"Arguments: {function_call.get('arguments')}")
                return {"additions": [], "removals": [], "modifications": []}
                
        except Exception as e:
            logger.error(f"[ORDER-MOD-ERROR] Error processing order modification: {str(e)}")
            logger.error(traceback.format_exc())
            return {"additions": [], "removals": [], "modifications": []}