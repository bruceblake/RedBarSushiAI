# Real-time Speech & Audio Integration

This document outlines the integration of OpenAI's real-time speech-to-text and text-to-speech APIs with the RedBarSushiAI platform.

## Overview

The real-time audio feature uses WebSockets to provide a low-latency, interactive conversation experience with the AI assistant. This is a significant improvement over the previous implementation, which relied on Twilio for voice interactions.

## Current Implementation Status

The system supports multiple audio processor implementations to accommodate different environments:

1. **DirectRealtimeAudioProcessor** - A direct WebSocket implementation that connects to OpenAI's Realtime API with no dependencies on the OpenAI Realtime client library
2. **HeadlessAudioProcessor** - A fallback implementation for headless environments with no GUI/X11 dependencies 
3. **BasicAudioProcessor** - A simple implementation using OpenAI's standard API for audio processing

For troubleshooting issues with realtime functionality, run:

```bash
python test_realtime_client.py
```

This script will test all available implementations and tell you which ones work in your environment.

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

- Uses Flask-Sock for WebSocket support
- Implements OpenAI's real-time API via the `openai-realtime-client` package
- Supports standard WebAudio API for client-side audio capture
- Handles streaming binary audio data between client and server

## Installation

To use the real-time audio features, install the required dependencies:

```bash
# Install system dependencies
sudo apt-get install portaudio19-dev

# Install Python packages
pip install openai-realtime-client==0.1.0 flask-sock==0.7.0 simple-websocket==1.1.0
```

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