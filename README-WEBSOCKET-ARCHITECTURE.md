# WebSocket Architecture for Twilio Media Streams

This document describes the architecture of the WebSocket implementation for Twilio Media Streams in RedBarSushiAI.

## Overview

The WebSocket implementation consists of three main components:

1. **TwiML Generation (HTTP)**: When Twilio calls our webhook, we generate TwiML that tells Twilio where to connect its WebSocket.
2. **FastAPI WebSocket Route**: A WebSocket endpoint that accepts connections from Twilio and handles bidirectional audio streaming.
3. **OpenAI Realtime Client**: A client that connects to OpenAI's Realtime API for processing audio and generating responses.

## Critical Path Alignment

For the WebSocket connection to work properly, the following paths must align exactly:

1. **TwiML WebSocket URL**: Defined in `app/api/voice.py` as:
   ```python
   ws_url = f"{ws_base_url}/realtime/ws/media/{call_sid}"
   ```

2. **FastAPI WebSocket Route**: Defined in `app/api/voice_async.py` as:
   ```python
   @router.websocket("/ws/media/{call_sid}")
   ```
   
   And registered in `app/api/__init__.py` with the prefix `/realtime`:
   ```python
   api_router.include_router(voice_async_router, prefix="/realtime")
   ```

   Resulting in the effective route: `/realtime/ws/media/{call_sid}`

The TwiML-generated URL and the FastAPI route **MUST** match exactly for the WebSocket connection to be established successfully.

## Validation

You can validate the path alignment with the `verify_ws_paths.py` script:

```bash
python verify_ws_paths.py
```

## Architecture Flow

1. Twilio calls the HTTP endpoint (`/voice` or `/webhook/voice`) defined in `app/api/voice.py`.
2. The endpoint generates TwiML with a WebSocket URL pointing to `/realtime/ws/media/{call_sid}`.
3. Twilio establishes a WebSocket connection to that URL, which is handled by `handle_media_stream()` in `app/api/voice_async.py`.
4. The WebSocket handler connects to OpenAI's Realtime API using `OpenAIRealtimeClient` from `app/utils/realtime_audio_async.py`.
5. Audio is streamed bidirectionally between Twilio and OpenAI, with processing by our AI agents.

## Warning

Do not modify the WebSocket routes or URL generation without ensuring alignment between all components. Any mismatch will cause the WebSocket connection to fail, resulting in the "couldn't connect" message being played to the user.