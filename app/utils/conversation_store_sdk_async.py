"""
Enhanced async conversation store for RedBarSushiAI with Agents SDK integration.
This module extends the original conversation store with support for OpenAI Agents SDK.
"""

import json
import logging
import time
import os
from typing import Dict, List, Any, Optional, Union
import uuid

from app.utils.conversation_store_async import async_conversation_store as base_store
from app.redis_async import redis_get, redis_set, redis_delete, get_redis

logger = logging.getLogger(__name__)

# Default expiration time for conversations (2 hours = 7200 seconds)
DEFAULT_EXPIRATION = 7200

class AsyncAgentsConversationStore:
    """Enhanced async conversation store with Agents SDK integration."""
    
    def __init__(self):
        """Initialize the async agents conversation store."""
        self.base_store = base_store
    
    async def get_thread_id(self, call_sid: str) -> Optional[str]:
        """
        Get the thread ID for a call SID.
        
        Args:
            call_sid: The Twilio call SID
            
        Returns:
            The thread ID if found, None otherwise
        """
        try:
            thread_id_bytes = await redis_get(f"call:{call_sid}")
            if thread_id_bytes:
                return thread_id_bytes.decode('utf-8')
            return None
        except Exception as e:
            logger.error(f"Error getting thread ID for call {call_sid}: {str(e)}")
            return None
    
    async def set_thread_id(self, call_sid: str, thread_id: str, expiration: int = DEFAULT_EXPIRATION) -> bool:
        """
        Store a thread ID for a call SID.
        
        Args:
            call_sid: The Twilio call SID
            thread_id: The thread ID to store
            expiration: Time in seconds until the mapping expires
            
        Returns:
            True if successful, False otherwise
        """
        try:
            success = await redis_set(f"call:{call_sid}", thread_id, expiration)
            if success:
                logger.info(f"Stored thread ID {thread_id} for call {call_sid}")
            return success
        except Exception as e:
            logger.error(f"Error storing thread ID for call {call_sid}: {str(e)}")
            return False
    
    async def get_cart(self, call_sid: str) -> Dict[str, Any]:
        """
        Get the cart for a call SID.
        
        Args:
            call_sid: The Twilio call SID
            
        Returns:
            The cart data as a dictionary
        """
        try:
            # Try to get Redis client
            redis_client = await get_redis()
            
            # Get cart from Redis hash
            cart_json = await redis_client.hget(f"cart:{call_sid}", "json")
            if cart_json:
                return json.loads(cart_json.decode('utf-8'))
            
            # Return an empty cart if none exists
            return {"items": [], "total_price": 0}
        except Exception as e:
            logger.error(f"Error getting cart for call {call_sid}: {str(e)}")
            return {"items": [], "total_price": 0}
    
    async def update_cart(
        self, 
        call_sid: str, 
        cart_data: Dict[str, Any], 
        expiration: int = DEFAULT_EXPIRATION
    ) -> bool:
        """
        Update the cart for a call SID.
        
        Args:
            call_sid: The Twilio call SID
            cart_data: The cart data to store
            expiration: Time in seconds until the cart expires
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Try to get Redis client
            redis_client = await get_redis()
            
            # Update cart in Redis hash
            cart_json = json.dumps(cart_data)
            await redis_client.hset(f"cart:{call_sid}", "json", cart_json)
            await redis_client.expire(f"cart:{call_sid}", expiration)
            
            logger.info(f"Updated cart for call {call_sid} with {len(cart_data.get('items', []))} items")
            return True
        except Exception as e:
            logger.error(f"Error updating cart for call {call_sid}: {str(e)}")
            return False
    
    async def add_to_cart(
        self, 
        call_sid: str, 
        item: Dict[str, Any], 
        expiration: int = DEFAULT_EXPIRATION
    ) -> Dict[str, Any]:
        """
        Add an item to the cart.
        
        Args:
            call_sid: The Twilio call SID
            item: The item to add
            expiration: Time in seconds until the cart expires
            
        Returns:
            The updated cart
        """
        # Get the current cart
        cart = await self.get_cart(call_sid)
        
        # Add the item
        cart["items"].append(item)
        
        # Calculate the total price
        total_price = 0
        for cart_item in cart["items"]:
            # Get the item price and quantity
            item_price = cart_item.get("price", 0)
            item_quantity = cart_item.get("quantity", 1)
            
            # Add to total
            total_price += item_price * item_quantity
            
            # Add modifier prices
            for modifier in cart_item.get("modifiers", []):
                mod_price = modifier.get("price_change", 0)
                mod_quantity = modifier.get("quantity", 1)
                total_price += mod_price * mod_quantity
        
        # Update the total price
        cart["total_price"] = total_price
        
        # Update the cart in Redis
        await self.update_cart(call_sid, cart, expiration)
        
        return cart
    
    async def remove_from_cart(
        self, 
        call_sid: str, 
        item_index: int, 
        expiration: int = DEFAULT_EXPIRATION
    ) -> Dict[str, Any]:
        """
        Remove an item from the cart.
        
        Args:
            call_sid: The Twilio call SID
            item_index: The index of the item to remove
            expiration: Time in seconds until the cart expires
            
        Returns:
            The updated cart
        """
        # Get the current cart
        cart = await self.get_cart(call_sid)
        
        # Check if the index is valid
        if item_index < 0 or item_index >= len(cart.get("items", [])):
            logger.warning(f"Invalid item index {item_index} for cart with {len(cart.get('items', []))} items")
            return cart
        
        # Remove the item
        cart["items"].pop(item_index)
        
        # Recalculate the total price
        total_price = 0
        for cart_item in cart["items"]:
            # Get the item price and quantity
            item_price = cart_item.get("price", 0)
            item_quantity = cart_item.get("quantity", 1)
            
            # Add to total
            total_price += item_price * item_quantity
            
            # Add modifier prices
            for modifier in cart_item.get("modifiers", []):
                mod_price = modifier.get("price_change", 0)
                mod_quantity = modifier.get("quantity", 1)
                total_price += mod_price * mod_quantity
        
        # Update the total price
        cart["total_price"] = total_price
        
        # Update the cart in Redis
        await self.update_cart(call_sid, cart, expiration)
        
        return cart
    
    async def clear_cart(self, call_sid: str) -> bool:
        """
        Clear the cart for a call SID.
        
        Args:
            call_sid: The Twilio call SID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            success = await redis_delete(f"cart:{call_sid}")
            if success:
                logger.info(f"Cleared cart for call {call_sid}")
            return success
        except Exception as e:
            logger.error(f"Error clearing cart for call {call_sid}: {str(e)}")
            return False
    
    async def get_call_state(self, call_sid: str) -> Dict[str, Any]:
        """
        Get the complete state for a call SID.
        
        Args:
            call_sid: The Twilio call SID
            
        Returns:
            The call state
        """
        try:
            # Get the conversation from the base store
            conversation = await self.base_store.get_conversation(call_sid)
            
            # Get the thread ID
            thread_id = await self.get_thread_id(call_sid)
            
            # Get the cart
            cart = await self.get_cart(call_sid)
            
            # Combine into a complete state
            state = {
                "call_sid": call_sid,
                "thread_id": thread_id,
                "conversation": conversation,
                "cart": cart,
                "timestamp": time.time()
            }
            
            return state
        except Exception as e:
            logger.error(f"Error getting call state for {call_sid}: {str(e)}")
            return {
                "call_sid": call_sid,
                "thread_id": None,
                "conversation": {"messages": []},
                "cart": {"items": [], "total_price": 0},
                "timestamp": time.time()
            }
    
    async def update_call_state(
        self, 
        call_sid: str, 
        state_updates: Dict[str, Any], 
        expiration: int = DEFAULT_EXPIRATION
    ) -> bool:
        """
        Update the state for a call SID.
        
        Args:
            call_sid: The Twilio call SID
            state_updates: The state updates
            expiration: Time in seconds until the state expires
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Update thread ID if provided
            if "thread_id" in state_updates:
                await self.set_thread_id(call_sid, state_updates["thread_id"], expiration)
            
            # Update conversation if provided
            if "conversation" in state_updates:
                await self.base_store.update_conversation(
                    call_sid, 
                    state_updates["conversation"], 
                    expiration
                )
            
            # Update cart if provided
            if "cart" in state_updates:
                await self.update_cart(call_sid, state_updates["cart"], expiration)
            
            return True
        except Exception as e:
            logger.error(f"Error updating call state for {call_sid}: {str(e)}")
            return False
    
    async def add_message(
        self, 
        call_sid: str, 
        role: str, 
        content: str, 
        expiration: int = DEFAULT_EXPIRATION
    ) -> bool:
        """
        Add a message to the conversation.
        Wrapper around the base store's add_message method.
        
        Args:
            call_sid: The Twilio call SID
            role: The message role (user or assistant)
            content: The message content
            expiration: Time in seconds until the message expires
            
        Returns:
            True if successful, False otherwise
        """
        return await self.base_store.add_message(call_sid, role, content, expiration)
    
    async def get_conversation(self, call_sid: str) -> Dict[str, Any]:
        """
        Get the conversation for a call SID.
        Wrapper around the base store's get_conversation method.
        
        Args:
            call_sid: The Twilio call SID
            
        Returns:
            The conversation data
        """
        return await self.base_store.get_conversation(call_sid)
    
    async def save_conversation(
        self, 
        session_id: str, 
        conversation_data: Dict[str, Any], 
        expiration: int = DEFAULT_EXPIRATION
    ) -> bool:
        """
        Save conversation data to Redis.
        Wrapper around the base store's save_conversation method.
        
        Args:
            session_id: The unique identifier for the conversation
            conversation_data: The conversation data to store
            expiration: Time in seconds until the data expires
            
        Returns:
            bool: True if successful, False otherwise
        """
        return await self.base_store.save_conversation(session_id, conversation_data, expiration)
    
    async def update_conversation(
        self, 
        session_id: str, 
        update_data: Dict[str, Any], 
        expiration: int = DEFAULT_EXPIRATION
    ) -> bool:
        """
        Update an existing conversation with new data.
        Wrapper around the base store's update_conversation method.
        
        Args:
            session_id: The unique identifier for the conversation
            update_data: The data to update in the conversation
            expiration: Time in seconds until the data expires
            
        Returns:
            bool: True if successful, False otherwise
        """
        return await self.base_store.update_conversation(session_id, update_data, expiration)
    
    async def delete_conversation(self, session_id: str) -> bool:
        """
        Delete a conversation from the store.
        
        Args:
            session_id: The unique identifier for the conversation
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Delete the thread ID mapping
            await redis_delete(f"call:{session_id}")
            
            # Delete the cart
            await redis_delete(f"cart:{session_id}")
            
            # Delete the conversation
            return await self.base_store.delete_conversation(session_id)
        except Exception as e:
            logger.error(f"Error deleting conversation {session_id}: {str(e)}")
            return False

# Singleton instance for easy import
async_agents_conversation_store = AsyncAgentsConversationStore()