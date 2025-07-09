"""
Enhanced Async Menu Agent with proper database integration.

This module provides an improved menu agent that efficiently accesses
menu data from the database and Redis cache.
"""

import json
import logging
from typing import Dict, List, Any, Optional

from app.agents.base_async import BaseAsyncAgent
from app.agents.ai_mixin import AIIntelligenceMixin
from app.utils.menu_matcher_cache_async import get_cached_async_menu_matcher
from app.utils.menu_db_store_async import async_menu_db_store
from app.db.crud_menu_async import (
    get_all_categories,
    get_items_by_category,
    get_item_by_plu,
    search_menu_items
)
from app.utils.enhanced_logging import get_logger
from app.utils.disambiguation import (
    disambiguation_detector,
    disambiguation_resolver,
    DisambiguationContext
)
from app.config import settings
from app.services.deliverect_service import deliverect_service
from app.models.deliverect_models import MenuLookupResult, Product, ModifierGroup, Modifier
import difflib

logger = get_logger(__name__)

class AsyncMenuAgentEnhanced(BaseAsyncAgent, AIIntelligenceMixin):
    """
    Enhanced menu agent with AI capabilities and efficient database access.
    """
    
    def __init__(self, agent_id: Optional[str] = None, db: Optional[Any] = None):
        """Initialize the enhanced menu agent."""
        BaseAsyncAgent.__init__(self, agent_id=agent_id, name="MenuEnhanced")
        AIIntelligenceMixin.__init__(self)
        
        # Set agent-specific max tokens
        self._default_max_tokens = getattr(settings, 'MENU_AGENT_MAX_TOKENS', 256)
        self.context = {}  # Store context for disambiguation
        
        self.db = db
        self._menu_cache = {}
        self._cache_ttl = 300  # 5 minutes
        
        # AI instructions - DYNAMIC
        self.instructions = f"""
You are a menu specialist for {settings.RESTAURANT_NAME}. Your role is to help customers
understand our menu, make recommendations, and answer questions about our dishes.

KEY RESPONSIBILITIES:
1. Provide accurate information about menu items, prices, and ingredients
2. Make personalized recommendations based on preferences
3. Explain dishes in an appetizing way
4. Help with dietary restrictions and allergies
5. Suggest popular items and good combinations

MENU KNOWLEDGE:
- Use the lookup tools to get accurate, real-time menu information
- Never make up dishes or prices
- Always check availability before recommending
- Be aware of modifier options (size, spice level, extras)

COMMUNICATION STYLE:
- Enthusiastic about the food
- Descriptive but concise
- Helpful with suggestions
- Knowledgeable about Japanese cuisine

IMPORTANT RULES:
- Only recommend items that actually exist in our database
- Always provide accurate prices
- Mention if items are unavailable or snoozed
- Be helpful with substitutions for dietary needs
"""
        
        # Define tools
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "lookup_menu_item",
                    "description": "Look up a specific menu item by name",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_name": {
                                "type": "string",
                                "description": "Name of the menu item to look up"
                            }
                        },
                        "required": ["item_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_categories",
                    "description": "Get all menu categories",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_items_by_category",
                    "description": "Get all items in a specific category",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category_name": {
                                "type": "string",
                                "description": "Name of the category"
                            }
                        },
                        "required": ["category_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_menu",
                    "description": "Search menu items by keyword",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "keyword": {
                                "type": "string",
                                "description": "Search keyword"
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Maximum number of results",
                                "default": 5
                            }
                        },
                        "required": ["keyword"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_item_details",
                    "description": "Get detailed information about a menu item including modifiers",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_plu": {
                                "type": "string",
                                "description": "PLU code of the item"
                            }
                        },
                        "required": ["item_plu"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_popular_items",
                    "description": "Get popular/recommended items, optionally by category",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "description": "Optional category to filter by (e.g. 'Appetizers', 'Sushi Rolls')"
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Maximum number of items to return",
                                "default": 5
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_item_availability", 
                    "description": "Check if a specific item is currently available (not snoozed)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_plu": {
                                "type": "string",
                                "description": "PLU code of the item to check"
                            }
                        },
                        "required": ["item_plu"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_items_by_category",
                    "description": "Get available items from a specific category",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category_name": {
                                "type": "string",
                                "description": "Name of the category"
                            },
                            "include_unavailable": {
                                "type": "boolean",
                                "description": "Whether to include snoozed/unavailable items",
                                "default": False
                            }
                        },
                        "required": ["category_name"]
                    }
                }
            }
        ]
    
    async def process_input(
        self, 
        input_text: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process menu inquiries using AI and database."""
        context = context or {}
        self.update_context(context)
        
        logger.info(f"[{self.name}] Processing menu question: {input_text}")
        
        # Use AI to understand and respond
        response = await self.process_with_ai(input_text, context)
        
        return response
    
    async def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute menu-related tools."""
        logger.info(f"[{self.name}] Executing tool: {tool_name} with args: {args}")
        
        try:
            if tool_name == "lookup_menu_item":
                return await self._lookup_menu_item(args.get("item_name", ""))
                
            elif tool_name == "list_categories":
                return await self._list_categories()
                
            elif tool_name == "get_items_by_category":
                return await self._get_items_by_category(args.get("category_name", ""))
                
            elif tool_name == "search_menu":
                return await self._search_menu(
                    args.get("keyword", ""),
                    args.get("max_results", 5)
                )
                
            elif tool_name == "get_item_details":
                return await self._get_item_details(args.get("item_plu", ""))
                
            elif tool_name == "get_popular_items":
                return await self._get_popular_items(
                    args.get("category"),
                    args.get("max_results", 5)
                )
                
            elif tool_name == "check_item_availability":
                return await self._check_item_availability(args.get("item_plu", ""))
                
            elif tool_name == "resolve_disambiguation":
                return await self._resolve_disambiguation(args.get("response", ""))
                
            else:
                return {"error": f"Unknown tool: {tool_name}"}
                
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {"error": str(e)}
    
    async def _lookup_menu_item(self, item_name: str) -> Dict[str, Any]:
        """
        Enhanced menu item lookup using database directly with fuzzy matching and confidence scores.
        Returns structured MenuLookupResult format for better AI understanding.
        """
        def normalize_for_matching(text: str) -> str:
            """Normalize text for better fuzzy matching by handling common variations."""
            import re
            normalized = text.lower().strip()
            # Replace hyphens and underscores with spaces
            normalized = re.sub(r'[-_]+', ' ', normalized)
            # Remove extra whitespace
            normalized = re.sub(r'\s+', ' ', normalized)
            return normalized
            
        if not item_name.strip():
            return {"found": False, "error": "Item name cannot be empty"}
        
        if not self.db:
            from app.db_async import async_session_factory
            self.db = async_session_factory()
            logger.info("Created new database session for menu agent")
        
        try:
            # Get all available menu items from database
            from app.db.crud_menu_async import get_all_menu_items
            items = await get_all_menu_items(self.db)
            
            if not items:
                return {"found": False, "error": "No menu items found in database"}
            
            # Perform fuzzy matching with confidence scores
            matches = []
            search_term = item_name.lower().strip()
            normalized_search = normalize_for_matching(search_term)
            
            for item in items:
                # Skip unavailable items unless explicitly requested
                if not item.is_available:
                    continue
                    
                item_name_lower = item.name.lower()
                normalized_item = normalize_for_matching(item_name_lower)
                
                # Calculate different types of matching scores using both original and normalized text
                exact_match = 1.0 if search_term == item_name_lower or normalized_search == normalized_item else 0.0
                contains_match = 0.8 if search_term in item_name_lower or normalized_search in normalized_item else 0.0
                reverse_contains = 0.7 if item_name_lower in search_term or normalized_item in normalized_search else 0.0
                
                # Use difflib for sequence matching on normalized text (better for punctuation differences)
                sequence_similarity = difflib.SequenceMatcher(None, normalized_search, normalized_item).ratio()
                
                # Calculate final confidence score (weighted combination)
                confidence = max(
                    exact_match,
                    contains_match,
                    reverse_contains,
                    sequence_similarity * 0.7  # Increased weight for sequence matching with normalization
                )
                
                # Only include matches above threshold
                if confidence >= 0.4:
                    matches.append({
                        'item': item,
                        'confidence': confidence
                    })
            
            # Sort by confidence score (highest first)
            matches.sort(key=lambda x: x['confidence'], reverse=True)
            
            if not matches:
                # Try alternative search with lower threshold or suggest alternatives
                return await self._generate_alternatives_db(search_term, items)
            
            # Get the best match
            best_match = matches[0]
            best_item = best_match['item']
            confidence = best_match['confidence']
            
            # Get modifier groups and modifiers for this item
            modifier_groups = []
            if hasattr(best_item, 'modifier_groups'):
                for group in best_item.modifier_groups:
                    group_data = {
                        "id": group.id,
                        "name": group.name,
                        "plu": group.plu,
                        "min_selection": group.min_selection,
                        "max_selection": group.max_selection,
                        "multiMax": group.multiMax,
                        "is_variant_group": group.is_variant_group,
                        "modifiers": []
                    }
                    
                    # Get modifiers in this group
                    if hasattr(group, 'modifiers'):
                        for modifier in group.modifiers:
                            group_data["modifiers"].append({
                                "id": modifier.id,
                                "name": modifier.name,
                                "plu": modifier.plu,
                                "price_change": float(modifier.price_change),
                                "price_formatted": f"${modifier.price_change:.2f}" if modifier.price_change > 0 else "No charge",
                                "is_available": modifier.is_available,
                                "snoozed": modifier.snoozed_until is not None
                            })
                    
                    modifier_groups.append(group_data)
            
            # Check if disambiguation is needed (multiple high-confidence matches)
            high_confidence_matches = [m for m in matches if m['confidence'] >= 0.7]
            if len(high_confidence_matches) > 1 and confidence < 0.9:
                # Multiple good matches - offer disambiguation
                alternatives = []
                for match in high_confidence_matches[:4]:  # Limit to 4 options
                    item = match['item']
                    alternatives.append({
                        "id": item.id,
                        "name": item.name,
                        "plu": item.plu,
                        "price": float(item.price),
                        "price_formatted": f"${item.price:.2f}",
                        "description": item.description,
                        "category": item.category.name if item.category else "Unknown"
                    })
                
                return {
                    "found": True,
                    "confidence": confidence,
                    "item": {
                        "id": best_item.id,
                        "name": best_item.name,
                        "plu": best_item.plu,
                        "price": float(best_item.price),
                        "price_formatted": f"${best_item.price:.2f}",
                        "description": best_item.description,
                        "category": best_item.category.name if best_item.category else "Unknown",
                        "is_available": best_item.is_available,
                        "modifier_groups": modifier_groups
                    },
                    "needs_disambiguation": True,
                    "alternatives": alternatives,
                    "has_required_modifiers": any(g["min_selection"] > 0 for g in modifier_groups)
                }
            
            # Single clear match - return full structured result
            return {
                "found": True,
                "confidence": confidence,
                "item": {
                    "id": best_item.id,
                    "name": best_item.name,
                    "plu": best_item.plu,
                    "price": float(best_item.price),
                    "price_formatted": f"${best_item.price:.2f}",
                    "description": best_item.description,
                    "category": best_item.category.name if best_item.category else "Unknown",
                    "is_available": best_item.is_available,
                    "modifier_groups": modifier_groups
                },
                "has_required_modifiers": any(g["min_selection"] > 0 for g in modifier_groups),
                "message": f"Found {best_item.name} with {confidence:.1%} confidence"
            }
            
        except Exception as e:
            logger.error(f"Error in database menu lookup: {e}")
            return {"found": False, "error": str(e)}
    
    async def _generate_alternatives_db(self, search_term: str, items: List[Any]) -> Dict[str, Any]:
        """Generate alternative suggestions when no good matches are found (database version)."""
        try:
            # Look for partial word matches or similar categories
            alternatives = []
            
            # Split search term into words
            search_words = search_term.split()
            
            for item in items[:10]:  # Limit search
                if not item.is_available:
                    continue
                    
                item_words = item.name.lower().split()
                
                # Check if any search word appears in item name
                for search_word in search_words:
                    if len(search_word) > 2:  # Ignore very short words
                        for item_word in item_words:
                            if search_word in item_word or item_word in search_word:
                                alternatives.append({
                                    "id": item.id,
                                    "name": item.name,
                                    "plu": item.plu,
                                    "price": float(item.price),
                                    "price_formatted": f"${item.price:.2f}",
                                    "description": item.description,
                                    "category": item.category.name if item.category else "Unknown"
                                })
                                break
                        if alternatives and alternatives[-1]["id"] == item.id:
                            break
            
            if alternatives:
                return {
                    "found": False,
                    "message": f"No exact match for '{search_term}', but here are some similar items:",
                    "suggested_alternatives": alternatives[:5]
                }
            else:
                return {
                    "found": False,
                    "message": f"No items found matching '{search_term}'. Try browsing our categories or ask about specific dishes."
                }
                
        except Exception as e:
            logger.error(f"Error generating alternatives: {e}")
            return {"found": False, "error": str(e)}
    
    async def _generate_alternatives(self, search_term: str, products: List[Product]) -> Dict[str, Any]:
        """Generate alternative suggestions when no good matches are found."""
        try:
            # Look for partial word matches or similar categories
            alternatives = []
            
            # Split search term into words
            search_words = search_term.split()
            
            for product in products[:10]:  # Limit search
                if product.snoozed:
                    continue
                    
                product_words = product.name.lower().split()
                
                # Check if any search word appears in product name
                for search_word in search_words:
                    if len(search_word) > 2:  # Ignore very short words
                        for product_word in product_words:
                            if search_word in product_word or product_word in search_word:
                                alternatives.append(product)
                                break
                        if product in alternatives:
                            break
            
            if alternatives:
                return {
                    "found": False,
                    "message": f"No exact match for '{search_term}', but here are some similar items:",
                    "suggested_alternatives": [p.dict() for p in alternatives[:5]]
                }
            else:
                return {
                    "found": False,
                    "message": f"No items found matching '{search_term}'. Try browsing our categories or ask about specific dishes."
                }
                
        except Exception as e:
            logger.error(f"Error generating alternatives: {e}")
            return {"found": False, "error": str(e)}
    
    async def _fallback_lookup_menu_item(self, item_name: str) -> Dict[str, Any]:
        """Fallback to original database lookup if cache is unavailable."""
        try:
            # Get the menu matcher
            from app.utils.menu_matcher_db_async import AsyncMenuMatcher
            matcher = AsyncMenuMatcher(self.db)
            await matcher.initialize()
            
            # Find all matching items
            matches = await matcher.find_all_matching_items(item_name, threshold=0.5)
            
            if not matches:
                return {
                    "found": False,
                    "search_term": item_name,
                    "message": "Item not found in our menu"
                }
            
            # Return the best match in new format
            best_match = matches[0]
            return {
                "found": True,
                "confidence": best_match.get("confidence", 0.5),
                "item": {
                    "name": best_match.get("name"),
                    "plu": best_match.get("plu"),
                    "price": best_match.get('price', 0),
                    "description": best_match.get("description", ""),
                    "snoozed": not best_match.get("is_available", True)
                },
                "modifier_groups": [],
                "modifiers": {},
                "has_required_modifiers": False,
                "message": "Found using fallback database lookup"
            }
            
        except Exception as e:
            logger.error(f"Error in fallback lookup: {e}")
            return {"found": False, "error": str(e)}
    
    async def _list_categories(self) -> Dict[str, Any]:
        """Get all menu categories."""
        if not self.db:
            from app.db_async import async_session_factory
            self.db = async_session_factory()
            logger.info("Created new database session for menu agent")
        
        try:
            categories = await get_all_categories(self.db)
            
            return {
                "categories": [
                    {
                        "id": cat.id,
                        "name": cat.name,
                        "description": cat.description
                    }
                    for cat in categories
                ],
                "count": len(categories)
            }
            
        except Exception as e:
            logger.error(f"Error listing categories: {e}")
            return {"categories": [], "error": str(e)}
    
    async def _get_items_by_category(self, category_name: str) -> Dict[str, Any]:
        """Get items in a specific category."""
        if not self.db:
            from app.db_async import async_session_factory
            self.db = async_session_factory()
            logger.info("Created new database session for menu agent")
        
        try:
            # First find the category
            categories = await get_all_categories(self.db)
            category = None
            
            for cat in categories:
                if cat.name.lower() == category_name.lower():
                    category = cat
                    break
            
            if not category:
                return {
                    "items": [],
                    "error": f"Category '{category_name}' not found"
                }
            
            # Get items in the category
            items = await get_items_by_category(self.db, category.id)
            
            return {
                "category": category_name,
                "items": [
                    {
                        "name": item.name,
                        "plu": item.plu,
                        "price": f"${item.price:.2f}",
                        "description": item.description,
                        "available": item.is_available
                    }
                    for item in items
                    if item.is_available  # Only show available items
                ],
                "count": len(items)
            }
            
        except Exception as e:
            logger.error(f"Error getting items by category: {e}")
            return {"items": [], "error": str(e)}
    
    async def _search_menu(self, keyword: str, max_results: int = 5) -> Dict[str, Any]:
        """Search menu items by keyword."""
        if not self.db:
            return {"results": [], "error": "Database not available"}
        
        try:
            # Use the search function
            items = await search_menu_items(self.db, keyword, limit=max_results)
            
            return {
                "keyword": keyword,
                "results": [
                    {
                        "name": item.name,
                        "plu": item.plu,
                        "price": f"${item.price:.2f}",
                        "category": item.category.name if item.category else "Unknown",
                        "description": item.description,
                        "available": item.is_available
                    }
                    for item in items
                ],
                "count": len(items)
            }
            
        except Exception as e:
            logger.error(f"Error searching menu: {e}")
            return {"results": [], "error": str(e)}
    
    async def _get_item_details(self, item_plu: str) -> Dict[str, Any]:
        """
        Get detailed information about a menu item including all modifiers from database.
        """
        if not item_plu.strip():
            return {"found": False, "error": "PLU cannot be empty"}
        
        if not self.db:
            from app.db_async import async_session_factory
            self.db = async_session_factory()
            logger.info("Created new database session for menu agent")
        
        try:
            item = await get_item_by_plu(self.db, item_plu)
            
            if not item:
                return {
                    "found": False,
                    "plu": item_plu,
                    "error": "Item not found"
                }
            
            # Get modifier groups if available
            modifier_groups = []
            if hasattr(item, 'modifier_groups'):
                for group in item.modifier_groups:
                    modifiers = []
                    if hasattr(group, 'modifiers'):
                        for mod in group.modifiers:
                            modifiers.append({
                                "id": mod.id,
                                "name": mod.name,
                                "plu": mod.plu,
                                "price_change": float(mod.price_change),
                                "price_formatted": f"${mod.price_change:.2f}" if mod.price_change > 0 else "No charge",
                                "is_available": mod.is_available,
                                "snoozed": mod.snoozed_until is not None
                            })
                    
                    modifier_groups.append({
                        "id": group.id,
                        "name": group.name,
                        "plu": group.plu,
                        "required": group.min_selection > 0,
                        "min_selection": group.min_selection,
                        "max_selection": group.max_selection,
                        "multiMax": group.multiMax,
                        "is_variant_group": group.is_variant_group,
                        "modifiers": modifiers
                    })
            
            return {
                "found": True,
                "item": {
                    "id": item.id,
                    "name": item.name,
                    "plu": item.plu,
                    "price": float(item.price),
                    "price_formatted": f"${item.price:.2f}",
                    "description": item.description,
                    "category": item.category.name if item.category else "Unknown",
                    "available": item.is_available,
                    "snoozed": item.snoozed_until is not None,
                    "modifier_groups": modifier_groups,
                    "total_modifier_groups": len(modifier_groups),
                    "has_required_modifiers": any(g["required"] for g in modifier_groups),
                    "image_url": item.image_url,
                    "source": "database"
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting item details from database: {e}")
            return {"found": False, "error": str(e)}
    
    async def _fallback_get_item_details(self, item_plu: str) -> Dict[str, Any]:
        """Fallback to database lookup for item details."""
        if not self.db:
            return {"found": False, "error": "No data source available"}
        
        try:
            item = await get_item_by_plu(self.db, item_plu)
            
            if not item:
                return {
                    "found": False,
                    "plu": item_plu,
                    "error": "Item not found"
                }
            
            # Get modifier groups if available
            modifier_groups = []
            if hasattr(item, 'modifier_groups'):
                for group in item.modifier_groups:
                    modifiers = []
                    if hasattr(group, 'modifiers'):
                        modifiers = [
                            {
                                "name": mod.name,
                                "price_change": f"${mod.price_change:.2f}" if mod.price_change else "No charge",
                                "plu": mod.plu
                            }
                            for mod in group.modifiers
                        ]
                    
                    modifier_groups.append({
                        "name": group.name,
                        "required": group.min_selection > 0,
                        "min_selection": group.min_selection,
                        "max_selection": group.max_selection,
                        "modifiers": modifiers
                    })
            
            return {
                "found": True,
                "item": {
                    "name": item.name,
                    "plu": item.plu,
                    "price": f"${item.price:.2f}",
                    "description": item.description,
                    "category": item.category.name if item.category else "Unknown",
                    "available": item.is_available,
                    "snoozed": item.snoozed_until is not None,
                    "modifier_groups": modifier_groups,
                    "image_url": item.image_url,
                    "source": "database_fallback"
                }
            }
            
        except Exception as e:
            logger.error(f"Error in fallback item details: {e}")
            return {"found": False, "error": str(e)}
    
    async def _resolve_disambiguation(self, user_response: str) -> Dict[str, Any]:
        """Resolve a disambiguation based on user's clarification response."""
        # Check if we have disambiguation context
        if not hasattr(self, 'context') or 'disambiguation' not in self.context:
            return {
                "resolved": False,
                "error": "No disambiguation in progress"
            }
        
        try:
            # Restore disambiguation context
            context_data = self.context['disambiguation']
            context = DisambiguationContext.from_dict(context_data)
            
            # Try to match the response
            matched_candidate = disambiguation_resolver.match_response(
                user_response, context
            )
            
            if matched_candidate:
                # Clear disambiguation context
                del self.context['disambiguation']
                
                # Return the matched item
                return {
                    "resolved": True,
                    "found": True,
                    "item": {
                        "name": matched_candidate.name,
                        "plu": matched_candidate.plu,
                        "price": f"${matched_candidate.price:.2f}",
                        "description": matched_candidate.description or "",
                        "category": matched_candidate.category,
                        "available": True,
                        "match_score": matched_candidate.confidence
                    }
                }
            else:
                # Couldn't match - increment attempt count
                context.attempt_count += 1
                
                if context.attempt_count >= context.max_attempts:
                    # Too many attempts - give up
                    del self.context['disambiguation']
                    return {
                        "resolved": False,
                        "error": "I'm having trouble understanding which item you mean. Could you please be more specific?",
                        "give_up": True
                    }
                else:
                    # Try again with a different phrasing
                    self.context['disambiguation'] = context.to_dict()
                    clarification = disambiguation_resolver.generate_clarification(context)
                    
                    return {
                        "resolved": False,
                        "needs_disambiguation": True,
                        "clarification_needed": f"I'm not sure I understood. {clarification}",
                        "attempt": context.attempt_count
                    }
                    
        except Exception as e:
            logger.error(f"Error resolving disambiguation: {e}")
            return {"resolved": False, "error": str(e)}
    
    async def _get_popular_items(self, category: Optional[str] = None, max_results: int = 5) -> Dict[str, Any]:
        """
        Get popular/recommended items from database, optionally filtered by category.
        For now, returns available items. In the future, this could be based on order frequency.
        """
        if not self.db:
            from app.db_async import async_session_factory
            self.db = async_session_factory()
            logger.info("Created new database session for menu agent")
        
        try:
            from app.db.crud_menu_async import get_all_menu_items
            items = await get_all_menu_items(self.db)
            
            if not items:
                return {"error": "No menu data available"}
            
            # Filter available items
            available_items = [item for item in items if item.is_available]
            
            # If category specified, filter by category
            if category:
                category_lower = category.lower()
                filtered_items = []
                for item in available_items:
                    # Check if category matches item's category or appears in name/description
                    item_category = item.category.name.lower() if item.category else ""
                    item_text = f"{item.name} {item.description or ''}".lower()
                    
                    if (category_lower in item_category or 
                        any(word in item_text for word in category_lower.split())):
                        filtered_items.append(item)
                
                available_items = filtered_items
            
            # Return first max_results items (in future, sort by popularity)
            popular_items = available_items[:max_results]
            
            return {
                "items": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "plu": item.plu,
                        "price": float(item.price),
                        "price_formatted": f"${item.price:.2f}",
                        "description": item.description,
                        "category": item.category.name if item.category else "Unknown",
                        "available": item.is_available
                    }
                    for item in popular_items
                ],
                "count": len(popular_items),
                "category_filter": category,
                "message": f"Here are {len(popular_items)} popular items" + (f" in {category}" if category else "")
            }
            
        except Exception as e:
            logger.error(f"Error getting popular items from database: {e}")
            return {"error": str(e)}
    
    async def _check_item_availability(self, item_plu: str) -> Dict[str, Any]:
        """Check if a specific item is currently available from database."""
        if not self.db:
            from app.db_async import async_session_factory
            self.db = async_session_factory()
            logger.info("Created new database session for menu agent")
        
        try:
            item = await get_item_by_plu(self.db, item_plu)
            
            if not item:
                return {
                    "plu": item_plu,
                    "name": "Unknown Item",
                    "is_available": False,
                    "snoozed": False,
                    "reason": "Item not found in menu"
                }
            
            is_snoozed = item.snoozed_until is not None
            
            return {
                "plu": item.plu,
                "name": item.name,
                "is_available": item.is_available and not is_snoozed,
                "snoozed": is_snoozed,
                "reason": "Item is temporarily unavailable" if is_snoozed else ("Item is disabled" if not item.is_available else None),
                "estimated_available_time": item.snoozed_until.isoformat() if item.snoozed_until else None
            }
            
        except Exception as e:
            logger.error(f"Error checking item availability from database: {e}")
            return {"error": str(e)}