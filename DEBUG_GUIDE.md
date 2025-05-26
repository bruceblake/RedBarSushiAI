# RedBarSushiAI Debugging Guide

## Table of Contents
1. [WebSocket Debugging](#websocket-debugging)
2. [ConversationRelay Debugging](#conversationrelay-debugging)
3. [Twilio Integration Debugging](#twilio-integration-debugging)
4. [Agent System Debugging](#agent-system-debugging)
5. [Complete Call Flow Debugging](#complete-call-flow-debugging)
6. [Useful Debug Commands](#useful-debug-commands)

---

## WebSocket Debugging

### Key Files

#### 1. **`app/api/conversation_relay/handler.py`** (Main WebSocket Handler)
**Purpose**: Handles WebSocket connection and message routing

**Key Functions to Debug**:
```python
# Line 212: WebSocket endpoint
@router.websocket("/conversation-relay")
async def conversation_relay_endpoint(websocket: WebSocket):
    await websocket.accept()  # BREAKPOINT: Connection established
    
# Line 180: Main event loop
async def run(self):
    async for message in self.websocket.iter_json():  # BREAKPOINT: Message received
        event_type = message.get("event")
```

**Common Issues**:
- Connection not establishing: Check line 222 `await websocket.accept()`
- Messages not received: Add logging at line 186 in `run()` method
- Event type not recognized: Log at line 189

#### 2. **`app/api/__init__.py`** (Router Registration)
**Purpose**: Registers WebSocket routes

**Check Registration** (Lines 44-46):
```python
from app.api.conversation_relay import conversation_relay_router
api_router.include_router(conversation_relay_router, prefix="/api", tags=["ConversationRelay"])
logger.info("Successfully registered ConversationRelay router")
```

### Debug WebSocket Connection

**Add Debug Logging**:
```python
# In handler.py, add at line 37 (handle_start method):
logger.debug(f"WebSocket connection state: {self.websocket.client_state}")
logger.debug(f"Headers: {dict(self.websocket.headers)}")
```

**Test WebSocket Manually**:
```bash
# Simple WebSocket test client
python simple_websocket_test.py

# Or use wscat
wscat -c "wss://your-domain.com/api/conversation-relay"
```

---

## ConversationRelay Debugging

### Key Files

#### 1. **`app/api/conversation_relay/handler.py`** (ConversationRelayHandler class)

**Critical Methods**:

**`handle_start()` (Line 37)** - Connection initialization
```python
async def handle_start(self, message: Dict[str, Any]):
    self.relay_id = message.get("relayId")
    self.call_sid = message.get("callSid")
    logger.info(f"ConversationRelay started - Relay: {self.relay_id}, Call: {self.call_sid}")
```

**`handle_media()` (Line 59)** - Audio processing
```python
async def handle_media(self, message: Dict[str, Any]):
    # BREAKPOINT: Check if audio is received
    audio_payload = media.get("payload", "")
    if not audio_payload:
        logger.warning(f"Empty audio payload for {self.call_sid}")
        return
```

**`handle_mark()` (Line 111)** - TTS completion tracking
```python
async def handle_mark(self, message: Dict[str, Any]):
    mark_name = mark.get("name", "")
    # Check if TTS playback completed
    if mark_name == self.last_mark_name:
        self.is_playing_tts = False
```

#### 2. **`app/api/conversation_relay/audio.py`** (Audio Processing)

**STT Function** (Line 36):
```python
async def speech_to_text(self, audio_bytes: bytes) -> Optional[str]:
    # Debug: Log audio size
    logger.debug(f"STT input size: {len(audio_bytes)} bytes")
    
    # Check OpenAI client
    if not self.client:
        logger.error("OpenAI client not available for STT")
        return None
```

**TTS Function** (Line 77):
```python
async def text_to_speech(self, text: str) -> Optional[bytes]:
    # Debug: Log text length
    logger.debug(f"TTS input: {text[:100]}...")
    
    # Check response
    pcm_data = response.content
    logger.debug(f"TTS generated {len(pcm_data)} bytes")
```

### Debug Audio Issues

**Add Audio Debugging**:
```python
# In handler.py handle_media(), after line 83:
logger.debug(f"Audio received: {len(audio_bytes)} bytes, first 10 bytes: {audio_bytes[:10].hex()}")

# Check for silence
if all(b == 0 for b in audio_bytes[:100]):
    logger.warning("Received silent audio")
```

---

## Twilio Integration Debugging

### Key Files

#### 1. **`app/api/conversation_relay/twiml.py`** (TwiML Generation)

**TwiML Generator** (Line 19):
```python
def generate_conversation_relay_twiml(params: TwiMLParams) -> str:
    # Debug: Log parameters
    logger.info(f"Generating ConversationRelay TwiML for {params.call_sid}")
    logger.debug(f"WebSocket URL: {params.ws_url}")
```

**Check Generated TwiML**:
```python
# Add after line 50:
logger.debug(f"Generated TwiML:\n{response}")
```

#### 2. **`app/api/voice/twiml.py`** (Main TwiML Router)

**Voice Handler Selection** (Line 118):
```python
if settings.VOICE_HANDLER == "conversation_relay":
    logger.info(f"Using ConversationRelay voice handler for call {call_sid}")
    twiml = generate_conversation_relay_twiml(twiml_params)
else:
    # Fallback to media streams
    logger.info(f"Using Media Streams voice handler for call {call_sid}")
```

### Debug Twilio Connection

**Check Environment**:
```python
# Add to twiml.py at line 40:
logger.info(f"VOICE_HANDLER setting: {settings.VOICE_HANDLER}")
logger.info(f"BASE_URL: {settings.BASE_URL}")
```

**Verify TwiML Response**:
```bash
# Test TwiML endpoint
curl -X POST https://your-domain.com/voice/ \
  -d "CallSid=TEST123" \
  -d "From=+1234567890"
```

---

## Agent System Debugging

### Key Files

#### 1. **`app/utils/agent_orchestration_async.py`** (Agent Orchestrator)

**Main Processing Function** (Line 210):
```python
async def process_voice_input(self, call_sid: str, transcript: str) -> Dict[str, Any]:
    logger.info(f"[{call_sid}] Processing transcript: {transcript}")
    
    # Get current FSM state
    fsm = await self.fsm_manager.get_fsm(call_sid)
    current_state = fsm.get_current_state()
    logger.debug(f"[{call_sid}] Current FSM state: {current_state}")
```

**Agent Selection** (Line 245):
```python
# Debug which agent is selected
selected_agent = self._select_agent_for_state(current_state)
logger.info(f"[{call_sid}] Selected agent: {selected_agent.name}")
```

#### 2. **`app/agents/frontline_async.py`** (Main Coordinator)

**Process Input** (Line 95):
```python
async def process_input(self, input_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
    logger.info(f"[Frontline] Processing: {input_text}")
    
    # Check intent detection
    intent = self._detect_intent(input_text)
    logger.debug(f"[Frontline] Detected intent: {intent}")
```

### Debug Agent Processing

**Add Agent Lifecycle Logging**:
```python
# In any agent's process_input method:
logger.info(f"[{self.name}] Start processing: {input_text[:50]}...")
result = await self._process_logic(input_text, context)
logger.info(f"[{self.name}] Result: {result.get('text', '')[:50]}...")
```

**Check Agent Handoffs**:
```python
# In agent_orchestration_async.py:
if result.get("handoff"):
    logger.warning(f"[{call_sid}] Handoff requested to: {result.get('handoff_to')}")
```

---

## Complete Call Flow Debugging

### 1. **Entry Point: Twilio Webhook**
```bash
# File: app/api/voice/twiml.py
# Function: receive_call() - Line 61
# Add logging:
logger.info(f"Incoming call: {call_sid} from {from_number}")
```

### 2. **WebSocket Connection**
```bash
# File: app/api/conversation_relay/handler.py
# Function: conversation_relay_endpoint() - Line 212
# Add logging:
logger.info(f"WebSocket connected: {websocket.client}")
```

### 3. **Audio Processing**
```bash
# File: app/api/conversation_relay/handler.py
# Function: handle_media() - Line 59
# Add logging:
logger.info(f"Audio chunk received: {len(audio_bytes)} bytes")
```

### 4. **Agent Processing**
```bash
# File: app/api/conversation_relay/handler.py
# Function: handle_media() - Line 93
# Add logging:
logger.info(f"Sending to agent: {transcript}")
response = await async_agent_orchestrator.process_voice_input(self.call_sid, transcript)
logger.info(f"Agent response: {response}")
```

### 5. **TTS Response**
```bash
# File: app/api/conversation_relay/handler.py
# Function: _send_tts_with_tracking() - Line 153
# Add logging:
logger.info(f"Generating TTS for: {text[:50]}...")
```

---

## Useful Debug Commands

### 1. **Watch Logs in Real-time**
```bash
# Docker logs
docker logs -f redbarsushi-app-1

# Grep for specific components
docker logs -f redbarsushi-app-1 | grep -E "ConversationRelay|WebSocket|Agent"
```

### 2. **Test WebSocket Connection**
```python
# Create test_websocket_debug.py
import asyncio
import websockets
import json

async def test_connection():
    uri = "ws://localhost:8000/api/conversation-relay"
    async with websockets.connect(uri) as websocket:
        # Send start event
        await websocket.send(json.dumps({
            "event": "start",
            "relayId": "test-relay",
            "callSid": "test-call"
        }))
        
        # Listen for responses
        async for message in websocket:
            print(f"Received: {message}")

asyncio.run(test_connection())
```

### 3. **Test Agent Processing**
```bash
# Use the testing endpoint
curl -X POST http://localhost:8000/voice/test/process \
  -H "Content-Type: application/json" \
  -d '{
    "call_sid": "test-123",
    "transcript": "I want to order a California roll"
  }'
```

### 4. **Check FSM State**
```bash
# Get current FSM state
curl http://localhost:8000/voice/test/fsm/test-123
```

### 5. **Enable Debug Logging**
```python
# Add to app/main.py or set environment variable
import logging
logging.getLogger("app.api.conversation_relay").setLevel(logging.DEBUG)
logging.getLogger("app.utils.agent_orchestration_async").setLevel(logging.DEBUG)
```

---

## Common Issues and Solutions

### WebSocket Not Connecting
1. Check URL format in TwiML: should be `wss://` not `ws://`
2. Verify ConversationRelay router is registered
3. Check Twilio webhook is pointing to correct endpoint

### No Audio Received
1. Check `handle_media()` is being called
2. Verify audio payload is base64 encoded
3. Check audio format is PCMU

### Agent Not Responding
1. Verify agent orchestrator is initialized
2. Check FSM state transitions
3. Ensure Redis is connected for state storage

### TTS Not Playing
1. Check OpenAI API key is valid
2. Verify audio conversion (PCM to PCMU)
3. Check mark events for completion tracking

---

## Debug Checklist

- [ ] WebSocket connection established?
- [ ] Start event received with call metadata?
- [ ] Media events arriving with audio?
- [ ] Audio successfully converted to transcript?
- [ ] Agent processing transcript?
- [ ] Response text generated?
- [ ] TTS audio created?
- [ ] Audio sent back to Twilio?
- [ ] Mark event confirming playback?

Use this guide to systematically debug issues in the voice pipeline!