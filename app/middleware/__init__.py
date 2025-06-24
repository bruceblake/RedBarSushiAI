"""
Middleware package for RedBarSushiAI.

Contains middleware for request processing, including correlation ID tracking.
"""

from app.middleware.correlation_id import CorrelationIdMiddleware

__all__ = ["CorrelationIdMiddleware"]