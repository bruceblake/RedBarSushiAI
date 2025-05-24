# ConversationRelay Migration Summary

## Why ConversationRelay?

The current implementation using Twilio Media Streams + OpenAI Realtime API is experiencing:
- Complex errors with audio format mismatches
- "Cannot have multiple concurrent receivers" issues
- Silence after greeting despite successful connections
- High complexity managing two separate WebSocket connections

ConversationRelay offers a cleaner solution with:
- Single bidirectional WebSocket
- Native audio handling by Twilio
- Lower latency
- Better barge-in support
- Simpler architecture

## Implementation Created

### 1. Module Structure
Created `app/api/conversation_relay/` with:
- `__init__.py`: Module exports
- `twiml.py`: TwiML generation for ConversationRelay
- `handler.py`: WebSocket handler for bidirectional audio
- `audio.py`: Audio processing (STT/TTS) utilities

### 2. Key Components

#### TwiML Generation
- Generates `<Connect><ConversationRelay>` instead of `<Start><Stream>`
- Requires `serviceSid` and `connectorName` from Twilio Console

#### WebSocket Handler
- Single endpoint: `/conversation-relay`
- Handles Twilio events: `start`, `media`, `mark`, `stop`
- Sends binary audio frames back to Twilio
- Integrates with existing agent orchestration

#### Audio Processing
- STT: Uses OpenAI Whisper API
- TTS: Uses OpenAI TTS API
- Format conversion: PCMU ↔ PCM/WAV
- Direct audio streaming without complex WebSocket relay

### 3. Configuration

Added to `.env`:
```
# Voice Handler Configuration
VOICE_HANDLER=media_streams  # or "conversation_relay"

# Twilio ConversationRelay Configuration
# TWILIO_CONVERSATION_SERVICE_SID=CVxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# TWILIO_CONNECTOR_NAME=redbarsushi-ai-connector
```

## Migration Path

1. **Keep Current System**: The existing Media Streams implementation remains functional
2. **Gradual Migration**: Use `VOICE_HANDLER` env var to switch between implementations
3. **Twilio Setup Required**: 
   - Create Conversation Service in Twilio Console
   - Configure External WebSocket Connector
   - Update environment variables
4. **Testing**: Can test ConversationRelay with subset of calls before full rollout

## Next Steps

1. **Twilio Console Setup**:
   - Create Conversation Service
   - Create External WebSocket Connector pointing to `/conversation-relay`
   - Note the service SID and connector name

2. **Update Voice Routes**:
   - Modify `/voice/webhook` to check `VOICE_HANDLER` setting
   - Return appropriate TwiML based on configuration

3. **Testing**:
   - Set `VOICE_HANDLER=conversation_relay`
   - Update Twilio configuration values
   - Test with phone calls

4. **Optimization**:
   - Fine-tune audio processing
   - Add caching for common responses
   - Implement mark events for better timing

## Benefits Over Current System

| Aspect | Current (Media Streams) | ConversationRelay |
|--------|------------------------|-------------------|
| WebSockets | 2 (complex relay) | 1 (bidirectional) |
| Audio Errors | Many format issues | Native handling |
| Latency | Higher | Lower |
| Code Complexity | High | Medium |
| Reliability | Issues observed | Expected better |

This migration provides a path to significantly simplify the voice architecture while improving reliability and performance.