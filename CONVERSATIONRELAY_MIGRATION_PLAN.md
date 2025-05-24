# Migration Plan: Twilio ConversationRelay for RedBarSushiAI

## Overview

This document outlines the migration from the current Twilio Media Streams + OpenAI Realtime API architecture to Twilio's ConversationRelay, which provides a cleaner, more reliable solution for real-time voice interactions.

## Current Architecture Issues

1. **Complex WebSocket Management**: Managing two separate WebSocket connections (Twilio → App → OpenAI)
2. **Audio Format Errors**: OpenAI Realtime API rejecting audio with multiple errors
3. **Processing Loop Conflicts**: "Cannot have multiple concurrent receivers" errors
4. **Silence After Greeting**: System connects but fails to generate audio responses

## Benefits of ConversationRelay

1. **Simplified Architecture**: Single bidirectional WebSocket for both input and output
2. **Native Audio Handling**: Twilio manages audio format conversions
3. **Lower Latency**: Direct audio streaming without intermediate processing
4. **Better Barge-in Support**: Built-in support for interruption handling
5. **Proven Reliability**: Purpose-built for AI voice interactions

## Migration Steps

### Phase 1: Twilio Console Configuration

**Prerequisites** (Manual setup in Twilio Console):

1. **Create Conversation Service**:
   - Note the `serviceSid` (format: `CVxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`)
   - This will be added to environment variables

2. **Create External WebSocket Connector**:
   - Name: `redbarsushi-ai-connector` (or similar)
   - WebSocket URL: `wss://your-domain.com/conversation-relay`
   - Authentication headers (if needed)
   - Audio format: PCMU/8kHz

3. **Update Phone Number Webhook**:
   - Keep pointing to `/voice/webhook`
   - The webhook will return ConversationRelay TwiML

### Phase 2: Code Implementation

#### 2.1 Environment Variables

Add to `.env`:
```
TWILIO_CONVERSATION_SERVICE_SID=CVxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_CONNECTOR_NAME=redbarsushi-ai-connector
```

#### 2.2 Update TwiML Generation

Replace current `<Start><Stream>` with:
```xml
<Response>
    <Connect>
        <ConversationRelay 
            serviceSid="{{TWILIO_CONVERSATION_SERVICE_SID}}" 
            connectorName="{{TWILIO_CONNECTOR_NAME}}" />
    </Connect>
</Response>
```

#### 2.3 New WebSocket Handler

Create `/conversation-relay` endpoint that handles:

**Incoming from Twilio**:
- `start`: Initialize conversation
- `media`: Process caller audio (base64 PCMU)
- `mark`: Track AI speech completion
- `stop`: Clean up resources

**Outgoing to Twilio**:
- Binary audio frames (PCMU format)
- Optional `mark` events for speech tracking

#### 2.4 Audio Processing

1. **Input Pipeline**:
   - Receive base64 PCMU from Twilio
   - Decode to raw audio
   - Convert to format needed by STT
   - Process with speech recognition

2. **Output Pipeline**:
   - Generate text response with AI
   - Convert to speech with TTS
   - Encode as PCMU
   - Stream as binary frames to Twilio

#### 2.5 Remove OpenAI Realtime Dependency

- Remove complex OpenAI WebSocket management
- Use standard OpenAI APIs for:
  - Whisper for STT
  - GPT-4 for conversation
  - TTS API for speech synthesis

### Phase 3: Implementation Plan

1. **Create new ConversationRelay module** (`app/api/conversation_relay/`):
   - `handler.py`: WebSocket handler
   - `audio.py`: Audio processing utilities
   - `twiml.py`: TwiML generation

2. **Update existing voice routes**:
   - Modify `/voice/webhook` to return ConversationRelay TwiML
   - Keep fallback to old system during transition

3. **Implement audio pipeline**:
   - STT: Use OpenAI Whisper API
   - AI: Use existing agent orchestration
   - TTS: Use OpenAI TTS API

4. **Add configuration**:
   - Load Twilio service/connector from env
   - Configure audio formats
   - Set up authentication if needed

### Phase 4: Testing

1. **Unit Tests**:
   - TwiML generation
   - Audio format conversion
   - Message parsing

2. **Integration Tests**:
   - WebSocket connection handling
   - Full conversation flow
   - Error scenarios

3. **End-to-End Tests**:
   - Real phone calls
   - Latency measurements
   - Barge-in functionality

## Key Differences from Current System

| Aspect | Current (Media Streams) | ConversationRelay |
|--------|------------------------|-------------------|
| WebSocket Connections | 2 (Twilio→App, App→OpenAI) | 1 (Bidirectional) |
| Audio Direction | Unidirectional + API calls | Bidirectional streaming |
| Complexity | High | Medium |
| Latency | Higher | Lower |
| Barge-in | Complex | Native support |

## Success Metrics

- **Latency**: < 500ms response time
- **Reliability**: > 99% call success rate
- **Audio Quality**: Clear, natural-sounding speech
- **Barge-in**: Successful interruption handling

## Risk Mitigation

1. **Gradual Rollout**: Test with subset of calls first
2. **Fallback Option**: Keep old system available
3. **Monitoring**: Comprehensive logging and metrics
4. **Documentation**: Clear setup and troubleshooting guides

## Next Steps

1. Set up Twilio Conversation Service in console
2. Create new ConversationRelay endpoints
3. Implement audio processing pipeline
4. Test with development phone number
5. Monitor and optimize performance
6. Full rollout

This migration will significantly simplify the voice architecture while improving reliability and performance.