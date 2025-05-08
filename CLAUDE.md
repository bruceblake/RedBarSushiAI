# RedBarSushiAI Project Context

This document provides essential context for the RedBarSushiAI project, explaining key architectural decisions, workflows, and components.

## Project Overview

FILES MUST NOT BE LONGER THAN 500 LINES LONG
NEVER IMPLEMENT FALLBACKS UNLESS SPECIFICALLY ASKED
WHEN IT COMES TO SPECIFIC API RELATED TASKS REFER TO MCP CONTEXT OR THIS DOCUMENT DO NOT MAKE UP ANYTHING
WE HAVE 2 ENVIRONMENTS, A STAGING ENVIRONMENT FOR TESTING AND A PRODUCTION ENVIRONMENT. ALL ENVIRONMENTS ARE DEPLOYED USING RENDER AND HAVE THEIR OWN ENVIRONMENT VARIABLES SET, THIS IS ON A LOCAL SYSTEM

RedBarSushiAI is an AI-powered voice ordering system for Red Bar Sushi that enables customers to place orders and get menu information over the phone. The system integrates with:

- **Twilio**: For phone/voice communication with programmable voice and media streams
- **OpenAI**: For real-time audio processing, natural language understanding, and orchestrated multi-agent interactions
- **Deliverect**: For order management and POS integration
- **PostgreSQL**: For data persistence of menu items, orders, and variants
- **Redis**: For caching, conversation state management, and as Celery broker
- **Celery**: For asynchronous task processing including order confirmation and polling

## Core Architecture

### Database Architecture

The system uses PostgreSQL for data persistence with these key models that mirror the Deliverect data structure:

1. **Menu Models** (`app/models/menu.py`):

   - `MenuCategory`: `id`, `deliverect_category_id`, `name`, `description`
   - `MenuItem`: `id`, `category_id`, `name`, `description`, `price`, `plu` (critical link to POS), `deliverect_item_id`, `is_available`, `is_combo`, `is_variant`, `image_url`, `snoozed_until`
   - `MenuModifier`: `id`, `modifier_group_id`, `name`, `price_change`, `plu` (critical), `deliverect_modifier_id`, `is_available`, `snoozed_until`
   - `MenuModifierGroup`: `id`, `deliverect_group_id`, `name`, `min_selection`, `max_selection`, `multiMax`, `plu`, `is_variant_group`
   - `ItemModifierGroup`: Links `menu_items` to `modifier_groups`
   - `GroupModifier`: Links `modifier_groups` to `modifiers`
   - `MenuNameVariant`: `variant_phrase` (lowercase), `canonical_name`, `target_plu` - Essential for mapping natural language to specific PLUs

2. **Order Models** (`app/models/order.py`):

   - `Order`: `id`, `deliverect_channel_order_id` (critical link to Deliverect), `customer_phone`, `order_type`, `status`, `total_price`, `placed_at`, `estimated_time`, `delivery_address`
   - `OrderItem`: Links `orders` to `menu_items` via `menu_item_plu`, stores quantity
   - `OrderItemModifier`: Links `order_items` to `modifiers` via `modifier_plu`

3. **Location Model** (`app/models/location.py`):
   - `Location`: Stores location settings, Deliverect connection details, and business hours
   - Each location has its own `channelLinkId` for Deliverect integration

### Voice Architecture

Voice interactions are managed through an orchestrated multi-agent architecture with real-time audio processing. The system has been refactored into a modular structure for improved maintainability:

```
┌───────────────────────────┐
│ OpenAI Realtime Session   │
│  • ASR & partial transcripts   │
│  • VAD-driven events           │
│  • Tool_call & tool_response   │
│  • TTS audio chunks            │
└─┬───────────────────────────┬─┘
  │ tool_call(name, args)     │ audio(TTS)
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

1. **Modular Voice Implementation** (`app/routes/voice/` directory):

   - Real-time audio processing via WebSockets
   - Multi-agent architecture with specialized roles
   - Finite State Machine (FSM) for conversation flow
   - Manages agent handoffs and escalations
   - Handles audio streaming and VAD events

2. **Key Components**:

   - **Stream Handler** (`app/routes/realtime.py`): Main WebSocket handler for real-time audio
   - **Event Handlers** (`app/routes/voice/handlers/`): Specialized handlers for different event types
   - **TwiML Generation** (`app/routes/voice/twilio/improved_twiml.py`): Generates TwiML for Twilio
   - **Tools Registry** (`app/routes/voice/utils/tools_registry.py`): Manages tool registration and execution
   - **VAD Configuration** (`app/routes/voice/utils/vad.py`): Voice Activity Detection settings

3. **Agent Roles**:

   - **Frontline Agent**: Manages overall call flow and delegates to specialists
   - **Menu Agent**: Handles menu inquiries and availability
   - **Cart Agent**: Manages order items and modifications
   - **Fulfillment Agent**: Processes order completion and payment
   - **Guardrail Agent**: Enforces constraints and business rules
   - **Escalation Agent**: Manages handoff to human staff when needed

4. **Silence & VAD Handling**:
   - Phase-specific timeouts based on conversation context
   - Voice Activity Detection with adaptive timeouts
   - Progressive fallbacks with configurable retry limits
   - State-aware reprompting strategies

## Real-time Voice Architecture

The real-time voice system is built using the OpenAI Realtime API with the following components:

### WebSocket Implementation

1. **Server Configuration**:
   - Uses Flask-Sock for WebSocket support
   - Uses Gevent worker with Gunicorn for concurrency
   - Applies Gevent monkey patching for cooperative concurrency

2. **WebSocket Connection Flow**:
   - **Twilio Connection**: Call comes in, Twilio connects via WebSocket to `/ws/media/<call_sid>`
   - **Handshake Process**: Handles 'connected' and 'start' events from Twilio
   - **OpenAI Connection**: Establishes WebSocket connection to OpenAI Realtime API
   - **Bidirectional Streaming**: Handles audio streaming in both directions

3. **Implementation Details**:
   - **Greenlet-based Concurrency**: Uses Gevent greenlets instead of asyncio for concurrency
   - **Event-based Communication**: Uses events and queues for inter-greenlet communication
   - **Proper Error Handling**: Gracefully handles connection errors and closures

### OpenAI Realtime Integration

1. **Session Configuration**:
   - Uses the `session.update` event to configure the OpenAI Realtime session
   - Sets up audio formats, VAD parameters, and model instructions
   - Configures server-side VAD for automatic speech detection

2. **Audio Processing**:
   - **Input**: Forwards Twilio audio packets to OpenAI using `input_audio_buffer.append`
   - **Output**: Receives audio from OpenAI via `response.audio.delta` events
   - **Transcription**: Processes final transcripts from OpenAI
   - **TTS**: Generates text-to-speech using a two-step process with `conversation.item.create` and `response.create`

3. **Tool Calling**:
   - Handles function calls from OpenAI via various event formats
   - Executes tools locally via the tools registry
   - Returns results to OpenAI using the documented format
   - Requests new responses using `response.create` after tool execution

### Multi-Agent Orchestration

1. **Agent Integration**:
   - Processes transcripts with the appropriate agent based on conversation state
   - Converts agent responses to TTS using OpenAI's voice synthesis
   - Manages agent handoffs and tool execution
   - Maintains conversation context throughout the interaction

2. **State Management**:
   - Tracks conversation state using a FSM
   - Maintains session context for stateful interactions
   - Enables seamless agent transitions based on intents and triggers

## Menu Management

The menu system uses a database-backed architecture with multi-level caching:

1. **Database Storage** (`app/utils/menu_db_store.py`):

   - PostgreSQL as the persistent source of truth
   - Redis caching layer for improved performance
   - In-memory fallback if Redis becomes unavailable
   - Menu validation and data integrity checks

2. **Menu Matching** (`app/utils/menu_matcher_db.py`):
   - Progressive matching strategy with fallbacks:
     - Exact match (fastest, first attempt)
     - Fuzzy matching with Levenshtein distance (second attempt)
     - AI-powered semantic matching (most accurate, final attempt)
   - Variant mapping to handle different ways customers refer to items
   - Context-aware matching based on previous items

## Order Processing

Orders are processed through a multi-stage pipeline with specialized agents:

1. **Cart Management** (`app/agents/cart.py`):

   - Parses natural language order descriptions
   - Resolves ambiguities through interactive clarification
   - Manages cart state in Redis
   - Handles item modifications and quantities

2. **Order Validation** (`app/agents/guardrail.py`):

   - Enforces business rules and constraints
   - Validates modifier selection limits
   - Verifies item availability and snooze status
   - Calculates accurate pricing

3. **Order Fulfillment** (`app/agents/fulfillment.py`):
   - Prepares the Deliverect payload
   - Submits orders to the POS system
   - Records orders in the database
   - Triggers SMS notifications via Celery

## Key Workflows

### Voice Call Workflow

1. **Setup Phase**:

   - Twilio initiates the call and connects to WebSocket endpoint `/ws/media/<call_sid>`
   - Twilio sends 'connected' and 'start' events to establish the media stream
   - System initializes the orchestrated voice agent
   - System establishes connection to OpenAI Realtime API

2. **Greeting Phase** (FSM: GREETING state):

   - Frontline agent introduces the restaurant and asks for customer name
   - Voice Activity Detection monitors for silence
   - System stores customer name and transitions to main menu

3. **Menu Phase** (FSM: MAIN_MENU state):

   - Customer is presented with options (ordering, menu inquiries, staff)
   - Menu agent handles inquiries about available items
   - Contextual responses based on previous questions

4. **Order Phase** (FSM: ORDERING state):

   - Cart agent processes natural language order descriptions
   - Interactive disambiguation for ambiguous items
   - System builds cart with precise PLUs for Deliverect

5. **Validation Phase** (FSM: VALIDATION state):

   - Guardrail agent validates order against business rules
   - System verifies item availability and modification constraints
   - Price calculation with modifier adjustments

6. **Confirmation Phase** (FSM: CONFIRMATION state):

   - System summarizes order details and total price
   - Customer confirms or makes adjustments
   - Delivery/pickup options presented

7. **Fulfillment Phase** (FSM: FULFILLMENT state):
   - Fulfillment agent prepares the order payload
   - Order submitted to Deliverect with proper formatting
   - Order recorded in database and confirmation sent
   - System transitions to COMPLETION or FOLLOW_UP state

### Real-time Audio Processing Workflow

1. **Audio Streaming**:

   - Raw audio data streams via WebSocket in 20ms packets from Twilio
   - Audio forwarded to OpenAI Realtime API in real-time
   - Voice Activity Detection processes silence events

2. **Speech Processing**:

   - OpenAI Realtime API processes streaming audio
   - Partial transcripts displayed during speech
   - Complete utterances forwarded to agents

3. **Agent Orchestration**:

   - Frontline agent handles initial understanding
   - Agent handoffs based on intent and FSM state
   - Specialized agents process different aspects of the interaction
   - Tool calls used for specific operations

4. **Response Generation**:
   - Text responses generated by appropriate agent
   - Text sent to OpenAI for TTS using conversation.item.create
   - OpenAI generates audio using the configured voice
   - Audio streamed back to customer in real-time via Twilio

## API Integrations

### OpenAI Realtime API Integration

The system integrates with OpenAI's Realtime API for real-time audio processing:

1. **Connection Details**:
   - **URL**: `wss://api.openai.com/v1/realtime`
   - **Parameters**: `model=gpt-4o-realtime-preview-2024-10-01`
   - **Headers**: 
     - `Authorization: Bearer YOUR_API_KEY`
     - `OpenAI-Beta: realtime=v1`

2. **Session Configuration**:
   - **Audio Formats**: `mulaw` for input and output
   - **Voice**: `shimmer` (configurable)
   - **VAD**: Server-side VAD with custom silence duration
   - **Modalities**: text and audio

3. **Event Flow**:
   - **Input**: `input_audio_buffer.append` events with base64-encoded audio
   - **Transcription**: `transcript.final` events with complete transcripts
   - **Response**: Two-step process with `conversation.item.create` and `response.create`
   - **Output**: `response.audio.delta` events with base64-encoded audio chunks

4. **Tool Calling**:
   - Functions registered with OpenAI for execution
   - Tool calls received via various event types
   - Results returned using `conversation.item.create` with type `function_call_output`
   - Responses triggered with `response.create` after tool execution

### Twilio Integration

The system integrates with Twilio for voice communication:

1. **Programmable Voice**:
   - Phone calls handled via webhooks
   - TwiML generation for call flow control
   - Media Streams for real-time audio processing

2. **WebSocket Integration**:
   - Bidirectional media streaming
   - Binary audio data transfer
   - Event-based protocol (`start`, `media`, `stop` events)

3. **Call Flow**:
   - Incoming call triggers webhook
   - TwiML instructs Twilio to connect to WebSocket
   - Media streams established for bidirectional audio
   - Call ended when WebSocket closes

### Deliverect Integration

The system integrates with Deliverect for order management:

1. **Order Submission**:
   - Orders formatted with specific Deliverect structure
   - PLUs used to identify menu items and modifiers
   - Customer details and order options included

2. **Status Tracking**:
   - Order status retrieved via polling
   - Status codes mapped to customer-friendly messages
   - Notifications sent based on status changes

## Deployment

The application is deployed on Render with these features:

1. **Environment Configuration**:
   - Production vs. Staging environments
   - Automatic database initialization
   - Redis connection handling

2. **Docker Configuration**:
   - Gevent worker class for Gunicorn
   - Monkey patching for cooperative concurrency
   - WebSocket support via Flask-Sock

3. **CI/CD Pipeline**:
   - Tests run on PR and push
   - Deploys to staging from `staging` branch
   - Deploys to production from `main` branch

## Development Guide

### Development Architecture

```
app/
├── agents/                 # Agent components
│   ├── base.py             # Base agent implementation
│   ├── cart.py             # Cart management agent
│   ├── factory.py          # Agent factory
│   └── ...                 # Other specialized agents
├── models/                 # Database models
│   ├── menu.py             # Menu items, modifiers, categories
│   ├── order.py            # Order and item tracking
│   └── ...                 # Other models
├── routes/                 # API endpoints
│   ├── realtime.py         # WebSocket handler for real-time audio
│   ├── voice/              # Voice implementation components
│   │   ├── twilio/         # Twilio integration
│   │   ├── handlers/       # Event handlers
│   │   └── utils/          # Utilities
│   └── ...                 # Other route modules
└── utils/                  # Shared utilities
    ├── realtime_audio_sdk.py  # Real-time audio processing
    ├── conversation_store.py  # Conversation state management
    └── ...                 # Other utilities
```

### WebSocket Implementation

1. **wsgi.py**:
   - Entry point for the application
   - Applies Gevent monkey patching
   - Exports Flask app for Gunicorn

2. **app/routes/realtime.py**:
   - WebSocket handler for Twilio media streams
   - Manages bidirectional audio between Twilio and OpenAI
   - Processes transcripts and handles agent responses

3. **app/utils/realtime_audio_sdk.py**:
   - Provides wrapper for OpenAI Realtime API
   - Handles audio format conversion
   - Manages session lifecycle

### Common Tasks

- **Run in Development**: `FLASK_DEBUG=1 FLASK_APP=run.py flask run`
- **Run Tests**: `pytest tests/e2e/test_orchestrated_voice_flow.py`
- **Rebuild Docker**: `./force_rebuild.sh && ./restart_docker.sh`
- **Check Logs**: `docker logs -f redbarsushi-app-1`

## API Reference

### OpenAI Realtime Events

1. **Client Events**:
   - `session.update`: Updates session configuration
   - `input_audio_buffer.append`: Sends audio chunk to OpenAI
   - `conversation.item.create`: Creates new conversation item
   - `response.create`: Requests response from model

2. **Server Events**:
   - `transcript.final`: Final transcript of user speech
   - `response.audio.delta`: Audio chunk from OpenAI TTS
   - `input_audio_buffer.speech_started`: User started speaking
   - `input_audio_buffer.speech_stopped`: User stopped speaking

### Twilio Media Streams Events

1. **Client Events**:
   - `media`: Audio data from Twilio
   - `start`: Initiates the media stream
   - `stop`: Ends the media stream

2. **Server Events**:
   - `media`: Audio data to Twilio
   - `heartbeat`: Keeps connection alive

## Error Handling

1. **Connection Errors**:
   - WebSocket connection failures
   - OpenAI API timeouts
   - Twilio connection issues

2. **Runtime Errors**:
   - Agent processing failures
   - Tool execution errors
   - Database connectivity issues

3. **Recovery Strategies**:
   - Graceful connection closure
   - Error reporting with appropriate codes
   - State preservation when possible

## Best Practices

1. **Code Organization**:
   - Keep files under 500 lines
   - Use modular, well-documented components
   - Follow established patterns for new features

2. **Error Handling**:
   - Provide meaningful error messages
   - Use appropriate WebSocket close codes
   - Log errors with sufficient context

3. **Performance**:
   - Optimize database queries
   - Use caching where appropriate
   - Monitor real-time audio performance

## System Configuration and Startup

### Environment Variables

The system relies on environment variables for configuration. Key variables include:

```
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/redbarsushi
TEST_DATABASE_URL=postgresql://user:password@localhost:5432/redbarsushi_test

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_ASSISTANT_ID=asst_...

# Twilio
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...

# Deliverect
DELIVERECT_CHANNEL_NAME=redbarsushi
DELIVERECT_API_KEY=...
DELIVERECT_BASE_URL=https://api.staging.deliverect.com

# Application Settings
FLASK_APP=run.py
FLASK_ENV=development  # or production
LOG_LEVEL=INFO
```

### Starting the Application

The application can be started with the following commands:

1. **Start the Flask server**:

   ```
   python run.py
   ```

   or in debug mode:

   ```
   FLASK_DEBUG=1 FLASK_APP=run.py flask run
   ```

2. **Start the Celery worker**:

   ```
   celery -A celery_app worker --loglevel=INFO
   ```

3. **Start with Docker**:
   ```
   ./start_docker.sh
   ```

### Database Initialization

On first run, the database needs to be initialized:

1. Create the database: `createdb redbarsushi`
2. Run migrations: `python -m flask db upgrade`
3. Initialize menu data: `python -m flask seed-menu`

## WebSocket Implementation Details

The WebSocket implementation for voice processing follows these key patterns:

1. **TwiML Generation** (`app/routes/voice/twilio/improved_twiml.py`):
   - Generates TwiML with `<Connect><Stream>` elements for bidirectional audio
   - Sends the CallSid to the WebSocket URL in the format: `wss://hostname/ws/media`
   - Configures proper track and stream name for media handling

2. **WebSocket Handler** (`app/routes/realtime.py`):
   - Implements a handler function using Flask-Sock and Gevent
   - Uses greenlets for concurrent operations and event processing
   - Establishes bidirectional connection between Twilio and OpenAI Realtime API
   - Forwards audio from Twilio to OpenAI and responses back to Twilio
   - Handles WebSocket lifecycle properly with appropriate close codes
   - Properly manages resource cleanup on connection termination

3. **Connection Reliability**:
   - Implements heartbeat mechanism to keep connections alive
   - Uses extensive error handling and logging for connection diagnostics
   - Gracefully handles WebSocket closures and reconnection attempts
   - Maintains session context across connection interruptions

4. **Realtime Audio SDK** (`app/utils/realtime_audio_sdk.py`):
   - Provides both async (WebSocket) and sync (gevent) implementations
   - Handles audio format conversion between Twilio and OpenAI
   - Manages OpenAI Realtime API session configuration
   - Processes events from OpenAI and converts them to application events