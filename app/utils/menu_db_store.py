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
            logger.warning("Redis package not available - using in-memory cache fallback")
            self.initialized = True
            return
            
        try:
            # Get Redis URL from environment or Flask config
            redis_url = None
            
            # Try to get from Flask config if in app context
            try:
                if current_app and current_app.config:
                    redis_url = current_app.config.get('REDIS_URL') or current_app.config.get('CELERY_BROKER_URL')
            except:
                pass
                
            # Fall back to environment variables
            if not redis_url:
                redis_url = os.environ.get('REDIS_URL') or os.environ.get('CELERY_BROKER_URL')
                
            # Default if nothing is set
            if not redis_url:
                redis_url = "redis://localhost:6379/0"
            
            # Ensure the URL has the proper redis:// prefix
            if not redis_url.startswith('redis://'):
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
        
    def _store_in_redis(self, key: str, data: Dict[str, Any], expiration: int = DEFAULT_REDIS_CACHE_DURATION) -> bool:
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
                    reverse=True
                )[:50]  # Keep only the 50 most recent
                
                # Rebuild the caches with only the items to keep
                new_cache = {}
                new_timestamps = {}
                
                for k, ts in items_to_keep:
                    if k in _memory_cache:
                        new_cache[k] = _memory_cache[k]
                        new_timestamps[k] = ts
                        
                _memory_cache = new_cache
                _memory_cache_timestamps = new_timestamps
                
                logger.info(f"Memory cache cleaned up, now storing {len(_memory_cache)} items")
                
            return True
        except Exception as e:
            logger.error(f"Error storing in memory cache: {str(e)}")
            return False
    
    def get_menu_data(self, location_id: Optional[str] = None, force_refresh: bool = False) -> Dict[str, Any]:
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
            from app import db
            
            # Query database for menu items
            query = MenuItem.query
            
            # Filter by location if specified
            if location_id:
                query = query.filter_by(location_id=location_id)
                
            # Execute query and convert to dictionaries
            items = [item.to_dict() for item in query.all()]
            
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
                "name_variants": {}  # Empty for compatibility with existing code
            }
            
            # Cache the result
            self._store_in_redis(cache_key, menu_data)
            self._store_in_memory_cache(cache_key, menu_data)
            
            logger.info(f"Loaded menu data from database: {len(items)} items, {len(modifiers)} modifiers, {len(modifier_groups)} groups")
            return menu_data
            
        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving menu data: {str(e)}")
            # Return empty menu data structure
            return {"items": [], "modifiers": [], "modifierGroups": [], "name_variants": {}}
            
        except Exception as e:
            logger.error(f"Unexpected error retrieving menu data: {str(e)}")
            # Return empty menu data structure
            return {"items": [], "modifiers": [], "modifierGroups": [], "name_variants": {}}
    
    def store_menu_data(self, menu_data: Dict[str, Any], location_id: Optional[str] = None) -> bool:
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
            from app import db
            
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
            for item_data in menu_data.get("items", []):
                # Add location_id to the data
                if location_id:
                    item_data["location_id"] = location_id
                    
                item = MenuItem.from_dict(item_data)
                db.session.add(item)
                
            # Store modifiers
            for modifier_data in menu_data.get("modifiers", []):
                # Add location_id to the data
                if location_id:
                    modifier_data["location_id"] = location_id
                    
                modifier = MenuModifier.from_dict(modifier_data)
                db.session.add(modifier)
                
            # Store modifier groups
            for group_data in menu_data.get("modifierGroups", []):
                # Add location_id to the data
                if location_id:
                    group_data["location_id"] = location_id
                    
                group = MenuModifierGroup.from_dict(group_data)
                db.session.add(group)
                
            # Commit the transaction only if we started it
            if not in_transaction:
                db.session.commit()
            
            # Invalidate cache
            cache_key = f"menu:{location_id if location_id else 'default'}"
            if self.redis_client:
                self.redis_client.delete(cache_key)
                
            # Also invalidate memory cache
            global _memory_cache, _memory_cache_timestamps
            if cache_key in _memory_cache:
                del _memory_cache[cache_key]
            if cache_key in _memory_cache_timestamps:
                del _memory_cache_timestamps[cache_key]
                
            logger.info(f"Stored menu data in database: {len(menu_data.get('items', []))} items")
            return True
            
        except SQLAlchemyError as e:
            # Rollback on error, but only if we started the transaction
            try:
                db.session.rollback()
            except:
                pass
            logger.error(f"Database error storing menu data: {str(e)}")
            return False
            
        except Exception as e:
            # Rollback on error, but only if we started the transaction
            try:
                db.session.rollback()
            except:
                pass
            logger.error(f"Unexpected error storing menu data: {str(e)}")
            return False
    
    def update_menu_item(self, item_data: Dict[str, Any], location_id: Optional[str] = None) -> bool:
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
            from app import db
            
            # Find the item by reference_handler or name
            query = MenuItem.query
            
            if "reference_handler" in item_data and item_data["reference_handler"]:
                item = query.filter_by(reference_handler=item_data["reference_handler"]).first()
            elif "plu" in item_data and item_data["plu"]:
                item = query.filter_by(plu=item_data["plu"]).first()
            elif "name" in item_data and item_data["name"]:
                item = query.filter_by(name=item_data["name"]).first()
            else:
                logger.error("Cannot update menu item: no reference_handler, plu, or name provided")
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
                            item.snooze_start = datetime.fromisoformat(value.replace("Z", "+00:00"))
                        except:
                            pass
                    elif key == "snoozeEnd" and value:
                        try:
                            item.snooze_end = datetime.fromisoformat(value.replace("Z", "+00:00"))
                        except:
                            pass
                    elif key == "snoozeUntil" and value:
                        try:
                            item.snooze_until = datetime.fromisoformat(value.replace("Z", "+00:00"))
                        except:
                            pass
                    # Map parentId to parent_id
                    elif key == "parentId":
                        item.parent_id = value
                    # Direct field mapping for common fields
                    elif key in ["name", "price", "description", "category", "available", "snoozed", 
                               "is_category", "is_variant", "reference_handler", "plu"]:
                        setattr(item, key, value)
                    # Store other properties in the JSON field
                    else:
                        # Ensure properties is initialized
                        if item.properties is None:
                            if hasattr(MenuItem, 'properties') and getattr(MenuItem, 'properties').type.python_type == dict:
                                item.properties = {}
                            else:
                                item.properties = json.dumps({})
                                
                        # Update the properties
                        if isinstance(item.properties, dict):
                            item.properties[key] = value
                        else:
                            # Load the JSON, update, and save back
                            try:
                                props = json.loads(item.properties) if item.properties else {}
                                props[key] = value
                                item.properties = json.dumps(props)
                            except:
                                # If parsing fails, initialize with just this property
                                item.properties = json.dumps({key: value})
                
                logger.info(f"Updated menu item: {item.name}")
                
            # Commit the changes
            try:
                db.session.commit()
            except Exception as e:
                # If we're in a transaction that wasn't started by us, 
                # we shouldn't commit, and this might throw an error
                logger.warning(f"Commit may have failed, but continuing: {e}")
            
            # Invalidate cache
            cache_key = f"menu:{location_id if location_id else 'default'}"
            if self.redis_client:
                self.redis_client.delete(cache_key)
                
            # Also invalidate memory cache
            global _memory_cache, _memory_cache_timestamps
            if cache_key in _memory_cache:
                del _memory_cache[cache_key]
            if cache_key in _memory_cache_timestamps:
                del _memory_cache_timestamps[cache_key]
                
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
    
    def find_menu_item(self, 
                       item_name: str, 
                       check_availability: bool = False,
                       location_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
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
                logger.info(f"Found fuzzy match for menu item: {cleaned_name} -> {item.name}")
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
    
    def load_menu_data_from_file(self, file_path: str, location_id: Optional[str] = None) -> bool:
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
            with open(file_path, 'r') as f:
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
    
    def export_menu_data_to_file(self, file_path: str, location_id: Optional[str] = None) -> bool:
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
            with open(file_path, 'w') as f:
                json.dump(menu_data, f, indent=2)
                
            logger.info(f"Exported menu data to file: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting menu data to file: {str(e)}")
            return False


# Create a singleton instance
menu_db_store = MenuDBStore()