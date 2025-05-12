# WebSocket Architecture & Fixes for RedBarSushiAI

This document provides an overview of the WebSocket architecture used in RedBarSushiAI and details the fixes implemented to resolve critical issues with the OpenAI Realtime API integration.

## WebSocket Architecture

RedBarSushiAI uses a robust WebSocket implementation for real-time voice communication:

1. **Client-Server Communication Flow**:
   ```
   Twilio Media Stream → FastAPI WebSocket Endpoint → OpenAI Realtime API → FastAPI WebSocket Endpoint → Twilio Media Stream
   ```

2. **Key Components**:
   - **Twilio Webhook & TwiML**: Generates TwiML with `<Connect><Stream>` to establish media connection
   - **FastAPI WebSocket Handler**: Manages connection with Twilio at `/ws/media/{call_sid}`
   - **OpenAIRealtimeClient**: Handles WebSocket connection to OpenAI's Realtime API
   - **Async Task Management**: Uses asyncio tasks for concurrent operations

3. **Message Flow**:
   - Twilio sends audio chunks to FastAPI WebSocket endpoint
   - FastAPI forwards audio to OpenAI via `input_audio_buffer.append` events
   - OpenAI processes audio and returns transcripts via `transcript.final` events
   - Agent system processes transcripts and generates responses
   - Responses are sent to OpenAI for TTS via `request_response` method
   - OpenAI returns audio chunks via `response.audio.delta` events
   - FastAPI forwards audio back to Twilio

## Recent Fixes (May 2025)

The following critical issues have been fixed in the WebSocket implementation:

### 1. Method Naming Mismatch
Fixed the `AttributeError: 'OpenAIRealtimeClient' object has no attribute 'request_response'` by enhancing the existing method with:
- Connection state validation
- Detailed logging
- Error handling
- Proper call SID context

### 2. WebSocket Connection Management
Addressed the `RuntimeError: cannot call recv while another coroutine is already waiting for the next message` by:
- Using safe `async for message in self.websocket` pattern
- Adding proper task management with flags
- Implementing graceful cancellation
- Adding connection state tracking 
- Handling connection errors properly

### 3. Task Lifecycle Management
Improved task management with:
- Proper task tracking and cancellation
- Timeout-based graceful shutdown before forced cancellation
- Resource cleanup in finally blocks
- State flags for clean loop termination

### 4. API Key Validation
Added proactive detection of:
- Missing API keys
- Test/dummy API keys (e.g., "sk-mytestapikey")
- Improperly formatted API keys
- Better error handling for API key issues

## Key Files

1. **`app/api/voice/handlers.py`**:
   - Manages WebSocket connections from Twilio
   - Creates and manages OpenAI client connections
   - Establishes initial greeting and conversation flow

2. **`app/utils/realtime_audio_async.py`**:
   - Contains the `OpenAIRealtimeClient` class
   - Manages WebSocket connection to OpenAI Realtime API
   - Handles message processing and event dispatch

## Testing & Verification

1. **Test Script**:
   - Use `test_realtime_client.py` to test the WebSocket implementation
   - Validates client initialization, connection, and TTS request handling

2. **Prerequisites**:
   - Valid OpenAI API key with access to Realtime API
   - Proper environment configuration

## Previous Fixes (May 2024)

These were earlier fixes to address initial WebSocket stability issues:

1. **Enhanced Route Registration** (`app/routes/voice/__init__.py`): Checks both route paths and function names to prevent duplicates.
2. **Improved Worker Configuration** (`Procfile`): Added graceful shutdown parameters to prevent abrupt termination.
3. **Multiple Keep-Alive Messages** (`app/routes/voice/handlers.py`): Implemented a sequence of keep-alive messages during critical phases.
4. **Enhanced TwiML Generation** (`app/routes/voice/twilio/twiml.py`): Added strategic pauses between connection steps.
5. **Task Preservation** (`app/routes/voice/realtime/stream_handler.py`): Added task tracking to prevent garbage collection.

## Usage Guidelines

### 1. Proper WebSocket Endpoint URL

When configuring Twilio, ensure the WebSocket URL is correctly formatted:
```xml
<Connect>
  <Stream url="wss://your-domain.com/ws/media/{{CallSid}}">
    <Parameter name="track" value="inbound_track"/>
  </Stream>
</Connect>
```

### 2. API Key Configuration

Ensure your OpenAI API key is:
- Valid and active
- Has access to the GPT-4o Realtime API
- Properly configured in environment variables
- Formatted correctly (starts with "sk-")

### 3. Error Handling

Common errors and solutions:
- **WebSocket Connection Failures**: Check network connectivity and TwiML format
- **OpenAI API Rejections**: Verify API key and model access
- **Task Cancellation Issues**: Check for proper resource cleanup

## Further Reading

For more details:
- [FIX_SUMMARY.md](/FIX_SUMMARY.md) - Comprehensive breakdown of the fixes
- [WEBSOCKET_FIX_CHANGES.md](/WEBSOCKET_FIX_CHANGES.md) - Summary of code changes
- [CLAUDE.md](/CLAUDE.md) - Complete project documentation