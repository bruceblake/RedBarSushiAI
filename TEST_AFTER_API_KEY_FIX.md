# OpenAI Realtime API WebSocket Connection Fix

This document outlines the fixes implemented to resolve the OpenAI Realtime API connection issues and provides instructions for testing.

## Changes Made

1. **OpenAI WebSocket Connection URL Fix**
   - Added the required `model` parameter as a query parameter in the WebSocket URL as required by OpenAI's documentation
   - Modified the `connect()` method in `app/utils/realtime_audio_async.py` to properly construct the URL with query parameters using `urlencode`
   - The URL now follows the format OpenAI expects: `wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01&voice=shimmer`
   - Added thorough validation and error handling for required parameters

2. **OpenAI Session Configuration Enhancements**
   - Updated the `_configure_session()` method to fully align with OpenAI's documentation
   - Added detailed audio format specifications with fallback to simplified format
   - Included additional fields like `stream_priority`, `interrupt_types`, and `buffer_ms` with sensible defaults
   - Implemented proper filtering of `None` values to maintain a clean configuration payload

3. **Audio Input/Output Message Format Fixes**
   - Updated the `send_audio()` method to use the correct format for sending audio to OpenAI:
     ```json
     {
       "type": "input_audio_buffer.append",
       "input_audio_buffer": {
         "payload": "BASE64_ENCODED_AUDIO",
         "end_of_stream": false
       }
     }
     ```
   - Fixed the `send_text_for_tts()` and `request_response()` methods to include the text to be spoken directly in the `response.create` message:
     ```json
     {
       "type": "response.create",
       "response_id": "UNIQUE_ID",
       "response": {
         "text": "The text to be spoken",
         "responder": {"type": "model"},
         "end_of_response": true,
         "modalities": ["audio"]
       }
     }
     ```
   - Implemented proper response_id generation and tracking

4. **Connection Stability Improvements**
   - Added proper timeout handling for WebSocket connections
   - Enhanced error handling and logging for better diagnostics
   - Improved task management for WebSocket messaging to reduce "cannot call recv" errors

## Summary of Fixes

We've made comprehensive changes to the OpenAI Realtime API integration to fix the "missing_model" error and related issues:

1. **Added model parameter to WebSocket URL**: Fixed the primary issue by including the model as a query parameter in the connection URL.

2. **Improved message formats for audio & TTS**: Updated the payloads for sending audio, requesting TTS, and handling audio responses to match OpenAI's documentation.

3. **Enhanced stability & error handling**: Added proper timeouts, improved task management, and enhanced error detection for WebSocket connections.

For a detailed technical breakdown of all changes, see [OPENAI_REALTIME_FIX_UPDATED.md](OPENAI_REALTIME_FIX_UPDATED.md).

## Testing Instructions

### 1. Verify Your OpenAI API Key

Before testing, ensure your OpenAI API key in `.env.development` is:
- Valid and has access to the OpenAI Realtime API
- Properly configured in the environment file
- Not a test/dummy key

### 2. Test the OpenAI Realtime Client

Run the test script to verify the OpenAI Realtime client can successfully connect and handle API requests:

```bash
python test_realtime_client.py
```

You should see output indicating:
- Successful client initialization
- Successful WebSocket connection to OpenAI
- The WebSocket URL in the logs should include `?model=gpt-4o-realtime-preview-2024-10-01&voice=shimmer`
- No `AttributeError` about missing `request_response` method
- No `RuntimeError` about `cannot call recv while another coroutine is already waiting`
- No `missing_model` error messages from OpenAI

### 3. Local Testing with Docker and ngrok

1. **Start Docker environment with rebuild**:
   ```bash
   ./force_rebuild.sh && ./restart_docker.sh
   ```

2. **Start ngrok for public URL tunneling**:
   ```bash
   ./setup_ngrok.sh
   ```
   Note the public URL displayed by ngrok. You'll use this to configure Twilio.

3. **Update Twilio webhook URL**:
   - Log in to your Twilio account dashboard
   - Go to the Phone Numbers section
   - Select your Twilio phone number
   - Under Voice & Fax > A Call Comes In
   - Update the webhook URL to: `https://YOUR-NGROK-URL/voice/webhook`
   - Save changes

4. **Monitor application logs**:
   ```bash
   docker logs -f redbarsushi-app-1
   ```

5. **Make a test call**:
   - Dial your Twilio phone number
   - Listen for the greeting message
   - Try to interact with the voice assistant

### 4. What to Look For in Logs

#### Success Indicators

1. **WebSocket URL with Query Parameters**:
   ```
   WEBSOCKET CONNECT ATTEMPT: wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01&voice=shimmer
   ```

2. **Session Configuration**:
   ```
   Sending session configuration: {"type": "session.update", "session": {...}}
   ```

3. **Successful OpenAI Connection**:
   ```
   SUCCESSFULLY CONNECTED to OpenAI Realtime API
   Session configuration sent successfully
   ```

4. **No Missing Model Error**:
   The logs should NOT contain:
   ```
   ERROR EVENT FROM OPENAI: {"type": "error", "error": {"code": "missing_model"}}
   ```

5. **Audio Events**:
   ```
   Received audio event: response.audio.delta
   ```

#### Troubleshooting

If you encounter issues:

1. **Check the URL Construction**:
   - Ensure the model parameter is included in the URL
   - The `connect_url` variable should include `?model=...`

2. **Examine Session Configuration**:
   - Verify the session configuration includes all required fields
   - Check for proper audio format specification

3. **API Key Validation**:
   - Invalid API keys will result in 401 errors
   - Check for "invalid_api_key" error messages from OpenAI

4. **Connection Issues**:
   - WebSocket connection failures often indicate networking problems
   - TimeoutError messages suggest connectivity issues

5. **WebSocket Stability**:
   - "cannot call recv while another coroutine is already waiting" errors suggest race conditions
   - Ensure proper task cancellation and cleanup in error cases