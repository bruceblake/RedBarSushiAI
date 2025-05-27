"""
Common tools for AI agents in the RedBarSushiAI application.
These functions provide various utilities that are used by different agent types.
"""

import logging
import json
import traceback
from typing import Dict, List, Any, Optional
import openai

from app.utils.menu_db_store_async import async_menu_db_store as menu_db_store
from app.utils.agent_utils.logging import log_openai_request, log_openai_response

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def find_menu_item_tool(item_name: str) -> Optional[Dict[str, Any]]:
    """
    Find a menu item by name using the database-backed menu store.
    This is designed for use as an OpenAI function tool.
    
    Args:
        item_name: The name of the menu item to find
        
    Returns:
        The menu item if found, None otherwise
    """
    logger.info(f"[TOOL-MENU-SEARCH] Searching for menu item: '{item_name}'")
    try:
        # Load menu data from DB
        menu = menu_db_store.get_menu()
        if not menu:
            logger.error("[TOOL-MENU-ERROR] Failed to load menu data")
            return None

        # Normalize search
        search_name = item_name.lower().strip()

        # Search for exact match first
        for item in menu.get("items", []):
            if item.get("name", "").lower() == search_name:
                logger.info(f"[TOOL-MENU-FOUND-EXACT] Found exact match: {item.get('name')}")
                return item

        # If no exact match, try fuzzy matching
        for item in menu.get("items", []):
            if search_name in item.get("name", "").lower():
                logger.info(f"[TOOL-MENU-FOUND-FUZZY] Found fuzzy match: {item.get('name')}")
                return item

        logger.warning(f"[TOOL-MENU-NOT-FOUND] No menu item found for: '{item_name}'")
        return None
    except Exception as e:
        logger.error(f"[TOOL-MENU-ERROR] Error finding menu item: {str(e)}")
        logger.error(traceback.format_exc())
        return None


def menu_search_tool(query: str) -> Dict[str, Any]:
    """
    Search the menu for items matching the query.
    This is designed for use as an OpenAI function tool.
    
    Args:
        query: The search query
        
    Returns:
        A dictionary with search results
    """
    logger.info(f"[TOOL-MENU-SEARCH] Searching menu for: '{query}'")
    results = {
        "items": [],
        "categories": [],
        "query": query
    }
    
    try:
        # Load menu data from DB
        menu = menu_db_store.get_menu()
        if not menu:
            logger.error("[TOOL-MENU-ERROR] Failed to load menu data")
            return results
            
        # Normalize query
        query_lower = query.lower().strip()
        
        # Search items
        for item in menu.get("items", []):
            item_name = item.get("name", "").lower()
            item_desc = item.get("description", "").lower()
            
            if query_lower in item_name or query_lower in item_desc:
                results["items"].append({
                    "name": item.get("name"),
                    "price": item.get("price"),
                    "description": item.get("description"),
                    "category": item.get("category")
                })
        
        # Search categories
        for category in menu.get("categories", []):
            category_name = category.get("name", "").lower()
            
            if query_lower in category_name:
                results["categories"].append({
                    "name": category.get("name"),
                    "description": category.get("description")
                })
        
        logger.info(f"[TOOL-MENU-RESULTS] Found {len(results['items'])} items and {len(results['categories'])} categories")
        return results
    except Exception as e:
        logger.error(f"[TOOL-MENU-ERROR] Error searching menu: {str(e)}")
        logger.error(traceback.format_exc())
        return results


def handle_conversational_question(question: str, context: str = "") -> str:
    """
    Handle a conversational question about the menu or restaurant.
    
    Args:
        question: The user's question
        context: Additional context
        
    Returns:
        The AI-generated response
    """
    logger.info(f"[CONVERSATION] Handling question: '{question}'")
    
    try:
        # Load menu data for context
        menu = menu_db_store.get_menu()
        if not menu:
            logger.error("[CONVERSATION-ERROR] Failed to load menu data")
            return "I'm sorry, I can't access the menu information right now."
        
        # Prepare menu context
        menu_context = "Restaurant menu information:\n"
        # Add top 10 items for context
        for i, item in enumerate(menu.get("items", [])[:10]):
            menu_context += f"- {item.get('name')}: {item.get('description', 'No description')}. Price: ${item.get('price', 0)/100:.2f}\n"
        menu_context += "... and more items."
        
        # Create messages for OpenAI
        messages = [
            {
                "role": "system",
                "content": "You are an AI assistant for a sushi restaurant. Provide clear, concise, and helpful answers about the menu, food items, and the restaurant. Keep responses brief and restaurant-focused."
            },
            {"role": "user", "content": f"{menu_context}\n\nAdditional context: {context}\n\nQuestion: {question}"}
        ]
        
        # Log the request
        log_openai_request("gpt-4-0613", messages, "handle_question")
        
        # Make the API call
        response = openai.ChatCompletion.create(
            model="gpt-4-0613",
            messages=messages,
            max_tokens=150
        )
        
        # Log the response
        log_openai_response(response, "handle_question")
        
        # Extract the response text
        answer = response.choices[0].message.content
        logger.info(f"[CONVERSATION-ANSWER] Generated answer of length {len(answer)}")
        
        return answer
    except Exception as e:
        logger.error(f"[CONVERSATION-ERROR] Error handling question: {str(e)}")
        logger.error(traceback.format_exc())
        return "I'm sorry, I encountered an error trying to answer your question."


def extract_modifiers_from_item(menu_item: Dict[str, Any], modifier_text: str) -> List[Dict[str, Any]]:
    """
    Extract structured modifiers from natural language text for a specific menu item.
    
    Args:
        menu_item: The menu item dictionary
        modifier_text: Natural language modifier description
        
    Returns:
        List of structured modifier objects
    """
    logger.info(f"[MODIFIER-EXTRACT] Extracting modifiers for {menu_item.get('name')}: '{modifier_text}'")
    
    extracted_modifiers = []
    try:
        # Load full menu for modifier lookup
        menu = menu_db_store.get_menu()
        if not menu:
            logger.error("[MODIFIER-ERROR] Failed to load menu data")
            return []
            
        # Get the modifier groups for this item
        item_plu = menu_item.get("plu")
        item_modifier_groups = []
        
        # Find the item-modifier group mappings
        for mapping in menu.get("itemModifierGroups", []):
            if mapping.get("menuItemPlu") == item_plu:
                group_id = mapping.get("modifierGroupId")
                if group_id:
                    # Find the corresponding modifier group
                    for group in menu.get("modifierGroups", []):
                        if group.get("id") == group_id:
                            item_modifier_groups.append(group)
                            break
        
        # If no modifier groups, return empty list
        if not item_modifier_groups:
            logger.warning(f"[MODIFIER-WARN] No modifier groups found for item: {menu_item.get('name')}")
            return []
            
        # Normalize modifier text
        modifier_text_lower = modifier_text.lower().strip()
        
        # For each modifier group, check if any of its modifiers match the description
        for group in item_modifier_groups:
            group_id = group.get("id")
            
            # Find modifiers in this group
            for mapping in menu.get("groupModifiers", []):
                if mapping.get("modifierGroupId") == group_id:
                    modifier_id = mapping.get("modifierId")
                    
                    # Find the modifier details
                    for modifier in menu.get("modifiers", []):
                        if modifier.get("id") == modifier_id:
                            modifier_name = modifier.get("name", "").lower()
                            
                            # Check if this modifier matches the text
                            if modifier_name in modifier_text_lower or modifier_text_lower in modifier_name:
                                extracted_modifiers.append({
                                    "name": modifier.get("name"),
                                    "plu": modifier.get("plu"),
                                    "price_change": modifier.get("priceChange", 0),
                                    "reference_handler": f"modifier_id:{modifier_id}"
                                })
                                logger.info(f"[MODIFIER-MATCH] Found modifier: {modifier.get('name')}")
        
        # Log the results
        logger.info(f"[MODIFIER-RESULT] Extracted {len(extracted_modifiers)} modifiers")
        return extracted_modifiers
    except Exception as e:
        logger.error(f"[MODIFIER-ERROR] Error extracting modifiers: {str(e)}")
        logger.error(traceback.format_exc())
        return []


def check_modifier_constraints(menu_item: Dict[str, Any], modifiers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Check if the selected modifiers meet the constraints for the menu item.
    
    Args:
        menu_item: The menu item dictionary
        modifiers: List of modifiers
        
    Returns:
        Dictionary with validation results
    """
    logger.info(f"[CONSTRAINT-CHECK] Checking constraints for {menu_item.get('name')} with {len(modifiers)} modifiers")
    
    result = {
        "valid": True,
        "missing_required": [],
        "group_violations": []
    }
    
    try:
        # Load full menu for constraint lookup
        menu = menu_db_store.get_menu()
        if not menu:
            logger.error("[CONSTRAINT-ERROR] Failed to load menu data")
            result["valid"] = False
            return result
            
        # Get the modifier groups for this item
        item_plu = menu_item.get("plu")
        item_modifier_groups = []
        
        # Find the item-modifier group mappings
        for mapping in menu.get("itemModifierGroups", []):
            if mapping.get("menuItemPlu") == item_plu:
                group_id = mapping.get("modifierGroupId")
                if group_id:
                    # Find the corresponding modifier group
                    for group in menu.get("modifierGroups", []):
                        if group.get("id") == group_id:
                            item_modifier_groups.append(group)
                            break
        
        # Check constraints for each group
        for group in item_modifier_groups:
            group_id = group.get("id")
            group_name = group.get("name")
            min_required = group.get("minSelection", 0)
            max_allowed = group.get("maxSelection", 0)
            
            # Get all modifiers in this group
            group_modifiers = []
            for mapping in menu.get("groupModifiers", []):
                if mapping.get("modifierGroupId") == group_id:
                    modifier_id = mapping.get("modifierId")
                    for modifier in menu.get("modifiers", []):
                        if modifier.get("id") == modifier_id:
                            group_modifiers.append(modifier)
            
            # Count selected modifiers from this group
            selected_count = 0
            for selected_mod in modifiers:
                selected_plu = selected_mod.get("plu")
                for group_mod in group_modifiers:
                    if group_mod.get("plu") == selected_plu:
                        selected_count += 1
                        break
            
            # Check minimum constraint
            if min_required > 0 and selected_count < min_required:
                result["valid"] = False
                result["missing_required"].append({
                    "group_name": group_name,
                    "required": min_required,
                    "selected": selected_count
                })
                logger.warning(f"[CONSTRAINT-VIOLATION] Group '{group_name}' requires at least {min_required} selections, but only {selected_count} were selected")
            
            # Check maximum constraint
            if max_allowed > 0 and selected_count > max_allowed:
                result["valid"] = False
                result["group_violations"].append({
                    "group_name": group_name,
                    "maximum": max_allowed,
                    "selected": selected_count
                })
                logger.warning(f"[CONSTRAINT-VIOLATION] Group '{group_name}' allows at most {max_allowed} selections, but {selected_count} were selected")
        
        return result
    except Exception as e:
        logger.error(f"[CONSTRAINT-ERROR] Error checking constraints: {str(e)}")
        logger.error(traceback.format_exc())
        result["valid"] = False
        return result