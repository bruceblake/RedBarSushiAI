"""
Enhanced logging with correlation ID support.

This module provides structured logging utilities that automatically
include correlation IDs and other contextual information.
"""

import logging
import json
from typing import Any, Dict, Optional
from datetime import datetime

from app.utils.correlation_id import get_correlation_id


class CorrelationIdFilter(logging.Filter):
    """Filter that adds correlation ID to log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation ID to the log record."""
        record.correlation_id = get_correlation_id() or "no-correlation-id"
        return True


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", "no-correlation-id"),
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ["name", "msg", "args", "created", "msecs", "relativeCreated", 
                          "levelname", "levelno", "pathname", "filename", "module", 
                          "lineno", "funcName", "exc_info", "exc_text", "stack_info",
                          "thread", "threadName", "processName", "process", "getMessage",
                          "correlation_id"]:
                log_data[key] = value
        
        return json.dumps(log_data)


class EnhancedLogger:
    """Enhanced logger that includes correlation IDs and structured data."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self._add_correlation_filter()
    
    def _add_correlation_filter(self):
        """Add correlation ID filter to logger."""
        # Check if filter already added
        for filter in self.logger.filters:
            if isinstance(filter, CorrelationIdFilter):
                return
        self.logger.addFilter(CorrelationIdFilter())
    
    def _add_context(self, **kwargs) -> Dict[str, Any]:
        """Add correlation ID and other context to extra fields."""
        extra = kwargs.get("extra", {})
        
        # Always include correlation ID
        correlation_id = get_correlation_id()
        if correlation_id:
            extra["correlation_id"] = correlation_id
        
        # Add call_sid if provided
        if "call_sid" in kwargs:
            extra["call_sid"] = kwargs.pop("call_sid")
        
        # Add order_id if provided
        if "order_id" in kwargs:
            extra["order_id"] = kwargs.pop("order_id")
            
        kwargs["extra"] = extra
        return kwargs
    
    def debug(self, msg: str, **kwargs):
        """Log debug message with context."""
        kwargs = self._add_context(**kwargs)
        self.logger.debug(msg, **kwargs)
    
    def info(self, msg: str, **kwargs):
        """Log info message with context."""
        kwargs = self._add_context(**kwargs)
        self.logger.info(msg, **kwargs)
    
    def warning(self, msg: str, **kwargs):
        """Log warning message with context."""
        kwargs = self._add_context(**kwargs)
        self.logger.warning(msg, **kwargs)
    
    def error(self, msg: str, **kwargs):
        """Log error message with context."""
        kwargs = self._add_context(**kwargs)
        self.logger.error(msg, **kwargs)
    
    def critical(self, msg: str, **kwargs):
        """Log critical message with context."""
        kwargs = self._add_context(**kwargs)
        self.logger.critical(msg, **kwargs)
    
    def exception(self, msg: str, **kwargs):
        """Log exception with context."""
        kwargs = self._add_context(**kwargs)
        self.logger.exception(msg, **kwargs)


def get_logger(name: str) -> EnhancedLogger:
    """Get an enhanced logger instance."""
    return EnhancedLogger(name)


def configure_logging(log_level: str = "INFO", use_json: bool = True):
    """
    Configure logging for the application.
    
    Args:
        log_level: The logging level
        use_json: Whether to use JSON formatting
    """
    # Normalize log level to uppercase
    if isinstance(log_level, str):
        log_level = log_level.upper()
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    
    # Set formatter
    if use_json:
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(
            "[%(asctime)s] [%(correlation_id)s] [%(levelname)s] [%(name)s] %(message)s"
        )
    
    console_handler.setFormatter(formatter)
    
    # Add correlation ID filter
    console_handler.addFilter(CorrelationIdFilter())
    
    # Add handler to root logger
    root_logger.addHandler(console_handler)
    
    # Reduce noise from external libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)