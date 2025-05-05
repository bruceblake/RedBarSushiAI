# RedBarSushi AI Phone System Breakdown

## System Overview

The RedBarSushi AI Phone System is an advanced voice ordering solution that enables customers to place orders and inquire about menu items over the phone using natural language. The system uses a multi-agent architecture with orchestration to provide specialized handling of different aspects of a restaurant call, such as menu inquiries, order taking, and payment processing.

## Core Components

### 1. Voice Handling Routes

The primary entry point is through Twilio, which routes incoming calls to the Flask web application routes in `app/routes/voice_orchestrated.py`. These routes handle:
- Initial call reception
- Speech processing
- Agent orchestration
- TwiML response generation
- Realtime audio streaming via WebSockets

### 2. Agent Architecture

The system uses a sophisticated multi-agent orchestration architecture:

- **Frontline Agent**: Primary voice interface that routes to specialist agents (`OrchestratedFrontlineAgent`)
- **Menu Agent**: Handles menu inquiries and item availability
- **Cart Agent**: Manages order collection and modifications
- **Fulfillment Agent**: Processes order completion and payment
- **Guardrail Agent**: Enforces business rules and order validation
- **Escalation Agent**: Handles fallbacks and human staff handoff

### 3. Orchestration System

The orchestration system in `app/utils/agent_orchestration.py` coordinates the agents and manages state:

- **Agent Graph**: Manages relationships between agents and transition conditions
- **Slot Store**: Persists conversation state and tracking information
- **FSM Orchestrator**: Manages state transitions via finite state machine
- **Model Escalator**: Provides automatic escalation to more powerful models when needed

### 4. Audio Processing

The system has multiple implementations for audio processing in `app/utils/realtime_audio.py`:

- **RealTimeAudioProcessor**: Uses OpenAI's Realtime API for streaming audio
- **BasicAudioProcessor**: Fallback implementation for headless environments
- **DirectRealtimeAudioProcessor**: Alternative implementation using WebSockets

## Call Flow Breakdown

### 1. Call Initialization

When a call comes in, the following sequence occurs:

```
Twilio → `/voice_orchestrated/` (receive_call) → Initialize agents → Generate initial TwiML response
```

**Key Function**: `receive_call()` in `voice_orchestrated.py`

**Implementation Details**:
- Logs incoming call details (call SID, caller number)
- Initializes agent system if not already initialized
- Sets initial session variables
- Generates TwiML with speech gathering parameters
- Returns TwiML response to Twilio

### 2. Voice Processing Flow

After initialization, the main voice processing occurs in a loop:

```
User speaks → Twilio captures audio → `/voice_orchestrated/process_input` → Agent processes input → TwiML response → Repeat
```

**Key Function**: `process_input()` in `voice_orchestrated.py`

**Implementation Details**:
- Retrieves speech input and DTMF input from Twilio
- Handles silence detection and fallbacks
- Initializes agents if needed
- Processes user input through the orchestrated frontline agent
- Tracks FSM state for authentication flow
- Returns TwiML response with appropriate gather parameters
- Redirects for silence handling if needed

### 3. Agent Processing Flow

When user input is received, the agent processing flow is:

```
Frontline Agent → Intent detection → Specialist agent handoff → State tracking → Response generation
```

**Key Function**: `process_voice_input()` in `frontline_with_orchestration.py`

**Implementation Details**:
- Logs voice call event
- Sets current call context
- Stores user input in conversation history
- Checks if in authentication flow
- Processes through FSM if in authentication flow
- Otherwise, processes through regular agent system
- Handles escalation if needed
- Stores assistant response in conversation history
- Returns formatted response

### 4. Agent Handoff Flow

The system uses a sophisticated handoff mechanism:

```
Frontline Agent → route_to_X tool → Agent Graph transition → Specialist Agent → Response → Transition back
```

**Key Functions**: 
- `route_to_menu()` and `route_to_order()` in `frontline_with_orchestration.py`
- `get_next_agent()` in `agent_orchestration.py`

**Implementation Details**:
- Frontline agent detects specific intent (menu inquiry, order placement)
- Updates state with intent information
- Uses Agent Graph to determine appropriate transition
- Hands off to specialist agent (Menu, Cart)
- Specialist agent processes request and returns response
- Control transitions back to Frontline agent

### 5. Authentication Flow

The system uses a Finite State Machine for authentication:

```
Initial → ASK_NAME → CONFIRM_NAME → ASK_PHONE → CONFIRM_PHONE → AUTHENTICATED
```

**Key Functions**:
- `authenticate_customer()` in `frontline_with_orchestration.py`
- `process_user_input()` in `agent_orchestration.py` (FSMOrchestrator class)

**Implementation Details**:
- Starts authentication with initial state
- Collects name and phone information through progressive prompts
- Confirms input at each step
- Tracks state using Redis-backed slot store
- Transitions to next state based on user responses
- Updates authentication status when complete

### 6. WebSocket Realtime Flow

For web interfaces, the system provides WebSocket-based realtime processing:

```
Client connects → `/api/ws/orchestrated_conversation` → Stream audio → Real-time processing → Stream responses
```

**Key Function**: `orchestrated_conversation()` in `voice_orchestrated.py`

**Implementation Details**:
- Establishes WebSocket connection
- Initializes audio processor and agents
- Streams audio chunks for processing
- Processes audio with OpenAI Realtime API
- Sends transcript segments to client as they arrive
- Processes complete transcript with orchestrated agent
- Streams response and TTS audio back to client
- Updates state information

### 7. Silence Handling Flow

The system has sophisticated silence handling for improved user experience:

```
No speech input → handle_silence() → Progressive fallback → Retry or redirect
```

**Key Functions**:
- `handle_silence()` in `voice_orchestrated.py`
- `get_adaptive_timeouts()` in `voice_orchestrated.py`

**Implementation Details**:
- Detects silence from empty speech input
- Tracks silence retry count in session
- Uses adaptive timeouts based on context and retry count
- Provides increasingly helpful prompts on retries
- Redirects to fallback after maximum retries
- Includes DTMF option after first retry

### 8. Fallback Flow

When persistent issues occur, the system uses progressive fallbacks:

```
Multiple silences → main_menu_fallback() → DTMF options → dtmf_only() → Graceful exit
```

**Key Functions**:
- `main_menu_fallback()` in `voice_orchestrated.py`
- `dtmf_only()` in `voice_orchestrated.py`
- `graceful_exit()` in `voice_orchestrated.py`

**Implementation Details**:
- Resets silence counters
- Provides clear menu options with DTMF alternatives
- Falls back to DTMF-only mode for severe audio issues
- Provides friendly exit message if needed

## Key Scenarios

### 1. Menu Inquiry Scenario

**Flow**:
1. Customer calls and asks about menu items
2. Frontline agent recognizes menu intent
3. `route_to_menu` tool is called with question
4. Agent Graph transitions to Menu Agent
5. Menu Agent processes inquiry and returns details
6. Frontline agent delivers response to customer
7. System remains ready for follow-up questions

**Key Route**: `process_input()` → `process_voice_input()` → `route_to_menu()`

### 2. Order Placement Scenario

**Flow**:
1. Customer calls and requests to place an order
2. Frontline agent recognizes order intent
3. If not authenticated, authentication flow begins
4. Once authenticated, `route_to_order` tool is called
5. Agent Graph transitions to Cart Agent
6. Cart Agent processes order and builds cart
7. Cart Agent interacts for clarifications if needed
8. Completed order details returned to Frontline
9. Frontline confirms order details to customer

**Key Route**: `process_input()` → `process_voice_input()` → `authenticate_customer()` → `route_to_order()`

### 3. Model Escalation Scenario

**Flow**:
1. Customer makes a complex or ambiguous request
2. Frontline agent uses `check_confidence` tool
3. Low confidence triggers escalation evaluation
4. Model Escalator determines stronger model is needed
5. Next request processed with more powerful model
6. Response delivered to customer without interruption

**Key Route**: `process_voice_input()` → `check_confidence()` → Model escalation

### 4. Human Escalation Scenario

**Flow**:
1. Customer requests human assistance or has complex issue
2. Frontline agent uses `escalate_to_staff` tool
3. Agent Graph transitions to Escalation Agent
4. Escalation Agent prepares handoff information
5. System notifies that customer will be connected to staff
6. In production, would trigger Twilio <Dial> to staff member

**Key Route**: `process_voice_input()` → `escalate_to_staff()` → Human handoff

### 5. Silent Customer Scenario

**Flow**:
1. Customer doesn't speak after prompt
2. System detects silence and increments counter
3. `handle_silence()` function manages progressive responses
4. System provides increasingly helpful prompts
5. After multiple silences, transitions to menu fallback
6. Offers DTMF alternatives for poor audio connections

**Key Route**: `process_input()` → silence detection → `handle_silence()` → `main_menu_fallback()`

## System Diagram

```
┌─────────────────┐  HTTP   ┌───────────────────────┐
│ Twilio Voice    ├────────→│ Flask Application     │
│ (Phone Call)    │←────────┤ (TwiML Responses)     │
└─────────────────┘         └───────────┬───────────┘
                                        │
                                        ▼
┌─────────────────┐  WS     ┌───────────────────────┐
│ Web Client      ├────────→│ WebSocket Endpoints   │
│ (Realtime Audio)│←────────┤ (Streaming Processing)│
└─────────────────┘         └───────────┬───────────┘
                                        │
                                        ▼
                            ┌───────────────────────┐
                            │ Agent Orchestration   │
                            │ ┌─────────────────┐   │
                            │ │ Agent Graph     │   │
                            │ └─────────────────┘   │
                            │ ┌─────────────────┐   │
                            │ │ Slot Store      │   │
                            │ └─────────────────┘   │
                            │ ┌─────────────────┐   │
                            │ │ FSM Orchestrator│   │
                            │ └─────────────────┘   │
                            └───────────┬───────────┘
                                        │
                                        ▼
                            ┌───────────────────────┐
┌─────────────┐            │ Specialized Agents     │
│ Redis       │◄──────────►│ ┌─────┐ ┌─────┐ ┌────┐│
│ (State)     │            │ │Menu │ │Cart │ │... ││
└─────────────┘            │ └─────┘ └─────┘ └────┘│
                            └───────────┬───────────┘
                                        │
                                        ▼
                            ┌───────────────────────┐
                            │ OpenAI APIs           │
                            │ ┌─────────┐ ┌───────┐ │
                            │ │Realtime │ │Chat   │ │
                            │ └─────────┘ └───────┘ │
                            └───────────────────────┘
```

## Function Reference

### Voice Route Functions

| Function | File | Description |
|----------|------|-------------|
| `receive_call()` | voice_orchestrated.py | Entry point for incoming calls |
| `process_input()` | voice_orchestrated.py | Processes speech input from user |
| `handle_silence()` | voice_orchestrated.py | Handles empty speech inputs |
| `main_menu_fallback()` | voice_orchestrated.py | Fallback for repeated silences |
| `dtmf_only()` | voice_orchestrated.py | Last resort fallback for audio issues |
| `graceful_exit()` | voice_orchestrated.py | Clean call termination |
| `orchestrated_conversation()` | voice_orchestrated.py | WebSocket endpoint for realtime processing |

### Agent Functions

| Function | File | Description |
|----------|------|-------------|
| `process_voice_input()` | frontline_with_orchestration.py | Main voice input processing |
| `route_to_menu()` | frontline_with_orchestration.py | Handles menu inquiries |
| `route_to_order()` | frontline_with_orchestration.py | Handles order placement |
| `authenticate_customer()` | frontline_with_orchestration.py | Manages customer authentication |
| `check_confidence()` | frontline_with_orchestration.py | Evaluates response confidence |
| `escalate_to_staff()` | frontline_with_orchestration.py | Handles human escalation |
| `get_restaurant_info()` | frontline_with_orchestration.py | Provides restaurant information |

### Orchestration Functions

| Function | File | Description |
|----------|------|-------------|
| `initialize_orchestrators()` | agent_orchestration.py | Sets up orchestration components |
| `get_next_agent()` | agent_orchestration.py | Determines agent transitions |
| `process_user_input()` | agent_orchestration.py | FSM input processing |
| `get_current_state()` | agent_orchestration.py | Retrieves FSM state |
| `set_current_state()` | agent_orchestration.py | Updates FSM state |
| `should_escalate()` | agent_orchestration.py | Evaluates model escalation need |

### Audio Processing Functions

| Function | File | Description |
|----------|------|-------------|
| `get_audio_processor()` | realtime_audio.py | Returns appropriate audio processor |
| `process_audio_stream()` | realtime_audio.py | Processes streaming audio |
| `process_audio()` | realtime_audio.py | Processes complete audio |
| `generate_speech()` | realtime_audio.py | Generates TTS audio |

## Common Scenarios and Debug Points

### Common Issues

1. **Redis Connection Failures**:
   - Check Redis URL configuration
   - Verify Render-specific host in Redis connection
   - Look for fallback to local storage in logs

2. **Agent Initialization Issues**:
   - Check OpenAI API key availability
   - Verify agent factory initialization
   - Examine agent registration logs

3. **Audio Processing Errors**:
   - Check for X11 display errors
   - Verify fallback to headless mode
   - Examine audio processor selection

4. **State Persistence Problems**:
   - Check Redis connection status
   - Verify slot store operations
   - Examine FSM state transitions

### Key Logging Points

1. `[VOICE_INIT]` - Voice route initialization logs
2. `[VOICE_AGENT]` - Agent initialization and registration logs
3. `[VOICE_PROC]` - Voice input processing logs
4. `[ORCH_GRAPH]` - Agent graph and transition logs
5. `[ORCH_SLOT]` - Slot store operation logs
6. `[ORCH_FSM]` - FSM state transition logs
7. `[ORCH_ESCALATION]` - Model escalation logs
8. `[ORCH_INIT]` - Orchestration initialization logs

## Deployment Environment Variables

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | Authentication for OpenAI APIs |
| `REDIS_URL` | Redis connection string |
| `RENDER` | Flag for Render environment |
| `RENDER_SERVICE_ID` | Render service identifier |
| `OPENAI_FRONTLINE_AGENT_ID` | Frontline agent identifier |
| `OPENAI_MENU_AGENT_ID` | Menu agent identifier |
| `OPENAI_CART_AGENT_ID` | Cart agent identifier |
| `OPENAI_FULFILLMENT_AGENT_ID` | Fulfillment agent identifier |
| `OPENAI_GUARDRAIL_AGENT_ID` | Guardrail agent identifier |
| `OPENAI_ESCALATION_AGENT_ID` | Escalation agent identifier |

## Testing the System

The system includes health check endpoints for verification:

- `/voice_orchestrated/health` - Checks voice route and agent health
- Testing can be done by calling the Twilio number
- Development testing can use the WebSocket demo page at `/voice_orchestrated/demo`