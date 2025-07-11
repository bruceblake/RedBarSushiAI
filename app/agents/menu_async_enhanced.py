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
                                "description": "Optional category to filter by - use exact category names from database"
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
        Use AI intelligence to search for menu items using database tools.
        """
        if not item_name.strip():
            return {"found": False, "error": "Item name cannot be empty"}
        
        try:
            # Use AI to intelligently search the database
            context = {
                "customer_request": item_name.strip(),
                "search_type": "menu_lookup"
            }
            
            # Let AI decide how to search using available tools
            response = await self.process_with_ai(
                f"Find menu items matching: {item_name}",
                context,
                use_tools=True
            )
            
            # If AI found something via tools, return it
            if response.get("tool_results"):
                for tool_result in response["tool_results"]:
                    if tool_result["tool"] == "search_menu" and tool_result["result"].get("results"):
                        results = tool_result["result"]["results"]
                        if results:
                            best_match = results[0]  # AI should have ordered by relevance
                            return {
                                "found": True,
                                "confidence": 0.9,  # High confidence since AI selected it
                                "item": {
                                    "name": best_match["name"],
                                    "plu": best_match["plu"],
                                    "price": float(best_match["price"].replace("$", "")),
                                    "price_formatted": best_match["price"],
                                    "description": best_match.get("description", ""),
                                    "category": best_match.get("category", "Unknown"),
                                    "is_available": best_match.get("available", True)
                                }
                            }
            
            # If no results from tools, return not found
            return {
                "found": False, 
                "message": f"I couldn't find '{item_name}' on our menu. Would you like me to suggest some alternatives?",
                "ai_response": response.get("text", "")
            }
            
        except Exception as e:
            logger.error(f"Error in AI menu lookup for '{item_name}': {e}")
            return {"found": False, "error": str(e)}
    
    async def _format_menu_result(self, item: Any, confidence: float = 1.0) -> Dict[str, Any]:
        """Format a menu item into the standard result format."""
        try:
            # Get modifier groups and modifiers for this item
            modifier_groups = []
            if hasattr(item, 'modifier_groups'):
                for group in item.modifier_groups:
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
            
            return {
                "found": True,
                "confidence": confidence,
                "item": {
                    "id": item.id,
                    "name": item.name,
                    "plu": item.plu,
                    "price": float(item.price),
                    "price_formatted": f"${item.price:.2f}",
                    "description": item.description,
                    "category": item.category.name if item.category else "Unknown",
                    "is_available": item.is_available,
                    "modifier_groups": modifier_groups
                },
                "has_required_modifiers": any(g["min_selection"] > 0 for g in modifier_groups),
                "message": f"Found {item.name} with {confidence:.1%} confidence"
            }
        except Exception as e:
            logger.error(f"Error formatting menu result: {e}")
            return {"found": False, "error": f"Error formatting result: {str(e)}"}
    
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
        """Get items in a specific category with fuzzy matching."""
        if not self.db:
            from app.db_async import async_session_factory
            self.db = async_session_factory()
            logger.info("Created new database session for menu agent")
        
        try:
            # First find the category with fuzzy matching
            categories = await get_all_categories(self.db)
            category = None
            
            # Try exact match first
            for cat in categories:
                if cat.name.lower() == category_name.lower():
                    category = cat
                    break
            
            # If no exact match, try fuzzy matching
            if not category:
                from difflib import SequenceMatcher
                best_match = None
                best_ratio = 0.0
                
                for cat in categories:
                    # Normalize for better matching
                    cat_normalized = cat.name.lower().replace("&", "and").replace("-", " ").strip()
                    search_normalized = category_name.lower().replace("&", "and").replace("-", " ").strip()
                    
                    ratio = SequenceMatcher(None, cat_normalized, search_normalized).ratio()
                    if ratio > best_ratio and ratio > 0.7:  # 70% similarity threshold
                        best_ratio = ratio
                        best_match = cat
                
                if best_match:
                    category = best_match
                    logger.info(f"Fuzzy matched '{category_name}' to '{category.name}' (similarity: {best_ratio:.2f})")
            
            if not category:
                available_categories = [cat.name for cat in categories]
                return {
                    "items": [],
                    "error": f"Category '{category_name}' not found. Available categories: {', '.join(available_categories)}"
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
    
    async def _ai_match_menu_item(self, search_term: str, item_name: str, item_description: str) -> float:
        """
        Use AI to determine how well a search term matches a menu item.
        
        Args:
            search_term: What the customer said they want
            item_name: Name of the menu item
            item_description: Description of the menu item
            
        Returns:
            Confidence score from 0.0 to 1.0
        """
        try:
            client = await self._get_ai_client()
            
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a menu matching specialist for a restaurant. 
                        
Analyze how well a customer's request matches a specific menu item and return a confidence score.

Return ONLY a JSON object with:
{"confidence": 0.0-1.0, "reasoning": "brief explanation"}

Guidelines:
- 1.0: Perfect/exact match (search term appears in item name)
- 0.8-0.9: Very close match (very similar names or synonyms)
- 0.6-0.7: Good semantic match (related food types)
- 0.4-0.5: Possible match (some ingredient or category overlap)
- 0.0-0.3: Poor/no match (unrelated items)

Consider:
- Exact name matches
- Semantic similarity between food types
- Ingredient overlap
- Item descriptions
- Common nicknames/abbreviations"""
                    },
                    {
                        "role": "user",
                        "content": f"Customer wants: '{search_term}'\nMenu item: '{item_name}'\nDescription: '{item_description}'"
                    }
                ],
                temperature=0.1,
                max_tokens=100
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Parse JSON response
            import json
            result = json.loads(result_text)
            
            confidence = result.get("confidence", 0.0)
            logger.debug(f"AI match: '{search_term}' → '{item_name}' = {confidence}")
            
            return max(0.0, min(1.0, confidence))  # Ensure 0.0-1.0 range
            
        except Exception as e:
            logger.error(f"Error in AI menu matching: {e}")
            # Conservative fallback - if AI fails, don't match
            return 0.0
    
    def _fast_fuzzy_match(self, search_term: str, item_name: str, item_description: str) -> float:
        """
        Fast fuzzy matching for menu items using string similarity.
        
        Args:
            search_term: What the customer said they want
            item_name: Name of the menu item  
            item_description: Description of the menu item
            
        Returns:
            Confidence score from 0.0 to 1.0
        """
        search_lower = search_term.lower().strip()
        name_lower = item_name.lower().strip()
        desc_lower = (item_description or '').lower().strip()
        
        # Exact match gets highest score
        if search_lower == name_lower:
            return 1.0
            
        # Check if search term is contained in name
        if search_lower in name_lower:
            return 0.9
            
        # Check if name is contained in search term (for phrases like "chicken burger")
        if name_lower in search_lower:
            return 0.8
            
        # Use difflib for fuzzy matching
        from difflib import SequenceMatcher
        
        # Name similarity
        name_similarity = SequenceMatcher(None, search_lower, name_lower).ratio()
        
        # Check word overlap
        search_words = set(search_lower.split())
        name_words = set(name_lower.split())
        desc_words = set(desc_lower.split()) if desc_lower else set()
        
        # Calculate word overlap scores
        if name_words:
            name_overlap = len(search_words & name_words) / len(search_words | name_words)
        else:
            name_overlap = 0.0
            
        if desc_words:
            desc_overlap = len(search_words & desc_words) / len(search_words | desc_words)
        else:
            desc_overlap = 0.0
        
        # Combine scores (prioritize name over description)
        combined_score = max(
            name_similarity * 0.8,
            name_overlap * 0.7,
            desc_overlap * 0.4
        )
        
        return min(1.0, combined_score)