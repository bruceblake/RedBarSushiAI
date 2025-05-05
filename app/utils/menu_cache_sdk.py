"""
Redis-based menu caching for RedBarSushiAI using OpenAI Agents SDK.
This module provides a fast, in-memory cache for menu data with Postgres as the source of truth.
"""

import json
import logging
import time
from typing import Dict, List, Any, Optional, Set, Union
import redis
import os
from functools import wraps

from app.utils.agents_sdk import get_redis_client

logger = logging.getLogger(__name__)

# Default TTL for cached menu items (1 hour)
DEFAULT_MENU_TTL = 3600  

# Channel name for menu update events
MENU_UPDATE_CHANNEL = "menu:updated"

class MenuCache:
    """Redis-based menu caching with PostgreSQL as the source of truth."""
    
    def __init__(self):
        """Initialize the menu cache."""
        self.redis_client = None
        self.initialized = False
        self.initialize_redis()
        
        # Subscribe to menu update events if Redis is available
        # This will be used to invalidate cache when menu items are updated
        self.pubsub = None
        if self.redis_client:
            self.setup_pubsub()
    
    def initialize_redis(self):
        """Initialize the Redis connection."""
        try:
            # Try multiple approaches to get a Redis client
            
            # Approach 1: Using agents_sdk module (may fail outside app context)
            try:
                self.redis_client = get_redis_client()
                if self.redis_client:
                    self.redis_client.ping()
                    self.initialized = True
                    logger.info("Redis menu cache initialized successfully using agents_sdk client")
                    return
            except Exception as e:
                logger.warning(f"Failed to get Redis client from agents_sdk: {str(e)}")
            
            # Approach 2: Try direct Redis initialization
            try:
                # Try to get Redis URL from environment variables
                redis_url = os.environ.get("REDIS_URL") or os.environ.get("CELERY_BROKER_URL")
                
                # If no Redis URL found, try default URLs for development and Docker environments
                if not redis_url:
                    logger.warning("No Redis URL found in environment variables, trying defaults")
                    # Try known Redis URLs in order of likelihood
                    for url in [
                        "redis://redis:6379/0",  # Docker Compose service name
                        "redis://localhost:6379/0",  # Local development
                        "redis://127.0.0.1:6379/0"   # Alternative local format
                    ]:
                        try:
                            # Test the connection with a 1-second timeout
                            test_client = redis.Redis.from_url(url, socket_timeout=1.0)
                            test_client.ping()
                            redis_url = url
                            logger.info(f"Successfully connected to Redis at {url}")
                            break
                        except Exception:
                            continue
                
                # If we have a Redis URL, use it
                if redis_url:
                    self.redis_client = redis.Redis.from_url(redis_url, socket_timeout=2.0)
                    self.redis_client.ping()
                    self.initialized = True
                    logger.info(f"Redis menu cache initialized successfully with URL: {redis_url}")
                    return
            except Exception as e:
                logger.warning(f"Failed to initialize Redis with direct connection: {str(e)}")
            
            # If all approaches failed, disable the cache
            logger.warning("All Redis connection approaches failed, menu cache will be disabled")
            self.redis_client = None
            self.initialized = False
            
        except Exception as e:
            logger.error(f"Error initializing Redis menu cache: {str(e)}")
            self.redis_client = None
            self.initialized = False
    
    def setup_pubsub(self):
        """Set up a Redis PubSub subscription for menu updates."""
        # Skip if Redis client isn't available
        if not self.redis_client or not self.initialized:
            self.pubsub = None
            logger.warning("Redis client not available, skipping PubSub setup")
            return
            
        try:
            self.pubsub = self.redis_client.pubsub()
            self.pubsub.subscribe(MENU_UPDATE_CHANNEL)
            logger.info(f"Subscribed to menu update channel: {MENU_UPDATE_CHANNEL}")
            
            # Start a background thread to handle updates
            # In a production environment, this would be a separate thread or process
            # For now, we'll just check for updates before each cache operation
        except Exception as e:
            logger.error(f"Error setting up Redis PubSub: {str(e)}")
            self.pubsub = None
            
        # Verify the subscription worked
        if self.pubsub:
            try:
                # Process any pending messages (including the subscription confirmation)
                self.pubsub.get_message(timeout=0.01)
                logger.info("PubSub setup confirmed")
            except Exception as e:
                logger.warning(f"Error processing initial PubSub messages: {str(e)}")
                # This isn't critical, we can still proceed
    
    def check_for_updates(self):
        """Check if there are any pending cache invalidation messages."""
        if not self.pubsub:
            return
        
        # Process any pending messages
        try:
            message = self.pubsub.get_message(timeout=0.01)
            while message:
                # Skip subscription confirmation messages
                if message['type'] == 'message':
                    # Parse the message data
                    data = message['data']
                    if isinstance(data, bytes):
                        data = data.decode('utf-8')
                    
                    try:
                        # Parse the message data as JSON
                        update_info = json.loads(data)
                        
                        # Handle different types of updates
                        if update_info.get('type') == 'item':
                            # Invalidate a specific item
                            self.invalidate_item(update_info.get('plu'))
                        elif update_info.get('type') == 'category':
                            # Invalidate a category
                            self.invalidate_category(update_info.get('category_id'))
                        elif update_info.get('type') == 'all':
                            # Invalidate all menu data
                            self.invalidate_all()
                    except json.JSONDecodeError:
                        # If the message is not valid JSON, just log and continue
                        logger.warning(f"Received invalid menu update message: {data}")
                
                # Get next message
                message = self.pubsub.get_message(timeout=0.01)
        except Exception as e:
            logger.error(f"Error processing menu updates: {str(e)}")
    
    def get_menu_item(self, plu: str) -> Optional[Dict[str, Any]]:
        """
        Get a menu item by PLU from the cache.
        If not found in cache, returns None (caller should fetch from DB and cache it).
        
        Args:
            plu: The PLU of the menu item
            
        Returns:
            The menu item if found in cache, None otherwise
        """
        if not self.initialized or not self.redis_client:
            return None
        
        # Check for cache invalidation messages before reading
        self.check_for_updates()
        
        try:
            # Get the item from Redis
            key = f"menu:item:{plu}"
            item_data = self.redis_client.hgetall(key)
            
            if not item_data:
                return None
            
            # Convert from Redis hash to dictionary
            item = {}
            for field, value in item_data.items():
                # Decode bytes to string
                if isinstance(field, bytes):
                    field = field.decode('utf-8')
                if isinstance(value, bytes):
                    value = value.decode('utf-8')
                
                # Convert numeric fields
                if field in ['price', 'id']:
                    try:
                        value = int(value)
                    except (ValueError, TypeError):
                        pass
                
                # Convert boolean fields
                elif field in ['available', 'is_combo', 'is_variant', 'snoozed']:
                    value = value.lower() == 'true'
                
                # Handle nested data stored as JSON
                elif field in ['modifierGroups', 'modifiers']:
                    try:
                        value = json.loads(value)
                    except json.JSONDecodeError:
                        value = []
                
                item[field] = value
            
            logger.debug(f"Cache hit for menu item {plu}")
            return item
        
        except Exception as e:
            logger.error(f"Error getting menu item {plu} from cache: {str(e)}")
            return None
    
    def set_menu_item(self, plu: str, item: Dict[str, Any], ttl: int = DEFAULT_MENU_TTL) -> bool:
        """
        Cache a menu item in Redis.
        
        Args:
            plu: The PLU of the menu item
            item: The menu item data to cache
            ttl: The time-to-live in seconds
            
        Returns:
            True if successful, False otherwise
        """
        if not self.initialized or not self.redis_client:
            return False
        
        try:
            # Prepare data for Redis hash
            # Redis hashes can only store string values, so we need to serialize complex types
            item_data = {}
            for key, value in item.items():
                # Skip None values
                if value is None:
                    continue
                
                # Convert to string representation
                if isinstance(value, (list, dict)):
                    item_data[key] = json.dumps(value)
                elif isinstance(value, bool):
                    item_data[key] = str(value).lower()
                else:
                    item_data[key] = str(value)
            
            # Store in Redis
            key = f"menu:item:{plu}"
            self.redis_client.hmset(key, item_data)
            
            # Set expiration
            self.redis_client.expire(key, ttl)
            
            logger.debug(f"Cached menu item {plu} with TTL {ttl}s")
            return True
        
        except Exception as e:
            logger.error(f"Error caching menu item {plu}: {str(e)}")
            return False
    
    def get_category_items(self, category_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get all items in a category from the cache.
        
        Args:
            category_id: The category ID
            
        Returns:
            List of items in the category if found in cache, None otherwise
        """
        if not self.initialized or not self.redis_client:
            return None
        
        # Check for cache invalidation messages before reading
        self.check_for_updates()
        
        try:
            # Get the category from Redis
            key = f"menu:category:{category_id}"
            items_json = self.redis_client.get(key)
            
            if not items_json:
                return None
            
            # Decode and parse JSON
            if isinstance(items_json, bytes):
                items_json = items_json.decode('utf-8')
            
            items = json.loads(items_json)
            
            logger.debug(f"Cache hit for category {category_id} with {len(items)} items")
            return items
        
        except Exception as e:
            logger.error(f"Error getting category {category_id} from cache: {str(e)}")
            return None
    
    def set_category_items(
        self, 
        category_id: str, 
        items: List[Dict[str, Any]], 
        ttl: int = DEFAULT_MENU_TTL
    ) -> bool:
        """
        Cache all items in a category.
        
        Args:
            category_id: The category ID
            items: The list of items in the category
            ttl: The time-to-live in seconds
            
        Returns:
            True if successful, False otherwise
        """
        if not self.initialized or not self.redis_client:
            return False
        
        try:
            # Store category items as JSON
            key = f"menu:category:{category_id}"
            items_json = json.dumps(items)
            
            # Store in Redis
            self.redis_client.setex(key, ttl, items_json)
            
            logger.debug(f"Cached {len(items)} items for category {category_id} with TTL {ttl}s")
            return True
        
        except Exception as e:
            logger.error(f"Error caching category {category_id}: {str(e)}")
            return False
    
    def get_categories(self) -> Optional[List[Dict[str, Any]]]:
        """
        Get all menu categories from the cache.
        
        Returns:
            List of categories if found in cache, None otherwise
        """
        if not self.initialized or not self.redis_client:
            return None
        
        # Check for cache invalidation messages before reading
        self.check_for_updates()
        
        try:
            # Get categories from Redis
            key = "menu:categories"
            categories_json = self.redis_client.get(key)
            
            if not categories_json:
                return None
            
            # Decode and parse JSON
            if isinstance(categories_json, bytes):
                categories_json = categories_json.decode('utf-8')
            
            categories = json.loads(categories_json)
            
            logger.debug(f"Cache hit for menu categories, found {len(categories)} categories")
            return categories
        
        except Exception as e:
            logger.error(f"Error getting categories from cache: {str(e)}")
            return None
    
    def set_categories(self, categories: List[Dict[str, Any]], ttl: int = DEFAULT_MENU_TTL) -> bool:
        """
        Cache all menu categories.
        
        Args:
            categories: The list of menu categories
            ttl: The time-to-live in seconds
            
        Returns:
            True if successful, False otherwise
        """
        if not self.initialized or not self.redis_client:
            return False
        
        try:
            # Store categories as JSON
            key = "menu:categories"
            categories_json = json.dumps(categories)
            
            # Store in Redis
            self.redis_client.setex(key, ttl, categories_json)
            
            logger.debug(f"Cached {len(categories)} menu categories with TTL {ttl}s")
            return True
        
        except Exception as e:
            logger.error(f"Error caching categories: {str(e)}")
            return False
    
    def get_name_variants(self) -> Optional[Dict[str, str]]:
        """
        Get all menu name variants from the cache.
        
        Returns:
            Dictionary mapping variant phrases to canonical PLUs if found in cache, None otherwise
        """
        if not self.initialized or not self.redis_client:
            return None
        
        # Check for cache invalidation messages before reading
        self.check_for_updates()
        
        try:
            # Get variants from Redis
            key = "menu:variants"
            variants_json = self.redis_client.get(key)
            
            if not variants_json:
                return None
            
            # Decode and parse JSON
            if isinstance(variants_json, bytes):
                variants_json = variants_json.decode('utf-8')
            
            variants = json.loads(variants_json)
            
            logger.debug(f"Cache hit for name variants, found {len(variants)} variants")
            return variants
        
        except Exception as e:
            logger.error(f"Error getting name variants from cache: {str(e)}")
            return None
    
    def set_name_variants(self, variants: Dict[str, str], ttl: int = DEFAULT_MENU_TTL) -> bool:
        """
        Cache all menu name variants.
        
        Args:
            variants: Dictionary mapping variant phrases to canonical PLUs
            ttl: The time-to-live in seconds
            
        Returns:
            True if successful, False otherwise
        """
        if not self.initialized or not self.redis_client:
            return False
        
        try:
            # Store variants as JSON
            key = "menu:variants"
            variants_json = json.dumps(variants)
            
            # Store in Redis
            self.redis_client.setex(key, ttl, variants_json)
            
            logger.debug(f"Cached {len(variants)} name variants with TTL {ttl}s")
            return True
        
        except Exception as e:
            logger.error(f"Error caching name variants: {str(e)}")
            return False
    
    def get_all_menu(self) -> Optional[Dict[str, Any]]:
        """
        Get the entire menu from the cache.
        
        Returns:
            The entire menu if found in cache, None otherwise
        """
        if not self.initialized or not self.redis_client:
            return None
        
        # Check for cache invalidation messages before reading
        self.check_for_updates()
        
        try:
            # Get full menu from Redis
            key = "menu:all"
            menu_json = self.redis_client.get(key)
            
            if not menu_json:
                return None
            
            # Decode and parse JSON
            if isinstance(menu_json, bytes):
                menu_json = menu_json.decode('utf-8')
            
            menu = json.loads(menu_json)
            
            logger.debug("Cache hit for full menu")
            return menu
        
        except Exception as e:
            logger.error(f"Error getting full menu from cache: {str(e)}")
            return None
    
    def set_all_menu(self, menu: Dict[str, Any], ttl: int = DEFAULT_MENU_TTL) -> bool:
        """
        Cache the entire menu.
        
        Args:
            menu: The entire menu data
            ttl: The time-to-live in seconds
            
        Returns:
            True if successful, False otherwise
        """
        if not self.initialized or not self.redis_client:
            return False
        
        try:
            # Store menu as JSON
            key = "menu:all"
            menu_json = json.dumps(menu)
            
            # Store in Redis
            self.redis_client.setex(key, ttl, menu_json)
            
            logger.debug(f"Cached full menu with TTL {ttl}s")
            return True
        
        except Exception as e:
            logger.error(f"Error caching full menu: {str(e)}")
            return False
    
    def invalidate_item(self, plu: str) -> bool:
        """
        Invalidate a cached menu item.
        
        Args:
            plu: The PLU of the menu item to invalidate
            
        Returns:
            True if successful, False otherwise
        """
        if not self.initialized or not self.redis_client:
            return False
        
        try:
            # Delete the item from Redis
            key = f"menu:item:{plu}"
            self.redis_client.delete(key)
            
            # Also invalidate the full menu
            self.redis_client.delete("menu:all")
            
            logger.debug(f"Invalidated menu item {plu} from cache")
            return True
        
        except Exception as e:
            logger.error(f"Error invalidating menu item {plu}: {str(e)}")
            return False
    
    def invalidate_category(self, category_id: str) -> bool:
        """
        Invalidate a cached category and all its items.
        
        Args:
            category_id: The category ID to invalidate
            
        Returns:
            True if successful, False otherwise
        """
        if not self.initialized or not self.redis_client:
            return False
        
        try:
            # Delete the category from Redis
            key = f"menu:category:{category_id}"
            self.redis_client.delete(key)
            
            # Also invalidate the categories list and full menu
            self.redis_client.delete("menu:categories")
            self.redis_client.delete("menu:all")
            
            logger.debug(f"Invalidated category {category_id} from cache")
            return True
        
        except Exception as e:
            logger.error(f"Error invalidating category {category_id}: {str(e)}")
            return False
    
    def invalidate_all(self) -> bool:
        """
        Invalidate all menu cache data.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.initialized or not self.redis_client:
            return False
        
        try:
            # Delete all menu-related keys
            # This uses a pattern match, which is not recommended for production
            # as it can block Redis. In production, you'd maintain a set of cached keys.
            pattern = "menu:*"
            cursor = 0
            while True:
                cursor, keys = self.redis_client.scan(cursor, match=pattern, count=100)
                if keys:
                    self.redis_client.delete(*keys)
                if cursor == 0:
                    break
            
            logger.debug("Invalidated all menu cache data")
            return True
        
        except Exception as e:
            logger.error(f"Error invalidating all menu cache: {str(e)}")
            return False
    
    def publish_update(
        self, 
        update_type: str, 
        plu: Optional[str] = None, 
        category_id: Optional[str] = None
    ) -> bool:
        """
        Publish a menu update event to invalidate cache in other instances.
        
        Args:
            update_type: The type of update (item, category, all)
            plu: The PLU of the updated item (for item updates)
            category_id: The category ID (for category updates)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.initialized or not self.redis_client:
            return False
        
        try:
            # Create update message
            message = {
                "type": update_type,
                "timestamp": time.time()
            }
            
            if plu:
                message["plu"] = plu
            
            if category_id:
                message["category_id"] = category_id
            
            # Publish to the update channel
            message_json = json.dumps(message)
            self.redis_client.publish(MENU_UPDATE_CHANNEL, message_json)
            
            logger.debug(f"Published menu update: {message}")
            return True
        
        except Exception as e:
            logger.error(f"Error publishing menu update: {str(e)}")
            return False

# Cache decorator for menu functions
def with_menu_cache(ttl: int = DEFAULT_MENU_TTL):
    """
    Decorator to cache the result of a function in Redis.
    
    Args:
        ttl: The time-to-live for the cached result
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate a cache key based on function name and arguments
            func_name = func.__name__
            args_str = str(args) + str(kwargs)
            cache_key = f"menu:function:{func_name}:{hash(args_str)}"
            
            # Try to get from cache
            if menu_cache.initialized and menu_cache.redis_client:
                try:
                    cached_result = menu_cache.redis_client.get(cache_key)
                    if cached_result:
                        if isinstance(cached_result, bytes):
                            cached_result = cached_result.decode('utf-8')
                        return json.loads(cached_result)
                except Exception as e:
                    logger.error(f"Error getting cached result for {func_name}: {str(e)}")
            
            # If not in cache or cache error, call the original function
            result = func(*args, **kwargs)
            
            # Cache the result
            if menu_cache.initialized and menu_cache.redis_client and result is not None:
                try:
                    result_json = json.dumps(result)
                    menu_cache.redis_client.setex(cache_key, ttl, result_json)
                except Exception as e:
                    logger.error(f"Error caching result for {func_name}: {str(e)}")
            
            return result
        
        return wrapper
    
    return decorator

# Singleton instance for easy import
menu_cache = MenuCache()

# Helper functions to simplify agent SDK usage

def get_menu_item_by_plu(plu: str) -> Optional[Dict[str, Any]]:
    """
    Get a menu item by its PLU.
    
    Args:
        plu: The PLU of the menu item
        
    Returns:
        Menu item data if found, None otherwise
    """
    # First try to get from cache
    item = menu_cache.get_menu_item(plu)
    
    if item:
        return item
    
    # If not in cache, we would normally fetch from DB
    # For now, return None to indicate item not found
    return None

def get_menu_item_availability(plu: str) -> bool:
    """
    Check if a menu item is available.
    
    Args:
        plu: The PLU of the menu item
        
    Returns:
        True if the item is available, False otherwise
    """
    item = get_menu_item_by_plu(plu)
    
    if not item:
        return False
    
    # Check if the item is marked as available
    return item.get('available', False)