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
        Enhanced menu item lookup using Deliverect cache with fuzzy matching and confidence scores.
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
        
        try:
            # Get all cached products
            products = await deliverect_service.get_all_cached_products()
            if not products:
                # Fallback to database if cache is empty
                logger.warning("No cached products found, falling back to database")
                return await self._fallback_lookup_menu_item(item_name)
            
            # Perform fuzzy matching with confidence scores
            matches = []
            search_term = item_name.lower().strip()
            normalized_search = normalize_for_matching(search_term)
            
            for product in products:
                # Skip snoozed items unless explicitly requested
                if product.snoozed:
                    continue
                    
                product_name = product.name.lower()
                normalized_product = normalize_for_matching(product_name)
                
                # Calculate different types of matching scores using both original and normalized text
                exact_match = 1.0 if search_term == product_name or normalized_search == normalized_product else 0.0
                contains_match = 0.8 if search_term in product_name or normalized_search in normalized_product else 0.0
                reverse_contains = 0.7 if product_name in search_term or normalized_product in normalized_search else 0.0
                
                # Use difflib for sequence matching on normalized text (better for punctuation differences)
                sequence_similarity = difflib.SequenceMatcher(None, normalized_search, normalized_product).ratio()
                
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
                        'product': product,
                        'confidence': confidence
                    })
            
            # Sort by confidence score (highest first)
            matches.sort(key=lambda x: x['confidence'], reverse=True)
            
            if not matches:
                # Try alternative search with lower threshold or suggest alternatives
                return await self._generate_alternatives(search_term, products)
            
            # Get the best match
            best_match = matches[0]
            best_product = best_match['product']
            confidence = best_match['confidence']
            
            # Get modifier groups and modifiers for this product
            modifier_groups = []
            modifiers = {}
            
            for group_plu in best_product.sub_products:
                group = await deliverect_service.get_cached_modifier_group(group_plu)
                if group:
                    modifier_groups.append(group)
                    
                    # Get individual modifiers in this group
                    for modifier_plu in group.sub_products:
                        modifier = await deliverect_service.get_cached_modifier(modifier_plu)
                        if modifier:
                            modifiers[modifier_plu] = modifier
            
            # Create structured result
            result = MenuLookupResult(
                found=True,
                confidence=confidence,
                item=best_product,
                modifier_groups=modifier_groups,
                modifiers=modifiers
            )
            
            # Check if disambiguation is needed (multiple high-confidence matches)
            high_confidence_matches = [m for m in matches if m['confidence'] >= 0.7]
            if len(high_confidence_matches) > 1 and confidence < 0.9:
                # Multiple good matches - offer disambiguation
                alternatives = []
                for match in high_confidence_matches[:4]:  # Limit to 4 options
                    alternatives.append(match['product'])
                
                result.suggested_alternatives = alternatives
                
                return {
                    "found": True,
                    "confidence": confidence,
                    "item": result.item.dict(),
                    "modifier_groups": [g.dict() for g in result.modifier_groups],
                    "modifiers": {k: v.dict() for k, v in result.modifiers.items()},
                    "needs_disambiguation": True,
                    "alternatives": [alt.dict() for alt in alternatives],
                    "has_required_modifiers": result.has_required_modifiers,
                    "required_modifier_groups": [g.dict() for g in result.required_modifier_groups]
                }
            
            # Single clear match - return full structured result
            return {
                "found": True,
                "confidence": confidence,
                "item": result.item.dict(),
                "modifier_groups": [g.dict() for g in result.modifier_groups],
                "modifiers": {k: v.dict() for k, v in result.modifiers.items()},
                "has_required_modifiers": result.has_required_modifiers,
                "required_modifier_groups": [g.dict() for g in result.required_modifier_groups],
                "message": f"Found {best_product.name} with {confidence:.1%} confidence"
            }
            
        except Exception as e:
            logger.error(f"Error in enhanced menu lookup: {e}")
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
        Enhanced get detailed information about a menu item including all modifiers.
        Uses Deliverect cache for comprehensive modifier information.
        """
        if not item_plu.strip():
            return {"found": False, "error": "PLU cannot be empty"}
        
        try:
            # Get product from Deliverect cache
            product = await deliverect_service.get_cached_product(item_plu)
            
            if not product:
                # Fallback to database
                return await self._fallback_get_item_details(item_plu)
            
            # Get all modifier groups and modifiers for this product
            modifier_groups = []
            modifiers = {}
            
            for group_plu in product.sub_products:
                group = await deliverect_service.get_cached_modifier_group(group_plu)
                if group:
                    # Get individual modifiers in this group
                    group_modifiers = []
                    for modifier_plu in group.sub_products:
                        modifier = await deliverect_service.get_cached_modifier(modifier_plu)
                        if modifier:
                            modifiers[modifier_plu] = modifier
                            group_modifiers.append({
                                "name": modifier.name,
                                "plu": modifier.plu,
                                "price": modifier.price,  # Price in cents
                                "price_formatted": f"${modifier.price / 100:.2f}" if modifier.price > 0 else "No charge",
                                "snoozed": modifier.snoozed,
                                "available": not modifier.snoozed
                            })
                    
                    modifier_groups.append({
                        "name": group.name,
                        "plu": group.plu,
                        "required": group.min_selection > 0,
                        "min_selection": group.min_selection,
                        "max_selection": group.max_selection,
                        "multi_max": group.multi_max,
                        "is_variant_group": group.is_variant_group,
                        "snoozed": group.snoozed,
                        "modifiers": group_modifiers
                    })
            
            return {
                "found": True,
                "item": {
                    "name": product.name,
                    "plu": product.plu,
                    "price": product.price,  # Price in cents
                    "price_formatted": f"${product.price / 100:.2f}",
                    "description": product.description,
                    "snoozed": product.snoozed,
                    "available": not product.snoozed,
                    "is_variant": product.is_variant,
                    "product_tags": product.product_tags,
                    "modifier_groups": modifier_groups,
                    "total_modifier_groups": len(modifier_groups),
                    "has_required_modifiers": any(g["required"] for g in modifier_groups)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting enhanced item details: {e}")
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
        Get popular/recommended items, optionally filtered by category.
        For now, returns available items. In the future, this could be based on order frequency.
        """
        try:
            products = await deliverect_service.get_all_cached_products()
            if not products:
                return {"error": "No menu data available"}
            
            # Filter available items
            available_products = [p for p in products if not p.snoozed]
            
            # If category specified, filter by category (would need category mapping)
            if category:
                # For now, use simple name matching. In production, you'd have proper category mapping
                category_lower = category.lower()
                filtered_products = []
                for product in available_products:
                    # Simple heuristic: check if category words appear in product name or description
                    product_text = f"{product.name} {product.description}".lower()
                    if any(word in product_text for word in category_lower.split()):
                        filtered_products.append(product)
                
                available_products = filtered_products
            
            # Return first max_results items (in future, sort by popularity)
            popular_items = available_products[:max_results]
            
            return {
                "items": [p.dict() for p in popular_items],
                "count": len(popular_items),
                "category_filter": category,
                "message": f"Here are {len(popular_items)} popular items" + (f" in {category}" if category else "")
            }
            
        except Exception as e:
            logger.error(f"Error getting popular items: {e}")
            return {"error": str(e)}
    
    async def _check_item_availability(self, item_plu: str) -> Dict[str, Any]:
        """Check if a specific item is currently available (not snoozed)."""
        try:
            availability = await deliverect_service.check_item_availability(item_plu)
            
            return {
                "plu": availability.plu,
                "name": availability.name,
                "is_available": availability.is_available,
                "snoozed": availability.snoozed,
                "reason": availability.reason,
                "estimated_available_time": availability.estimated_available_time
            }
            
        except Exception as e:
            logger.error(f"Error checking item availability: {e}")
            return {"error": str(e)}