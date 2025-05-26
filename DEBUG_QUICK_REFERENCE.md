# Debug Quick Reference Card

## 🔍 Most Important Debug Locations

### 1. WebSocket Connection
```python
# FILE: app/api/conversation_relay/handler.py
# LINE: 212 - WebSocket endpoint
# ADD: logger.info(f"WebSocket connection from: {websocket.client}")

# LINE: 37 - Start event handler
# ADD: logger.debug(f"Full start message: {json.dumps(message, indent=2)}")
```

### 2. Audio Flow
```python
# FILE: app/api/conversation_relay/handler.py
# LINE: 83 - Audio received
# ADD: logger.info(f"Audio: {len(audio_bytes)} bytes, silent: {all(b == 0 for b in audio_bytes[:100])}")

# FILE: app/api/conversation_relay/audio.py
# LINE: 52 - Before Whisper call
# ADD: logger.info(f"Calling Whisper with {len(wav_data)} bytes of WAV")

# LINE: 69 - After Whisper
# ADD: logger.info(f"Whisper result: '{transcript}'")
```

### 3. Agent Processing
```python
# FILE: app/api/conversation_relay/handler.py
# LINE: 93 - Send to agent
# ADD: logger.info(f"→ Agent input: '{transcript}'")

# LINE: 98 - Agent response
# ADD: logger.info(f"← Agent output: '{response_text[:100]}...'")

# FILE: app/utils/agent_orchestration_async.py
# LINE: 245 - Agent selection
# ADD: logger.warning(f"STATE: {current_state} → AGENT: {selected_agent.name}")
```

### 4. TTS Generation
```python
# FILE: app/api/conversation_relay/audio.py
# LINE: 99 - Before TTS call
# ADD: logger.info(f"TTS request: '{normalized_text[:50]}...'")

# LINE: 109 - After TTS
# ADD: logger.info(f"TTS generated: {len(pcm_data)} bytes PCM → {len(pcmu_data)} bytes PCMU")
```

## 🚀 Quick Debug Commands

### Watch Everything
```bash
docker logs -f redbarsushi-app-1 | grep -E "WebSocket|Audio:|Agent|TTS|STATE:"
```

### Watch Specific Call
```bash
docker logs -f redbarsushi-app-1 | grep "YOUR-CALL-SID"
```

### Test Manually
```bash
# Test TwiML generation
curl -X POST http://localhost:8000/voice/ -d "CallSid=TEST123"

# Test agent processing
curl -X POST http://localhost:8000/voice/test/process \
  -H "Content-Type: application/json" \
  -d '{"call_sid": "TEST123", "transcript": "I want sushi"}'

# Run debug script
python debug_conversationrelay.py --url ws://localhost:8000/api/conversation-relay
```

## 🔧 Environment Variables for Debugging

```bash
# Add to .env or docker-compose
LOG_LEVEL=DEBUG
VOICE_HANDLER=conversation_relay
PYTHONUNBUFFERED=1  # See logs immediately

# In Python code
import logging
logging.getLogger("app.api.conversation_relay").setLevel(logging.DEBUG)
logging.getLogger("app.agents").setLevel(logging.DEBUG)
```

## 🐛 Common Issues

### WebSocket Won't Connect
1. Check: Is `/api/conversation-relay` route registered?
   - Look in `app/api/__init__.py` line 46
2. Check: Is URL correct in TwiML?
   - Look in `app/api/conversation_relay/twiml.py` line 35

### No Audio Received
1. Check: Are media events arriving?
   - Add log in `handler.py` line 59
2. Check: Is audio base64 encoded?
   - Add log in `handler.py` line 83

### Agent Not Responding
1. Check: Is orchestrator initialized?
   - Look in `app/main.py` line 176
2. Check: Is transcript reaching agent?
   - Add log in `handler.py` line 93

### No TTS Audio
1. Check: OpenAI API key valid?
   - Look in `app/config.py` for OPENAI_API_KEY
2. Check: Audio conversion working?
   - Add logs in `audio.py` lines 109-113

## 📊 State Flow Debugging

```
GREETING → MAIN_MENU → ORDERING → VALIDATION → CONFIRMATION → FULFILLMENT → COMPLETION

Check state at each step:
curl http://localhost:8000/voice/test/fsm/YOUR-CALL-SID
```