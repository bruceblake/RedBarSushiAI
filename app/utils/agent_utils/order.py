"""
Order analysis and processing utilities for AI agents.
These functions help AI agents understand and process customer orders.
"""

import logging
import json
import traceback
from typing import Dict, List, Any, Optional

# Local imports
from app.utils.agent_utils.menu import SushiMenuTool
from app.utils.agent_utils.modification import OrderModificationAgent
from app.utils.agent_utils.logging import log_openai_request, log_openai_response

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def analyze_user_input(input_text: str) -> Dict[str, Any]:
    """
    Analyze user input to determine intent and extract menu items.
    
    Args:
        input_text: The user's input text
        
    Returns:
        A dictionary with intent and extracted menu items
    """
    logger.info(f"[ANALYZE-INPUT] Analyzing user input: '{input_text}'")
    
    # Default response structure
    intent = "unknown"
    menu_items = []
    
    try:
        # Check for menu question intent
        menu_question_keywords = ["menu", "what do you have", "what do you offer", "what's available"]
        if any(keyword in input_text.lower() for keyword in menu_question_keywords):
            intent = "ask_menu"
            logger.info("[ANALYZE-INTENT] Detected menu question intent")
        
        # Check for order intent
        order_keywords = ["order", "want", "get", "have", "give me", "i'll take", "i'd like"]
        if any(keyword in input_text.lower() for keyword in order_keywords):
            intent = "place_order"
            logger.info("[ANALYZE-INTENT] Detected order intent")
            
            # Extract items using the specialized parser
            from app.utils.agent_utils.parsing import OrderParsingAgent
            parser = OrderParsingAgent()
            parsed_items = parser.parse_order(input_text)
            
            if parsed_items:
                menu_items = parsed_items
                logger.info(f"[ANALYZE-ITEMS] Extracted {len(menu_items)} items from order")
                
                # Ensure modifiers are preserved for each item
                for item in menu_items:
                    if "modifier" in item and item["modifier"]:
                        logger.info(
                            f"[ANALYZE-MODS] Item '{item.get('name')}' has {len(item['modifier'])} modifiers"
                        )
                        # Log each modifier for debugging
                        for mod in item["modifier"]:
                            if isinstance(mod, dict):
                                logger.info(
                                    f"[ANALYZE-MOD-DETAIL] Modifier for {item.get('name')}: {mod.get('name')} (ref: {mod.get('reference_handler', 'none')})"
                                )
                            else:
                                logger.warning(
                                    f"[ANALYZE-MOD-ERROR] Invalid modifier format: {mod}"
                                )

    except Exception as e:
        logger.error(f"[ANALYZE-ERROR] Error in analyze_user_input: {str(e)}")
        logger.error(f"[ANALYZE-TRACEBACK] {traceback.format_exc()}")

    # Return a consistent structure for all intents
    result = {"intent": intent, "menu_items": menu_items}

    # Add any intent-specific data
    if intent == "ask_menu":
        # Extract the menu query for ask_menu intent
        menu_tool = SushiMenuTool()
        query = input_text.strip()
        search_result = menu_tool.search_menu(query)
        result["menu_query"] = query
        result["search_results"] = search_result

    logger.info(
        f"[ANALYZE-FINAL] Final intent: '{intent}' with {len(menu_items)} menu items"
    )
    return result


def get_order_modifications(
    user_input: str, current_order_items: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Use AI to interpret order modifications from user speech.

    Args:
        user_input: The user's modification request
        current_order_items: The current order items

    Returns:
        dict: The parsed modifications
    """
    # Prepare current order structure if provided
    current_order = {"items": current_order_items or []}

    # Create an order modification agent
    agent = OrderModificationAgent()

    # Get modifications
    logger.info(
        f"[ORDER-MODIFICATIONS] Processing modification request: '{user_input}'"
    )
    modifications = agent.modify_order(current_order, user_input)

    logger.info(
        f"[ORDER-MODIFICATIONS] Found modifications: additions={len(modifications.get('additions', []))}, removals={len(modifications.get('removals', []))}, modifications={len(modifications.get('modifications', []))}"
    )
    
    return modifications