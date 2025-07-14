"""
Conversation-specific exceptions for RedBarSushiAI.

These exceptions are used to handle conversation state persistence failures
and ensure proper error handling in agent operations.
"""


class ConversationError(Exception):
    """Base exception for conversation-related errors."""
    pass


class RedisSaveError(ConversationError):
    """
    Raised when conversation data cannot be saved to Redis.
    
    This exception indicates that the conversation state could not be
    persisted to Redis, which could lead to split-brain scenarios
    where in-memory state diverges from persistent state.
    """
    
    def __init__(self, message: str, call_sid: str = None, operation: str = None):
        """
        Initialize Redis save error.
        
        Args:
            message: Error description
            call_sid: Call SID where error occurred
            operation: Operation that failed (e.g., 'save_conversation', 'update_cart')
        """
        super().__init__(message)
        self.call_sid = call_sid
        self.operation = operation


class ConversationLoadError(ConversationError):
    """
    Raised when conversation data cannot be loaded from storage.
    
    This exception indicates that conversation state could not be
    retrieved from the persistent store.
    """
    
    def __init__(self, message: str, call_sid: str = None):
        """
        Initialize conversation load error.
        
        Args:
            message: Error description
            call_sid: Call SID where error occurred
        """
        super().__init__(message)
        self.call_sid = call_sid


class StateInconsistencyError(ConversationError):
    """
    Raised when in-memory state is inconsistent with persistent state.
    
    This exception is used when state validation detects that
    the in-memory conversation state has diverged from what's
    stored in Redis.
    """
    
    def __init__(self, message: str, call_sid: str = None, memory_state=None, redis_state=None):
        """
        Initialize state inconsistency error.
        
        Args:
            message: Error description
            call_sid: Call SID where inconsistency detected
            memory_state: Current in-memory state
            redis_state: State from Redis
        """
        super().__init__(message)
        self.call_sid = call_sid
        self.memory_state = memory_state
        self.redis_state = redis_state


class ConversationRollbackError(ConversationError):
    """
    Raised when conversation state rollback fails.
    
    This exception indicates that after a Redis save failure,
    the system was unable to rollback in-memory changes to
    maintain consistency.
    """
    
    def __init__(self, message: str, call_sid: str = None, original_error=None):
        """
        Initialize rollback error.
        
        Args:
            message: Error description
            call_sid: Call SID where rollback failed
            original_error: The original error that triggered rollback
        """
        super().__init__(message)
        self.call_sid = call_sid
        self.original_error = original_error