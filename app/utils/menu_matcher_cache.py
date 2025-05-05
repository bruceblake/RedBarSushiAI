"""
Enhanced menu matching with Redis caching for RedBarSushiAI.
This module enhances menu_matcher_db.py with Redis caching for faster lookups.
"""

import logging
import json
import time
from typing import Dict, List, Any, Optional, Tuple

from app.utils.menu_matcher_db import MenuMatcher as BaseMenuMatcher
from app.utils.menu_cache_sdk import menu_cache, with_menu_cache

logger = logging.getLogger(__name__)

class CachedMenuMatcher(BaseMenuMatcher):
    """
    Enhanced MenuMatcher with Redis caching for faster lookups.
    This class wraps the original MenuMatcher, adding caching for performance.
    """
    
    def __init__(self):
        """Initialize the cached menu matcher."""
        super().__init__()
        self.cache = menu_cache
    
    @with_menu_cache(ttl=3600)  # Cache for 1 hour
    def find_menu_item(
        self,
        item_name: str,
        check_availability: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Find a menu item with Redis caching.
        Tries to get the result from cache first, then falls back to the regular implementation.
        
        Args:
            item_name: Name of the item requested by the customer
            check_availability: Only return available items if True
            context: Additional context about the order/conversation
            
        Returns:
            dict or None: The matched menu item if found, None otherwise
        """
        # The actual implementation is handled by the @with_menu_cache decorator
        # which will handle caching logic and call the parent class method if needed
        return super().find_menu_item(item_name, check_availability, context)
    
    def _find_exact_match(
        self, item_name: str, check_availability: bool
    ) -> Optional[Dict[str, Any]]:
        """
        Find an exact match for the item name with Redis caching.
        
        Args:
            item_name: The name of the item
            check_availability: Flag to check item availability
            
        Returns:
            The menu item if found, None otherwise
        """
        # Clean up the name for comparison
        cleaned_name = item_name.lower().strip()
        
        # Try to get from name variants cache
        variants = self.cache.get_name_variants()
        if variants and cleaned_name in variants:
            plu = variants[cleaned_name]
            item = self.cache.get_menu_item(plu)
            
            if item:
                # Apply availability check if needed
                if not check_availability or (
                    item.get("available", True) and not item.get("snoozed", False)
                ):
                    return item
        
        # Fall back to original implementation
        return super()._find_exact_match(item_name, check_availability)
    
    @with_menu_cache(ttl=300)  # Cache for 5 minutes
    def _find_fast_fuzzy_match(
        self, item_name: str, check_availability: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Use fast local fuzzy matching with caching.
        
        Args:
            item_name: The name of the item
            check_availability: Flag to check item availability
            
        Returns:
            The matched menu item if found, None otherwise
        """
        # The actual implementation is handled by the @with_menu_cache decorator
        return super()._find_fast_fuzzy_match(item_name, check_availability)
    
    @with_menu_cache(ttl=300)  # Cache for 5 minutes
    def _find_ai_match(
        self, 
        item_name: str, 
        check_availability: bool = False, 
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Use AI to match menu items with caching.
        
        Args:
            item_name: The name of the item
            check_availability: Flag to check item availability
            context: Additional context for AI matching
            
        Returns:
            The matched menu item if found, None otherwise
        """
        # The actual implementation is handled by the @with_menu_cache decorator
        return super()._find_ai_match(item_name, check_availability, context)
    
    @with_menu_cache(ttl=600)  # Cache for 10 minutes
    def interactive_order_resolution(
        self,
        customer_request: str,
        context: Dict[str, Any] = None,
        session_id: str = None,
    ) -> Dict[str, Any]:
        """
        Interactively resolve an order with caching.
        
        Args:
            customer_request: The customer's original request
            context: Additional context about the conversation
            session_id: Unique identifier for the conversation session
            
        Returns:
            The resolved order with clarification dialog
        """
        # For interactive resolution, we only cache when there is no session_id,
        # as session-based interactions are stateful and shouldn't be cached
        if session_id:
            # Skip cache for session-based interactions
            return super().interactive_order_resolution(
                customer_request, context, session_id
            )
        else:
            # The actual implementation is handled by the @with_menu_cache decorator
            return super().interactive_order_resolution(
                customer_request, context, session_id
            )
    
    def invalidate_cache_for_item(self, plu: str):
        """
        Invalidate cache for a specific menu item.
        
        Args:
            plu: The PLU of the item to invalidate
        """
        self.cache.invalidate_item(plu)
        # Also publish an update to inform other instances
        self.cache.publish_update("item", plu=plu)
    
    def invalidate_all_cache(self):
        """Invalidate all menu cache."""
        self.cache.invalidate_all()
        # Also publish an update to inform other instances
        self.cache.publish_update("all")

# Create cached matcher instance
cached_menu_matcher = CachedMenuMatcher()