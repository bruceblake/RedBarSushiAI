"""
Redis-based conversation store for maintaining context in interactive conversations.
Stores conversation history and state between API calls for menu questions and order resolution.
"""

import json
import logging
import time
import os
from typing import Dict, List, Any, Optional

# Configure logger
logger = logging.getLogger(__name__)

# Default expiration time for conversations (30 minutes)
DEFAULT_EXPIRATION = 1800  

class ConversationStore:
    """Manages conversation state and history using Redis as a backend store."""
    
    def __init__(self):
        """Initialize the conversation store with Redis connection."""
        self.redis_client = None
        self.initialized = False
        self._initialize_redis()
        
    def _initialize_redis(self):
        """Initialize the Redis connection."""
        try:
            import redis
            
            # Get Redis URL from environment or use default
            redis_url = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
            
            # Fix malformed Redis URLs that might be coming from Render
            if ':' in redis_url and not redis_url.startswith('redis://'):
                if redis_url.count(':') == 1 and '/' in redis_url:
                    # Format appears to be hostname:port/db
                    host_port, db = redis_url.rsplit('/', 1)
                    host, port = host_port.split(':')
                    # Make sure we have a valid DB number
                    try:
                        db_num = int(db)
                    except ValueError:
                        db_num = 0
                    # Reconstruct proper Redis URL
                    redis_url = f"redis://{host}:{port}/{db_num}"
                else:
                    # Just prefix with redis://
                    redis_url = f"redis://{redis_url}"
            
            # Ensure the URL has the proper redis:// prefix
            if not redis_url.startswith('redis://'):
                redis_url = f"redis://{redis_url}"
            
            logger.info(f"Connecting to Redis at: {redis_url}")
            self.redis_client = redis.from_url(redis_url, socket_timeout=2.0)
            
            # Test the connection
            self.redis_client.ping()
            logger.info("Successfully connected to Redis")
            self.initialized = True
            
        except ImportError:
            logger.warning("Redis package not installed, using in-memory fallback for conversation store")
            self.redis_client = None
            self.memory_store = {}
            self.initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis connection: {str(e)}")
            logger.info("Using in-memory fallback for conversation store")
            self.redis_client = None
            self.memory_store = {}
            self.initialized = True
    
    def get_conversation(self, session_id: str) -> Dict[str, Any]:
        """
        Retrieve a stored conversation by session ID.
        
        Args:
            session_id: The unique identifier for the conversation
            
        Returns:
            The conversation data or an empty object if not found
        """
        if not self.initialized:
            self._initialize_redis()
        
        key = f"conv:{session_id}"
        
        try:
            if self.redis_client:
                data = self.redis_client.get(key)
                if data:
                    return json.loads(data)
            else:
                # Fallback to in-memory store
                return self.memory_store.get(key, {})
        
        except Exception as e:
            logger.error(f"Error retrieving conversation {session_id}: {str(e)}")
        
        # Return empty conversation if nothing found or error occurred
        return {
            "id": session_id,
            "created_at": time.time(),
            "updated_at": time.time(),
            "messages": [],
            "context": {},
            "resolved": False
        }
    
    def save_conversation(self, session_id: str, conversation_data: Dict[str, Any], 
                         expiration: int = DEFAULT_EXPIRATION) -> bool:
        """
        Save conversation data to Redis with expiration.
        
        Args:
            session_id: The unique identifier for the conversation
            conversation_data: The conversation data to store
            expiration: Time in seconds until the data expires (default 30 minutes)
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.initialized:
            self._initialize_redis()
        
        key = f"conv:{session_id}"
        
        try:
            # Ensure updated_at is current
            conversation_data["updated_at"] = time.time()
            
            if self.redis_client:
                serialized = json.dumps(conversation_data)
                self.redis_client.setex(key, expiration, serialized)
            else:
                # Fallback to in-memory store
                self.memory_store[key] = conversation_data
                
                # Clean up old conversations in memory to prevent memory leaks
                self._cleanup_memory_store()
                
            return True
            
        except Exception as e:
            logger.error(f"Error saving conversation {session_id}: {str(e)}")
            return False
    
    def update_conversation(self, session_id: str, 
                           update_data: Dict[str, Any], 
                           expiration: int = DEFAULT_EXPIRATION) -> bool:
        """
        Update an existing conversation with new data.
        
        Args:
            session_id: The unique identifier for the conversation
            update_data: The data to update in the conversation
            expiration: Time in seconds until the data expires
            
        Returns:
            bool: True if successful, False otherwise
        """
        conversation = self.get_conversation(session_id)
        
        # Update the conversation with new data
        conversation.update(update_data)
        
        # Set updated timestamp
        conversation["updated_at"] = time.time()
        
        # Save the updated conversation
        return self.save_conversation(session_id, conversation, expiration)
    
    def add_message(self, session_id: str, role: str, content: str, 
                   expiration: int = DEFAULT_EXPIRATION) -> bool:
        """
        Add a message to a conversation.
        
        Args:
            session_id: The unique identifier for the conversation
            role: The role of the message sender (user, assistant, system)
            content: The message content
            expiration: Time in seconds until the data expires
            
        Returns:
            bool: True if successful, False otherwise
        """
        conversation = self.get_conversation(session_id)
        
        # Initialize messages array if not present
        if "messages" not in conversation:
            conversation["messages"] = []
        
        # Add the new message
        conversation["messages"].append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })
        
        # Save the updated conversation
        return self.save_conversation(session_id, conversation, expiration)
    
    def delete_conversation(self, session_id: str) -> bool:
        """
        Delete a conversation from the store.
        
        Args:
            session_id: The unique identifier for the conversation
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.initialized:
            self._initialize_redis()
        
        key = f"conv:{session_id}"
        
        try:
            if self.redis_client:
                self.redis_client.delete(key)
            else:
                # Fallback to in-memory store
                if key in self.memory_store:
                    del self.memory_store[key]
                    
            return True
            
        except Exception as e:
            logger.error(f"Error deleting conversation {session_id}: {str(e)}")
            return False
    
    def _cleanup_memory_store(self):
        """Clean up expired conversations from in-memory store to prevent memory leaks."""
        if not hasattr(self, 'memory_store'):
            return
            
        current_time = time.time()
        keys_to_delete = []
        
        # Find expired conversations (older than DEFAULT_EXPIRATION)
        for key, conversation in self.memory_store.items():
            updated_at = conversation.get("updated_at", 0)
            if current_time - updated_at > DEFAULT_EXPIRATION:
                keys_to_delete.append(key)
        
        # Delete expired conversations
        for key in keys_to_delete:
            del self.memory_store[key]
        
        # Also enforce a maximum size for the memory store (1000 conversations)
        if len(self.memory_store) > 1000:
            # Sort by updated_at and keep only the 800 most recent
            sorted_items = sorted(
                self.memory_store.items(),
                key=lambda x: x[1].get("updated_at", 0),
                reverse=True
            )
            
            # Rebuild the memory store with only the most recent conversations
            self.memory_store = dict(sorted_items[:800])
            
            logger.info(f"Memory store cleaned up, keeping {len(self.memory_store)} recent conversations")

# Singleton instance for easy import
conversation_store = ConversationStore()