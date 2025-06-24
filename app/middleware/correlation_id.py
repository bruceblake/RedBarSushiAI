"""
Correlation ID middleware for FastAPI.

This middleware ensures every request has a correlation ID for tracking
through the entire request lifecycle.
"""

import logging
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.utils.correlation_id import (
    generate_correlation_id,
    set_correlation_id,
    get_correlation_id
)

logger = logging.getLogger(__name__)

# Standard headers for correlation IDs
CORRELATION_ID_HEADERS = [
    "X-Correlation-ID",
    "X-Request-ID",
    "X-Trace-ID"
]


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware to handle correlation IDs for request tracking."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and ensure it has a correlation ID."""
        # Try to get correlation ID from request headers
        correlation_id = None
        for header in CORRELATION_ID_HEADERS:
            correlation_id = request.headers.get(header)
            if correlation_id:
                break
        
        # Generate new ID if not provided
        if not correlation_id:
            correlation_id = generate_correlation_id()
            logger.debug(f"Generated new correlation ID: {correlation_id}")
        else:
            logger.debug(f"Using correlation ID from request: {correlation_id}")
        
        # Set correlation ID in context
        set_correlation_id(correlation_id)
        
        # Store in request state for easy access
        request.state.correlation_id = correlation_id
        
        # Process the request
        response = await call_next(request)
        
        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id
        
        return response