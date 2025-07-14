"""
Circuit Breaker Implementation for OpenAI API Dependencies.

This module implements a circuit breaker pattern to protect against cascading
failures when the OpenAI API is unavailable, providing graceful degradation
to a static fallback mode.
"""

import asyncio
import time
import logging
from enum import Enum
from typing import Optional, Callable, Any, Dict
from dataclasses import dataclass
from threading import Lock

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit open, failing fast
    HALF_OPEN = "half_open"  # Testing if service recovered

@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    failure_threshold: int = 5          # Failures before opening circuit
    recovery_timeout: int = 60          # Seconds before trying half-open
    success_threshold: int = 2          # Successes needed to close circuit
    timeout_threshold: float = 10.0     # Request timeout threshold
    monitor_window: int = 300           # Window for tracking failures (5 min)

class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""
    pass

class OpenAICircuitBreaker:
    """
    Circuit breaker specifically designed for OpenAI API calls.
    
    Monitors OpenAI API health and switches to static fallback mode
    when the service is unavailable or experiencing issues.
    """
    
    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_state_change = time.time()
        self._lock = Lock()
        
        # Track recent failures for sliding window
        self.recent_failures = []
        
        logger.info(f"Circuit breaker initialized with config: {self.config}")
    
    def _clean_old_failures(self):
        """Remove failures outside the monitoring window."""
        current_time = time.time()
        cutoff_time = current_time - self.config.monitor_window
        self.recent_failures = [
            failure_time for failure_time in self.recent_failures
            if failure_time > cutoff_time
        ]
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt to reset from OPEN to HALF_OPEN."""
        if self.state != CircuitState.OPEN:
            return False
        
        if self.last_failure_time is None:
            return False
        
        time_since_failure = time.time() - self.last_failure_time
        return time_since_failure >= self.config.recovery_timeout
    
    def _record_success(self):
        """Record a successful operation."""
        with self._lock:
            self.success_count += 1
            
            if self.state == CircuitState.HALF_OPEN:
                if self.success_count >= self.config.success_threshold:
                    self._transition_to_closed()
            elif self.state == CircuitState.OPEN:
                # Direct transition from OPEN to CLOSED on success
                self._transition_to_closed()
    
    def _record_failure(self, error: Exception):
        """Record a failed operation."""
        current_time = time.time()
        
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = current_time
            self.recent_failures.append(current_time)
            self._clean_old_failures()
            
            # Check if we should open the circuit
            if self.state == CircuitState.CLOSED:
                if len(self.recent_failures) >= self.config.failure_threshold:
                    self._transition_to_open()
            elif self.state == CircuitState.HALF_OPEN:
                # Any failure in half-open state goes back to open
                self._transition_to_open()
        
        logger.warning(f"Circuit breaker recorded failure: {error}")
    
    def _transition_to_open(self):
        """Transition circuit to OPEN state."""
        logger.critical("🚨 CIRCUIT BREAKER OPENED - OpenAI API unavailable, switching to static fallback mode")
        old_state = self.state.value
        self.state = CircuitState.OPEN
        self.last_state_change = time.time()
        self.success_count = 0
        
        # Trigger critical alert
        asyncio.create_task(self._send_circuit_breaker_alert("OPEN", old_state))
    
    def _transition_to_half_open(self):
        """Transition circuit to HALF_OPEN state."""
        logger.warning("🔄 CIRCUIT BREAKER HALF-OPEN - Testing OpenAI API recovery")
        self.state = CircuitState.HALF_OPEN
        self.last_state_change = time.time()
        self.success_count = 0
    
    def _transition_to_closed(self):
        """Transition circuit to CLOSED state."""
        logger.info("✅ CIRCUIT BREAKER CLOSED - OpenAI API recovered, resuming normal operation")
        old_state = self.state.value
        self.state = CircuitState.CLOSED
        self.last_state_change = time.time()
        self.failure_count = 0
        self.recent_failures.clear()
        self.success_count = 0
        
        # Trigger recovery alert
        if old_state != "closed":
            asyncio.create_task(self._send_circuit_breaker_alert("CLOSED", old_state))
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function through the circuit breaker.
        
        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerError: When circuit is open
        """
        # Check if we should attempt reset
        if self._should_attempt_reset():
            with self._lock:
                if self.state == CircuitState.OPEN:
                    self._transition_to_half_open()
        
        # Fast fail if circuit is open
        if self.state == CircuitState.OPEN:
            raise CircuitBreakerError("Circuit breaker is OPEN - OpenAI API unavailable")
        
        try:
            # Execute the function with timeout monitoring
            start_time = time.time()
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            
            # Check for slow responses (potential service degradation)
            if duration > self.config.timeout_threshold:
                logger.warning(f"OpenAI API slow response: {duration:.2f}s")
                # Don't record as failure, but log the concern
            
            self._record_success()
            return result
            
        except Exception as error:
            self._record_failure(error)
            raise
    
    @property
    def is_open(self) -> bool:
        """Check if circuit breaker is open."""
        return self.state == CircuitState.OPEN
    
    @property
    def status(self) -> Dict[str, Any]:
        """Get current circuit breaker status."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "recent_failures": len(self.recent_failures),
            "last_failure_time": self.last_failure_time,
            "last_state_change": self.last_state_change,
            "uptime_since_last_change": time.time() - self.last_state_change
        }
    
    async def _send_circuit_breaker_alert(self, new_state: str, old_state: str) -> None:
        """Send alert for circuit breaker state change."""
        try:
            # Import here to avoid circular imports
            from app.services.alerting import alert_circuit_breaker_open, alert_circuit_breaker_closed
            from app.utils.metrics_logger import log_circuit_breaker_state_change
            
            # Log metrics
            log_circuit_breaker_state_change(
                from_state=old_state,
                to_state=new_state,
                failure_count=self.failure_count
            )
            
            # Send appropriate alert
            metadata = {
                "old_state": old_state,
                "new_state": new_state,
                "failure_count": self.failure_count,
                "success_count": self.success_count,
                "recent_failures": len(self.recent_failures),
                "recovery_timeout": self.config.recovery_timeout,
                "failure_threshold": self.config.failure_threshold
            }
            
            if new_state == "OPEN":
                await alert_circuit_breaker_open(metadata)
            elif new_state == "CLOSED":
                await alert_circuit_breaker_closed(metadata)
                
        except Exception as e:
            logger.error(f"Failed to send circuit breaker alert: {e}")

# Global circuit breaker instance
_circuit_breaker: Optional[OpenAICircuitBreaker] = None

def get_circuit_breaker() -> OpenAICircuitBreaker:
    """Get or create the global circuit breaker instance."""
    global _circuit_breaker
    if _circuit_breaker is None:
        # Load configuration from settings
        from app.config import settings
        config = CircuitBreakerConfig(
            failure_threshold=settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            recovery_timeout=settings.CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
            success_threshold=settings.CIRCUIT_BREAKER_SUCCESS_THRESHOLD
        )
        _circuit_breaker = OpenAICircuitBreaker(config)
    return _circuit_breaker

async def protected_openai_call(func: Callable, *args, **kwargs) -> Any:
    """
    Execute an OpenAI API call with circuit breaker protection.
    
    Args:
        func: The OpenAI API function to call
        *args: Function arguments
        **kwargs: Function keyword arguments
        
    Returns:
        API response
        
    Raises:
        CircuitBreakerError: When circuit is open
    """
    circuit_breaker = get_circuit_breaker()
    return await circuit_breaker.call(func, *args, **kwargs)