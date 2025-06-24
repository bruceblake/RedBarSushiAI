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
                    "description": "Get detailed information about a menu item",
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
                
            elif tool_name == "resolve_disambiguation":
                return await self._resolve_disambiguation(args.get("response", ""))
                
            else:
                return {"error": f"Unknown tool: {tool_name}"}
                
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {"error": str(e)}
    
    async def _lookup_menu_item(self, item_name: str) -> Dict[str, Any]:
        """Look up a menu item using the matcher with disambiguation support."""
        if not self.db:
            return {"found": False, "error": "Database not available"}
        
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
            
            # Check if disambiguation is needed
            needs_disambig, disambig_type = disambiguation_detector.needs_disambiguation(
                matches, item_name
            )
            
            if needs_disambig:
                # Create disambiguation context
                context = disambiguation_detector.create_context(
                    matches, item_name, disambig_type
                )
                
                # Generate clarification question
                clarification = disambiguation_resolver.generate_clarification(context)
                
                # Store context for follow-up
                if hasattr(self, 'context'):
                    self.context['disambiguation'] = context.to_dict()
                
                return {
                    "found": False,
                    "needs_disambiguation": True,
                    "clarification_needed": clarification,
                    "candidates": [c.to_dict() for c in context.candidates],
                    "disambiguation_type": disambig_type.value
                }
            
            # Single best match found
            best_match = matches[0]
            
            # Format the response
            return {
                "found": True,
                "item": {
                    "name": best_match.get("name"),
                    "plu": best_match.get("plu"),
                    "price": f"${best_match.get('price', 0):.2f}",
                    "description": best_match.get("description", ""),
                    "category": best_match.get("category_name", ""),
                    "available": best_match.get("is_available", True),
                    "match_score": best_match.get("confidence", 0)
                }
            }
            
        except Exception as e:
            logger.error(f"Error looking up menu item: {e}")
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
                        "price": f"${item.price / 100:.2f}",
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
                        "price": f"${item.price / 100:.2f}",
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
        """Get detailed information about a menu item."""
        if not self.db:
            return {"found": False, "error": "Database not available"}
        
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
                                "price_change": f"${mod.price_change / 100:.2f}" if mod.price_change else "No charge",
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
                    "price": f"${item.price / 100:.2f}",
                    "description": item.description,
                    "category": item.category.name if item.category else "Unknown",
                    "available": item.is_available,
                    "snoozed": item.snoozed_until is not None,
                    "modifier_groups": modifier_groups,
                    "image_url": item.image_url
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting item details: {e}")
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