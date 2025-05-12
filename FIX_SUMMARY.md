# RedBarSushiAI WebSocket Fixes Summary

## Overview of Fixes

The following critical issues have been fixed in the WebSocket implementation for the RedBarSushiAI voice system:

1. **Enhanced `request_response` Method**
   - Added robust error handling and connection state validation
   - Improved logging with call SID context for better debugging
   - Ensured proper flow from handler call to TTS generation

2. **Improved WebSocket Connection Management**
   - Enhanced task lifecycle management to prevent the "cannot call recv" error
   - Added better error classification and handling for different WebSocket events
   - Implemented proper event loop management with controlled shutdown

3. **Added API Key Validation**
   - Added detection for test/dummy API keys that will be rejected by OpenAI
   - Improved logging to clearly identify API key issues before they cause runtime errors
   - Enhanced error messages to guide troubleshooting

## Technical Details of Fixes

### 1. Request Response Method Enhancement

The `request_response` method is called by the voice handler to generate TTS for greetings and responses. We've enhanced it by:

- Adding connection state validation to fail fast if the WebSocket is not connected
- Checking if the WebSocket is still open before attempting to send messages
- Adding detailed logging with call SID context for better debugging
- Properly forwarding to `send_text_for_tts` with exception handling

```python
async def request_response(self, text: str, response_id: Optional[str] = None):
    """
    Requests OpenAI to generate TTS for the given text.
    This is an alias for send_text_for_tts to maintain compatibility with handlers.py.
    
    Args:
        text: The text to convert to speech
        response_id: Optional unique ID for the response
    """
    call_sid = getattr(self, 'session_id', 'UNKNOWN_CALL')
    logger.critical(f"🔄 [{call_sid}] request_response CALLED for text: \"{text}\"")
    
    # Connection validation and error handling...
    
    try:
        await self.send_text_for_tts(text)
        return True
    except Exception as e:
        logger.critical(f"🔴 [{call_sid}] EXCEPTION in request_response: {str(e)}")
        raise
```

### 2. WebSocket Connection and Task Management

The most critical issue was the "cannot call recv while another coroutine is already waiting for the next message" error. We've fixed this by:

- Using `async for message in self.websocket` with proper task management
- Implementing controlled task cancellation in `close()` method
- Adding a flag `is_processing_loop_active` to properly signal loop termination
- Implementing specific error detection for invalid API keys to exit loops cleanly
- Adding separate handling for normal vs. abnormal WebSocket closure

```python
# In process_messages()
self.is_processing_loop_active = True
try:
    # Using async for is safer but needs proper loop control
    async for message in self.websocket:
        if not self.is_processing_loop_active or not self.running:
            logger.info(f"[{call_sid}] Event loop flagged to stop, breaking")
            break
        
        # Process messages...
        
        # Special handling for API key errors
        if event_type in ["error", "session.error"]:
            # Check for specific error types that should trigger clean shutdown
            if "error" in event:
                error_code = error_info.get("code", "")
                if error_code == "invalid_api_key":
                    self.is_processing_loop_active = False
                    break
```

### 3. Graceful Connection Closure

We've completely rewritten the `close()` method to ensure proper cleanup:

- First signals the processing loop to stop before touching the socket
- Waits briefly for the loop to exit gracefully before forcing cancellation
- Properly checks if the WebSocket is still open before attempting to close it
- Includes comprehensive logging of the closure process

```python
async def close(self):
    """Close the connection to the OpenAI Realtime API."""
    call_sid = getattr(self, 'session_id', 'UNKNOWN_CALL')
    
    # Signal the loop to stop first
    self.running = False
    self.is_processing_loop_active = False
    
    # Give the loop a chance to exit gracefully
    if self._event_processing_task and not self._event_processing_task.done():
        try:
            await asyncio.wait_for(asyncio.shield(self._event_processing_task), timeout=0.5)
        except asyncio.TimeoutError:
            # If it doesn't exit quickly, cancel it
            self._event_processing_task.cancel()
            # Wait for cancellation to complete...
    
    # Now close the actual WebSocket
    if self.websocket:
        is_open = getattr(self.websocket, 'open', False)
        if is_open:
            await self.websocket.close(1000, "Closing connection normally")
```

### 4. API Key Validation and Early Warning

Added extra validation for API keys to detect common issues early:

```python
# Check for test/dummy key patterns
test_key_patterns = ['mytestapikey', 'test', 'dummy', 'sample', 'example']
if any(pattern in self.api_key.lower() for pattern in test_key_patterns):
    logger.critical(f"🔴 [{self.session_id}] CRITICAL WARNING: API key appears to be a test/dummy key: {key_preview}")
    logger.critical(f"🔴 [{self.session_id}] This key will NOT work with OpenAI. Please use a real API key!")
```

## Testing and Verification

To verify the fixes are working properly:

1. **Test the WebSocket Connection**:
   - Make a call to your Twilio phone number
   - Check the logs for successful WebSocket connection and greeting TTS

2. **Test with a Valid OpenAI API Key**:
   - Update your .env.development file with a valid OpenAI API key
   - Ensure the key has access to the gpt-4o-realtime-preview-2024-10-01 model
   - Restart your Docker containers with `./restart_docker.sh`

3. **Test the Error Handling**:
   - Observe how the system handles invalid API keys more gracefully
   - Check logs for specific error messages that pinpoint issues

## Common Issues and Solutions

1. **"OpenAI API Key appears to be a test/dummy key"**:
   - Your API key is not valid - it contains test patterns like "mytestapikey"
   - Solution: Replace with a real OpenAI API key in your .env.development file

2. **"WebSocket CONNECTION CLOSED WITH ERROR: code=3000, reason=invalid_request_error.invalid_api_key"**:
   - OpenAI rejected your API key
   - Solution: Ensure you're using a valid key with access to the specific model

3. **"AttributeError: 'OpenAIRealtimeClient' object has no attribute 'request_response'"**:
   - If this still occurs, the codebase may be using a different version of the file
   - Solution: Check for cached .pyc files or rebuild Docker container with `./force_rebuild.sh`

## Next Steps

1. **Update API Key**: Set a valid OpenAI API key in your .env.development file:
   ```
   # In your .env.development
   OPENAI_API_KEY=sk-your-actual-openai-key
   ```

2. **Rebuild Docker**: Run `./force_rebuild.sh && ./restart_docker.sh`

3. **Test End-to-End**: Make a call to your Twilio number and verify:
   - Connection to OpenAI is established
   - Greeting TTS is generated and played
   - Voice conversation proceeds normally

## Conclusion

These fixes address the core issues with WebSocket connection management in the RedBarSushiAI voice system. The implementation now handles:

- Proper WebSocket lifecycle management
- Robust error detection and recovery
- Clear error reporting for debugging
- Graceful task cancellation and resource cleanup

With these fixes and a valid API key, the system should be able to successfully establish a WebSocket connection with OpenAI, send greeting text for TTS, receive audio responses, and maintain a stable connection throughout the call.