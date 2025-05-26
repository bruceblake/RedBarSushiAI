# TwiML App Setup Guide for ConversationRelay

## Overview

Since you have a TwiML App SID, we'll use the **direct URL approach** for ConversationRelay, which is simpler and doesn't require creating a Conversation Service.

## Setup Steps

### 1. Configure Your TwiML App

1. Go to [Twilio Console](https://console.twilio.com) → **Develop** → **Voice** → **TwiML Apps**
2. Find your TwiML App (or create one if needed)
3. Configure:
   - **Voice Request URL**: `https://your-domain.com/voice/`
   - **Voice Request Method**: `POST`
   - **Voice Fallback URL**: (optional)
   - **Voice Status Callback URL**: (optional)
4. Save the TwiML App
5. Copy the **TwiML App SID** (starts with `AP`)

### 2. Configure Your Phone Number

1. Go to **Phone Numbers** → **Manage** → **Active Numbers**
2. Click on your phone number
3. In the **Voice Configuration**:
   - **Configure with**: TwiML App
   - **TwiML App**: Select your TwiML App from the dropdown
4. Save

### 3. Environment Variables

Add to your `.env` file:
```bash
# Optional - for reference
TWILIO_TWIML_APP_SID=APxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Required
VOICE_HANDLER=conversation_relay

# Your app's base URL (for generating WebSocket URLs)
BASE_URL=https://your-domain.com

# Other required variables you should already have
OPENAI_API_KEY=sk-...
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 4. How It Works

When a call comes in:

1. Twilio calls your Voice Request URL: `POST https://your-domain.com/voice/`
2. Your app returns TwiML:
   ```xml
   <Response>
     <Connect>
       <ConversationRelay url="wss://your-domain.com/api/conversation-relay" />
     </Connect>
   </Response>
   ```
3. Twilio establishes WebSocket connection to your `/api/conversation-relay` endpoint
4. Bidirectional audio streaming begins

## Testing

### Local Development with ngrok:

1. Start your app:
   ```bash
   docker-compose up
   ```

2. Start ngrok:
   ```bash
   ngrok http 8000
   ```

3. Update your TwiML App with ngrok URL:
   - Voice Request URL: `https://abcd1234.ngrok.io/voice/`

4. The app will automatically use the ngrok domain for the WebSocket URL

### Test the TwiML Response:

```bash
# Test locally
curl -X POST http://localhost:8000/voice/ \
  -d "CallSid=TEST123" \
  -d "From=+1234567890"
```

Expected response:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <ConversationRelay url="wss://your-domain.com/api/conversation-relay" />
    </Connect>
</Response>
```

### Monitor Logs:

```bash
docker logs -f redbarsushi-app | grep -E "ConversationRelay|WebSocket"
```

## Troubleshooting

### WebSocket Won't Connect

1. **Check URL**: Must be `wss://` (secure WebSocket) for production
2. **Check accessibility**: The WebSocket endpoint must be publicly accessible
3. **Check logs**: Look for connection attempts

### No Audio

1. **Check format**: ConversationRelay expects PCMU, 8kHz, mono
2. **Check events**: Log the event types and payload sizes
3. **Check handlers**: Ensure `handle_media()` is processing audio

### Common Issues

- **"No BASE_URL configured"**: Add BASE_URL to your .env file
- **WebSocket closes immediately**: Check for errors in the `start` event handler
- **No greeting**: Check agent orchestrator initialization

## Production Deployment

1. Set `BASE_URL` in your production environment:
   ```bash
   BASE_URL=https://your-production-domain.com
   ```

2. Update TwiML App with production URL

3. Ensure SSL certificate is valid

4. Monitor first few calls closely

## Summary

- **TwiML App**: Handles incoming call webhooks
- **Voice Request URL**: `https://your-domain.com/voice/`
- **WebSocket URL**: `wss://your-domain.com/api/conversation-relay`
- **No Conversation Service needed** with this approach

The code now supports both approaches:
- Direct URL (what you should use with TwiML App)
- Service-based (if you later want to use Conversation Services)