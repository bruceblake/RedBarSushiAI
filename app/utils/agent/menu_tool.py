"""
Menu tool for searching, retrieving and suggesting menu items.
"""

import json
import time
import logging
from typing import Dict, List, Any
import openai

from app.utils.menu_utils import load_menu_data, find_menu_item_by_name
from app.utils.agent.config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

class SushiMenuTool:
    """A tool for querying the sushi menu."""

    def __init__(self):
        """Initialize the tool with menu data."""
        self.menu_data = load_menu_data()
        self.current_conversation = []  # To track conversation context
        self.last_refresh_time = time.time()

    def search_menu(self, query: str) -> Dict[str, Any]:
        """
        Search the menu for items matching the query.

        Args:
            query: The search query

        Returns:
            dict: The search results
        """
        # Add the query to the conversation context
        self.current_conversation.append({"role": "user", "content": query})
        context = {"conversation": self.current_conversation}
        
        # First try to find exact matches
        item = find_menu_item_by_name(query)
        if item:
            return {"found": True, "items": [item], "query": query}

        # If exact match fails, try AI matching
        try:
            # Import here to avoid circular imports
            from app.utils.menu_matcher import find_menu_item_ai
            
            ai_match = find_menu_item_ai(query, check_availability=False, context=context)
            if ai_match:
                logger.info(f"[MENU-TOOL] AI matcher found: {ai_match.get('name')} for '{query}'")
                return {"found": True, "items": [ai_match], "query": query}
        except Exception as e:
            logger.error(f"[MENU-TOOL] Error in AI matching: {str(e)}")
            # Continue with fallback if AI matching fails

        # Fallback to traditional scoring system
        results = []
        scored_items = []
        query_lower = query.lower().strip()

        # Get all menu items and evaluate with a scoring system
        for item in self.menu_data.get("items", []):
            item_name = item.get("name", "").lower()

            # Skip empty names
            if not item_name:
                continue

            # Calculate match score
            score = 0

            # Check for direct matches
            if item_name == query_lower:
                score = 100
            elif query_lower in item_name:
                # Longer query matches are better
                score = 80 + min(len(query_lower), 15)
            elif item_name in query_lower:
                # If menu item is contained in query
                match_ratio = len(item_name) / len(query_lower)
                score = 60 + int(match_ratio * 20)

            # Word-level matching
            if score < 30:  # Only do word matching for lower-scoring matches
                query_words = set(query_lower.split())
                item_words = set(item_name.split())

                # Words in common
                common_words = query_words.intersection(item_words)

                if common_words:
                    # Calculate scores based on word overlap
                    word_match_ratio = (
                        len(common_words) / len(item_words) if item_words else 0
                    )
                    query_coverage = (
                        len(common_words) / len(query_words) if query_words else 0
                    )

                    # Combined score with higher weight for query coverage
                    word_score = int(
                        (word_match_ratio * 0.4 + query_coverage * 0.6) * 50
                    )
                    score = max(score, word_score)

            # Only include reasonably good matches
            if score >= 30:
                scored_items.append((item, score))

        # Sort by score
        scored_items.sort(key=lambda x: x[1], reverse=True)

        # Take the top results
        results = [item for item, _ in scored_items[:5]]

        return {
            "found": len(results) > 0,
            "items": results,
            "query": query,
            "debug_info": {
                "top_matches": (
                    [(item.get("name"), score) for item, score in scored_items[:3]]
                    if scored_items
                    else []
                )
            },
        }

    def get_menu_categories(self) -> List[str]:
        """
        Get all menu categories.

        Returns:
            list: All menu categories
        """
        categories = set()
        for item in self.menu_data.get("items", []):
            category = item.get("category")
            if category:
                categories.add(category)
        return sorted(list(categories))

    def get_items_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Get all items in a category.

        Args:
            category: The category name

        Returns:
            list: All items in the category
        """
        results = []
        category_lower = category.lower().strip()

        for item in self.menu_data.get("items", []):
            item_category = item.get("category", "").lower()
            if item_category == category_lower:
                results.append(item)

        return results

    def get_details(self, item_name: str) -> Dict[str, Any]:
        """
        Get detailed information about a menu item with its modifiers.

        Args:
            item_name: The menu item name

        Returns:
            dict: Detailed item information including all available modifiers
        """
        # Ensure we have fresh menu data
        if time.time() - self.last_refresh_time > 300:  # Refresh every 5 minutes
            self.menu_data = load_menu_data(force_refresh=True)
            self.last_refresh_time = time.time()
            
        # First find the item 
        item = find_menu_item_by_name(item_name)
        if not item:
            # If exact match fails, try AI matching
            try:
                # Import here to avoid circular imports
                from app.utils.menu_matcher import find_menu_item_ai
                
                ai_match = find_menu_item_ai(item_name, check_availability=False)
                if ai_match:
                    item = ai_match
                else:
                    return {"found": False}
            except Exception as e:
                logger.error(f"[MENU-TOOL] Error in AI matching: {str(e)}")
                return {"found": False}
            
        # Get modifiers for this item
        mod_groups = []
        
        # Get all modifier groups in the menu
        all_modifier_groups = self.menu_data.get("modifierGroups", [])
        all_modifiers = self.menu_data.get("modifiers", [])
        
        # Check if item has modifiers through modifierGroups or modifierGroupIds
        item_modifier_group_ids = item.get("modifierGroups", []) or item.get("modifierGroupIds", [])
        
        # Process modifier groups - only using actual data from the menu
        for group_id in item_modifier_group_ids:
            # Find the modifier group
            group = next((g for g in all_modifier_groups if g.get("id") == group_id), None)
            if group:
                group_mods = []
                
                # Get all modifiers for this group
                modifier_ids = group.get("modifiers", []) or group.get("subProducts", [])
                for mod_id in modifier_ids:
                    # Find modifier
                    modifier = next((m for m in all_modifiers if m.get("id") == mod_id or m.get("reference_handler") == mod_id), None)
                    if modifier:
                        group_mods.append(modifier)
                
                if group_mods:
                    mod_group = {
                        "name": group.get("name"),
                        "id": group.get("id"),
                        "min": group.get("min", 0),
                        "max": group.get("max", 0),
                        "modifiers": group_mods
                    }
                    mod_groups.append(mod_group)
        
        return {
            "found": True,
            "item": item,
            "modifiers": mod_groups
        }
        
    def suggest_modifiers(self, item_name: str) -> Dict[str, Any]:
        """
        Intelligently suggest modifiers for a menu item. Returns appropriate suggestions
        based on the menu item type and available modifier groups.
        
        Args:
            item_name: The menu item name to get suggestions for
            
        Returns:
            dict: Suggested modifiers with friendly descriptions
        """
        # Get item details including available modifiers
        item_details = self.get_details(item_name)
        
        if not item_details.get("found"):
            return {"found": False, "suggestions": []}
            
        item = item_details.get("item", {})
        modifier_groups = item_details.get("modifiers", [])
        
        if not modifier_groups:
            return {"found": True, "item": item, "suggestions": []}
            
        # Build smart suggestions based on modifier groups
        suggestions = []
        item_name_lower = item.get("name", "").lower()
        
        for group in modifier_groups:
            group_name = group.get("name", "")
            group_required = group.get("min", 0) > 0
            group_type = group_name.lower()
            mods = group.get("modifiers", [])
            
            # Skip if no modifiers
            if not mods:
                continue
                
            # Create appropriate suggestion based on modifier group type 
            # Use simple pattern matching on the group name for better safety
            suggestion_type = "general"
            prompt = f"Would you like to customize your {item.get('name')} with any {group_name}?"
            
            # Pattern match on group name but keep it simple and safe
            if any(term in group_type for term in ["cook", "temperature", "done", "rare", "well", "medium"]):
                suggestion_type = "cooking_preference"
                prompt = f"How would you like your {item.get('name')} cooked?"
            elif any(term in group_type for term in ["sauce", "dressing"]):
                suggestion_type = "sauce"
                prompt = f"Would you like any special sauce with your {item.get('name')}?"
            elif any(term in group_type for term in ["side"]):
                suggestion_type = "side"
                prompt = f"Would you like to add any sides to your {item.get('name')}?"
            elif any(term in group_type for term in ["spic", "heat"]):
                suggestion_type = "spice"
                prompt = f"How spicy would you like your {item.get('name')}?"
                
            suggestion = {
                "type": suggestion_type,
                "prompt": prompt,
                "group": group_name,
                "required": group_required,
                "options": [mod.get("name") for mod in mods]
            }
            suggestions.append(suggestion)
        
        # Sort suggestions - required first, then by type importance
        type_order = {"cooking_preference": 0, "spice": 1, "side": 2, "sauce": 3, "general": 4}
        
        # Sort by required status first, then by type importance
        suggestions.sort(key=lambda x: (not x.get("required"), type_order.get(x.get("type"), 5)))
        
        return {
            "found": True,
            "item": item,
            "suggestions": suggestions
        }
    
    def generate_modifier_prompt(self, item_name: str) -> str:
        """
        Generate a prompt to suggest modifiers for an item.
        
        Args:
            item_name: The menu item name
            
        Returns:
            str: Prompt suggesting modifiers
        """
        # Get structured modifier suggestions
        suggestion_data = self.suggest_modifiers(item_name)
        
        if not suggestion_data.get("found") or not suggestion_data.get("suggestions"):
            return f"Would you like any modifications for your {item_name}?"
            
        # Template-based prompt
        prompts = []
        
        # Add up to 2 suggestion prompts (prioritize required modifiers)
        for suggestion in suggestion_data.get("suggestions", [])[:2]:
            prompts.append(suggestion.get("prompt"))
            
        if prompts:
            return " ".join(prompts)
        
        return f"Would you like any modifications for your {item_name}?"
        
    def ai_match_item(self, item_name: str) -> Dict[str, Any]:
        """
        Match an item using AI-based matching.
        
        Args:
            item_name: The name or description of the item to match
            
        Returns:
            dict: The match results
        """
        self.current_conversation.append({"role": "user", "content": f"Find menu item: {item_name}"})
        context = {"conversation": self.current_conversation}
        
        try:
            # Import here to avoid circular imports
            from app.utils.menu_matcher import find_menu_item_ai
            
            ai_match = find_menu_item_ai(item_name, check_availability=False, context=context)
            if ai_match:
                logger.info(f"[MENU-TOOL] AI matcher found: {ai_match.get('name')} for '{item_name}'")
                return {
                    "found": True,
                    "item": ai_match,
                    "confidence": "high",
                    "matching_type": "ai_match"
                }
        except Exception as e:
            logger.error(f"[MENU-TOOL] Error in AI matching: {str(e)}")
            
        # If AI matching fails, try exact match as fallback
        item = find_menu_item_by_name(item_name)
        if item:
            return {
                "found": True,
                "item": item,
                "confidence": "exact",
                "matching_type": "exact_match"
            }
            
        # No match found
        return {"found": False, "item_name": item_name}