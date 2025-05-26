# Debug Flow Diagram - File by File

## 1. Call Initiation Flow

```
INCOMING CALL
     ↓
[app/api/voice/twiml.py] - receive_call() - Line 61
     ├─ Extracts: CallSid, From, To
     ├─ Logs: logger.info(f"Incoming call from {from_number}")
     └─ Checks: settings.VOICE_HANDLER (Line 118)
            ↓
[app/api/conversation_relay/twiml.py] - generate_conversation_relay_twiml() - Line 19
     ├─ Creates WebSocket URL: wss://{BASE_URL}/api/conversation-relay
     └─ Returns TwiML with <Connect><ConversationRelay> tag
```

## 2. WebSocket Connection Flow

```
TWILIO CONNECTS
     ↓
[app/api/conversation_relay/handler.py] - conversation_relay_endpoint() - Line 212
     ├─ await websocket.accept() - Establishes connection
     ├─ Creates AudioProcessor() instance
     └─ Creates ConversationRelayHandler() → await handler.run()
            ↓
[handler.py] - run() method - Line 180
     └─ async for message in websocket.iter_json(): - Main event loop
            ├─ "start" → handle_start() - Line 37
            ├─ "media" → handle_media() - Line 59
            ├─ "mark" → handle_mark() - Line 111
            └─ "stop" → handle_stop() - Line 122
```

## 3. Audio Processing Flow

```
AUDIO RECEIVED (media event)
     ↓
[handler.py] - handle_media() - Line 59
     ├─ Extract: audio_payload = media.get("payload", "")
     ├─ Decode: audio_bytes = base64.b64decode(audio_payload) - Line 83
     └─ Process STT:
            ↓
[app/api/conversation_relay/audio.py] - speech_to_text() - Line 36
     ├─ Convert: PCMU → WAV (_pcmu_to_wav) - Line 122
     ├─ Call: OpenAI Whisper API - Line 63
     └─ Return: transcript text
            ↓
TRANSCRIPT READY → Send to Agents
```

## 4. Agent Processing Flow

```
TRANSCRIPT → AGENT ORCHESTRATOR
     ↓
[handler.py] - Line 93
     response = await async_agent_orchestrator.process_voice_input(call_sid, transcript)
            ↓
[app/utils/agent_orchestration_async.py] - process_voice_input() - Line 210
     ├─ Get FSM: fsm = await self.fsm_manager.get_fsm(call_sid) - Line 215
     ├─ Get State: current_state = fsm.get_current_state() - Line 216
     └─ Select Agent: agent = self._select_agent_for_state(current_state) - Line 245
            ↓
AGENT SELECTED (based on FSM state)
     ├─ GREETING → FrontlineAgent
     ├─ MAIN_MENU → FrontlineAgent
     ├─ ORDERING → CartAgent
     ├─ VALIDATION → GuardrailAgent
     └─ FULFILLMENT → FulfillmentAgent
            ↓
[app/agents/{agent_name}_async.py] - process_input() method
     ├─ Process transcript based on agent logic
     ├─ May call tools or other agents
     └─ Return: {"text": "response", "handoff": null, ...}
```

## 5. Response Flow

```
AGENT RESPONSE
     ↓
[handler.py] - handle_media() - Line 99
     if response_text:
         self.current_tts_task = asyncio.create_task(
             self._send_tts_with_tracking(response_text)
         )
            ↓
[handler.py] - _send_tts_with_tracking() - Line 153
     ├─ Set flag: self.is_playing_tts = True
     ├─ Generate mark: mark_name = f"tts_{int(time.time() * 1000)}"
     └─ Convert to speech:
            ↓
[audio.py] - text_to_speech() - Line 77
     ├─ Normalize: normalized_text = normalize_for_tts(text) - Line 93
     ├─ Call: OpenAI TTS API - Line 99
     ├─ Convert: PCM → PCMU (_pcm_to_pcmu) - Line 112
     └─ Return: PCMU audio bytes
            ↓
[handler.py] - send_audio() - Line 127
     └─ await websocket.send_bytes(audio_data) - Send to Twilio
            ↓
[handler.py] - send_mark() - Line 135
     └─ Send mark event to track playback completion
```

## 6. FSM State Transitions

```
[app/utils/fsm_async.py] - AsyncConversationFSM class

State Transition Points:
├─ start_new_conversation() → GREETING
├─ After greeting → MAIN_MENU
├─ "I want to order" → ORDERING
├─ Cart has items → VALIDATION
├─ Order valid → CONFIRMATION
├─ Customer confirms → FULFILLMENT
└─ Order submitted → COMPLETION

Each transition logged in agent_orchestration_async.py:
logger.info(f"[{call_sid}] State change: {prev} → {new}")
```

## Key Debug Points

### 1. **Connection Issues**
```python
# app/api/conversation_relay/handler.py - Line 212
logger.critical(f"WebSocket state: {websocket.client_state}")
logger.critical(f"Headers: {dict(websocket.headers)}")
```

### 2. **Audio Issues**
```python
# app/api/conversation_relay/handler.py - Line 83
logger.debug(f"Audio size: {len(audio_bytes)}, First bytes: {audio_bytes[:10].hex()}")
```

### 3. **Agent Issues**
```python
# app/utils/agent_orchestration_async.py - Line 250
logger.info(f"Agent selected: {agent.name} for state: {current_state}")
```

### 4. **TTS Issues**
```python
# app/api/conversation_relay/audio.py - Line 109
logger.debug(f"TTS response size: {len(pcm_data)} bytes")
```

## Quick Debug Commands

```bash
# 1. Watch all ConversationRelay logs
docker logs -f redbarsushi-app-1 | grep -i conversationrelay

# 2. Watch agent decisions
docker logs -f redbarsushi-app-1 | grep -E "Selected agent:|Agent response:"

# 3. Watch audio flow
docker logs -f redbarsushi-app-1 | grep -E "Audio received:|STT:|TTS:"

# 4. Watch FSM transitions
docker logs -f redbarsushi-app-1 | grep "State change:"
```