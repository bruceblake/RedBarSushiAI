# WebSocket Implementation for RedBarSushiAI

This document provides a comprehensive guide for setting up, testing, and troubleshooting the WebSocket implementation in the RedBarSushiAI application.

## Overview

The application uses WebSockets to enable real-time audio streaming between the client and server. This implementation leverages:

1. **Flask-Sock** for WebSocket server endpoints
2. **OpenAI Realtime API** for streaming audio transcription and response generation
3. **Browser WebAudio API** for client-side audio capture

## Architecture

![WebSocket Architecture](https://cdn.openai.com/API/docs/images/diagram-realtime-customer-service-3.png)

### Server Endpoints

The application exposes three main WebSocket endpoints:

1. `/api/ws/speech-to-text` - Receives streaming audio and returns real-time transcription
2. `/api/ws/text-to-speech` - Receives text and returns synthesized speech
3. `/api/ws/conversation` - A full-featured endpoint for two-way conversation with audio

### Components

- **RealtimeAudioProcessor:** Uses OpenAI's realtime client for WebSocket API access
- **BasicAudioProcessor:** Fallback processor that uses standard REST API calls
- **HeadlessAudioProcessor:** Minimal implementation for environments without display servers

## Setup Instructions

### Environment Configuration

These environment variables control the WebSocket behavior:

```bash
# Enable headless operation (no X11 or display server required)
export PYNPUT_HEADLESS=1
export NO_X11=1
export HEADLESS=1
export DISPLAY=:99

# Enable OpenAI Realtime client
export OPENAI_REALTIME_AVAILABLE=1
```

### Dependencies

Required Python packages:

```bash
# Core WebSocket functionality
pip install websockets==13.1 flask-sock==0.7.0 simple-websocket==1.1.0

# OpenAI integration
pip install openai==1.68.2 openai-realtime-client==0.1.0

# WebSocket server support
pip install python-socketio==5.8.0 eventlet==0.33.3 gevent==23.9.1 gevent-websocket==0.10.1
```

## Testing

### Run Diagnostic Tests

We've included a diagnostic script that tests all components of the WebSocket implementation:

```bash
python diagnose.py
```

The script checks:
- Environment variables
- Dependency availability
- OpenAI API connectivity
- OpenAI Realtime client functionality
- Audio processor capabilities
- Redis connection string format

### Manual Testing

1. **Test the speech-to-text endpoint**:
   ```bash
   python test_websocket.py --test stt --server http://localhost:8080
   ```

2. **Test the text-to-speech endpoint**:
   ```bash
   python test_websocket.py --test tts --text "Hello, this is a test" --server http://localhost:8080
   ```

3. **Test the conversation endpoint**:
   ```bash
   python test_websocket.py --test conversation --text "I'd like to order sushi" --server http://localhost:8080
   ```

4. **Interactive Browser Demo**:
   Visit `/demo` in your browser to test the full WebSocket implementation.

## Troubleshooting

### Common Issues

1. **WebSocketResponse Import Error**:
   - The OpenAI Realtime client doesn't export a WebSocketResponse class
   - Solution: Import only the Session class from openai_realtime_client

2. **X11/Display Server Errors**:
   - Application fails because it tries to use GUI components in a headless environment
   - Solution: Set environment variables in docker-entrypoint.sh and use HeadlessAudioProcessor

3. **Redis URL Format Issues**:
   - Celery fails due to improperly formatted Redis URLs
   - Solution: Fix Redis URLs in docker-entrypoint.sh before application startup

### Logs and Debugging

To enable detailed WebSocket logs:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('app.utils.realtime_audio').setLevel(logging.DEBUG)
```

## Implementation Details

### Client-Side Integration

For client applications to use these WebSocket endpoints:

1. Check server capabilities with a GET request to `/api/ws/capabilities`
2. Connect to the appropriate WebSocket endpoint
3. Send audio data in chunks (for speech-to-text) or text (for text-to-speech)
4. Process the streamed responses

### Fallback Behavior

The system implements a three-tier fallback system:
1. **First choice:** OpenAI Realtime WebSocket API (lowest latency)
2. **Second choice:** Standard OpenAI REST API with streaming (medium latency)
3. **Last resort:** Headless implementation with no GUI dependencies (highest compatibility)

## References

- [OpenAI Realtime API Documentation](https://platform.openai.com/docs/api-reference/realtime)
- [Flask-Sock Documentation](https://flask-sock.readthedocs.io/)
- [WebAudio API Documentation](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API)