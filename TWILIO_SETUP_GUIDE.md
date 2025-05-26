# Twilio ConversationRelay Setup Guide

## Prerequisites

1. Twilio Account with:
   - A phone number configured
   - Access to Conversations API
   - API credentials (Account SID, Auth Token)

2. Your application deployed with:
   - Public HTTPS URL (use ngrok for local development)
   - WebSocket endpoint accessible at `/api/conversation-relay`

## Step-by-Step Twilio Console Configuration

### 1. Create a Conversation Service

1. Log into [Twilio Console](https://console.twilio.com)
2. Navigate to **Develop** → **Conversations** → **Services**
3. Click **Create new Service**
4. Name it: `RedBarSushi AI Service` (or similar)
5. Click **Create**
6. Copy the **Service SID** (starts with `CV`)
   - Example: `CVa1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`

### 2. Create an External WebSocket Connector

1. In your Conversation Service, go to **Connectors**
2. Click **Create new Connector**
3. Select **External WebSocket**
4. Configure:
   - **Connector Name**: `redbarsushi-ai-connector`
   - **WebSocket URL**: 
     - Production: `wss://your-domain.com/api/conversation-relay`
     - Local/ngrok: `wss://abcd1234.ngrok.io/api/conversation-relay`
   - **Audio Format**: 
     - Format: `PCMU`
     - Sample Rate: `8000`
     - Channels: `1` (mono)
   - **Authentication** (optional but recommended):
     - Add custom headers for security
     - Example: `X-API-Key: your-secret-key`
5. Click **Create**

### 3. Configure Your Twilio Phone Number

1. Navigate to **Phone Numbers** → **Manage** → **Active Numbers**
2. Click on your phone number
3. In the **Voice Configuration** section:
   - **A call comes in**: Webhook
   - **URL**: `https://your-domain.com/voice/`
   - **HTTP Method**: `POST`
4. Click **Save**

## Environment Variables Setup

Add these to your `.env` file:

```bash
# Twilio Core (you should already have these)
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_PHONE_NUMBER=+1234567890

# ConversationRelay Configuration (NEW)
TWILIO_CONVERSATION_SERVICE_SID=CVa1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
TWILIO_CONNECTOR_NAME=redbarsushi-ai-connector

# Voice Handler Selection
VOICE_HANDLER=conversation_relay

# OpenAI (you should already have this)
OPENAI_API_KEY=sk-...
```

## Testing Your Setup

### 1. Test TwiML Generation

```bash
curl -X POST http://localhost:8000/voice/ \
  -d "CallSid=CA1234567890abcdef1234567890abcdef" \
  -d "From=+1234567890" \
  -d "To=+0987654321"
```

Expected response:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <ConversationRelay serviceSid="CVa1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6" connectorName="redbarsushi-ai-connector" />
    </Connect>
</Response>
```

### 2. Monitor WebSocket Connection

Watch your application logs:
```bash
docker logs -f redbarsushi-app | grep -i conversationrelay
```

### 3. Make a Test Call

1. Call your Twilio phone number
2. You should see in logs:
   - TwiML webhook hit
   - WebSocket connection established
   - `start` event received with `relayId`
   - Audio streaming begins

## Troubleshooting

### No WebSocket Connection

1. **Check Connector URL**: Ensure it's publicly accessible and uses `wss://`
2. **Check logs**: Look for connection attempts in your app logs
3. **Verify Service SID**: Make sure it matches between Console and .env
4. **Test WebSocket**: Use `wscat` to test your endpoint manually

### No Audio

1. **Check audio format**: Must be PCMU, 8kHz, mono
2. **Verify `media` events**: Log the payload size
3. **Check STT**: Ensure audio is reaching Whisper correctly

### Common Errors

- **"Missing ConversationRelay configuration"**: Add Service SID and Connector Name to .env
- **"Failed to connect to OpenAI"**: Check OPENAI_API_KEY
- **WebSocket closes immediately**: Check authentication headers if configured

## Local Development with ngrok

1. Start your app: `docker-compose up`
2. Start ngrok: `ngrok http 8000`
3. Copy the HTTPS URL (e.g., `https://abcd1234.ngrok.io`)
4. Update Twilio:
   - Phone number webhook: `https://abcd1234.ngrok.io/voice/`
   - Connector WebSocket URL: `wss://abcd1234.ngrok.io/api/conversation-relay`

## Production Deployment

1. Ensure your domain has valid SSL certificate
2. Update Connector WebSocket URL to production domain
3. Update phone number webhook to production URL
4. Monitor logs for the first few calls

## URLs Summary

### For Twilio Phone Number (Voice Webhook)
- **Purpose**: Returns TwiML instructions when call arrives
- **URL**: `https://your-domain.com/voice/`
- **Method**: POST
- **What it does**: Returns `<Connect><ConversationRelay>` TwiML

### For ConversationRelay Connector (WebSocket)
- **Purpose**: Bidirectional audio streaming
- **URL**: `wss://your-domain.com/api/conversation-relay`
- **Protocol**: WebSocket (not HTTP)
- **What it does**: Handles real-time audio and AI processing