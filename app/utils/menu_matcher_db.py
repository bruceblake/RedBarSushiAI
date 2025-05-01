"""
Menu item matching using AI to find the best match from database.
This is an updated version of menu_matcher.py that uses the database-backed menu store.
"""

import os
import json
import logging
import traceback
import time
from typing import Dict, List, Any, Optional, Tuple
import openai

from app.utils.menu_utils_db import load_menu_data
from app.utils.agent_utils import log_openai_request, log_openai_response

logger = logging.getLogger(__name__)


class MenuMatcher:
    """
    AI-powered menu item matcher that finds the best match for a customer request
    and facilitates customer interaction to clarify orders.
    """

    def __init__(self):
        """Initialize the menu matcher."""
        self._menu_data = None  # Will be loaded on first use
        self.model = "gpt-4.1-mini"  # Can be configured based on needs
        
    @property
    def menu_data(self):
        """Lazy-load menu data only when actually needed."""
        if self._menu_data is None:
            self._menu_data = load_menu_data()
        return self._menu_data
        
    @menu_data.setter
    def menu_data(self, value):
        """Setter for menu_data property."""
        self._menu_data = value

    def find_menu_item(
        self,
        item_name: str,
        check_availability: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Find a menu item based on the given name, using multiple matching strategies.

        Args:
            item_name: Name of the item requested by the customer
            check_availability: Only return available items if True
            context: Additional context about the order/conversation

        Returns:
            dict or None: The matched menu item if found, None otherwise
        """
        if not item_name:
            return None

        # Performance optimization: Try matching strategies in order of increasing complexity/cost

        # 1. First try exact match (fastest)
        exact_match = self._find_exact_match(item_name, check_availability)
        if exact_match:
            logger.info(
                f"[MENU-MATCHER] Found exact match for '{item_name}': {exact_match.get('name')}"
            )
            return exact_match

        # 2. Then try fast fuzzy matching (local algorithms, still very quick)
        fuzzy_match = self._find_fast_fuzzy_match(item_name, check_availability)
        if fuzzy_match:
            logger.info(
                f"[MENU-MATCHER] Found fast fuzzy match for '{item_name}': {fuzzy_match.get('name')}"
            )
            return fuzzy_match

        # 3. Only if local matching fails, use AI (most expensive/slow, but most powerful)
        logger.info(
            f"[MENU-MATCHER] No local match found, using AI matching for '{item_name}'"
        )
        return self._find_ai_match(item_name, check_availability, context)

    def _find_exact_match(
        self, item_name: str, check_availability: bool
    ) -> Optional[Dict[str, Any]]:
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

    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """
        Calculate the Levenshtein distance between two strings.
        This is a measure of string similarity - lower values mean more similar strings.

        Args:
            s1: First string to compare
            s2: Second string to compare

        Returns:
            int: The edit distance between the strings
        """
        # Optimization: early return for identical strings
        if s1 == s2:
            return 0

        # Handle empty strings
        if len(s1) == 0:
            return len(s2)
        if len(s2) == 0:
            return len(s1)

        # Create matrix of size (len(s1)+1) x (len(s2)+1)
        matrix = [[0 for _ in range(len(s2) + 1)] for _ in range(len(s1) + 1)]

        # Fill the first row and column
        for i in range(len(s1) + 1):
            matrix[i][0] = i
        for j in range(len(s2) + 1):
            matrix[0][j] = j

        # Fill the rest of the matrix
        for i in range(1, len(s1) + 1):
            for j in range(1, len(s2) + 1):
                cost = 0 if s1[i - 1] == s2[j - 1] else 1
                matrix[i][j] = min(
                    matrix[i - 1][j] + 1,  # deletion
                    matrix[i][j - 1] + 1,  # insertion
                    matrix[i - 1][j - 1] + cost,  # substitution
                )

        return matrix[len(s1)][len(s2)]

    def _calculate_similarity(self, s1: str, s2: str) -> float:
        """
        Calculate similarity score between two strings based on Levenshtein distance.
        Returns a value between 0 and 1, where 1 means identical strings.

        Args:
            s1: First string
            s2: Second string

        Returns:
            float: Similarity score between 0 and 1
        """
        # Handle empty strings
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0

        # Calculate Levenshtein distance
        distance = self._levenshtein_distance(s1, s2)
        max_len = max(len(s1), len(s2))

        # Convert distance to similarity score (1 - normalized distance)
        if max_len == 0:
            return 0.0
        return 1.0 - (distance / max_len)

    def _find_fast_fuzzy_match(
        self, item_name: str, check_availability: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Use fast local fuzzy matching instead of AI for quicker responses."""
        if not item_name:
            return None

        # Normalize the input
        item_name_lower = item_name.lower()
        item_name_normalized = item_name_lower.replace(" ", "")
        item_name_terms = set(item_name_lower.split())

        # Track possible matches with their scores
        matches = {
            "exact": None,
            "normalized": None,
            "substring": None,
            "terms": None,
            "levenshtein": None,
        }
        scores = {
            "exact": 0,
            "normalized": 0,
            "substring": 0,
            "terms": 0,
            "levenshtein": 0,
        }

        # Fast loop through all menu items
        for item in self.menu_data.get("items", []):
            # Skip category items
            if item.get("is_category", False):
                continue

            # Skip unavailable items if checking availability
            if check_availability and (
                not item.get("available", True) or item.get("snoozed", False)
            ):
                continue

            menu_item_name = item.get("name", "")
            menu_item_lower = menu_item_name.lower()

            # Check for exact match first (fastest check)
            if menu_item_lower == item_name_lower:
                logger.info(
                    f"[MENU-MATCHER] Found exact match: '{item_name}' = '{menu_item_name}'"
                )
                return item  # Return immediately on exact match

            # Check for normalized match (spaces removed)
            menu_item_normalized = menu_item_lower.replace(" ", "")
            if menu_item_normalized == item_name_normalized:
                matches["normalized"] = item
                scores["normalized"] = 1.0  # Perfect normalized match

            # Check for substring match
            if item_name_lower in menu_item_lower:
                # Item is contained in menu item - higher score for longer matches
                substring_score = len(item_name_lower) / len(menu_item_lower)
                if substring_score > scores["substring"]:
                    matches["substring"] = item
                    scores["substring"] = substring_score
            elif menu_item_lower in item_name_lower:
                # Menu item is contained in item - lower score
                substring_score = (
                    len(menu_item_lower) / len(item_name_lower) * 0.8
                )  # Slightly lower weight
                if substring_score > scores["substring"]:
                    matches["substring"] = item
                    scores["substring"] = substring_score

            # Check for term-based match (improved to handle partial terms)
            menu_item_terms = set(menu_item_lower.split())

            # Check for common terms
            common_terms = item_name_terms.intersection(menu_item_terms)

            # Also check for partial term matches (like "spcy" matching "spicy")
            partial_matches = 0
            for input_term in item_name_terms:
                if not input_term:
                    continue
                for menu_term in menu_item_terms:
                    if not menu_term:
                        continue
                    # Check if the term is a substring or has high character overlap
                    if (
                        input_term in menu_term
                        or menu_term in input_term
                        or self._calculate_similarity(input_term, menu_term) >= 0.7
                    ):
                        partial_matches += 1
                        break

            # Calculate score based on both exact and partial matches
            if common_terms or partial_matches > 0:
                # Term match score is based on both exact matches and partial matches
                exact_match_score = (
                    len(common_terms) / max(len(item_name_terms), len(menu_item_terms))
                    if menu_item_terms
                    else 0
                )
                partial_match_score = (
                    partial_matches / len(item_name_terms) if item_name_terms else 0
                )

                # Combine scores with higher weight for exact matches
                term_score = (exact_match_score * 0.7) + (partial_match_score * 0.3)

                if term_score > scores["terms"]:
                    matches["terms"] = item
                    scores["terms"] = term_score

            # Only calculate Levenshtein similarity if there's potential for a match
            # (i.e., length difference is not too large)
            if abs(len(menu_item_lower) - len(item_name_lower)) <= min(
                len(menu_item_lower), len(item_name_lower)
            ):
                similarity = self._calculate_similarity(
                    menu_item_lower, item_name_lower
                )
                # Only consider similarity matches above a threshold
                if similarity >= 0.7 and similarity > scores["levenshtein"]:
                    matches["levenshtein"] = item
                    scores["levenshtein"] = similarity

        # Return the best match based on priority and score
        # Normalized match (removing spaces) is very reliable
        if matches["normalized"]:
            logger.info(
                f"[MENU-MATCHER] Found normalized match: '{item_name}' ≈ '{matches['normalized'].get('name')}' (spaces removed)"
            )
            return matches["normalized"]

        # Term match is good for abbreviations and word variations
        if matches["terms"] and scores["terms"] >= 0.6:
            logger.info(
                f"[MENU-MATCHER] Found high-confidence term match: '{item_name}' ≈ '{matches['terms'].get('name')}' (score: {scores['terms']:.2f})"
            )
            return matches["terms"]

        # Levenshtein match with high similarity is reliable
        if matches["levenshtein"] and scores["levenshtein"] >= 0.8:
            logger.info(
                f"[MENU-MATCHER] Found similarity match: '{item_name}' ≈ '{matches['levenshtein'].get('name')}' (similarity: {scores['levenshtein']:.2f})"
            )
            return matches["levenshtein"]

        # Substring match can be good for partial menu item names
        if matches["substring"] and scores["substring"] >= 0.7:
            logger.info(
                f"[MENU-MATCHER] Found substring match: '{item_name}' ≈ '{matches['substring'].get('name')}' (score: {scores['substring']:.2f})"
            )
            return matches["substring"]

        # Lower confidence term match
        if matches["terms"] and scores["terms"] >= 0.4:
            logger.info(
                f"[MENU-MATCHER] Found term-based match: '{item_name}' ≈ '{matches['terms'].get('name')}' (score: {scores['terms']:.2f})"
            )
            return matches["terms"]

        # Lower confidence Levenshtein match as last resort
        if matches["levenshtein"] and scores["levenshtein"] >= 0.7:
            logger.info(
                f"[MENU-MATCHER] Found low-confidence similarity match: '{item_name}' ≈ '{matches['levenshtein'].get('name')}' (similarity: {scores['levenshtein']:.2f})"
            )
            return matches["levenshtein"]

        logger.warning(f"[MENU-MATCHER] No fuzzy match found for '{item_name}'")
        return None

    def _find_ai_match(
        self,
        item_name: str,
        check_availability: bool,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Use AI to find the best match for the item name in the menu."""
        # We already tried fast matching in the main find_menu_item method,
        # so go directly to AI matching for better performance
        try:
            # First check if input is asking about menu in general - use advanced pattern matching
            # Define core patterns about menu inquiries (what's on menu, etc.)
            menu_core_patterns = [
                "menu", "on the menu", "in the menu", "have on", "serve", "offer", "available",
                "options", "dishes", "food", "choices", "specials", "popular", "best", "recommend"
            ]
            
            # Define question patterns (what do you, can you tell me, etc.)
            question_patterns = [
                "what", "tell me", "show me", "can you", "could you", "would you", "may i", "should i",
                "give me", "list", "i want to know", "i'd like to know", "tell us", "yeah", "yes"
            ]
            
            # Build advanced combined pattern matching
            menu_question_patterns = [
                # Direct menu questions
                "what's on the menu", "what is on the menu", "what do you have", "what's in the menu",
                "tell me about the menu", "what food do you have", "menu items", "what can i order",
                "do you have", "what dishes", "what are the options", "tell me what's",
                "what do you offer", "show me the menu", "i want to see the menu",
                
                # Generic inquiries that likely refer to menu
                "tell me some", "what are your", "what's available", "what is available",
                "tell me some things", "what kind of", "tell me what", "could you tell me",
                "can you tell me", "yeah can you tell me", "yes tell me", 
                
                # Common order starters
                "i want to order", "i would like to order", "i want to get", "i would like to get",
                "i want to try", "i would like to try", "what should i get",
                
                # Common menu browsing questions 
                "any specials", "what's good", "what's popular", "what do you recommend",
                "what should i order", "what's the best", "what is the best"
            ]
            
            # Check if this is a general menu inquiry using basic pattern matching
            is_menu_inquiry = False
            item_name_lower = item_name.lower().strip()
            
            # First try direct pattern matching
            for pattern in menu_question_patterns:
                if pattern in item_name_lower:
                    logger.info(f"[MENU-MATCHER] Detected general menu inquiry with direct pattern: '{pattern}' in '{item_name}'")
                    is_menu_inquiry = True
                    break
                    
            # If no direct match, try more advanced pattern matching with combinations
            if not is_menu_inquiry:
                # Check for a combination of question pattern + menu core pattern
                for q_pattern in question_patterns:
                    if q_pattern in item_name_lower:
                        for m_pattern in menu_core_patterns:
                            if m_pattern in item_name_lower:
                                logger.info(f"[MENU-MATCHER] Detected general menu inquiry with combined patterns: '{q_pattern}' + '{m_pattern}' in '{item_name}'")
                                is_menu_inquiry = True
                                break
                        if is_menu_inquiry:
                            break
            
            # Special case detection for very short inquiries that are likely menu related
            if not is_menu_inquiry and len(item_name_lower.split()) <= 3:
                short_menu_patterns = ["menu", "food", "eat", "order", "options", "items", "dishes"]
                for pattern in short_menu_patterns:
                    if pattern in item_name_lower:
                        logger.info(f"[MENU-MATCHER] Detected short menu inquiry: '{pattern}' in '{item_name}'")
                        is_menu_inquiry = True
                        break
                        
            # Log the final determination        
            if is_menu_inquiry:
                logger.info(f"[MENU-MATCHER] Handling as general menu inquiry: '{item_name}'")
            else:
                logger.info(f"[MENU-MATCHER] Not a general menu inquiry, proceeding with item matching: '{item_name}'")
                    
            if is_menu_inquiry:
                # For general menu questions, don't try to find a specific item
                # Return None to let the calling function handle this as a general menu inquiry
                logger.info(f"[MENU-MATCHER] Handling as general menu inquiry, not specific item request")
                return None
                
            # Check if we have menu items to work with
            menu_items = []
            for item in self.menu_data.get("items", []):
                if not item.get("is_category", False) and (
                    not check_availability
                    or (item.get("available", True) and not item.get("snoozed", False))
                ):
                    menu_items.append(
                        {
                            "name": item.get("name", ""),
                            "category": item.get("category", ""),
                            "description": item.get("description", ""),
                            "price": item.get("price", 0.0),
                        }
                    )

            # No items to match against
            if not menu_items:
                logger.warning(
                    "[MENU-MATCHER] No menu items available to match against"
                )
                # Try to reload menu data in case it wasn't loaded properly
                # Force refresh from database to bypass any cache issues
                self._menu_data = load_menu_data(force_refresh=True)

                # If reload didn't help, return None
                if not self.menu_data.get("items", []):
                    logger.error("[MENU-MATCHER] No menu items available after reload")
                    return None

                # After reload, return to the main matching function
                # to try all matching strategies again
                logger.info(f"[MENU-MATCHER] Retrying match after menu reload")
                return self.find_menu_item(item_name, check_availability, context)

            # Build concise menu item list - only send essential data to reduce token usage
            simplified_menu = [{"name": item["name"]} for item in menu_items]

            # Build the messages for the API call
            messages = [
                {
                    "role": "system",
                    "content": """You are a restaurant menu matcher that matches customer requests to menu items.
                    Rules:
                    1. Match similar words regardless of spaces ("hamburger" matches "Ham Burger")
                    2. Match similar words regardless of case or punctuation
                    3. Handle misspellings and typos (e.g., "califorrnia" should match "California")
                    4. Consider common food abbreviations (e.g., "cali roll" matches "California Roll")
                    5. Return ONLY the exact menu item name that best matches, no explanation
                    
                    Your response should be just the menu item name - nothing else. Never add quotes, colons, explanations, or anything other than the exact menu item name.
                    """,
                },
                {
                    "role": "user",
                    "content": f"Customer requested: '{item_name}'\n\nChoose from these menu items ONLY:\n{json.dumps(simplified_menu)}\n\nReturn ONLY the exact menu item name that best matches. Don't add any quotes, prefixes, or explanation.",
                },
            ]

            # Log the request
            log_openai_request(self.model, messages, "menu_ai_matcher")

            # Make the API call with minimal tokens
            response = openai.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.5,  # Very low temp for deterministic results
                max_tokens=500,  # Keep responses very short
            )

            # Log the response
            log_openai_response(response, "menu_ai_matcher")

            # Extract the matched item name from the response
            matched_item_name = response.choices[0].message.content.strip()

            # Clean up the response (AI model shouldn't add these, but just in case)
            # Remove common response patterns like "Menu Item: California Roll"
            if ":" in matched_item_name:
                matched_item_name = matched_item_name.split(":", 1)[1].strip()
            # Remove quotation marks
            if matched_item_name.startswith('"') and matched_item_name.endswith('"'):
                matched_item_name = matched_item_name[1:-1].strip()
            # Remove any prefix like "The best match is" or "I recommend"
            prefixes = ["the best match is", "i recommend", "best match:", "match:"]
            for prefix in prefixes:
                if matched_item_name.lower().startswith(prefix):
                    matched_item_name = matched_item_name[len(prefix) :].strip()

            logger.info(
                f"[MENU-MATCHER] AI suggested match: '{matched_item_name}' for request '{item_name}'"
            )

            # Two-pass matching to find the item:
            # 1. First try exact case-insensitive match
            for item in self.menu_data.get("items", []):
                if (
                    not item.get("is_category", False)
                    and item.get("name", "").lower() == matched_item_name.lower()
                ):
                    logger.info(
                        f"[MENU-MATCHER] Found exact AI-matched item in menu: {item.get('name')}"
                    )
                    return item

            # 2. If exact match fails, try fuzzy matching with the AI's suggestion
            # This handles cases where the AI might return something close but not exact
            logger.info(
                f"[MENU-MATCHER] No exact match for AI suggestion, trying fuzzy matching"
            )
            best_match = None
            best_similarity = 0

            for item in self.menu_data.get("items", []):
                if item.get("is_category", False):
                    continue

                # Skip unavailable items if checking availability
                if check_availability and (
                    not item.get("available", True) or item.get("snoozed", False)
                ):
                    continue

                menu_item_name = item.get("name", "").lower()
                similarity = self._calculate_similarity(
                    menu_item_name, matched_item_name.lower()
                )

                if (
                    similarity > best_similarity and similarity >= 0.8
                ):  # Only consider high similarity matches
                    best_similarity = similarity
                    best_match = item

            if best_match:
                logger.info(
                    f"[MENU-MATCHER] Found fuzzy match for AI suggestion: '{best_match.get('name')}' (similarity: {best_similarity:.2f})"
                )
                return best_match

            # If all else fails, use our local fuzzy matcher on the original query
            logger.info(
                f"[MENU-MATCHER] AI matching unsuccessful, trying local fuzzy matching on original query"
            )
            return self._find_fast_fuzzy_match(item_name, check_availability)

        except Exception as e:
            logger.error(f"[MENU-MATCHER] Error in AI matching: {str(e)}")
            logger.error(f"[MENU-MATCHER] Traceback: {traceback.format_exc()}")
            return None

    def interactive_order_resolution(
        self, customer_request: str, context: Dict[str, Any] = None, session_id: str = None
    ) -> Dict[str, Any]:
        """
        Interactively resolve an order with the customer when the request is ambiguous.

        Args:
            customer_request: The customer's original request
            context: Additional context about the conversation
            session_id: Unique identifier for the conversation session to maintain state

        Returns:
            dict: The resolved order with clarification dialog
        """
        try:
            # Import the conversation store
            from app.utils.conversation_store import conversation_store
            
            # Generate a session ID if none provided
            if not session_id:
                import uuid
                session_id = str(uuid.uuid4())
                logger.info(f"[MENU-MATCHER] Created new session ID: {session_id}")
            
            # Get conversation from store or initialize a new one
            conversation_data = None
            if session_id:
                conversation_data = conversation_store.get_conversation(session_id)
                logger.info(f"[MENU-MATCHER] Retrieved conversation for session: {session_id}")
            
            # Prepare menu categories and items, using ONLY actual menu data
            categories = {}
            available_items = []

            # First, find all category items to create category map
            category_map = {}
            for item in self.menu_data.get("items", []):
                if item.get("is_category", True):  # This item IS a category
                    reference = item.get("reference_handler", "")
                    if reference:
                        # Clean up category name if it has [CATEGORY] prefix
                        category_name = item.get("name", "Unknown Category")
                        if category_name.startswith("[CATEGORY]"):
                            category_name = category_name[10:].strip()
                        category_map[reference] = category_name
                
                # Build list of all available non-category items
                if not item.get("is_category", False) and item.get("available", True) and not item.get("snoozed", False):
                    available_items.append(item)

            # Now process actual menu items and organize by category
            for item in available_items:
                # Get parent category name from parentId or use "Uncategorized"
                parent_id = item.get("parentId", "")
                category_name = category_map.get(parent_id, "Uncategorized")

                if category_name not in categories:
                    categories[category_name] = []

                # Add item name and price for better menu display
                item_price = item.get("price", 0)
                item_price_str = f"${item_price:.2f}" if isinstance(item_price, (int, float)) else ""
                
                # Include price with item name for better menu representation
                item_entry = {
                    "name": item.get("name", ""),
                    "price": item_price_str,
                    "description": item.get("description", "")
                }
                
                categories[category_name].append(item_entry)
            
            # Log the actual menu categories being used
            logger.info(f"[MENU-MATCHER] Using ACTUAL menu with {len(categories)} categories and {len(available_items)} items")
            for category, items in categories.items():
                logger.info(f"[MENU-MATCHER] Category '{category}' has {len(items)} items")
                if len(items) > 0:
                    logger.info(f"[MENU-MATCHER] Sample items in '{category}': {[item['name'] for item in items[:3]]}")

            # Build prompt for AI to clarify the order with ACTUAL menu data emphasis
            messages = [
                {
                    "role": "system",
                    "content": """You are an AI assistant for a restaurant that helps customers clarify their orders.
                    Your goal is to understand what the customer wants to order and suggest the appropriate menu items.
                    
                    ===CRITICAL MANDATORY RULES===
                    1. ONLY suggest ACTUAL menu items from the categories and items provided - NEVER invent items
                    2. When talking about the menu, you may ONLY reference items that appear in the ACTUAL MENU DATA section
                    3. Ask clarifying questions when the order is ambiguous
                    4. Be friendly and helpful in your responses
                    5. Base your suggestions ONLY on the menu categories and items available in the ACTUAL MENU DATA
                    6. NEVER, under any circumstances, mention food items that are not explicitly listed in the ACTUAL MENU DATA
                    7. If you're unsure if an item exists, assume it does NOT exist unless you can see it in the ACTUAL MENU DATA
                    8. Don't include any greetings
                    9. For general menu questions, list several actual menu items with their prices, organized by category
                    10. COMPARE EVERY ITEM YOU MENTION AGAINST THE ACTUAL MENU DATA before responding
                    
                    If you catch yourself about to mention a food item not in the ACTUAL MENU DATA, stop and replace it with an actual menu item.
                    
                    When suggesting menu items, use ONLY the exact item names as they appear in the ACTUAL MENU DATA.
                    Focus on understanding the customer's intent and helping them find the right items.""",
                },
            ]
            
            # Add conversation messages if available from the store
            if conversation_data and "messages" in conversation_data and conversation_data["messages"]:
                for message in conversation_data["messages"]:
                    messages.append({
                        "role": message["role"],
                        "content": message["content"]
                    })
                
                # Format the menu data with complete information for display
            formatted_menu = {}
            for category, items in categories.items():
                # For each category, include item name, price, and description
                formatted_menu[category] = [{
                    "name": item["name"],
                    "price": item["price"],
                    "description": item["description"] if len(item["description"]) > 0 else "No description available"
                } for item in items]
            
            # Create a detailed menu representation for the AI
            menu_representation = "ACTUAL MENU DATA (Use ONLY these items when discussing the menu):\n"
            for category, items in formatted_menu.items():
                menu_representation += f"\n== {category} ==\n"
                for item in items:
                    menu_representation += f"- {item['name']} ({item['price']})\n"
            
            # Add the new user request with ACTUAL menu data
            if conversation_data and "messages" in conversation_data and conversation_data["messages"]:
                messages.append({
                    "role": "user",
                    "content": f"Customer request: '{customer_request}'\n\n{menu_representation}\n\nPlease address this request while remembering our previous conversation. ONLY mention items from our ACTUAL menu above."
                })
                
                # Also add the request to the stored conversation
                conversation_store.add_message(session_id, "user", customer_request)
                
                logger.info(f"[MENU-MATCHER] Using existing conversation with {len(conversation_data['messages'])} messages")
            else:
                # This is a new conversation - include full menu details
                messages.append({
                    "role": "user",
                    "content": f"Customer request: '{customer_request}'\n\n{menu_representation}\n\nHow would you clarify the order? Ask specific questions to determine what the customer wants. ONLY mention items from our ACTUAL menu above.",
                })
                
                # Initialize conversation in the store
                if session_id:
                    conversation_store.save_conversation(session_id, {
                        "id": session_id,
                        "created_at": time.time(),
                        "updated_at": time.time(),
                        "messages": [
                            {"role": "user", "content": customer_request, "timestamp": time.time()}
                        ],
                        "context": context or {},
                        "resolved": False,
                        "items": []
                    })
                    logger.info(f"[MENU-MATCHER] Initialized new conversation for session: {session_id}")

            # Add additional conversation context if provided
            if context and "conversation" in context:
                messages[0][
                    "content"
                ] += "\nUse the conversation history to understand the customer's preferences."
                messages.append(
                    {
                        "role": "user",
                        "content": f"Additional conversation history:\n{context['conversation']}",
                    }
                )

            # Log the request
            log_openai_request(self.model, messages, "order_clarification")

            # Make the API call
            response = openai.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,  # Higher temperature for more creativity in responses
                max_tokens=550,  # Allow for a longer clarifying response
            )

            # Log the response
            log_openai_response(response, "order_clarification")

            # Extract the clarification dialog
            clarification = response.choices[0].message.content.strip()
            
            # Store the assistant's response in the conversation
            if session_id:
                conversation_store.add_message(session_id, "assistant", clarification)
                logger.info(f"[MENU-MATCHER] Added assistant response to conversation: {session_id}")
            
            # Check if we have previous items in the conversation
            items = []
            resolved = False
            
            if conversation_data:
                items = conversation_data.get("items", [])
                resolved = conversation_data.get("resolved", False)
            
            # Return the clarification along with the original request
            result = {
                "original_request": customer_request,
                "clarification_dialog": clarification,
                "resolved": resolved,
                "items": items,
                "session_id": session_id  # Include the session ID for state tracking
            }
            
            # Update the conversation with the latest state
            if session_id:
                conversation_store.update_conversation(session_id, {
                    "items": items,
                    "resolved": resolved
                })
            
            return result

        except Exception as e:
            logger.error(f"[MENU-MATCHER] Error in interactive resolution: {str(e)}")
            logger.error(f"[MENU-MATCHER] Traceback: {traceback.format_exc()}")
            return {
                "original_request": customer_request,
                "clarification_dialog": "I'm sorry, I'm having trouble understanding your order right now. Could you please be more specific about what you'd like to order?",
                "resolved": False,
                "items": [],
                "session_id": session_id
            }

    def process_customer_response(
        self, order_state: Dict[str, Any], customer_response: str
    ) -> Dict[str, Any]:
        """
        Process a customer's response to a clarification question and update the order state.

        Args:
            order_state: The current state of the order resolution
            customer_response: The customer's response to the clarification

        Returns:
            dict: The updated order state
        """
        try:
            # Import the conversation store
            from app.utils.conversation_store import conversation_store
            
            # Get session ID from order state or initialize a new one
            session_id = order_state.get("session_id")
            if not session_id:
                import uuid
                session_id = str(uuid.uuid4())
                logger.info(f"[MENU-MATCHER] Created new session ID for customer response: {session_id}")
                
            # Get existing conversation or create a new one
            conversation_data = None
            if session_id:
                conversation_data = conversation_store.get_conversation(session_id)
                logger.info(f"[MENU-MATCHER] Retrieved conversation data for: {session_id}")
            
            # Update the conversation with the new customer response
            if session_id:
                # First add the assistant's previous response if not already in the store
                assistant_message = order_state.get("clarification_dialog", "")
                if assistant_message:
                    conversation_store.add_message(session_id, "assistant", assistant_message)
                
                # Then add the customer's new response
                conversation_store.add_message(session_id, "user", customer_response)
                
                # Update other state information
                conversation_store.update_conversation(session_id, {
                    "items": order_state.get("items", []),
                    "resolved": order_state.get("resolved", False)
                })
                logger.info(f"[MENU-MATCHER] Updated conversation with customer response: {session_id}")

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

                menu_summary.append(
                    {
                        "name": item.get("name", ""),
                        "category": category_name,
                        "description": item.get("description", ""),
                        "price": item.get("price", 0.0),
                    }
                )

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
                    5. Maintain context from the entire conversation history to understand the customer's requests
                    
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
                    """,
                }
            ]

            # Get conversation messages from the store if available
            conversation = []
            if conversation_data and "messages" in conversation_data:
                # Add messages from conversation store
                for message in conversation_data["messages"]:
                    messages.append({
                        "role": message["role"],
                        "content": message["content"]
                    })
                    
                    # Also build the conversation array for backward compatibility
                    conversation.append({
                        "role": message["role"],
                        "content": message["content"]
                    })
                    
                logger.info(f"[MENU-MATCHER] Using {len(conversation_data['messages'])} messages from conversation store")
            else:
                # Fallback to legacy conversation from order_state if available
                conversation = order_state.get("conversation", [])
                if conversation:
                    # Add the conversation to messages
                    for msg in conversation:
                        messages.append({"role": msg["role"], "content": msg["content"]})
                    
                    # Add current messages to the conversation array
                    if "clarification_dialog" in order_state:
                        conversation.append({
                            "role": "assistant", 
                            "content": order_state.get("clarification_dialog", "")
                        })
                    conversation.append({"role": "user", "content": customer_response})

            # Format the menu data with complete information for display
            formatted_menu = {}
            available_items = []
            category_map = {}
            
            # First, identify categories
            for item in self.menu_data.get("items", []):
                if item.get("is_category", True):  # This item IS a category
                    reference = item.get("reference_handler", "")
                    if reference:
                        # Clean up category name if it has [CATEGORY] prefix
                        category_name = item.get("name", "Unknown Category")
                        if category_name.startswith("[CATEGORY]"):
                            category_name = category_name[10:].strip()
                        category_map[reference] = category_name
                        
                # Build list of all available non-category items
                if not item.get("is_category", False) and item.get("available", True) and not item.get("snoozed", False):
                    available_items.append(item)
            
            # Organize items by category
            categories = {}
            for item in available_items:
                # Get parent category name from parentId or use "Uncategorized"
                parent_id = item.get("parentId", "")
                category_name = category_map.get(parent_id, "Uncategorized")

                if category_name not in categories:
                    categories[category_name] = []

                # Add item name and price for better menu display
                item_price = item.get("price", 0)
                item_price_str = f"${item_price:.2f}" if isinstance(item_price, (int, float)) else ""
                
                # Include price with item name for better menu representation
                item_entry = {
                    "name": item.get("name", ""),
                    "price": item_price_str,
                    "description": item.get("description", "")
                }
                
                categories[category_name].append(item_entry)
                
            # Create a detailed menu representation for the AI
            menu_representation = "ACTUAL MENU DATA (Use ONLY these items when processing orders):\n"
            for category, items in categories.items():
                menu_representation += f"\n== {category} ==\n"
                for item in items:
                    menu_representation += f"- {item['name']} ({item['price']})\n"
            
            # Log how many actual menu items are being used
            logger.info(f"[MENU-MATCHER] Using ACTUAL menu with {len(categories)} categories and {len(available_items)} items")
            
            # Add the menu context with ACTUAL menu data
            messages.append(
                {
                    "role": "user",
                    "content": f"{menu_representation}\n\nPlease process this conversation and identify the order. ONLY match against items from our ACTUAL menu data above.",
                }
            )

            # Log the request
            log_openai_request(self.model, messages, "process_customer_response")

            # Make the API call
            response = openai.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=500,
                response_format={"type": "json_object"},
            )

            # Log the response
            log_openai_response(response, "process_customer_response")

            # Parse the response
            try:
                parsed_response = json.loads(response.choices[0].message.content)

                # Update the order state
                order_state["conversation"] = conversation
                order_state["resolved"] = parsed_response.get("resolved", False)
                order_state["session_id"] = session_id  # Include session ID in state

                # If items were identified, update the items list
                if "items" in parsed_response and parsed_response["items"]:
                    identified_items = []

                    # Look up the actual menu items
                    for item_info in parsed_response["items"]:
                        menu_item = self.find_menu_item(item_info["name"])
                        if menu_item:
                            identified_items.append(
                                {
                                    "name": menu_item["name"],
                                    "price": menu_item.get("price", 0.0),
                                    "reference_handler": menu_item.get(
                                        "reference_handler", ""
                                    ),
                                    "quantity": item_info.get("quantity", 1),
                                    "notes": item_info.get("notes", ""),
                                    "modifier": [],  # Can be populated later for modifiers
                                }
                            )

                    order_state["items"] = identified_items
                    
                    # Update items in the conversation store
                    if session_id:
                        conversation_store.update_conversation(session_id, {
                            "items": identified_items
                        })

                # If the order is not resolved, add the next question
                if not order_state["resolved"] and "next_question" in parsed_response:
                    next_question = parsed_response["next_question"]
                    order_state["clarification_dialog"] = next_question
                    
                    # Store the assistant's response
                    if session_id:
                        conversation_store.add_message(session_id, "assistant", next_question)
                elif not order_state["resolved"]:
                    default_question = "Could you please clarify what you'd like to order from our menu?"
                    order_state["clarification_dialog"] = default_question
                    
                    # Store the assistant's response
                    if session_id:
                        conversation_store.add_message(session_id, "assistant", default_question)
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
                    
                    # Store the assistant's response
                    if session_id:
                        conversation_store.add_message(session_id, "assistant", confirmation)
                        conversation_store.update_conversation(session_id, {
                            "resolved": True
                        })

                return order_state

            except json.JSONDecodeError:
                logger.error(
                    f"[MENU-MATCHER] Failed to parse JSON response: {response.choices[0].message.content}"
                )
                error_msg = "I'm having trouble understanding your order. Could you tell me exactly what items you'd like to order from our menu?"
                order_state["clarification_dialog"] = error_msg
                
                # Store the error message in the conversation
                if session_id:
                    conversation_store.add_message(session_id, "assistant", error_msg)
                
                return order_state

        except Exception as e:
            logger.error(f"[MENU-MATCHER] Error processing customer response: {str(e)}")
            logger.error(f"[MENU-MATCHER] Traceback: {traceback.format_exc()}")
            error_msg = "I'm sorry, I'm having trouble processing your response. Could you please try again with a clear list of items you'd like to order?"
            order_state["clarification_dialog"] = error_msg
            
            # Store the error message in the conversation
            if "session_id" in order_state and order_state["session_id"]:
                conversation_store.add_message(order_state["session_id"], "assistant", error_msg)
                
            return order_state


# Creating a singleton instance for easy import
menu_matcher = MenuMatcher()


def find_menu_item_ai(
    item_name: str,
    check_availability: bool = False,
    context: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
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