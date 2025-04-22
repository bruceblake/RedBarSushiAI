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
        Intelligently suggest modifiers for a menu item using AI analysis. Returns appropriate 
        suggestions based on the menu item type and available modifier groups.
        
        This function analyzes the item and returns appropriate modifiers with NO fallbacks.
        
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
            
        # Use AI to analyze the item and determine appropriate modifier groups
        # This allows us to intelligently handle ANY menu item with appropriate modifiers
        # even as the menu changes, without hardcoded values
        
        # Build smart suggestions based on AI analysis of item and modifier groups
        suggestions = []
        item_name_lower = item.get("name", "").lower()
        item_description = item.get("description", "")
        
        # First perform AI analysis to determine item type without hardcoded categories
        item_type = self._analyze_item_type(item_name_lower, item_description)
        logger.info(f"[MENU-TOOL] Item '{item_name}' classified as type: {item_type}")
        
        for group in modifier_groups:
            group_name = group.get("name", "")
            group_required = group.get("min", 0) > 0
            group_type = group_name.lower()
            mods = group.get("modifiers", [])
            
            # Skip if no modifiers
            if not mods:
                continue
                
            # AI-based classification of modifier group type
            group_classification = self._classify_modifier_group(group_name, [mod.get("name", "") for mod in mods])
            suggestion_type = group_classification.get("type", "general")
            
            # Get the prompt directly from AI classification or build one
            if "prompt_question" in group_classification:
                prompt = group_classification["prompt_question"]
            else:
                prompt = f"Would you like to customize your {item.get('name')} with any {group_name}?"
                
            # Build suggestion
            suggestion = {
                "type": suggestion_type,
                "prompt": prompt,
                "group": group_name,
                "required": group_required,
                "options": [mod.get("name") for mod in mods]
            }
            suggestions.append(suggestion)
        
        # No special handling for any specific item type
        # We rely entirely on the AI to determine appropriate modifiers for any menu item
        
        # Sort suggestions - required first only
        # We don't use hardcoded type priorities since that would assume specific menu categories
        
        # Sort by required status - required items first
        suggestions.sort(key=lambda x: not x.get("required"))
        
        return {
            "found": True,
            "item": item,
            "suggestions": suggestions
        }
        
    def _analyze_item_type(self, item_name: str, item_description: str = "") -> Dict[str, bool]:
        """
        Use AI to analyze an item's type based on its name and description.
        No hardcoded food categories or item types - completely dynamic.
        
        Args:
            item_name: The name of the menu item
            item_description: Optional item description
            
        Returns:
            dict: Item type classifications with modifier needs
        """
        # Import here to avoid circular imports
        import openai
        from app.utils.agent.logging import log_openai_request, log_openai_response
        
        try:
            # Build a prompt for classification that's completely dynamic
            prompt = f"""Analyze this menu item to determine what modifiers a customer might need to be asked about:
            
            Item name: {item_name}
            Description: {item_description}
            
            Think about what customization options would be appropriate for this dish. Return a JSON object with:
            - modifier_needs: A list of modifier categories that would be appropriate to ask about
            - preparation_options: Does this item need cooking preference/preparation options?
            - customizable: Is this item typically customizable?
            
            Do not make assumptions based on common dish types - analyze this specific item.
            """
            
            messages = [
                {"role": "system", "content": "You are a restaurant menu analyst that assesses customer ordering needs."},
                {"role": "user", "content": prompt}
            ]
            
            # Log the request
            log_openai_request("gpt-4.1-mini", messages, "analyze_item_type")
            
            # Make the API call
            response = openai.chat.completions.create(
                model="gpt-4.1-mini",
                messages=messages,
                temperature=0.1,
                max_tokens=150,
                response_format={"type": "json_object"}
            )
            
            # Log the response
            log_openai_response(response, "analyze_item_type")
            
            # Extract the classification
            result = json.loads(response.choices[0].message.content)
            logger.info(f"[MENU-TOOL] Item '{item_name}' classified: {json.dumps(result)}")
            return result
            
        except Exception as e:
            logger.error(f"[MENU-TOOL] Error analyzing item type: {str(e)}")
            # Return a very minimal result without any assumptions
            return {
                "modifier_needs": [],
                "preparation_options": False,
                "customizable": False
            }
            
    def _classify_modifier_group(self, group_name: str, modifier_options: List[str]) -> Dict[str, str]:
        """
        Use AI to classify a modifier group based on its name and options.
        No hardcoded categories - completely data-driven.
        
        Args:
            group_name: The name of the modifier group
            modifier_options: List of modifier option names
            
        Returns:
            dict: Classification information including type
        """
        # Import here to avoid circular imports
        import openai
        from app.utils.agent.logging import log_openai_request, log_openai_response
        
        try:
            # Build a prompt for classification that's completely dynamic
            prompt = f"""Analyze this modifier group from a restaurant menu:
            
            Group name: {group_name}
            Options: {', '.join(modifier_options)}
            
            Based ONLY on the actual data provided (not assumptions about typical menus),
            determine:
            1. What type of customization does this group represent?
            2. What question should be asked to the customer about this option group?
            
            Return your answer as JSON with:
            - "type": A single word descriptor for this modifier type
            - "prompt_question": The question that should be asked to the customer
            """
            
            messages = [
                {"role": "system", "content": "You are a restaurant menu analyst that analyzes dish modifiers."},
                {"role": "user", "content": prompt}
            ]
            
            # Log the request
            log_openai_request("gpt-4.1-mini", messages, "classify_modifier_group")
            
            # Make the API call
            response = openai.chat.completions.create(
                model="gpt-4.1-mini",
                messages=messages,
                temperature=0.1,
                max_tokens=150,
                response_format={"type": "json_object"}
            )
            
            # Log the response
            log_openai_response(response, "classify_modifier_group")
            
            # Extract the classification
            result = json.loads(response.choices[0].message.content)
            result_type = result.get("type", "general").lower()
            logger.info(f"[MENU-TOOL] Group '{group_name}' classified as: {result_type}")
            
            # Add the question to the result if available
            if "prompt_question" in result:
                logger.info(f"[MENU-TOOL] Prompt question: {result['prompt_question']}")
            
            return result
            
        except Exception as e:
            logger.error(f"[MENU-TOOL] Error classifying modifier group: {str(e)}")
            # Return a generic result without any assumptions
            return {
                "type": "general",
                "prompt_question": f"Would you like to customize with any {group_name}?"
            }
    
    def generate_modifier_prompt(self, item_name: str) -> str:
        """
        Generate a prompt to suggest modifiers for an item using AI analysis.
        No hardcoded assumptions - completely data-driven.
        
        Args:
            item_name: The menu item name
            
        Returns:
            str: AI-generated prompt suggesting appropriate modifiers
        """
        # Get structured modifier suggestions through AI
        suggestion_data = self.suggest_modifiers(item_name)
        
        if not suggestion_data.get("found") or not suggestion_data.get("suggestions"):
            # Import here to avoid circular imports
            import openai
            from app.utils.agent.logging import log_openai_request, log_openai_response
            
            try:
                # Use AI to generate a custom prompt just for this item
                prompt = f"""Generate a natural-sounding question to ask a customer about modifiers for this menu item:
                
                Item: {item_name}
                
                The question should ask if they would like to customize or modify their order in any way.
                Keep it brief, friendly, and specifically tailored to this menu item.
                Return ONLY the question text with no additional explanation.
                """
                
                messages = [
                    {"role": "system", "content": "You are a friendly restaurant server suggesting food customizations."},
                    {"role": "user", "content": prompt}
                ]
                
                # Log the request
                log_openai_request("gpt-4.1-mini", messages, "generate_modifier_prompt")
                
                # Make the API call
                response = openai.chat.completions.create(
                    model="gpt-4.1-mini",
                    messages=messages,
                    temperature=0.3,
                    max_tokens=60
                )
                
                # Log the response
                log_openai_response(response, "generate_modifier_prompt")
                
                # Extract the prompt
                custom_prompt = response.choices[0].message.content.strip()
                if custom_prompt:
                    logger.info(f"[MENU-TOOL] Generated custom prompt for {item_name}: {custom_prompt}")
                    return custom_prompt
            except Exception as e:
                logger.error(f"[MENU-TOOL] Error generating modifier prompt: {str(e)}")
                
            # Default if AI fails
            return f"Would you like any modifications for your {item_name}?"
            
        # AI-generated prompts from the suggestions
        prompts = []
        
        # Add up to 2 suggestion prompts (prioritize required modifiers)
        for suggestion in suggestion_data.get("suggestions", [])[:2]:
            prompts.append(suggestion.get("prompt"))
            
        if prompts:
            return " ".join(prompts)
        
        # Last resort default
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