# OpenAI Realtime API Payload Format Fixes

This document outlines the precise changes made to align our OpenAI Realtime API integration with the exact payload formats expected by OpenAI.

## Model Update

Updated the model name to the latest version across the codebase:
- In `app/config.py`: Changed default `OPENAI_REALTIME_MODEL` to `gpt-4o-realtime-preview-2024-12-17` 
- In `.env.development`: Added explicit model configuration
- In `RealtimeConfig` class: Updated default model
- In `RealtimeClientManager`: Updated default configuration
- In all places that create Realtime clients

## Session Configuration Update

Simplified the session.update payload to match documentation exactly:

1. **Removed Problematic Fields**:
   - Removed `stream_priority` which was causing `unknown_parameter` error
   - Removed other undocumented fields like `buffer_ms` and `interrupt_types`

2. **Audio Format Specification**:
   - Changed from simplified `{"type": "mulaw"}` format to explicit:
   ```json
   {
     "container": "raw",
     "encoding": "pcm_mulaw",
     "sample_rate": 8000
   }
   ```

3. **Minimal Session Configuration**:
   - Only including well-documented fields from OpenAI's reference
   - Focus on essential fields: modalities, formats, VAD, instructions

## Conversation Item and Response Creation

Fixed message formats for TTS requests:

1. **Fixed Conversation Item Creation**:
   - Changed `conversationItem` key to `item` in the payload
   - Updated structure to match OpenAI's documentation:
   ```json
   {
     "type": "conversation.item.create",
     "item": {
       "type": "assistant.message",
       "text_content": "Text to be spoken"
     }
   }
   ```

2. **Simplified Response Creation**:
   - Removed potentially problematic fields
   - Ensured `text` appears directly in the response object:
   ```json
   {
     "type": "response.create",
     "response_id": "unique-id",
     "response": {
       "text": "Text to be spoken",
       "responder": {"type": "model"},
       "end_of_response": true
     }
   }
   ```

## Tool Handling Improvements

Updated tool call handling to match OpenAI's documentation:

1. **Tool Call Handling**:
   - Enhanced `_handle_tool_call` to handle multiple possible formats
   - Added detailed logging for tool calls
   - Properly handling string vs JSON arguments

2. **Tool Response Format**:
   - Fixed `send_tool_response` to use the correct payload structure:
   ```json
   {
     "type": "conversation.item.create",
     "item": {
       "type": "tool_result",
       "tool_call_id": "tool-id",
       "content": "tool-result-json"
     }
   }
   ```

## Error Handling Enhancements

Improved error handling throughout the client:

1. **More Comprehensive Error Detection**:
   - Expanded list of fatal error types to handle
   - Added detailed logging for all error parameters
   - Storing last error for future reference

2. **Cleaner Loop Termination**:
   - Setting both `is_processing_loop_active` and `running` to false
   - Immediate break from processing loop on fatal errors
   - Better error information printing

## Next Steps

1. **Testing with Real API Key**:
   - The environment shows you have a valid API key (`sk-proj-...`) configured
   - Verify this key has access to the latest model (`gpt-4o-realtime-preview-2024-12-17`)

2. **Monitoring Error Responses**:
   - The enhanced logging will help identify any remaining payload format issues
   - Each error from OpenAI will be clearly logged with code, message, and parameter

3. **Progressive Testing**:
   - If sessions establish but errors occur with specific messages (like TTS requests),
     the detailed error logging will help isolate those issues for further fixes

The changes made ensure we're strictly following OpenAI's documented message formats and addressing the specific errors seen in previous testing.