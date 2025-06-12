"""
Enhanced Async Menu Agent with proper database integration.

This module provides an improved menu agent that efficiently accesses
menu data from the database and Redis cache.
"""

import logging
from typing import Dict, Any, Optional

from app.agents.base_async import BaseAsyncAgent
from app.agents.ai_mixin import AIIntelligenceMixin
from app.utils.menu_matcher_cache_async import get_cached_async_menu_matcher
from app.db.crud_menu_async import (
    get_all_categories,
    get_items_by_category,
    get_item_by_plu,
    search_menu_items,
)

logger = logging.getLogger(__name__)


class AsyncMenuAgentEnhanced(BaseAsyncAgent, AIIntelligenceMixin):
    """
    Enhanced menu agent with AI capabilities and efficient database access.
    """

    def __init__(self, agent_id: Optional[str] = None, db: Optional[Any] = None):
        """Initialize the enhanced menu agent."""
        BaseAsyncAgent.__init__(self, agent_id=agent_id, name="MenuEnhanced")
        AIIntelligenceMixin.__init__(self)

        self.db = db
        self._menu_cache = {}
        # self._cache_ttl = 300  # 5 minutes # Removed as flagged by Vulture

        # AI instructions
        self.instructions = """
You are a menu specialist for Red Bar Sushi restaurant. Your role is to help customers
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
                                "description": "Name of the menu item to look up",
                            }
                        },
                        "required": ["item_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_categories",
                    "description": "Get all menu categories",
                    "parameters": {"type": "object", "properties": {}},
                },
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
                                "description": "Name of the category",
                            }
                        },
                        "required": ["category_name"],
                    },
                },
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
                                "description": "Search keyword",
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Maximum number of results",
                                "default": 5,
                            },
                        },
                        "required": ["keyword"],
                    },
                },
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
                                "description": "PLU code of the item",
                            }
                        },
                        "required": ["item_plu"],
                    },
                },
            },
        ]

    async def process_input(
        self, input_text: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process menu inquiries using AI and database."""
        context = context or {}
        self.update_context(context)

        logger.info(f"[{self.name}] Processing menu question: {input_text}")

        # Use AI to understand and respond
        response = await self.process_with_ai(input_text, context)

        return response

    async def execute_tool(
        self, tool_name: str, args: Dict[str, Any]
    ) -> Dict[str, Any]:
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
                    args.get("keyword", ""), args.get("max_results", 5)
                )

            elif tool_name == "get_item_details":
                return await self._get_item_details(args.get("item_plu", ""))

            else:
                return {"error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {"error": str(e)}

    async def _lookup_menu_item(self, item_name: str) -> Dict[str, Any]:
        """Look up a menu item using the matcher."""
        if not self.db:
            return {"found": False, "error": "Database not available"}

        try:
            # Use the menu matcher for intelligent matching
            matcher = await get_cached_async_menu_matcher(self.db)
            item_result, score = await matcher.match_item(item_name)

            if not item_result:
                return {
                    "found": False,
                    "search_term": item_name,
                    "message": "Item not found in our menu",
                }

            # Format the response
            return {
                "found": True,
                "item": {
                    "name": item_result.get("name"),
                    "plu": item_result.get("plu"),
                    "price": f"${item_result.get('price', 0) / 100:.2f}",
                    "description": item_result.get("description", ""),
                    "category": item_result.get("category_name", ""),
                    "available": item_result.get("is_available", True),
                    "match_score": score,
                },
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
                    {"id": cat.id, "name": cat.name, "description": cat.description}
                    for cat in categories
                ],
                "count": len(categories),
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
                return {"items": [], "error": f"Category '{category_name}' not found"}

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
                        "available": item.is_available,
                    }
                    for item in items
                    if item.is_available  # Only show available items
                ],
                "count": len(items),
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
                        "available": item.is_available,
                    }
                    for item in items
                ],
                "count": len(items),
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
                return {"found": False, "plu": item_plu, "error": "Item not found"}

            # Get modifier groups if available
            modifier_groups = []
            if hasattr(item, "modifier_groups"):
                for group in item.modifier_groups:
                    modifiers = []
                    if hasattr(group, "modifiers"):
                        modifiers = [
                            {
                                "name": mod.name,
                                "price_change": f"${mod.price_change / 100:.2f}"
                                if mod.price_change
                                else "No charge",
                                "plu": mod.plu,
                            }
                            for mod in group.modifiers
                        ]

                    modifier_groups.append(
                        {
                            "name": group.name,
                            "required": group.min_selection > 0,
                            "min_selection": group.min_selection,
                            "max_selection": group.max_selection,
                            "modifiers": modifiers,
                        }
                    )

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
                    "image_url": item.image_url,
                },
            }

        except Exception as e:
            logger.error(f"Error getting item details: {e}")
            return {"found": False, "error": str(e)}
