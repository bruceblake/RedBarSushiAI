# OpenAI Realtime API Integration Fixes

This document explains the fixes applied to resolve WebSocket connection issues with the OpenAI Realtime API integration.

## Issues Fixed

### Issue 1: Circular Dependency in Event Processor
- **Problem**: `TypeError: RealtimeEventProcessor.__init__() missing 1 required positional argument: 'client'`
- **Fix**: Modified initialization order to create client first, then processor, then set processor on client

### Issue 2: Multiple Coroutines Waiting on WebSocket
- **Problem**: `RuntimeError: cannot call recv while another coroutine is already waiting for the next message`
- **Fix**: Changed from manually calling `await self.websocket.recv()` to using the safer `async for message in self.websocket:` pattern

### Issue 3: Missing Method in OpenAIRealtimeClient
- **Problem**: `AttributeError: 'OpenAIRealtimeClient' object has no attribute 'request_response'`
- **Fix**: Added `request_response` method as an alias to `send_text_for_tts` to maintain compatibility with handlers.py

## Key Changes

### 1. WebSocket Message Processing
```python
# Old pattern (problematic):
while self.running and self.connected:
    message = await self.websocket.recv()  # <-- Could cause RuntimeError

# New pattern (safe):
async for message in self.websocket:
    if not self.is_processing_loop_active or not self.running:
        break
    # Process message
```

### 2. Added Method Compatibility
```python
async def request_response(self, text: str, response_id: Optional[str] = None):
    """
    Requests OpenAI to generate TTS for the given text.
    This is an alias for send_text_for_tts to maintain compatibility with handlers.py.
    """
    logger.critical(f"Requesting response for text: {text}")
    return await self.send_text_for_tts(text)
```

### 3. Task Management
```python
# Added task tracking
self._event_processing_task = None
self.is_processing_loop_active = False

# Proper task cancellation in close() method
if self._event_processing_task and not self._event_processing_task.done():
    self._event_processing_task.cancel()
    try:
        await self._event_processing_task
    except asyncio.CancelledError:
        logger.info("Event processing task successfully cancelled during close")
```

## How to Apply the Fix

1. Run the update script to apply the fixes to the Docker container:
   ```bash
   ./update_methods.sh
   ```

2. Alternatively, start a new Docker environment with the fixed implementation:
   ```bash
   ./start_dev_env.sh up --build
   ```

## Verification

To verify the fixes are working:

1. After deployment, make a test call to your Twilio number

2. Check for the following successful events in the logs:
   - `🟢 [CALL_SID] WebSocket acceptance SUCCESSFUL` - Twilio connection successful
   - `🟢 SUCCESSFULLY CONNECTED to OpenAI Realtime API` - OpenAI connection successful
   - `🔄 [CALL_SID] Sending greeting for TTS: "Hello there! Welcome to Red Bar Sushi"` - Greeting generation
   - `🟢 [CALL_SID] Successfully sent greeting for TTS` - TTS successfully requested

3. Confirm audio flows in both directions:
   - Audio from Twilio to OpenAI: `Forwarding audio chunk to OpenAI Realtime API`
   - Audio from OpenAI to Twilio: `Processed audio chunk from OpenAI Realtime API`

## Environment Variable Requirements

Ensure these critical environment variables are set:

| Variable | Description | Status |
|----------|-------------|--------|
| `OPENAI_API_KEY` | OpenAI API key | **Required** |
| `TWILIO_ACCOUNT_SID` | Twilio account SID | **Required** |
| `TWILIO_AUTH_TOKEN` | Twilio authentication token | **Required** |
| `TWILIO_PHONE_NUMBER` | Twilio phone number | **Required** |
| `SECRET_KEY` | Application secret key | **Required** |

## Troubleshooting

If issues persist:

1. **Check logs for specific error messages**:
   - API key errors: `🔴 OPENAI API KEY MISSING`
   - Connection errors: `🔴 CONNECTION FAILED`
   - Method errors: Look for `AttributeError` mentions

2. **Verify environment variables**:
   ```bash
   docker exec redbarsushi-app env | grep -E 'OPENAI|TWILIO|SECRET'
   ```

3. **Test OpenAI API connectivity**:
   ```bash
   docker exec redbarsushi-app python /app/verify_openai_api_simple.py
   ```

4. **Verify method implementation**:
   ```bash
   docker exec redbarsushi-app python /app/verify_methods.py
   ```