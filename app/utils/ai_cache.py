"""
Advanced AI response caching system for ultra-fast responses.
Caches AI responses based on input patterns and conversation state.
"""

import hashlib
import json
import time
import asyncio
from typing import Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class AIResponseCache:
    """Advanced caching system for AI responses with pattern matching."""
    
    def __init__(self, ttl: int = 3600):
        """
        Initialize AI response cache.
        
        Args:
            ttl: Time to live in seconds (default: 1 hour)
        """
        self._cache: Dict[str, Tuple[Dict, float]] = {}
        self._pattern_cache: Dict[str, Tuple[Dict, float]] = {}
        self._ttl = ttl
        self._lock = asyncio.Lock()
        
        # Pre-populate with common patterns
        self._initialize_patterns()
    
    def _initialize_patterns(self):
        """Pre-populate cache with common conversational patterns."""
        current_time = time.time()
        
        # Name recognition patterns
        name_patterns = {
            # Single names
            "single_name_greeting": {
                "pattern": r"^[A-Z][a-z]+$",
                "state": "GREETING",
                "response": {
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
            # Common ordering patterns
            "want_to_order": {
                "pattern": r"(want to order|place an order|order food|hungry)",
                "state": "MAIN_MENU",
                "response": {
                    "text": "Great! I'd be happy to help you place an order. What would you like today?",
                    "actions": []
                }
            },
            # Item ordering patterns
            "order_item_quantity": {
                "pattern": r"(\d+|one|two|three|four|five)\s+(\w+\s*)+",
                "state": "ORDERING",
                "response": {
                    "text": "I'll add that to your order.",
                    "requires_lookup": True
                }
            },
            # Completion patterns
            "order_complete": {
                "pattern": r"(that's all|done|finished|complete|ready)",
                "state": "ORDERING",
                "response": {
                    "text": "Perfect! Let me confirm your order.",
                    "actions": []
                }
            }
        }
        
        # Store patterns
        for key, pattern_data in name_patterns.items():
            self._pattern_cache[key] = (pattern_data, current_time)
    
    def _generate_cache_key(self, input_text: str, state: str, context: Dict[str, Any]) -> str:
        """Generate a unique cache key based on input and context."""
        # Include relevant context in cache key
        cache_data = {
            "input": input_text.lower().strip(),
            "state": state,
            "has_name": bool(context.get("customer_name")),
            "cart_items": len(context.get("cart", {}).get("items", []))
        }
        
        # Create hash
        cache_str = json.dumps(cache_data, sort_keys=True)
        return hashlib.md5(cache_str.encode()).hexdigest()
    
    async def get(self, input_text: str, state: str, context: Dict[str, Any]) -> Optional[Dict]:
        """
        Get cached response if available.
        
        Args:
            input_text: User input
            state: Current conversation state
            context: Conversation context
            
        Returns:
            Cached response or None
        """
        async with self._lock:
            # Check exact match first
            cache_key = self._generate_cache_key(input_text, state, context)
            if cache_key in self._cache:
                response, timestamp = self._cache[cache_key]
                if time.time() - timestamp < self._ttl:
                    logger.debug(f"Cache hit for exact match: {input_text[:30]}...")
                    return response.copy()
            
            # Check pattern matches
            import re
            for pattern_key, (pattern_data, timestamp) in self._pattern_cache.items():
                if time.time() - timestamp > self._ttl:
                    continue
                
                if pattern_data.get("state") != state:
                    continue
                
                pattern = pattern_data.get("pattern", "")
                if re.search(pattern, input_text, re.IGNORECASE):
                    response = pattern_data.get("response", {}).copy()
                    
                    # Handle dynamic replacements
                    if "{name}" in response.get("text", ""):
                        # Extract name from input
                        name = input_text.strip()
                        if " " not in name and name[0].isupper():
                            response["text"] = response["text"].replace("{name}", name)
                            
                            # Update tool calls if present
                            if response.get("tool_calls"):
                                for tool_call in response["tool_calls"]:
                                    if isinstance(tool_call["function"]["arguments"], str):
                                        tool_call["function"]["arguments"] = tool_call["function"]["arguments"].replace("{name}", name)
                            
                            # Update actions if present
                            if response.get("actions"):
                                for action in response["actions"]:
                                    if action.get("name") == "{name}":
                                        action["name"] = name
                            
                            logger.debug(f"Cache hit for pattern: {pattern_key}")
                            return response
                    else:
                        logger.debug(f"Cache hit for pattern: {pattern_key}")
                        return response
            
            return None
    
    async def set(self, input_text: str, state: str, context: Dict[str, Any], response: Dict):
        """
        Cache a response.
        
        Args:
            input_text: User input
            state: Current conversation state
            context: Conversation context
            response: Response to cache
        """
        async with self._lock:
            cache_key = self._generate_cache_key(input_text, state, context)
            self._cache[cache_key] = (response.copy(), time.time())
            
            # Limit cache size
            if len(self._cache) > 1000:
                # Remove oldest entries
                sorted_items = sorted(self._cache.items(), key=lambda x: x[1][1])
                for key, _ in sorted_items[:100]:
                    del self._cache[key]
    
    def get_fast_response(self, input_text: str, state: str) -> Optional[str]:
        """
        Get a fast pre-generated response for common patterns.
        Synchronous method for immediate responses.
        """
        input_lower = input_text.lower().strip()
        
        # Ultra-fast responses for common patterns
        fast_responses = {
            "GREETING": {
                # Single word names
                r"^[a-z]+$": lambda: f"Nice to meet you, {input_text.capitalize()}! How can I help you today?",
                r"^my name is (.+)$": lambda m: f"Nice to meet you, {m.group(1).capitalize()}! How can I help you today?",
                r"^i'm (.+)$": lambda m: f"Nice to meet you, {m.group(1).capitalize()}! How can I help you today?",
                r"^this is (.+)$": lambda m: f"Nice to meet you, {m.group(1).capitalize()}! How can I help you today?",
            },
            "MAIN_MENU": {
                r"order|hungry|food": lambda: "Great! I'd be happy to help you place an order. What would you like today?",
                r"menu|what do you have": lambda: "We have various menu categories. What type of items are you interested in?",
                r"pickup|delivery": lambda: "We offer both pickup and delivery. Which would you prefer?",
            },
            "ORDERING": {
                r"that's all|done|finished": lambda: "Perfect! Let me confirm your order for you.",
                r"add|want|like": lambda: "I'll add that to your order.",
                r"remove|delete|cancel": lambda: "I'll remove that from your order.",
                r"what's in my|show.*cart": lambda: "Let me show you what's in your cart.",
            }
        }
        
        # Check patterns for current state
        import re
        if state in fast_responses:
            for pattern, response_func in fast_responses[state].items():
                match = re.search(pattern, input_lower)
                if match:
                    if callable(response_func):
                        try:
                            if match.groups():
                                return response_func(match)
                            else:
                                return response_func()
                        except:
                            pass
        
        return None


# Global instance
ai_cache = AIResponseCache()