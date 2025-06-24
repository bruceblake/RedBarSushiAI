"""
Streaming utilities for handling chunked responses.

This module provides utilities for streaming text responses in chunks,
useful for real-time voice responses and progressive UI updates.
"""

import asyncio
import logging
from typing import AsyncGenerator, Optional, Callable, Awaitable
from enum import Enum

logger = logging.getLogger(__name__)


class ChunkType(Enum):
    """Types of chunks that can be streamed."""
    TEXT = "text"
    AUDIO = "audio"
    METADATA = "metadata"
    END = "end"


class StreamingChunker:
    """
    Utility for chunking text into streamable pieces.
    
    This class helps break down large text responses into smaller chunks
    that can be streamed progressively to improve perceived latency.
    """
    
    def __init__(self, chunk_size: int = 100, delimiter: str = " "):
        """
        Initialize the chunker.
        
        Args:
            chunk_size: Target size for each chunk (in characters)
            delimiter: Character to use for splitting (default: space)
        """
        self.chunk_size = chunk_size
        self.delimiter = delimiter
        self.buffer = ""
        
    def add_text(self, text: str) -> list[str]:
        """
        Add text and get any complete chunks.
        
        Args:
            text: Text to add to the buffer
            
        Returns:
            List of complete chunks ready to stream
        """
        self.buffer += text
        chunks = []
        
        # Split into chunks at delimiter boundaries
        while len(self.buffer) >= self.chunk_size:
            # Find the last delimiter within chunk_size
            chunk_end = self.buffer.rfind(self.delimiter, 0, self.chunk_size)
            
            if chunk_end == -1:
                # No delimiter found, use the whole chunk_size
                chunk_end = self.chunk_size
            else:
                # Include the delimiter
                chunk_end += len(self.delimiter)
            
            # Extract the chunk
            chunk = self.buffer[:chunk_end]
            chunks.append(chunk)
            self.buffer = self.buffer[chunk_end:]
        
        return chunks
    
    def flush(self) -> Optional[str]:
        """
        Get any remaining text in the buffer.
        
        Returns:
            Remaining text or None if buffer is empty
        """
        if self.buffer:
            chunk = self.buffer
            self.buffer = ""
            return chunk
        return None


class StreamingResponse:
    """
    Helper for creating streaming responses.
    
    This class manages the streaming of responses, handling chunking
    and providing an async generator interface.
    """
    
    def __init__(self, chunker: Optional[StreamingChunker] = None):
        """
        Initialize the streaming response.
        
        Args:
            chunker: Optional chunker to use (creates default if not provided)
        """
        self.chunker = chunker or StreamingChunker()
        self._queue = asyncio.Queue()
        self._finished = False
        
    async def add_text(self, text: str):
        """Add text to be streamed."""
        chunks = self.chunker.add_text(text)
        for chunk in chunks:
            await self._queue.put((ChunkType.TEXT, chunk))
    
    async def add_metadata(self, metadata: dict):
        """Add metadata to the stream."""
        await self._queue.put((ChunkType.METADATA, metadata))
    
    async def finish(self):
        """Signal that streaming is complete."""
        # Flush any remaining text
        remaining = self.chunker.flush()
        if remaining:
            await self._queue.put((ChunkType.TEXT, remaining))
        
        # Add end marker
        await self._queue.put((ChunkType.END, None))
        self._finished = True
    
    async def stream(self) -> AsyncGenerator[tuple[ChunkType, any], None]:
        """
        Stream chunks as they become available.
        
        Yields:
            Tuples of (chunk_type, chunk_data)
        """
        while True:
            chunk_type, chunk_data = await self._queue.get()
            
            if chunk_type == ChunkType.END:
                break
                
            yield chunk_type, chunk_data


class StreamProcessor:
    """
    Process streaming responses with callbacks.
    
    This class provides a way to process streaming responses with
    different callbacks for different chunk types.
    """
    
    def __init__(self):
        """Initialize the processor."""
        self.handlers = {}
        
    def on_text(self, handler: Callable[[str], Awaitable[None]]):
        """Register handler for text chunks."""
        self.handlers[ChunkType.TEXT] = handler
        
    def on_metadata(self, handler: Callable[[dict], Awaitable[None]]):
        """Register handler for metadata chunks."""
        self.handlers[ChunkType.METADATA] = handler
        
    def on_end(self, handler: Callable[[], Awaitable[None]]):
        """Register handler for stream end."""
        self.handlers[ChunkType.END] = handler
        
    async def process(self, stream: AsyncGenerator[tuple[ChunkType, any], None]):
        """
        Process a stream with registered handlers.
        
        Args:
            stream: Async generator yielding (chunk_type, chunk_data) tuples
        """
        async for chunk_type, chunk_data in stream:
            handler = self.handlers.get(chunk_type)
            if handler:
                if chunk_type == ChunkType.END:
                    await handler()
                else:
                    await handler(chunk_data)
            else:
                logger.debug(f"No handler for chunk type: {chunk_type}")


async def stream_text_progressively(
    text: str,
    callback: Callable[[str, bool], Awaitable[None]],
    chunk_size: int = 100,
    delay: float = 0.05
):
    """
    Stream text progressively with a callback.
    
    This is a convenience function for streaming text in chunks with
    a configurable delay between chunks to simulate natural speech.
    
    Args:
        text: The text to stream
        callback: Async function called with (chunk, is_last)
        chunk_size: Size of each chunk
        delay: Delay between chunks in seconds
    """
    chunker = StreamingChunker(chunk_size=chunk_size)
    chunks = chunker.add_text(text)
    
    # Add any remaining text
    remaining = chunker.flush()
    if remaining:
        chunks.append(remaining)
    
    # Stream chunks with delay
    for i, chunk in enumerate(chunks):
        is_last = (i == len(chunks) - 1)
        await callback(chunk, is_last)
        
        if not is_last and delay > 0:
            await asyncio.sleep(delay)