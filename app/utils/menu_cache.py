"""
Menu caching utilities to improve performance by caching menu queries and responses.
"""

import time
import logging
from typing import Dict, Any, Tuple, Optional, List, Callable
import functools

logger = logging.getLogger(__name__)

# Cache for menu questions to avoid redundant API calls
_menu_questions_cache = {}
_menu_questions_cache_duration = 300  # 5 minutes

# Cache for menu items to avoid redundant lookups
_menu_items_cache = {}
_menu_items_cache_duration = 600  # 10 minutes

# Cache for AI responses to avoid redundant API calls
_ai_response_cache = {}
_ai_response_cache_duration = 300  # 5 minutes


def get_cached_response(
    query: str, cache_type: str = "question"
) -> Optional[Tuple[Any, float]]:
    """
    Get a cached response for a query.

    Args:
        query: The query to look up
        cache_type: The type of cache to check (question, item, ai)

    Returns:
        Tuple of (cached_value, timestamp) or None if not found
    """
    cache = _get_cache_for_type(cache_type)
    duration = _get_duration_for_type(cache_type)

    cleaned_query = query.strip().lower()
    current_time = time.time()

    if cleaned_query in cache:
        cached_data, timestamp = cache[cleaned_query]
        if current_time - timestamp < duration:
            logger.info(f"Cache hit for {cache_type}: '{cleaned_query}'")
            return (cached_data, timestamp)

    logger.info(f"Cache miss for {cache_type}: '{cleaned_query}'")
    return None


def cache_response(query: str, response: Any, cache_type: str = "question") -> None:
    """
    Cache a response for a query.

    Args:
        query: The query to cache
        response: The response to cache
        cache_type: The type of cache to use (question, item, ai)
    """
    cache = _get_cache_for_type(cache_type)

    cleaned_query = query.strip().lower()
    current_time = time.time()

    # Store the response in cache
    cache[cleaned_query] = (response, current_time)

    # Limit cache size to avoid memory issues
    if len(cache) > 100:
        # Remove oldest entries
        oldest_keys = sorted(cache.items(), key=lambda x: x[1][1])[:30]
        for key, _ in oldest_keys:
            cache.pop(key, None)

    logger.info(f"Cached response for {cache_type}: '{cleaned_query}'")


def _get_cache_for_type(cache_type: str) -> Dict[str, Tuple[Any, float]]:
    """Get the appropriate cache dictionary for the given type."""
    if cache_type == "question":
        return _menu_questions_cache
    elif cache_type == "item":
        return _menu_items_cache
    elif cache_type == "ai":
        return _ai_response_cache
    else:
        return _menu_questions_cache  # Default


def _get_duration_for_type(cache_type: str) -> int:
    """Get the appropriate cache duration for the given type."""
    if cache_type == "question":
        return _menu_questions_cache_duration
    elif cache_type == "item":
        return _menu_items_cache_duration
    elif cache_type == "ai":
        return _ai_response_cache_duration
    else:
        return _menu_questions_cache_duration  # Default


def menu_cache(cache_type: str = "item"):
    """
    Decorator to cache function results for menu operations.

    Args:
        cache_type: The type of cache to use

    Returns:
        Decorated function with caching
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Try to create a cache key from the first string argument
            cache_key = None
            for arg in args:
                if isinstance(arg, str):
                    cache_key = f"{func.__name__}:{arg.lower().strip()}"
                    break

            if not cache_key:
                # No suitable cache key found
                return func(*args, **kwargs)

            # Check cache
            cached = get_cached_response(cache_key, cache_type)
            if cached:
                return cached[0]

            # Call the function
            result = func(*args, **kwargs)

            # Cache the result
            cache_response(cache_key, result, cache_type)

            return result

        return wrapper

    return decorator


def clear_caches():
    """Clear all caches."""
    _menu_questions_cache.clear()
    _menu_items_cache.clear()
    _ai_response_cache.clear()
    logger.info("All menu caches cleared")
