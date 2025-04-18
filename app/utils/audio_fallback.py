"""
Headless audio fallback utilities that don't require X11 or any GUI components.
This module provides minimal audio processing capabilities for environments
without display servers, such as Docker containers.
"""

import os
import logging
import tempfile
import time
from typing import Dict, Any

# Force headless mode without X11 dependency
os.environ["PYNPUT_HEADLESS"] = "1"
os.environ["NO_X11"] = "1"
os.environ["HEADLESS"] = "1"
os.environ["OPENAI_REALTIME_NO_DISPLAY"] = "1"

# Explicitly remove DISPLAY to avoid X11 connection attempts
if "DISPLAY" in os.environ:
    del os.environ["DISPLAY"]

# Import OpenAI
from openai import OpenAI

# Get the OpenAI API key from agent_utils
try:
    from app.utils.agent_utils import OPENAI_API_KEY
except ImportError:
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

logger = logging.getLogger(__name__)

# Create OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)


class HeadlessAudioProcessor:
    """
    A minimal audio processor implementation that works in headless environments
    without any GUI or X11 dependencies.
    """

    def __init__(self):
        """Initialize the headless audio processor."""
        self.openai_client = client

    async def process_audio(
        self, audio_data: bytes, content_type: str = "audio/webm"
    ) -> Dict[str, Any]:
        """
        Process audio data to text using OpenAI's speech-to-text API.

        Args:
            audio_data: The complete audio data
            content_type: The content type of the audio

        Returns:
            Dict containing the transcript
        """
        try:
            logger.info(
                f"[HEADLESS] Processing audio with content type: {content_type}"
            )

            # Create a temporary file to store the audio
            with tempfile.NamedTemporaryFile(
                suffix=".webm" if "webm" in content_type else ".mp3"
            ) as temp_file:
                temp_file.write(audio_data)
                temp_file.flush()

                # Process with OpenAI
                with open(temp_file.name, "rb") as audio_file:
                    response = self.openai_client.audio.transcriptions.create(
                        model="whisper-1", file=audio_file, language="en"
                    )

                return {
                    "type": "transcript_complete",
                    "text": response.text,
                    "final": True,
                    "timestamp": time.time(),
                }

        except Exception as e:
            error_msg = f"[HEADLESS] Error in audio processing: {str(e)}"
            logger.error(error_msg)
            return {"type": "error", "error": error_msg}

    def generate_speech(self, text: str, voice: str = "alloy") -> bytes:
        """
        Generate speech from text using OpenAI's text-to-speech API.

        Args:
            text: The text to convert to speech
            voice: The voice to use

        Returns:
            Audio data as bytes
        """
        try:
            logger.info(
                f"[HEADLESS] Generating speech for text: '{text[:50]}...' using voice: {voice}"
            )

            response = self.openai_client.audio.speech.create(
                model="tts-1", voice=voice, input=text
            )

            return response.content

        except Exception as e:
            error_msg = f"[HEADLESS] Error in speech generation: {str(e)}"
            logger.error(error_msg)
            return b""

    # Async versions of methods
    async def process_audio_stream(
        self, audio_chunks_generator, content_type: str = "audio/webm"
    ):
        """
        Process audio chunks (non-streaming implementation that collects all chunks first).

        Args:
            audio_chunks_generator: An async generator yielding audio chunks
            content_type: The content type of the audio

        Yields:
            Dict containing the transcript
        """
        # Collect all audio chunks
        all_audio = bytes()
        async for chunk in audio_chunks_generator:
            all_audio += chunk

        # Process the complete audio
        result = await self.process_audio(all_audio, content_type)
        yield result

    async def generate_speech(self, text: str, voice: str = "alloy"):
        """
        Async version of generate_speech.

        Args:
            text: The text to convert to speech
            voice: The voice to use

        Yields:
            Audio data as bytes
        """
        audio_data = self.generate_speech(text, voice)
        yield audio_data

    async def process_conversation(self, transcript: str, conversation_history=None):
        """
        Process a conversation message using OpenAI's streaming chat API.

        Args:
            transcript: The user's message transcript
            conversation_history: Previous conversation history

        Yields:
            Response tokens as they arrive
        """
        try:
            if conversation_history is None:
                conversation_history = []

            # Add system message if not present
            if not any(msg.get("role") == "system" for msg in conversation_history):
                conversation_history.insert(
                    0,
                    {
                        "role": "system",
                        "content": "You are an AI assistant for Red Bar Sushi restaurant. "
                        "Be helpful, concise, and friendly. Provide restaurant information "
                        "and take orders accurately. When asked about menu items or prices, "
                        "always check the actual menu data to provide accurate information. "
                        "Verify all menu items exist before providing information about them. "
                        "Use the menu data to accurately quote prices and menu options.",
                    },
                )

            # Add user message
            messages = conversation_history + [{"role": "user", "content": transcript}]

            # Create a streaming chat completion
            response = self.openai_client.chat.completions.create(
                model="gpt-4.1-mini", messages=messages, stream=True
            )

            # Keep track of the complete response
            complete_text = ""

            # Stream the response tokens
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    delta_content = chunk.choices[0].delta.content
                    complete_text += delta_content
                    yield {
                        "type": "message",
                        "text": delta_content,
                        "complete": False,
                        "timestamp": time.time(),
                    }

            # Yield the complete message
            yield {
                "type": "message_complete",
                "text": complete_text,
                "complete": True,
                "timestamp": time.time(),
            }

            # Log the complete response
            logger.info(f"[HEADLESS] Complete response: {complete_text[:100]}...")

        except Exception as e:
            error_msg = f"[HEADLESS] Error in conversation processing: {str(e)}"
            logger.error(error_msg)
            yield {"type": "error", "error": error_msg}


# Function to get the headless processor
def get_headless_audio_processor():
    """
    Get the headless audio processor instance.

    Returns:
        HeadlessAudioProcessor instance
    """
    return HeadlessAudioProcessor()
