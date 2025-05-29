# ConversationRelay Docker Setup Guide

## Overview

This guide will help you set up ConversationRelay with FSM agents in your Docker development environment. ConversationRelay is Twilio's improved voice processing system that provides better latency and reliability compared to Media Streams.

## Current Status

Based on the codebase analysis:
- ✅ ConversationRelay handler is implemented (`app/api/conversation_relay/handler.py`)
- ✅ TwiML generation supports ConversationRelay (`app/api/conversation_relay/twiml.py`)
- ✅ Voice webhook routing is configured (`app/api/voice/twiml.py`)
- ✅ FSM agents are integrated with async agent orchestrator
- ✅ Docker Compose is configured with `VOICE_HANDLER=conversation_relay`

## Setup Steps

### 1. Configure Environment Variables

Update your `.env` file with the following variables:

```bash
# Voice Handler Configuration
VOICE_HANDLER=conversation_relay

# ConversationRelay Settings (for URL mode - recommended)
BASE_URL=http://localhost:8000  # Update with ngrok URL when testing

# ConversationRelay TTS/STT Configuration
CONVERSATION_RELAY_TTS_PROVIDER=ElevenLabs
CONVERSATION_RELAY_TTS_VOICE=your-voice-id  # Optional, uses default if not set
CONVERSATION_RELAY_LANGUAGE=en-US
CONVERSATION_RELAY_STT_PROVIDER=Google
CONVERSATION_RELAY_SPEECH_MODEL=telephony
CONVERSATION_RELAY_INTERRUPTIBLE=any
CONVERSATION_RELAY_DTMF_DETECTION=false

# Optional: Service/Connector Mode (if you prefer this over URL mode)
# TWILIO_CONVERSATION_SERVICE_SID=CVxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# TWILIO_CONNECTOR_NAME=redbarsushi-ai-connector
```

### 2. Start Docker Environment

```bash
# Start all services
./start_docker.sh

# Or manually with docker-compose
docker-compose up -d

# Check logs
docker-compose logs -f app
```

### 3. Test Local Setup with ngrok

For local testing, you need to expose your local server to the internet:

```bash
# Terminal 1: Start ngrok
ngrok http 8000

# Note the HTTPS URL (e.g., https://abcd1234.ngrok.io)
```

### 4. Configure Twilio

#### Option A: URL Mode (Recommended)

1. In Twilio Console, go to your phone number settings
2. Set the webhook for "A call comes in" to:
   - URL: `https://your-ngrok-url.ngrok.io/voice/`
   - Method: `POST`

The system will automatically generate ConversationRelay TwiML with the WebSocket URL.

#### Option B: Service/Connector Mode (Advanced)

1. Create a Conversation Service in Twilio Console
2. Create an External WebSocket Connector with URL: `wss://your-ngrok-url.ngrok.io/api/conversation-relay`
3. Add the Service SID and Connector Name to your `.env` file
4. Configure your phone number webhook same as Option A

### 5. Test the Integration

#### Test TwiML Generation

```bash
# Test that TwiML is generated correctly
curl -X POST http://localhost:8000/voice/ \
  -d "CallSid=TEST123" \
  -d "From=+1234567890" \
  -d "To=+19876543210"
```

Expected response should contain ConversationRelay TwiML:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <ConversationRelay 
            url="ws://localhost:8000/api/conversation-relay"
            welcomeGreeting="Welcome to development Red Bar Sushi AI!"
            language="en-US"
            ttsProvider="ElevenLabs"
            transcriptionProvider="Google"
            speechModel="telephony"
            interruptible="any"
        />
    </Connect>
</Response>
```

#### Test WebSocket Connection

```bash
# Install wscat if you don't have it
npm install -g wscat

# Test the WebSocket endpoint
wscat -c "ws://localhost:8000/api/conversation-relay"
```

#### Monitor Logs

```bash
# Watch for ConversationRelay events
docker-compose logs -f app | grep -i "conversationrelay"

# Watch for agent orchestration
docker-compose logs -f app | grep -i "agent"
```

## How It Works

### 1. Call Flow

1. **Incoming Call**: Twilio receives call and hits your webhook
2. **TwiML Response**: Your app returns ConversationRelay TwiML
3. **WebSocket Connection**: Twilio connects to your WebSocket endpoint
4. **Event Processing**: Your handler processes ConversationRelay events
5. **Agent Orchestration**: FSM agents process the conversation

### 2. Event Types

ConversationRelay sends these event types:

- **setup**: Initial connection with call details
- **prompt**: Transcribed user speech
- **interrupt**: User interrupted AI speech
- **dtmf**: Touch-tone input
- **error**: Error events

Your handler responds with:

- **text**: Text for Twilio to convert to speech
- **language**: Change language mid-call
- **play**: Play audio from URL
- **end**: End the conversation

### 3. FSM Integration

The ConversationRelay handler integrates with the FSM agents:

```python
# In handler.py
await async_agent_orchestrator.start_new_conversation(call_sid)
response = await async_agent_orchestrator.process_voice_input(call_sid, voice_prompt)
```

## Debugging Tips

### 1. Check Environment Variables

```bash
# Inside the container
docker-compose exec app python -c "from app.config import settings; print(f'VOICE_HANDLER: {settings.VOICE_HANDLER}')"
```

### 2. Test Database Connection

```bash
docker-compose exec app python test_db_connection.py
```

### 3. Verify Agent Initialization

```bash
# Check that agents are initialized
docker-compose logs app | grep "agent orchestrator initialized"
```

### 4. Common Issues

1. **WebSocket Connection Fails**
   - Check ngrok is running and URL is correct
   - Verify firewall/security groups allow WebSocket connections
   - Check Docker port mapping (8000:8080 in docker-compose.yml)

2. **No Audio/Transcription**
   - Verify TTS provider settings
   - Check ConversationRelay attributes in TwiML
   - Monitor WebSocket events in logs

3. **Agent Not Responding**
   - Check OPENAI_API_KEY is set correctly
   - Verify agent orchestrator initialization
   - Check database connection for menu data

## Production Deployment

For production on Render:

1. Set `BASE_URL` to your Render URL
2. Configure all environment variables in Render dashboard
3. Ensure WebSocket support is enabled
4. Use `wss://` for secure WebSocket connections

## Testing with Real Calls

1. Make sure ngrok is running
2. Update Twilio webhook with ngrok URL
3. Call your Twilio number
4. Monitor logs in real-time:

```bash
# Terminal 1: App logs
docker-compose logs -f app

# Terminal 2: Celery logs (for order processing)
docker-compose logs -f celery

# Terminal 3: Database queries
docker-compose logs -f postgres
```

## Next Steps

1. Test with different TTS providers (Google, Amazon)
2. Implement custom voice selection
3. Add language detection and switching
4. Enhance interrupt handling
5. Add DTMF menu navigation

## References

- [Twilio ConversationRelay Docs](https://www.twilio.com/docs/voice/twiml/connect/conversationrelay)
- [RedBarSushiAI Architecture](SYSTEM_ARCHITECTURE.md)
- [FSM Implementation](app/utils/fsm_async.py)
- [Agent Orchestration](app/utils/agent_orchestration_async.py)