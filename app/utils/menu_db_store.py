"""
Database and Redis-backed menu storage module.

This module provides a persistent storage solution for menu data with:
1. PostgreSQL/SQLite as the primary storage backend
2. Redis as a read-through caching layer for performance
3. In-memory fallback when Redis is unavailable
"""

import json
import logging
import time
import os
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

# Set up logging
logger = logging.getLogger(__name__)

# Import Redis
try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis package not installed, using database-only functionality")

# Default cache durations
DEFAULT_REDIS_CACHE_DURATION = 300  # 5 minutes
DEFAULT_MEMORY_CACHE_DURATION = 60  # 1 minute

# In-memory cache as fallback
_memory_cache = {}
_memory_cache_timestamps = {}


class MenuDBStore:
    """
    Database and Redis-backed menu data store.

    This class provides persistent storage for menu data using a database,
    with Redis as a caching layer for performance optimization.
    """

    def __init__(self):
        """Initialize the menu database store."""
        self.redis_client = None
        self.initialized = False
        self._initialize_redis()

    def _initialize_redis(self):
        """Initialize the Redis connection for caching."""
        if not REDIS_AVAILABLE:
            logger.warning(
                "Redis package not available - using in-memory cache fallback"
            )
            self.initialized = True
            return

        try:
            # Get Redis URL from environment or Flask config
            redis_url = None

            # Try to get from Flask config if in app context
            try:
                if current_app and current_app.config:
                    redis_url = current_app.config.get(
                        "REDIS_URL"
                    ) or current_app.config.get("CELERY_BROKER_URL")
            except:
                pass

            # Always prioritize REDIS_URL from environment variables
            redis_url = os.environ.get("REDIS_URL")
            
            if redis_url:
                logger.info(f"Using Redis URL from environment variable: {redis_url}")
            else:
                # Fall back to CELERY_BROKER_URL if REDIS_URL not set
                redis_url = os.environ.get("CELERY_BROKER_URL")
                if redis_url:
                    logger.info(f"Falling back to CELERY_BROKER_URL: {redis_url}")
                    
                # Check for Render environment
                is_render = os.environ.get("RENDER", "").lower() == "true" or os.environ.get("RENDER_SERVICE_ID")
                if is_render and not redis_url:
                    logger.warning("Running in Render environment but no Redis URL provided in environment variables!")

                # Default if nothing is set
                if not redis_url:
                    redis_url = "redis://localhost:6379/0"
                
                # For Docker environment
                if os.environ.get("DOCKER") and "localhost" in redis_url:
                    redis_url = redis_url.replace("localhost", "redis")

            # Ensure the URL has the proper redis:// prefix
            if not redis_url.startswith("redis://"):
                redis_url = f"redis://{redis_url}"

            logger.info(f"Connecting to Redis at: {redis_url}")
            self.redis_client = redis.from_url(redis_url, socket_timeout=2.0)

            # Test the connection
            self.redis_client.ping()
            logger.info("Successfully connected to Redis for menu caching")
            self.initialized = True

        except Exception as e:
            logger.error(f"Failed to initialize Redis connection: {str(e)}")
            logger.info("Using in-memory fallback for menu caching")
            self.redis_client = None
            self.initialized = True

    def _get_from_redis(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get menu data from Redis cache.

        Args:
            key: The cache key to retrieve

        Returns:
            The cached data or None if not found/expired
        """
        if not self.initialized:
            self._initialize_redis()

        if not self.redis_client:
            return None

        try:
            # Get the cached data
            data = self.redis_client.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Error retrieving from Redis cache: {str(e)}")

        return None

    def _store_in_redis(
        self,
        key: str,
        data: Dict[str, Any],
        expiration: int = DEFAULT_REDIS_CACHE_DURATION,
    ) -> bool:
        """
        Store menu data in Redis cache.

        Args:
            key: The cache key to store
            data: The data to cache
            expiration: Time in seconds until expiration

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.initialized:
            self._initialize_redis()

        if not self.redis_client:
            return False

        try:
            serialized = json.dumps(data)
            self.redis_client.setex(key, expiration, serialized)
            logger.debug(f"Stored menu data in Redis cache: {key}")
            return True
        except Exception as e:
            logger.error(f"Error storing in Redis cache: {str(e)}")
            return False

    def _get_from_memory_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get menu data from in-memory cache.

        Args:
            key: The cache key to retrieve

        Returns:
            The cached data or None if not found/expired
        """
        global _memory_cache, _memory_cache_timestamps

        if key not in _memory_cache or key not in _memory_cache_timestamps:
            return None

        timestamp = _memory_cache_timestamps.get(key, 0)
        current_time = time.time()

        # Check if the cache entry has expired
        if current_time - timestamp > DEFAULT_MEMORY_CACHE_DURATION:
            # Clean up expired entry
            if key in _memory_cache:
                del _memory_cache[key]
            if key in _memory_cache_timestamps:
                del _memory_cache_timestamps[key]
            return None

        return _memory_cache.get(key)

    def _sanitize_properties(self, data: Dict[str, Any], item_type: str = 'item') -> None:
        """
        Sanitize the properties field of menu data to ensure it's JSON-serializable.
        
        Args:
            data: The menu data dictionary to sanitize
            item_type: Type of item being sanitized ('item', 'modifier', or 'group')
            
        Returns:
            None, modifies the data dict in place
        """
        name = data.get('name', f'Unknown {item_type}')
        
        # Log the properties structure before sanitization
        logger.debug(f"[MENU-STORE] {item_type.capitalize()} properties type: {type(data.get('properties'))}")
        if 'properties' in data and data['properties'] is not None:
            logger.debug(f"[MENU-STORE] {item_type.capitalize()} properties content sample: {str(data['properties'])[:100]}")
            
            # Enhanced JSONB handling - sanitize any non-JSON-serializable values
            try:
                # Test JSON serializability by attempting to serialize
                json.dumps(data['properties'])
                logger.debug(f"[MENU-STORE] Properties for {name} is already JSON-serializable")
            except (TypeError, ValueError) as json_err:
                logger.warning(f"[MENU-STORE] Non-serializable properties for {item_type} {name}, error: {json_err}")
                
                # If properties is a string, try to parse it
                if isinstance(data['properties'], str):
                    try:
                        data['properties'] = json.loads(data['properties'])
                        logger.info(f"[MENU-STORE] Converted properties string to dict for {item_type} {name}")
                    except json.JSONDecodeError:
                        logger.warning(f"[MENU-STORE] Could not parse properties string for {item_type} {name}, setting to empty dict")
                        data['properties'] = {}
                elif isinstance(data['properties'], dict):
                    # If it's a dict but contains non-serializable values, sanitize them
                    sanitized_props = {}
                    for k, v in data['properties'].items():
                        # Handle non-serializable values
                        if isinstance(v, dict):
                            # Recursively sanitize nested dicts
                            try:
                                json.dumps(v)  # Test if serializable
                                sanitized_props[k] = v
                            except (TypeError, ValueError):
                                logger.warning(f"[MENU-STORE] Sanitizing non-serializable nested dict at key '{k}' for {item_type} {name}")
                                sanitized_props[k] = str(v)
                        elif isinstance(v, (list, tuple)):
                            # Handle lists/tuples - convert any non-serializable items to strings
                            try:
                                json.dumps(v)  # Test if serializable
                                sanitized_props[k] = v
                            except (TypeError, ValueError):
                                logger.warning(f"[MENU-STORE] Sanitizing non-serializable list/tuple at key '{k}' for {item_type} {name}")
                                # Convert non-serializable items in lists to strings
                                sanitized_props[k] = [str(item) if not isinstance(item, (str, int, float, bool, type(None))) else item for item in v]
                        elif isinstance(v, (str, int, float, bool, type(None))):
                            # These types are always JSON-serializable
                            sanitized_props[k] = v
                        else:
                            # Convert other types to strings
                            logger.warning(f"[MENU-STORE] Converting non-serializable value type {type(v)} at key '{k}' to string for {item_type} {name}")
                            sanitized_props[k] = str(v)
                            
                    # Replace with sanitized properties
                    data['properties'] = sanitized_props
                    logger.info(f"[MENU-STORE] Sanitized properties for {item_type} {name}")
                else:
                    # If not a string or dict, set to empty dict
                    logger.warning(f"[MENU-STORE] Properties not dict or string for {item_type} {name}, setting to empty dict")
                    data['properties'] = {}

    def _store_in_memory_cache(self, key: str, data: Dict[str, Any]) -> bool:
        """
        Store menu data in in-memory cache.

        Args:
            key: The cache key to store
            data: The data to cache

        Returns:
            bool: True if successful, False otherwise
        """
        global _memory_cache, _memory_cache_timestamps

        try:
            _memory_cache[key] = data
            _memory_cache_timestamps[key] = time.time()

            # Clean up the cache if it gets too large
            if len(_memory_cache) > 100:
                # Sort by timestamp and keep the 50 most recent entries
                items_to_keep = sorted(
                    _memory_cache_timestamps.items(),
                    key=lambda x: x[1],  # Sort by timestamp
                    reverse=True,
                )[
                    :50
                ]  # Keep only the 50 most recent

                # Rebuild the caches with only the items to keep
                new_cache = {}
                new_timestamps = {}

                for k, ts in items_to_keep:
                    if k in _memory_cache:
                        new_cache[k] = _memory_cache[k]
                        new_timestamps[k] = ts

                _memory_cache = new_cache
                _memory_cache_timestamps = new_timestamps

                logger.info(
                    f"Memory cache cleaned up, now storing {len(_memory_cache)} items"
                )

            return True
        except Exception as e:
            logger.error(f"Error storing in memory cache: {str(e)}")
            return False

    def _get_menu_data_from_db(
        self, location_id: Optional[str] = None, cache_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Helper method to retrieve menu data directly from the database.

        Args:
            location_id: Optional location ID to filter menu data
            cache_key: Optional cache key for storing the result

        Returns:
            dict: The complete menu data
        """
        # Import models here to avoid circular imports
        from app.models.menu import MenuItem, MenuModifier, MenuModifierGroup

        # Query database for menu items
        query = MenuItem.query

        # Filter by location if specified
        if location_id:
            query = query.filter_by(location_id=location_id)

        # Log the query being executed
        try:
            query_str = str(
                query.statement.compile(compile_kwargs={"literal_binds": True})
            )
            logger.info(f"[MENU-DB] Executing SQL query: {query_str}")
        except Exception as e:
            logger.info(f"[MENU-DB] Could not log query: {e}")

        # Execute query and convert to dictionaries
        try:
            items = [item.to_dict() for item in query.all()]
            logger.info(f"[MENU-DB] Found {len(items)} menu items in database")
        except Exception as e:
            logger.error(f"[MENU-DB] Error querying menu items: {e}")
            items = []

        # Query modifiers
        mod_query = MenuModifier.query
        if location_id:
            mod_query = mod_query.filter_by(location_id=location_id)
        modifiers = [mod.to_dict() for mod in mod_query.all()]

        # Query modifier groups
        group_query = MenuModifierGroup.query
        if location_id:
            group_query = group_query.filter_by(location_id=location_id)
        modifier_groups = [group.to_dict() for group in group_query.all()]

        # Construct the complete menu data
        menu_data = {
            "items": items,
            "modifiers": modifiers,
            "modifierGroups": modifier_groups,
        }

        # Cache the result if a cache key was provided
        if cache_key:
            self._store_in_redis(cache_key, menu_data)
            self._store_in_memory_cache(cache_key, menu_data)

        logger.info(
            f"Loaded menu data from database: {len(items)} items, {len(modifiers)} modifiers, {len(modifier_groups)} groups"
        )
        return menu_data

    def get_menu_data(
        self, location_id: Optional[str] = None, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Get the complete menu data, using a cache-first approach.

        Args:
            location_id: Optional location ID to filter menu data
            force_refresh: If True, bypass cache and load directly from database

        Returns:
            dict: The complete menu data
        """
        # Generate the cache key
        cache_key = f"menu:{location_id if location_id else 'default'}"

        # Check if we should bypass the cache
        if not force_refresh:
            # First try Redis cache
            redis_data = self._get_from_redis(cache_key)
            if redis_data:
                logger.info(f"Retrieved menu data from Redis cache: {cache_key}")
                return redis_data

            # Then try memory cache
            memory_data = self._get_from_memory_cache(cache_key)
            if memory_data:
                logger.info(f"Retrieved menu data from memory cache: {cache_key}")
                return memory_data

        # No cached data or force refresh, load from database
        try:
            # Import models here to avoid circular imports
            from app.models.menu import MenuItem, MenuModifier, MenuModifierGroup
            from app.legacy_db import db, get_session, get_engine, session_scope
            from flask import current_app, has_app_context

            # Check if we're in an application context
            if not has_app_context():
                logger.warning(
                    "Working outside of application context, checking file backup"
                )
                # Instead of creating an app context, try to load from the file backup
                try:
                    # Look for a backup file first
                    menu_file_path = os.path.join(os.getcwd(), "menu_data.json")
                    if os.path.exists(menu_file_path):
                        logger.info(f"Loading menu from backup file: {menu_file_path}")
                        with open(menu_file_path, "r") as f:
                            menu_data = json.load(f)
                        if (
                            menu_data
                            and "items" in menu_data
                            and len(menu_data["items"]) > 0
                        ):
                            logger.info(
                                f"Loaded {len(menu_data['items'])} items from backup file"
                            )
                            # Cache the result
                            if cache_key:
                                self._store_in_redis(cache_key, menu_data)
                                self._store_in_memory_cache(cache_key, menu_data)
                            return menu_data
                except Exception as e:
                    logger.error(f"Failed to load menu from backup file: {e}")

                # If we get here, there's no file or an error occurred
                logger.warning("No menu data available outside application context")
                return {"items": [], "modifiers": [], "modifierGroups": []}

            # Get the menu data from the database using our helper method
            return self._get_menu_data_from_db(location_id, cache_key)

        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving menu data: {str(e)}")
            # Return empty menu data structure
            return {"items": [], "modifiers": [], "modifierGroups": []}

        except Exception as e:
            logger.error(f"Unexpected error retrieving menu data: {str(e)}")
            # Return empty menu data structure
            return {"items": [], "modifiers": [], "modifierGroups": []}

    def store_menu_data(
        self, menu_data: Dict[str, Any], location_id: Optional[str] = None
    ) -> bool:
        """
        Store complete menu data in the database.

        Args:
            menu_data: The complete menu data to store
            location_id: Optional location ID for the menu data

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Import models here to avoid circular imports
            from app.models.menu import MenuItem, MenuModifier, MenuModifierGroup
            from app.legacy_db import db, get_session, get_engine, session_scope
            from flask import current_app, has_app_context

            # Check if we're in an application context
            if not has_app_context():
                logger.warning(
                    "Working outside of application context, attempting to write to backup file"
                )
                # Since we can't access the database, at least save to a file
                try:
                    menu_file_path = os.path.join(os.getcwd(), "menu_data.json")
                    with open(menu_file_path, "w") as f:
                        json.dump(menu_data, f, indent=2)
                    logger.info(f"Saved menu data to backup file: {menu_file_path}")

                    # Also update memory cache so it's available for this session
                    cache_key = f"menu:{location_id if location_id else 'default'}"
                    self._store_in_memory_cache(cache_key, menu_data)

                    # Try Redis if available
                    if self.redis_client:
                        self._store_in_redis(cache_key, menu_data)

                    logger.info("Menu data saved to backup file and caches")
                    return True
                except Exception as e:
                    logger.error(f"Failed to write menu data to backup file: {e}")
                    return False

            # Try to begin a transaction - this will raise an exception if one is already in progress
            try:
                db.session.begin()
                in_transaction = False  # We started the transaction
            except Exception as tx_error:
                logger.debug(f"Transaction already in progress: {tx_error}")
                in_transaction = True  # Transaction was already started elsewhere

            # If location_id is provided, delete existing menu data for this location
            if location_id:
                MenuItem.query.filter_by(location_id=location_id).delete()
                MenuModifier.query.filter_by(location_id=location_id).delete()
                MenuModifierGroup.query.filter_by(location_id=location_id).delete()
            else:
                # If no location specified, only delete items without a location_id
                MenuItem.query.filter_by(location_id=None).delete()
                MenuModifier.query.filter_by(location_id=None).delete()
                MenuModifierGroup.query.filter_by(location_id=None).delete()

            # Store items
            successfully_added_items = 0
            for item_data in menu_data.get("items", []):
                try:
                    # Add location_id to the data
                    if location_id:
                        item_data["location_id"] = location_id

                    # Log the item data for debugging (only the main fields)
                    logger.info(
                        f"[MENU-STORE] Processing item: {item_data.get('name')}, PLU: {item_data.get('plu')}, Price: {item_data.get('price')}"
                    )

                    # Process properties field
                    self._sanitize_properties(item_data, 'item')
                    
                    item = MenuItem.from_dict(item_data)
                    session = get_session()
                    if session:
                        session.add(item)
                        successfully_added_items += 1
                    else:
                        logger.error(f"[MENU-STORE] No database session available for item {item_data.get('name')}")
                        raise RuntimeError("No database session available")
                except Exception as item_error:
                    logger.error(
                        f"[MENU-STORE] Error adding item {item_data.get('name', 'Unknown')}: {str(item_error)}"
                    )
                    # Print stack trace for better debugging
                    import traceback
                    logger.error(f"[MENU-STORE] Stack trace: {traceback.format_exc()}")
                    continue  # Skip this item but continue processing others

            logger.info(
                f"[MENU-STORE] Successfully added {successfully_added_items} items to the session"
            )

            # Store modifiers
            for modifier_data in menu_data.get("modifiers", []):
                # Add location_id to the data
                if location_id:
                    modifier_data["location_id"] = location_id
                
                # Process properties field
                self._sanitize_properties(modifier_data, 'modifier')

                try:
                    modifier = MenuModifier.from_dict(modifier_data)
                    session = get_session()
                    if session:
                        session.add(modifier)
                    else:
                        logger.error(f"[MENU-STORE] No database session available for modifier {modifier_data.get('name')}")
                        continue
                except Exception as modifier_error:
                    logger.error(f"[MENU-STORE] Error adding modifier {modifier_data.get('name', 'Unknown')}: {str(modifier_error)}")
                    import traceback
                    logger.error(f"[MENU-STORE] Stack trace: {traceback.format_exc()}")
                    continue  # Skip this modifier but continue processing others

            # Store modifier groups
            for group_data in menu_data.get("modifierGroups", []):
                # Add location_id to the data
                if location_id:
                    group_data["location_id"] = location_id
                
                # Process properties field
                self._sanitize_properties(group_data, 'group')

                try:
                    group = MenuModifierGroup.from_dict(group_data)
                    session = get_session()
                    if session:
                        session.add(group)
                    else:
                        logger.error(f"[MENU-STORE] No database session available for group {group_data.get('name')}")
                        continue
                except Exception as group_error:
                    logger.error(f"[MENU-STORE] Error adding group {group_data.get('name', 'Unknown')}: {str(group_error)}")
                    import traceback
                    logger.error(f"[MENU-STORE] Stack trace: {traceback.format_exc()}")
                    continue  # Skip this group but continue processing others

            # Check if tables exist before committing
            try:
                from sqlalchemy import inspect
                
                # Check if engine is available
                engine = get_engine()
                if engine:
                    inspector = inspect(engine)
                    tables = inspector.get_table_names()
                    required_tables = [
                        "menu_items",
                        "menu_modifiers",
                        "menu_modifier_groups",
                    ]
                    missing_tables = [
                        table for table in required_tables if table not in tables
                    ]

                    if missing_tables:
                        logger.error(
                            f"[MENU-STORE] Missing required tables: {missing_tables}. Tables found: {tables}"
                        )
                        # If tables are missing, we'll try to create them
                        from app.db_init import create_tables

                        logger.info("[MENU-STORE] Attempting to create missing tables")
                        create_tables()
                    else:
                        logger.info(
                            f"[MENU-STORE] All required tables exist: {required_tables}"
                        )
                else:
                    logger.warning("[MENU-STORE] No database engine available, skipping table check")
            except Exception as inspect_error:
                logger.error(
                    f"[MENU-STORE] Error checking table existence: {inspect_error}"
                )

            # Always commit the transaction regardless of who started it
            try:
                logger.info("[MENU-STORE] Force committing transaction to database")
                session = get_session()
                if session:
                    session.commit()
                    logger.info("[MENU-STORE] Transaction committed successfully")
                else:
                    logger.error("[MENU-STORE] No database session available for commit")
            except Exception as commit_error:
                logger.error(
                    f"[MENU-STORE] Error committing transaction: {commit_error}"
                )
                # Only rollback if we started the transaction
                if not in_transaction:
                    try:
                        session = get_session()
                        if session:
                            session.rollback()
                            logger.info("[MENU-STORE] Transaction rolled back")
                        else:
                            logger.error("[MENU-STORE] No database session available for rollback")
                    except Exception as rollback_error:
                        logger.error(
                            f"[MENU-STORE] Error during rollback: {rollback_error}"
                        )
                raise commit_error

            # Thoroughly invalidate all related caches
            logger.info("[MENU-STORE] Invalidating all menu caches")

            # Clear Redis cache for both specific location and default
            specific_key = f"menu:{location_id if location_id else 'default'}"
            default_key = "menu:default"

            if self.redis_client:
                try:
                    # Delete the specific location key
                    self.redis_client.delete(specific_key)
                    logger.info(f"[MENU-STORE] Deleted Redis cache key: {specific_key}")

                    # Delete default key if different
                    if specific_key != default_key:
                        self.redis_client.delete(default_key)
                        logger.info(
                            f"[MENU-STORE] Deleted Redis cache key: {default_key}"
                        )

                    # Clear specific menu cache keys related to current operation
                    # Instead of using pattern matching which can be expensive on large Redis instances,
                    # focus on deleting the most important known keys

                    # Clear primary cache keys first (specific location and default)
                    cache_keys_to_delete = [
                        specific_key,  # Current location key
                        default_key,  # Default location key
                        f"menu_item:*:{location_id if location_id else 'default'}",  # Item patterns for this location
                    ]

                    # Delete known keys for this specific location
                    for key in cache_keys_to_delete:
                        try:
                            if "*" not in key:  # Only direct keys, not patterns
                                self.redis_client.delete(key)
                                logger.info(
                                    f"[MENU-STORE] Deleted Redis cache key: {key}"
                                )
                        except Exception as e:
                            logger.error(
                                f"[MENU-STORE] Error deleting Redis key {key}: {e}"
                            )

                    # For exact keys related to common menu operations, delete directly
                    for operation in ["menu_item", "menu_category", "menu_modifier"]:
                        try:
                            # Delete with this location ID
                            if location_id:
                                cache_key = f"{operation}:{location_id}"
                                self.redis_client.delete(cache_key)
                            # Also delete default version
                            cache_key = f"{operation}:default"
                            self.redis_client.delete(cache_key)
                        except Exception as e:
                            logger.error(
                                f"[MENU-STORE] Error deleting operation key {operation}: {e}"
                            )

                    # If running in a small Redis instance (dev/test),
                    # we can use scan instead of keys for pattern matching
                    try:
                        # Only use this in dev/test environments or with small Redis instances
                        # Check Redis info to determine instance size
                        info = self.redis_client.info()
                        total_keys = (
                            info.get("db0", {}).get("keys", 0)
                            if isinstance(info.get("db0"), dict)
                            else 0
                        )

                        # Only do pattern scanning if Redis has a reasonable number of keys
                        if total_keys < 10000:  # Only scan if Redis is small
                            logger.info(
                                f"[MENU-STORE] Redis instance has {total_keys} keys, safe to use scan"
                            )

                            # Scan for menu item pattern keys
                            menu_item_keys = []
                            cursor = "0"
                            pattern = "menu_item:*"

                            # Use scan instead of keys, to avoid blocking Redis
                            while cursor != 0:
                                cursor, keys = self.redis_client.scan(
                                    cursor=cursor, match=pattern, count=100
                                )
                                if keys:
                                    menu_item_keys.extend(keys)

                            # Delete found keys in batches to avoid huge commands
                            if menu_item_keys:
                                # Delete in smaller batches of 100 keys
                                for i in range(0, len(menu_item_keys), 100):
                                    batch = menu_item_keys[i : i + 100]
                                    if batch:
                                        self.redis_client.delete(*batch)
                                logger.info(
                                    f"[MENU-STORE] Deleted {len(menu_item_keys)} menu item Redis cache keys using scan"
                                )

                            # Repeat for menu: pattern (again with scan for safety)
                            menu_keys = []
                            cursor = "0"
                            pattern = "menu:*"

                            while cursor != 0:
                                cursor, keys = self.redis_client.scan(
                                    cursor=cursor, match=pattern, count=100
                                )
                                if keys:
                                    menu_keys.extend(keys)

                            # Delete found menu: keys in batches
                            if menu_keys:
                                for i in range(0, len(menu_keys), 100):
                                    batch = menu_keys[i : i + 100]
                                    if batch:
                                        self.redis_client.delete(*batch)
                                logger.info(
                                    f"[MENU-STORE] Deleted {len(menu_keys)} menu Redis cache keys using scan"
                                )
                        else:
                            logger.info(
                                f"[MENU-STORE] Large Redis instance detected with {total_keys} keys, skipping pattern scan"
                            )
                    except Exception as scan_error:
                        logger.error(
                            f"[MENU-STORE] Error during Redis scan operation: {scan_error}"
                        )
                        # Fall back to the specific key deletion we already did
                except Exception as e:
                    logger.error(f"[MENU-STORE] Error clearing Redis cache: {e}")

            # Clear in-memory cache
            global _memory_cache, _memory_cache_timestamps
            keys_to_remove = []

            # Find all menu-related keys
            for key in list(_memory_cache.keys()):
                if key.startswith("menu:") or key.startswith("menu_item:"):
                    keys_to_remove.append(key)

            # Remove all identified keys
            for key in keys_to_remove:
                if key in _memory_cache:
                    del _memory_cache[key]
                if key in _memory_cache_timestamps:
                    del _memory_cache_timestamps[key]

            logger.info(
                f"[MENU-STORE] Cleared {len(keys_to_remove)} menu-related in-memory cache entries"
            )

            logger.info(
                f"Stored menu data in database: {len(menu_data.get('items', []))} items"
            )
            return True

        except SQLAlchemyError as e:
            # Rollback on error, but only if we started the transaction
            try:
                if "in_transaction" in locals() and not in_transaction:
                    db.session.rollback()
            except:
                pass
            logger.error(f"Database error storing menu data: {str(e)}")
            return False

        except Exception as e:
            # Rollback on error, but only if we started the transaction
            try:
                if "in_transaction" in locals() and not in_transaction:
                    db.session.rollback()
            except:
                pass
            logger.error(f"Unexpected error storing menu data: {str(e)}")
            import traceback
            logger.error(f"Stack trace: {traceback.format_exc()}")
            
            # If this is a JSONB related error, give more specific information
            if "JSONB" in str(e) or "json" in str(e).lower() or "column" in str(e).lower() or "properties" in str(e).lower():
                logger.error(f"JSONB serialization error detected. This is likely due to non-serializable data in properties.")
                
                # Try to identify and fix the issue
                try:
                    # Import sanitize function from models
                    from app.models.menu import sanitize_properties
                    
                    # Log detailed error info
                    logger.error(f"JSONB Error details: {e}")
                    logger.error(f"Error class: {e.__class__.__name__}")
                    
                    # Enhanced sanitization approach
                    fixed_count = 0
                    
                    # Check and sanitize items
                    for i, item in enumerate(menu_data.get("items", [])):
                        if "properties" in item:
                            old_prop = item["properties"]
                            try:
                                # Use our enhanced sanitize function
                                item["properties"] = sanitize_properties(item["properties"])
                                if item["properties"] != old_prop:
                                    fixed_count += 1
                                    logger.info(f"Fixed properties for item: {item.get('name', 'unknown')}")
                            except Exception as item_err:
                                logger.error(f"Failed to sanitize item {item.get('name', 'unknown')}: {item_err}")
                                # Last resort - empty dict
                                item["properties"] = {}
                                fixed_count += 1
                    
                    # Check and sanitize modifiers
                    for i, modifier in enumerate(menu_data.get("modifiers", [])):
                        if "properties" in modifier:
                            old_prop = modifier["properties"]
                            try:
                                modifier["properties"] = sanitize_properties(modifier["properties"])
                                if modifier["properties"] != old_prop:
                                    fixed_count += 1
                                    logger.info(f"Fixed properties for modifier: {modifier.get('name', 'unknown')}")
                            except Exception as mod_err:
                                logger.error(f"Failed to sanitize modifier {modifier.get('name', 'unknown')}: {mod_err}")
                                modifier["properties"] = {}
                                fixed_count += 1
                    
                    # Check and sanitize modifier groups
                    for i, group in enumerate(menu_data.get("modifierGroups", [])):
                        if "properties" in group:
                            old_prop = group["properties"]
                            try:
                                group["properties"] = sanitize_properties(group["properties"])
                                if group["properties"] != old_prop:
                                    fixed_count += 1
                                    logger.info(f"Fixed properties for group: {group.get('name', 'unknown')}")
                            except Exception as group_err:
                                logger.error(f"Failed to sanitize group {group.get('name', 'unknown')}: {group_err}")
                                group["properties"] = {}
                                fixed_count += 1
                    
                    # Handle column name issues (snoozed_until vs snoozeUntil vs snoozedUntil)
                    for i, item in enumerate(menu_data.get("items", [])):
                        # Process different field names for snoozed_until to ensure compatibility
                        # Priority: snoozedUntil (DB column name) > snoozeUntil (camelCase API name)
                        
                        # If only snoozeUntil exists, add snoozedUntil for DB compatibility
                        if "snoozeUntil" in item and "snoozedUntil" not in item:
                            item["snoozedUntil"] = item["snoozeUntil"]
                            logger.info(f"Added snoozedUntil for DB compatibility with item: {item.get('name', 'unknown')}")
                            fixed_count += 1
                            
                        # If only snoozedUntil exists, add snoozeUntil for API compatibility
                        elif "snoozedUntil" in item and "snoozeUntil" not in item:
                            item["snoozeUntil"] = item["snoozedUntil"]
                            logger.info(f"Added snoozeUntil for API compatibility with item: {item.get('name', 'unknown')}")
                            fixed_count += 1
                            
                        # Log detailed debug info for snooze fields
                        logger.debug(f"Item {item.get('name', 'unknown')} snooze fields: " +
                                   f"snoozedUntil={item.get('snoozedUntil')}, " +
                                   f"snoozeUntil={item.get('snoozeUntil')}")
                    
                    logger.info(f"Fixed {fixed_count} properties fields")
                    
                    if fixed_count > 0:
                        # Try to store again with sanitized data
                        logger.info("Attempting to store menu data again with sanitized properties")
                        return self.store_menu_data(menu_data, location_id)
                    else:
                        logger.warning("No properties were fixed, the issue might be something else")
                
                except Exception as debug_err:
                    logger.error(f"Error while debugging JSONB issue: {debug_err}")
                    logger.exception("Exception details:")
                    
                # Provide more helpful information in logs
                try:
                    # Get database schema information for debugging
                    from sqlalchemy import inspect
                    engine = get_engine()
                    if engine:
                        inspector = inspect(engine)
                        column_info = inspector.get_columns('menu_items')
                        schema_columns = [col['name'] for col in column_info]
                        logger.info(f"Database schema for menu_items table: {schema_columns}")
                        
                        # Check for specific column presence
                        if 'properties' in schema_columns:
                            column_type = next((col['type'] for col in column_info if col['name'] == 'properties'), None)
                            logger.info(f"Properties column type: {column_type}")
                        
                        if 'snoozed_until' in schema_columns:
                            logger.info("Column 'snoozed_until' exists in database schema")
                        else:
                            logger.warning("Column 'snoozed_until' NOT FOUND in database schema - this will cause errors")
                except Exception as schema_err:
                    logger.error(f"Could not get schema information: {schema_err}")
            
            return False

    def update_menu_item(
        self, item_data: Dict[str, Any], location_id: Optional[str] = None
    ) -> bool:
        """
        Update a single menu item in the database.

        Args:
            item_data: The item data to update
            location_id: Optional location ID for the menu item

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Import models here to avoid circular imports
            from app.models.menu import MenuItem
            from app.legacy_db import db, get_session, get_engine, session_scope
            from flask import current_app, has_app_context

            # Check if we're in an application context
            if not has_app_context():
                logger.warning(
                    "Working outside of application context, cannot update menu item in database"
                )
                return False

            # Find the item by reference_handler or name
            query = MenuItem.query

            if "reference_handler" in item_data and item_data["reference_handler"]:
                item = query.filter_by(
                    reference_handler=item_data["reference_handler"]
                ).first()
            elif "plu" in item_data and item_data["plu"]:
                item = query.filter_by(plu=item_data["plu"]).first()
            elif "name" in item_data and item_data["name"]:
                item = query.filter_by(name=item_data["name"]).first()
            else:
                logger.error(
                    "Cannot update menu item: no reference_handler, plu, or name provided"
                )
                return False

            # If not found, create a new item
            if not item:
                # Add location_id to the data
                if location_id:
                    item_data["location_id"] = location_id

                item = MenuItem.from_dict(item_data)
                db.session.add(item)
                logger.info(f"Created new menu item: {item_data.get('name')}")
            else:
                # Update the existing item
                for key, value in item_data.items():
                    # Special handling for date fields
                    if key == "snoozeStart" and value:
                        try:
                            item.snooze_start = datetime.fromisoformat(
                                value.replace("Z", "+00:00")
                            )
                        except:
                            pass
                    elif key == "snoozeEnd" and value:
                        try:
                            item.snooze_end = datetime.fromisoformat(
                                value.replace("Z", "+00:00")
                            )
                        except:
                            pass
                    elif key == "snoozeUntil" and value:
                        try:
                            item.snooze_until = datetime.fromisoformat(
                                value.replace("Z", "+00:00")
                            )
                        except:
                            pass
                    # Map parentId to parent_id
                    elif key == "parentId":
                        item.parent_id = value
                    # Direct field mapping for common fields
                    elif key in [
                        "name",
                        "price",
                        "description",
                        "category",
                        "available",
                        "snoozed",
                        "is_category",
                        "is_variant",
                        "reference_handler",
                        "plu",
                    ]:
                        setattr(item, key, value)
                    # Store other properties in the JSON field
                    else:
                        # Ensure properties is initialized
                        if item.properties is None:
                            try:
                                if (
                                    hasattr(MenuItem, "properties")
                                    and hasattr(
                                        getattr(MenuItem, "properties").type,
                                        "python_type",
                                    )
                                    and getattr(MenuItem, "properties").type.python_type
                                    == dict
                                ):
                                    item.properties = {}
                                else:
                                    item.properties = json.dumps({})
                            except (AttributeError, TypeError):
                                # If any attribute checks fail, just use JSON as fallback
                                item.properties = json.dumps({})

                        # Update the properties
                        try:
                            if isinstance(item.properties, dict):
                                item.properties[key] = value
                            else:
                                # Load the JSON, update, and save back
                                try:
                                    props = (
                                        json.loads(item.properties)
                                        if item.properties
                                        else {}
                                    )
                                    props[key] = value
                                    item.properties = json.dumps(props)
                                except:
                                    # If parsing fails, initialize with just this property
                                    item.properties = json.dumps({key: value})
                        except (AttributeError, TypeError):
                            # If attribute error, create new JSON object
                            item.properties = json.dumps({key: value})

                logger.info(f"Updated menu item: {item.name}")

            # Commit the changes
            try:
                db.session.commit()
            except Exception as e:
                # If we're in a transaction that wasn't started by us,
                # we shouldn't commit, and this might throw an error
                logger.warning(f"Commit may have failed, but continuing: {e}")

            # Thoroughly invalidate all related caches
            logger.info("[MENU-STORE] Invalidating all menu caches")

            # Clear Redis cache for both specific location and default
            specific_key = f"menu:{location_id if location_id else 'default'}"
            default_key = "menu:default"

            if self.redis_client:
                try:
                    # Delete the specific location key
                    self.redis_client.delete(specific_key)
                    logger.info(f"[MENU-STORE] Deleted Redis cache key: {specific_key}")

                    # Delete default key if different
                    if specific_key != default_key:
                        self.redis_client.delete(default_key)
                        logger.info(
                            f"[MENU-STORE] Deleted Redis cache key: {default_key}"
                        )

                    # Clear specific menu cache keys related to current operation
                    # Instead of using pattern matching which can be expensive on large Redis instances,
                    # focus on deleting the most important known keys

                    # Clear primary cache keys first (specific location and default)
                    cache_keys_to_delete = [
                        specific_key,  # Current location key
                        default_key,  # Default location key
                        f"menu_item:*:{location_id if location_id else 'default'}",  # Item patterns for this location
                    ]

                    # Delete known keys for this specific location
                    for key in cache_keys_to_delete:
                        try:
                            if "*" not in key:  # Only direct keys, not patterns
                                self.redis_client.delete(key)
                                logger.info(
                                    f"[MENU-STORE] Deleted Redis cache key: {key}"
                                )
                        except Exception as e:
                            logger.error(
                                f"[MENU-STORE] Error deleting Redis key {key}: {e}"
                            )

                    # For exact keys related to common menu operations, delete directly
                    for operation in ["menu_item", "menu_category", "menu_modifier"]:
                        try:
                            # Delete with this location ID
                            if location_id:
                                cache_key = f"{operation}:{location_id}"
                                self.redis_client.delete(cache_key)
                            # Also delete default version
                            cache_key = f"{operation}:default"
                            self.redis_client.delete(cache_key)
                        except Exception as e:
                            logger.error(
                                f"[MENU-STORE] Error deleting operation key {operation}: {e}"
                            )

                    # If running in a small Redis instance (dev/test),
                    # we can use scan instead of keys for pattern matching
                    try:
                        # Only use this in dev/test environments or with small Redis instances
                        # Check Redis info to determine instance size
                        info = self.redis_client.info()
                        total_keys = (
                            info.get("db0", {}).get("keys", 0)
                            if isinstance(info.get("db0"), dict)
                            else 0
                        )

                        # Only do pattern scanning if Redis has a reasonable number of keys
                        if total_keys < 10000:  # Only scan if Redis is small
                            logger.info(
                                f"[MENU-STORE] Redis instance has {total_keys} keys, safe to use scan"
                            )

                            # Scan for menu item pattern keys
                            menu_item_keys = []
                            cursor = "0"
                            pattern = "menu_item:*"

                            # Use scan instead of keys, to avoid blocking Redis
                            while cursor != 0:
                                cursor, keys = self.redis_client.scan(
                                    cursor=cursor, match=pattern, count=100
                                )
                                if keys:
                                    menu_item_keys.extend(keys)

                            # Delete found keys in batches to avoid huge commands
                            if menu_item_keys:
                                # Delete in smaller batches of 100 keys
                                for i in range(0, len(menu_item_keys), 100):
                                    batch = menu_item_keys[i : i + 100]
                                    if batch:
                                        self.redis_client.delete(*batch)
                                logger.info(
                                    f"[MENU-STORE] Deleted {len(menu_item_keys)} menu item Redis cache keys using scan"
                                )

                            # Repeat for menu: pattern (again with scan for safety)
                            menu_keys = []
                            cursor = "0"
                            pattern = "menu:*"

                            while cursor != 0:
                                cursor, keys = self.redis_client.scan(
                                    cursor=cursor, match=pattern, count=100
                                )
                                if keys:
                                    menu_keys.extend(keys)

                            # Delete found menu: keys in batches
                            if menu_keys:
                                for i in range(0, len(menu_keys), 100):
                                    batch = menu_keys[i : i + 100]
                                    if batch:
                                        self.redis_client.delete(*batch)
                                logger.info(
                                    f"[MENU-STORE] Deleted {len(menu_keys)} menu Redis cache keys using scan"
                                )
                        else:
                            logger.info(
                                f"[MENU-STORE] Large Redis instance detected with {total_keys} keys, skipping pattern scan"
                            )
                    except Exception as scan_error:
                        logger.error(
                            f"[MENU-STORE] Error during Redis scan operation: {scan_error}"
                        )
                        # Fall back to the specific key deletion we already did
                except Exception as e:
                    logger.error(f"[MENU-STORE] Error clearing Redis cache: {e}")

            # Clear in-memory cache
            global _memory_cache, _memory_cache_timestamps
            keys_to_remove = []

            # Find all menu-related keys
            for key in list(_memory_cache.keys()):
                if key.startswith("menu:") or key.startswith("menu_item:"):
                    keys_to_remove.append(key)

            # Remove all identified keys
            for key in keys_to_remove:
                if key in _memory_cache:
                    del _memory_cache[key]
                if key in _memory_cache_timestamps:
                    del _memory_cache_timestamps[key]

            logger.info(
                f"[MENU-STORE] Cleared {len(keys_to_remove)} menu-related in-memory cache entries"
            )

            return True

        except SQLAlchemyError as e:
            # Rollback on error, but only if we started the transaction
            try:
                db.session.rollback()
            except:
                pass
            logger.error(f"Database error updating menu item: {str(e)}")
            return False

        except Exception as e:
            # Rollback on error, but only if we started the transaction
            try:
                db.session.rollback()
            except:
                pass
            logger.error(f"Unexpected error updating menu item: {str(e)}")
            return False

    def find_menu_item(
        self,
        item_name: str,
        check_availability: bool = False,
        location_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Find a menu item by name, using exact and fuzzy matching.

        Args:
            item_name: The name of the item to find
            check_availability: If True, only return available items
            location_id: Optional location ID to filter items

        Returns:
            dict or None: The menu item if found, None otherwise
        """
        if not item_name:
            return None

        # Clean up the name for comparison
        cleaned_name = item_name.lower().strip()

        # Try Redis cache first
        cache_key = f"menu_item:{cleaned_name}:{1 if check_availability else 0}:{location_id if location_id else 'default'}"

        # Check Redis cache
        cached_item = self._get_from_redis(cache_key)
        if cached_item:
            logger.info(f"Found menu item in Redis cache: {cleaned_name}")
            return cached_item

        # Check memory cache
        memory_item = self._get_from_memory_cache(cache_key)
        if memory_item:
            logger.info(f"Found menu item in memory cache: {cleaned_name}")
            return memory_item

        try:
            # Import models here to avoid circular imports
            from app.models.menu import MenuItem

            # Start building the query
            query = MenuItem.query

            # Filter by availability if requested
            if check_availability:
                query = query.filter_by(available=True, snoozed=False)

            # Filter by location if specified
            if location_id:
                query = query.filter_by(location_id=location_id)

            # Exclude category items
            query = query.filter_by(is_category=False)

            # Try exact match first (case-insensitive)
            item = query.filter(MenuItem.name.ilike(cleaned_name)).first()

            if item:
                result = item.to_dict()
                # Cache the result
                self._store_in_redis(cache_key, result)
                self._store_in_memory_cache(cache_key, result)
                logger.info(f"Found exact match for menu item: {cleaned_name}")
                return result

            # If exact match fails, try fuzzy matching
            # This is a simple implementation - in a real system, you might use
            # database-specific features like trigram matching

            # First try LIKE search for containing the term
            item = query.filter(MenuItem.name.ilike(f"%{cleaned_name}%")).first()

            if item:
                result = item.to_dict()
                # Cache the result
                self._store_in_redis(cache_key, result)
                self._store_in_memory_cache(cache_key, result)
                logger.info(
                    f"Found fuzzy match for menu item: {cleaned_name} -> {item.name}"
                )
                return result

            # If still no match, try advanced AI matching via menu_matcher
            # (this is done by menu_matcher itself)

            # No match found
            logger.info(f"No match found for menu item: {cleaned_name}")
            return None

        except SQLAlchemyError as e:
            logger.error(f"Database error finding menu item: {str(e)}")
            return None

        except Exception as e:
            logger.error(f"Unexpected error finding menu item: {str(e)}")
            return None

    def load_menu_data_from_file(
        self, file_path: str, location_id: Optional[str] = None
    ) -> bool:
        """
        Load menu data from a JSON file and store it in the database.

        Args:
            file_path: Path to the JSON file
            location_id: Optional location ID for the menu data

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Read the JSON file
            with open(file_path, "r") as f:
                menu_data = json.load(f)

            # Store the menu data in the database
            return self.store_menu_data(menu_data, location_id)

        except FileNotFoundError:
            logger.error(f"Menu file not found: {file_path}")
            return False

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in menu file: {file_path}")
            return False

        except Exception as e:
            logger.error(f"Error loading menu data from file: {str(e)}")
            return False

    def export_menu_data_to_file(
        self, file_path: str, location_id: Optional[str] = None
    ) -> bool:
        """
        Export menu data from the database to a JSON file.

        Args:
            file_path: Path to the output JSON file
            location_id: Optional location ID to filter menu data

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get the menu data
            menu_data = self.get_menu_data(location_id=location_id, force_refresh=True)

            # Write to the file
            with open(file_path, "w") as f:
                json.dump(menu_data, f, indent=2)

            logger.info(f"Exported menu data to file: {file_path}")
            return True

        except Exception as e:
            logger.error(f"Error exporting menu data to file: {str(e)}")
            return False


# Create a singleton instance
menu_db_store = MenuDBStore()
