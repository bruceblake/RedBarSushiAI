"""
FastAPI dependency injection module.

This module contains dependencies for use with FastAPI's dependency injection system.
These dependencies provide access to key resources like database sessions, Redis,
and other shared services.
"""

import logging
from typing import Dict, Any  # Generator removed

from fastapi import WebSocket, WebSocketDisconnect


# Set up logging
logger = logging.getLogger(__name__)

# Common dependencies

# Re-export get_db for convenience
# db_dependency = get_db # Removed as unused

# Redis dependency
# redis_dependency = get_redis # Removed as unused

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
        Register a new WebSocket connection.
        Note: The connection must already be accepted with await websocket.accept()

        Args:
            websocket: The WebSocket connection to register (already accepted)
            call_sid: The unique identifier for the call
        """
        logger.info(f"[{call_sid}] Registering WebSocket connection")
        self.active_connections[call_sid] = websocket
        self.call_data[call_sid] = {"connected_at": None}

    async def disconnect(self, call_sid: str) -> None:
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

    # get_connection method removed

    # get_call_data method removed

    # update_call_data method removed

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
# connection_manager = ConnectionManager() # Removed as get_connection_manager is removed

# Return this as a dependency
# async def get_connection_manager() -> ConnectionManager: # Removed as unused
#     """
#     Dependency that provides the WebSocket connection manager.

#     Returns:
#         ConnectionManager: The WebSocket connection manager
#     """
#     return connection_manager
