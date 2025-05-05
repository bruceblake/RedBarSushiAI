"""
Agent-specific monitoring utilities for RedBarSushiAI.
This module provides specialized monitoring for the OpenAI Agents SDK integration.
"""

import os
import time
import logging
import json
from typing import Dict, List, Any, Optional, Union, Callable
from datetime import datetime

from app.utils.monitoring import (
    log_with_context, 
    increment_counter, 
    record_histogram, 
    record_gauge,
    time_function,
    AgentMetrics,
    start_trace,
    end_trace,
    get_current_trace_id
)

# Configure logging
logger = logging.getLogger(__name__)

# Dictionary to store agent metrics by agent_id
_agent_metrics = {}

def get_agent_metrics(agent_name: str) -> AgentMetrics:
    """
    Get or create metrics for an agent.
    
    Args:
        agent_name: The name of the agent
        
    Returns:
        AgentMetrics instance for the agent
    """
    if agent_name not in _agent_metrics:
        _agent_metrics[agent_name] = AgentMetrics(agent_name)
    
    return _agent_metrics[agent_name]

def log_agent_call(
    agent_name: str,
    call_sid: str,
    thread_id: str,
    message: str,
    duration_ms: float = None,
    success: bool = True,
    context: Dict[str, Any] = None
) -> None:
    """
    Log an agent call with details for monitoring.
    
    Args:
        agent_name: The name of the agent
        call_sid: Twilio Call SID
        thread_id: OpenAI thread ID
        message: Log message
        duration_ms: Optional duration in milliseconds
        success: Whether the call was successful
        context: Additional context dictionary
    """
    if context is None:
        context = {}
    
    # Add call details to context
    context.update({
        "agent_name": agent_name,
        "call_sid": call_sid,
        "thread_id": thread_id,
        "success": success
    })
    
    # Add duration if provided
    if duration_ms is not None:
        context["duration_ms"] = duration_ms
        
        # Record metrics
        metrics = get_agent_metrics(agent_name)
        metrics.record_latency(duration_ms)
    
    # Log with the enhanced context
    log_level = "info" if success else "warning"
    log_with_context(log_level, message, context)
    
    # Record metrics
    metrics = get_agent_metrics(agent_name)
    metrics.increment_calls()
    metrics.record_success(success)

def log_tool_call(
    agent_name: str,
    tool_name: str,
    arguments: Dict[str, Any],
    result: Any,
    duration_ms: float,
    success: bool = True,
    context: Dict[str, Any] = None
) -> None:
    """
    Log a tool call with details for monitoring.
    
    Args:
        agent_name: The name of the agent
        tool_name: The name of the tool
        arguments: Tool arguments
        result: Tool result
        duration_ms: Duration in milliseconds
        success: Whether the call was successful
        context: Additional context dictionary
    """
    if context is None:
        context = {}
    
    # Add tool call details to context
    context.update({
        "agent_name": agent_name,
        "tool_name": tool_name,
        "arguments": arguments,
        "duration_ms": duration_ms,
        "success": success
    })
    
    # Sanitize result for logging
    if isinstance(result, dict):
        # Remove potentially sensitive or verbose fields
        sanitized_result = result.copy()
        for key in ["content", "full_response", "raw_response", "response_text"]:
            if key in sanitized_result and isinstance(sanitized_result[key], str) and len(sanitized_result[key]) > 100:
                sanitized_result[key] = f"{sanitized_result[key][:100]}... [truncated]"
        context["result"] = sanitized_result
    else:
        # Don't log the full result if it's not a dict
        context["result_type"] = type(result).__name__
    
    # Log with the enhanced context
    log_level = "info" if success else "warning"
    log_with_context(log_level, f"Tool call: {tool_name}", context)
    
    # Record metrics
    metrics = get_agent_metrics(agent_name)
    metrics.increment_calls(tool_name)
    metrics.record_latency(duration_ms, tool_name)
    metrics.record_success(success, tool_name)

def tool_monitoring(agent_name: str, tool_name: str) -> Callable:
    """
    Decorator to monitor a tool function.
    
    Args:
        agent_name: The name of the agent
        tool_name: The name of the tool
        
    Returns:
        Decorator function
    """
    def decorator(func):
        import functools
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            result = None
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                end_time = time.time()
                duration_ms = (end_time - start_time) * 1000
                
                # Extract arguments for logging
                # Skip self argument for class methods
                call_args = {}
                if args:
                    # If it's a method of a class, skip the first argument (self)
                    if hasattr(func, "__self__") or (args and hasattr(args[0], func.__name__)):
                        non_self_args = args[1:]
                    else:
                        non_self_args = args
                    
                    # Combine positional args with their parameter names
                    import inspect
                    sig = inspect.signature(func)
                    params = list(sig.parameters.keys())
                    
                    # Skip self parameter if it's a method
                    if params and params[0] == "self":
                        params = params[1:]
                    
                    # Map positional args to parameter names where possible
                    for i, arg in enumerate(non_self_args):
                        if i < len(params):
                            call_args[params[i]] = arg
                        else:
                            call_args[f"arg{i}"] = arg
                
                # Add keyword arguments
                call_args.update(kwargs)
                
                # Log the tool call
                try:
                    log_tool_call(
                        agent_name=agent_name,
                        tool_name=tool_name,
                        arguments=call_args,
                        result=result,
                        duration_ms=duration_ms,
                        success=success
                    )
                except Exception as log_error:
                    logger.error(f"Error logging tool call: {str(log_error)}")
        
        return wrapper
    
    return decorator

def log_agents_sdk_request(
    call_sid: str,
    endpoint: str,
    method: str,
    request_data: Dict[str, Any],
    response_code: int,
    duration_ms: float,
    context: Dict[str, Any] = None
) -> None:
    """
    Log an Agents SDK API request for monitoring.
    
    Args:
        call_sid: Twilio Call SID
        endpoint: API endpoint
        method: HTTP method
        request_data: Request data
        response_code: HTTP response code
        duration_ms: Duration in milliseconds
        context: Additional context dictionary
    """
    if context is None:
        context = {}
    
    # Add request details to context
    context.update({
        "call_sid": call_sid,
        "endpoint": endpoint,
        "method": method,
        "request_data": request_data,
        "response_code": response_code,
        "duration_ms": duration_ms
    })
    
    # Determine log level based on response code
    if response_code >= 500:
        log_level = "error"
    elif response_code >= 400:
        log_level = "warning"
    else:
        log_level = "info"
    
    # Log with the enhanced context
    log_with_context(log_level, f"Agents SDK API: {method} {endpoint}", context)
    
    # Record metrics
    increment_counter(f"agents_sdk.api.{endpoint}.{method}.{response_code}")
    record_histogram(f"agents_sdk.api.{endpoint}.{method}.duration_ms", duration_ms)

def api_monitoring(func=None, endpoint=None):
    """
    Decorator to monitor API requests.
    
    Args:
        func: The function to decorate
        endpoint: Optional endpoint name (defaults to function name)
        
    Returns:
        Decorated function
    """
    def decorator(func):
        import functools
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            # Extract call SID from request
            call_sid = None
            request_data = {}
            
            try:
                from flask import request
                call_sid = request.values.get("CallSid")
                request_data = {
                    "form": dict(request.form),
                    "args": dict(request.args)
                }
            except:
                pass
            
            # Call the original function
            try:
                response = func(*args, **kwargs)
                response_code = response.status_code if hasattr(response, "status_code") else 200
            except Exception as e:
                response_code = 500
                raise
            finally:
                end_time = time.time()
                duration_ms = (end_time - start_time) * 1000
                
                # Log the request
                try:
                    log_agents_sdk_request(
                        call_sid=call_sid or "unknown",
                        endpoint=endpoint or func.__name__,
                        method=request.method if 'request' in locals() else "UNKNOWN",
                        request_data=request_data,
                        response_code=response_code,
                        duration_ms=duration_ms
                    )
                except Exception as log_error:
                    logger.error(f"Error logging API request: {str(log_error)}")
            
            return response
        
        return wrapper
    
    # Handle both @api_monitoring and @api_monitoring(endpoint="...")
    if func is None:
        return decorator
    return decorator(func)

def log_voice_call_event(
    call_sid: str,
    event_type: str,
    details: Dict[str, Any] = None,
    duration_ms: Optional[float] = None
) -> None:
    """
    Log a voice call event for monitoring.
    
    Args:
        call_sid: Twilio Call SID
        event_type: Event type (start, end, silence, input, etc.)
        details: Additional event details
        duration_ms: Optional duration in milliseconds
    """
    if details is None:
        details = {}
    
    # Create context dictionary
    context = {
        "call_sid": call_sid,
        "event_type": event_type,
        **details
    }
    
    # Add duration if provided
    if duration_ms is not None:
        context["duration_ms"] = duration_ms
    
    # Log with context
    log_with_context("info", f"Voice call event: {event_type}", context)
    
    # Record metrics
    increment_counter(f"voice.call.event.{event_type}")
    if duration_ms is not None:
        record_histogram(f"voice.call.event.{event_type}.duration_ms", duration_ms)
    
    # Update active calls gauge for start/end events
    if event_type == "start":
        record_gauge("voice.call.active", 1, add=True)
    elif event_type == "end":
        record_gauge("voice.call.active", -1, add=True)

def trace_call(call_sid: str, description: str = None) -> Callable:
    """
    Decorator to trace a call through the system.
    
    Args:
        call_sid: Twilio Call SID
        description: Optional description
        
    Returns:
        Decorator function
    """
    def decorator(func):
        import functools
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Start trace
            trace_id = start_trace()
            
            # Add trace context
            trace_context = {
                "call_sid": call_sid,
                "trace_id": trace_id,
                "function": func.__name__
            }
            
            if description:
                trace_context["description"] = description
            
            log_with_context("info", f"Starting trace: {func.__name__}", trace_context)
            
            # Call the original function
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                # End trace
                trace_info = end_trace()
                if trace_info:
                    log_with_context(
                        "info", 
                        f"Ending trace: {func.__name__}", 
                        {**trace_context, "duration_ms": trace_info["duration_ms"]}
                    )
        
        return wrapper
    
    return decorator