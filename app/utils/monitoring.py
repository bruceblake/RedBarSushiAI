"""
Monitoring and observability utilities for RedBarSushiAI.
This module provides tools for logging, metrics, and tracing to enable better observability.
"""

import os
import time
import logging
import json
import traceback
import functools
import threading
from typing import Dict, List, Any, Optional, Union, Callable
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

# Determine environment
IS_PROD = os.environ.get("FLASK_ENV") == "production"
IS_STAGING = os.environ.get("FLASK_ENV") == "staging" or os.environ.get("IS_STAGING") == "true"

# In-memory metrics storage for local development and testing
_metrics_store = {
    "counters": {},
    "timers": {},
    "gauges": {},
    "histograms": {}
}

# Thread-local storage for tracing
_thread_local = threading.local()

class AgentMetrics:
    """
    Metrics collection for agent operations.
    Captures counts, timing, and success rates for agent interactions.
    """
    
    def __init__(self, agent_name: str):
        """
        Initialize metrics for an agent.
        
        Args:
            agent_name: The name of the agent
        """
        self.agent_name = agent_name
        self.prefix = f"agent.{agent_name.lower().replace(' ', '_')}"
    
    def increment_calls(self, tool_name: Optional[str] = None):
        """
        Increment the count of agent calls.
        
        Args:
            tool_name: Optional tool name for specific tool metrics
        """
        if tool_name:
            metric_name = f"{self.prefix}.tool.{tool_name}.calls"
        else:
            metric_name = f"{self.prefix}.calls"
        
        increment_counter(metric_name)
    
    def record_latency(self, latency_ms: float, tool_name: Optional[str] = None):
        """
        Record the latency of an agent operation.
        
        Args:
            latency_ms: The latency in milliseconds
            tool_name: Optional tool name for specific tool metrics
        """
        if tool_name:
            metric_name = f"{self.prefix}.tool.{tool_name}.latency_ms"
        else:
            metric_name = f"{self.prefix}.latency_ms"
        
        record_histogram(metric_name, latency_ms)
    
    def record_success(self, success: bool, tool_name: Optional[str] = None):
        """
        Record the success or failure of an agent operation.
        
        Args:
            success: Whether the operation was successful
            tool_name: Optional tool name for specific tool metrics
        """
        result = "success" if success else "failure"
        
        if tool_name:
            metric_name = f"{self.prefix}.tool.{tool_name}.{result}"
        else:
            metric_name = f"{self.prefix}.{result}"
        
        increment_counter(metric_name)
    
    def time_operation(self, tool_name: Optional[str] = None) -> Callable:
        """
        Decorator to time an agent operation and record metrics.
        
        Args:
            tool_name: Optional tool name for specific tool metrics
            
        Returns:
            Decorator function
        """
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                success = True
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    success = False
                    raise
                finally:
                    end_time = time.time()
                    latency_ms = (end_time - start_time) * 1000
                    
                    # Record metrics
                    self.increment_calls(tool_name)
                    self.record_latency(latency_ms, tool_name)
                    self.record_success(success, tool_name)
            
            return wrapper
        
        return decorator

def start_trace(trace_id: Optional[str] = None) -> str:
    """
    Start a new trace or continue an existing one.
    
    Args:
        trace_id: Optional trace ID to continue an existing trace
        
    Returns:
        The trace ID
    """
    if not trace_id:
        trace_id = generate_trace_id()
    
    _thread_local.trace_id = trace_id
    _thread_local.span_id = generate_span_id()
    _thread_local.trace_start_time = time.time()
    
    return trace_id

def end_trace() -> Optional[Dict[str, Any]]:
    """
    End the current trace and return trace information.
    
    Returns:
        Trace information dictionary
    """
    if not hasattr(_thread_local, 'trace_id'):
        return None
    
    trace_info = {
        "trace_id": _thread_local.trace_id,
        "span_id": _thread_local.span_id,
        "duration_ms": (time.time() - _thread_local.trace_start_time) * 1000
    }
    
    # Clear thread-local storage
    delattr(_thread_local, 'trace_id')
    delattr(_thread_local, 'span_id')
    delattr(_thread_local, 'trace_start_time')
    
    return trace_info

def get_current_trace_id() -> Optional[str]:
    """
    Get the current trace ID.
    
    Returns:
        The current trace ID or None if no trace is active
    """
    return getattr(_thread_local, 'trace_id', None)

def generate_trace_id() -> str:
    """
    Generate a new trace ID.
    
    Returns:
        A unique trace ID
    """
    import uuid
    return f"trace-{uuid.uuid4()}"

def generate_span_id() -> str:
    """
    Generate a new span ID.
    
    Returns:
        A unique span ID
    """
    import uuid
    return f"span-{uuid.uuid4()}"

def log_with_context(
    level: str,
    message: str,
    context: Dict[str, Any] = None
) -> None:
    """
    Log a message with additional context.
    
    Args:
        level: The log level (info, warning, error, debug)
        message: The log message
        context: Additional context dictionary
    """
    if context is None:
        context = {}
    
    # Add trace context if available
    trace_id = get_current_trace_id()
    if trace_id:
        context["trace_id"] = trace_id
    
    # Add timestamp
    context["timestamp"] = datetime.now().isoformat()
    
    # Format log message with context
    log_data = {
        "message": message,
        "context": context
    }
    
    # Get the appropriate logger method
    log_method = getattr(logger, level.lower(), logger.info)
    
    # Log the message with context
    if IS_PROD or IS_STAGING:
        # In production/staging, log as JSON for easier parsing
        log_method(json.dumps(log_data))
    else:
        # In development, log in a more readable format
        log_method(f"{message} | Context: {json.dumps(context)}")

def increment_counter(name: str, value: int = 1, tags: Dict[str, str] = None) -> None:
    """
    Increment a counter metric.
    
    Args:
        name: The metric name
        value: The increment value
        tags: Optional metric tags
    """
    # In a real implementation, this would send to a metrics system
    # For now, just store in memory
    if name not in _metrics_store["counters"]:
        _metrics_store["counters"][name] = 0
    
    _metrics_store["counters"][name] += value
    
    # Log the metric for development
    if not (IS_PROD or IS_STAGING):
        logger.debug(f"METRIC | Counter {name} += {value} | Current: {_metrics_store['counters'][name]}")

def record_gauge(name: str, value: float, tags: Dict[str, str] = None) -> None:
    """
    Record a gauge metric.
    
    Args:
        name: The metric name
        value: The gauge value
        tags: Optional metric tags
    """
    # In a real implementation, this would send to a metrics system
    # For now, just store in memory
    _metrics_store["gauges"][name] = value
    
    # Log the metric for development
    if not (IS_PROD or IS_STAGING):
        logger.debug(f"METRIC | Gauge {name} = {value}")

def record_histogram(name: str, value: float, tags: Dict[str, str] = None) -> None:
    """
    Record a histogram metric.
    
    Args:
        name: The metric name
        value: The value to add to the histogram
        tags: Optional metric tags
    """
    # In a real implementation, this would send to a metrics system
    # For now, just append to a list
    if name not in _metrics_store["histograms"]:
        _metrics_store["histograms"][name] = []
    
    _metrics_store["histograms"][name].append(value)
    
    # Keep only recent values (last 100)
    if len(_metrics_store["histograms"][name]) > 100:
        _metrics_store["histograms"][name] = _metrics_store["histograms"][name][-100:]
    
    # Log the metric for development
    if not (IS_PROD or IS_STAGING):
        logger.debug(f"METRIC | Histogram {name} += {value}")

def time_function(name: str, tags: Dict[str, str] = None) -> Callable:
    """
    Decorator to time a function and record metrics.
    
    Args:
        name: The metric name
        tags: Optional metric tags
        
    Returns:
        Decorator function
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                end_time = time.time()
                duration_ms = (end_time - start_time) * 1000
                
                # Record the duration
                if name not in _metrics_store["timers"]:
                    _metrics_store["timers"][name] = []
                
                _metrics_store["timers"][name].append(duration_ms)
                
                # Keep only recent values (last 100)
                if len(_metrics_store["timers"][name]) > 100:
                    _metrics_store["timers"][name] = _metrics_store["timers"][name][-100:]
                
                # Record histogram for the duration
                record_histogram(f"{name}.duration_ms", duration_ms, tags)
                
                # Log the metric for development
                if not (IS_PROD or IS_STAGING):
                    logger.debug(f"METRIC | Timer {name} = {duration_ms:.2f}ms")
        
        return wrapper
    
    return decorator

def get_metrics_snapshot() -> Dict[str, Any]:
    """
    Get a snapshot of all metrics for monitoring dashboards.
    
    Returns:
        Dictionary with all metrics
    """
    # Calculate histogram stats
    histogram_stats = {}
    for name, values in _metrics_store["histograms"].items():
        if values:
            histogram_stats[name] = {
                "count": len(values),
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
                "recent": values[-10:]  # Last 10 values
            }
    
    # Calculate timer stats
    timer_stats = {}
    for name, values in _metrics_store["timers"].items():
        if values:
            timer_stats[name] = {
                "count": len(values),
                "min_ms": min(values),
                "max_ms": max(values),
                "avg_ms": sum(values) / len(values),
                "recent_ms": values[-10:]  # Last 10 values
            }
    
    # Return full snapshot
    return {
        "timestamp": datetime.now().isoformat(),
        "counters": _metrics_store["counters"].copy(),
        "gauges": _metrics_store["gauges"].copy(),
        "histograms": histogram_stats,
        "timers": timer_stats
    }

def setup_prometheus_metrics():
    """
    Set up Prometheus metrics integration.
    This should be called at application startup.
    """
    try:
        from prometheus_client import Counter, Gauge, Histogram, Summary
        
        # Define global metrics
        global api_request_count, api_request_latency, active_calls, agent_call_count, agent_call_latency
        
        # API metrics
        api_request_count = Counter(
            'redbarsushi_api_requests_total',
            'Count of API requests',
            ['endpoint', 'method', 'status']
        )
        
        api_request_latency = Histogram(
            'redbarsushi_api_request_duration_seconds', 
            'API request latency in seconds',
            ['endpoint', 'method'],
            buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)
        )
        
        # Call metrics
        active_calls = Gauge(
            'redbarsushi_active_calls',
            'Number of currently active calls'
        )
        
        # Agent metrics
        agent_call_count = Counter(
            'redbarsushi_agent_calls_total',
            'Count of agent calls',
            ['agent', 'tool', 'success']
        )
        
        agent_call_latency = Histogram(
            'redbarsushi_agent_call_duration_seconds',
            'Agent call latency in seconds',
            ['agent', 'tool'],
            buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 20, 30)
        )
        
        logger.info("Prometheus metrics initialized successfully")
        return True
    
    except ImportError:
        logger.warning("prometheus_client not installed, using in-memory metrics only")
        return False
    except Exception as e:
        logger.error(f"Failed to initialize Prometheus metrics: {str(e)}")
        return False

def log_exception(exc_info=None, context=None):
    """
    Log an exception with additional context.
    
    Args:
        exc_info: Exception info from sys.exc_info()
        context: Additional context dictionary
    """
    if exc_info is None:
        import sys
        exc_info = sys.exc_info()
    
    if context is None:
        context = {}
    
    exc_type, exc_value, exc_tb = exc_info
    
    # Extract exception details
    exception_details = {
        "type": exc_type.__name__ if exc_type else "Unknown",
        "message": str(exc_value) if exc_value else "No message",
        "traceback": traceback.format_exception(exc_type, exc_value, exc_tb) if exc_tb else []
    }
    
    # Add exception details to context
    context["exception"] = exception_details
    
    # Log the exception
    log_with_context("error", f"Exception: {exception_details['type']}: {exception_details['message']}", context)


# Initialize monitors
def init_monitoring(app=None):
    """
    Initialize all monitoring components.
    
    Args:
        app: Optional Flask app
    """
    # Set up Prometheus if available
    has_prometheus = setup_prometheus_metrics()
    
    # Create healthcheck endpoint if app is provided
    if app and has_prometheus:
        try:
            from prometheus_client import generate_latest
            
            @app.route('/metrics', methods=['GET'])
            def metrics():
                from flask import Response
                return Response(generate_latest(), mimetype='text/plain')
            
            logger.info("Prometheus metrics endpoint added at /metrics")
        except Exception as e:
            logger.error(f"Failed to create metrics endpoint: {str(e)}")
    
    # Log successful initialization
    logger.info(f"Monitoring initialized with Prometheus: {has_prometheus}")
    
    return has_prometheus