# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Critical Rules

- FILES MUST NOT BE LONGER THAN 1000 LINES LONG
- NEVER IMPLEMENT FALLBACKS UNLESS SPECIFICALLY ASKED
- WHEN IT COMES TO SPECIFIC API RELATED TASKS REFER TO MCP CONTEXT OR THIS DOCUMENT DO NOT MAKE UP ANYTHING
- WE HAVE 2 ENVIRONMENTS: STAGING AND PRODUCTION. ALL ENVIRONMENTS ARE DEPLOYED USING RENDER WITH THEIR OWN ENVIRONMENT VARIABLES
- NEVER create files unless absolutely necessary - ALWAYS prefer editing existing files
- NEVER proactively create documentation files (*.md) or README files unless explicitly requested

## Common Development Commands

### Running the Application
```bash
# Local development with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Start Celery worker (in separate terminal)
celery -A celery_app_fastapi worker --loglevel=INFO

# Docker development (recommended)
./start_docker.sh

# View Docker logs
docker logs -f redbarsushi-app-1
```

### Database Operations
```bash
# Initialize database (Docker)
docker exec -it redbarsushi-app-1 python init_db.py

# Seed menu data
docker exec -it redbarsushi-app-1 python seed_menu_db.py

# Check database connection
docker exec -it redbarsushi-app-1 python test_db_connection.py
```

### Testing Commands
```bash
# Run unit and integration tests
pytest tests/unit tests/integration -v

# Run a specific test file
pytest tests/integration/test_fsm_orchestration.py -v

# Run E2E tests (staging environment only)
export FASTAPI_ENV=staging
pytest tests/e2e -v

# Run a single test
pytest tests/e2e/test_conversationrelay_fsm.py::test_complete_order_flow -v -s
```

### Linting and Type Checking
```bash
# Run linter (if configured)
ruff check app/

# Run type checker (if configured)  
mypy app/
```

### Docker Management
```bash
# Rebuild and restart
./force_rebuild.sh && ./restart_docker.sh

# Clean volumes and restart
./clean_docker_volumes.sh
./restart_docker.sh

# Stop all containers
docker-compose down
```

### Deployment
```bash
# Deploy to staging
git push origin staging

# Deploy to production  
git push origin main

# Fix Render deployment issues
./fix_render_deploy.sh
```

## Project Overview

RedBarSushiAI is an AI-powered voice ordering system that enables customers to place orders over the phone using natural language. It uses a multi-agent architecture with real-time audio processing through FastAPI and WebSockets.

## High-Level Architecture

The system follows a multi-agent architecture where specialized AI agents handle different aspects of the conversation, coordinated by a Finite State Machine (FSM) and orchestrator. Voice interactions use either ConversationRelay (webhook-based) or WebSocket mode for real-time audio processing with OpenAI's Realtime API.

### Key Architecture Components

#### Database Layer (Async SQLAlchemy 2.0)
- **Engine**: `app/db_async.py` - Async engine with connection pooling, auto-converts URLs to asyncpg format
- **Sessions**: Dependency injection via `get_db()`, proper lifecycle management
- **Key Models**:
  - `MenuItem`: PLU field is critical for POS integration, tracks availability and snooze status
  - `MenuNameVariant`: Maps natural language ("cali roll") to PLUs for better matching
  - `Order`: Links to Deliverect via `deliverect_channel_order_id`, tracks status and timestamps
  - `MenuModifier`: Individual modifier options with PLUs and price changes
  - `MenuModifierGroup`: Groups modifiers with selection rules (min/max)
  - `Location`: Store configuration, Deliverect credentials, business hours
- **Relationships**:
  - Many-to-many between items and modifier groups
  - One-to-many between orders and order items
  - Cascade deletes for data integrity
- **Compatibility**: `app/compat_models.py` handles Flask-SQLAlchemy legacy code
- **CRUD Operations**: `app/db/crud_menu_async.py` and `crud_order_async.py` for async DB operations

#### Multi-Agent Architecture
Specialized AI agents handle different conversation aspects:
- **Frontline** (`app/agents/frontline_async_ai.py`): 
  - Main conversation coordinator
  - Handles greetings, general queries, and delegation
  - Manages conversation flow and handoffs
  - Tools: `handoff_to_specialist`, `escalate_to_human`
- **Menu** (`app/agents/menu_async_enhanced.py`):
  - Answers menu questions and dietary restrictions
  - Checks item availability and snooze status
  - Provides recommendations and descriptions
  - Tools: `get_menu_items`, `check_availability`, `search_menu`
- **Cart** (`app/agents/cart_async.py`):
  - Parses natural language orders into structured items
  - Manages cart state and modifications
  - Handles quantities and ambiguity resolution
  - Tools: `add_to_cart`, `remove_from_cart`, `update_quantity`
- **Guardrail** (`app/agents/guardrail_async.py`):
  - Validates business rules and constraints
  - Checks modifier limits (min/max selections)
  - Calculates accurate pricing with modifiers
  - Tools: `validate_order`, `check_modifier_rules`
- **Fulfillment** (`app/agents/fulfillment_async.py`):
  - Collects delivery/pickup information
  - Submits orders to Deliverect POS
  - Records orders in database
  - Tools: `submit_order`, `send_confirmation`
- **Escalation** (`app/agents/escalation_async.py`):
  - Manages human handoff when needed
  - Preserves conversation context
  - Provides staff with order details
  - Tools: `transfer_to_human`, `send_context`

#### Voice Processing Modes
1. **ConversationRelay** (webhook-based, recommended):
   - `app/api/conversation_relay/handler.py` - Main webhook
   - Reliable delivery, built-in retries
   - Simplified audio processing

2. **WebSocket** (real-time, lower latency):
   - `app/api/voice/websocket.py` - WebSocket handler
   - Direct connection to OpenAI Realtime API
   - Bidirectional audio streaming

#### FSM (Finite State Machine)
Conversation flow management via states:
- **States**: 
  - `GREETING`: Initial state, collects customer name
  - `MAIN_MENU`: Presents options (order, inquire, staff)
  - `ORDERING`: Building cart, adding items
  - `VALIDATION`: Checking business rules
  - `CONFIRMATION`: Review order details
  - `FULFILLMENT`: Collect delivery/payment info
  - `COMPLETION`: Order submitted successfully
  - `ESCALATION`: Human handoff needed
  - `ERROR_RECOVERY`: Handle errors gracefully
- **Events**: Triggers for state transitions
  - `CUSTOMER_GREETED`, `ORDER_STARTED`, `MENU_INQUIRY`
  - `CART_UPDATED`, `ORDER_VALIDATED`, `ORDER_CONFIRMED`
  - `DETAILS_PROVIDED`, `ORDER_COMPLETED`, `ESCALATION_REQUESTED`
- **Core**: `app/fsm/core.py` - State definitions and transition rules
- **Handlers**: `app/fsm/handlers/` - State-specific behavior
  - Each handler implements `handle()` method for state logic
  - Handlers can trigger events to transition states
  - Context preserved across state transitions
- **Manager**: `app/utils/fsm_async.py` - FSM lifecycle and persistence
  - Creates and manages FSM instances per call
  - Stores state in Redis for persistence
  - Handles concurrent FSM operations

#### Agent Orchestration
- **Factory**: `app/agents/factory_async.py` - Creates and manages agents
- **Orchestrator**: `app/utils/agent_orchestration_async.py` - Coordinates agents based on FSM state
- **Intent Detection**: `app/utils/intent_detector_async.py` - LLM-based, no hardcoded keywords

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

The menu system uses a database-backed architecture with intelligent matching:

### Menu Data Model
1. **Hierarchical Structure**:
   - Categories → Items → Modifier Groups → Modifiers
   - Each level has Deliverect IDs and PLUs
   - Supports combos, variants, and nested modifiers

2. **Database Storage** (`app/db/crud_menu_async.py`):
   - PostgreSQL as persistent source of truth
   - Async operations for performance
   - Automatic sync from Deliverect webhooks
   - Menu validation and integrity checks

3. **Menu Matching System** (`app/utils/menu_matcher_cache_async.py`):
   - **Three-tier Progressive Strategy**:
     1. **Exact Match**: Direct PLU or normalized name lookup (fastest)
     2. **Fuzzy Match**: Levenshtein distance for typos/variations
     3. **AI Match**: GPT-4 semantic understanding for complex queries
   - **Variant Handling**: Maps colloquial names to canonical items
   - **Context Awareness**: Uses previous items to improve matching
   - **Caching**: Redis cache for performance optimization

4. **Availability Management**:
   - Real-time availability checking
   - Snooze functionality with timestamps
   - Business hours validation
   - Stock level tracking (if enabled)

## Order Processing

Orders flow through a sophisticated multi-stage pipeline:

### 1. Natural Language Parsing (`app/agents/cart_async.py`)
- **Intent Recognition**: Identifies add/remove/modify intents
- **Item Extraction**: Parses items and quantities from speech
- **Modifier Parsing**: Extracts customizations and preferences
- **Ambiguity Resolution**: Interactive clarification for unclear items
- **Examples**:
  - "I'll have two California rolls" → 2x California Roll
  - "Can I get a salmon roll with no wasabi, extra ginger" → Salmon Roll + modifiers
  - "Actually, make that three rolls" → Updates last item quantity

### 2. Cart State Management
- **Redis Storage**: Maintains cart state per session
- **Structure**:
  ```json
  {
    "items": [
      {
        "plu": "CALI_ROLL_001",
        "name": "California Roll",
        "quantity": 2,
        "modifiers": [
          {"plu": "NO_WASABI", "name": "No Wasabi"}
        ]
      }
    ],
    "customer_name": "John",
    "order_type": "pickup"
  }
  ```

### 3. Order Validation (`app/agents/guardrail_async.py`)
- **Business Rules**:
  - Minimum order amount
  - Delivery radius restrictions
  - Operating hours validation
  - Maximum item quantities
- **Modifier Rules**:
  - Min/max selection enforcement
  - Mutual exclusivity checks
  - Price adjustment validation
- **Availability Checks**:
  - Item availability status
  - Snooze period validation
  - Stock level verification

### 4. Price Calculation
- **Base Price**: Item prices from database
- **Modifier Adjustments**: Add modifier price changes
- **Quantity Multiplication**: Apply quantities
- **Tax Calculation**: Based on location settings
- **Delivery Fees**: If applicable

### 5. Order Submission (`app/agents/fulfillment_async.py`)
- **Deliverect Payload Formation**:
  ```json
  {
    "channelOrderId": "RBS-20240115-001",
    "orderType": 1,  // 1=pickup, 2=delivery
    "customer": {
      "name": "John Doe",
      "phone": "+1234567890"
    },
    "items": [
      {
        "plu": "CALI_ROLL_001",
        "quantity": 2,
        "price": 1295,  // cents
        "modifiers": [...]
      }
    ]
  }
  ```
- **POS Integration**: Direct submission to Deliverect
- **Database Recording**: Store order details
- **Confirmation**: SMS via Twilio/Celery

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
   - Keep files under 1000 lines
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

## Important Architectural Patterns

### 1. Async-First Design
- All I/O operations use async/await
- Database queries use AsyncSession
- API calls use httpx or aiohttp
- WebSocket operations are fully async
- No blocking operations in request handlers

### 2. Dependency Injection
- FastAPI's dependency system for:
  - Database sessions (`get_db()`)
  - Redis connections
  - Agent instances
  - Configuration objects
- Clean separation of concerns
- Easy testing with mock dependencies

### 3. Error Handling Strategy
- Custom exception classes for different error types
- Graceful degradation for non-critical failures
- User-friendly error messages
- Comprehensive logging for debugging
- Automatic retries with exponential backoff

### 4. State Management
- Redis for ephemeral state (cart, FSM)
- PostgreSQL for persistent data
- No in-memory state in handlers
- Session affinity not required
- Horizontal scaling ready

### 5. Security Considerations
- Environment variables for secrets
- No hardcoded credentials
- API key validation
- Request rate limiting
- Input sanitization

## Testing Strategy

### 1. Unit Tests (`tests/unit/`)
- Test individual components in isolation
- Mock external dependencies
- Fast execution (<1s per test)
- High code coverage target (>80%)

### 2. Integration Tests (`tests/integration/`)
- Test component interactions
- Use test database and Redis
- Mock external APIs (OpenAI, Twilio, Deliverect)
- Verify data flow and transformations

### 3. E2E Tests (`tests/e2e/`)
- Complete workflow testing
- Real services in staging environment
- Voice flow simulation
- Order submission verification
- Performance benchmarking

### 4. Test Fixtures (`tests/conftest.py`)
- Async test client setup
- Database migrations and seeding
- Mock services configuration
- Cleanup after tests

## Performance Optimizations

### 1. Database Optimizations
- Connection pooling with SQLAlchemy
- Indexed queries on frequently accessed fields
- Eager loading to prevent N+1 queries
- Query result caching in Redis
- Batch operations where possible

### 2. Caching Strategy
- Redis for menu data caching
- TTL-based cache invalidation
- Cache warming on startup
- Lazy loading for large datasets
- Cache aside pattern implementation

### 3. Async Concurrency
- Concurrent API calls with asyncio.gather()
- Task-based processing for audio
- Non-blocking I/O throughout
- Proper task cancellation handling
- Resource cleanup on shutdown

### 4. Audio Processing
- Streaming in small chunks (20ms)
- Minimal buffering for low latency
- Efficient base64 encoding/decoding
- Audio format optimization (μ-law)
- Concurrent audio pipeline tasks

## Monitoring and Observability

### 1. Logging
- Structured JSON logging
- Correlation IDs for request tracking
- Log levels: DEBUG, INFO, WARNING, ERROR
- Centralized log aggregation
- Performance metrics in logs

### 2. Health Checks
- `/health` endpoint for system status
- Database connectivity check
- Redis connectivity check
- External API availability
- Resource usage monitoring

### 3. Metrics
- Request latency tracking
- Error rate monitoring
- Agent performance metrics
- Audio processing statistics
- Business metrics (orders, revenue)

## Common Debugging Scenarios

### 1. WebSocket Connection Issues
- Check OpenAI API key validity
- Verify network connectivity
- Review WebSocket logs for errors
- Test with `websocket_test_client.py`
- Check task lifecycle management

### 2. Menu Matching Problems
- Verify menu data in database
- Check Redis cache state
- Review matching algorithm logs
- Test with specific examples
- Clear cache if needed

### 3. Order Submission Failures
- Validate Deliverect credentials
- Check order payload format
- Review validation errors
- Verify POS connectivity
- Test with minimal payload

### 4. FSM State Issues
- Check Redis for FSM state
- Review state transition logs
- Verify event handling
- Test state handlers individually
- Reset FSM if stuck

## Code Style Guidelines

### 1. Python Style
- Follow PEP 8 conventions
- Use type hints throughout
- Descriptive variable names
- Docstrings for public methods
- Maximum line length: 120 chars

### 2. Async Patterns
- Always use `async def` for I/O operations
- Proper `async with` for resources
- `await` all coroutines
- No synchronous blocking calls
- Handle task cancellation

### 3. Error Messages
- User-friendly for customer-facing errors
- Technical details in logs only
- Consistent error format
- Actionable error messages
- Avoid exposing internals

### 4. Testing Conventions
- Test files mirror source structure
- One test class per source class
- Descriptive test method names
- Arrange-Act-Assert pattern
- Comprehensive edge case coverage