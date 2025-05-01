#!/usr/bin/env python3
"""
Standalone script to interact directly with OpenAI's Realtime API
Bypassing the openai-realtime-client package which has dependency issues
"""

import asyncio
import websockets
import json
import base64
import time
import os
import logging
import uuid
from typing import Dict, Any, AsyncGenerator, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Get API key from environment
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable must be set")


class RealtimeSession:
    """Direct implementation of OpenAI's Realtime API using WebSockets"""

    # OpenAI Realtime API endpoint
    WEBSOCKET_URL = "wss://api.openai.com/v1/realtime"

    def __init__(self, api_key: str):
        """Initialize the session"""
        self.api_key = api_key
        self.session_id = None
        self.websocket = None
        self.events_queue = asyncio.Queue()
        self._listening_task = None

    async def connect(self, session_config: Dict[str, Any] = None):
        """Connect to the OpenAI Realtime API"""
        if session_config is None:
            session_config = {}

        # Create a new session
        self.session_id = str(uuid.uuid4())
        logger.info(f"Creating new session with ID: {self.session_id}")

        # Connect to the WebSocket
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            self.websocket = await websockets.connect(
                self.WEBSOCKET_URL, extra_headers=headers
            )

            # Initialize session
            await self.send_event({"type": "session.update", "session": session_config})

            # Start listening for events
            self._listening_task = asyncio.create_task(self._listen_for_events())

            # Wait for the session.created event
            session_created = False
            timeout = 10
            start_time = time.time()
            while not session_created and time.time() - start_time < timeout:
                event = await asyncio.wait_for(self.events_queue.get(), timeout=5)
                if event.get("type") == "session.created":
                    session_created = True
                    self.session_id = event.get("session", {}).get("id")
                    logger.info(f"Session created with ID: {self.session_id}")

            if not session_created:
                raise ConnectionError("Timed out waiting for session.created event")

            return self.session_id
        except Exception as e:
            logger.error(f"Error connecting to OpenAI Realtime API: {e}")
            raise

    async def send_event(self, event: Dict[str, Any]):
        """Send an event to the OpenAI Realtime API"""
        if not self.websocket:
            raise RuntimeError("Not connected to OpenAI Realtime API")

        try:
            await self.websocket.send(json.dumps(event))
        except Exception as e:
            logger.error(f"Error sending event: {e}")
            raise

    async def _listen_for_events(self):
        """Listen for events from the OpenAI Realtime API"""
        if not self.websocket:
            raise RuntimeError("Not connected to OpenAI Realtime API")

        try:
            while True:
                message = await self.websocket.recv()
                event = json.loads(message)
                await self.events_queue.put(event)
                logger.debug(f"Received event: {event.get('type')}")
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error listening for events: {e}")

    async def close(self):
        """Close the WebSocket connection"""
        if self.websocket:
            await self.websocket.close()
            if self._listening_task:
                self._listening_task.cancel()
                try:
                    await self._listening_task
                except asyncio.CancelledError:
                    pass

    async def get_next_event(self, timeout=None):
        """Get the next event from the queue"""
        try:
            if timeout:
                return await asyncio.wait_for(self.events_queue.get(), timeout)
            else:
                return await self.events_queue.get()
        except asyncio.TimeoutError:
            return None

    async def events(self, timeout=30):
        """Generator to yield events"""
        start_time = time.time()
        try:
            while True:
                if timeout and time.time() - start_time > timeout:
                    logger.warning(
                        f"Timed out waiting for events after {timeout} seconds"
                    )
                    break

                event = await self.get_next_event(timeout=1)
                if event:
                    yield event
        except Exception as e:
            logger.error(f"Error in events generator: {e}")
            raise


async def speech_to_text_example(audio_file_path: str):
    """Example of using the Realtime API for speech-to-text"""
    session = RealtimeSession(api_key=OPENAI_API_KEY)

    try:
        # Connect to the API with audio format configuration
        await session.connect(
            session_config={
                "input_audio_format": {"type": "audio/webm"},
                "output_audio_format": {"type": "audio/mp3"},
            }
        )

        # Read audio file
        with open(audio_file_path, "rb") as f:
            audio_data = f.read()

        # Convert to base64
        base64_audio = base64.b64encode(audio_data).decode("utf-8")

        # Append to audio buffer
        await session.send_event(
            {"type": "input_audio_buffer.append", "audio": base64_audio}
        )

        # Signal end of audio
        await session.send_event({"type": "input_audio_buffer.commit"})

        # Create a response to get transcription
        await session.send_event(
            {"type": "response.create", "response": {"modalities": ["text"]}}
        )

        # Process events
        transcript = ""
        async for event in session.events():
            if event.get("type") == "response.audio_transcript.delta":
                delta = event.get("delta", "")
                transcript += delta
                print(f"Transcript (in progress): {transcript}")
            elif event.get("type") == "response.audio_transcript.done":
                print(f"Final transcript: {transcript}")
                break

        # Close the session
        await session.close()

        return transcript
    except Exception as e:
        logger.error(f"Error in speech to text example: {e}")
        if session.websocket:
            await session.close()
        raise


async def text_to_speech_example(text: str, voice: str = "alloy"):
    """Example of using the Realtime API for text-to-speech"""
    session = RealtimeSession(api_key=OPENAI_API_KEY)

    try:
        # Connect to the API with audio format configuration
        await session.connect(
            session_config={"output_audio_format": {"type": "audio/mp3"}}
        )

        # Create a conversation item with the text
        await session.send_event(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": text}],
                },
            }
        )

        # Create a response with TTS
        await session.send_event(
            {
                "type": "response.create",
                "response": {"modalities": ["text", "audio"], "voice": voice},
            }
        )

        # Process events and save audio
        audio_data = bytearray()
        output_file = f"realtime_tts_{int(time.time())}.mp3"

        async for event in session.events():
            if event.get("type") == "response.audio.delta":
                delta = event.get("delta", "")
                if delta:
                    chunk = base64.b64decode(delta)
                    audio_data.extend(chunk)
                    print(f"Received audio chunk: {len(chunk)} bytes")
            elif event.get("type") == "response.audio.done":
                print(f"Audio generation complete. Total size: {len(audio_data)} bytes")
                break

        # Save the audio
        with open(output_file, "wb") as f:
            f.write(audio_data)

        print(f"Audio saved to {output_file}")

        # Close the session
        await session.close()

        return output_file
    except Exception as e:
        logger.error(f"Error in text to speech example: {e}")
        if session.websocket:
            await session.close()
        raise


async def conversation_example(text: str):
    """Example of using the Realtime API for conversation"""
    session = RealtimeSession(api_key=OPENAI_API_KEY)

    try:
        # Connect to the API
        await session.connect()

        # Add a system message
        await session.send_event(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "You are an AI assistant for Red Bar Sushi restaurant. "
                            "Be helpful, concise, and friendly. Provide restaurant information "
                            "and take orders accurately.",
                        }
                    ],
                },
            }
        )

        # Add a user message
        await session.send_event(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": text}],
                },
            }
        )

        # Create a response
        await session.send_event(
            {"type": "response.create", "response": {"modalities": ["text"]}}
        )

        # Process events
        response_text = ""
        async for event in session.events():
            if event.get("type") == "response.text.delta":
                delta = event.get("delta", "")
                response_text += delta
                print(f"Response (in progress): {response_text}", end="\r")
            elif event.get("type") == "response.text.done":
                print(f"\nFinal response: {response_text}")
                break

        # Close the session
        await session.close()

        return response_text
    except Exception as e:
        logger.error(f"Error in conversation example: {e}")
        if session.websocket:
            await session.close()
        raise


async def main():
    """Main function to demonstrate Realtime API"""
    import argparse

    parser = argparse.ArgumentParser(description="OpenAI Realtime API Demo")
    parser.add_argument(
        "--mode",
        choices=["stt", "tts", "conversation"],
        required=True,
        help="Mode to run: speech-to-text, text-to-speech, or conversation",
    )
    parser.add_argument("--audio", help="Path to audio file for speech-to-text")
    parser.add_argument("--text", help="Text for text-to-speech or conversation")
    parser.add_argument(
        "--voice",
        default="alloy",
        help="Voice for text-to-speech (alloy, echo, fable, onyx, nova, shimmer)",
    )

    args = parser.parse_args()

    if args.mode == "stt":
        if not args.audio:
            parser.error("--audio is required for speech-to-text mode")
        await speech_to_text_example(args.audio)
    elif args.mode == "tts":
        if not args.text:
            parser.error("--text is required for text-to-speech mode")
        await text_to_speech_example(args.text, args.voice)
    elif args.mode == "conversation":
        if not args.text:
            parser.error("--text is required for conversation mode")
        await conversation_example(args.text)


if __name__ == "__main__":
    asyncio.run(main())
