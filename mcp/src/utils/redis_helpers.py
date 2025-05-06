"""
Redis helper functions for the MCP server.

This module provides utility functions for Redis operations
used by the RedBarSushi MCP server tools.
"""

import json
import time
from typing import Any, Dict, List, Optional, Union

def get_redis_value(redis_client, key: str) -> Optional[Union[str, Dict, List]]:
    """
    Get a value from Redis, handling different types automatically.
    
    Args:
        redis_client: Redis client
        key: The key to fetch
        
    Returns:
        The value in the appropriate Python type, or None if the key doesn't exist
    """
    if redis_client is None:
        return None
        
    # Check if key exists
    if not redis_client.exists(key):
        return None
    
    # Get the key type
    key_type = redis_client.type(key).decode('utf-8')
    
    # Handle different types
    if key_type == 'string':
        value = redis_client.get(key)
        # Try to decode as JSON, fall back to string
        try:
            return json.loads(value.decode('utf-8'))
        except (ValueError, TypeError):
            return value.decode('utf-8')
    elif key_type == 'hash':
        hash_value = redis_client.hgetall(key)
        return {k.decode('utf-8'): v.decode('utf-8') for k, v in hash_value.items()}
    elif key_type == 'list':
        return [item.decode('utf-8') for item in redis_client.lrange(key, 0, -1)]
    elif key_type == 'set':
        return [item.decode('utf-8') for item in redis_client.smembers(key)]
    elif key_type == 'zset':
        return {item[0].decode('utf-8'): item[1] for item in redis_client.zrange(key, 0, -1, withscores=True)}
    else:
        return None

def get_conversation_state(redis_client, session_id: str) -> Dict[str, Any]:
    """
    Get the state of a conversation from Redis.
    
    Args:
        redis_client: Redis client
        session_id: The session ID of the conversation
        
    Returns:
        A dictionary with the conversation state
    """
    if redis_client is None:
        return {"error": "Redis client not available"}
    
    # Get the conversation key
    conversation_key = f"conversation:{session_id}"
    
    # Check if the key exists
    if not redis_client.exists(conversation_key):
        return {"error": f"No conversation found for session ID: {session_id}"}
    
    # Get the conversation state
    state = redis_client.hgetall(conversation_key)
    
    # Decode bytes to strings and parse JSON values
    result = {}
    for k, v in state.items():
        key = k.decode('utf-8')
        value = v.decode('utf-8')
        
        # Try to parse JSON values
        try:
            result[key] = json.loads(value)
        except (ValueError, TypeError):
            result[key] = value
    
    # Get the cart if it exists
    cart_key = f"cart:{session_id}"
    if redis_client.exists(cart_key):
        cart_json = redis_client.hget(cart_key, "json")
        if cart_json:
            try:
                result["cart"] = json.loads(cart_json.decode('utf-8'))
            except (ValueError, TypeError):
                result["cart"] = cart_json.decode('utf-8')
    
    return result

def get_redis_memory_stats(redis_client) -> Dict[str, Any]:
    """
    Get memory statistics from Redis.
    
    Args:
        redis_client: Redis client
        
    Returns:
        A dictionary with memory statistics
    """
    if redis_client is None:
        return {"error": "Redis client not available"}
    
    # Get info about memory
    info = redis_client.info("memory")
    
    # Get the biggest keys
    biggest_keys = []
    
    # Scan all keys
    cursor = 0
    while True:
        cursor, keys = redis_client.scan(cursor, count=100)
        
        # Process each key
        for key in keys:
            key_str = key.decode('utf-8')
            key_type = redis_client.type(key).decode('utf-8')
            key_size = 0
            
            # Get memory usage for this key
            try:
                key_size = redis_client.memory_usage(key)
            except:
                # If memory_usage is not available, estimate size
                if key_type == 'string':
                    value = redis_client.get(key)
                    key_size = len(key) + len(value) if value else 0
                elif key_type == 'hash':
                    key_size = sum(len(k) + len(v) for k, v in redis_client.hgetall(key).items())
                elif key_type == 'list':
                    key_size = sum(len(item) for item in redis_client.lrange(key, 0, -1))
                elif key_type == 'set':
                    key_size = sum(len(item) for item in redis_client.smembers(key))
            
            # Add to biggest keys list
            biggest_keys.append({
                "key": key_str,
                "type": key_type,
                "size_bytes": key_size
            })
            
            # Sort and keep only the top 10
            biggest_keys = sorted(biggest_keys, key=lambda x: x["size_bytes"], reverse=True)[:10]
        
        # Stop when we've scanned all keys
        if cursor == 0:
            break
    
    return {
        "memory_info": info,
        "biggest_keys": biggest_keys
    }