# OpenAI Realtime API Parameter Fixes

This document outlines additional fixes to address OpenAI Realtime API parameter issues and WebSocket processing errors.

## 1. Turn Detection Parameter Fix

Fixed the "Unknown parameter: 'session.vad'" error by updating to the correct parameter name:

### Before:
```json
{
  "type": "session.update",
  "session": {
    "modalities": ["text", "audio"],
    "input_audio_format": { /* ... */ },
    "output_audio_format": { /* ... */ },
    "vad": {
      "mode": "server",
      "silence_threshold_ms": 1000,
      "speech_threshold_ms": 8000
    }
  }
}
```

### After (using correct documentation):
```json
{
  "type": "session.update",
  "session": {
    "modalities": ["text", "audio"],
    "input_audio_format": { /* ... */ },
    "output_audio_format": { /* ... */ },
    "turn_detection": {
      "type": "server_vad",
      "silence_duration_ms": 1000,
      "create_response": true
    }
  }
}
```

The key changes:
- Changed `vad` to `turn_detection` (correct parameter name per OpenAI docs)
- Changed `mode` to `type` with value `server_vad`
- Changed `silence_threshold_ms` to `silence_duration_ms`
- Added `create_response: true` to automatically generate responses on turn completion

## 2. Twilio Parameter Handling Enhancement

Enhanced WebSocket handling to properly parse Twilio's custom parameters:

- Added detailed logging of the full start event message from Twilio
- Extracted and stored custom parameters from the start event JSON structure
- Updated call data to include these parameters for use throughout the session

This implementation correctly handles parameters passed via TwiML's `<Parameter>` tags by:
- Inspecting the start event message which contains a structure like:
  ```json
  {
    "event": "start",
    "streamSid": "...",
    "start": {
      "customParameters": {
        "debug": "true",
        "client": "iphone",
        "time": "1621234567"
      }
    }
  }
  ```
- Storing these parameters for reference during the call session

## 3. WebSocket "cannot call recv" Error Fix

Fixed the "cannot call recv while another coroutine is already waiting" error by:

1. Adding explicit checks before creating duplicate process_messages tasks:
   - Verifying that no processing loop is already active
   - Checking if an existing task exists and is still running
   - Reusing the existing task instead of creating a new one

2. Enhancing the process_messages method:
   - Adding an early return if a processing loop is already active
   - Setting a clear flag when the loop becomes active
   - Including detailed logging to identify when duplicate activations occur

3. Improving task tracking:
   - Storing a reference to the created task in the client object
   - Using this reference in subsequent calls to detect duplicates

These changes prevent multiple coroutines from awaiting on the same WebSocket connection's recv() method, which was causing the RuntimeError.

## Testing

To verify these fixes:

1. Confirm that the session.update payload sent to OpenAI no longer contains "vad" but instead uses "turn_detection"
2. Verify custom parameters from TwiML are correctly extracted from the start event message
3. Check that the "cannot call recv while another coroutine is already waiting" error no longer occurs when processing WebSocket messages

The enhanced logging will help trace exactly what's happening with both the OpenAI connection parameters and Twilio start event structure.