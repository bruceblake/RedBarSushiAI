"""
Simplified agent utilities that handle graceful fallback when OpenAI is not available.
"""
import logging
from typing import Dict, List, Any, Optional

# Import our shim module that handles missing OpenAI package
from app.utils.openai_shim import (
    openai, 
    OPENAI_AVAILABLE, 
    OPENAI_AGENTS_AVAILABLE,
    fallback_analyze_user_input,
    fallback_get_order_modifications
)

# Import menu utilities
from app.utils.menu_utils import load_menu_data, find_menu_item_by_name

logger = logging.getLogger(__name__)

def analyze_user_input(text: str) -> Dict[str, Any]:
    """
    Analyze user input to determine intent and extract menu items.
    Falls back to a simplified implementation if OpenAI is not available.
    
    Args:
        text: The user's input text
        
    Returns:
        dict: Analysis with intent and menu items
    """
    if not OPENAI_AVAILABLE:
        return fallback_analyze_user_input(text)
        
    # Basic implementation that returns a preset order
    # This function would normally use OpenAI to analyze the input
    logger.info(f"Analyzing user input: {text}")
    
    # Load the menu to look up items
    menu_data = load_menu_data()
    
    # Simple keyword matching as a fallback
    keywords = ["sushi", "roll", "california", "dragon", "spicy", "tuna", "salmon"]
    
    found_items = []
    for keyword in keywords:
        if keyword.lower() in text.lower():
            # Try to find a matching menu item
            menu_item = find_menu_item_by_name(keyword)
            if menu_item:
                found_items.append({
                    "name": menu_item.get("name"),
                    "price": menu_item.get("price", 0.0),
                    "reference_handler": menu_item.get("reference_handler", ""),
                    "quantity": 1
                })
    
    return {
        "intent": "order_food" if found_items else "other",
        "menu_items": found_items,
        "confidence": 0.8 if found_items else 0.2
    }

def process_user_input(text: str) -> Dict[str, Any]:
    """
    Process user input to determine intent and extract relevant information.
    This is a wrapper around analyze_user_input that handles additional processing.
    
    Args:
        text: The user's input text
        
    Returns:
        dict: Processed input with intent and extracted information
    """
    # First analyze the basic intent and items
    analysis = analyze_user_input(text)
    
    # Additional processing for specific intents
    if analysis["intent"] == "order_food":
        # Enhance the order with details if needed
        pass
    elif analysis["intent"] == "menu_query":
        # Add query type information
        analysis["query"] = {"type": "generic"}
        if "price" in text.lower() or "cost" in text.lower() or "how much" in text.lower():
            analysis["query"]["type"] = "price"
            # Try to extract which item they're asking about
            menu_data = load_menu_data()
            for item in menu_data.get("items", []):
                item_name = item.get("name", "").lower()
                if item_name in text.lower():
                    analysis["query"]["item"] = item.get("name")
                    break
    
    # Enhance with conversation context if needed
    if "hello" in text.lower() or "hi" in text.lower() or "greeting" in text.lower():
        analysis["intent"] = "greeting"
    
    return analysis

def get_order_modifications(text: str, current_items: List[Dict[str, Any]]) -> Dict[str, List]:
    """
    Analyze text to determine requested modifications to an order.
    Falls back to a simplified implementation if OpenAI is not available.
    
    Args:
        text: The user's modification request
        current_items: The current items in the order
        
    Returns:
        dict: Modifications with additions and removals
    """
    if not OPENAI_AVAILABLE:
        return fallback_get_order_modifications(text, current_items)
    
    # Simple keyword-based modification for fallback
    logger.info(f"Processing order modification: {text}")
    
    additions = []
    removals = []
    
    # Simple keyword matching for additions
    add_keywords = ["add", "include", "want", "get", "plus"]
    for keyword in add_keywords:
        if keyword.lower() in text.lower():
            # Find what comes after the keyword
            index = text.lower().find(keyword.lower())
            after_text = text[index + len(keyword):].strip()
            
            # Try to find a menu item
            menu_item = find_menu_item_by_name(after_text)
            if menu_item:
                additions.append({
                    "name": menu_item.get("name"),
                    "price": menu_item.get("price", 0.0),
                    "reference_handler": menu_item.get("reference_handler", ""),
                    "quantity": 1
                })
    
    # Simple keyword matching for removals
    remove_keywords = ["remove", "without", "no", "delete", "take off", "cancel"]
    for keyword in remove_keywords:
        if keyword.lower() in text.lower():
            # Find what comes after the keyword
            index = text.lower().find(keyword.lower())
            after_text = text[index + len(keyword):].strip()
            
            # Check if it matches any current items
            for item in current_items:
                if after_text.lower() in item.get("name", "").lower():
                    removals.append({
                        "name": item.get("name"),
                        "quantity": 1
                    })
    
    return {
        "additions": additions,
        "removals": removals
    }

# Placeholder for the OrderParsingAgent class
class OrderParsingAgent:
    """Simple placeholder for the OrderParsingAgent class."""
    
    def __init__(self):
        pass
        
    def parse_order(self, text):
        """Fallback implementation of order parsing."""
        return analyze_user_input(text)