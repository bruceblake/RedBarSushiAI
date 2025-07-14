# RedBarSushiAI Complete System Architecture Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture Components](#architecture-components)
3. [Voice Processing Flow](#voice-processing-flow)
4. [Multi-Agent System](#multi-agent-system)
5. [Hierarchical State Machine (HSM)](#hierarchical-state-machine-hsm)
6. [Tool Calling System](#tool-calling-system)
7. [Database Architecture](#database-architecture)
8. [External Service Integrations](#external-service-integrations)
9. [Complete Conversation Flow](#complete-conversation-flow)
10. [Agent Orchestration System](#agent-orchestration-system)
11. [Error Handling & Recovery](#error-handling--recovery)
12. [Performance Optimizations](#performance-optimizations)
13. [Development & Deployment](#development--deployment)
14. [Debugging Guide](#debugging-guide)
15. [Known Issues & Incomplete Features](#known-issues--incomplete-features)

## System Overview

RedBarSushiAI is a sophisticated AI-powered voice ordering system for a sushi restaurant that uses a multi-agent architecture with finite state machine conversation management. The system is built with FastAPI and integrates with Twilio for voice handling, OpenAI for AI intelligence, and Deliverect for POS integration.

### Core Architectural Principles

1. **AI-First Philosophy**: All agents use OpenAI's GPT models for intelligence with NO hardcoded patterns or keyword matching
2. **Finite State Machine (FSM) Orchestration**: Conversation flow is managed by an HSM (Hierarchical State Machine)
3. **Tool-Based Agent Communication**: Agents use structured tool calls for all operations
4. **Async-First Design**: All operations are asynchronous for optimal performance
5. **Specialist Delegation**: Each agent has clearly defined expertise areas

## Architecture Components

### Main Entry Points

**File**: `/app/main.py`
- **FastAPI Application**: Creates the main FastAPI app with comprehensive configuration
- **Key Features**:
  - Correlation ID middleware for request tracing
  - Static file serving at `/static`
  - Environment detection (staging vs production)
  - Health check endpoints (`/healthcheck`, `/db-debug`)
  - Database migration endpoints for maintenance
  - Route listing endpoints for debugging

**Key Endpoints**:
- `/` - Root endpoint with environment info
- `/healthcheck` - Basic health status
- `/voice/` and `/voice/webhook` - Twilio TwiML webhooks
- `/conversation-relay/{call_sid}` - WebSocket for voice processing
- `/api/deliverect/*` - POS integration endpoints
- `/api/menu/*` - Menu management
- `/api/order/*` - Order processing

### Configuration System

**File**: `/app/config.py`
- **Pydantic Settings**: Environment variable loading with validation
- **Key Settings**:
  - Database connection strings
  - Redis configuration
  - OpenAI API settings
  - Twilio credentials
  - Deliverect POS integration
  - Performance tuning parameters

## Voice Processing Flow

### 1. Phone Call Initiation

**Process Flow**:
```
Twilio Incoming Call → /voice/webhook (TwiML endpoint)
```

**File**: `/app/api/voice/twiml.py`

**Process**:
1. **Webhook Reception**: Twilio sends POST request to `/voice/webhook` with call parameters
2. **Call SID Generation**: Twilio provides unique `CallSid` for session tracking
3. **TwiML Generation**: System generates ConversationRelay TwiML with WebSocket URL
4. **WebSocket URL Construction**: Creates `wss://host/conversation-relay/{call_sid}`

**TwiML Output**:
```xml
<Response>
    <Connect>
        <ConversationRelay url="wss://host/conversation-relay/{call_sid}"
                          interruptible="any"
                          ttsProvider="ElevenLabs"
                          transcriptionProvider="Google"
                          language="en-US">
            <Parameter name="call_sid" value="{call_sid}" />
            <Parameter name="customer_phone" value="{caller}" />
        </ConversationRelay>
    </Connect>
</Response>
```

### 2. ConversationRelay WebSocket Setup

**File**: `/app/api/voice/conversation_relay.py`

**Process**:
1. **WebSocket Accept**: Twilio ConversationRelay connects to `/conversation-relay/{call_sid}`
2. **Handler Creation**: `ConversationRelayHandler` instance created for this call
3. **Session Setup**: Receives setup message with session parameters
4. **Orchestrator Initialization**: Creates async agent orchestrator for conversation management

**Setup Message Flow**:
```python
# Setup message from ConversationRelay
{
    "type": "setup",
    "sessionId": "session_id",
    "customParameters": {...},
    "language": "en-US",
    "ttsProvider": "ElevenLabs"
}
```

### 3. Real-Time Voice Processing

**Message Types**:
- **Setup**: Initial session configuration
- **Prompt**: User speech-to-text transcripts
- **Interruption**: User interruption events
- **Error**: System error notifications

**Response Flow**:
```
Customer Speech → ConversationRelay STT → Transcript → Orchestrator → AI Processing → TTS → Customer
```

## Multi-Agent System

### Agent Hierarchy

#### **Base Agent Infrastructure**

**BaseAsyncAgent** (`/app/agents/base_async.py`)
- **Role**: Foundation class for all agents
- **Key Features**:
  - Specialist registration and delegation system
  - Context management and conversation history
  - Tool execution framework
  - Policy agent integration
- **Methods**: `process_input()`, `execute_tool()`, `delegate_to_specialist()`, `register_specialist()`

**AIIntelligenceMixin** (`/app/agents/ai_mixin.py`)
- **Role**: Adds AI capabilities to agents
- **Key Features**:
  - OpenAI API integration with connection pooling
  - Dynamic system prompt building
  - Tool calling and response processing
  - Streaming response support
  - Intent understanding capabilities
- **Critical Methods**: `process_with_ai()`, `understand_intent()`, `_build_messages()`

#### **Primary Agent Roles**

**Frontline Agent** (`/app/agents/frontline_async_ai.py`)
- **Role**: Main conversation orchestrator and customer interface
- **AI Instructions**: Natural, warm conversation management with state-aware responses
- **Tools Available**:
  - `ask_menu_specialist`: Delegates menu questions to Menu Agent
  - `add_to_cart`: Adds items via Cart Agent
  - `update_customer_info`: Captures customer details
  - `get_cart_summary`: Retrieves order status
  - `proceed_to_checkout`: Initiates order completion
  - `confirm_order`: Finalizes orders
  - `escalate_to_human`: Transfers to staff

**State Handlers**:
- `_handle_greeting()`: Name capture and welcome
- `_handle_main_menu()`: General conversation and menu inquiries
- `_handle_ordering()`: Order building and item addition
- `_handle_validation()`: Order verification
- `_handle_confirmation()`: Final order approval

**Menu Agent Enhanced** (`/app/agents/menu_async_enhanced.py`)
- **Role**: Menu knowledge specialist with database integration
- **AI Instructions**: Enthusiastic food expert with accurate menu information
- **Tools Available**:
  - `lookup_menu_item`: AI-powered item search with database integration
  - `list_categories`: Retrieves menu categories
  - `get_items_by_category`: Category-based item listings
  - `search_menu`: Keyword-based menu search
  - `get_item_details`: Detailed item information including modifiers
  - `get_popular_items`: Recommendation system
  - `check_item_availability`: Real-time availability checking

**Key Intelligence**: Uses sophisticated AI-driven menu matching instead of hardcoded patterns

**Cart Agent** (`/app/agents/cart_async.py`)
- **Role**: Order building and cart management specialist
- **AI Instructions**: Concise cart operations with accurate item handling
- **Tools Available**:
  - `lookup_menu_item`: Delegates to Menu Agent for verification
  - `add_item_to_cart`: Adds items with PLU codes and modifiers
  - `remove_from_cart`: Item removal
  - `modify_cart_item`: Item quantity/modifier changes
  - `get_current_cart`: Cart status retrieval
  - `suggest_additions`: Upselling recommendations
  - `clear_cart`: Complete cart reset

**Critical Feature**: ALL menu item identification is delegated to Menu Agent - Cart Agent never guesses items

**Validation Agent** (`/app/agents/validation_async.py`)
- **Role**: Business rule enforcement and order completeness verification
- **AI Instructions**: Thorough validation specialist focusing on critical issues
- **Tools Available**:
  - `validate_order_for_checkout`: Complete order validation against database constraints
  - `validate_single_item`: Individual item validation
  - `check_allergen_conflicts`: Allergen safety verification

**Validation Types**:
- Required modifier selection checking
- Item availability verification
- Business rule compliance
- Maximum/minimum quantity enforcement

#### **Support Agents**

**Guardrail Agent** (`/app/agents/guardrail_async.py`)
- **Role**: Basic business rule validation
- **Function**: Simpler validation layer for basic constraints

**Escalation Agent** (`/app/agents/escalation_async.py`)
- **Role**: Human handoff management
- **Function**: Manages transfers to human staff with context preservation
- **Status**: **INCOMPLETE** - Contains placeholder logic, missing HUMAN_HANDOFF_NUMBER configuration

**Fulfillment Agent** (`/app/agents/fulfillment_async.py`)
- **Role**: Order submission to POS (Deliverect)
- **Function**: Final order processing and customer notifications

### Agent Coordination System

**Agent Factory** (`/app/agents/factory_async.py`)
- **Role**: Agent instantiation and dependency injection
- **Features**:
  - Database session management for data-dependent agents
  - AI/rule-based agent selection based on settings
  - Specialist registration automation
  - Agent caching and reuse

### Agent Communication Patterns

#### **Tool-Based Delegation**
- Frontline Agent delegates menu questions to Menu Agent via `ask_menu_specialist` tool
- Cart Agent delegates item lookups to Menu Agent for verification
- All inter-agent communication uses structured tool calls

#### **AI-Driven Intelligence**
- **NO hardcoded patterns**: All decision-making uses AI intelligence
- Dynamic system prompts based on conversation state
- Context-aware responses using conversation history
- Intent detection for state transitions

## Hierarchical State Machine (HSM)

### FSM Core Structure

**File**: `/app/fsm/core.py`

### State Hierarchy

The FSM uses a hierarchical structure with parent-child relationships:

#### Root States:
1. **INITIAL** - System startup state
2. **ACTIVE** - Main conversation flow (has substates)
3. **COMPLETION** - Conversation end state
4. **ERROR_RECOVERY** - Error handling (has substates)

#### ACTIVE Substates (Main Flow):
- **GREETING** - Initial customer greeting
- **MAIN_MENU** - Main navigation/menu presentation
- **ORDERING** - Order building process (hierarchical with substates)
- **VALIDATION** - Order validation
- **CONFIRMATION** - Order confirmation (hierarchical with substates)
- **FULFILLMENT** - Order processing and delivery (hierarchical with substates)
- **FOLLOW_UP** - Post-order follow-up
- **ESCALATION** - Human handoff

#### ORDERING Substates (Hierarchical):
- **ORDERING_BROWSING** - Menu browsing
- **ORDERING_MENU_INQUIRY** - Menu questions
- **ORDERING_ITEM_CUSTOMIZATION** - Item customization
- **ORDERING_CART_REVIEW** - Cart review
- **ORDERING_VALIDATION** - Order validation
- **ORDERING_OUT_OF_STOCK** - Handle unavailable items
- **ORDERING_UPSELL_SUGGESTION** - Upselling opportunities
- **ORDERING_ITEM_MODIFICATION** - Modify existing cart items

#### Global Superstates (Can be entered from anywhere):
- **GLOBAL_INQUIRY** - Information requests (hours, location, policies, menu)
- **GLOBAL_HELP** - Help requests
- **GLOBAL_CANCELLATION** - Order cancellation

### State Transition Logic

#### Event-Driven Transitions

State transitions are triggered by **HSMEvent** objects that contain:
- Event name (from ConversationHSMEvents)
- Optional event data

#### Event Detection Process

**File**: `/app/utils/intent_detector_async.py`

The system uses **AI-powered intent detection** (no hardcoded keywords):

1. **Global Command Detection**: First checks for global commands (CANCEL, HELP, REPEAT, etc.)
2. **State-Specific Intent Detection**: Uses OpenAI GPT-4o-mini with state-specific prompts
3. **Intent-to-Event Mapping**: Maps detected intents to HSM events

#### State-Specific Intent Mappings:

**GREETING State:**
- `USER_PROVIDES_NAME` → User giving their name
- `START_ORDER` → Skip to ordering
- `REQUEST_ESCALATION` → Need help

**MAIN_MENU State:**
- `START_ORDER` → Begin ordering
- `REQUEST_MENU_INFO` → Menu questions
- `REQUEST_ESCALATION` → Human assistance

**ORDERING State:**
- `ADD_ITEM` → Adding items
- `REMOVE_ITEM` → Removing items
- `MODIFY_ITEM` → Changing items
- `COMPLETE_ORDER` → Finish ordering

### State Handlers

Each state has a dedicated handler inheriting from `HSMStateHandler`:

#### Key State Behaviors:

**INITIAL State** (`/app/fsm/handlers/initial.py`)
- **Entry**: System initialization
- **Transitions**: `START_CONVERSATION` → GREETING

**GREETING State** (`/app/fsm/handlers/greeting.py`)
- **Entry**: Generates greeting message via frontline agent
- **Behavior**: Collects customer name or skips to ordering
- **Transitions**: 
  - `USER_PROVIDES_NAME` → MAIN_MENU
  - `START_ORDER` → ORDERING

**MAIN_MENU State** (`/app/fsm/handlers/main_menu.py`)
- **Entry**: Generates main menu response
- **Behavior**: Navigation hub for ordering or information
- **Transitions**:
  - `START_ORDER` → ORDERING
  - `REQUEST_MENU_INFO` → Stay in MAIN_MENU

**ORDERING States** (`/app/fsm/handlers/ordering.py`)
- **Superstate Entry**: Initializes cart, tracks timing
- **Hierarchical Navigation**: Between browsing, customization, cart review
- **Global Commands**: CLEAR_CART, VIEW_CART, CHECKOUT

**VALIDATION State** (`/app/fsm/handlers/validation.py`)
- **Purpose**: Validates order completeness and correctness
- **Transitions**:
  - `ORDER_VALID` → CONFIRMATION
  - `ORDER_INVALID` → ORDERING

**CONFIRMATION State** (`/app/fsm/handlers/confirmation.py`)
- **Entry**: Generates order summary for final confirmation
- **Transitions**:
  - `CONFIRM_ORDER` → FULFILLMENT
  - `MODIFY_ORDER` → ORDERING
  - `REJECT_ORDER` → ORDERING

### State Storage and Persistence

**File**: `/app/fsm/state_store.py`

#### Redis-Based Storage
- **State Path**: Stores complete hierarchy from root to leaf
- **Context Data**: Maintains conversation context
- **History Tracking**: Keeps last 20 state transitions
- **Session Management**: 24-hour expiry

#### Key Storage Methods:
- `get_current_state_path()` - Get full state hierarchy
- `set_state_path()` - Update state configuration
- `push_state()` / `pop_state()` - Stack operations
- `is_in_state()` - Check if in specific state

### FSM Manager

**File**: `/app/fsm/manager.py`

#### Core Responsibilities:
1. **State Registration**: Registers all handlers and definitions
2. **Event Processing**: Processes events through bubble-up mechanism
3. **Transition Execution**: Manages state entry/exit lifecycle
4. **Hierarchy Management**: Handles parent-child relationships

#### Transition Algorithm:
1. **Event Reception**: Receives HSMEvent for processing
2. **Bubble-Up Processing**: Starts from leaf state, bubbles up to root
3. **Handler Invocation**: Calls state-specific event handlers
4. **Transition Calculation**: Determines exit/enter paths
5. **State Lifecycle**: Executes exit → transition → enter sequence

## Tool Calling System

### Tool Architecture Overview

The RedBarSushiAI system implements a sophisticated multi-agent architecture with AI-driven tool calling coordination. The system uses OpenAI's function calling capabilities combined with a hierarchical agent structure where the Frontline Agent orchestrates specialist agents through tool delegation.

### Agent Tool Mapping

#### **Frontline Agent (AsyncFrontlineVoiceAgentAI)**
Primary orchestrator with delegation tools:

```python
Tools = [
    "ask_menu_specialist",     # Delegates to Menu Agent
    "add_to_cart",            # Delegates to Cart Agent  
    "update_customer_info",   # Updates customer context
    "get_cart_summary",       # Delegates to Cart Agent
    "proceed_to_checkout",    # State transition trigger
    "confirm_order",          # Order finalization
    "escalate_to_human"       # Human handoff
]
```

**Delegation Pattern**:
```python
async def _ask_menu_specialist(self, question: str):
    menu_agent = await async_agent_factory.get_agent("menu", db=self._db_session)
    response = await menu_agent.process_with_ai(question, context, use_tools=True)
    return response
```

#### **Menu Agent (AsyncMenuAgentEnhanced)**
Database and menu intelligence specialist:

```python
Tools = [
    "lookup_menu_item",       # AI-driven fuzzy search
    "list_categories",        # Database query
    "get_items_by_category",  # Filtered database query
    "search_menu",           # Full-text search
    "get_item_details",      # PLU-based lookup with modifiers
    "get_popular_items",     # Recommendation engine
    "check_item_availability" # Real-time availability check
]
```

**Database Operations**:
- Uses `app.db.crud_menu_async` for async SQLAlchemy operations
- AI-powered fuzzy matching with confidence scoring
- Intelligent disambiguation for ambiguous queries

#### **Cart Agent (AsyncCartAgent)**
Order management and validation specialist:

```python
Tools = [
    "lookup_menu_item",      # Delegates to Menu Agent
    "add_item_to_cart",      # Core cart operations
    "remove_from_cart",      # Item removal
    "modify_cart_item",      # Quantity/modifier changes
    "get_current_cart",      # Cart state retrieval
    "suggest_additions",     # AI-driven upselling
    "clear_cart"            # Cart reset
]
```

**Critical Cart Operations**:
```python
async def _add_item_to_cart(self, plu: str, quantity: int, modifiers: List, special_instructions: str):
    # 1. Validate item exists via database
    item = await async_menu_db_store.get_item_by_plu(plu, self.db)
    
    # 2. Validate modifiers
    for mod in modifiers:
        modifier = await async_menu_db_store.get_modifier_by_plu(mod_plu, self.db)
    
    # 3. Update conversation store
    conversation = await async_agents_conversation_store.get_conversation(call_sid)
    cart = conversation.get("context", {}).get("cart", {"items": [], "total_price": 0})
    
    # 4. Calculate pricing with modifiers
    # 5. Save to Redis via conversation store
```

### Tool Execution Flow

#### 1. **AI Request Processing**
```python
async def process_with_ai(self, input_text: str, context: Dict, use_tools: bool = True):
    # Build conversation history
    messages = self._build_messages(input_text, context)
    
    # Make OpenAI call with tools
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=self.tools if use_tools else None,
        tool_choice="auto"
    )
    
    # Process tool calls
    if response.choices[0].message.tool_calls:
        return await self._process_ai_response(response, context)
```

#### 2. **Tool Call Execution**
```python
async def _process_ai_response(self, response, context):
    tool_results = []
    
    for tool_call in response.choices[0].message.tool_calls:
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)
        
        # Execute tool via agent's execute_tool method
        result = await self.execute_tool(tool_name, tool_args)
        tool_results.append({"tool": tool_name, "result": result})
    
    # Get final AI response incorporating tool results
    return await self._get_final_response_after_tools(response, tool_results, context)
```

#### 3. **Inter-Agent Delegation**
```python
# Frontline Agent delegating to Cart Agent
async def _add_to_cart(self, item_name: str, quantity: int, modifiers: List):
    # 1. Look up item via Cart Agent (which delegates to Menu Agent)
    lookup_result = await self.specialists["cart"].execute_tool(
        "lookup_menu_item", {"item_name": item_name}
    )
    
    # 2. Add to cart with PLU
    if lookup_result.get("found"):
        result = await self.specialists["cart"].execute_tool(
            "add_item_to_cart", {
                "plu": lookup_result["item"]["plu"],
                "quantity": quantity,
                "modifiers": modifiers
            }
        )
```

## Database Architecture

### Database Configuration

**File**: `/app/db_async.py`
- **SQLAlchemy 2.0 Async**: Uses `asyncpg` for PostgreSQL
- **Connection Pooling**: Optimized with configurable pool settings
- **Migration System**: Automatic schema updates on startup

### Core Models

#### Menu System

**File**: `/app/models/menu_async.py`

```
MenuCategory (categories)
    ↓ (one-to-many)
MenuItem (menu_items) ←→ MenuModifierGroup (modifier_groups)
                              ↓ (many-to-many)
                          MenuModifier (menu_modifiers)
MenuNameVariant (menu_name_variants) → PLU mapping
```

**Key Relationships**:
- **MenuItem ← PLU → MenuNameVariant**: Enables intelligent menu matching
- **JSONB Fields**: Flexible modifier storage and order metadata
- **PLU Codes**: Primary integration point with Deliverect POS

#### Order System

**File**: `/app/models/order_async.py`

```
Order (orders)
    ↓ (one-to-many)
OrderItem (order_items)
    ↓ (one-to-many)
OrderItemModifier (order_item_modifiers)
```

### Storage Systems
- **PostgreSQL**: Primary data store (port 5432)
- **Redis**: Session state, caching, FSM persistence (port 6379)
- **JSONB Fields**: Flexible metadata storage in PostgreSQL

### Database Operations by Tools

#### **Menu Database Operations**
Via `app.db.crud_menu_async`:
- `get_all_menu_items()` - Paginated retrieval with relationships
- `get_item_by_plu()` - Primary key lookup
- `search_menu_items()` - Full-text search
- `get_items_by_category()` - Category filtering
- `get_all_categories()` - Category enumeration

#### **Cart State Management**
Via `app.utils.conversation_store_async`:
- `get_conversation()` - Session state retrieval
- `save_conversation()` - Cart persistence
- `add_message()` - Conversation history
- `clear_cart()` - Cart reset

#### **Order Processing**
Via `app.db.crud_order_async`:
- `create_order()` - Order object creation
- `update_order_status()` - Status transitions
- `get_order_by_id()` - Order retrieval

## External Service Integrations

### Twilio Integration
- **ConversationRelay**: AI-powered voice processing with built-in STT/TTS
- **WebSocket Protocol**: Real-time bidirectional communication
- **TwiML Generation**: Dynamic call routing and configuration
- **SMS Notifications**: Via Celery background tasks

### OpenAI Integration

**File**: `/app/config.py`
- **GPT-4 for Intelligence**: All conversation processing and intent detection
- **No Hardcoded Logic**: System requires AI for all business logic
- **Connection Pooling**: Optimized client pool for performance
- **Model Configuration**: Configurable models and token limits

### Deliverect POS Integration

**File**: `/app/services/deliverect_service.py`

```python
Tools/Operations:
- get_full_menu()          # Menu synchronization
- parse_and_cache_menu()   # Redis caching
- get_cached_product()     # Fast lookups
- check_item_availability() # Real-time status
- submit_order()           # Order transmission
```

**API Endpoints**:
- `GET /{channel}/menu/{link_id}` - Menu data
- `POST /{channel}/orders` - Order submission
- `GET /{channel}/orders/{id}` - Order status

### Redis Operations

**File**: `/app/redis_async.py`
- Menu caching: `menu:product:{plu}`, `menu:modifier:{plu}`
- Session state: Conversation data with cart state
- Cache TTL: 3600 seconds (1 hour) for menu data

## Complete Conversation Flow

### Typical Successful Ordering Conversation

#### Step 1: Initial Greeting (INITIAL → ACTIVE.GREETING)
**Trigger**: `START_CONVERSATION` event
**State**: `INITIAL` → `ACTIVE.GREETING`

**Process**:
1. HSM transitions to GREETING state
2. Frontline agent generates AI-powered greeting
3. Response sent via ConversationRelay TTS
4. Conversation history stored in Redis

**Response Example**: "Hi! This is Sarah from Red Bar Sushi. How can I help you today?"

#### Step 2: Customer Provides Name (GREETING → MAIN_MENU)
**Input**: "Hi, this is John"
**Trigger**: `USER_PROVIDES_NAME` event detected by AI intent detector
**State**: `ACTIVE.GREETING` → `ACTIVE.MAIN_MENU`

**Process**:
1. **AI Intent Detection**: LLM analyzes transcript for name provision
2. **Tool Calling**: Frontline agent calls `update_customer_info` tool
3. **State Transition**: HSM moves to MAIN_MENU state
4. **Context Update**: Customer name stored in conversation context
5. **Database Persistence**: Customer info saved to conversation store

#### Step 3: Menu Inquiry (MAIN_MENU → ORDERING.MENU_INQUIRY)
**Input**: "What sushi rolls do you have?"
**Trigger**: `REQUEST_MENU_INFO` event
**State**: `ACTIVE.MAIN_MENU` → `ACTIVE.ORDERING.MENU_INQUIRY`

**Process**:
1. **AI Analysis**: Frontline agent determines menu query intent
2. **Tool Delegation**: Calls `ask_menu_specialist` tool
3. **Menu Agent Processing**: Menu agent queries database for sushi rolls
4. **Database Query**: Async SQLAlchemy queries menu_items table
5. **Response Generation**: AI-formatted menu information
6. **State Management**: Remains in ORDERING context for follow-up questions

#### Step 4: Item Selection (ORDERING.MENU_INQUIRY → ORDERING.CART_REVIEW)
**Input**: "I'll take a California roll"
**Trigger**: `ADD_ITEM` event
**State**: `ACTIVE.ORDERING.MENU_INQUIRY` → `ACTIVE.ORDERING.CART_REVIEW`

**Process**:
1. **Item Recognition**: Menu agent uses AI to match "California roll" to database PLU
2. **Cart Addition**: Cart agent processes `add_to_cart` tool call
3. **Price Calculation**: Real-time pricing from database
4. **Availability Check**: Verifies item is not snoozed/out-of-stock
5. **Order Confirmation**: Confirms addition and provides cart summary

#### Step 5: Order Completion (ORDERING → CONFIRMATION)
**Input**: "That's all for today"
**Trigger**: `COMPLETE_ORDER` event
**State**: `ACTIVE.ORDERING` → `ACTIVE.CONFIRMATION`

**Process**:
1. **Completion Detection**: AI recognizes order completion intent
2. **Cart Validation**: Ensures cart has items and valid pricing
3. **Order Summary**: Generates complete order review
4. **Confirmation Request**: Asks customer to confirm order details

#### Step 6: Order Confirmation (CONFIRMATION → FULFILLMENT)
**Input**: "Yes, that's correct"
**Trigger**: `CONFIRM_ORDER` event
**State**: `ACTIVE.CONFIRMATION` → `ACTIVE.FULFILLMENT`

**Process**:
1. **Order Processing**: Creates order record in PostgreSQL
2. **Deliverect Integration**: Submits order to POS system
3. **Payment Processing**: Handles payment information
4. **Delivery/Pickup**: Coordinates fulfillment method
5. **Order Tracking**: Provides order status and timing

### Message Flow Architecture

```
Customer Speech → ConversationRelay STT → Transcript → Orchestrator
                                                          ↓
HSM State Transition ← Intent Detection ← AI Analysis ← Agent Selection
                                                          ↓
Database Operations ← Tool Execution ← Agent Processing ← Context Loading
                                                          ↓
Response Generation → Conversation Store → TTS → Customer Audio
```

### Key Components:

1. **Conversation Store**: Redis-based session management
2. **Database Layer**: Async SQLAlchemy with PostgreSQL
3. **AI Intelligence**: OpenAI GPT-4 for all decision making
4. **Tool System**: Function calling for database operations
5. **State Persistence**: HSM state stored in Redis
6. **Context Management**: Multi-layered context tracking

## Agent Orchestration System

### Agent Orchestrator (AsyncAgentOrchestrator)

**File**: `/app/utils/agent_orchestration_async.py`

The `AsyncAgentOrchestrator` serves as the central coordination point for all agent interactions. It maintains:

- **Agent Registry**: Manages instances of specialized agents (frontline, menu, cart, validation, fulfillment, escalation, guardrail)
- **Session Management**: Tracks active conversation sessions with metadata (start time, last activity, current state)
- **FSM Integration**: Coordinates with the Hierarchical State Machine for state transitions
- **Context Sharing**: Manages conversation context across agents and states

### process_voice_input Method Flow

```python
async def process_voice_input(call_sid, input_text, context) -> Dict[str, Any]:
```

**Complete Processing Flow:**

1. **Initialization & Session Management**
   - Initialize agents if not already done
   - Create/update session tracking
   - Initialize HSM for new sessions

2. **Conversation Store Management**
   - Add user message to conversation store
   - Load conversation history for context

3. **HSM State Processing**
   - Get current HSM state configuration
   - Handle first interaction trigger (START_CONVERSATION event)
   - Track state before HSM processing

4. **Global Command Detection**
   - Use AI-powered intent detection for global commands (REPEAT, START_OVER, GO_BACK, HELP, CANCEL)
   - Process special commands that don't map to FSM events
   - Handle confidence thresholds (≥0.8 for execution)

5. **Intent Detection & Event Processing**
   - Use AI to detect HSM events from transcript
   - Process events through HSM for state transitions
   - Handle errors with graceful degradation

6. **Agent Selection & Processing**
   - Select appropriate agent based on current HSM state
   - Process input with selected agent
   - Handle agent processing errors with AI-generated recovery

7. **Response Processing**
   - Extract actions from agent responses
   - Handle special actions (set_customer_name, TRANSFER_CALL)
   - Update conversation store and session state
   - Return comprehensive response with metadata

### Agent Selection Logic

#### Primary Selection Algorithm
The orchestrator uses a **state-based agent selection** approach:

```python
async def _process_with_appropriate_agent(current_state, input_text, context):
```

**Decision Tree:**
- **ESCALATION State** → Escalation Agent
- **All Other States** → Frontline Agent (default orchestrator)

#### Frontline Agent as Primary Coordinator
The Frontline Agent (`AsyncFrontlineVoiceAgentAI`) acts as the primary coordinator that:
- Handles most conversation states
- Delegates to specialist agents via tool calling
- Maintains conversation flow and context
- Uses AI intelligence for understanding and response generation

#### Specialist Agent Delegation
Specialist agents are accessed through tool calling patterns:
- **Menu queries** → Menu Agent via `ask_menu_specialist` tool
- **Cart operations** → Cart Agent via `add_to_cart`, `view_cart` tools
- **Order processing** → Validation Agent via validation tools

### Global Commands System

#### AI-Powered Detection
Global commands use sophisticated AI detection (`/app/utils/global_commands.py`):

```python
async def detect_command(input_text: str) -> Tuple[GlobalCommand, float]:
```

**Available Commands:**
- **REPEAT**: Repeat last assistant message
- **START_OVER**: Reset conversation and HSM state
- **GO_BACK**: Return to previous conversation step
- **HELP**: Provide assistance and options
- **CANCEL**: Cancel current order/conversation

#### Command Processing Priority
1. **High Priority**: Global commands (confidence ≥ 0.8) override normal flow
2. **Special Handling**: REPEAT, START_OVER, GO_BACK don't map to FSM events
3. **FSM Integration**: HELP and CANCEL map to HSM events

### Intent Detection System

#### AI-Driven Intent Recognition
The system uses `AsyncIntentDetector` (`/app/utils/intent_detector_async.py`) for intelligent intent detection:

**Process:**
1. **Global Command Check**: First check for global commands
2. **State-Specific Prompts**: Build prompts based on current HSM state
3. **LLM Processing**: Use GPT-4o-mini for fast, accurate intent detection
4. **Event Mapping**: Map detected intents to HSM events

**State-Specific Intent Mappings:**
- **GREETING**: USER_PROVIDES_NAME, START_ORDER, REQUEST_ESCALATION
- **MAIN_MENU**: START_ORDER, REQUEST_MENU_INFO, REQUEST_ESCALATION
- **ORDERING**: ADD_ITEM, REMOVE_ITEM, MODIFY_ITEM, COMPLETE_ORDER
- **CONFIRMATION**: CONFIRM_ORDER, MODIFY_ORDER, REJECT_ORDER

### Context Management

#### Multi-Layer Context System
Context flows through multiple layers:

1. **Session Context**: Call-specific information (call_sid, session metadata)
2. **Conversation History**: Message history from conversation store
3. **HSM Context**: State-specific context and transitions
4. **Agent Context**: Agent-specific context (customer name, order items)

#### Context Persistence
- **Redis Storage**: Primary storage for conversation history and state
- **Memory Fallback**: In-memory backup for Redis failures
- **Context Updates**: Real-time updates through conversation store

#### Context Sharing Mechanism
```python
# Load conversation history from store
conversation = await conversation_store.get_conversation(call_sid)
agent_context["conversation_history"] = conversation_history
agent_context["customer_name"] = stored_context.get("customer_name")
```

### Session Management

#### Session Lifecycle
1. **Initialization**: Create session entry in `active_sessions`
2. **HSM Setup**: Initialize HSM with initial state
3. **Activity Tracking**: Update last activity on each interaction
4. **Cleanup**: Automatic cleanup of inactive sessions

#### Session State Tracking
```python
active_sessions[call_sid] = {
    "started_at": time.time(),
    "last_activity": time.time(), 
    "state": ConversationHSMStates.INITIAL
}
```

#### Session Persistence
- **Active Sessions**: In-memory tracking for performance
- **Conversation Store**: Persistent storage for conversation data
- **HSM State**: Redis-based state persistence
- **Auto-Cleanup**: Configurable timeout for inactive sessions (default: 1 hour)

## Error Handling & Recovery

### Multi-Level Error Handling

#### Agent Processing Errors
```python
try:
    agent, response = await self._process_with_appropriate_agent(...)
except Exception as e:
    # AI-generated error recovery
    error_response = await ai_mixin.process_with_ai(
        "Generate customer-friendly error recovery message",
        error_context
    )
```

#### HSM Processing Errors
- Automatic transition to ERROR_RECOVERY state
- Graceful degradation with user-friendly messages
- Logging with correlation IDs for debugging

#### Global Error Recovery
- **AI-Generated Responses**: Use AI to generate contextually appropriate error messages
- **State Recovery**: Attempt to recover to valid states
- **Escalation Path**: Automatic escalation for persistent errors

### Error Recovery Mechanisms
1. **Immediate Recovery**: Try to continue with degraded functionality
2. **State Recovery**: Reset to known good state if possible
3. **AI Assistance**: Generate appropriate user-facing error messages
4. **Escalation**: Transfer to human agent as last resort

### Error Scenarios:
1. **Database Connectivity**: Graceful degradation with retry logic
2. **AI Service Failures**: Circuit breaker patterns
3. **Voice Recognition Errors**: Context-aware clarification
4. **Menu Item Unavailability**: Alternative suggestions
5. **Payment Issues**: Recovery workflows

### Recovery Mechanisms:
- **HSM Error States**: Structured error state transitions
- **Retry Logic**: Automatic retry with exponential backoff
- **Escalation Paths**: Human handoff capabilities
- **Context Preservation**: Maintains conversation state during errors

## Performance Optimizations

### Caching Strategy:
- **Menu Cache**: In-memory menu data caching
- **Response Cache**: Common response caching
- **Connection Pooling**: Database and HTTP connection reuse
- **OpenAI Pool**: Pre-warmed AI client connections

### Async Operations:
- **Non-blocking I/O**: All database and API calls are async
- **Concurrent Processing**: Parallel tool execution where possible
- **Streaming Responses**: Immediate response initiation
- **Background Tasks**: Celery for SMS and notifications

### Connection Pooling:
- **Database Pool**: SQLAlchemy connection pooling with configurable limits
- **Redis Pool**: Connection pool for Redis operations
- **HTTP Pool**: Reusable HTTP connections for external APIs
- **OpenAI Pool**: Pre-warmed OpenAI client connections

## Development & Deployment

### Docker Environment

**File**: `/docker-compose.yml`

```
Services:
- app: FastAPI application (port 8000)
- postgres: PostgreSQL database (port 5432)
- redis: Redis cache/state store (port 6379)
- celery: Background task worker
```

### Environment Management
- **Staging**: `redbarsushiai-staging.onrender.com`
- **Production**: `redbarsushi-web.onrender.com`
- **Development**: Docker Compose setup
- **Configuration**: Environment-specific settings via Pydantic

### Common Development Commands

#### Running Tests
```bash
# Run all tests in Docker (recommended for consistency)
./run-docker-tests.sh

# Run specific test categories in Docker
./run-docker-tests.sh unit          # Unit tests only
./run-docker-tests.sh integration   # Integration tests only  
./run-docker-tests.sh e2e          # E2E tests only
./run-docker-tests.sh advanced     # Advanced E2E tests only

# Run tests locally (faster for development)
pytest tests/unit/ -v              # Unit tests
pytest tests/integration/ -v       # Integration tests
pytest tests/e2e/ -v              # E2E tests
```

#### Running the Application
```bash
# Local development with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Docker development (recommended)
docker-compose up -d

# View Docker logs
docker logs -f redbarsushi-app-1

# Access container shell
docker exec -it redbarsushi-app-1 bash
```

#### Database Operations
```bash
# Initialize database (Docker)
docker exec -it redbarsushi-app-1 python init_db.py

# Seed menu data
docker exec -it redbarsushi-app-1 python seed_menu_db.py

# Access PostgreSQL
docker exec -it redbarsushi-postgres-1 psql -U redbarsushi -d redbarsushi
```

### Logging and Monitoring
- **Enhanced Logging**: Structured logging with correlation IDs
- **Health Checks**: Database, Redis, and service health endpoints
- **Error Handling**: Comprehensive error recovery and logging

## Debugging Guide

### Debugging Process

To debug issues, you should:

1. **Check logs with correlation IDs**: Every request has a unique correlation ID for tracing
2. **Examine HSM state transitions**: State changes are logged at CRITICAL level
3. **Review agent selection logic**: Orchestrator logs show which agents are selected
4. **Monitor tool calls**: All tool executions are logged with arguments and results
5. **Check conversation store**: Redis contains full conversation context

### Log Analysis

#### Key Log Patterns
- **Correlation ID**: `"correlation_id": "CA602b7edb07e93347969f10db8975ac16"`
- **HSM Transitions**: `"Transitioning: ACTIVE.MAIN_MENU -> ACTIVE.ESCALATION"`
- **Tool Execution**: `"EXECUTING TOOL: update_customer_info"`
- **Agent Selection**: `"Agent selection complete: AsyncFrontlineVoiceAgentAI"`

#### Important Log Locations
- **Agent Processing**: `/app/logs/agent/agent.log`
- **Database Operations**: `/app/logs/database/database.log`
- **Voice Processing**: `/app/logs/voice/voice.log`
- **OpenAI Calls**: `/app/logs/openai/openai.log`

### Common Debug Scenarios

#### Voice Processing Issues
1. Check Twilio webhook configuration
2. Verify ConversationRelay service setup
3. Review HTTP webhook logs
4. Check TwiML generation
5. Verify agent response handling

#### Database Connection Issues
1. Verify database URL and credentials
2. Check connection pool settings
3. Review async session management
4. Monitor connection counts

#### AI Processing Problems
1. Check OpenAI API key configuration
2. Review model selection and parameters
3. Monitor token usage and limits
4. Examine prompt engineering

## Known Issues & Incomplete Features

### Current Issues

#### 1. Escalation Agent - INCOMPLETE
**Status**: Partially implemented with placeholder logic

**Problems**:
- Missing `HUMAN_HANDOFF_NUMBER` configuration (FIXED)
- Placeholder logic in escalation workflow
- Incomplete human handoff process
- No staff notification system

**Files Affected**:
- `/app/agents/escalation_async.py` - Contains placeholder comments
- `/app/utils/agent_orchestration_async.py` - Transfer logic incomplete

**What Needs Completion**:
- Complete staff availability checking
- Implement staff notification system
- Add proper context handoff to human agents
- Configure actual phone numbers for transfer

#### 2. Testing Coverage
**Status**: Tests exist but coverage may be incomplete

**Areas Needing Attention**:
- Advanced E2E test scenarios
- Error recovery testing
- Load testing for concurrent calls
- Integration testing with external services

### Development Best Practices

#### 1. Code Organization
- Keep files under 1000 lines (split large files into logical components)
- Follow existing patterns for new features
- Place new agents in `app/agents/`, utilities in `app/utils/`
- Use type hints throughout for better IDE support

#### 2. AI-First Development
- **NEVER** use hardcoded phrases, keywords, or string matching
- All business logic must use AI intelligence with sophisticated system prompts
- Use tool calling for all operations - let AI decide when to call tools
- Create dynamic, adaptable system prompts that guide AI behavior
- Trust AI intelligence over hardcoded rules

#### 3. Error Handling
- Implement proper error boundaries in agents
- Use specific exception types for different failures
- Log errors with context (call_sid, order_id, etc.)
- Graceful degradation for non-critical failures

#### 4. Testing Strategy
- Unit tests: Heavy mocking, test business logic
- Integration tests: Test component interactions
- E2E tests: Real service calls (staging only)
- Always add tests for new features

#### 5. Performance Considerations
- Use connection pooling for database
- Implement caching for frequently accessed data
- Stream audio in small chunks (20ms)
- Batch database operations where possible

### Architecture Strengths

#### AI-First Design
- **No Hardcoded Logic**: All intelligence is AI-driven
- **Dynamic Adaptation**: System adapts to user behavior patterns
- **Sophisticated Prompts**: Context-aware prompts for each state

#### Async-First Architecture
- **Non-blocking Operations**: All I/O operations use async/await
- **Concurrent Processing**: Multiple operations can run simultaneously
- **Scalable Design**: Supports horizontal scaling

#### Hierarchical State Management
- **Complex State Modeling**: Supports nested states and transitions
- **Event-Driven**: State changes triggered by detected events
- **Context Preservation**: State context maintained across transitions

#### Robust Error Handling
- **Multiple Fallback Levels**: Redis → Memory → AI-generated responses
- **Graceful Degradation**: System continues functioning during partial failures
- **User-Friendly Recovery**: AI generates contextually appropriate error messages

### Integration Points

#### Database Integration
- **Async SQLAlchemy**: Menu data and order persistence
- **Connection Pooling**: Efficient database connection management

#### External Services
- **OpenAI API**: Text processing and intent detection
- **Twilio**: Voice processing via ConversationRelay
- **Redis**: State and conversation persistence
- **Deliverect**: POS system integration

#### Agent Coordination
- **Tool-Based Delegation**: Frontline agent delegates via tool calls
- **Specialist Registration**: Agents register with frontline agent
- **Context Sharing**: Seamless context flow between agents

---

This documentation provides a comprehensive overview of the RedBarSushiAI system architecture. The system is well-designed with sophisticated AI-driven intelligence, robust state management, and scalable async architecture. However, some features like the escalation system require completion for full production readiness.

For specific debugging or feature development, refer to the detailed sections above and the logging patterns described in the debugging guide.