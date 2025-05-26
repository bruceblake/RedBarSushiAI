# RedBarSushiAI Codebase Analysis

## 1. Directory Structure Overview

```
app/
├── __init__.py
├── main.py                     # FastAPI application entry point
├── config.py                   # Application configuration
├── db_async.py                # Async database configuration
├── redis_async.py             # Redis configuration
├── dependencies.py            # FastAPI dependencies
│
├── api/                       # API endpoints
│   ├── __init__.py           # Main API router
│   ├── conversation_relay/    # ConversationRelay WebSocket handler
│   ├── menu/                 # Menu-related endpoints
│   ├── order/                # Order-related endpoints
│   └── voice/                # Voice/TwiML endpoints
│
├── agents/                    # AI agent implementations
│   ├── base_async.py         # Base agent class
│   ├── frontline_async.py    # Main conversation coordinator
│   ├── menu_async.py         # Menu inquiry specialist
│   ├── cart_async.py         # Order management specialist
│   ├── guardrail_async.py    # Order validation specialist
│   ├── fulfillment_async.py  # Order submission specialist
│   ├── escalation_async.py   # Human handoff specialist
│   └── factory_async.py      # Agent creation factory
│
├── fsm/                      # Finite State Machine
│   ├── core.py              # Core FSM implementation
│   └── handlers/            # State-specific handlers
│
├── models/                   # Database models
│   ├── menu_async.py        # Menu item models
│   ├── order_async.py       # Order models
│   └── location_async.py    # Location models
│
├── schemas/                  # Pydantic schemas
│   └── menu.py              # Menu data schemas
│
├── db/                      # Database operations
│   └── crud_menu_async.py   # Menu CRUD operations
│
├── utils/                   # Utility modules
│   ├── agent_orchestration_async.py  # Agent coordination
│   ├── conversation_store_async.py   # Conversation state storage
│   ├── fsm_async.py                  # FSM utilities
│   ├── menu_db_store_async.py        # Menu storage
│   ├── menu_matcher_db_async.py      # Menu item matching
│   ├── deliverect/                   # Deliverect integration
│   └── text_normalization.py         # Text processing
│
└── static/                  # Static files
    ├── websocket-test.html  # WebSocket testing page
    └── orchestrated_demo.html
```

## 2. Key Architectural Components

### 2.1 FastAPI Application Structure
- **Entry Point**: `app.main.py` - FastAPI application with async support
- **Configuration**: `app.config.py` - Environment-based settings using Pydantic
- **API Router**: `app.api.__init__.py` - Main router that includes all sub-routers

### 2.2 Multi-Agent Architecture
The system uses a multi-agent architecture where specialized agents handle different aspects of the conversation:

1. **Frontline Agent**: Main conversation coordinator that delegates to specialists
2. **Menu Agent**: Handles menu inquiries and availability checks
3. **Cart Agent**: Manages order items and modifications
4. **Guardrail Agent**: Validates orders against business rules
5. **Fulfillment Agent**: Processes order completion and submission
6. **Escalation Agent**: Manages handoff to human staff

### 2.3 Finite State Machine (FSM)
- Manages conversation flow through defined states
- States: INITIAL → GREETING → MAIN_MENU → ORDERING → VALIDATION → CONFIRMATION → FULFILLMENT → COMPLETION
- Event-driven transitions between states
- State-specific handlers for each conversation phase

### 2.4 Database Layer
- **Async SQLAlchemy**: Uses SQLAlchemy 2.0 with asyncpg for PostgreSQL
- **Models**: Menu items, modifiers, orders, locations
- **CRUD Operations**: Async database operations for all entities
- **Connection Management**: Proper async session handling with dependency injection

## 3. Request Flow for Voice Calls

### 3.1 Call Initiation Flow
```
1. Incoming Call → Twilio
2. Twilio → POST /voice/webhook (TwiML generation)
3. TwiML Response → Instructs Twilio to connect via WebSocket
4. Twilio → WebSocket /api/conversation-relay or /realtime/ws/media/{call_sid}
```

### 3.2 ConversationRelay Flow (Primary Voice Handler)
```
1. WebSocket Connection Established
   └─> ConversationRelayHandler initialized
   
2. Start Event Received
   └─> Initialize conversation with agent_orchestrator
   └─> Send greeting via TTS
   
3. Media Events (Audio from Caller)
   └─> AudioProcessor.speech_to_text() → Convert audio to text
   └─> agent_orchestrator.process_voice_input() → Process with agents
   └─> AudioProcessor.text_to_speech() → Convert response to audio
   └─> Send audio back to Twilio
   
4. Mark Events
   └─> Track TTS playback completion
   └─> Handle barge-in detection
   
5. Stop Event
   └─> Clean up conversation
   └─> Close WebSocket connection
```

### 3.3 Agent Processing Flow
```
1. Voice Input → Agent Orchestrator
   └─> Get/Create FSM for session
   └─> Determine current state
   └─> Route to appropriate agent based on state
   
2. Agent Processing
   └─> Frontline Agent analyzes intent
   └─> May delegate to specialist agents
   └─> Returns response with actions
   
3. State Transitions
   └─> FSM handles state changes
   └─> Updates conversation context
   └─> Persists state to Redis
```

## 4. Database Architecture

### 4.1 Core Tables

#### Menu Tables
- **menu_categories**: Category organization
- **menu_items**: Individual menu items with PLUs
- **menu_modifiers**: Available modifications
- **modifier_groups**: Groups of related modifiers
- **menu_name_variants**: Natural language mappings to PLUs
- **item_modifier_group**: M2M relationship
- **group_modifier**: M2M relationship

#### Order Tables
- **orders**: Order header information
- **order_items**: Line items in orders
- **order_item_modifiers**: Modifiers applied to items
- **contact_requests**: Customer callback requests

#### System Tables
- **locations**: Restaurant location configuration

### 4.2 Key Relationships
```
MenuCategory ─┐
              ├─> MenuItem ─┬─> ItemModifierGroup ─> ModifierGroup ─> MenuModifier
              │             └─> OrderItem ─> OrderItemModifier
              └─> MenuNameVariant (maps phrases to PLUs)

Order ─> OrderItem ─> OrderItemModifier
```

## 5. Key Modules and Responsibilities

### 5.1 API Layer (`app/api/`)
- **conversation_relay/**: WebSocket handler for Twilio ConversationRelay
  - `handler.py`: Main WebSocket event processing
  - `audio.py`: STT/TTS audio processing
  - `twiml.py`: TwiML generation for ConversationRelay
  
- **menu/**: RESTful endpoints for menu operations
  - Categories, items, modifiers, search, variants
  
- **order/**: Order management endpoints
  - Checkout, confirmation, status, modifications
  
- **voice/**: Voice call handling
  - TwiML generation for incoming calls
  - Testing endpoints

### 5.2 Agent System (`app/agents/`)
- **factory_async.py**: Creates and manages agent instances
- **base_async.py**: Base class with common agent functionality
- Each specialized agent inherits from BaseAsyncAgent

### 5.3 Utilities (`app/utils/`)
- **agent_orchestration_async.py**: Coordinates agent interactions
- **conversation_store_async.py**: Manages conversation state in Redis
- **menu_matcher_db_async.py**: Intelligent menu item matching
- **deliverect/**: Integration with POS system

## 6. ConversationRelay Integration

### 6.1 Overview
ConversationRelay is Twilio's newer WebSocket protocol that provides:
- Lower latency than Media Streams
- Better reliability
- Built-in barge-in detection
- Simplified audio handling

### 6.2 Implementation Details

#### WebSocket Handler (`app/api/conversation_relay/handler.py`)
```python
class ConversationRelayHandler:
    - Manages WebSocket connection lifecycle
    - Processes Twilio events (start, media, mark, stop)
    - Handles barge-in detection
    - Coordinates with agent orchestrator
```

#### Audio Processing (`app/api/conversation_relay/audio.py`)
```python
class AudioProcessor:
    - speech_to_text(): OpenAI Whisper for STT
    - text_to_speech(): OpenAI TTS for speech generation
    - Audio format conversion (PCMU ↔ PCM ↔ WAV)
```

#### TwiML Generation
- Configured via VOICE_HANDLER environment variable
- Falls back to Media Streams if ConversationRelay not configured
- Generates appropriate TwiML based on handler type

### 6.3 Configuration
```
VOICE_HANDLER=conversation_relay
TWILIO_CONVERSATION_SERVICE_SID=<service-sid>
TWILIO_CONNECTOR_NAME=<connector-name>
```

## 7. Key Design Patterns

### 7.1 Dependency Injection
- FastAPI's dependency system for database sessions
- Agent factory pattern for creating agent instances
- Configuration management through Pydantic settings

### 7.2 Async/Await Pattern
- All I/O operations use async/await
- Proper task management with asyncio
- Non-blocking database operations

### 7.3 State Management
- FSM for conversation flow control
- Redis for distributed state storage
- Context preservation across interactions

### 7.4 Error Handling
- Graceful degradation for failures
- Proper WebSocket error handling
- Fallback responses for agent failures

## 8. Integration Points

### 8.1 External Services
- **Twilio**: Voice calls and SMS
- **OpenAI**: STT (Whisper) and TTS
- **Deliverect**: POS integration
- **PostgreSQL**: Data persistence
- **Redis**: Caching and state management

### 8.2 Internal Integration
- Agents communicate through the orchestrator
- FSM manages conversation flow
- Database layer provides data access
- WebSocket handlers manage real-time communication

## 9. Deployment Considerations

### 9.1 Environment Variables
- Database connection strings
- API keys (OpenAI, Twilio, Deliverect)
- Service configuration (Redis, etc.)
- Voice handler selection

### 9.2 Scalability
- Async architecture for handling concurrent calls
- Redis for distributed state
- Connection pooling for database
- Stateless agent design

### 9.3 Monitoring
- Comprehensive logging throughout
- Error tracking and reporting
- Performance metrics collection
- WebSocket connection monitoring