"""
Correlation ID utilities for request tracking.

This module provides utilities for generating, managing, and propagating
correlation IDs throughout the application for better observability.
"""

import uuid
from typing import Optional
from contextvars import ContextVar

# Context variable to store correlation ID for the current async context
correlation_id_context: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


def generate_correlation_id() -> str:
    """Generate a new correlation ID."""
    return str(uuid.uuid4())


def set_correlation_id(correlation_id: Optional[str]) -> None:
    """Set the correlation ID for the current context."""
    correlation_id_context.set(correlation_id)


def get_correlation_id() -> Optional[str]:
    """Get the correlation ID for the current context."""
    return correlation_id_context.get()


def get_or_create_correlation_id() -> str:
    """Get the current correlation ID or create a new one if none exists."""
    correlation_id = get_correlation_id()
    if not correlation_id:
        correlation_id = generate_correlation_id()
        set_correlation_id(correlation_id)
    return correlation_id