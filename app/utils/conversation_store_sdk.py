"""
Enhanced conversation store for RedBarSushiAI with Agents SDK integration.
This module extends the original conversation store with support for OpenAI Agents SDK.
"""

import json
import logging
import time
import os
from typing import Dict, List, Any, Optional, Union
import uuid

from app.utils.conversation_store import conversation_store as base_store
from app.utils.agents_sdk import get_redis_client

logger = logging.getLogger(__name__)

# Default expiration time for conversations (2 hours = 7200 seconds)
DEFAULT_EXPIRATION = 7200

class AgentsConversationStore:
    """Enhanced conversation store with Agents SDK integration."""
    
    def __init__(self):
        """Initialize the agents conversation store."""
        self.base_store = base_store
        self.redis_client = None
        self.initialized = False
    
    def _initialize_redis(self):
        """Initialize the Redis connection reusing the base store's connection."""
        if self.base_store.initialized:
            self.redis_client = self.base_store.redis_client
            self.initialized = True
        else:
            # Force the base store to initialize
            self.base_store._initialize_redis()
            if self.base_store.initialized:
                self.redis_client = self.base_store.redis_client
                self.initialized = True
            else:
                # Fall back to our own Redis client
                self.redis_client = get_redis_client()
                self.initialized = self.redis_client is not None
    
    def get_thread_id(self, call_sid: str) -> Optional[str]:
        """
        Get the thread ID for a call SID.
        
        Args:
            call_sid: The Twilio call SID
            
        Returns:
            The thread ID if found, None otherwise
        """
        if not self.initialized:
            self._initialize_redis()
        
        if not self.redis_client:
            logger.error("Redis client not available")
            return None
        
        try:
            thread_id = self.redis_client.get(f"call:{call_sid}")
            if thread_id:
                return thread_id.decode('utf-8')
            return None
        except Exception as e:
            logger.error(f"Error getting thread ID for call {call_sid}: {str(e)}")
            return None
    
    def set_thread_id(self, call_sid: str, thread_id: str, expiration: int = DEFAULT_EXPIRATION) -> bool:
        """
        Store a thread ID for a call SID.
        
        Args:
            call_sid: The Twilio call SID
            thread_id: The thread ID to store
            expiration: Time in seconds until the mapping expires
            
        Returns:
            True if successful, False otherwise
        """
        if not self.initialized:
            self._initialize_redis()
        
        if not self.redis_client:
            logger.error("Redis client not available")
            return False
        
        try:
            self.redis_client.setex(f"call:{call_sid}", expiration, thread_id)
            logger.info(f"Stored thread ID {thread_id} for call {call_sid}")
            return True
        except Exception as e:
            logger.error(f"Error storing thread ID for call {call_sid}: {str(e)}")
            return False
    
    def get_cart(self, call_sid: str) -> Dict[str, Any]:
        """
        Get the cart for a call SID.
        
        Args:
            call_sid: The Twilio call SID
            
        Returns:
            The cart data as a dictionary
        """
        if not self.initialized:
            self._initialize_redis()
        
        if not self.redis_client:
            logger.error("Redis client not available")
            return {"items": [], "total_price": 0}
        
        try:
            cart_json = self.redis_client.hget(f"cart:{call_sid}", "json")
            if cart_json:
                return json.loads(cart_json.decode('utf-8'))
            
            # Return an empty cart if none exists
            return {"items": [], "total_price": 0}
        except Exception as e:
            logger.error(f"Error getting cart for call {call_sid}: {str(e)}")
            return {"items": [], "total_price": 0}
    
    def update_cart(
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
        if not self.initialized:
            self._initialize_redis()
        
        if not self.redis_client:
            logger.error("Redis client not available")
            return False
        
        try:
            cart_json = json.dumps(cart_data)
            self.redis_client.hset(f"cart:{call_sid}", "json", cart_json)
            self.redis_client.expire(f"cart:{call_sid}", expiration)
            logger.info(f"Updated cart for call {call_sid} with {len(cart_data.get('items', []))} items")
            return True
        except Exception as e:
            logger.error(f"Error updating cart for call {call_sid}: {str(e)}")
            return False
    
    def add_to_cart(
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
        cart = self.get_cart(call_sid)
        
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
        self.update_cart(call_sid, cart, expiration)
        
        return cart
    
    def remove_from_cart(
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
        cart = self.get_cart(call_sid)
        
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
        self.update_cart(call_sid, cart, expiration)
        
        return cart
    
    def clear_cart(self, call_sid: str) -> bool:
        """
        Clear the cart for a call SID.
        
        Args:
            call_sid: The Twilio call SID
            
        Returns:
            True if successful, False otherwise
        """
        if not self.initialized:
            self._initialize_redis()
        
        if not self.redis_client:
            logger.error("Redis client not available")
            return False
        
        try:
            self.redis_client.delete(f"cart:{call_sid}")
            logger.info(f"Cleared cart for call {call_sid}")
            return True
        except Exception as e:
            logger.error(f"Error clearing cart for call {call_sid}: {str(e)}")
            return False
    
    def get_call_state(self, call_sid: str) -> Dict[str, Any]:
        """
        Get the complete state for a call SID.
        
        Args:
            call_sid: The Twilio call SID
            
        Returns:
            The call state
        """
        if not self.initialized:
            self._initialize_redis()
        
        try:
            # Get the conversation from the base store
            conversation = self.base_store.get_conversation(call_sid)
            
            # Get the thread ID
            thread_id = self.get_thread_id(call_sid)
            
            # Get the cart
            cart = self.get_cart(call_sid)
            
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
    
    def update_call_state(
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
        if not self.initialized:
            self._initialize_redis()
        
        if not self.redis_client:
            logger.error("Redis client not available")
            return False
        
        try:
            # Update thread ID if provided
            if "thread_id" in state_updates:
                self.set_thread_id(call_sid, state_updates["thread_id"], expiration)
            
            # Update conversation if provided
            if "conversation" in state_updates:
                self.base_store.update_conversation(
                    call_sid, 
                    state_updates["conversation"], 
                    expiration
                )
            
            # Update cart if provided
            if "cart" in state_updates:
                self.update_cart(call_sid, state_updates["cart"], expiration)
            
            return True
        except Exception as e:
            logger.error(f"Error updating call state for {call_sid}: {str(e)}")
            return False
    
    def add_message(
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
        return self.base_store.add_message(call_sid, role, content, expiration)
    
    def get_conversation(self, call_sid: str) -> Dict[str, Any]:
        """
        Get the conversation for a call SID.
        Wrapper around the base store's get_conversation method.
        
        Args:
            call_sid: The Twilio call SID
            
        Returns:
            The conversation data
        """
        return self.base_store.get_conversation(call_sid)
    
    def save_conversation(
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
        return self.base_store.save_conversation(session_id, conversation_data, expiration)
    
    def update_conversation(
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
        return self.base_store.update_conversation(session_id, update_data, expiration)
    
    def delete_conversation(self, session_id: str) -> bool:
        """
        Delete a conversation from the store.
        Wrapper around the base store's delete_conversation method.
        
        Args:
            session_id: The unique identifier for the conversation
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.initialized:
            self._initialize_redis()
        
        # Delete the thread ID mapping
        if self.redis_client:
            try:
                self.redis_client.delete(f"call:{session_id}")
            except Exception as e:
                logger.error(f"Error deleting thread ID for call {session_id}: {str(e)}")
        
        # Delete the cart
        if self.redis_client:
            try:
                self.redis_client.delete(f"cart:{session_id}")
            except Exception as e:
                logger.error(f"Error deleting cart for call {session_id}: {str(e)}")
        
        # Delete the conversation
        return self.base_store.delete_conversation(session_id)

# Singleton instance for easy import
agents_conversation_store = AgentsConversationStore()