# Advanced Agentic Patterns for RedBarSushiAI

This document provides an overview of the advanced agentic patterns implemented in the RedBarSushiAI system, including sequential handoffs, background escalation, and state-machine slot filling.

## Overview

We've implemented several advanced agentic patterns to enhance the capabilities of the RedBarSushiAI system:

1. **Sequential Handoffs** - A directed acyclic graph (DAG) of agents for specialized tasks
2. **Background Escalation** - Dynamic model upgrading based on confidence levels
3. **State-Machine Slot Filling** - Robust authentication flow through a finite state machine

These patterns work together to create a more capable and robust voice ordering system that can handle complex conversations, authentication, and graceful fallbacks.

## Components

### 1. Agent Graph (`AgentGraph`)

The Agent Graph provides a structured way to orchestrate transitions between specialist agents:

- **Nodes** - Each node represents a specialist agent with its model and confidence threshold
- **Transitions** - Directed edges between nodes with conditional logic
- **State-based decisions** - Uses conversation state to determine when to hand off

```python
graph = AgentGraph()
graph.add_node(
    name="Frontline",
    model="gpt-4.1-mini",
    description="Primary voice agent"
)
graph.add_transition(
    from_agent="Frontline", 
    to_agent="Menu",
    condition={
        "type": "tool_result",
        "tool": "intent_classifier",
        "field": "intent",
        "value": "menu_inquiry"
    }
)
```

### 2. FSM Orchestrator (`FSMOrchestrator`)

The FSM Orchestrator manages state transitions for structured conversations like authentication:

- **States** - Well-defined conversation states (e.g., ASK_NAME, CONFIRM_PHONE)
- **State transitions** - Rules for moving between states based on user input
- **Persistence** - Redis-backed state tracking across conversation turns

```python
fsm = FSMOrchestrator(slot_store)
result = fsm.process_user_input(call_sid, "John Smith")
# State transitions from ASK_NAME to CONFIRM_NAME
```

### 3. Model Escalator (`ModelEscalator`)

The Model Escalator provides dynamic model upgrading based on confidence:

- **Confidence monitoring** - Tracks agent confidence in responses
- **Model tiers** - Defined progression from weaker to stronger models
- **Conditional escalation** - Uses context to determine when to escalate

```python
escalator = ModelEscalator()
if escalator.should_escalate(0.5, "gpt-4.1-mini", is_critical=True):
    # Upgrade to a stronger model
    escalated_request = escalator.escalate_request(request, "gpt-4.1-mini")
```

### 4. Slot Store (`SlotStore`)

The Slot Store provides persistent storage for conversation state:

- **Redis persistence** - Primary storage for slots
- **Memory fallback** - Local in-memory storage if Redis is unavailable
- **Call-scoped data** - Organizes data by call SID

```python
store = SlotStore(redis_client)
store.set_slot(call_sid, "authenticated", True)
store.set_slot(call_sid, "user_name", "John Smith")
```

## Integration with Voice Agents

The orchestration system is integrated with the voice agents through the `OrchestratedFrontlineAgent` class, which extends the base `HandoffCapableAgent`:

- Handles routing between specialist agents
- Manages authentication via FSM
- Implements confidence-based model escalation
- Tracks conversation state across turns

## Voice Routes

The orchestrated voice routes (`/voice_orchestrated`) provide endpoints for:

- Basic phone call handling with TwiML
- Real-time audio streaming via WebSockets
- Silence handling with progressive fallbacks
- Authentication flow with FSM
- Interactive demo UI

## Example Flow: Authentication

1. Customer indicates intent to place an order
2. System checks if authentication is required
3. FSM transitions to ASK_NAME state
4. Customer provides name
5. FSM transitions to CONFIRM_NAME state
6. Customer confirms name
7. FSM transitions to ASK_PHONE state
8. Customer provides phone number
9. FSM transitions to CONFIRM_PHONE state
10. Customer confirms phone number
11. FSM transitions to AUTHENTICATED state
12. System proceeds with order placement

## Example Flow: Model Escalation

1. Customer asks a complex question
2. Frontline agent checks its confidence level
3. If confidence is below threshold, model is escalated
4. Request is reprocessed with stronger model
5. Response is delivered with higher quality

## Technical Details

### State Management

State is managed across multiple layers:

- **Redis** - Primary storage for persistence across servers
- **In-memory** - Fallback for Redis failures
- **Session** - Flask session for web request context

### Voice Interfaces

The system supports multiple voice interfaces:

- **TwiML** - Traditional phone call handling
- **WebSockets** - Real-time streaming audio
- **Web UI** - Interactive demo for testing

### Testing

Comprehensive testing is provided through:

- **Unit tests** - Test individual components
- **Integration tests** - Test component interactions
- **E2E tests** - Test full conversation flows

## Demo

An interactive demo is available at `/voice_orchestrated/demo` that allows testing the system through a web interface, including:

- Text-based conversation
- Microphone input for speech
- Real-time state visualization
- Error handling demonstration

## Conclusion

The advanced agentic patterns provide a robust foundation for complex conversational flows, enhancing the capabilities of the RedBarSushiAI system with sequential handoffs, background escalation, and state-machine slot filling.