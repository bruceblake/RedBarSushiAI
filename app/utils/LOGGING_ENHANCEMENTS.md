# Voice System Logging Enhancements

This document describes the comprehensive logging enhancements added to the voice system in RedBarSushiAI, with a focus on improving debugging capabilities.

## Overview

The logging system has been enhanced with detailed, structured logging that makes it easier to:

1. Track the flow of conversations through the agent orchestration system
2. Identify and diagnose issues with Redis connections and state management
3. Monitor agent transitions and state machine progression
4. Measure performance of key operations
5. Provide rich context for debugging

## Core Components Enhanced

### 1. Agent Orchestration (`agent_orchestration.py`)

Added a dedicated logging function with consistent formatting and context:

```python
def log_orchestration_event(level, message, context=None, call_sid=None, phase=None):
    """Enhanced logging for agent orchestration with consistent formatting."""
    prefix = "[ORCH"
    if phase:
        prefix += f"_{phase}"
    prefix += "]"
    
    full_message = f"{prefix} {message}"
    
    log_context = context or {}
    if call_sid:
        log_context["call_sid"] = call_sid
    
    # Add timestamp for performance tracking
    log_context["timestamp"] = time.time()
    
    if level == "debug":
        logger.debug(full_message, extra={"context": log_context})
    elif level == "info":
        logger.info(full_message, extra={"context": log_context})
    # ...
```

### 2. Component-Specific Logging

Each major component now includes detailed logging with phase-specific prefixes:

- **Agent Graph**: `[ORCH_GRAPH]` - Agent relationships, transitions, and selection logic
- **Slot Store**: `[ORCH_SLOT]` - State data storage and retrieval operations
- **FSM**: `[ORCH_FSM]` - State machine transitions and logic (to be enhanced further)
- **Model Escalation**: `[ORCH_ESCALATION]` - LLM escalation decisions and model switching
- **Initialization**: `[ORCH_INIT]` - Component initialization and Redis connection

### 3. Performance Tracking

Added detailed timing information at multiple levels:

- Entry/exit timing for major functions
- Operation-specific timing (e.g., Redis operations, slot retrieval, transition checks)
- Component initialization timing
- Total elapsed time for complex operations

### 4. Enhanced Error Handling

Improved error reporting with:

- Consistent error context structure
- Detailed traceback information
- Graceful fallbacks with appropriate logging
- Redis connection and operation error tracking

### 5. Data Privacy Features

Added safeguards for sensitive information:

- Redaction of sensitive fields (phone, payment info)
- Truncation of long values in logs
- Safe request/response summarization 

### 6. Operational Insights

Added logging for:

- Redis connection status and details
- State machine transitions with reasons
- Agent selection decisions and conditions that led to them
- Fallback mechanisms and their triggering conditions

## Example Log Patterns

### Redis Connection

```
[ORCH_INIT] Setting up Redis connection (Render environment: true) {"is_render": true}
[ORCH_INIT] Using Render-specific Redis URL: redis://red-ceqpb6rf1sgc739ut8e0:6379/0 {"redis_host": "red-ceqpb6rf1sgc739ut8e0", "redis_port": 6379, "redis_db": 0}
[ORCH_INIT] Successfully connected to Redis and received ping response in 0.123s {"ping_response": true, "ping_time_ms": 123.45}
```

### Agent Transition

```
[ORCH_GRAPH] Finding next agent from Frontline {"current_agent": "Frontline", "state_keys": ["slots", "last_confidence", "tool_results"]}
[ORCH_GRAPH] Found 3 possible transitions from Frontline {"transition_count": 3, "transitions": ["Frontline → Menu", "Frontline → Cart", "Frontline → Escalation"]}
[ORCH_GRAPH] Checking tool_result condition for tool 'intent_classifier', field 'intent', comparison 'eq': true {"from": "Frontline", "to": "Cart", "description": "Route to Cart Agent for order placement", "condition_type": "tool_result", "tool": "intent_classifier", "field": "intent", "expected_value": "place_order", "actual_value": "place_order"}
[ORCH_GRAPH] Selected transition: Frontline → Cart {"transition": {"index": 1, "from": "Frontline", "to": "Cart", "satisfied": true, "time_ms": 0.5, "description": "Route to Cart Agent for order placement"}, "elapsed_ms": 0.5}
```

### Slot Operations

```
[ORCH_SLOT] Setting slot 'current_state' for call CA123456 {"slot_name": "current_state", "call_sid": "CA123456", "value_type": "str", "value_summary": "ordering"}
[ORCH_SLOT] Storing in Redis key 'slot:CA123456:current_state' {"key": "slot:CA123456:current_state", "serialized_size": 12}
[ORCH_SLOT] Successfully stored slot in Redis in 0.003s {"elapsed_ms": 3.21}
```

### Model Escalation

```
[ORCH_ESCALATION] Checking if model escalation is needed {"confidence": 0.65, "current_model": "gpt-4.1-mini", "is_critical": true, "threshold": 0.7}
[ORCH_ESCALATION] Confidence 0.65 below threshold 0.8, can escalate to gpt-4o {"next_model": "gpt-4o", "current_index": 0}
[ORCH_ESCALATION] Escalation request prepared: gpt-4.1-mini → gpt-4o {"original_model": "gpt-4.1-mini", "escalation_model": "gpt-4o", "elapsed_ms": 1.23}
```

## Benefits for Debugging

1. **Structured Context**: Each log entry contains relevant context as JSON
2. **Consistent Formatting**: Standardized prefixes and message structures
3. **Performance Data**: Timing information at multiple levels of granularity
4. **Error Tracing**: Detailed error information with graceful fallbacks
5. **Call Tracking**: Consistent call_sid throughout the logs
6. **Phase Identification**: Clear indication of which component generated each log

## Further Areas for Enhancement

1. **FSM Prompt Templates**: Add detailed logging to the prompt template system
2. **Voice Controller**: Extend to the voice_controller.py module
3. **Realtime Audio**: Add comprehensive logging to the audio processing pipeline
4. **Centralized Configuration**: Add logging configuration options for different environments
5. **Log Rotation**: Ensure proper log rotation for production environments