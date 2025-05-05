"""
WebSocket-specific logging utilities for voice processing.

This module provides specialized logging functions and decorators for WebSocket
connections in the voice processing system, integrating with the enhanced logging system.
"""

import logging
import json
import time
import asyncio
import traceback
import uuid
from datetime import datetime
from functools import wraps

# Import the enhanced logging system
from app.utils.enhanced_logging import (
    log_websocket_event,
    LoggingTimer,
    get_session_logger
)

# Set up module logger
logger = logging.getLogger('websocket')

def get_connection_id():
    """Generate a unique identifier for a WebSocket connection."""
    return str(uuid.uuid4())[:8]

def log_connection_event(event, ws, call_sid=None, details=None):
    """
    Log a WebSocket connection lifecycle event.
    
    Args:
        event: The lifecycle event (connect, disconnect, error)
        ws: The WebSocket connection object
        call_sid: Optional Twilio Call SID for correlation
        details: Additional details about the event
    """
    conn_id = getattr(ws, '_log_id', get_connection_id())
    
    # Store the ID on the websocket object for future logging
    if not hasattr(ws, '_log_id'):
        setattr(ws, '_log_id', conn_id)
    
    # Create a timestamp
    timestamp = datetime.now().isoformat()
    
    # Format the event details
    event_details = {
        'connection_id': conn_id,
        'timestamp': timestamp,
        'event': event
    }
    
    # Add call SID if available
    if call_sid:
        event_details['call_sid'] = call_sid
    
    # Add any additional details
    if details:
        event_details.update(details)
    
    # Log the event with appropriate level
    if event == 'connect':
        logger.info(f"WebSocket connection established: {conn_id}", extra=event_details)
    elif event == 'disconnect':
        logger.info(f"WebSocket connection closed: {conn_id}", extra=event_details)
    elif event == 'error':
        logger.error(f"WebSocket connection error: {conn_id}", extra=event_details)
    else:
        logger.info(f"WebSocket event {event}: {conn_id}", extra=event_details)
    
    # Log to session-specific logger if call_sid is available
    if call_sid:
        session_logger = get_session_logger(call_sid)
        session_logger.info(f"WebSocket {event}: {conn_id}", extra=event_details)

async def log_websocket_message_flow(message, direction, ws, call_sid=None, message_type=None):
    """
    Log a WebSocket message with detailed formatting.
    
    Args:
        message: The message content (string, bytes, or dict)
        direction: The message direction ('SEND' or 'RECV')
        ws: The WebSocket connection object
        call_sid: Optional Twilio Call SID for correlation
        message_type: Type of message (e.g., 'media', 'transcript', 'tool_call')
    """
    # Get or generate the connection ID
    conn_id = getattr(ws, '_log_id', get_connection_id())
    if not hasattr(ws, '_log_id'):
        setattr(ws, '_log_id', conn_id)
    
    # Determine message format and extract type if not provided
    formatted_message = None
    detected_type = message_type
    
    if isinstance(message, str):
        try:
            # Try to parse as JSON
            data = json.loads(message)
            
            # Extract message type if not provided
            if not detected_type:
                detected_type = data.get('type', data.get('event', 'unknown'))
            
            # Handle binary data in the message
            if 'media' in data and 'payload' in data['media']:
                payload_size = len(data['media']['payload'])
                data['media']['payload'] = f"<{payload_size} bytes of data>"
            
            formatted_message = json.dumps(data)
        except json.JSONDecodeError:
            # Plain text message
            formatted_message = message
            if not detected_type:
                detected_type = 'text'
    elif isinstance(message, bytes):
        # Binary message
        formatted_message = f"<{len(message)} bytes of binary data>"
        if not detected_type:
            detected_type = 'binary'
    elif isinstance(message, dict):
        # Dict message (already parsed)
        if not detected_type:
            detected_type = message.get('type', message.get('event', 'unknown'))
        
        # Handle binary data in the message
        message_copy = message.copy()
        if 'media' in message_copy and 'payload' in message_copy['media']:
            payload_size = len(message_copy['media']['payload'])
            message_copy['media']['payload'] = f"<{payload_size} bytes of data>"
        
        formatted_message = json.dumps(message_copy)
    else:
        # Unknown message type
        formatted_message = str(message)
        if not detected_type:
            detected_type = 'unknown'
    
    # Log the message through the enhanced logging system
    extra_info = {
        'connection_id': conn_id,
        'message_size': len(formatted_message) if formatted_message else 0
    }
    
    # Use the enhanced logging utility
    log_websocket_event(
        event_type=detected_type,
        data=message,
        call_sid=call_sid,
        direction=direction,
        extra_info=extra_info
    )

def websocket_handler(func):
    """
    Decorator for WebSocket handler functions that adds logging and error handling.
    
    Args:
        func: The WebSocket handler function to decorate
    """
    @wraps(func)
    async def wrapper(ws, *args, **kwargs):
        # Extract or generate call_sid from args or kwargs
        call_sid = kwargs.get('call_sid') or kwargs.get('session_id')
        if not call_sid and args and isinstance(args[0], str):
            call_sid = args[0]
        
        # Generate a connection ID
        conn_id = get_connection_id()
        setattr(ws, '_log_id', conn_id)
        
        # Log connection establishment
        log_connection_event('connect', ws, call_sid)
        
        # Track connection stats
        start_time = time.time()
        messages_received = 0
        messages_sent = 0
        
        # Override the WebSocket's send method to log outgoing messages
        original_send = ws.send
        
        async def logged_send(message):
            nonlocal messages_sent
            try:
                await log_websocket_message_flow(message, 'SEND', ws, call_sid)
                messages_sent += 1
                return await original_send(message)
            except Exception as e:
                logger.error(f"Error sending WebSocket message: {e}", 
                             extra={'connection_id': conn_id, 'call_sid': call_sid})
                raise
        
        # Replace the send method with our logging version
        ws.send = logged_send
        
        # Override the WebSocket's receive method to log incoming messages
        original_receive = ws.receive
        
        async def logged_receive():
            nonlocal messages_received
            try:
                message = await original_receive()
                await log_websocket_message_flow(message, 'RECV', ws, call_sid)
                messages_received += 1
                return message
            except Exception as e:
                logger.error(f"Error receiving WebSocket message: {e}",
                             extra={'connection_id': conn_id, 'call_sid': call_sid})
                raise
        
        # Replace the receive method with our logging version
        ws.receive = logged_receive
        
        try:
            # Execute the handler function
            with LoggingTimer(logger, f"WebSocket handler {func.__name__}", extra={'connection_id': conn_id, 'call_sid': call_sid}):
                return await func(ws, *args, **kwargs)
        except Exception as e:
            # Log the error
            logger.error(f"Error in WebSocket handler {func.__name__}: {e}",
                         extra={'connection_id': conn_id, 'call_sid': call_sid})
            logger.error(traceback.format_exc())
            
            # Log connection error event
            log_connection_event('error', ws, call_sid, {'error': str(e), 'traceback': traceback.format_exc()})
            
            # Try to send an error message to the client
            try:
                error_message = {
                    'type': 'error',
                    'message': f"Internal error: {str(e)}",
                    'timestamp': time.time()
                }
                await ws.send(json.dumps(error_message))
            except:
                pass
            
            raise
        finally:
            # Calculate statistics
            duration = time.time() - start_time
            
            # Log disconnection
            log_connection_event('disconnect', ws, call_sid, {
                'duration': duration,
                'messages_received': messages_received,
                'messages_sent': messages_sent
            })
    
    return wrapper

def track_timing(name):
    """
    Decorator that tracks timing of async functions with logging.
    
    Args:
        name: The name of the operation being timed
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Try to extract call_sid from args or kwargs
            call_sid = kwargs.get('call_sid') or kwargs.get('session_id')
            if not call_sid:
                for arg in args:
                    if hasattr(arg, '_log_id'):
                        conn_id = getattr(arg, '_log_id')
                        break
            
            # Get appropriate logger
            log = logger
            
            # Start the timer
            start_time = time.time()
            
            # Log the start
            log.debug(f"Starting {name}...")
            
            try:
                # Call the function
                result = await func(*args, **kwargs)
                
                # Calculate duration
                duration = (time.time() - start_time) * 1000  # ms
                
                # Log the completion
                log.debug(f"Completed {name} in {duration:.2f}ms")
                
                return result
            except Exception as e:
                # Calculate duration
                duration = (time.time() - start_time) * 1000  # ms
                
                # Log the error
                log.error(f"Error in {name} after {duration:.2f}ms: {e}")
                log.error(traceback.format_exc())
                
                # Re-raise the exception
                raise
        
        return wrapper
    
    return decorator

# Stats tracking for WebSocket connections
class WebSocketStats:
    """Class for tracking WebSocket connection statistics."""
    
    def __init__(self):
        """Initialize the stats tracker."""
        self.active_connections = 0
        self.total_connections = 0
        self.connection_durations = []
        self.connection_errors = 0
        self.messages_received = 0
        self.messages_sent = 0
        self.active_sessions = set()
    
    def connection_opened(self, session_id=None):
        """Track a new connection."""
        self.active_connections += 1
        self.total_connections += 1
        if session_id:
            self.active_sessions.add(session_id)
    
    def connection_closed(self, duration, msgs_received=0, msgs_sent=0, session_id=None):
        """Track a closed connection."""
        self.active_connections = max(0, self.active_connections - 1)
        self.connection_durations.append(duration)
        self.messages_received += msgs_received
        self.messages_sent += msgs_sent
        if session_id and session_id in self.active_sessions:
            self.active_sessions.remove(session_id)
    
    def connection_error(self):
        """Track a connection error."""
        self.connection_errors += 1
    
    def get_stats(self):
        """Get the current statistics."""
        avg_duration = sum(self.connection_durations) / len(self.connection_durations) if self.connection_durations else 0
        
        return {
            'active_connections': self.active_connections,
            'total_connections': self.total_connections,
            'active_sessions': len(self.active_sessions),
            'avg_duration': avg_duration,
            'connection_errors': self.connection_errors,
            'messages_received': self.messages_received,
            'messages_sent': self.messages_sent
        }

# Create a global stats tracker
websocket_stats = WebSocketStats()

async def send_heartbeat(ws, session_id, interval=5.0):
    """
    Send periodic heartbeat messages to keep the WebSocket connection alive.
    
    Args:
        ws: WebSocket connection
        session_id: Session identifier
        interval: Time between heartbeats in seconds (default reduced to 5.0)
    """
    logger.info(f"Starting heartbeat task for session {session_id} with {interval}s interval")
    heartbeat_count = 0
    
    try:
        # Send an immediate heartbeat to establish the connection
        heartbeat_message = {
            "type": "heartbeat",
            "count": heartbeat_count,
            "session_id": session_id,
            "timestamp": time.time(),
            "message": "Initial connection heartbeat"
        }
        await ws.send(json.dumps(heartbeat_message))
        logger.info(f"Sent initial heartbeat to session {session_id}")
        
        while True:
            # Wait for the specified interval
            await asyncio.sleep(interval)
            
            # Increment counter
            heartbeat_count += 1
            
            # Send heartbeat message
            try:
                heartbeat_message = {
                    "type": "heartbeat",
                    "count": heartbeat_count,
                    "session_id": session_id,
                    "timestamp": time.time(),
                    "message": "Connection is alive"
                }
                await ws.send(json.dumps(heartbeat_message))
                
                # Log the heartbeat (but not too frequently to avoid log flooding)
                if heartbeat_count % 5 == 0:
                    logger.debug(f"Sent heartbeat #{heartbeat_count} to session {session_id}")
                else:
                    logger.debug(f"Heartbeat #{heartbeat_count} sent")
            except Exception as e:
                logger.error(f"Error sending heartbeat to session {session_id}: {e}")
                logger.error(traceback.format_exc())
                
                # Make second attempt to send heartbeat with different message format
                try:
                    retry_message = {
                        "event": "ping", 
                        "session_id": session_id,
                        "timestamp": time.time()
                    }
                    await ws.send(json.dumps(retry_message))
                    logger.debug(f"Retry heartbeat (format: ping) succeeded for session {session_id}")
                    continue  # Continue the loop if retry succeeded
                except Exception as retry_e:
                    logger.error(f"Retry heartbeat also failed: {retry_e}")
                    # If we can't send a heartbeat after retry, the connection might be dead - exit the loop
                    logger.warning(f"Connection to session {session_id} might be dead, stopping heartbeat task")
                    break
    except asyncio.CancelledError:
        logger.info(f"Heartbeat task for session {session_id} cancelled after {heartbeat_count} heartbeats")
    except Exception as e:
        logger.error(f"Error in heartbeat task for session {session_id}: {e}")
        logger.error(traceback.format_exc())