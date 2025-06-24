"""
Centralized circuit breaker service for external API resilience.

This module provides circuit breaker protection for all external service
calls, preventing cascading failures and improving system resilience.
"""

import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from enum import Enum

from app.config import settings
from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, rejecting calls
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""
    def __init__(self, service_name: str, message: str = None):
        self.service_name = service_name
        self.message = message or f"Circuit breaker is open for {service_name}"
        super().__init__(self.message)


class ServiceCircuitBreaker:
    """
    Circuit breaker implementation for a single service.
    
    Tracks failures and prevents calls to failing services.
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        """
        Initialize a circuit breaker.
        
        Args:
            name: Service name
            failure_threshold: Number of failures before opening
            recovery_timeout: Seconds before attempting recovery
            expected_exception: Exception type to catch
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        # State tracking
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._last_success_time: Optional[datetime] = None
        
        # Listeners
        self._on_open_callbacks: list[Callable] = []
        self._on_close_callbacks: list[Callable] = []
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        # Check if we should transition from OPEN to HALF_OPEN
        if self._state == CircuitState.OPEN:
            if self._last_failure_time:
                time_since_failure = (datetime.now() - self._last_failure_time).total_seconds()
                if time_since_failure >= self.recovery_timeout:
                    logger.info(
                        f"Circuit breaker transitioning to HALF_OPEN",
                        service=self.name,
                        time_since_failure=time_since_failure
                    )
                    self._state = CircuitState.HALF_OPEN
        
        return self._state
    
    def call(self, func: Callable, *args, **kwargs):
        """
        Execute a function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerError: If circuit is open
            Exception: If function fails
        """
        if self.state == CircuitState.OPEN:
            logger.warning(
                f"Circuit breaker rejecting call",
                service=self.name,
                state=self._state.value
            )
            raise CircuitBreakerError(self.name)
        
        try:
            # Execute the function
            result = func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure(e)
            raise
    
    async def async_call(self, func: Callable, *args, **kwargs):
        """
        Execute an async function with circuit breaker protection.
        
        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerError: If circuit is open
            Exception: If function fails
        """
        if self.state == CircuitState.OPEN:
            logger.warning(
                f"Circuit breaker rejecting call",
                service=self.name,
                state=self._state.value
            )
            raise CircuitBreakerError(self.name)
        
        try:
            # Execute the async function
            result = await func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure(e)
            raise
    
    def _on_success(self):
        """Handle successful call."""
        self._success_count += 1
        self._last_success_time = datetime.now()
        
        # If in HALF_OPEN state, close the circuit
        if self._state == CircuitState.HALF_OPEN:
            logger.info(
                f"Circuit breaker closing after successful call",
                service=self.name
            )
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._notify_close()
    
    def _on_failure(self, exception: Exception):
        """Handle failed call."""
        self._failure_count += 1
        self._last_failure_time = datetime.now()
        
        logger.error(
            f"Circuit breaker recorded failure",
            service=self.name,
            failure_count=self._failure_count,
            threshold=self.failure_threshold,
            exception=str(exception)
        )
        
        # If in HALF_OPEN state, reopen immediately
        if self._state == CircuitState.HALF_OPEN:
            logger.warning(
                f"Circuit breaker reopening after failure in HALF_OPEN",
                service=self.name
            )
            self._state = CircuitState.OPEN
            self._notify_open(exception)
        
        # Check if we should open the circuit
        elif self._failure_count >= self.failure_threshold:
            logger.critical(
                f"Circuit breaker opening due to failures",
                service=self.name,
                failures=self._failure_count
            )
            self._state = CircuitState.OPEN
            self._notify_open(exception)
    
    def add_listener(self, on_open: Callable = None, on_close: Callable = None):
        """Add event listeners."""
        if on_open:
            self._on_open_callbacks.append(on_open)
        if on_close:
            self._on_close_callbacks.append(on_close)
    
    def _notify_open(self, exception: Exception):
        """Notify listeners that circuit opened."""
        for callback in self._on_open_callbacks:
            try:
                callback(self, exception)
            except Exception as e:
                logger.error(f"Error in circuit open callback: {e}")
    
    def _notify_close(self):
        """Notify listeners that circuit closed."""
        for callback in self._on_close_callbacks:
            try:
                callback(self)
            except Exception as e:
                logger.error(f"Error in circuit close callback: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure": self._last_failure_time.isoformat() if self._last_failure_time else None,
            "last_success": self._last_success_time.isoformat() if self._last_success_time else None
        }
    
    def reset(self):
        """Reset circuit breaker to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        logger.info(f"Circuit breaker manually reset", service=self.name)


class ServiceCircuitBreakers:
    """Centralized circuit breaker management for all external services."""
    
    def __init__(self):
        """Initialize circuit breakers for each service."""
        # OpenAI Circuit Breaker
        self.openai = ServiceCircuitBreaker(
            name="OpenAI",
            failure_threshold=getattr(settings, 'CIRCUIT_BREAKER_OPENAI_FAIL_MAX', 5),
            recovery_timeout=getattr(settings, 'CIRCUIT_BREAKER_OPENAI_RESET_TIMEOUT', 60),
            expected_exception=Exception  # Catch all OpenAI errors
        )
        
        # Twilio Circuit Breaker
        self.twilio = ServiceCircuitBreaker(
            name="Twilio",
            failure_threshold=getattr(settings, 'CIRCUIT_BREAKER_TWILIO_FAIL_MAX', 3),
            recovery_timeout=getattr(settings, 'CIRCUIT_BREAKER_TWILIO_RESET_TIMEOUT', 30),
            expected_exception=Exception
        )
        
        # Deliverect Circuit Breaker
        self.deliverect = ServiceCircuitBreaker(
            name="Deliverect",
            failure_threshold=getattr(settings, 'CIRCUIT_BREAKER_DELIVERECT_FAIL_MAX', 5),
            recovery_timeout=getattr(settings, 'CIRCUIT_BREAKER_DELIVERECT_RESET_TIMEOUT', 300),
            expected_exception=Exception
        )
        
        # Set up listeners
        self._setup_listeners()
    
    def _setup_listeners(self):
        """Set up circuit breaker event listeners."""
        for breaker in [self.openai, self.twilio, self.deliverect]:
            breaker.add_listener(
                on_open=self._on_circuit_open,
                on_close=self._on_circuit_close
            )
    
    def _on_circuit_open(self, breaker: ServiceCircuitBreaker, exception: Exception):
        """Handle circuit open events."""
        logger.critical(
            f"CIRCUIT BREAKER OPENED",
            service=breaker.name,
            exception=str(exception),
            stats=breaker.get_stats()
        )
        
        # Send alert via Celery task
        try:
            from app.tasks.notifications import send_circuit_breaker_alert
            send_circuit_breaker_alert.delay(
                service_name=breaker.name,
                error=str(exception),
                timestamp=datetime.now().isoformat()
            )
        except Exception as e:
            logger.error(f"Failed to send circuit breaker alert: {e}")
    
    def _on_circuit_close(self, breaker: ServiceCircuitBreaker):
        """Handle circuit close events."""
        logger.info(
            f"CIRCUIT BREAKER CLOSED",
            service=breaker.name,
            stats=breaker.get_stats()
        )
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all circuit breakers."""
        return {
            "openai": self.openai.get_stats(),
            "twilio": self.twilio.get_stats(),
            "deliverect": self.deliverect.get_stats(),
            "summary": {
                "healthy_services": sum(
                    1 for b in [self.openai, self.twilio, self.deliverect]
                    if b.state == CircuitState.CLOSED
                ),
                "degraded_services": sum(
                    1 for b in [self.openai, self.twilio, self.deliverect]
                    if b.state == CircuitState.HALF_OPEN
                ),
                "failed_services": sum(
                    1 for b in [self.openai, self.twilio, self.deliverect]
                    if b.state == CircuitState.OPEN
                )
            }
        }


# Global instance
circuit_breakers = ServiceCircuitBreakers()