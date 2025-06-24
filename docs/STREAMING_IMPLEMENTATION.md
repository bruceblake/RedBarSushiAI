# Streaming AI Responses Implementation

## Overview

This document describes the implementation of streaming AI responses in RedBarSushiAI to reduce perceived latency and improve user experience during voice conversations.

## Problem Statement

Previously, the system would:
1. Receive user speech (transcribed by Twilio)
2. Process with AI (1-3 seconds)
3. Send complete response back to Twilio
4. Twilio performs TTS and plays audio

This created a noticeable delay where users heard nothing while AI processing occurred.

## Solution: Streaming Responses

The new implementation streams AI responses in chunks, allowing Twilio to start TTS playback while the AI is still generating the rest of the response.

### Architecture Changes

1. **AI Mixin Enhancement** (`app/agents/ai_mixin.py`)
   - Added `process_with_ai_streaming()` method
   - Implements smart chunking based on sentence boundaries
   - Maintains complete response for logging/context

2. **ConversationRelay Handler** (`app/api/conversation_relay/handler.py`)
   - Updated `handle_prompt()` to support streaming callbacks
   - Sends text chunks with `"last": false` for partial responses
   - Final chunk sent with `"last": true`

3. **Agent Orchestrator** (`app/utils/agent_orchestration_async.py`)
   - Added `process_voice_input_streaming()` method
   - Routes streaming requests to appropriate agents
   - Falls back to non-streaming for tool-using responses

4. **Frontline Agent** (`app/agents/frontline_async_ai.py`)
   - Updated handlers to accept streaming callbacks
   - Implements fast acknowledgments for better UX

## Implementation Details

### Streaming Flow

```python
# 1. ConversationRelay receives user speech
voice_prompt = "Hi, my name is John"

# 2. Handler creates streaming callback
async def stream_callback(chunk: str, is_last: bool):
    await self.send_text(chunk, is_last)

# 3. Orchestrator processes with streaming
response = await orchestrator.process_voice_input_streaming(
    call_sid, voice_prompt, stream_callback
)

# 4. AI generates and streams chunks
# Chunk 1: "Nice to meet you, John!" (sent immediately)
# Chunk 2: "How can I help you today?" (sent when ready)
```

### Chunking Strategy

The system uses intelligent chunking to ensure natural speech:

1. **Sentence Boundaries**: Chunks end at `.`, `!`, `?`, `:`, or newlines
2. **Phrase Boundaries**: Long sentences chunk at commas or spaces
3. **Minimum Size**: Chunks must be meaningful (>20 chars) before breaking
4. **Maximum Buffer**: Prevents excessive buffering (>50 chars triggers chunking)

### When Streaming is Used

Streaming is enabled for:
- Initial greetings
- Main menu interactions
- General responses without tool calls

Streaming is disabled for:
- Responses requiring tool calls (menu lookup, cart operations)
- Complex multi-step operations
- Error fallback messages

## Performance Benefits

1. **Reduced Perceived Latency**: Users hear first response in ~0.5s vs 2-3s
2. **Natural Conversation Flow**: Mimics human speech patterns
3. **Better UX**: Users know the system is responding immediately
4. **Graceful Degradation**: Falls back to non-streaming when needed

## Configuration

Key settings in `app/config.py`:
```python
AI_MAX_TOKENS = 256  # Maximum tokens for responses
FRONTEND_AGENT_MAX_TOKENS = 150  # Tokens for frontline agent
DEFAULT_LLM_API_TIMEOUT = 10.0  # API timeout
OPENAI_CLIENT_POOL_SIZE = 5  # Connection pool size
```

## Testing

Use the test script to see streaming in action:
```bash
python test_streaming.py
```

## Future Enhancements

1. **Adaptive Chunking**: Adjust chunk size based on network conditions
2. **Interruption Handling**: Better support for user interruptions during streaming
3. **Multi-Language**: Streaming support for multiple languages
4. **Advanced Caching**: Cache and stream common response patterns

## Troubleshooting

### Issue: Choppy Audio
**Solution**: Increase minimum chunk size or adjust sentence boundaries

### Issue: Long Initial Delay
**Solution**: Check if response requires tools; consider pre-warming responses

### Issue: Incomplete Responses  
**Solution**: Ensure `"last": true` is sent for final chunk

## Conclusion

Streaming AI responses significantly improves the perceived responsiveness of RedBarSushiAI, creating a more natural and engaging conversation experience for users ordering by phone.