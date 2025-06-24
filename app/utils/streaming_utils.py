"""
Streaming utilities for robust AI response streaming.

This module provides utilities for managing streaming responses
with proper error handling and state tracking.
"""

import asyncio
import logging
from typing import Optional, Callable, List, Dict, Any
from datetime import datetime, timedelta
from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)


class StreamingSession:
    """
    Manages a streaming session with state tracking and error recovery.
    """
    
    def __init__(self, session_id: str, stream_callback: Callable):
        self.session_id = session_id
        self.stream_callback = stream_callback
        self.chunks_sent: List[str] = []
        self.start_time = datetime.now()
        self.is_complete = False
        self.has_error = False
        self.error_message: Optional[str] = None
        self.total_chars_sent = 0
        
    async def send_chunk(self, chunk: str, is_final: bool = False) -> bool:
        """
        Send a chunk with error handling and tracking.
        
        Returns:
            True if chunk was sent successfully, False otherwise
        """
        try:
            await self.stream_callback(chunk, is_final)
            self.chunks_sent.append(chunk)
            self.total_chars_sent += len(chunk)
            
            if is_final:
                self.is_complete = True
                
            logger.debug(
                f"Sent chunk {len(self.chunks_sent)} ({len(chunk)} chars)",
                session_id=self.session_id
            )
            return True
            
        except Exception as e:
            logger.error(
                f"Failed to send chunk: {e}",
                session_id=self.session_id,
                exc_info=True
            )
            self.has_error = True
            self.error_message = str(e)
            return False
    
    async def complete_with_error(self, error_msg: str):
        """
        Complete the stream with an error message.
        """
        self.has_error = True
        self.error_message = error_msg
        
        # Try to send error indication
        try:
            # Send a completion message to properly close the stream
            error_chunk = " I apologize, but I encountered an issue. Please let me know if you'd like me to try again."
            await self.stream_callback(error_chunk, is_final=True)
        except Exception as e:
            logger.error(
                f"Failed to send error completion: {e}",
                session_id=self.session_id
            )
    
    def get_sent_content(self) -> str:
        """Get all successfully sent content."""
        return "".join(self.chunks_sent)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get streaming session statistics."""
        duration = (datetime.now() - self.start_time).total_seconds()
        return {
            "session_id": self.session_id,
            "chunks_sent": len(self.chunks_sent),
            "total_chars": self.total_chars_sent,
            "duration_seconds": duration,
            "is_complete": self.is_complete,
            "has_error": self.has_error,
            "error_message": self.error_message
        }


class StreamingErrorHandler:
    """
    Handles errors during streaming with retry logic and fallback strategies.
    """
    
    def __init__(self, max_retries: int = 2, retry_delay: float = 0.5):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
    async def handle_streaming_error(
        self,
        error: Exception,
        session: StreamingSession,
        fallback_response: Optional[str] = None
    ) -> bool:
        """
        Handle a streaming error with appropriate recovery.
        
        Returns:
            True if error was handled, False if unrecoverable
        """
        error_type = type(error).__name__
        
        logger.error(
            f"Streaming error: {error_type} - {str(error)}",
            session_id=session.session_id,
            stats=session.get_stats()
        )
        
        # Determine if error is recoverable
        is_recoverable = self._is_recoverable_error(error)
        
        if is_recoverable and session.chunks_sent:
            # If we've already sent some content, complete gracefully
            await session.complete_with_error(str(error))
            return True
            
        elif fallback_response:
            # Use fallback response if available
            try:
                await session.send_chunk(fallback_response, is_final=True)
                return True
            except Exception as e:
                logger.error(
                    f"Failed to send fallback response: {e}",
                    session_id=session.session_id
                )
                return False
        
        return False
    
    def _is_recoverable_error(self, error: Exception) -> bool:
        """Determine if an error is recoverable."""
        recoverable_errors = (
            asyncio.TimeoutError,
            ConnectionError,
            OSError,
        )
        return isinstance(error, recoverable_errors)


class ChunkBuffer:
    """
    Buffers and manages chunks for reliable delivery.
    """
    
    def __init__(self, max_buffer_size: int = 10):
        self.buffer: List[tuple[str, bool]] = []
        self.max_buffer_size = max_buffer_size
        self.sent_chunks: List[str] = []
        
    def add_chunk(self, chunk: str, is_final: bool = False):
        """Add a chunk to the buffer."""
        if len(self.buffer) >= self.max_buffer_size:
            # Remove oldest chunk if buffer is full
            self.buffer.pop(0)
        self.buffer.append((chunk, is_final))
        
    def mark_sent(self, chunk: str):
        """Mark a chunk as successfully sent."""
        self.sent_chunks.append(chunk)
        # Remove from buffer if present
        self.buffer = [(c, f) for c, f in self.buffer if c != chunk]
        
    def get_pending_chunks(self) -> List[tuple[str, bool]]:
        """Get all pending chunks."""
        return self.buffer.copy()
        
    def has_pending(self) -> bool:
        """Check if there are pending chunks."""
        return len(self.buffer) > 0