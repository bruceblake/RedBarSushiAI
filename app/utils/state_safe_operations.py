"""
State-Safe Operation Utilities for RedBarSushiAI.

This module provides utilities for performing state modifications with
automatic rollback on persistence failures to prevent split-brain scenarios.
"""

import copy
import logging
from typing import Dict, Any, Callable, Optional, Union
from contextlib import asynccontextmanager

from app.exceptions.conversation_exceptions import RedisSaveError, ConversationRollbackError
from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)


class StateSafeWrapper:
    """
    Wrapper for performing state-safe operations with automatic rollback.
    
    This class captures the original state before modification and can
    restore it if the persistence operation fails.
    """
    
    def __init__(self, conversation_store, call_sid: str):
        """
        Initialize state-safe wrapper.
        
        Args:
            conversation_store: The conversation store instance
            call_sid: Call SID for the conversation
        """
        self.conversation_store = conversation_store
        self.call_sid = call_sid
        self.original_state: Optional[Dict[str, Any]] = None
        self.modified_state: Optional[Dict[str, Any]] = None
    
    async def capture_original_state(self) -> Dict[str, Any]:
        """
        Capture the current conversation state before modification.
        
        Returns:
            Deep copy of the current conversation state
        """
        current_conversation = await self.conversation_store.get_conversation(self.call_sid)
        self.original_state = copy.deepcopy(current_conversation)
        return self.original_state
    
    async def apply_state_changes(self, state_modifier: Callable[[Dict[str, Any]], Dict[str, Any]]) -> Dict[str, Any]:
        """
        Apply state changes and capture the modified state.
        
        Args:
            state_modifier: Function that takes current state and returns modified state
            
        Returns:
            Modified state
        """
        if self.original_state is None:
            raise ValueError("Must capture original state before applying changes")
        
        # Apply modifications to a copy of the original state
        self.modified_state = state_modifier(copy.deepcopy(self.original_state))
        return self.modified_state
    
    async def persist_changes(self) -> bool:
        """
        Attempt to persist the modified state to Redis.
        
        Returns:
            True if successful
            
        Raises:
            RedisSaveError: If persistence fails
        """
        if self.modified_state is None:
            raise ValueError("No modified state to persist")
        
        try:
            success = await self.conversation_store.save_conversation(
                self.call_sid, 
                self.modified_state
            )
            logger.debug(f"[{self.call_sid}] Successfully persisted state changes")
            return success
        except RedisSaveError as e:
            logger.error(f"[{self.call_sid}] Failed to persist state changes: {e}")
            raise
    
    async def rollback_to_original(self) -> bool:
        """
        Rollback to the original state captured before modification.
        
        This method attempts to restore the conversation store to the
        original state if persistence fails.
        
        Returns:
            True if rollback successful
            
        Raises:
            ConversationRollbackError: If rollback fails
        """
        if self.original_state is None:
            raise ValueError("No original state captured for rollback")
        
        try:
            # Attempt to restore original state
            success = await self.conversation_store.save_conversation(
                self.call_sid,
                self.original_state
            )
            
            if success:
                logger.info(f"[{self.call_sid}] Successfully rolled back to original state")
                return True
            else:
                raise ConversationRollbackError(
                    f"Failed to rollback conversation state for {self.call_sid}",
                    call_sid=self.call_sid
                )
                
        except Exception as e:
            logger.error(f"[{self.call_sid}] Rollback operation failed: {e}")
            raise ConversationRollbackError(
                f"Rollback failed for {self.call_sid}: {str(e)}",
                call_sid=self.call_sid,
                original_error=e
            )


@asynccontextmanager
async def state_safe_operation(conversation_store, call_sid: str):
    """
    Async context manager for state-safe operations.
    
    This context manager ensures that conversation state modifications
    are either fully persisted or completely rolled back to prevent
    split-brain scenarios.
    
    Args:
        conversation_store: The conversation store instance
        call_sid: Call SID for the conversation
        
    Example:
        async with state_safe_operation(store, call_sid) as state_wrapper:
            # Capture original state
            original = await state_wrapper.capture_original_state()
            
            # Apply modifications
            modified = await state_wrapper.apply_state_changes(
                lambda state: {**state, "cart": updated_cart}
            )
            
            # Changes automatically persisted or rolled back
    """
    wrapper = StateSafeWrapper(conversation_store, call_sid)
    
    try:
        yield wrapper
        
        # Automatically persist changes if they were applied
        if wrapper.modified_state is not None:
            await wrapper.persist_changes()
            
    except RedisSaveError as e:
        logger.warning(f"[{call_sid}] Persistence failed, attempting rollback: {e}")
        
        try:
            await wrapper.rollback_to_original()
            logger.info(f"[{call_sid}] Successfully rolled back after persistence failure")
        except ConversationRollbackError as rollback_error:
            logger.critical(f"[{call_sid}] CRITICAL: Both persistence and rollback failed!")
            raise rollback_error
        
        # Re-raise the original persistence error after successful rollback
        raise e
    except Exception as e:
        logger.error(f"[{call_sid}] Unexpected error in state-safe operation: {e}")
        raise


async def safe_cart_update(
    conversation_store, 
    call_sid: str, 
    cart_modifier: Callable[[Dict[str, Any]], Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Safely update cart with automatic rollback on persistence failure.
    
    Args:
        conversation_store: The conversation store instance
        call_sid: Call SID for the conversation
        cart_modifier: Function that takes current cart and returns modified cart
        
    Returns:
        Updated conversation state with modified cart
        
    Raises:
        RedisSaveError: If persistence fails and rollback succeeds
        ConversationRollbackError: If both persistence and rollback fail
    """
    async with state_safe_operation(conversation_store, call_sid) as state_wrapper:
        # Capture current state
        await state_wrapper.capture_original_state()
        
        # Apply cart modifications
        def update_cart_in_state(state: Dict[str, Any]) -> Dict[str, Any]:
            current_cart = state.get("context", {}).get("cart", {"items": [], "total_price": 0})
            updated_cart = cart_modifier(current_cart)
            
            # Update the cart in context
            if "context" not in state:
                state["context"] = {}
            state["context"]["cart"] = updated_cart
            
            return state
        
        modified_state = await state_wrapper.apply_state_changes(update_cart_in_state)
        return modified_state


async def safe_context_update(
    conversation_store,
    call_sid: str,
    context_key: str,
    new_value: Any
) -> Dict[str, Any]:
    """
    Safely update a specific context value with automatic rollback.
    
    Args:
        conversation_store: The conversation store instance
        call_sid: Call SID for the conversation
        context_key: Key in the context to update
        new_value: New value to set
        
    Returns:
        Updated conversation state
        
    Raises:
        RedisSaveError: If persistence fails and rollback succeeds
        ConversationRollbackError: If both persistence and rollback fail
    """
    async with state_safe_operation(conversation_store, call_sid) as state_wrapper:
        # Capture current state
        await state_wrapper.capture_original_state()
        
        # Apply context modification
        def update_context_in_state(state: Dict[str, Any]) -> Dict[str, Any]:
            if "context" not in state:
                state["context"] = {}
            state["context"][context_key] = new_value
            return state
        
        modified_state = await state_wrapper.apply_state_changes(update_context_in_state)
        return modified_state