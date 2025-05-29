"""
Menu-related agent tools and utilities.
These functions help AI agents interact with the menu data.
"""

import logging
import json
from typing import Dict, List, Any, Optional
import traceback

from app.utils.menu_db_store_async import async_menu_db_store as menu_db_store

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def find_menu_item_by_name(item_name: str) -> Optional[Dict[str, Any]]:
    """
    Find a menu item by name using the database-backed menu store.
    
    Args:
        item_name: The name of the menu item to find
        
    Returns:
        The menu item if found, None otherwise
    """
    logger.info(f"[MENU-SEARCH] Searching for menu item: '{item_name}'")
    try:
        # Load menu data from DB
        menu = menu_db_store.get_menu()
        if not menu:
            logger.error("[MENU-ERROR] Failed to load menu data")
            return None

        # Normalize search
        search_name = item_name.lower().strip()

        # Search for exact match first
        for item in menu.get("items", []):
            if item.get("name", "").lower() == search_name:
                logger.info(f"[MENU-FOUND-EXACT] Found exact match: {item.get('name')}")
                return item

        # If no exact match, try fuzzy matching
        for item in menu.get("items", []):
            if search_name in item.get("name", "").lower():
                logger.info(f"[MENU-FOUND-FUZZY] Found fuzzy match: {item.get('name')}")
                return item

        logger.warning(f"[MENU-NOT-FOUND] No menu item found for: '{item_name}'")
        return None
    except Exception as e:
        logger.error(f"[MENU-ERROR] Error finding menu item: {str(e)}")
        logger.error(traceback.format_exc())
        return None


def get_menu_items() -> List[Dict[str, Any]]:
    """
    Get all menu items from the database-backed store.
    
    Returns:
        List of all menu items
    """
    try:
        # Load menu data from DB
        menu = menu_db_store.get_menu()
        if not menu:
            logger.error("[MENU-ERROR] Failed to load menu data")
            return []

        return menu.get("items", [])
    except Exception as e:
        logger.error(f"[MENU-ERROR] Error getting menu items: {str(e)}")
        logger.error(traceback.format_exc())
        return []


class SushiMenuTool:
    """
    A tool for AI agents to search and retrieve menu information.
    """
    
    def __init__(self):
        """Initialize the SushiMenuTool."""
        self.menu = menu_db_store.get_menu() or {}
    
    def search_menu(self, query: str) -> Dict[str, Any]:
        """
        Search the menu for items matching the query.
        
        Args:
            query: The search query
            
        Returns:
            A dictionary with search results
        """
        logger.info(f"[MENU-TOOL-SEARCH] Searching menu for: '{query}'")
        results = {
            "items": [],
            "categories": [],
            "query": query
        }
        
        try:
            # Normalize query
            query_lower = query.lower().strip()
            
            # Search items
            for item in self.menu.get("items", []):
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
            for category in self.menu.get("categories", []):
                category_name = category.get("name", "").lower()
                
                if query_lower in category_name:
                    results["categories"].append({
                        "name": category.get("name"),
                        "description": category.get("description")
                    })
            
            logger.info(f"[MENU-TOOL-RESULTS] Found {len(results['items'])} items and {len(results['categories'])} categories")
            return results
        except Exception as e:
            logger.error(f"[MENU-TOOL-ERROR] Error searching menu: {str(e)}")
            logger.error(traceback.format_exc())
            return results