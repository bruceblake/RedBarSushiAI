# OpenAI Realtime API Integration

This document outlines the integration of OpenAI's Realtime API with the RedBarSushiAI voice system.

## Overview

The Realtime API integration provides a streaming, VAD-driven voice system with sub-300ms latency. This implementation uses:

1. Twilio's Media Streams API for real-time audio streaming
2. OpenAI's Realtime API for streaming audio processing
3. WebSockets for bidirectional communication
4. Tool-based agent integration for specialized tasks
5. VAD-driven conversation flow instead of turn-based interactions

## Key Components

- **Media Streams WebSocket (`/ws/media`)**: Handles Twilio Media Streams
- **Realtime Session**: Direct WebSocket connection to OpenAI's Realtime API
- **Tool Registry**: Maps tool calls to agent methods
- **Audio Conversion**: Converts between μ-law (Twilio) and PCM (OpenAI)

## Configuration

To enable the Realtime voice handler:

```bash
# In your environment or .env file
VOICE_HANDLER=realtime
```

## Testing

### Local Testing

1. Start the application:

```bash
VOICE_HANDLER=realtime python run.py
```

2. Use Twilio's console to point a phone number to:

```
https://your-ngrok-url/
```

3. Place a call to the Twilio phone number

### Staging Testing

1. Set the environment variable in the Render dashboard:

```
VOICE_HANDLER=realtime
```

2. Deploy to staging

3. Use Twilio's console to point a phone number to:

```
https://redbarsushiai-staging.onrender.com/
```

4. Place a call to the Twilio phone number

## Implementation Details

### Twilio TwiML

```xml
<Response>
    <Start>
        <Stream url="wss://your-server.com/ws/media" track="inbound_track"/>
    </Start>
    <Say>Welcome to Red Bar Sushi!</Say>
    <Connect>
        <Stream url="wss://your-server.com/ws/media" track="both_tracks"/>
    </Connect>
</Response>
```

### Realtime Session Configuration

```python
session_config = {
    "input_audio_format": {
        "type": "audio/mulaw", 
        "sampling_rate": 8000  # Twilio uses 8kHz mulaw
    },
    "output_audio_format": {
        "type": "audio/mp3"
    },
    "turn_detection": {
        "mode": "dynamic_threshold",  # Better for phone calls
        "timeout": 2.0,               # Appropriate for voice conversations 
        "interrupt_assistant": True,  # Allow interruptions
        "create_response": True,      # Auto-generate responses
        "speech_started_delay": 0.3,  # Adjust for phone audio quality
    }
}
```

### VAD Parameters by Context

The implementation uses context-aware VAD configurations:

| Context | Timeout | Speech Delay | Notes |
|---------|---------|--------------|-------|
| Greeting | 1.5s | 0.2s | Quick responses expected |
| Ordering | 3.0s | 0.4s | Longer for complex orders |
| Confirmation | 1.2s | 0.2s | Quick yes/no responses |
| Complex Order | 4.0s | 0.5s | Maximum patience |

## Tool Integration

The Realtime implementation integrates with the agent system using tools:

```
tool_call → execute_tool → tool_response
```

Available tools include:
- `lookup_menu_item`: Get menu item details
- `add_item_to_cart`: Add items to the cart
- `get_cart`: Retrieve cart contents
- `complete_order`: Submit the order

## Troubleshooting

Common issues:

1. **WebSocket Connection Failure**:
   - Check that Twilio has HTTPS access to your endpoint
   - Verify WebSocket endpoint is properly registered

2. **Audio Not Processing**:
   - Check μ-law to PCM conversion
   - Verify audio format configuration matches Twilio's format

3. **Tool Calls Not Working**:
   - Check tool registry configuration
   - Verify agent implementation for tool methods

## Performance Monitoring

The implementation tracks:
- WebSocket connection events
- Audio chunk counts
- VAD events (speech.started, speech.finished, silence_detected)
- Tool call execution time
- Overall response latency