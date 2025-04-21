"""
Menu item matching using AI to find the best match when exact matches aren't found.
This module provides advanced menu item matching and customer interaction capabilities.
"""

import os
import json
import logging
import traceback
from typing import Dict, List, Any, Optional, Tuple
import openai

from app.utils.menu_utils import load_menu_data
from app.utils.agent_utils import log_openai_request, log_openai_response

logger = logging.getLogger(__name__)

class MenuMatcher:
    """
    AI-powered menu item matcher that finds the best match for a customer request 
    and facilitates customer interaction to clarify orders.
    """
    
    def __init__(self):
        """Initialize the menu matcher."""
        self.menu_data = load_menu_data()
        self.model = "gpt-4.1-mini"  # Can be configured based on needs

    def find_menu_item(self, item_name: str, check_availability: bool = False, 
                      context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Find a menu item based on the given name, using AI to find the best match.
        
        Args:
            item_name: Name of the item requested by the customer
            check_availability: Only return available items if True
            context: Additional context about the order/conversation
            
        Returns:
            dict or None: The matched menu item if found, None otherwise
        """
        if not item_name:
            return None
            
        # First try exact match to avoid unnecessary API calls
        exact_match = self._find_exact_match(item_name, check_availability)
        if exact_match:
            logger.info(f"[MENU-MATCHER] Found exact match for '{item_name}': {exact_match.get('name')}")
            return exact_match
            
        # No exact match found, use AI to find the best match
        return self._find_ai_match(item_name, check_availability, context)
    
    def _find_exact_match(self, item_name: str, check_availability: bool) -> Optional[Dict[str, Any]]:
        """Find an exact match for the item name in the menu."""
        # Clean up the name for comparison
        cleaned_name = item_name.lower().strip()
        
        # Try direct match with menu items
        for item in self.menu_data.get("items", []):
            # Skip category items
            if item.get("is_category", False):
                continue
                
            if item.get("name", "").lower() == cleaned_name:
                if not check_availability or (
                    item.get("available", True) and not item.get("snoozed", False)
                ):
                    return item
                    
        return None
    
    def _find_ai_match(self, item_name: str, check_availability: bool, 
                      context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Use AI to find the best match for the item name in the menu."""
        try:
            # Prepare menu context
            menu_items = []
            for item in self.menu_data.get("items", []):
                # Skip category items
                if item.get("is_category", False):
                    continue
                    
                # Skip unavailable items if we're checking availability
                if check_availability and (
                    not item.get("available", True) or item.get("snoozed", False)
                ):
                    continue
                    
                menu_items.append({
                    "name": item.get("name", ""),
                    "category": item.get("category", ""),
                    "description": item.get("description", ""),
                    "price": item.get("price", 0.0),
                })
                
            # No items to match against
            if not menu_items:
                logger.warning("[MENU-MATCHER] No menu items available to match against")
                return None
                
            # Build the messages for the API call
            messages = [
                {
                    "role": "system",
                    "content": """You are an AI assistant for a restaurant that helps match customer requests to menu items.
                    Your goal is to find the best match for a customer's item request based on the available menu items.
                    
                    Important rules:
                    1. ONLY match against actual menu items, not category names
                    2. Consider item names, descriptions, and ingredients in your matching
                    3. Use fuzzy matching when appropriate (e.g., "cheeseburger" might match "Burger with Cheese")
                    4. Focus on the customer's intent, not just literal word matching
                    5. Return the name of the best matching menu item, exactly as it appears in the menu
                    6. NEVER invent or suggest items that don't exist in the menu
                    
                    Always format your response as a single menu item name, exactly as it appears in the menu."""
                },
                {
                    "role": "user",
                    "content": f"Customer requested: '{item_name}'\n\nAvailable menu items:\n{json.dumps(menu_items, indent=2)}\n\nWhat is the best matching menu item?"
                }
            ]
            
            # Add conversation context if provided
            if context and "conversation" in context:
                messages[0]["content"] += "\nUse the conversation history to understand the customer's preferences and requirements."
                messages.append({
                    "role": "user",
                    "content": f"Conversation history:\n{context['conversation']}"
                })
                
            # Log the request
            log_openai_request(self.model, messages, "menu_ai_matcher")
            
            # Make the API call
            response = openai.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,  # Lower temperature for more deterministic results
                max_tokens=150,   # Keep responses concise
            )
            
            # Log the response
            log_openai_response(response, "menu_ai_matcher")
            
            # Extract the matched item name from the response
            matched_item_name = response.choices[0].message.content.strip()
            
            # Clean up the response to handle various output formats
            if ":" in matched_item_name:
                matched_item_name = matched_item_name.split(":", 1)[1].strip()
            if matched_item_name.startswith('"') and matched_item_name.endswith('"'):
                matched_item_name = matched_item_name[1:-1].strip()
                
            logger.info(f"[MENU-MATCHER] AI suggested match: '{matched_item_name}' for request '{item_name}'")
            
            # Find the matched item in the menu
            for item in self.menu_data.get("items", []):
                if item.get("name", "").lower() == matched_item_name.lower():
                    logger.info(f"[MENU-MATCHER] Found AI-matched item in menu: {item.get('name')}")
                    return item
                    
            # If we can't find the exact name the AI returned, try a close match
            for item in self.menu_data.get("items", []):
                if matched_item_name.lower() in item.get("name", "").lower() or item.get("name", "").lower() in matched_item_name.lower():
                    logger.info(f"[MENU-MATCHER] Found close AI-matched item in menu: {item.get('name')}")
                    return item
                    
            logger.warning(f"[MENU-MATCHER] AI suggested '{matched_item_name}' but item not found in menu")
            return None
            
        except Exception as e:
            logger.error(f"[MENU-MATCHER] Error in AI matching: {str(e)}")
            logger.error(f"[MENU-MATCHER] Traceback: {traceback.format_exc()}")
            return None
    
    def interactive_order_resolution(self, customer_request: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Interactively resolve an order with the customer when the request is ambiguous.
        
        Args:
            customer_request: The customer's original request
            context: Additional context about the conversation
            
        Returns:
            dict: The resolved order with clarification dialog
        """
        try:
            # Prepare menu categories and some example items
            categories = {}
            
            # First, find all category items to create category map
            category_map = {}
            for item in self.menu_data.get("items", []):
                if item.get("is_category", True):  # This item IS a category
                    reference = item.get("reference_handler", "")
                    if reference:
                        category_map[reference] = item.get("name", "Unknown Category")
            
            # Now process actual menu items
            for item in self.menu_data.get("items", []):
                # Skip category headers
                if item.get("is_category", False):
                    continue
                    
                # Get parent category name from parentId or use "Uncategorized"
                parent_id = item.get("parentId", "")
                category_name = category_map.get(parent_id, "Uncategorized")
                
                if category_name not in categories:
                    categories[category_name] = []
                if len(categories[category_name]) < 3:  # Just get a few examples per category
                    categories[category_name].append(item.get("name", ""))
                    
            # Build prompt for AI to clarify the order
            messages = [
                {
                    "role": "system",
                    "content": """You are an AI assistant for a restaurant that helps customers clarify their orders.
                    Your goal is to understand what the customer wants to order and suggest the appropriate menu items.
                    
                    Important rules:
                    1. ONLY suggest actual menu items, not category names
                    2. Ask clarifying questions when the order is ambiguous
                    3. Be friendly, helpful, and concise in your responses
                    4. Base your suggestions ONLY on the menu categories and items available
                    5. NEVER make up items that aren't in the menu
                    
                    When suggesting menu items, be precise and use the exact item names as they appear in the menu.
                    Focus on understanding the customer's intent and helping them find the right items."""
                },
                {
                    "role": "user",
                    "content": f"Customer request: '{customer_request}'\n\nMenu Categories and Example Items:\n{json.dumps(categories, indent=2)}\n\nHow would you clarify the order? Ask specific questions to determine what the customer wants."
                }
            ]
            
            # Add conversation context if provided
            if context and "conversation" in context:
                messages[0]["content"] += "\nUse the conversation history to understand the customer's preferences."
                messages.append({
                    "role": "user", 
                    "content": f"Conversation history:\n{context['conversation']}"
                })
                
            # Log the request
            log_openai_request(self.model, messages, "order_clarification")
            
            # Make the API call
            response = openai.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,  # Higher temperature for more creativity in responses
                max_tokens=250,   # Allow for a longer clarifying response
            )
            
            # Log the response
            log_openai_response(response, "order_clarification")
            
            # Extract the clarification dialog
            clarification = response.choices[0].message.content.strip()
            
            # Return the clarification along with the original request
            return {
                "original_request": customer_request,
                "clarification_dialog": clarification,
                "resolved": False,  # This will be set to True when the order is finalized
                "items": []         # Will be populated when items are confirmed
            }
            
        except Exception as e:
            logger.error(f"[MENU-MATCHER] Error in interactive resolution: {str(e)}")
            logger.error(f"[MENU-MATCHER] Traceback: {traceback.format_exc()}")
            return {
                "original_request": customer_request,
                "clarification_dialog": "I'm sorry, I'm having trouble understanding your order right now. Could you please be more specific about what you'd like to order?",
                "resolved": False,
                "items": []
            }
            
    def process_customer_response(self, order_state: Dict[str, Any], customer_response: str) -> Dict[str, Any]:
        """
        Process a customer's response to a clarification question and update the order state.
        
        Args:
            order_state: The current state of the order resolution
            customer_response: The customer's response to the clarification
            
        Returns:
            dict: The updated order state
        """
        try:
            # Update the conversation context
            conversation = order_state.get("conversation", [])
            conversation.append({"role": "assistant", "content": order_state.get("clarification_dialog", "")})
            conversation.append({"role": "user", "content": customer_response})
            
            # Build a menu summary for the AI
            menu_summary = []
            
            # First, find all category items to create category map
            category_map = {}
            for item in self.menu_data.get("items", []):
                if item.get("is_category", True):  # This item IS a category
                    reference = item.get("reference_handler", "")
                    if reference:
                        category_map[reference] = item.get("name", "Unknown Category")
            
            # Now process actual menu items
            for item in self.menu_data.get("items", []):
                # Skip category headers
                if item.get("is_category", False):
                    continue
                    
                # Get parent category name from parentId or use "Uncategorized"
                parent_id = item.get("parentId", "")
                category_name = category_map.get(parent_id, "Uncategorized")
                       
                menu_summary.append({
                    "name": item.get("name", ""),
                    "category": category_name,
                    "description": item.get("description", ""),
                    "price": item.get("price", 0.0)
                })
                
            # Build the prompt for the AI
            messages = [
                {
                    "role": "system",
                    "content": """You are an AI assistant for a restaurant that helps customers place orders.
                    Based on the conversation, identify the specific menu items the customer wants to order.
                    
                    Important rules:
                    1. ONLY match against actual menu items, not category names
                    2. Be precise in identifying menu items - match to exact item names in the menu
                    3. For ambiguous requests, ask clarifying questions
                    4. NEVER make up items that don't exist in the menu
                    
                    Return a JSON object with the following structure:
                    {
                        "items": [
                            {"name": "exact menu item name", "quantity": 1, "notes": "any special requests"},
                            ...
                        ],
                        "resolved": true/false (whether the order is fully resolved),
                        "next_question": "next question to ask if not resolved"
                    }
                    
                    Only include items that match exactly with menu items from the provided list.
                    For unclear items, set resolved to false and provide a specific clarifying question.
                    """
                }
            ]
            
            # Add the conversation context
            for msg in conversation:
                messages.append({"role": msg["role"], "content": msg["content"]})
                
            # Add the menu context
            messages.append({
                "role": "user",
                "content": f"Available menu items:\n{json.dumps(menu_summary, indent=2)}\n\nPlease process this conversation and identify the order."
            })
            
            # Log the request
            log_openai_request(self.model, messages, "process_customer_response")
            
            # Make the API call
            response = openai.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            # Log the response
            log_openai_response(response, "process_customer_response")
            
            # Parse the response
            try:
                parsed_response = json.loads(response.choices[0].message.content)
                
                # Update the order state
                order_state["conversation"] = conversation
                order_state["resolved"] = parsed_response.get("resolved", False)
                
                # If items were identified, update the items list
                if "items" in parsed_response and parsed_response["items"]:
                    identified_items = []
                    
                    # Look up the actual menu items
                    for item_info in parsed_response["items"]:
                        menu_item = self.find_menu_item(item_info["name"])
                        if menu_item:
                            identified_items.append({
                                "name": menu_item["name"],
                                "price": menu_item.get("price", 0.0),
                                "reference_handler": menu_item.get("reference_handler", ""),
                                "quantity": item_info.get("quantity", 1),
                                "notes": item_info.get("notes", ""),
                                "modifier": []  # Can be populated later for modifiers
                            })
                            
                    order_state["items"] = identified_items
                    
                # If the order is not resolved, add the next question
                if not order_state["resolved"] and "next_question" in parsed_response:
                    order_state["clarification_dialog"] = parsed_response["next_question"]
                elif not order_state["resolved"]:
                    order_state["clarification_dialog"] = "Could you please clarify what you'd like to order from our menu?"
                else:
                    # Order is resolved, create a confirmation message
                    confirmation = "Great! Here's your order:\n"
                    for item in order_state.get("items", []):
                        confirmation += f"- {item.get('quantity', 1)}x {item.get('name', 'Unknown item')}"
                        if item.get("notes"):
                            confirmation += f" ({item['notes']})"
                        confirmation += "\n"
                    confirmation += "\nIs this correct?"
                    order_state["clarification_dialog"] = confirmation
                    
                return order_state
                
            except json.JSONDecodeError:
                logger.error(f"[MENU-MATCHER] Failed to parse JSON response: {response.choices[0].message.content}")
                order_state["clarification_dialog"] = "I'm having trouble understanding your order. Could you tell me exactly what items you'd like to order from our menu?"
                return order_state
                
        except Exception as e:
            logger.error(f"[MENU-MATCHER] Error processing customer response: {str(e)}")
            logger.error(f"[MENU-MATCHER] Traceback: {traceback.format_exc()}")
            order_state["clarification_dialog"] = "I'm sorry, I'm having trouble processing your response. Could you please try again with a clear list of items you'd like to order?"
            return order_state


# Creating a singleton instance for easy import
menu_matcher = MenuMatcher()

def find_menu_item_ai(item_name: str, check_availability: bool = False, 
                     context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    Find a menu item using AI matching when exact matches aren't found.
    This is a convenient function that uses the MenuMatcher singleton.
    
    Args:
        item_name: Name of the item to find
        check_availability: Only return available items if True
        context: Additional context about the order/conversation
        
    Returns:
        dict or None: The matched menu item if found, None otherwise
    """
    return menu_matcher.find_menu_item(item_name, check_availability, context)