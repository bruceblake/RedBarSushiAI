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

The system uses PostgreSQL with SQLAlchemy for data persistence, with async support through asyncpg:

#### Database Engine and Sessions

1. **AsyncEngine Setup** (`app/db_async.py`):
   - Creates an async database engine using `create_async_engine` 
   - Configures connection pooling with `pool_pre_ping` and `pool_recycle`
   - Automatically converts `postgresql://` URLs to `postgresql+asyncpg://`
   - Provides validation and retry mechanisms for connection stability

2. **Async Sessions**:
   - Uses `async_sessionmaker` for creating async database sessions
   - Dependency injection with `get_db()` for FastAPI endpoints
   - Proper session lifecycle management with automatic cleanup
   - Connection verification with `verify_connection()`

3. **Model Base Classes**:
   - Uses SQLAlchemy 2.0 style with `DeclarativeBase` in `app/db_async.py`
   - Compatibility layer in `app/compat_models.py` for legacy Flask-SQLAlchemy-style models
   - Proper transaction management with async commit/rollback

#### Key Database Models

1. **Menu Models** (`app/models/menu_async.py`):

   - `MenuCategory`: `id`, `deliverect_category_id`, `name`, `description`
   - `MenuItem`: `id`, `category_id`, `name`, `description`, `price`, `plu` (critical link to POS), `deliverect_item_id`, `is_available`, `is_combo`, `is_variant`, `image_url`, `snoozed_until`
   - `MenuModifier`: `id`, `modifier_group_id`, `name`, `price_change`, `plu` (critical), `deliverect_modifier_id`, `is_available`, `snoozed_until`
   - `MenuModifierGroup`: `id`, `deliverect_group_id`, `name`, `min_selection`, `max_selection`, `multiMax`, `plu`, `is_variant_group`
   - `ItemModifierGroup`: Links `menu_items` to `modifier_groups`
   - `GroupModifier`: Links `modifier_groups` to `modifiers`
   - `MenuNameVariant`: `variant_phrase` (lowercase), `canonical_name`, `target_plu` - Essential for mapping natural language to specific PLUs

2. **Order Models** (`app/models/order_async.py`):

   - `Order`: `id`, `deliverect_channel_order_id` (critical link to Deliverect), `customer_phone`, `order_type`, `status`, `total_price`, `placed_at`, `estimated_time`, `delivery_address`
   - `OrderItem`: Links `orders` to `menu_items` via `menu_item_plu`, stores quantity
   - `OrderItemModifier`: Links `order_items` to `modifiers` via `modifier_plu`

3. **Location Model** (`app/models/location_async.py`):
   - `Location`: Stores location settings, Deliverect connection details, and business hours
   - Each location has its own `channelLinkId` for Deliverect integration

4. **Special Data Types**:
   - Uses PostgreSQL JSONB for flexible property storage with proper fallback to Text
   - Helper module `app/jsonb_helper.py` for dialect-aware column type selection
   - TimestampMixin for consistent created_at/updated_at tracking

### Voice Architecture

Voice interactions are managed through an orchestrated multi-agent architecture with real-time audio processing using FastAPI and WebSockets:

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

1. **Async Voice Implementation** (`app/api/voice_async.py`):

   - Real-time audio processing via WebSockets
   - Multi-agent architecture with specialized roles
   - Finite State Machine (FSM) for conversation flow
   - Manages agent handoffs and escalations
   - Handles audio streaming and VAD events

2. **Key Components**:

   - **WebSocket Handler** (`app/api/voice_async.py`): FastAPI WebSocket handler for real-time audio
   - **FSM Implementation** (`app/utils/fsm_async.py`): Async FSM for conversation management
   - **Agent Orchestrator** (`app/utils/agent_orchestration_async.py`): Async agent coordination system
   - **Realtime Audio SDK** (`app/utils/realtime_audio_async.py`): Async OpenAI Realtime API client
   - **Database Layer** (`app/db/session_async.py`): Async SQLAlchemy with asyncpg for non-blocking DB operations

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

## FastAPI Implementation

The system has been migrated from Flask/Gevent to FastAPI with native async support:

### Core FastAPI Components

1. **Application Entry Point** (`app/main.py`):
   - FastAPI application setup with lifespan events
   - API router registration
   - Database, agent, and FSM initialization

2. **API Routes**:
   - RESTful endpoints for menu, order, and voice operations
   - WebSocket endpoint for Twilio media streams
   - FSM debugging endpoints for testing conversation flows

3. **Dependency Injection**:
   - Database session management via dependencies
   - Connection management for WebSockets
   - Agent factories and orchestrator dependencies

4. **Pydantic Models**:
   - Request and response validation
   - Data schema definitions
   - Configuration management

### Async Database Layer

1. **SQLAlchemy 2.0 Async Setup** (`app/db/session_async.py`):
   - AsyncEngine with create_async_engine()
   - AsyncSession with async_sessionmaker()
   - Dependency function for session injection
   - Proper session lifecycle management

2. **Async CRUD Operations** (`app/db/crud_*.py`):
   - Non-blocking database operations
   - Error handling for async database queries
   - Transaction management with async commit/rollback

3. **ORM Models** (`app/models/*.py`):
   - SQLAlchemy models for menu, order, and location data
   - Relationships between models
   - Base class with common fields

### Async FSM Implementation

1. **State Machine Components** (`app/utils/fsm_async.py`):
   - ConversationState enum for defining conversation states
   - ConversationEvent enum for triggering state transitions
   - AsyncStateHandler base class for state-specific behavior
   - Specialized handlers for each conversation state

2. **Core FSM Class** (`AsyncConversationFSM`):
   - State transition logic with validation
   - Event triggering and processing
   - Context maintenance across transitions
   - Persistence with async storage

3. **FSM Manager** (`AsyncFSMManager`):
   - Management of multiple FSM instances
   - Instance creation, retrieval, and removal
   - State handler provider system
   - Session tracking and cleanup

### Agent System

1. **Agent Factory** (`app/agents/factory_async.py`):
   - Async initialization of agent instances
   - Agent registration and retrieval
   - Voice agent system creation

2. **Base Agent** (`app/agents/base_async.py`):
   - Common agent functionality
   - Tool execution framework
   - Context management

3. **Specialized Agents**:
   - `AsyncFrontlineVoiceAgent`: Main conversation coordinator
   - `AsyncMenuAgent`: Menu inquiry specialist
   - `AsyncCartAgent`: Order management specialist
   - `AsyncGuardrailAgent`: Order validation specialist
   - `AsyncFulfillmentAgent`: Order submission specialist
   - `AsyncEscalationAgent`: Human handoff specialist

4. **Agent Orchestrator** (`app/utils/agent_orchestration_async.py`):
   - Integration with FSM for state-driven agent selection
   - Voice input processing through appropriate agents
   - Tool call handling with specialized agents
   - Session state management and cleanup

## Real-time Voice Architecture

The real-time voice system is built using the OpenAI Realtime API with FastAPI WebSockets:

### WebSocket Implementation

1. **Server Configuration**:
   - Uses FastAPI's native WebSocket support
   - Async/await pattern for non-blocking operations
   - Task-based concurrency with asyncio
   - Proper resource management with task cancellation

2. **WebSocket Connection Flow**:
   - **Twilio Connection**: Call comes in, Twilio connects via WebSocket to `/ws/media/{call_sid}`
   - **Handshake Process**: Handles 'connected' and 'start' events from Twilio
   - **OpenAI Connection**: Establishes WebSocket connection to OpenAI Realtime API
   - **Bidirectional Streaming**: Handles audio streaming in both directions

3. **Implementation Details**:
   - **Task-based Concurrency**: Uses asyncio tasks for concurrent operations
   - **Queue-based Communication**: Uses asyncio queues for inter-task communication
   - **Event-based Processing**: Processes events through dedicated handlers
   - **Proper Error Handling**: Gracefully handles connection errors and closures

### OpenAI Realtime Integration

1. **Session Configuration**:
   - Uses the `session.update` event to configure the OpenAI Realtime session
   - Sets up audio formats, VAD parameters, and model instructions
   - Configures server-side VAD for automatic speech detection
   - Proper interruption handling and timeout configuration

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

The menu system uses a database-backed architecture with async operations:

1. **Database Storage** (`app/db/crud_menu_async.py`):

   - PostgreSQL as the persistent source of truth
   - Async database operations with SQLAlchemy 2.0
   - Menu validation and data integrity checks

2. **Menu Matching**:
   - Progressive matching strategy with fallbacks:
     - Exact match (fastest, first attempt)
     - Fuzzy matching with Levenshtein distance (second attempt)
     - AI-powered semantic matching (most accurate, final attempt)
   - Variant mapping to handle different ways customers refer to items
   - Context-aware matching based on previous items

## Order Processing

Orders are processed through a multi-stage pipeline with specialized agents:

1. **Cart Management** (`app/agents/cart_async.py`):

   - Parses natural language order descriptions
   - Resolves ambiguities through interactive clarification
   - Manages cart state in Redis
   - Handles item modifications and quantities

2. **Order Validation** (`app/agents/guardrail_async.py`):

   - Enforces business rules and constraints
   - Validates modifier selection limits
   - Verifies item availability and snooze status
   - Calculates accurate pricing

3. **Order Fulfillment** (`app/agents/fulfillment_async.py`):
   - Prepares the Deliverect payload
   - Submits orders to the POS system
   - Records orders in the database
   - Triggers SMS notifications via Celery

## Key Workflows

### Voice Call Workflow

1. **Setup Phase**:

   - Twilio initiates the call and connects to WebSocket endpoint `/ws/media/{call_sid}`
   - Twilio sends 'connected' and 'start' events to establish the media stream
   - System initializes the FSM and agent orchestrator
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
   - Essential environment variables (must be set in Render dashboard):
     - `DATABASE_URL`: PostgreSQL connection string
     - `OPENAI_API_KEY`: For OpenAI Realtime API access
     - `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`: For Twilio integration
     - `DELIVERECT_API_KEY`: For Deliverect POS integration
     - `STRIPE_API_KEY` (if payment processing is enabled)

2. **Docker Configuration**:
   - FastAPI with Uvicorn and async workers
   - Support for non-blocking WebSocket operations
   - PostgreSQL and Redis containers
   - Custom Dockerfile with multi-stage build for optimized deployments

3. **CI/CD Pipeline**:
   - Tests run on PR and push
   - Deploys to staging from `staging` branch
   - Deploys to production from `main` branch
   - Automated fixes applied during build via `fix_render_deploy.sh`

4. **Render-specific Adaptations**:
   - Custom `fastapi_render_entrypoint.sh` script to handle initialization
   - Environment-aware database URL transformation for asyncpg
   - Compatibility layer for SQLAlchemy models (see `compat_models.py`)
   - Headless mode enforcement for server environments

## Development Guide

### Development Architecture

```
app/
├── api/                    # API endpoints
│   ├── api_v1/             # API version 1 routes
│   │   ├── endpoints/      # Endpoint modules
│   │   └── api.py          # API router
│   └── voice_async.py      # Voice WebSocket handler
├── agents/                 # Agent components
│   ├── base_async.py       # Base async agent implementation
│   ├── cart_async.py       # Async cart management agent
│   ├── factory_async.py    # Async agent factory
│   └── ...                 # Other specialized async agents
├── db/                     # Database components
│   ├── crud_menu_async.py  # Async CRUD operations for menu
│   ├── session_async.py    # Async database session setup
│   └── ...                 # Other CRUD modules
├── models/                 # Database models
│   ├── menu_async.py       # Async menu models
│   ├── order_async.py      # Async order models
│   └── ...                 # Other model modules
├── schemas/                # Pydantic schemas
│   ├── menu.py             # Menu schemas
│   ├── order.py            # Order schemas
│   └── ...                 # Other schema modules
└── utils/                  # Shared utilities
    ├── fsm_async.py        # Async finite state machine
    ├── agent_orchestration_async.py  # Async agent orchestration
    ├── realtime_audio_async.py  # Async OpenAI Realtime client
    └── ...                 # Other utility modules
```

### FastAPI Implementation

1. **main.py**:
   - Entry point for the application
   - FastAPI app configuration
   - Lifespan events for startup/shutdown
   - Router registration

2. **app/api/voice_async.py**:
   - WebSocket handler for Twilio media streams
   - Manages bidirectional audio between Twilio and OpenAI
   - Processes transcripts and handles agent responses

3. **app/utils/realtime_audio_async.py**:
   - Provides async wrapper for OpenAI Realtime API
   - Handles audio format conversion
   - Manages session lifecycle

### Common Tasks

- **Run in Development**: `uvicorn app.main:app --reload`
- **Run Tests**: `pytest tests/e2e/test_async_voice_flow.py`
- **Rebuild Docker**: `./force_rebuild.sh && ./restart_docker.sh`
- **Check Logs**: `docker logs -f redbarsushi-app-1`
- **Deploy to Staging**: Push changes to the `staging` branch
- **Deploy to Production**: Push changes to the `main` branch
- **Fix Render Deployment Issues**: `./fix_render_deploy.sh`
- **Check WebSocket Connections**: `python websocket_test_client.py`

### Deployment and Fixes

1. **Render Deployment Process**:
   - Code is pushed to GitHub repository
   - Render builds the application using `Dockerfile` and `render.yaml` configuration
   - Deployment fixes applied automatically via `fix_render_deploy.sh`
   - Environment variables injected from Render dashboard

2. **Known Issues and Fixes**:
   - **Database Connectivity**: Ensure `DATABASE_URL` is properly set and formatted
   - **SQLAlchemy Compatibility**: Use `compat_models.py` for transitioning from Flask-SQLAlchemy to async SQLAlchemy
   - **JSONB Detection**: Use `jsonb_helper.py` for database-dialect aware JSONB column configuration
   - **WebSocket Handling**: Carefully manage task cancellation and resource cleanup
   - **Environment Variables**: Ensure Twilio, OpenAI, and Deliverect credentials are set

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
   - **WebSocket Connection Failures**:
     - Graceful error handling for client disconnections
     - Automatic task cleanup and resource release
     - Proper WebSocket close code selection based on error type
   - **OpenAI API Timeouts**:
     - Configurable request timeouts with fallback strategies
     - Retry logic with exponential backoff for transient issues
     - Session recreation for persistent errors
   - **Twilio Connection Issues**:
     - Proper detection of Twilio connection loss
     - Safe reconnection strategies with WebSocket protocol
     - Call preservation mechanisms when possible

2. **Runtime Errors**:
   - **Agent Processing Failures**:
     - Monitored execution with error boundaries
     - Fallback to general responses on agent-specific errors
     - Complete error logging for diagnosis
   - **Tool Execution Errors**:
     - Isolated tool execution to prevent cascade failures
     - Tool-specific error handlers with standardized reporting
     - Default responses for failed tool calls
   - **Database Connectivity Issues**:
     - Connection pool management with health checks
     - Graceful request failure with user-friendly messages
     - Retry logic for transient database errors

3. **Recovery Strategies**:
   - **Graceful Degradation**:
     - Feature-specific fallbacks that maintain core functionality
     - User experience preservation with appropriate messaging
     - Progressive reduction of capabilities based on error severity
   - **Session Preservation**:
     - Persistent session state with Redis for recovery
     - Conversation context maintenance across reconnections
     - Order state preservation during system instability
   - **Monitoring and Alerting**:
     - Structured logging with context for easy debugging
     - Error rate monitoring with severity classification
     - Automated alerts for critical system failures

## Best Practices

1. **Code Organization**:
   - Keep files under 500 lines
   - Use modular, well-documented components
   - Follow established patterns for new features
   - Separate concerns with specialized agents and utilities

2. **Error Handling**:
   - Provide meaningful error messages
   - Use appropriate WebSocket close codes
   - Log errors with sufficient context
   - Implement graceful degradation strategies
   - Ensure proper resource cleanup in error cases

3. **Performance**:
   - Optimize database queries using async SQLAlchemy
   - Use async/await for all I/O-bound operations
   - Implement proper connection pooling 
   - Use caching with Redis for frequently accessed data
   - Stream audio in small chunks with minimal buffering

4. **Database Operations**:
   - Use the async session factory and dependency injection
   - Properly close all database sessions
   - Handle transaction boundaries explicitly
   - Use SQLAlchemy 2.0 style with async/await patterns
   - Avoid N+1 query problems with proper relationship loading

5. **WebSocket Handling**:
   - Maintain single responsibility per asyncio task
   - Use proper exception handling within tasks
   - Ensure all tasks are properly cancelled on cleanup
   - Implement keep-alive mechanisms for long connections
   - Handle reconnection scenarios gracefully

6. **Deployment Considerations**:
   - Always set required environment variables in Render dashboard
   - Use the fix_render_deploy.sh script to apply necessary fixes
   - Keep Docker images optimized with multi-stage builds
   - Ensure model compatibility between SQLAlchemy versions

## System Configuration and Startup

### Environment Variables

The system relies on environment variables for configuration. Key variables include:

```
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/redbarsushi
TEST_DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/redbarsushi_test

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# OpenAI
OPENAI_API_KEY=sk-...                                 # Required for all API calls
OPENAI_REALTIME_MODEL=gpt-4o-realtime-preview-2024-10-01  # Realtime model version
OPENAI_REALTIME_VOICE=shimmer                         # Voice for TTS

# Twilio
TWILIO_ACCOUNT_SID=AC...                              # Required for Twilio API calls
TWILIO_AUTH_TOKEN=...                                 # Required for Twilio auth
TWILIO_PHONE_NUMBER=+1...                             # Phone number for outbound calls/SMS

# Deliverect
DELIVERECT_CHANNEL_NAME=redbarsushi                   # Channel identifier
DELIVERECT_API_KEY=...                                # Required for Deliverect API calls
DELIVERECT_CLIENT_ID=...                              # Required for Deliverect authentication
DELIVERECT_CLIENT_SECRET=...                          # Required for Deliverect authentication
DELIVERECT_BASE_URL=https://api.staging.deliverect.com  # API endpoint

# Application Settings
APP_SECRET_KEY=...                                    # For session security
FLASK_ENV=staging|production                          # Environment type
FASTAPI_ENV=staging|production                        # FastAPI environment type
FORCE_HEADLESS=true                                   # For server environments
LOG_LEVEL=INFO
VOICE_HANDLER=realtime                                # Voice processing mode
```

### Configuration System

The application uses Pydantic's `BaseSettings` for configuration management:

1. **Config Module** (`app/config.py`):
   - Loads environment variables with proper validation
   - Provides defaults where appropriate
   - Ensures required values are present
   - Converts types automatically (strings to booleans, ints, etc.)

2. **Environment Detection**:
   - Automatically detects Render environment
   - Sets appropriate defaults based on environment
   - Configures headless mode for server deployment
   - Adapts database connection parameters based on environment

### Starting the Application

The application can be started with the following commands:

1. **Start the FastAPI server**:

   ```
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

   or in debug mode:

   ```
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Start the Celery worker**:

   ```
   celery -A app.celery_app worker --loglevel=INFO
   ```

3. **Start with Docker**:
   ```
   ./start_docker.sh
   ```

### Database Initialization

On first run, the database needs to be initialized:

1. Create the database: `createdb redbarsushi`
2. Run migrations: `python -m app.db.init_db`
3. Initialize menu data: `python -m app.db.seed_db`

## WebSocket Implementation Details

The WebSocket implementation for voice processing follows these key patterns:

1. **TwiML Generation**:
   - Generates TwiML with `<Connect><Stream>` elements for bidirectional audio
   - Sends the CallSid to the WebSocket URL in the format: `wss://hostname/ws/media/{call_sid}`
   - Configures proper track and stream name for media handling

2. **WebSocket Handler**:
   - Implements a handler function using FastAPI's WebSocket support
   - Uses asyncio tasks for concurrent operations and event processing
   - Establishes bidirectional connection between Twilio and OpenAI Realtime API
   - Forwards audio from Twilio to OpenAI and responses back to Twilio
   - Handles WebSocket lifecycle properly with appropriate close codes
   - Properly manages resource cleanup on connection termination

3. **Connection Reliability**:
   - Implements heartbeat mechanism to keep connections alive
   - Uses extensive error handling and logging for connection diagnostics
   - Gracefully handles WebSocket closures and reconnection attempts
   - Maintains session context across connection interruptions

4. **Realtime Audio SDK**:
   - Provides async WebSocket implementation for OpenAI Realtime API
   - Handles audio format conversion between Twilio and OpenAI
   - Manages OpenAI Realtime API session configuration
   - Processes events from OpenAI and converts them to application events

### WebSocket Stability Enhancements (May 2025)

Several critical fixes have been implemented to enhance WebSocket stability:

1. **Method Naming Consistency**:
   - Added robust `request_response` method to ensure compatibility between handlers and the OpenAI client
   - Implemented connection state validation before TTS requests
   - Added detailed logging with call SID context for improved debugging

2. **WebSocket Connection Management**:
   - Fixed the "cannot call recv while another coroutine is already waiting" error by using the safe `async for message in self.websocket` pattern
   - Implemented proper task tracking with the `is_processing_loop_active` flag
   - Separated connection closure handling for normal vs. abnormal disconnects
   - Added specific handling for OpenAI API key errors

3. **Task Lifecycle Management**:
   - Enhanced task tracking to prevent resource leaks
   - Implemented graceful task termination with timeout
   - Added state flags for clean loop termination
   - Improved error classification for different error scenarios

4. **API Key Validation**:
   - Added proactive detection for test/dummy API keys
   - Enhanced error reporting for invalid keys
   - Improved logging to clearly identify key-related issues

5. **Testing & Verification**:
   - Added comprehensive test script (`test_realtime_client.py`) to verify WebSocket implementation
   - Created detailed documentation in `FIX_SUMMARY.md` and `WEBSOCKET_FIX_CHANGES.md`
   - Added step-by-step debugging instructions for WebSocket issues

These improvements ensure a more reliable WebSocket connection between Twilio, the FastAPI server, and the OpenAI Realtime API, addressing previous issues with connection handling, method naming, and task management.