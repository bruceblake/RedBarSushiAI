"""
FastAPI dependency injection module.

This module contains dependencies for use with FastAPI's dependency injection system.
These dependencies provide access to key resources like database sessions, Redis,
and other shared services.
"""

import logging
from typing import AsyncGenerator, Optional, Dict, Any, Generator

from fastapi import Depends, WebSocket, WebSocketDisconnect, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.db_async import get_db
from app.redis_async import get_redis
from app.config import settings

# Set up logging
logger = logging.getLogger(__name__)

# Common dependencies

# Re-export get_db for convenience
db_dependency = get_db

# Redis dependency
redis_dependency = get_redis

# WebSocket Connection Manager

class ConnectionManager:
    """
    WebSocket connection manager for handling multiple client connections.
    
    This class provides methods for managing WebSocket connections, including
    accepting new connections, disconnecting clients, and broadcasting messages.
    """
    
    def __init__(self):
        """Initialize the connection manager."""
        self.active_connections: Dict[str, WebSocket] = {}
        self.call_data: Dict[str, Dict[str, Any]] = {}
        
    async def connect(self, websocket: WebSocket, call_sid: str) -> None:
        """
        Accept a new WebSocket connection.
        
        Args:
            websocket: The WebSocket connection to accept
            call_sid: The unique identifier for the call
        """
        logger.info(f"[{call_sid}] Accepting WebSocket connection")
        await websocket.accept()
        self.active_connections[call_sid] = websocket
        self.call_data[call_sid] = {"connected_at": None}
        
    def disconnect(self, call_sid: str) -> None:
        """
        Register a disconnection for a call.
        
        Args:
            call_sid: The unique identifier for the call
        """
        if call_sid in self.active_connections:
            logger.info(f"[{call_sid}] Removing connection from manager")
            del self.active_connections[call_sid]
        if call_sid in self.call_data:
            del self.call_data[call_sid]
            
    async def send_json(self, call_sid: str, data: Dict[str, Any]) -> bool:
        """
        Send JSON data to a specific connection.
        
        Args:
            call_sid: The unique identifier for the call
            data: JSON-serializable data to send
            
        Returns:
            bool: True if successful, False otherwise
        """
        if call_sid not in self.active_connections:
            logger.warning(f"[{call_sid}] Attempted to send to non-existent connection")
            return False
            
        try:
            await self.active_connections[call_sid].send_json(data)
            return True
        except WebSocketDisconnect:
            logger.warning(f"[{call_sid}] WebSocket disconnected during send_json")
            self.disconnect(call_sid)
            return False
        except Exception as e:
            logger.error(f"[{call_sid}] Error sending JSON via WebSocket: {e}")
            return False
            
    async def send_text(self, call_sid: str, text: str) -> bool:
        """
        Send text data to a specific connection.
        
        Args:
            call_sid: The unique identifier for the call
            text: Text data to send
            
        Returns:
            bool: True if successful, False otherwise
        """
        if call_sid not in self.active_connections:
            logger.warning(f"[{call_sid}] Attempted to send to non-existent connection")
            return False
            
        try:
            await self.active_connections[call_sid].send_text(text)
            return True
        except WebSocketDisconnect:
            logger.warning(f"[{call_sid}] WebSocket disconnected during send_text")
            self.disconnect(call_sid)
            return False
        except Exception as e:
            logger.error(f"[{call_sid}] Error sending text via WebSocket: {e}")
            return False
            
    async def send_bytes(self, call_sid: str, data: bytes) -> bool:
        """
        Send binary data to a specific connection.
        
        Args:
            call_sid: The unique identifier for the call
            data: Binary data to send
            
        Returns:
            bool: True if successful, False otherwise
        """
        if call_sid not in self.active_connections:
            logger.warning(f"[{call_sid}] Attempted to send to non-existent connection")
            return False
            
        try:
            await self.active_connections[call_sid].send_bytes(data)
            return True
        except WebSocketDisconnect:
            logger.warning(f"[{call_sid}] WebSocket disconnected during send_bytes")
            self.disconnect(call_sid)
            return False
        except Exception as e:
            logger.error(f"[{call_sid}] Error sending bytes via WebSocket: {e}")
            return False
            
    def get_connection(self, call_sid: str) -> Optional[WebSocket]:
        """
        Get a WebSocket connection by call SID.
        
        Args:
            call_sid: The unique identifier for the call
            
        Returns:
            Optional[WebSocket]: The WebSocket connection or None if not found
        """
        return self.active_connections.get(call_sid)
        
    def get_call_data(self, call_sid: str) -> Dict[str, Any]:
        """
        Get data associated with a call.
        
        Args:
            call_sid: The unique identifier for the call
            
        Returns:
            Dict[str, Any]: Data associated with the call or empty dict if not found
        """
        return self.call_data.get(call_sid, {})
        
    def update_call_data(self, call_sid: str, data: Dict[str, Any]) -> None:
        """
        Update data associated with a call.
        
        Args:
            call_sid: The unique identifier for the call
            data: Data to update
        """
        if call_sid in self.call_data:
            self.call_data[call_sid].update(data)
        else:
            self.call_data[call_sid] = data
            
    def is_connected(self, call_sid: str) -> bool:
        """
        Check if a call is connected.
        
        Args:
            call_sid: The unique identifier for the call
            
        Returns:
            bool: True if connected, False otherwise
        """
        return call_sid in self.active_connections

# Create a singleton instance
connection_manager = ConnectionManager()

# Return this as a dependency
async def get_connection_manager() -> ConnectionManager:
    """
    Dependency that provides the WebSocket connection manager.
    
    Returns:
        ConnectionManager: The WebSocket connection manager
    """
    return connection_manager