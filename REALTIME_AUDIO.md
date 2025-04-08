# Real-time Speech & Audio Integration

This document outlines the integration of OpenAI's real-time speech-to-text and text-to-speech APIs with the RedBarSushiAI platform.

## Overview

The real-time audio feature uses WebSockets to provide a low-latency, interactive conversation experience with the AI assistant. This is a significant improvement over the previous implementation, which relied on Twilio for voice interactions.

## Current Implementation Status

The system supports multiple audio processor implementations to accommodate different environments:

1. **DirectRealtimeAudioProcessor** - A direct WebSocket implementation with dual backend support:
   - Uses either `websockets` or `aiohttp` libraries for WebSocket communication
   - Automatically detects and uses the best available library
   - Connects directly to OpenAI's Realtime API with no dependencies on the OpenAI Realtime client
   - Provides full WebSocket functionality without X11/display dependencies
2. **RealtimeAudioProcessor** - Uses the official OpenAI Realtime client library (via RealtimeClient class) when available
3. **HeadlessAudioProcessor** - A fallback implementation for headless environments with no GUI/X11 dependencies 
4. **BasicAudioProcessor** - A simple implementation using OpenAI's standard API for audio processing
5. **MinimalAudioProcessor** - An emergency fallback with minimal dependencies for maximum compatibility

For troubleshooting issues with realtime functionality, run:

```bash
python test_realtime_client.py
```

This script will test all available implementations and tell you which ones work in your environment.

## April 2025 Update: API Changes

In April 2025, the OpenAI Realtime client API underwent changes:

1. `openai_realtime_client.client.Session` class is no longer available
2. `openai_realtime_client.RealtimeClient` class is now the main entry point

The RedBarSushiAI platform has been updated to handle these changes:

- The realtime_audio.py module now attempts to use the RealtimeClient class first
- If RealtimeClient is found, it tries various methods that might exist in the current API
- If any problems occur with the new API, it transparently falls back to our custom implementation
- The system stays backwards compatible with older versions of the API

The implementation includes:
- Dynamic API detection and adaptation
- Client method discovery and testing
- Graceful fallback to our custom implementation
- Detailed logging for troubleshooting

## Features

- **Real-time Speech-to-Text**: Stream audio directly from the browser to the server and get transcription results as you speak
- **Real-time Text-to-Speech**: Convert AI responses to speech with natural-sounding voices
- **Conversation History**: Keep track of conversation context for more coherent interactions
- **Fallback Implementation**: Works even without real-time libraries by using standard OpenAI API calls

## WebSocket Endpoints

The following WebSocket endpoints are available:

1. `/api/ws/speech-to-text` - Receives streaming audio and returns real-time transcription
2. `/api/ws/text-to-speech` - Receives text and returns synthesized speech audio
3. `/api/ws/conversation` - Full conversation endpoint that handles both speech-to-text, AI processing, and text-to-speech

## Demo

A demo implementation is available at `/demo` which showcases the real-time conversation capabilities.

## Implementation Details

### Server-Side Architecture

- Uses Flask-Sock for WebSocket endpoint management
- Implements a robust audio processor selection system with multiple fallback levels
- Provides a custom dual-backend WebSocket implementation that can use either:
  - `websockets` library (primary choice)
  - `aiohttp` library (secondary choice)
  - Official `openai-realtime-client` package's RealtimeClient class (tertiary choice)
  - Standard OpenAI API (final fallback)
- Automatic error detection and recovery with graceful degradation
- Headless operation support for server environments without X11/display
- Enhanced logging for troubleshooting WebSocket connection issues

### Client-Side Integration

- Supports standard WebAudio API for client-side audio capture
- Handles streaming binary audio data between client and server
- Provides unified WebSocket event handling regardless of backend implementation
- Includes demo implementation for testing and integration reference
- Support for both browser-based and Twilio phone call audio formats

## Installation

To use the real-time audio features, install the required dependencies:

```bash
# Install system dependencies (if using microphone directly - not needed for Twilio integration)
sudo apt-get install portaudio19-dev

# Install Python packages
pip install openai-realtime-client flask-sock==0.7.0 simple-websocket==1.1.0 websockets==13.1 aiohttp==3.11.13
```

### Handling X11 Display Requirements

The system offers two approaches to handle the OpenAI Realtime client's X11 display dependency:

#### Option 1: Headless Mode (Default, Recommended)

The system uses a custom dual-backend WebSocket implementation that bypasses the X11 dependency entirely. This mode is automatically active and requires no additional configuration. It works by:

1. Using either `websockets` or `aiohttp` libraries directly
2. Implementing the OpenAI Realtime WebSocket protocol without the official client
3. Following a comprehensive fallback hierarchy when libraries are unavailable

#### Option 2: Virtual X Server (Alternative)

If you prefer to use the official OpenAI Realtime client with its X11 dependency, you can set up a virtual X server:

```bash
# Install virtual X server
apt-get update && apt-get install -y xvfb x11-utils xorg

# Start virtual X server
Xvfb :99 -screen 0 1024x768x16 -ac &
export DISPLAY=:99

# Test X server connection
xdpyinfo > /dev/null 2>&1 && echo "X server is working" || echo "X server failed"
```

To use this option with Docker, set the `USE_XVFB` environment variable to `true`:

```bash
docker run -e USE_XVFB=true -p 8080:8080 redbarushiai:latest
```

### Fallback Hierarchy

The system follows this fallback hierarchy to ensure it works in all environments:

1. Try to use `websockets` library for WebSocket communication (preferred)
2. If `websockets` is unavailable, try to use `aiohttp` for WebSocket communication
3. If neither library is available, try to use the official `openai-realtime-client` RealtimeClient class (with X11 if available)
4. If RealtimeClient has API incompatibilities, try various methods to adapt to available functionality
5. If official client is unavailable or incompatible, fall back to standard OpenAI API calls

This makes the system very resilient to different environment configurations and API changes.

## Client Integration

To integrate this into your own client applications:

1. Check server capabilities using the `/api/ws/capabilities` endpoint
2. Connect to the appropriate WebSocket endpoint
3. Stream audio data in chunks or send text messages
4. Process responses (transcriptions, AI messages, audio data) as they arrive

See the demo implementation in `app/static/js/realtime_demo.js` for a complete example.

## WebSocket API Reference

### Speech-to-Text

**Endpoint**: `/api/ws/speech-to-text`

**Client to Server**:
- Binary audio data chunks
- Control messages (JSON):
  - `{"type": "end"}` - Signal the end of audio stream

**Server to Client** (JSON):
- `{"type": "connection_established", "session_id": "uuid", "message": "Ready to receive audio"}`
- `{"type": "transcript", "text": "partial transcript", "final": false, "timestamp": 1234567890}`
- `{"type": "transcript_complete", "text": "final transcript", "final": true, "timestamp": 1234567890}`
- `{"type": "error", "error": "error message"}`
- `{"type": "session_complete", "session_id": "uuid", "message": "Processing complete"}`

### Text-to-Speech

**Endpoint**: `/api/ws/text-to-speech`

**Client to Server** (JSON):
- `{"type": "text", "text": "Text to convert to speech", "voice": "alloy"}`
- `{"type": "end"}` - Close the session

**Server to Client**:
- JSON: `{"type": "connection_established", "message": "Ready to receive text for speech synthesis"}`
- JSON: `{"type": "speech_starting", "timestamp": 1234567890}`
- Binary audio data chunks
- JSON: `{"type": "speech_complete", "timestamp": 1234567890}`
- JSON: `{"type": "error", "error": "error message"}`
- JSON: `{"type": "session_complete", "message": "Text-to-speech session complete"}`

### Conversation

**Endpoint**: `/api/ws/conversation`

**Client to Server**:
- Binary audio data chunks
- Control messages (JSON):
  - `{"type": "text", "text": "Text input instead of audio"}`
  - `{"type": "end"}` - Signal the end of audio stream

**Server to Client**:
- JSON: `{"type": "connection_established", "session_id": "uuid", "message": "Ready to receive audio or text"}`
- JSON: `{"type": "transcript", "text": "partial transcript", "final": false, "timestamp": 1234567890}`
- JSON: `{"type": "transcript_complete", "text": "final transcript", "final": true, "timestamp": 1234567890}`
- JSON: `{"type": "message", "text": "partial AI response", "complete": false, "timestamp": 1234567890}`
- JSON: `{"type": "message_complete", "text": "complete AI response", "complete": true, "timestamp": 1234567890}`
- JSON: `{"type": "speech_starting", "timestamp": 1234567890}`
- Binary audio data chunks
- JSON: `{"type": "speech_complete", "timestamp": 1234567890}`
- JSON: `{"type": "error", "error": "error message"}`
- JSON: `{"type": "session_complete", "session_id": "uuid", "message": "Processing complete"}`

## Supported Audio Formats

- WebM (recommended for browser-based applications)
- MP3
- WAV

## Supported Voices

All OpenAI TTS voices are supported:

- alloy
- echo
- fable
- onyx
- nova
- shimmer