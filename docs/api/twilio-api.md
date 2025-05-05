# Twilio API Documentation

## Overview

The Twilio API enables RedBarSushiAI to handle voice communications and SMS notifications.

## Voice Handling

### Incoming Call Webhook

```
POST /webhook/voice
```

Twilio sends incoming call notifications to this endpoint, which responds with TwiML.

**Response Example**:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Amy-Neural">Welcome to Red Bar Sushi! How can I help you today?</Say>
    <Gather input="speech" action="/webhook/voice/input" method="POST" speechTimeout="auto" enhanced="true">
        <Say voice="Polly.Amy-Neural">You can ask about our menu or place an order.</Say>
    </Gather>
</Response>
```

### Voice Input Webhook

```
POST /webhook/voice/input
```

Receives transcribed speech from Twilio and processes the user's input.

**Request Parameters**:
- `CallSid`: Unique identifier for the call
- `SpeechResult`: Transcribed text from the user's speech

**Response**: TwiML with appropriate next actions

## SMS Notifications

### Sending SMS

```python
from twilio.rest import Client

def send_sms_notification(to_number, message):
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    message = client.messages.create(
        body=message,
        from_=settings.TWILIO_PHONE_NUMBER,
        to=to_number
    )
    return message.sid
```

## TwiML Elements

### `<Say>`

Used to convert text to speech for the caller.

```xml
<Say voice="Polly.Amy-Neural">Welcome to Red Bar Sushi!</Say>
```

### `<Gather>`

Collects user input (speech or keypad).

```xml
<Gather input="speech" action="/webhook/voice/input" method="POST" speechTimeout="auto" enhanced="true">
    <Say voice="Polly.Amy-Neural">How can I help you today?</Say>
</Gather>
```

### `<Redirect>`

Transfers control to another URL.

```xml
<Redirect method="POST">/webhook/voice/menu</Redirect>
```

### `<Hangup>`

Ends the call.

```xml
<Hangup/>
```

## Progressive Timeouts

The system implements these timeouts for handling silence:

1. First attempt: 5 seconds
2. Second attempt: 8 seconds
3. Third attempt: 10 seconds with DTMF fallback