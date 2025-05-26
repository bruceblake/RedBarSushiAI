# ConversationRelay Implementation Guide for RedBarSushiAI

## Current Issues Identified

1. **Misconception**: The current implementation treats ConversationRelay as a custom WebSocket protocol, but it's actually a Twilio service that requires:
   - A Conversation Service SID
   - A Connector Name configured in Twilio Console
   - Proper TwiML response format

2. **Missing Configuration**: The Twilio Console configuration steps haven't been completed:
   - Need to create a Conversation Service
   - Need to create an External WebSocket Connector
   - Need to add these to environment variables

3. **Protocol Mismatch**: The handler expects different event formats than what Twilio ConversationRelay actually sends

## Correct Implementation Steps

### Step 1: Twilio Console Configuration (MUST DO FIRST)

1. **Create Conversation Service**:
   - Go to Twilio Console → Conversations → Services
   - Create new service
   - Copy Service SID (starts with `CV`)
   - Add to `.env`: `TWILIO_CONVERSATION_SERVICE_SID=CVxxxxxxxx`

2. **Create External WebSocket Connector**:
   - In the Conversation Service → Connectors
   - Create "External WebSocket" connector
   - Name: `redbarsushi-ai-connector`
   - WebSocket URL: `wss://your-domain.com/api/conversation-relay`
   - Audio Format: PCMU, 8kHz, mono
   - Add to `.env`: `TWILIO_CONNECTOR_NAME=redbarsushi-ai-connector`

### Step 2: Fix TwiML Generation

The TwiML should be:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <ConversationRelay serviceSid="CVxxxxxxxx" connectorName="redbarsushi-ai-connector" />
    </Connect>
</Response>
```

### Step 3: Fix WebSocket Handler

The handler needs to expect ConversationRelay events:
- `start`: Contains `relayId`, `callSid`, `streamSid`
- `media`: Contains audio in `payload` (base64 PCMU)
- `mark`: Playback completion events
- `stop`: Call ended

### Step 4: Audio Format Handling

- **From Twilio**: Base64 PCMU (µ-law), 8kHz, mono
- **To Whisper**: Convert PCMU → Linear PCM → WAV
- **From OpenAI TTS**: PCM (usually 24kHz) → Resample to 8kHz → Convert to PCMU
- **To Twilio**: Raw PCMU bytes (binary WebSocket frames)

## URLs for Twilio Configuration

### For Incoming Calls (Twilio Phone Number Webhook):
- **URL**: `https://your-domain.com/voice/` or `https://your-domain.com/voice/webhook`
- **Method**: POST
- **Purpose**: Returns TwiML with ConversationRelay instruction

### For ConversationRelay WebSocket (Connector Configuration):
- **URL**: `wss://your-domain.com/api/conversation-relay`
- **Protocol**: WebSocket (not HTTP)
- **Purpose**: Bidirectional audio streaming

## Required Environment Variables

```bash
# Twilio ConversationRelay
TWILIO_CONVERSATION_SERVICE_SID=CVxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_CONNECTOR_NAME=redbarsushi-ai-connector

# Voice Handler Selection
VOICE_HANDLER=conversation_relay

# Other required
OPENAI_API_KEY=sk-...
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

## Testing Flow

1. **Local Development with ngrok**:
   ```bash
   ngrok http 8000
   # Use the HTTPS URL for webhook and WSS URL for connector
   ```

2. **Test TwiML Generation**:
   ```bash
   curl -X POST http://localhost:8000/voice/ \
     -d "CallSid=TEST123" \
     -d "From=+1234567890"
   ```

3. **Verify WebSocket Endpoint**:
   ```bash
   wscat -c "ws://localhost:8000/api/conversation-relay"
   ```

## Current Code Fixes Needed

1. **app/api/conversation_relay/twiml.py**: 
   - Return proper ConversationRelay TwiML (not Stream)
   - Use serviceSid and connectorName from config

2. **app/api/conversation_relay/handler.py**:
   - Expect ConversationRelay event format
   - Handle `relayId` properly
   - Send `mark` events as JSON (not binary)

3. **app/config.py**:
   - Add TWILIO_CONVERSATION_SERVICE_SID
   - Add TWILIO_CONNECTOR_NAME

4. **Audio Processing**:
   - Fix PCMU ↔ PCM conversions
   - Handle proper sample rates
   - Stream TTS output in chunks