"""
Enhanced AI response caching system using centralized cache service.

This module provides optimized caching for AI responses with:
- Multi-tier caching (memory + Redis)
- Pattern-based matching for common queries
- Context-aware cache keys
- Fast synchronous fallbacks
"""

import hashlib
import json
import re
import time
from typing import Dict, Any, Optional, List, Callable
import asyncio

from app.services.cache_service import cache_service
from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)


class AIResponseCacheEnhanced:
    """Enhanced AI response cache with centralized caching."""
    
    def __init__(self):
        """Initialize enhanced AI response cache."""
        self.namespace = "ai_response"
        self.pattern_namespace = "ai_pattern"
        self.default_ttl = 300  # 5 minutes default
        self._patterns_initialized = False
    
    async def _ensure_patterns_initialized(self):
        """Ensure patterns are initialized."""
        if not self._patterns_initialized:
            await self._initialize_patterns()
    
    async def _initialize_patterns(self):
        """Initialize common conversation patterns."""
        patterns = {
            # Greeting patterns
            "single_name": {
                "pattern": r"^[A-Z][a-z]+$",
                "states": ["GREETING"],
                "priority": 100,
                "response_template": {
                    "text": "Nice to meet you, {name}! How can I help you today?",
                    "tool_calls": [{
                        "function": {
                            "name": "update_customer_info",
                            "arguments": {"name": "{name}"}
                        }
                    }],
                    "actions": [{"type": "set_customer_name", "name": "{name}"}]
                }
            },
            "name_introduction": {
                "pattern": r"(my name is|i'm|this is|call me)\s+([A-Za-z]+)",
                "states": ["GREETING", "MAIN_MENU"],
                "priority": 90,
                "response_template": {
                    "text": "Nice to meet you, {name}! What can I help you with today?",
                    "tool_calls": [{
                        "function": {
                            "name": "update_customer_info",
                            "arguments": {"name": "{name}"}
                        }
                    }],
                    "actions": [{"type": "set_customer_name", "name": "{name}"}]
                }
            },
            
            # Ordering patterns
            "want_to_order": {
                "pattern": r"(want to order|place an order|order food|hungry|ready to order)",
                "states": ["MAIN_MENU", "GREETING"],
                "priority": 80,
                "response_template": {
                    "text": "Great! I'd be happy to help you place an order. What would you like today?",
                    "actions": []
                }
            },
            "view_menu": {
                "pattern": r"(show.*menu|what.*have|menu|options)",
                "states": ["MAIN_MENU", "ORDERING"],
                "priority": 70,
                "response_template": {
                    "text": "We have appetizers, sushi rolls, sashimi, nigiri, and beverages. What category would you like to explore?",
                    "actions": []
                }
            },
            
            # Order completion patterns
            "order_complete": {
                "pattern": r"(that's all|done|finished|complete|ready|nothing else)",
                "states": ["ORDERING"],
                "priority": 90,
                "response_template": {
                    "text": "Perfect! Let me confirm your order for you.",
                    "actions": []
                }
            },
            
            # Cart operations
            "view_cart": {
                "pattern": r"(what's in my|show.*cart|my order|repeat.*order)",
                "states": ["ORDERING", "CONFIRMATION"],
                "priority": 80,
                "response_template": {
                    "text": "Let me show you what's in your cart.",
                    "requires_context": True,
                    "actions": []
                }
            }
        }
        
        # Store patterns in cache
        for pattern_id, pattern_data in patterns.items():
            await cache_service.set(
                pattern_id,
                pattern_data,
                namespace=self.pattern_namespace,
                ttl=86400  # 24 hours for patterns
            )
        
        logger.info(f"Initialized {len(patterns)} AI response patterns")
        self._patterns_initialized = True
    
    def _generate_cache_key(self, input_text: str, state: str, context: Dict[str, Any]) -> str:
        """
        Generate a context-aware cache key.
        
        Args:
            input_text: User input
            state: Current FSM state
            context: Conversation context
            
        Returns:
            Cache key hash
        """
        # Normalize input
        normalized_input = input_text.lower().strip()
        
        # Extract relevant context features
        context_features = {
            "input": normalized_input,
            "state": state,
            "has_name": bool(context.get("customer_name")),
            "cart_size": len(context.get("cart", {}).get("items", [])),
            "order_type": context.get("order_type", "unknown")
        }
        
        # Create stable hash
        cache_str = json.dumps(context_features, sort_keys=True)
        return hashlib.sha256(cache_str.encode()).hexdigest()[:16]
    
    async def get(self, input_text: str, state: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get cached AI response.
        
        Args:
            input_text: User input
            state: Current FSM state
            context: Conversation context
            
        Returns:
            Cached response or None
        """
        # Try exact match first
        cache_key = self._generate_cache_key(input_text, state, context)
        cached_response = await cache_service.get(cache_key, namespace=self.namespace)
        
        if cached_response:
            logger.debug(f"AI cache hit (exact): {input_text[:30]}...")
            return cached_response
        
        # Try pattern matching
        await self._ensure_patterns_initialized()
        pattern_response = await self._match_patterns(input_text, state, context)
        if pattern_response:
            logger.debug(f"AI cache hit (pattern): {input_text[:30]}...")
            return pattern_response
        
        logger.debug(f"AI cache miss: {input_text[:30]}...")
        return None
    
    async def set(
        self, 
        input_text: str, 
        state: str, 
        context: Dict[str, Any], 
        response: Dict[str, Any]
    ):
        """
        Cache an AI response.
        
        Args:
            input_text: User input
            state: Current FSM state
            context: Conversation context
            response: AI response to cache
        """
        # Don't cache responses with errors or dynamic tool results
        if response.get("error") or response.get("tool_results"):
            logger.debug("Skipping cache for dynamic/error response")
            return
        
        # Don't cache responses that are too personalized
        if any(key in str(response).lower() for key in ["order_id", "transaction", "payment"]):
            logger.debug("Skipping cache for personalized response")
            return
        
        cache_key = self._generate_cache_key(input_text, state, context)
        
        # Use shorter TTL for ordering state (more dynamic)
        ttl = self.default_ttl
        if state in ["ORDERING", "CONFIRMATION"]:
            ttl = 180  # 3 minutes
        elif state == "GREETING":
            ttl = 600  # 10 minutes
        
        await cache_service.set(
            cache_key,
            response,
            namespace=self.namespace,
            ttl=ttl
        )
        
        logger.debug(f"Cached AI response: {input_text[:30]}... (TTL: {ttl}s)")
    
    async def _match_patterns(
        self, 
        input_text: str, 
        state: str, 
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Match input against cached patterns.
        
        Args:
            input_text: User input
            state: Current FSM state
            context: Conversation context
            
        Returns:
            Generated response or None
        """
        # Get all pattern IDs (could be optimized with pattern index)
        pattern_ids = [
            "single_name", "name_introduction", "want_to_order", 
            "view_menu", "order_complete", "view_cart"
        ]
        
        matches = []
        
        for pattern_id in pattern_ids:
            pattern_data = await cache_service.get(pattern_id, namespace=self.pattern_namespace)
            if not pattern_data:
                continue
            
            # Check state compatibility
            if state not in pattern_data.get("states", []):
                continue
            
            # Try to match pattern
            pattern = pattern_data.get("pattern")
            match = re.search(pattern, input_text, re.IGNORECASE)
            if match:
                matches.append((pattern_data, match))
        
        if not matches:
            return None
        
        # Sort by priority and select best match
        matches.sort(key=lambda x: x[0].get("priority", 0), reverse=True)
        best_pattern, match = matches[0]
        
        # Generate response from template
        response_template = best_pattern.get("response_template", {})
        response = json.loads(json.dumps(response_template))  # Deep copy
        
        # Apply substitutions
        if match.groups():
            # Extract captured groups
            if "name" in response.get("text", ""):
                # For name patterns, use the last captured group
                name = match.groups()[-1].strip().capitalize()
                response["text"] = response["text"].replace("{name}", name)
                
                # Update tool calls
                if response.get("tool_calls"):
                    for tool_call in response["tool_calls"]:
                        args = tool_call["function"]["arguments"]
                        if isinstance(args, dict) and "name" in args:
                            args["name"] = name
                
                # Update actions
                if response.get("actions"):
                    for action in response["actions"]:
                        if action.get("name") == "{name}":
                            action["name"] = name
        
        # Check if context is required
        if response.get("requires_context"):
            # This response needs dynamic context (e.g., cart contents)
            # Return None to force actual AI processing
            return None
        
        # Add metadata
        response["cached_pattern"] = pattern_id
        response["cache_hit"] = True
        
        return response
    
    def get_fast_response(self, input_text: str, state: str) -> Optional[str]:
        """
        Get ultra-fast synchronous response for common patterns.
        
        This is used for immediate feedback while AI processes.
        
        Args:
            input_text: User input
            state: Current FSM state
            
        Returns:
            Fast response text or None
        """
        input_lower = input_text.lower().strip()
        
        # Define fast responses by state
        fast_responses = {
            "GREETING": [
                (r"^[a-z]+$", lambda: f"Nice to meet you! How can I help you today?"),
                (r"^(hi|hello|hey)", lambda: "Hello! Welcome to our restaurant. May I have your name?"),
            ],
            "MAIN_MENU": [
                (r"(order|hungry|food)", lambda: "Great! What would you like to order today?"),
                (r"(menu|options)", lambda: "I can help you explore our menu categories."),
                (r"(pickup|delivery)", lambda: "Sure! I can help you with that."),
            ],
            "ORDERING": [
                (r"(done|finished|that's all)", lambda: "Let me confirm your order..."),
                (r"(add|want|like)", lambda: "I'll help you add that."),
                (r"(remove|delete)", lambda: "I'll help you remove that."),
                (r"(cart|order)", lambda: "Let me check your cart..."),
            ],
            "CONFIRMATION": [
                (r"(yes|confirm|correct)", lambda: "Perfect! Processing your order..."),
                (r"(no|change|modify)", lambda: "No problem, let's make changes."),
            ]
        }
        
        # Check patterns for current state
        if state in fast_responses:
            for pattern, response_func in fast_responses[state]:
                if re.search(pattern, input_lower):
                    try:
                        return response_func()
                    except Exception as e:
                        logger.error(f"Fast response error: {e}")
        
        # Generic fallback
        return "I'm processing your request..."
    
    async def warm_cache(self, common_queries: List[Dict[str, Any]]):
        """
        Warm cache with common queries.
        
        Args:
            common_queries: List of {input, state, context, response} dicts
        """
        logger.info(f"Warming AI cache with {len(common_queries)} queries...")
        
        success_count = 0
        for query in common_queries:
            try:
                await self.set(
                    query["input"],
                    query["state"],
                    query.get("context", {}),
                    query["response"]
                )
                success_count += 1
            except Exception as e:
                logger.error(f"Error warming cache: {e}")
        
        logger.info(f"AI cache warmed with {success_count}/{len(common_queries)} queries")
    
    async def clear(self):
        """Clear all AI response caches."""
        await cache_service.clear_namespace(self.namespace)
        logger.info("AI response cache cleared")
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get AI cache statistics."""
        # Get general cache stats
        stats = cache_service.get_stats()
        
        # Add AI-specific information
        pattern_count = 0
        pattern_ids = [
            "single_name", "name_introduction", "want_to_order",
            "view_menu", "order_complete", "view_cart"
        ]
        
        for pattern_id in pattern_ids:
            if await cache_service.get(pattern_id, namespace=self.pattern_namespace):
                pattern_count += 1
        
        stats["ai_patterns"] = {
            "loaded": pattern_count,
            "total": len(pattern_ids)
        }
        
        return stats


# Global instance
ai_cache_enhanced = AIResponseCacheEnhanced()


# Convenience decorator for caching AI responses
def cached_ai_response(state: Optional[str] = None, ttl: Optional[int] = None):
    """
    Decorator for caching AI agent responses.
    
    Usage:
        @cached_ai_response(state="ORDERING", ttl=300)
        async def process_order_query(self, input_text, context):
            # AI processing
            return response
    """
    def decorator(func: Callable):
        async def wrapper(self, input_text: str, context: Dict[str, Any], *args, **kwargs):
            # Determine state
            current_state = state or context.get("conversation_state", "UNKNOWN")
            
            # Check cache
            cached = await ai_cache_enhanced.get(input_text, current_state, context)
            if cached:
                return cached
            
            # Call original function
            response = await func(self, input_text, context, *args, **kwargs)
            
            # Cache result
            await ai_cache_enhanced.set(input_text, current_state, context, response)
            
            return response
        
        return wrapper
    return decorator