"""
State Store for HSM state persistence in Redis.

This module manages the hierarchical state stack for each conversation,
storing the active state path and supporting state navigation.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.redis_async import get_redis
from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)


class HSMStateStore:
    """
    Manages HSM state persistence in Redis.
    
    Stores the current state path (from root to leaf) and maintains
    state history for each conversation.
    """
    
    def __init__(self, key_prefix: str = "hsm:state"):
        """
        Initialize the state store.
        
        Args:
            key_prefix: Redis key prefix for state storage
        """
        self.key_prefix = key_prefix
    
    def _get_key(self, call_sid: str) -> str:
        """Generate Redis key for a conversation."""
        return f"{self.key_prefix}:{call_sid}"
    
    def _get_history_key(self, call_sid: str) -> str:
        """Generate Redis key for state history."""
        return f"{self.key_prefix}:history:{call_sid}"
    
    async def get_current_state_path(self, call_sid: str) -> List[str]:
        """
        Get the current state path for a conversation.
        
        Args:
            call_sid: Conversation identifier
            
        Returns:
            List of state names from root to current leaf state
        """
        try:
            redis_client = await get_redis()
            key = self._get_key(call_sid)
            data = await redis_client.get(key)
            
            if data:
                state_data = json.loads(data)
                path = state_data.get("path", [])
                logger.debug(f"[{call_sid}] Retrieved state path: {path}")
                return path
            else:
                logger.debug(f"[{call_sid}] No state path found")
                return []
                
        except Exception as e:
            logger.error(f"[{call_sid}] Error retrieving state path: {e}")
            return []
    
    async def set_state_path(self, call_sid: str, state_path: List[str]) -> None:
        """
        Set the current state path for a conversation.
        
        Args:
            call_sid: Conversation identifier
            state_path: List of state names from root to leaf
        """
        try:
            redis_client = await get_redis()
            key = self._get_key(call_sid)
            state_data = {
                "path": state_path,
                "updated_at": datetime.utcnow().isoformat(),
                "leaf_state": state_path[-1] if state_path else None
            }
            
            await redis_client.set(key, json.dumps(state_data))
            logger.info(f"[{call_sid}] Set state path: {state_path}")
            
            # Add to history
            await self._add_to_history(call_sid, state_path)
            
        except Exception as e:
            logger.error(f"[{call_sid}] Error setting state path: {e}")
    
    async def push_state(self, call_sid: str, state_to_enter: str, event_data: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        Push a new state onto the state stack.
        
        This is used when entering a substate or transitioning to a new state.
        
        Args:
            call_sid: Conversation identifier
            state_to_enter: Name of the state to enter
            event_data: Optional event data that triggered the transition
            
        Returns:
            Updated state path
        """
        try:
            current_path = await self.get_current_state_path(call_sid)
            
            # If the new state is already in the path, we need to pop back to it
            if state_to_enter in current_path:
                index = current_path.index(state_to_enter)
                new_path = current_path[:index + 1]
            else:
                # Simply append the new state
                new_path = current_path + [state_to_enter]
            
            await self.set_state_path(call_sid, new_path)
            
            logger.info(f"[{call_sid}] Pushed state '{state_to_enter}', new path: {new_path}")
            return new_path
            
        except Exception as e:
            logger.error(f"[{call_sid}] Error pushing state: {e}")
            return current_path if 'current_path' in locals() else []
    
    async def pop_state(self, call_sid: str, event_data: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Pop the current leaf state from the stack.
        
        Args:
            call_sid: Conversation identifier
            event_data: Optional event data that triggered the pop
            
        Returns:
            The new leaf state after popping, or None if stack is empty
        """
        try:
            current_path = await self.get_current_state_path(call_sid)
            
            if len(current_path) > 1:
                # Remove the leaf state
                popped_state = current_path.pop()
                await self.set_state_path(call_sid, current_path)
                
                new_leaf = current_path[-1] if current_path else None
                logger.info(f"[{call_sid}] Popped state '{popped_state}', new leaf: '{new_leaf}'")
                return new_leaf
            else:
                logger.warning(f"[{call_sid}] Cannot pop from state path: {current_path}")
                return None
                
        except Exception as e:
            logger.error(f"[{call_sid}] Error popping state: {e}")
            return None
    
    async def replace_state_path(self, call_sid: str, new_path: List[str]) -> None:
        """
        Replace the entire state path (used for major transitions).
        
        Args:
            call_sid: Conversation identifier
            new_path: New complete state path
        """
        await self.set_state_path(call_sid, new_path)
    
    async def get_leaf_state(self, call_sid: str) -> Optional[str]:
        """
        Get the current leaf (active) state.
        
        Args:
            call_sid: Conversation identifier
            
        Returns:
            Name of the current leaf state, or None
        """
        path = await self.get_current_state_path(call_sid)
        return path[-1] if path else None
    
    async def get_parent_state(self, call_sid: str) -> Optional[str]:
        """
        Get the parent of the current leaf state.
        
        Args:
            call_sid: Conversation identifier
            
        Returns:
            Name of the parent state, or None
        """
        path = await self.get_current_state_path(call_sid)
        return path[-2] if len(path) > 1 else None
    
    async def is_in_state(self, call_sid: str, state_name: str) -> bool:
        """
        Check if the conversation is currently in a given state.
        
        This checks if the state is anywhere in the current path.
        
        Args:
            call_sid: Conversation identifier
            state_name: State to check for
            
        Returns:
            True if the state is in the current path
        """
        path = await self.get_current_state_path(call_sid)
        return state_name in path
    
    async def clear_state(self, call_sid: str) -> None:
        """
        Clear all state information for a conversation.
        
        Args:
            call_sid: Conversation identifier
        """
        try:
            redis_client = await get_redis()
            key = self._get_key(call_sid)
            history_key = self._get_history_key(call_sid)
            
            await redis_client.delete(key)
            await redis_client.delete(history_key)
            
            logger.info(f"[{call_sid}] Cleared state information")
            
        except Exception as e:
            logger.error(f"[{call_sid}] Error clearing state: {e}")
    
    async def _add_to_history(self, call_sid: str, state_path: List[str]) -> None:
        """
        Add a state path to the conversation history.
        
        Args:
            call_sid: Conversation identifier
            state_path: State path to record
        """
        try:
            redis_client = await get_redis()
            history_key = self._get_history_key(call_sid)
            
            history_entry = {
                "path": state_path,
                "leaf_state": state_path[-1] if state_path else None,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Add to a Redis list (keeping last 20 entries)
            await redis_client.lpush(history_key, json.dumps(history_entry))
            await redis_client.ltrim(history_key, 0, 19)
            
            # Set expiry on history (24 hours)
            await redis_client.expire(history_key, 86400)
            
        except Exception as e:
            logger.error(f"[{call_sid}] Error adding to history: {e}")
    
    async def get_state_history(self, call_sid: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get the state transition history for a conversation.
        
        Args:
            call_sid: Conversation identifier
            limit: Maximum number of history entries to return
            
        Returns:
            List of history entries (newest first)
        """
        try:
            redis_client = await get_redis()
            history_key = self._get_history_key(call_sid)
            history_data = await redis_client.lrange(history_key, 0, limit - 1)
            
            history = []
            for entry in history_data:
                try:
                    history.append(json.loads(entry))
                except json.JSONDecodeError:
                    logger.warning(f"[{call_sid}] Invalid history entry: {entry}")
            
            return history
            
        except Exception as e:
            logger.error(f"[{call_sid}] Error retrieving history: {e}")
            return []
    
    async def initialize_hsm(self, call_sid: str, initial_state_name: str) -> None:
        """
        Initialize the HSM for a new conversation.
        
        Args:
            call_sid: Conversation identifier
            initial_state_name: Name of the initial state
        """
        # Clear any existing state
        await self.clear_state(call_sid)
        
        # Set the initial state path
        await self.set_state_path(call_sid, [initial_state_name])
        
        logger.info(f"[{call_sid}] Initialized HSM with state: {initial_state_name}")


# Global instance for easy access
hsm_state_store = HSMStateStore()