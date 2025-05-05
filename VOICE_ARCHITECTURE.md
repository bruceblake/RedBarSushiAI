# Voice System Architecture

RedBarSushiAI offers three different voice handling implementations, with the Realtime API approach providing the most advanced features and architecture.

## Voice Handler Configuration

The active voice handler can be configured using the `VOICE_HANDLER` environment variable:

```bash
# Options: "standard", "orchestrated", "realtime"
VOICE_HANDLER=orchestrated  # Default
```

## 1. Standard Voice Handler (`voice.py`)

The original implementation using direct OpenAI API calls.

**Key Features:**
- Basic voice handling with Twilio TwiML
- Manual conversation state tracking
- Simple intent recognition

**Route:** Root URL when configured as primary

## 2. Orchestrated Voice Handler (`voice_orchestrated.py`)

Advanced implementation with multi-agent orchestration using Twilio's `<Gather>` for audio processing.

**Key Features:**
- Multi-agent architecture with specialized agents
- Sequential handoffs between agents
- State-machine slot filling for structured conversations
- Background escalation for complex scenarios
- Automated guardrails and validation

**Route:** Root URL when configured as primary

## 3. Realtime Voice Handler (`voice_orchestrated_realtime.py`)

The most advanced implementation using OpenAI's Realtime API with Twilio Media Streams.

**Key Features:**
- Direct WebSocket integration with OpenAI's Realtime API
- Streaming audio processing with sub-300ms latency
- VAD-driven conversation flow instead of turn-based
- Continuous bidirectional audio streaming
- Tool-based agent integration for specialized tasks
- All orchestrated agent capabilities with WebSocket events

**Route:** Root URL when `VOICE_HANDLER=realtime` (recommended for production)

## Architecture Diagram

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

## Agent Roles

**Frontline Voice Agent**
- Manages overall call flow and reprompts
- Routes to specialists via handoffs or tool calls

**Menu Agent**
- Answers questions about items, prices, availability

**Cart Agent**
- Parses order language, manages Redis cart

**Fulfillment Agent**
- Prepares Deliverect payload, records order, triggers SMS task

**Guardrail Agent**
- Validates business rules, triggers retries on violations

**Escalation Agent**
- Takes over for human handoff when needed

## Invocation Patterns

**Tool Calls**
- Quick queries, synchronous (e.g. lookup_menu_item)

**Direct Handoffs**
- Sub-dialogues (e.g. full order submission)

**Nested Calls**
- Specialists can themselves call other agents as tools

## Data & State Management

The system uses Redis for ephemeral data and PostgreSQL for persistent storage:

| Function | Store | Key / Table | TTL / Retention |
|----------|-------|-------------|----------------|
| Conversation context | Redis hash | conversation:{CallSid} | 2 hours |
| Silence counts | Redis field | silence_count:{phase} | per-call |
| Cart contents | Redis hash | cart:{CallSid} | 2 hours |
| Menu caching | Redis hashes | menu:item:{plu} | 1 hour |
| Persistent menu & orders | PostgreSQL | menu_items, orders | Permanent |

## Silence & VAD Handling

Voice Activity Detection (VAD) is handled with phase-specific timeouts:
- Greeting: 5s → reprompt
- Main menu: 4s → reprompt
- Menu inquiry: 6s → reprompt
- Order-taking: 8s → reprompt
- Confirmation: 5s → reprompt

The system implements progressive fallbacks:
1. Voice reprompt
2. Stronger reprompt
3. DTMF prompt
4. Human escalation or hang-up

## Why Use the Orchestrated Handler?

The orchestrated voice handler is recommended for production use because it:

1. Uses a true multi-agent architecture
2. Supports complex conversation flows
3. Provides better error handling and recovery
4. Enables specialized agents for different tasks
5. Implements proper slot-filling for structured data
6. Aligns with the target architecture for RedBarSushiAI