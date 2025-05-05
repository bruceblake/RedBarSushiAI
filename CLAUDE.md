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

Voice interactions are managed through an orchestrated multi-agent architecture with real-time audio processing:

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

1. **Orchestrated Voice Implementation** (`app/routes/voice_orchestrated.py`):

   - Real-time audio processing via WebSockets
   - Multi-agent architecture with specialized roles
   - Finite State Machine (FSM) for conversation flow
   - Manages agent handoffs and escalations
   - Handles audio streaming and VAD events

2. **Agent Roles**:

   - **Frontline Agent**: Manages overall call flow and delegates to specialists
   - **Menu Agent**: Handles menu inquiries and availability
   - **Cart Agent**: Manages order items and modifications
   - **Fulfillment Agent**: Processes order completion and payment
   - **Guardrail Agent**: Enforces constraints and business rules
   - **Escalation Agent**: Manages handoff to human staff when needed

3. **Silence & VAD Handling**:
   - Phase-specific timeouts based on conversation context
   - Voice Activity Detection with adaptive timeouts
   - Progressive fallbacks with configurable retry limits
   - State-aware reprompting strategies

### Menu Management

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

### Order Processing

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

   - Twilio initiates the call and invokes the WebSocket endpoint
   - System initializes the orchestrated voice agent
   - Media stream established for real-time audio processing

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

   - Raw audio data streams via WebSocket in 20ms packets
   - Audio converted from μ-law (8kHz) to PCM16 (16kHz)
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
   - Main agent maintains conversation context

4. **Response Generation**:
   - Text responses generated by appropriate agent
   - Text-to-Speech converts responses to audio
   - Audio streamed back to customer in real-time

### Menu Management Workflow

1. **Menu Data Import**:
   - Menu data is imported from JSON file (`menu_data.json`)
   - System loads detailed menu structure during initialization
   - Manual updates to menu data are processed through admin interface
2. **Menu Data Processing**:
   - System parses categories, items, modifiers, and modifier groups
   - Each entity is identified by PLU and stored in PostgreSQL
   - System builds `menu_name_variants` table mapping natural language to PLUs
3. **Menu Data Access**:
   - Menu data is cached in Redis for quick access
   - If Redis fails, system falls back to PostgreSQL
   - If PostgreSQL fails, system falls back to in-memory cache

### Database Migration

The system was migrated from file-based to database storage:

1. **Migration Process** (`database_menu_integration.py`):

   - Initialize database tables
   - Transfer data from JSON to database
   - Verify migration success
   - Update configuration

2. **Storage Layer** (`app/utils/menu_db_store.py`):
   - Redis caching for performance
   - Memory fallback for reliability
   - Database as source of truth

## Real-time Features

The system includes real-time processing features:

1. **Real-time Audio** (`app/utils/realtime_audio.py`):

   - WebSocket-based audio streaming
   - Real-time speech-to-text processing
   - Real-time text-to-speech responses

2. **WebSocket Endpoints**:
   - `/api/ws/speech-to-text`: Real-time transcription
   - `/api/ws/text-to-speech`: Real-time audio generation
   - `/api/ws/conversation`: Full conversation processing

## Conversation Context

The system maintains conversation context using Redis:

1. **Conversation Store** (`app/utils/conversation_store.py`):

   - Redis-backed conversation history
   - Memory fallback if Redis unavailable
   - Automatic session expiration

2. **Menu Questions**:
   - Maintains context between questions
   - Remembers previous inquiries
   - Provides contextual responses

## Testing Approach

The project uses a comprehensive testing strategy:

1. **Unit Tests** (`tests/unit/`):

   - Test individual components in isolation
   - Fast execution with mocked dependencies

2. **Integration Tests** (`tests/integration/`):

   - Test interactions between components
   - Database integration testing

3. **E2E Tests** (`tests/e2e/`):
   - Full workflow testing
   - Simulated voice calls
   - Complete order processing

## Deployment

The application is deployed on Render with these features:

1. **Environment Configuration**:

   - Production vs. Staging environments
   - Automatic database initialization
   - Redis connection handling

2. **CI/CD Pipeline**:
   - Tests run on PR and push
   - Deploys to staging from `staging` branch
   - Deploys to production from `main` branch

## Development Architecture

### Code Organization

```
app/
├── agents/                 # Agent components
│   ├── base.py             # Base agent implementation
│   ├── cart.py             # Cart management agent
│   ├── escalation.py       # Human handoff agent
│   ├── factory.py          # Basic agent factory
│   ├── factory_with_orchestration.py  # Enhanced orchestration factory
│   ├── frontline.py        # Primary conversational agent
│   ├── frontline_with_orchestration.py  # Orchestrated frontline agent
│   ├── fulfillment.py      # Order fulfillment agent
│   ├── guardrail.py        # Validation and constraint agent
│   └── menu.py             # Menu information agent
├── models/                 # Database models
│   ├── base.py             # Base model class
│   ├── location.py         # Location settings and details
│   ├── menu.py             # Menu items, modifiers, categories
│   └── order.py            # Order and item tracking
├── routes/                 # API endpoints
│   ├── location.py         # Location management
│   ├── menu.py             # Menu endpoints
│   ├── order.py            # Order processing
│   ├── order_ai.py         # AI-powered order resolution
│   ├── realtime.py         # Real-time audio endpoints
│   ├── voice.py            # Basic voice handler
│   └── voice_orchestrated.py  # Orchestrated voice implementation
└── utils/                  # Shared utilities
    ├── agent_orchestration.py  # Orchestration components
    ├── conversation_store.py   # Session state management
    ├── deliverect/         # Deliverect API interaction
    ├── menu_matcher_db.py  # Menu lookup and matching
    ├── realtime_audio.py   # Audio processing
    └── voice_controller.py # Voice handling coordination
```

### Agent Architecture

The system uses a modular agent architecture with specialized components:

- **Base Agent**: Core functionality shared by all agents
- **Frontline Agent**: Main entry point and dispatcher
- **Specialized Agents**: Domain-specific handlers
- **Factory Pattern**: Configurable agent creation
- **Orchestration Layer**: Coordination between agents

### Style Conventions

- Follow PEP 8 for Python code
- Use Black for code formatting
- Use Ruff for linting
- Use pytest for testing

### Common Tasks

- **Run Tests**: `pytest`
- **Format Code**: `black app tests`
- **Lint Code**: `ruff check app tests`
- **Run Dev Server**: `FLASK_DEBUG=1 FLASK_APP=run.py flask run`
- **Run Celery**: `celery -A celery_app worker --loglevel=INFO`
- **Test Voice Flow**: `VOICE_HANDLER=orchestrated pytest tests/e2e/test_orchestrated_voice_flow.py`

## API Integrations

### Deliverect API Integration

The system integrates with Deliverect to manage menu data and process orders:

1. **Base URL**: `https://api.staging.deliverect.com`

2. **Key Identifiers**:

   - `channelName`: Scope identifier for API access
   - `channelLinkId`: Unique store instance identifier
   - `channelOrderId`: Application-generated unique order ID
   - `plu`: Product/modifier unique identifier (critical for order processing)

3. **Endpoints - Deliverect Integration**:

   - **Create Order**: `POST /{channelName}/order/{channelLinkId}`
     - Places a new order with structured payload containing items identified by PLU
     - Order status is determined through manual polling rather than webhooks
     - Success response (201) only indicates the request was valid, not POS acceptance

4. **Menu Data Structure**:

   - Menu data is received as a hierarchical JSON structure with these key components:
     - **Categories**: Groups of menu items (e.g., "Steak & Burgers", "Sides")
       - Contains `_id`, `name`, `posCategoryId`, and array of `subProducts` (item IDs)
     - **Products**: Dictionary mapping product ID to details
       - Contains `_id`, `name`, `description`, `price` (in cents), `plu`, `productType`
       - May include `isVariant`, `isCombo` for special product types
       - Products reference `subProducts` array of attached Modifier Group IDs
     - **ModifierGroups**: Dictionary mapping group ID to details
       - Contains `_id`, `name`, `plu`, `min`, `max`, `multiMax` to control selection rules
       - References array of `subProducts` (modifier IDs)
       - May include `isVariantGroup` for product variants (e.g., sizes)
     - **Modifiers**: Dictionary mapping modifier ID to details
       - Contains `_id`, `name`, `price` (differential price), `plu`, `parentId`
   - **Variants System**: Supports different product versions (e.g., sizes)
     - Base product marked with `isVariant: true`
     - Variant group marked with `isVariantGroup: true`
     - Individual variants set price differentials (e.g., +$3 for large size)
   - **MenuNameVariants**: System builds table mapping natural language to PLUs
     - Maps common terms (e.g., "fries", "coke") to specific menu item PLUs
     - Essential for translating customer speech to specific order items

5. **Order Structure**:

   - Order payload to Deliverect must follow specific format:
     - `channelOrderId`: Unique ID generated by our system (cannot be reused within 48 hours)
     - `orderType`: Integer indicating pickup (1), delivery (2), eat-in (3), or curbside (4)
     - `customer`: Object with customer details (name, phoneNumber, email)
     - `deliveryAddress`: Required for delivery orders (street, postcode, city, etc.)
     - `orderIsAlreadyPaid`: Boolean indicating if payment was handled
     - `payment`: Object with amount (in cents), type (0=card, 1=cash, 2=voucher, 3=online)
     - `items`: Array of ordered items, each with:
       - `plu`: Exact PLU identifier from menu data
       - `name`: Item name
       - `price`: Price in cents
       - `quantity`: Quantity ordered
       - `subItems`: Array of modifiers attached to this item (each with plu, name, price, quantity)
   - Orders can include additional fields:
     - `pickupTime`/`deliveryTime`: Estimated times in ISO 8601 format
     - `note`: General order notes
     - `discountTotal`: Total discount in cents
     - `deliveryCost`: Delivery fee in cents
     - `serviceFee`: Service charge in cents
     - `driverTip`/`tip`: Tips in cents
     - `bagFee`: Bag fee in cents (mandatory in some regions)

6. **Order Types and Status**:

   - Order Types:
     - `1`: Pick up
     - `2`: Delivery
     - `3`: Eat-in
     - `4`: Curbside
   - Order Status Codes:
     - `20`: Accepted (order confirmed by restaurant)
     - `70`: Ready for Pickup
     - `80`: Delivered
     - `100`: Cancellation Request
     - `110`: Canceled (successfully canceled)
   - Payment Types:
     - `0`: Credit card online
     - `1`: Cash
     - `2`: Voucher
     - `3`: Online payment

### OpenAI Assistants API Integration

The system uses OpenAI's Assistants API for conversation management:

1. **Key Components**:

   - **Assistant**: Configured AI personality with specific capabilities
   - **Thread**: Represents a single conversation
   - **Message**: User input or AI response
   - **Run**: Execution of the Assistant on a Thread

2. **Tool Integration**:

   - When the Assistant needs external data or actions, it requests specific tools with parameters
   - Backend executes these tools as local Python functions
   - Results are submitted back to the Assistant

3. **Essential Tools**:
   - `lookup_menu_item(item_name)`: Translates user requests to specific menu items by PLU
   - `get_restaurant_info(query)`: Retrieves static restaurant information
   - `add_item_to_cart(plu, quantity, modifiers)`: Updates the current order
   - `get_current_cart()`: Retrieves the current order state
   - `place_order(customer_details, delivery_details, order_type)`: Submits order to Deliverect

### Twilio API Integration

The system uses Twilio for voice communication:

1. **Voice Handling**:

   - Receives calls via webhooks to `/webhook/voice`
   - Generates TwiML with `<Say>`, `<Gather>`, and other commands
   - Uses callbacks with transcription results

2. **SMS Notifications**:
   - Sends order status updates via Twilio's REST API
   - Managed through Celery tasks for asynchronous processing

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

3. **Optional - Start Celery beat for scheduled tasks**:
   ```
   celery -A celery_app beat --loglevel=INFO
   ```

### Database Initialization

On first run, the database needs to be initialized:

1. Create the database: `createdb redbarsushi`
2. Run migrations: `python -m flask db upgrade`
3. Initialize menu data: `python -m flask seed-menu`

## Detailed API Specifications

### Deliverect API Details

#### Creating an Order

The system creates orders by posting to the Deliverect API:

```
POST /{channelName}/order/{channelLinkId}
```

**Request Body Example**:

```json
{
  "channelOrderId": "RBS-12345-ABCDE",
  "channelOrderDisplayId": "RBS-12345",
  "orderType": 1,
  "pickupTime": "2025-05-03T12:30:00Z",
  "courier": "restaurant",
  "customer": {
    "name": "John Doe",
    "phoneNumber": "+15551234567",
    "email": "john.doe@example.com"
  },
  "orderIsAlreadyPaid": true,
  "payment": {
    "amount": 2550,
    "type": 0
  },
  "note": "No soy sauce please",
  "items": [
    {
      "plu": "CALI-ROLL",
      "name": "California Roll",
      "price": 1200,
      "quantity": 1,
      "subItems": [
        {
          "plu": "EXTRA-AVO",
          "name": "Extra Avocado",
          "price": 150,
          "quantity": 1
        }
      ]
    },
    {
      "plu": "SPICY-TUNA",
      "name": "Spicy Tuna Roll",
      "price": 1200,
      "quantity": 1
    }
  ],
  "decimalDigits": 2
}
```

**Response**:

- `201 Created`: Order received by Deliverect (valid format)
- `400 Bad Request`: Invalid request format or data
- `401 Unauthorized`: Invalid authentication
- `404 Not Found`: Endpoint not found
- `500 Internal Server Error`: Deliverect server error

#### Polling for Order Status

Since webhooks are not used, the system polls for order status using:

```
GET /{channelName}/order/{channelLinkId}/{channelOrderId}
```

**Response Example**:

```json
{
  "orderId": "61e9c9f98e5e2b001c82eabc",
  "status": 20,
  "channelOrderId": "RBS-12345-ABCDE",
  "location": "61e9c9f98e5e2b001c82eabd",
  "channelLink": "61e9c9f98e5e2b001c82eabe"
}
```

**Status Codes**:

- `10`: Received (initial state)
- `20`: Accepted (confirmed by restaurant)
- `30`: In Preparation
- `40`: Prepared (ready for pickup/delivery)
- `70`: Ready for Pickup
- `80`: Delivered/Completed
- `90`: Rejected (order refused)
- `100`: Cancellation Request
- `110`: Canceled

### Agent Orchestration Architecture

The system uses a sophisticated agent orchestration architecture for managing complex interactions:

#### Agent Factory

```python
# Enhanced factory pattern with orchestration support
from app.agents.factory_with_orchestration import enhanced_agent_factory

# Create agents with proper initialization
frontline_agent = enhanced_agent_factory.create_agents()
```

#### Agent Graph

```python
# Create the agent relationship graph
agent_graph = AgentGraph()

# Register specialized agents
agent_graph.register_agent("menu", menu_agent)
agent_graph.register_agent("cart", cart_agent)
agent_graph.register_agent("fulfillment", fulfillment_agent)

# Define relationships and handoff patterns
agent_graph.add_edge("frontline", "menu", "menu_inquiry")
agent_graph.add_edge("frontline", "cart", "order_intent")
agent_graph.add_edge("cart", "fulfillment", "order_complete")
```

#### FSM Orchestrator

```python
# Define the conversation state machine
fsm_orchestrator = FSMOrchestrator()

# Configure state transitions
fsm_orchestrator.add_transition(FSMState.GREETING, FSMState.MAIN_MENU, "name_provided")
fsm_orchestrator.add_transition(FSMState.MAIN_MENU, FSMState.ORDERING, "order_intent")
fsm_orchestrator.add_transition(FSMState.ORDERING, FSMState.CONFIRMATION, "order_complete")

# Get current conversation state
current_state = fsm_orchestrator.get_current_state(session_id)
```

#### Agent Handoffs

```python
# Handle agent handoff from frontline to specialist
def handle_order_intent(session_id, user_input):
    # Frontline agent detects order intent
    cart_agent = agent_graph.get_agent("cart")

    # Execute handoff with context
    cart_response = cart_agent.process_input(
        session_id,
        user_input,
        context={"from_agent": "frontline"}
    )

    # Update FSM state
    fsm_orchestrator.transition(
        session_id,
        FSMState.ORDERING,
        reason="order_initiated"
    )

    return cart_response
```

### Twilio Integration

#### Media Streams API

The system uses Twilio's Media Streams API for real-time audio processing:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Start>
        <Stream url="wss://example.com/ws/media" track="inbound_track" />
    </Start>
    <Say voice="Polly.Amy-Neural">Welcome to Red Bar Sushi! How can I help you today?</Say>
    <Connect>
        <Stream url="wss://example.com/ws/media" track="outbound_track" />
    </Connect>
</Response>
```

#### WebSocket Audio Streaming

```python
@sock.route("/api/ws/orchestrated_conversation")
async def orchestrated_conversation(ws):
    """WebSocket endpoint for real-time conversation with orchestrated agents."""
    # Initialize the audio processor and agents
    audio_processor = get_audio_processor()
    frontline_agent = enhanced_agent_factory.create_agents()

    # Process streaming audio in real-time
    async for audio_chunk in receive_audio_stream():
        # Process with OpenAI Realtime API
        transcript = await audio_processor.process_audio_chunk(audio_chunk)

        # Forward to appropriate agent based on state
        response = frontline_agent.process_voice_input(session_id, transcript)

        # Generate TTS response and stream back
        audio_response = await text_to_speech(response)
        await ws.send(audio_response)
```

#### SMS Notifications

```python
@celery_app.task
def send_order_confirmation(order_id, customer_phone):
    """Send order confirmation via SMS."""
    # Get order details
    order = Order.query.get(order_id)

    # Format confirmation message
    message = (
        f"Thank you for ordering from Red Bar Sushi! "
        f"Your order #{order.id} has been received. "
        f"Estimated time: {order.estimated_time.strftime('%I:%M %p')}. "
        f"Total: ${order.total_price/100:.2f}"
    )

    # Send through Twilio
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    client.messages.create(
        body=message,
        from_=settings.TWILIO_PHONE_NUMBER,
        to=customer_phone
    )
```

## Database Schema Details

### Menu Tables

#### menu_categories

```sql
CREATE TABLE menu_categories (
    id SERIAL PRIMARY KEY,
    deliverect_category_id VARCHAR(255),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### menu_items

```sql
CREATE TABLE menu_items (
    id SERIAL PRIMARY KEY,
    category_id INTEGER REFERENCES menu_categories(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price INTEGER NOT NULL,
    plu VARCHAR(255) NOT NULL UNIQUE,
    deliverect_item_id VARCHAR(255),
    is_available BOOLEAN DEFAULT TRUE,
    is_combo BOOLEAN DEFAULT FALSE,
    is_variant BOOLEAN DEFAULT FALSE,
    image_url TEXT,
    snoozed_until TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### menu_modifier_groups

```sql
CREATE TABLE menu_modifier_groups (
    id SERIAL PRIMARY KEY,
    deliverect_group_id VARCHAR(255),
    name VARCHAR(255) NOT NULL,
    min_selection INTEGER DEFAULT 0,
    max_selection INTEGER DEFAULT 0,
    multi_max INTEGER DEFAULT 1,
    plu VARCHAR(255),
    is_variant_group BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### menu_modifiers

```sql
CREATE TABLE menu_modifiers (
    id SERIAL PRIMARY KEY,
    modifier_group_id INTEGER REFERENCES menu_modifier_groups(id),
    name VARCHAR(255) NOT NULL,
    price_change INTEGER NOT NULL,
    plu VARCHAR(255) NOT NULL,
    deliverect_modifier_id VARCHAR(255),
    is_available BOOLEAN DEFAULT TRUE,
    snoozed_until TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### item_modifier_groups

```sql
CREATE TABLE item_modifier_groups (
    id SERIAL PRIMARY KEY,
    menu_item_id INTEGER REFERENCES menu_items(id),
    modifier_group_id INTEGER REFERENCES menu_modifier_groups(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### menu_name_variants

```sql
CREATE TABLE menu_name_variants (
    id SERIAL PRIMARY KEY,
    variant_phrase VARCHAR(255) NOT NULL,
    canonical_name VARCHAR(255) NOT NULL,
    target_plu VARCHAR(255) NOT NULL REFERENCES menu_items(plu),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX menu_name_variants_phrase_idx ON menu_name_variants (variant_phrase);
```

### Order Tables

#### orders

```sql
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    deliverect_channel_order_id VARCHAR(255) UNIQUE,
    customer_phone VARCHAR(20) NOT NULL,
    customer_name VARCHAR(255),
    order_type INTEGER NOT NULL,
    status INTEGER DEFAULT 10,
    total_price INTEGER NOT NULL,
    placed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    estimated_time TIMESTAMP WITH TIME ZONE,
    delivery_address TEXT,
    notes TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### order_items

```sql
CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    menu_item_plu VARCHAR(255) REFERENCES menu_items(plu),
    name VARCHAR(255) NOT NULL,
    price INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### order_item_modifiers

```sql
CREATE TABLE order_item_modifiers (
    id SERIAL PRIMARY KEY,
    order_item_id INTEGER REFERENCES order_items(id),
    modifier_plu VARCHAR(255) REFERENCES menu_modifiers(plu),
    name VARCHAR(255) NOT NULL,
    price_change INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## State Management Architecture

### Finite State Machine (FSM)

The conversation flow is managed by a finite state machine to ensure consistent interactions:

```python
# FSM States
class FSMState(Enum):
    GREETING = "greeting"              # Initial state, getting customer name
    MAIN_MENU = "main_menu"            # Presenting main options (order, menu, etc.)
    MENU_INQUIRY = "menu_inquiry"      # Answering menu questions
    ORDERING = "ordering"              # Taking order details
    ITEM_CLARIFICATION = "item_clarification"  # Resolving ambiguous items
    VALIDATION = "validation"          # Validating order against constraints
    CONFIRMATION = "confirmation"      # Confirming complete order
    PAYMENT = "payment"                # Handling payment details
    FULFILLMENT = "fulfillment"        # Processing order with Deliverect
    FOLLOW_UP = "follow_up"            # Post-order interaction
    STAFF_HANDOFF = "staff_handoff"    # Escalation to human staff
    COMPLETION = "completion"          # Ending the conversation
```

### Slot Store

Structured data collected during the conversation is managed in a slot store:

```python
# Register slots for data collection
slot_store.register_slot("customer_name", required=True)
slot_store.register_slot("phone_number", required=True, validation=validate_phone)
slot_store.register_slot("delivery_address", required=False)
slot_store.register_slot("payment_method", required=True, options=["cash", "card"])

# Store and retrieve slot values
slot_store.set_slot(session_id, "customer_name", "John")
customer_name = slot_store.get_slot(session_id, "customer_name")

# Check if all required slots are filled
is_complete = slot_store.all_required_slots_filled(session_id)
```

### Redis Data Structures

#### Conversation Context Store

```
HSET conversation:{session_id}
    fsm_state "ordering"
    customer_name "John"
    last_utterance "I want to order sushi"
    silence_count 0
    agent_history "[{\"agent\":\"frontline\",\"time\":1714521140}]"
    last_activity_timestamp 1714521145
```

#### Cart Store

```
HSET cart:{session_id}
    json "{
        'items': [
            {
                'plu': 'CALI-ROLL',
                'name': 'California Roll',
                'price': 1200,
                'quantity': 1,
                'modifiers': [
                    {
                        'plu': 'EXTRA-AVO',
                        'name': 'Extra Avocado',
                        'price_change': 150,
                        'quantity': 1
                    }
                ]
            }
        ],
        'total_price': 1350,
        'order_type': 1,
        'modified_at': 1714521145
    }"
```

#### Menu Cache

```
# Fast item lookup by PLU
HSET menu:item:{plu} name "California Roll" price 1200 description "Crab, avocado, cucumber"

# Variant matching for natural language lookups
HSET menu:variants name:california_roll "CALI-ROLL"
HSET menu:variants name:cali_roll "CALI-ROLL"
HSET menu:variants name:crab_avocado_roll "CALI-ROLL"

# Menu structure for fast navigation
HSET menu:categories category:sushi_rolls items "[\"CALI-ROLL\",\"SPICY-TUNA\"]"

# Set cache TTL
EXPIRE menu:* 86400  # 24 hour cache
```

## Resilience Patterns

### Service Degradation Strategy

The system implements a graceful degradation strategy for service failures:

```python
class DegradationLevel(Enum):
    NONE = 0          # All systems operational
    MINOR = 1         # Some non-critical services degraded
    MODERATE = 2      # Critical services partially degraded
    SEVERE = 3        # Critical services severely degraded
    CATASTROPHIC = 4  # Complete system failure
```

### Database Connection Resilience

Database operations use retry logic with exponential backoff:

```python
@retry(
    retry=retry_if_exception_type(OperationalError),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    stop=stop_after_attempt(5),
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
def get_menu_items_with_retry():
    with Session() as session:
        return session.query(MenuItem).all()
```

### Redis Fallback Chain

The system implements a multi-level cache fallback strategy:

```python
def get_menu_item(plu):
    # Try Redis first (fastest)
    try:
        redis_result = redis_client.hgetall(f"menu:item:{plu}")
        if redis_result:
            return redis_result
    except RedisError:
        logger.warning(f"Redis unavailable, falling back to database for {plu}")

    # Fall back to database if Redis fails
    try:
        db_result = MenuItem.query.filter_by(plu=plu).first()
        if db_result:
            return db_result.to_dict()
    except SQLAlchemyError:
        logger.error(f"Database unavailable, falling back to memory cache for {plu}")

    # Fall back to memory cache as last resort
    return memory_cache.get(f"menu:item:{plu}")
```

### Voice Processing Fallbacks

Real-time audio processing implements progressive fallbacks:

1. **Real-time Streaming**: Primary approach using OpenAI Realtime API
2. **Chunk-based Processing**: Fallback for partial streaming failures
3. **Complete Utterance Processing**: Fallback for streaming failures
4. **Text-only Mode**: Ultimate fallback if audio processing fails

### Agent Handling

The orchestration system includes error handling at multiple levels:

1. **Agent-level Recovery**: Each agent has error handling for its domain
2. **Orchestrator Recovery**: FSM can reset to safe states on agent failures
3. **Conversation Repair**: System can reconstruct context after failures
4. **Automatic Escalation**: Serious errors trigger escalation to human staff

## Celery Tasks

The system uses Celery for asynchronous processing:

```python
@celery_app.task
def send_order_confirmation(order_id, customer_phone):
    """Send SMS confirmation after order is placed"""
    try:
        # Get order details from database
        order = get_order_by_id(order_id)

        # Format message
        message = f"Thank you for ordering from Red Bar Sushi! Your order #{order.id} "
        message += f"has been received and will be ready around {order.estimated_time.strftime('%I:%M %p')}. "
        message += f"Total: ${order.total_price/100:.2f}"

        # Send SMS via Twilio
        send_sms_notification(customer_phone, message)

        # Update order record to indicate confirmation sent
        update_order_confirmation_sent(order_id)

    except Exception as e:
        logger.error(f"Failed to send order confirmation: {str(e)}")
        # Retry up to 3 times with exponential backoff
        self.retry(exc=e, countdown=2 ** self.request.retries * 60, max_retries=3)
```

```python
@celery_app.task
def poll_order_status(order_id, channel_order_id):
    """Poll Deliverect for order status updates"""
    try:
        # Check current status in our database
        current_status = get_order_status(order_id)

        # Skip polling if order is in a terminal state
        terminal_states = [80, 90, 110]  # Delivered, Rejected, Canceled
        if current_status in terminal_states:
            return

        # Poll Deliverect for status
        deliverect_status = get_deliverect_order_status(channel_order_id)

        # If status changed, update in our database
        if deliverect_status != current_status:
            update_order_status(order_id, deliverect_status)

            # If status warrants customer notification, send SMS
            if deliverect_status in [20, 70, 80, 110]:  # Accepted, Ready, Delivered, Canceled
                send_status_update_notification.delay(order_id)

        # Schedule next polling based on current status
        # Poll more frequently for active orders, less for orders near completion
        if deliverect_status < 40:  # Before preparation is completed
            poll_order_status.apply_async(args=[order_id, channel_order_id], countdown=60)  # Check again in 1 minute
        else:
            poll_order_status.apply_async(args=[order_id, channel_order_id], countdown=180)  # Check again in 3 minutes

    except Exception as e:
        logger.error(f"Failed to poll order status: {str(e)}")
        self.retry(exc=e, countdown=30, max_retries=5)
```

## Menu Matching Algorithm

The system uses a three-tier approach for menu matching:

### 1. Exact Match

```python
def find_exact_match(item_name):
    """Find exact match in menu_name_variants table"""
    normalized_name = item_name.lower().strip()

    # Query database for exact match
    variant = MenuNameVariant.query.filter_by(variant_phrase=normalized_name).first()
    if variant:
        return MenuItem.query.filter_by(plu=variant.target_plu).first()

    return None
```

### 2. Fuzzy Matching

```python
def find_fuzzy_match(item_name, threshold=80):
    """Find fuzzy match using Levenshtein distance"""
    normalized_name = item_name.lower().strip()

    # Get all menu name variants
    variants = MenuNameVariant.query.all()

    # Calculate similarity scores
    matches = []
    for variant in variants:
        ratio = fuzz.ratio(normalized_name, variant.variant_phrase)
        if ratio >= threshold:
            matches.append((variant, ratio))

    # Sort by similarity score
    matches.sort(key=lambda x: x[1], reverse=True)

    # Return best match if any
    if matches:
        best_match = matches[0][0]
        return MenuItem.query.filter_by(plu=best_match.target_plu).first()

    return None
```

### 3. AI-Powered Matching

```python
def find_ai_match(item_name, context=None):
    """Use OpenAI to match menu item based on contextual understanding"""
    # Create prompt for OpenAI
    prompt = f"The customer ordered: '{item_name}'\n\n"
    prompt += "Based on our menu items below, what is the most likely menu item they want?\n\n"

    # Add menu items for context
    menu_items = MenuItem.query.all()
    for item in menu_items:
        prompt += f"- {item.name}: {item.description}\n"

    # Add customer context if available
    if context:
        prompt += f"\nAdditional context: {context}\n"

    prompt += "\nReturn only the exact name of the menu item from the list above."

    # Query OpenAI
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=50,
        temperature=0.3
    )

    # Extract item name from response
    ai_item_name = response.choices[0].text.strip()

    # Find item in database
    return MenuItem.query.filter(
        func.lower(MenuItem.name) == func.lower(ai_item_name)
    ).first()
```

## Important Notes

- The system has been migrated from file-based to database storage
- Redis is used for caching and conversation store
- OpenAI Assistants API is used for NLP and voice processing
- Twilio is used for phone communication and SMS notifications
- Deliverect is used for order management and POS integration
- PLU identifiers are critical for mapping between system and Deliverect
- The system maintains parallel data structures in PostgreSQL that mirror Deliverect's menu format
- Order status polling is used instead of webhooks for integration with Deliverect
