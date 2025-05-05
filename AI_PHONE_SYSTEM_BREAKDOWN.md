# RedBarSushi AI Phone System Breakdown

## System Overview

The RedBarSushi AI Phone System is an advanced voice ordering solution that enables customers to place orders and inquire about menu items over the phone using natural language. The system uses OpenAI's Realtime API with Twilio Media Streams for low-latency, streaming conversation experience. It employs a multi-agent architecture with orchestration to provide specialized handling of different aspects of a restaurant call, such as menu inquiries, order taking, and payment processing.

## Core Components

### 1. Voice Handling Routes

The system offers three voice handling implementations:

1. **Standard Voice Handler** (`app/routes/voice.py`): Basic implementation with Twilio's Gather
2. **Orchestrated Voice Handler** (`app/routes/voice_orchestrated.py`): Advanced implementation with multi-agent orchestration using Twilio's Gather
3. **Realtime Voice Handler** (`app/routes/voice_orchestrated_realtime.py`): Most advanced implementation using OpenAI's Realtime API with Twilio Media Streams

The primary entry point for the Realtime implementation is through Twilio webhooks to the Flask application, which responds with TwiML containing Stream elements that point to a WebSocket endpoint for real-time audio streaming.

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
- **Tool Registry**: Maps tool calls to agent methods for the Realtime implementation

### 4. Audio Processing

The system has multiple implementations for audio processing:

- **Realtime Audio SDK** (`app/utils/realtime_audio_sdk.py`): Direct WebSocket integration with OpenAI's Realtime API
- **Realtime Audio** (`app/utils/realtime_audio.py`): Provides fallback implementations
- **Direct Realtime** (`app/utils/direct_realtime.py`): Alternative WebSocket implementation

## Call Flow Breakdown

### 1. Call Initialization (Realtime Implementation)

When a call comes in using the Realtime Voice Handler, the following sequence occurs:

```
Twilio → `/` (receive_call) → Initialize agents → Generate TwiML with Stream elements → WebSocket connection
```

**Key Function**: `receive_call()` in `voice_orchestrated_realtime.py`

**Implementation Details**:
- Logs incoming call details (call SID, caller number)
- Initializes agent system if not already initialized
- Sets initial session variables
- Generates TwiML with Stream elements pointing to the WebSocket endpoint
- Returns TwiML response to Twilio
- Twilio establishes WebSocket connection to `/ws/media`

### 2. WebSocket Media Stream Processing

After initialization, the real-time audio processing occurs through WebSockets:

```
Twilio streams audio → `/ws/media` WebSocket → OpenAI Realtime API → Process events → Stream responses → Continuous bidirectional audio
```

**Key Function**: `media_stream()` in `voice_orchestrated_realtime.py`

**Implementation Details**:
- Establishes WebSocket connection with Twilio
- Processes incoming media chunks from Twilio
- Initializes and maintains connection to OpenAI's Realtime API
- Processes VAD-driven events (speech started, speech finished, silence detected)
- Handles tool calls for agent interactions
- Streams TTS audio responses back to Twilio
- Maintains continuous bidirectional audio stream

### 3. Realtime Agent Processing Flow

In the Realtime implementation, agent processing happens through tool calls:

```
OpenAI Realtime → tool_call event → Tool Registry → Execute tool → Tool response → Continue conversation
```

**Key Components**: 
- `ToolRegistry` class in `voice_orchestrated_realtime.py`
- `process_media_stream()` in `realtime_audio_sdk.py`

**Implementation Details**:
- OpenAI's Realtime API identifies when a tool is needed
- Sends tool_call event with tool name and arguments
- Tool Registry maps tool call to appropriate agent method
- Tool result is formatted and sent back to OpenAI
- Conversation continues with the tool result incorporated

### 4. Agent Handoff with Tool Calls

The Realtime implementation uses tools for agent handoffs:

```
OpenAI Realtime → lookup_menu_item tool → Menu Agent → Tool response → Continue conversation
OpenAI Realtime → add_item_to_cart tool → Cart Agent → Tool response → Continue conversation
```

**Key Components**: 
- `register_default_tools()` in `voice_orchestrated_realtime.py`
- Tool definitions for each agent capability

**Implementation Details**:
- Tools are registered for each agent capability
- OpenAI's Realtime API selects appropriate tool based on context
- Tool executes with agent-specific logic
- Tool response is sent back to OpenAI
- Single WebSocket connection maintains the entire conversation

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

### 6. VAD-Driven Conversation Flow

The Realtime implementation uses OpenAI's server-side Voice Activity Detection (VAD):

```
OpenAI VAD → silence_detected event → Context-specific reprompt → Continue conversation
```

**Key Components**: 
- `configure_vad_for_context()` in `voice_orchestrated_realtime.py`
- VAD event handling in `media_stream()` handler

**Implementation Details**:
- OpenAI's Realtime API manages silence detection with server-side VAD
- Different VAD parameters are used based on conversation context
- When silence is detected, appropriate reprompts are delivered
- System maintains bidirectional audio throughout silence handling
- No need for separate silence tracking in session state

### 7. Real-time TTS Response Flow

The Realtime implementation streams Text-to-Speech audio in real-time:

```
OpenAI Realtime → response.audio.delta → Audio chunk streaming → Twilio Media Stream
```

**Key Components**:
- Audio handling in `process_media_stream()` in `realtime_audio_sdk.py`
- Audio format conversion between OpenAI and Twilio formats

**Implementation Details**:
- OpenAI's Realtime API generates streaming TTS audio
- Audio is delivered in chunks via WebSocket events
- System converts audio format if needed (PCM16 to μ-law)
- Audio chunks are forwarded to Twilio via Media Stream API
- Continuous streaming provides natural conversation experience

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

## System Diagram (Realtime Implementation)

```
┌─────────────────┐  HTTP   ┌───────────────────────┐
│ Twilio Voice    ├────────→│ Flask Application     │
│ (Phone Call)    │←────────┤ (TwiML with Stream)   │
└─────┬───────────┘         └───────────────────────┘
      │
      │ WebSocket (Media Streams API)
      ▼
┌─────────────────┐         ┌───────────────────────┐
│ /ws/media       │         │ RealtimeAudioProcessor│
│ WebSocket Hub   │←───────→│ (Audio Format Conv.)  │
└─────┬───────────┘         └───────────┬───────────┘
      │                                  │
      │                                  │ WebSocket
      │                                  ▼
      │                     ┌───────────────────────┐
      │                     │ OpenAI Realtime API   │
      │                     │ ┌─────────────────┐   │
      │                     │ │ ASR + VAD       │   │
      │                     │ └─────────────────┘   │
      │                     │ ┌─────────────────┐   │
      │                     │ │ Tool Execution  │   │
      │                     │ └─────────────────┘   │
      │                     │ ┌─────────────────┐   │
      │                     │ │ TTS Streaming   │   │
      │                     │ └─────────────────┘   │
      │                     └───────────┬───────────┘
      │                                 │
      │                                 │ tool_call
      │                                 ▼
      │                     ┌───────────────────────┐
      │                     │ Tool Registry         │
      │                     └───────────┬───────────┘
      │                                 │
      │                                 ▼
┌─────────────┐            ┌───────────────────────┐
│ Redis       │◄──────────→│ Specialized Agents     │
│ (State)     │            │ ┌─────┐ ┌─────┐ ┌────┐│
└─────────────┘            │ │Menu │ │Cart │ │... ││
                            │ └─────┘ └─────┘ └────┘│
                            └───────────────────────┘
```

## Function Reference (Realtime Implementation)

### Realtime Voice Route Functions

| Function | File | Description |
|----------|------|-------------|
| `receive_call()` | voice_orchestrated_realtime.py | Entry point for incoming calls with Media Streams |
| `media_stream()` | voice_orchestrated_realtime.py | WebSocket endpoint for Twilio Media Streams |
| `health_check()` | voice_orchestrated_realtime.py | Health check endpoint for realtime components |
| `initialize_agents()` | voice_orchestrated_realtime.py | Initializes agents and tools for realtime use |
| `register_default_tools()` | voice_orchestrated_realtime.py | Registers agent tools for realtime use |
| `configure_vad_for_context()` | voice_orchestrated_realtime.py | Configures VAD parameters by context |

### Realtime Session Functions

| Function | File | Description |
|----------|------|-------------|
| `RealtimeSession.create()` | realtime_audio_sdk.py | Creates a new Realtime session |
| `RealtimeSession.connect()` | realtime_audio_sdk.py | Connects to OpenAI's Realtime API |
| `RealtimeSession.send_event()` | realtime_audio_sdk.py | Sends events to OpenAI's Realtime API |
| `RealtimeSession.get_events()` | realtime_audio_sdk.py | Gets events from OpenAI's Realtime API |
| `RealtimeSession.get_next_event()` | realtime_audio_sdk.py | Gets the next event from the queue |
| `RealtimeSession.close()` | realtime_audio_sdk.py | Closes the Realtime session |

### Realtime Audio Processing Functions

| Function | File | Description |
|----------|------|-------------|
| `process_realtime_session()` | realtime_audio_sdk.py | Processes a real-time session with streaming audio |
| `process_media_stream()` | realtime_audio_sdk.py | Processes a media stream from Twilio |
| `send_tool_response()` | realtime_audio_sdk.py | Sends a tool response to the Realtime API |
| `ulaw_to_pcm()` | realtime_audio_sdk.py | Converts μ-law audio to PCM format |
| `pcm_to_ulaw()` | realtime_audio_sdk.py | Converts PCM audio to μ-law format |

### Tool Registry Functions

| Function | File | Description |
|----------|------|-------------|
| `ToolRegistry.register_tool()` | voice_orchestrated_realtime.py | Registers a tool with the registry |
| `ToolRegistry.get_tool_definitions()` | voice_orchestrated_realtime.py | Gets tool definitions in OpenAI format |
| `ToolRegistry.execute_tool()` | voice_orchestrated_realtime.py | Executes a registered tool |

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