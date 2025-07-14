"""
Redis-based async conversation store for maintaining context in interactive conversations.
Stores conversation history and state between API calls for menu questions and order resolution.
"""

import json
import logging
import time
import os
from decimal import Decimal
from typing import Dict, List, Any, Optional

from app.redis_async import redis_get, redis_set, redis_delete, memory_cache_get, memory_cache_set

# Configure logger
logger = logging.getLogger(__name__)

# Default expiration time for conversations (30 minutes)
DEFAULT_EXPIRATION = 1800

def safe_json_dumps(obj: Any, **kwargs) -> str:
    """JSON dumps with Decimal support."""
    def decimal_default(o):
        if isinstance(o, Decimal):
            return float(o)
        raise TypeError(f'Object of type {o.__class__.__name__} is not JSON serializable')
    
    return json.dumps(obj, default=decimal_default, **kwargs)


class AsyncConversationStore:
    """Manages conversation state and history using Redis with async API."""

    def __init__(self):
        """Initialize the async conversation store."""
        self.memory_store = {}  # Initialize memory store for fallback

    async def get_conversation(self, session_id: str) -> Dict[str, Any]:
        """
        Retrieve a stored conversation by session ID.

        Args:
            session_id: The unique identifier for the conversation

        Returns:
            The conversation data or an empty object if not found
        """
        key = f"conv:{session_id}"

        try:
            # Try to get from Redis
            data = await redis_get(key)
            
            if data:
                try:
                    conversation = json.loads(data.decode('utf-8'))
                    # Verify that we actually have a proper conversation object
                    if not isinstance(conversation.get("messages"), list):
                        logger.warning(
                            f"Retrieved invalid conversation format for {session_id}, initializing new conversation"
                        )
                        # Return new conversation if format is invalid
                        return {
                            "id": session_id,
                            "created_at": time.time(),
                            "updated_at": time.time(),
                            "messages": [],
                            "context": {},
                            "resolved": False,
                            "items": [],
                        }
                    return conversation
                except json.JSONDecodeError:
                    logger.error(
                        f"Error decoding JSON for conversation {session_id}"
                    )
            else:
                # Fallback to in-memory store
                conversation = memory_cache_get(key)
                if conversation:
                    # Verify that we actually have a proper conversation object
                    if not isinstance(conversation.get("messages"), list):
                        logger.warning(
                            f"Retrieved invalid in-memory conversation format for {session_id}, initializing new conversation"
                        )
                        # Return new conversation if format is invalid
                        return {
                            "id": session_id,
                            "created_at": time.time(),
                            "updated_at": time.time(),
                            "messages": [],
                            "context": {},
                            "resolved": False,
                            "items": [],
                        }
                    return conversation

        except Exception as e:
            logger.error(f"Error retrieving conversation {session_id}: {str(e)}")

        # Return empty conversation if nothing found or error occurred
        return {
            "id": session_id,
            "created_at": time.time(),
            "updated_at": time.time(),
            "messages": [],
            "context": {},
            "resolved": False,
            "items": [],
        }

    async def save_conversation(
        self,
        session_id: str,
        conversation_data: Dict[str, Any],
        expiration: int = DEFAULT_EXPIRATION,
    ) -> bool:
        """
        Save conversation data to Redis with robust error handling.
        
        This method now raises RedisSaveError when Redis operations fail,
        allowing calling code to handle split-brain scenarios appropriately.

        Args:
            session_id: The unique identifier for the conversation
            conversation_data: The conversation data to store
            expiration: Time in seconds until the data expires (default 30 minutes)

        Returns:
            bool: True if successful
            
        Raises:
            RedisSaveError: If conversation cannot be saved to Redis
        """
        key = f"conv:{session_id}"

        try:
            # Ensure updated_at is current
            conversation_data["updated_at"] = time.time()

            # Try to save in Redis - this is now REQUIRED
            serialized = safe_json_dumps(conversation_data)
            redis_success = await redis_set(key, serialized, expiration)
            
            if not redis_success:
                # Redis save failed - this is now an error condition
                from app.exceptions.conversation_exceptions import RedisSaveError
                error_msg = f"Failed to save conversation {session_id} to Redis"
                logger.error(error_msg)
                raise RedisSaveError(
                    error_msg, 
                    call_sid=session_id, 
                    operation="save_conversation"
                )

            # Success - also update memory cache for fast access
            memory_cache_set(key, conversation_data)
            logger.debug(f"Successfully saved conversation {session_id} to Redis and memory")
            return True

        except Exception as e:
            # Check if this is already a RedisSaveError
            from app.exceptions.conversation_exceptions import RedisSaveError
            if isinstance(e, RedisSaveError):
                raise  # Re-raise Redis save errors
            
            # Unexpected error during save operation
            error_msg = f"Unexpected error saving conversation {session_id}: {str(e)}"
            logger.error(error_msg)
            raise RedisSaveError(
                error_msg,
                call_sid=session_id,
                operation="save_conversation"
            )

    async def update_conversation(
        self,
        session_id: str,
        update_data: Dict[str, Any],
        expiration: int = DEFAULT_EXPIRATION,
    ) -> bool:
        """
        Update an existing conversation with new data.

        Args:
            session_id: The unique identifier for the conversation
            update_data: The data to update in the conversation
            expiration: Time in seconds until the data expires

        Returns:
            bool: True if successful, False otherwise
        """
        conversation = await self.get_conversation(session_id)

        # Update the conversation with new data
        conversation.update(update_data)

        # Set updated timestamp
        conversation["updated_at"] = time.time()

        # Save the updated conversation
        return await self.save_conversation(session_id, conversation, expiration)

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        expiration: int = DEFAULT_EXPIRATION,
    ) -> bool:
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
        conversation = await self.get_conversation(session_id)

        # Initialize messages array if not present
        if "messages" not in conversation:
            conversation["messages"] = []

        # Add the new message
        conversation["messages"].append(
            {"role": role, "content": content, "timestamp": time.time()}
        )

        # Save the updated conversation
        return await self.save_conversation(session_id, conversation, expiration)

    async def delete_conversation(self, session_id: str) -> bool:
        """
        Delete a conversation from the store.

        Args:
            session_id: The unique identifier for the conversation

        Returns:
            bool: True if successful, False otherwise
        """
        key = f"conv:{session_id}"

        try:
            # Try to delete from Redis
            await redis_delete(key)
            
            # Also remove from memory cache if it exists
            if memory_cache_get(key):
                memory_cache_set(key, None)
                
            return True

        except Exception as e:
            logger.error(f"Error deleting conversation {session_id}: {str(e)}")
            return False


# Singleton instance for easy import
async_conversation_store = AsyncConversationStore()
# Alias for backward compatibility
async_agents_conversation_store = async_conversation_store