# ConversationRelay Implementation Checklist

## ✅ Code Implementation Status

### TwiML Generation
- [x] Fixed `app/api/conversation_relay/twiml.py` to generate proper ConversationRelay TwiML
- [x] Updated to use `serviceSid` and `connectorName` attributes
- [x] Added error handling for missing configuration

### WebSocket Handler
- [x] Fixed `app/api/conversation_relay/handler.py` to expect ConversationRelay event format
- [x] Updated `handle_start()` to parse ConversationRelay fields
- [x] Added support for `connected` event
- [x] Mark events properly formatted with `relayId`

### Configuration
- [x] Config fields exist in `app/config.py`:
  - `TWILIO_CONVERSATION_SERVICE_SID`
  - `TWILIO_CONNECTOR_NAME`

### Import Fixes
- [x] Fixed missing `menu_utils` import in `snooze_validator.py`
- [x] Updated TwiML import path

## ❌ Twilio Console Configuration Required

### Must Complete in Twilio Console:
1. [ ] Create Conversation Service
   - [ ] Copy Service SID to `.env`
2. [ ] Create External WebSocket Connector
   - [ ] Set connector name: `redbarsushi-ai-connector`
   - [ ] Set WebSocket URL: `wss://your-domain.com/api/conversation-relay`
   - [ ] Configure audio format: PCMU, 8kHz, mono
3. [ ] Update Phone Number webhook
   - [ ] Set to: `https://your-domain.com/voice/`

### Environment Variables to Add:
```bash
TWILIO_CONVERSATION_SERVICE_SID=CV... # From step 1
TWILIO_CONNECTOR_NAME=redbarsushi-ai-connector
VOICE_HANDLER=conversation_relay
```

## 🔧 Audio Processing Implementation

### Current Status:
- [x] Audio processor exists in `app/api/conversation_relay/audio.py`
- [ ] Need to verify PCMU conversion functions:
  - [ ] `_pcmu_to_wav()` for Whisper
  - [ ] `_pcm_to_pcmu()` for TTS output

### Audio Flow:
1. **From Twilio**: Base64 PCMU → Decode → Convert to WAV → Whisper
2. **To Twilio**: OpenAI TTS (PCM) → Resample to 8kHz → Convert to PCMU → Binary WebSocket

## 📝 Testing Plan

### 1. Unit Tests
- [ ] Test TwiML generation with/without config
- [ ] Test WebSocket event parsing
- [ ] Test audio format conversions

### 2. Integration Tests
- [ ] Test with ngrok locally
- [ ] Verify WebSocket connection
- [ ] Test audio round-trip

### 3. End-to-End Test
- [ ] Make actual phone call
- [ ] Verify greeting plays
- [ ] Test conversation flow
- [ ] Verify order submission

## 🚀 Deployment Steps

1. **Local Testing**:
   ```bash
   # Start app
   docker-compose up
   
   # Start ngrok
   ngrok http 8000
   
   # Update Twilio with ngrok URLs
   ```

2. **Staging Deployment**:
   - Deploy to staging
   - Update Twilio Connector with staging URL
   - Test with real phone calls

3. **Production Deployment**:
   - Deploy to production
   - Update Twilio Connector with production URL
   - Monitor first calls closely

## 🐛 Known Issues to Fix

1. **Audio Format**: Need to verify PCMU conversion is working correctly
2. **Error Handling**: Need better error messages for missing Twilio config
3. **Barge-in**: Test interruption handling during TTS playback
4. **Mark Events**: Verify mark event tracking for TTS completion

## 📊 Monitoring

Add logging for:
- [ ] WebSocket connection establishment
- [ ] Event types received
- [ ] Audio payload sizes
- [ ] STT/TTS latencies
- [ ] Agent processing times

## 🎯 Success Criteria

- [ ] Phone call connects successfully
- [ ] Greeting plays within 2 seconds
- [ ] Speech recognition works accurately
- [ ] AI responses are natural and quick
- [ ] Orders can be placed end-to-end
- [ ] Barge-in works smoothly