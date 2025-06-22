"""
Response cache for common conversational patterns.
Speeds up responses by caching common replies.
"""

import time
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class ResponseCache:
    """Simple in-memory cache for common responses."""
    
    def __init__(self, ttl: int = 3600):
        """
        Initialize response cache.
        
        Args:
            ttl: Time to live in seconds (default: 1 hour)
        """
        self._cache: Dict[str, Tuple[Dict, float]] = {}
        self._ttl = ttl
        
        # Pre-populate with common responses
        self._initialize_common_responses()
    
    def _initialize_common_responses(self):
        """Pre-populate cache with common conversational responses."""
        from app.config import settings
        
        common_responses = {
            # Greetings
            "greeting_initial": {
                "text": f"Hello! Welcome to {settings.RESTAURANT_NAME}. I'm {settings.RESTAURANT_GREETING_NAME}, and I'll be helping you today. What's your name?",
                "actions": []
            },
            
            # Common acknowledgments
            "acknowledge_order_start": {
                "text": "Great! I'd be happy to help you place an order. What would you like to have today?",
                "actions": []
            },
            
            # Menu questions
            "menu_categories": {
                "text": "We have various categories on our menu. What type of items are you interested in?",
                "actions": []
            },
            
            # Order completion
            "order_completion_check": {
                "text": "Is there anything else you'd like to add to your order?",
                "actions": []
            },
            
            # Confirmations
            "order_confirmed": {
                "text": "Perfect! I've confirmed your order. ",
                "actions": []
            }
        }
        
        # Add to cache with current timestamp
        current_time = time.time()
        for key, response in common_responses.items():
            self._cache[key] = (response, current_time)
    
    def get(self, key: str) -> Optional[Dict]:
        """
        Get cached response if available and not expired.
        
        Args:
            key: Cache key
            
        Returns:
            Cached response or None if not found/expired
        """
        if key not in self._cache:
            return None
        
        response, timestamp = self._cache[key]
        
        # Check if expired
        if time.time() - timestamp > self._ttl:
            del self._cache[key]
            return None
        
        return response.copy()  # Return a copy to prevent modification
    
    def set(self, key: str, response: Dict):
        """
        Cache a response.
        
        Args:
            key: Cache key
            response: Response to cache
        """
        self._cache[key] = (response.copy(), time.time())
    
    def get_for_pattern(self, input_text: str, state: str) -> Optional[Dict]:
        """
        Get cached response for common patterns.
        
        Args:
            input_text: User input
            state: Current conversation state
            
        Returns:
            Cached response or None
        """
        input_lower = input_text.lower()
        
        # Check for common patterns
        if state == "GREETING" and not input_text:
            return self.get("greeting_initial")
        
        if state == "MAIN_MENU":
            if any(phrase in input_lower for phrase in ["order", "place an order", "want to order"]):
                return self.get("acknowledge_order_start")
            elif any(phrase in input_lower for phrase in ["menu", "what do you have", "options"]):
                return self.get("menu_categories")
        
        if state == "ORDERING":
            if any(phrase in input_lower for phrase in ["that's all", "done", "complete", "finished"]):
                return self.get("order_completion_check")
        
        if state == "CONFIRMATION":
            if any(phrase in input_lower for phrase in ["yes", "correct", "confirm", "that's right"]):
                return self.get("order_confirmed")
        
        return None


# Global instance
response_cache = ResponseCache()