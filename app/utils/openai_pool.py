"""
OpenAI connection pool manager for faster API calls.
Pre-warms connections and reuses clients for better performance.
"""

import asyncio
import logging
from typing import Optional
import openai
from app.config import settings

logger = logging.getLogger(__name__)


class OpenAIConnectionPool:
    """Manages OpenAI client connections with pre-warming."""
    
    _instance: Optional['OpenAIConnectionPool'] = None
    _clients: list[openai.AsyncOpenAI] = []
    _initialized: bool = False
    _warm_tasks: list[asyncio.Task] = []
    _current_client_idx: int = 0
    _lock: asyncio.Lock = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def initialize(self):
        """Initialize multiple OpenAI clients and warm up connections."""
        if self._initialized:
            return
            
        logger.info("Initializing OpenAI connection pool with multiple clients...")
        self._lock = asyncio.Lock()
        
        # Create multiple clients for better concurrency
        num_clients = 3
        for i in range(num_clients):
            client = openai.AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                max_retries=1,  # Reduced for speed
                timeout=5.0     # Reduced timeout for faster responses
            )
            self._clients.append(client)
            
            # Start background warmup for each client
            warm_task = asyncio.create_task(self._warm_connection(client, i))
            self._warm_tasks.append(warm_task)
        
        self._initialized = True
        logger.info(f"OpenAI connection pool initialized with {num_clients} clients")
    
    async def _warm_connection(self, client: openai.AsyncOpenAI, idx: int):
        """Warm up a connection with a simple request."""
        try:
            logger.info(f"Warming up OpenAI connection {idx}...")
            await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5,
                temperature=0
            )
            logger.info(f"OpenAI connection {idx} warmed up successfully")
        except Exception as e:
            logger.error(f"Failed to warm up OpenAI connection {idx}: {e}")
    
    async def get_client(self) -> openai.AsyncOpenAI:
        """Get a warmed OpenAI client using round-robin."""
        if not self._initialized:
            await self.initialize()
        
        async with self._lock:
            # Get next client in round-robin fashion
            client = self._clients[self._current_client_idx]
            self._current_client_idx = (self._current_client_idx + 1) % len(self._clients)
            
            # Don't wait for warmup - just return the client
            return client
    
    async def close(self):
        """Close the connection pool."""
        for task in self._warm_tasks:
            if task and not task.done():
                task.cancel()
        self._warm_tasks.clear()
        self._clients.clear()
        self._initialized = False
        logger.info("OpenAI connection pool closed")


# Global instance
openai_pool = OpenAIConnectionPool()


async def get_openai_client() -> openai.AsyncOpenAI:
    """Get a warmed OpenAI client from the pool."""
    return await openai_pool.get_client()