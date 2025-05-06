"""
Connection management utilities for WebSocket connections in voice processing.

This module provides comprehensive connection management for WebSocket connections
with advanced stability features, keep-alive mechanisms, and connection recovery.
"""

import asyncio
import json
import logging
import random
import time
import traceback
from enum import Enum
from datetime import datetime

# Set up logger
logger = logging.getLogger(__name__)

# Global registry to prevent task garbage collection
if not hasattr(asyncio, "_connection_tasks"):
    asyncio._connection_tasks = set()

# Connection state tracking
class ConnectionState(Enum):
    """States for WebSocket connection lifecycle."""
    INITIALIZING = "initializing"
    CONNECTING = "connecting"
    ESTABLISHED = "established"
    AUTHENTICATED = "authenticated"
    STABLE = "stable"
    GREETING = "greeting"
    DEGRADED = "degraded"
    RECOVERING = "recovering"
    CLOSING = "closing"
    CLOSED = "closed"
    ERROR = "error"


class ConnectionManager:
    """
    Manages WebSocket connections with advanced stability features.
    
    This class provides tools for aggressive keep-alive scheduling,
    connection recovery, and health monitoring.
    """
    
    def __init__(self, session_id):
        """
        Initialize the connection manager.
        
        Args:
            session_id: Unique identifier for the WebSocket session
        """
        self.session_id = session_id
        self.state = ConnectionState.INITIALIZING
        self.connection_start_time = time.time()
        self.last_activity_time = time.time()
        self.last_sent_time = time.time()
        self.last_received_time = time.time()
        self.greeting_time = None
        self.messages_sent = 0
        self.messages_received = 0
        self.keep_alives_sent = 0
        self.connection_errors = 0
        self.recovery_attempts = 0
        self.connection_quality = 100.0  # 0-100 scale
        self.tasks = set()
        self.stream_sid = None
        self.call_sid = None
        self.media_count = 0
        self.audio_chunks_processed = 0
        self.health_log = []
        self.log_health_event("INIT", "Connection manager initialized")
        
    def log_health_event(self, event_type, message, data=None):
        """
        Log a connection health event.
        
        Args:
            event_type: Type of health event
            message: Event description
            data: Optional additional data
        """
        timestamp = time.time()
        
        # Calculate connection age
        age = timestamp - self.connection_start_time
        
        # Create health event record
        event = {
            "timestamp": timestamp,
            "time_str": datetime.utcfromtimestamp(timestamp).isoformat(),
            "age": age,
            "type": event_type,
            "message": message,
            "state": self.state.value if isinstance(self.state, ConnectionState) else str(self.state),
            "connection_quality": self.connection_quality
        }
        
        # Add optional data
        if data:
            event["data"] = data
            
        # Add to health log
        self.health_log.append(event)
        
        # Keep log at reasonable size by truncating old events if needed
        if len(self.health_log) > 1000:
            self.health_log = self.health_log[-1000:]
            
        # Log the event
        log_level = logging.INFO
        if event_type in ("ERROR", "DISCONNECT", "FAILURE"):
            log_level = logging.ERROR
        elif event_type in ("WARNING", "DEGRADED"):
            log_level = logging.WARNING
            
        logger.log(log_level, f"[WS:{self.session_id}] [{event_type}] {message} (age: {age:.2f}s, quality: {self.connection_quality:.1f})")
    
    def update_state(self, new_state, reason=None):
        """
        Update the connection state with logging.
        
        Args:
            new_state: The new ConnectionState
            reason: Optional reason for the state change
        """
        if new_state == self.state:
            return
            
        old_state = self.state
        self.state = new_state
        
        # Log state transition
        transition_message = f"State change: {old_state.value} → {new_state.value}"
        if reason:
            transition_message += f" (Reason: {reason})"
            
        self.log_health_event("STATE", transition_message, {
            "old_state": old_state.value if isinstance(old_state, ConnectionState) else str(old_state),
            "new_state": new_state.value if isinstance(new_state, ConnectionState) else str(new_state),
            "reason": reason
        })
        
        # Update connection quality based on state
        if new_state == ConnectionState.STABLE:
            self.connection_quality = min(100.0, self.connection_quality + 10.0)
        elif new_state == ConnectionState.DEGRADED:
            self.connection_quality = max(30.0, self.connection_quality - 20.0)
        elif new_state == ConnectionState.RECOVERING:
            self.connection_quality = max(10.0, self.connection_quality - 10.0)
        elif new_state == ConnectionState.ERROR:
            self.connection_quality = max(5.0, self.connection_quality - 50.0)
    
    def register_task(self, task, name=None):
        """
        Register a task with the connection manager and global registry.
        
        Args:
            task: The asyncio task to register
            name: Optional name for the task
        """
        # Add task to the connection's task set
        self.tasks.add(task)
        
        # Also add to global registry to prevent garbage collection
        asyncio._connection_tasks.add(task)
        
        # Set up cleanup callback
        task_name = name or f"task-{len(self.tasks)}"
        
        def cleanup_task(completed_task):
            try:
                # Remove from both registries
                self.tasks.discard(completed_task)
                asyncio._connection_tasks.discard(completed_task)
                
                # Log completion only if it's not cancelled
                if not completed_task.cancelled():
                    try:
                        # Try to get result to check for exceptions
                        completed_task.result()
                        self.log_health_event("TASK", f"Task '{task_name}' completed successfully")
                    except Exception as e:
                        self.log_health_event("ERROR", f"Task '{task_name}' failed: {str(e)}")
                else:
                    self.log_health_event("TASK", f"Task '{task_name}' was cancelled")
            except Exception as e:
                logger.error(f"[WS:{self.session_id}] Error in task cleanup: {str(e)}")
                
        task.add_done_callback(cleanup_task)
        
        # Log task registration
        self.log_health_event("TASK", f"Task '{task_name}' registered")
        return task
    
    def cleanup_tasks(self):
        """Cancel all tasks associated with this connection."""
        for task in list(self.tasks):
            try:
                if not task.done():
                    task.cancel()
            except Exception as e:
                logger.error(f"[WS:{self.session_id}] Error cancelling task: {str(e)}")
                
        # Clear the task set
        self.tasks.clear()
        self.log_health_event("CLEANUP", "All tasks cancelled")
    
    def record_message_sent(self, message_type=None):
        """
        Record a message sent through the WebSocket.
        
        Args:
            message_type: Optional type of the message
        """
        self.messages_sent += 1
        self.last_sent_time = time.time()
        self.last_activity_time = time.time()
        
        # Update connection quality (sending is a positive sign)
        self.connection_quality = min(100.0, self.connection_quality + 0.5)
        
        # Special handling for keep-alive messages
        if message_type in ("keep_alive", "heartbeat", "ping"):
            self.keep_alives_sent += 1
    
    def record_message_received(self, message_type=None):
        """
        Record a message received through the WebSocket.
        
        Args:
            message_type: Optional type of the message
        """
        self.messages_received += 1
        self.last_received_time = time.time()
        self.last_activity_time = time.time()
        
        # Update connection quality (receiving is a positive sign)
        self.connection_quality = min(100.0, self.connection_quality + 1.0)
    
    def assess_connection_health(self):
        """
        Assess the current health of the connection.
        
        Returns:
            Tuple of (health_score, issues)
        """
        current_time = time.time()
        issues = []
        
        # Calculate time since last activity
        time_since_sent = current_time - self.last_sent_time
        time_since_received = current_time - self.last_received_time
        time_since_activity = current_time - self.last_activity_time
        
        # Check for long periods of inactivity
        if time_since_activity > 30:
            issues.append(f"No activity for {time_since_activity:.1f}s")
            
        if time_since_received > 20:
            issues.append(f"No messages received for {time_since_received:.1f}s")
            
        # Consider connection quality
        if self.connection_quality < 50:
            issues.append(f"Low connection quality: {self.connection_quality:.1f}")
            
        # Check error count
        if self.connection_errors > 3:
            issues.append(f"Multiple connection errors: {self.connection_errors}")
            
        # Calculate health score (0-100)
        health_score = self.connection_quality
        
        # Reduce score based on inactivity
        if time_since_activity > 10:
            health_score -= min(30, time_since_activity)
            
        # Reduce score based on error count
        health_score -= (self.connection_errors * 10)
        
        # Ensure score is in range
        health_score = max(0, min(100, health_score))
        
        return health_score, issues
        
    def get_status_report(self):
        """
        Get a comprehensive status report of the connection.
        
        Returns:
            Dict with connection status details
        """
        current_time = time.time()
        connection_age = current_time - self.connection_start_time
        
        # Get connection health
        health_score, health_issues = self.assess_connection_health()
        
        # Calculate metrics for greeting phase
        post_greeting_age = None
        if self.greeting_time:
            post_greeting_age = current_time - self.greeting_time
        
        # Prepare status report
        status = {
            "session_id": self.session_id,
            "state": self.state.value if isinstance(self.state, ConnectionState) else str(self.state),
            "age": connection_age,
            "health_score": health_score,
            "health_issues": health_issues,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "keep_alives_sent": self.keep_alives_sent,
            "connection_quality": self.connection_quality,
            "connection_errors": self.connection_errors,
            "recovery_attempts": self.recovery_attempts,
            "call_sid": self.call_sid,
            "stream_sid": self.stream_sid,
            "media_count": self.media_count,
            "audio_chunks_processed": self.audio_chunks_processed,
            "greeting_detected": self.greeting_time is not None,
            "post_greeting_age": post_greeting_age,
            "time_since_sent": current_time - self.last_sent_time,
            "time_since_received": current_time - self.last_received_time,
            "time_since_activity": current_time - self.last_activity_time
        }
        
        return status
    
    def format_status_log(self):
        """Format connection status for logging."""
        status = self.get_status_report()
        
        # Format the status as a multi-line log message
        log_lines = [
            f"=== WebSocket Status Report: {self.session_id} ===",
            f"• State: {status['state']}",
            f"• Age: {status['age']:.2f}s",
            f"• Health: {status['health_score']:.1f}/100",
            f"• Messages: {status['messages_received']} received, {status['messages_sent']} sent",
            f"• Keep-alives: {status['keep_alives_sent']}",
            f"• Media chunks: {status['media_count']}",
            f"• Connection quality: {status['connection_quality']:.1f}",
            f"• Errors/Recoveries: {status['connection_errors']}/{status['recovery_attempts']}"
        ]
        
        # Add greeting info if available
        if status['greeting_detected']:
            log_lines.append(f"• Post-greeting age: {status['post_greeting_age']:.2f}s")
            
        # Add health issues if any
        if status['health_issues']:
            issues_str = "; ".join(status['health_issues'])
            log_lines.append(f"• Health issues: {issues_str}")
            
        return "\n".join(log_lines)


async def get_adaptive_ping_interval(connection_manager):
    """
    Calculate adaptive ping interval based on connection state and stability.
    
    Args:
        connection_manager: The ConnectionManager instance
        
    Returns:
        Float interval in seconds for next ping
    """
    # Base interval depends on connection state
    if connection_manager.state == ConnectionState.INITIALIZING:
        # Very aggressive pings during initialization
        return 0.2
    elif connection_manager.state == ConnectionState.CONNECTING:
        # Aggressive pings during connection
        return 0.5
    elif connection_manager.state == ConnectionState.ESTABLISHED:
        # Still aggressive but slightly less so
        return 1.0
    elif connection_manager.state == ConnectionState.GREETING:
        # Critical phase - very aggressive
        return 0.3
    elif connection_manager.state == ConnectionState.DEGRADED:
        # More frequent pings when connection quality is low
        return 1.0
    elif connection_manager.state == ConnectionState.RECOVERING:
        # Aggressive during recovery
        return 0.5
    elif connection_manager.state == ConnectionState.STABLE:
        # Can be less aggressive when stable
        base_interval = 3.0
        
        # Adjust based on connection quality
        if connection_manager.connection_quality > 90:
            # Excellent connection - longer intervals
            return base_interval + 1.0
        elif connection_manager.connection_quality < 70:
            # Lower quality - shorter intervals
            return max(1.0, base_interval - 1.0)
        else:
            # Normal quality
            return base_interval
    
    # Default interval
    return 2.0


async def maintain_connection(ws, connection_manager):
    """
    Maintain WebSocket connection with adaptive keep-alive messages.
    
    Args:
        ws: The WebSocket connection
        connection_manager: The ConnectionManager instance
    """
    try:
        connection_manager.log_health_event("MAINTAIN", "Starting connection maintenance task")
        
        # Initial burst of keep-alives
        # Start with extremely frequent keep-alives during critical initial phase
        initial_intervals = [
            0.2, 0.2, 0.2, 0.5, 0.5,    # First 5 keep-alives (200-500ms)
            1.0, 1.0, 1.0,              # Next 3 keep-alives (1s)
            2.0, 2.0                    # Next 2 keep-alives (2s)
        ]
        
        # Send initial burst
        for i, interval in enumerate(initial_intervals):
            # Send keep-alive
            try:
                keep_alive = {
                    "type": "keep_alive",
                    "count": i + 1,
                    "timestamp": time.time(),
                    "session_id": connection_manager.session_id,
                    "message": "Connection maintenance"
                }
                await ws.send(json.dumps(keep_alive))
                connection_manager.record_message_sent("keep_alive")
                
                # Log with reduced frequency to avoid spam
                if i % 3 == 0 or i == 0:
                    connection_manager.log_health_event(
                        "KEEP_ALIVE", 
                        f"Initial keep-alive #{i+1}/{len(initial_intervals)} sent"
                    )
                
                # Check if greeting was detected during this initial burst
                if connection_manager.greeting_time:
                    # If greeting detected, send additional frequent keep-alives
                    connection_manager.log_health_event(
                        "GREETING", 
                        "Greeting detected during initial keep-alive burst - sending additional stabilization"
                    )
                    
                    # Send 3 quick post-greeting keep-alives to stabilize connection
                    for j in range(3):
                        try:
                            stabilize_msg = {
                                "type": "keep_alive",
                                "count": f"post-greeting-{j+1}",
                                "timestamp": time.time(),
                                "session_id": connection_manager.session_id,
                                "message": "Post-greeting stabilization"
                            }
                            await ws.send(json.dumps(stabilize_msg))
                            connection_manager.record_message_sent("keep_alive")
                            await asyncio.sleep(0.1)  # Very short delay for post-greeting stabilization
                        except Exception as e:
                            connection_manager.log_health_event(
                                "ERROR", 
                                f"Error sending post-greeting stabilization: {str(e)}"
                            )
                            break
                
                # Wait for specified interval before next keep-alive
                await asyncio.sleep(interval)
                
            except Exception as e:
                connection_manager.log_health_event(
                    "ERROR", 
                    f"Error sending initial keep-alive #{i+1}: {str(e)}"
                )
                connection_manager.connection_errors += 1
                
                # If we can't send keep-alives, connection may be dead
                if connection_manager.connection_errors >= 3:
                    connection_manager.log_health_event(
                        "FAILURE", 
                        "Multiple keep-alive failures during initialization - connection may be dead"
                    )
                    connection_manager.update_state(ConnectionState.ERROR, "keep_alive_failure")
                    return
        
        # Transition to ongoing maintenance phase
        connection_manager.update_state(ConnectionState.STABLE, "initial_burst_complete")
        
        # Main keep-alive loop with adaptive intervals
        while True:
            try:
                # Get adaptive interval based on connection state
                interval = await get_adaptive_ping_interval(connection_manager)
                
                # Send keep-alive message
                keep_alive_count = connection_manager.keep_alives_sent + 1
                keep_alive = {
                    "type": "keep_alive",
                    "count": keep_alive_count,
                    "timestamp": time.time(),
                    "session_id": connection_manager.session_id,
                    "message": "Connection maintenance",
                    "connection_quality": connection_manager.connection_quality
                }
                
                await ws.send(json.dumps(keep_alive))
                connection_manager.record_message_sent("keep_alive")
                
                # Log keep-alives, but not too frequently
                if keep_alive_count % 5 == 0:
                    health_score, _ = connection_manager.assess_connection_health()
                    connection_manager.log_health_event(
                        "KEEP_ALIVE", 
                        f"Keep-alive #{keep_alive_count} sent (health: {health_score:.1f}/100, interval: {interval:.1f}s)"
                    )
                
                # If connection quality is low, try alternative keep-alive format
                if connection_manager.connection_quality < 70 and keep_alive_count % 3 == 0:
                    try:
                        # Send alternative format keep-alive
                        alt_keep_alive = {
                            "event": "ping",
                            "timestamp": time.time(),
                            "session_id": connection_manager.session_id
                        }
                        await ws.send(json.dumps(alt_keep_alive))
                        connection_manager.record_message_sent("ping")
                    except Exception as e:
                        connection_manager.log_health_event(
                            "WARNING", 
                            f"Failed to send alternative keep-alive: {str(e)}"
                        )
                
                # Wait for the adaptive interval
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                connection_manager.log_health_event("CANCEL", "Keep-alive task cancelled")
                break
                
            except Exception as e:
                connection_manager.log_health_event(
                    "ERROR", 
                    f"Error in keep-alive: {str(e)}"
                )
                connection_manager.connection_errors += 1
                
                # If multiple failures, connection may be degraded
                if connection_manager.connection_errors >= 2:
                    connection_manager.update_state(
                        ConnectionState.DEGRADED, 
                        f"keep_alive_errors: {connection_manager.connection_errors}"
                    )
                
                # If failures continue, try to recover or exit
                if connection_manager.connection_errors >= 5:
                    connection_manager.log_health_event(
                        "FAILURE", 
                        "Multiple keep-alive failures - attempting recovery"
                    )
                    
                    # Try recovery ping with different format
                    try:
                        recovery_msg = {
                            "event": "recovery",
                            "message": f"Connection recovery attempt",
                            "timestamp": time.time(),
                            "session_id": connection_manager.session_id
                        }
                        await ws.send(json.dumps(recovery_msg))
                        connection_manager.record_message_sent("recovery")
                        connection_manager.recovery_attempts += 1
                        connection_manager.update_state(ConnectionState.RECOVERING, "attempting_recovery")
                    except Exception as recovery_error:
                        connection_manager.log_health_event(
                            "FAILURE", 
                            f"Recovery attempt failed: {str(recovery_error)}"
                        )
                        connection_manager.update_state(ConnectionState.ERROR, "recovery_failed")
                        break
                
                # Shorter wait time after an error
                await asyncio.sleep(1.0)
                
    except asyncio.CancelledError:
        connection_manager.log_health_event("CANCEL", "Connection maintenance task cancelled")
    except Exception as e:
        connection_manager.log_health_event(
            "ERROR", 
            f"Unexpected error in connection maintenance: {str(e)}\n{traceback.format_exc()}"
        )
        connection_manager.update_state(ConnectionState.ERROR, f"unexpected_error: {str(e)}")


async def attempt_reconnection(ws, connection_manager, max_attempts=5):
    """
    Attempt to reconnect a broken WebSocket connection with exponential backoff.
    
    Args:
        ws: The original WebSocket connection object
        connection_manager: The ConnectionManager instance
        max_attempts: Maximum number of reconnection attempts
        
    Returns:
        New WebSocket connection if successful, None otherwise
    """
    connection_manager.update_state(ConnectionState.RECOVERING, "initiating_reconnection")
    connection_manager.log_health_event("RECONNECT", f"Starting reconnection attempts (max: {max_attempts})")
    
    # Base delay for exponential backoff
    base_delay = 0.5  # Start with 500ms
    
    for attempt in range(max_attempts):
        try:
            # Calculate backoff with jitter
            jitter = random.uniform(0.5, 1.5)  # 50% below to 50% above base
            delay = base_delay * (2 ** attempt) * jitter
            
            connection_manager.log_health_event(
                "RECONNECT", 
                f"Waiting {delay:.2f}s before reconnection attempt {attempt+1}/{max_attempts}"
            )
            
            # Wait before attempting reconnection
            await asyncio.sleep(delay)
            
            # This is a placeholder for actual reconnection logic
            # In a real implementation, you would create a new WebSocket connection
            # and restore the session state
            connection_manager.log_health_event(
                "RECONNECT", 
                f"Reconnection attempt {attempt+1}/{max_attempts} executed"
            )
            
            # If reconnection is successful, restore session state
            # For this example, we just simulate success or failure
            
            # Simulate a successful reconnection after a few attempts
            if attempt >= 1:  # Succeed after 2nd attempt
                connection_manager.log_health_event(
                    "RECONNECT", 
                    f"Reconnection successful on attempt {attempt+1}/{max_attempts}"
                )
                connection_manager.update_state(
                    ConnectionState.ESTABLISHED, 
                    f"reconnected: attempt {attempt+1}"
                )
                
                # Return the new connection (in this example, we just return the original)
                return ws
                
        except Exception as e:
            connection_manager.log_health_event(
                "ERROR", 
                f"Error during reconnection attempt {attempt+1}: {str(e)}"
            )
    
    # All attempts failed
    connection_manager.log_health_event(
        "FAILURE", 
        f"All {max_attempts} reconnection attempts failed"
    )
    connection_manager.update_state(ConnectionState.ERROR, "reconnection_failed")
    
    return None


async def monitor_connection_health(ws, connection_manager, interval=10.0):
    """
    Periodically monitor and log connection health.
    
    Args:
        ws: The WebSocket connection
        connection_manager: The ConnectionManager instance
        interval: Monitoring interval in seconds
    """
    try:
        connection_manager.log_health_event("MONITOR", "Starting connection health monitoring")
        
        while True:
            try:
                # Sleep first to allow initial connections to establish
                await asyncio.sleep(interval)
                
                # Get health assessment
                health_score, health_issues = connection_manager.assess_connection_health()
                
                # Log health status
                if health_issues:
                    issue_str = "; ".join(health_issues)
                    connection_manager.log_health_event(
                        "HEALTH", 
                        f"Connection health: {health_score:.1f}/100 - Issues: {issue_str}"
                    )
                elif connection_manager.messages_received % 10 == 0:
                    # Log health periodically even without issues
                    connection_manager.log_health_event(
                        "HEALTH", 
                        f"Connection health: {health_score:.1f}/100 - No issues detected"
                    )
                
                # If health is very poor, take action
                if health_score < 30 and connection_manager.state not in (
                    ConnectionState.RECOVERING, ConnectionState.ERROR, ConnectionState.CLOSING, ConnectionState.CLOSED
                ):
                    connection_manager.log_health_event(
                        "WARNING", 
                        f"Poor connection health detected: {health_score:.1f}/100"
                    )
                    
                    # Update state to degraded
                    connection_manager.update_state(ConnectionState.DEGRADED, "poor_health")
                    
                    # Send a status message to test connection
                    try:
                        status_msg = {
                            "type": "status",
                            "message": "Connection health check",
                            "timestamp": time.time(),
                            "session_id": connection_manager.session_id,
                            "health_score": health_score
                        }
                        await ws.send(json.dumps(status_msg))
                        connection_manager.record_message_sent("status")
                        connection_manager.log_health_event(
                            "ACTION", 
                            "Sent status message to test degraded connection"
                        )
                    except Exception as e:
                        connection_manager.log_health_event(
                            "ERROR", 
                            f"Failed to send status message on degraded connection: {str(e)}"
                        )
                
                # Log detailed status periodically
                if connection_manager.messages_received % 50 == 0 or health_score < 50:
                    status_log = connection_manager.format_status_log()
                    connection_manager.log_health_event("STATUS", status_log)
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                connection_manager.log_health_event(
                    "ERROR", 
                    f"Error in health monitoring: {str(e)}"
                )
                
                # Wait a bit and continue
                await asyncio.sleep(2.0)
                
    except asyncio.CancelledError:
        connection_manager.log_health_event("CANCEL", "Health monitoring task cancelled")
    except Exception as e:
        connection_manager.log_health_event(
            "ERROR", 
            f"Unexpected error in health monitoring: {str(e)}\n{traceback.format_exc()}"
        )