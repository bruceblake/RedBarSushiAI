# RedBarSushiAI: System Architecture

## Overview

RedBarSushiAI is an AI-powered voice ordering system for Red Bar Sushi that enables customers to place orders and get menu information over the phone. The system integrates real-time speech processing with a specialized multi-agent architecture to provide natural conversations and accurate order fulfillment.

## Glossary of Terms

- **ASGI**: Asynchronous Server Gateway Interface - A specification for asynchronous web servers and applications
- **WSGI**: Web Server Gateway Interface - A specification for synchronous web servers and applications
- **PLU**: Product Lookup Unit - Unique identifier for menu items in the POS system
- **POS**: Point of Sale - Restaurant management system (Deliverect in this case)
- **FSM**: Finite State Machine - Pattern for modeling conversation flow through discrete states
- **TTS**: Text-to-Speech - Converting text responses to spoken audio
- **ASR**: Automatic Speech Recognition - Converting spoken audio to text
- **VAD**: Voice Activity Detection - Identifying when someone is speaking vs silent

## Core Components and Integration Points

### 1. Voice Processing Infrastructure

The system uses Twilio for phone communication, OpenAI for real-time audio processing, and a multi-agent architecture for conversation management:

- **Twilio Integration**: Handles incoming calls using WebSockets for bidirectional audio streaming
- **OpenAI Realtime API**: Provides speech-to-text, natural language understanding, and text-to-speech
- **Multi-Agent System**: Specialized agents handle different aspects of the ordering process

### 2. Database and Storage

- **PostgreSQL**: Primary data store for menu items, orders, and configuration
- **Redis**: Caching layer and session state management
- **Celery**: Asynchronous task processing for order confirmation and updates

### 3. External Integrations

- **Deliverect**: Order management and POS integration using API with PLU-based identification
- **Stripe**: Payment processing (configured but appears to be optional)

## System Architecture

The application is structured as a Flask application with WebSocket support through Flask-Sock, using the ASGI architecture for handling async operations with uvicorn workers.

### Key Components:

1. **Voice Processing Pipeline**:
   ```
   ┌───────────────────────────┐
   │ OpenAI Realtime Session   │
   │  • ASR & partial transcripts   │
   │  • VAD-driven events           │
   │  • Tool_call & tool_response   │
   │  • TTS audio chunks            │
   └─┬───────────────────────────┬─┘
     │ transcript.final          │ audio(TTS)
     ▼                            ▼
   ┌──────────┐             ┌─────────────┐
   │ Frontline│─handoff─▶   │ Fulfillment │
   │ Voice    │  or tool    │ Agent       │
   │ Agent     ◀─tool───    └─────────────┘
   └─┬────────┘
     │ tool calls
     ▼
   ┌────────────┐  ┌─────────┐  ┌───────────┐
   │ Menu Agent │  │ Cart    │  │ Guardrail │
   │            │  │ Agent   │  │ Agent     │
   └────────────┘  └─────────┘  └───────────┘
   ```

2. **Multi-Agent Architecture**:
   - Frontline agent handles initial conversation and routing
   - Menu agent answers questions about available items
   - Cart agent processes orders and modifications
   - Fulfillment agent handles order completion
   - Guardrail agent enforces business rules

3. **Menu Management**:
   - Database-backed menu items with Redis caching
   - Menu matching via exact, fuzzy, and AI-powered matching
   - Variant handling for different ways customers refer to items

4. **Order Processing**:
   - Natural language order parsing by specialized agents
   - Cart state maintained in Redis (scoped per active call session by call_sid)
   - Order validation against business rules
   - Deliverect integration for POS submission

## Directory Structure and Key Files

### Application Core (`/app`)
- **`/app/__init__.py`**: Flask application factory and initialization
- **`/app/db.py`**: Database connection management
- **`/app/models/`**: Database models for menu, orders, and locations

### Agent System (`/app/agents`)
- **`/app/agents/base.py`**: Base agent implementation
- **`/app/agents/frontline.py`**: Main conversational agent
- **`/app/agents/menu.py`**: Menu specialist agent
- **`/app/agents/cart.py`**: Order management agent
- **`/app/agents/fulfillment.py`**: Order submission agent
- **`/app/agents/guardrail.py`**: Validation agent
- **`/app/agents/factory_with_orchestration.py`**: Creates agent relationships

### Routes and API Endpoints (`/app/routes`)
- **`/app/routes/realtime.py`**: WebSocket endpoints for real-time audio
- **`/app/routes/voice/`**: Voice system components
- **`/app/routes/voice/twilio/improved_twiml.py`**: TwiML generation
- **`/app/routes/order.py`**: Order management endpoints
- **`/app/routes/menu.py`**: Menu information endpoints

### Utilities and Helpers (`/app/utils`)
- **`/app/utils/agent_orchestration.py`**: Coordinates agent interactions
- **`/app/utils/conversation_store.py`**: Manages conversation state
- **`/app/utils/menu_matcher_db.py`**: Menu item lookup and matching
- **`/app/utils/deliverect/`**: Deliverect API integration

### Infrastructure
- **`/docker-entrypoint.sh`**: Container initialization and server launch
- **`/wsgi.py`**: WSGI/ASGI application entry point
- **`/db/init/01_schema.sql`**: Database schema definition
- **`/force_rebuild.sh`**: Docker container rebuild script

## Technical Implementation Details

### 1. WebSocket Architecture for Real-time Voice

The system uses a WebSocket-based approach for real-time audio processing:

1. Twilio initiates a MediaStream connection through `/ws/media/<call_sid>`
2. The application establishes a connection to OpenAI's Realtime API
3. Audio streams bidirectionally between Twilio and OpenAI
4. Events (transcripts, audio, tool calls) are processed by specialized handlers
5. Agent responses are converted to speech and streamed back to Twilio

#### Agent-OpenAI TTS Integration

When the agent needs to speak to the user:

1. The WebSocket handler (in `realtime.py`) receives `transcript.final` event from OpenAI
2. The handler calls `frontline_agent.handle_voice_input()` with the transcript
3. Agent response text is generated through the agent system
4. Text response is sent to OpenAI using a `conversation.item.create` message followed by a `response.create` message
5. OpenAI generates TTS audio which is streamed back to Twilio

#### Tool Execution Flow

When an agent needs to execute a tool:

1. The WebSocket handler receives a `tool_call` event from OpenAI with `name` and `arguments`
2. The handler dispatches the tool call to the appropriate tool handler via the tools registry
3. Tool handler executes the requested operation (e.g., looking up menu item, updating cart)
4. Tool result is returned to the handler
5. Handler sends a `tool_result` message back to OpenAI with the operation result
6. OpenAI may generate additional tool calls or a text response based on the tool result

This tool execution flow is critical for specialized operations like menu lookups, cart management, and order validation.

The `process_openai_responses_and_interact` coroutine in `realtime.py` is the critical component connecting the WebSocket stream to the agent system and handling the bidirectional interaction.

### 2. Multi-Agent Orchestration

The system implements a sophisticated agent orchestration system:

1. **Agent Graph**: Manages transitions between specialized agents
2. **Finite State Machine**: Controls conversation flow states
   - GREETING → MAIN_MENU → ORDERING → VALIDATION → CONFIRMATION → FULFILLMENT
3. **Slot System**: Tracks collected customer information
4. **Tool Registry**: Allows agents to perform specific actions

### 3. Database Schema

The database schema mirrors Deliverect's data structure:

1. **Menu Tables**:
   - `menu_categories`: Groups of menu items
   - `menu_items`: Individual food items with prices and PLUs
   - `menu_modifier_groups`: Groups of modifiers (e.g., "Spice Level")
   - `menu_modifiers`: Individual modifications (e.g., "Extra Spicy")
   - `menu_name_variants`: Maps natural language to specific PLUs

2. **Order Tables**:
   - `orders`: Customer orders with status and delivery info
   - `order_items`: Items in each order with quantity
   - `order_item_modifiers`: Modifications to specific order items

### 4. State Management

The system uses Redis for state management with multiple data structures:

1. **Conversation Context**:
   - FSM state tracking
   - Customer information
   - Conversation history
   - Scoped per active call session by call_sid

2. **Cart State**:
   - Items with quantities and modifiers
   - Order type and delivery information
   - Price calculations
   - Scoped per active call session by call_sid (not shared between calls)

3. **Menu Cache**:
   - Fast item lookup by PLU
   - Variant matching for natural language
   - Category organization

### 5. Resilience Patterns

The system implements extensive resilience patterns:

1. **Multi-level Cache Fallbacks**:
   - Redis (primary) → Database → Memory (fallback)
   - If Redis fails, the system falls back to direct database queries
   - If database fails, the system uses in-memory cache as last resort

2. **Audio Processing Fallbacks**:
   - Real-time streaming (preferred): Process audio in small chunks as it arrives
   - Chunk processing (fallback 1): Process larger buffered audio chunks if streaming fails
   - Complete utterance (fallback 2): Process entire audio utterance if chunk processing fails
   - Text-only mode (fallback 3): Fall back to text-only if all audio processing fails
   - Each step has appropriate error handling and logging

3. **WebSocket Error Handling**:
   - **Connection Loss**: If WebSocket connection to OpenAI drops, system attempts reconnection with exponential backoff
   - **Session Errors**: When receiving `session.error` events from OpenAI, the system:
     1. Logs detailed error information
     2. Attempts to gracefully recover the session if possible
     3. Falls back to a default error message via TTS if session can't be restored
     4. Eventually transfers to a human operator after multiple failures
   - **Malformed Messages**: System validates all messages before processing, discarding invalid ones
   - **Timeouts**: Implements heartbeat mechanism to detect inactive connections

4. **Database Connection Resilience**:
   - Retry logic with exponential backoff
   - Connection pooling with health checks
   - Session cleanup to prevent leaks

5. **Docker Environment Detection**:
   - Environment-specific configuration
   - Automatic URL transformation for Render platform
   - Fallback dependency installation

### 6. ASGI/WSGI Implementation

The application is structured as a Flask (WSGI) application that is made compatible with ASGI through the WsgiToAsgi adapter:

1. Flask application created in `app/__init__.py` with a factory pattern
2. WSGI entry point defined in `wsgi.py`
3. ASGI compatibility added using `asgiref.wsgi.WsgiToAsgi`
4. Uvicorn worker used for handling async WebSockets
5. Multiple fallback mechanisms to ensure resilience:
   - asgiref dependency in requirements.txt
   - Runtime check and installation in docker-entrypoint.sh
   - SimpleWsgiToAsgi fallback class in wsgi.py

This architecture allows a traditional Flask application to handle WebSockets and async workloads effectively.

## Recent System Improvements

### ASGI Infrastructure Improvements

The WebSocket handling has been improved with these changes:

1. **Removed Redundant Middleware**:
   - Eliminated unnecessary DispatcherMiddleware that was causing compatibility issues

2. **Added ASGI Adapter**:
   - Added WsgiToAsgi adapter to bridge Flask's WSGI app to ASGI
   - Included asgiref in requirements.txt for proper dependency management

3. **Enhanced Resilience**:
   - Added runtime check for asgiref in docker-entrypoint.sh
   - Created SimpleWsgiToAsgi fallback in wsgi.py
   - Multiple layers of protection against dependency issues

4. **Standardized Server Configuration**:
   - Standardized on uvicorn worker with wsgi:asgi_app as the gunicorn target
   - Consistent approach to server startup in docker-entrypoint.sh

These changes ensure proper handling of WebSocket upgrade requests, which helps address issues that might otherwise present as Twilio HTTP 11200 errors (though network connectivity can still be a factor in such errors).

### Real-time Audio Processing Enhancements

Recent improvements to the real-time audio processing system enable more natural conversations:

1. **Enhanced Interruption Handling**:
   - Configured OpenAI session with explicit `interrupt_response: true` setting
   - Added `interruption_threshold_ms` parameter (300ms) to define when interruption triggers
   - Implemented strategic gevent.sleep() calls to improve cooperative multitasking:
     ```python
     # Differentiated yielding for speech vs. silence packets
     if is_speech:
         # For speech packets (potential interruptions), use longer sleep
         gevent.sleep(0.003)  # Slightly longer sleep for speech packets
     else:
         # For silence packets, use shorter sleep
         gevent.sleep(0.001)  # Shorter sleep for silence packets
     ```
   - Added extra yields during audio playback to ensure responsiveness
   - Enhanced VAD configuration for better silence detection and turn-taking

2. **Improved Observability**:
   - Added detailed logging for FSM state transitions:
     ```python
     log_orchestration_event(
         "info",
         f"[{call_sid}] FSM STATE TRANSITION: {previous_state_value} → {state.value}",
         {
             "call_sid": call_sid,
             "previous_state": previous_state_value,
             "new_state": state.value,
             "retry_count": retry_count + 1,
             "timestamp": datetime.now().isoformat()
         },
         call_sid=call_sid,
         phase="FSM"
     )
     ```
   - Enhanced intent detection logging to track decision factors
   - Implemented speech detection event logging for interruption analysis
   - Added slot update logging with proper redaction of sensitive data

3. **Database Resilience Improvements**:
   - Fixed schema-model discrepancy between `snoozed_until` (DB schema) and `snooze_until` (model code)
   - Added property getters/setters for backward compatibility
   - Implemented JSONB sanitization to ensure proper serialization
   - Enhanced error handling for JSONB operations
   - Added multi-level fallbacks for database operations

## Deployment and Infrastructure

### Docker Configuration

The system uses Docker for containerization with these key components:

1. **docker-entrypoint.sh**:
   - Configures environment variables
   - Installs dependencies
   - Initializes database
   - Starts Gunicorn with appropriate worker

2. **force_rebuild.sh**:
   - Stops existing containers
   - Removes Docker images
   - Rebuilds from scratch

3. **restart_docker.sh**:
   - Restarts containers with existing images

### Environment Variables

Key environment variables that control system behavior:

- `FLASK_APP`: Entry point for the Flask application
- `PORT`: Port to bind the web server
- `REDIS_URL`: Connection URL for Redis
- `SQLALCHEMY_DATABASE_URI`: Connection URL for PostgreSQL
- `OPENAI_API_KEY`: API key for OpenAI
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`: Twilio credentials
- `DELIVERECT_CHANNEL_NAME`, `DELIVERECT_API_KEY`: Deliverect credentials

## Conclusion

RedBarSushiAI demonstrates an advanced architecture combining voice technologies, multi-agent systems, and e-commerce integration. The system's modular design with specialized agents, robust WebSocket implementation, and multi-layered fallback mechanisms provide a resilient and scalable platform for voice-based ordering.

The system expertly orchestrates interactions between Twilio for phone handling, OpenAI for natural language processing, and Deliverect for order management, providing a seamless customer experience.