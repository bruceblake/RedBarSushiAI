# app/utils/realtime_audio.py
import logging
import json
import asyncio
import time
import traceback
from typing import Dict, Any, Optional, List, Generator, AsyncGenerator
import base64

# Import OpenAI
import openai
from openai import OpenAI

# Mark as headless explicitly - don't try to import problematic packages
REALTIME_AVAILABLE = False
OPENAI_STREAMING_AVAILABLE = True
logging.info("Using direct OpenAI API for audio streaming without pynput (headless mode)")

# Get the OpenAI API key from agent_utils to keep it consistent
from app.utils.agent_utils import OPENAI_API_KEY, log_openai_request, log_openai_response

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Modified implementation for headless environments
class BasicAudioProcessor:
    """
    A fallback implementation for audio processing in headless environments.
    Uses direct OpenAI API calls which work in all environments.
    """
    
    def __init__(self):
        """Initialize the basic audio processor."""
        self.openai_client = client
    
    async def process_audio(self, audio_data: bytes, content_type: str = "audio/webm") -> Dict[str, Any]:
        """
        Process audio data to text using OpenAI's speech-to-text API.
        
        Args:
            audio_data: The complete audio data
            content_type: The content type of the audio
            
        Returns:
            Dict containing the transcript
        """
        try:
            logger.info(f"Processing audio with content type: {content_type}")
            
            # Create a temporary file to store the audio
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".webm" if "webm" in content_type else ".mp3") as temp_file:
                temp_file.write(audio_data)
                temp_file.flush()
                
                # Process with OpenAI
                with open(temp_file.name, "rb") as audio_file:
                    response = self.openai_client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="en"
                    )
                
                return {
                    "type": "transcript_complete",
                    "text": response.text,
                    "final": True,
                    "timestamp": time.time()
                }
                
        except Exception as e:
            error_msg = f"Error in audio processing: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
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
            logger.info(f"Generating speech for text: '{text[:50]}...' using voice: {voice}")
            
            response = self.openai_client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text
            )
            
            return response.content
            
        except Exception as e:
            error_msg = f"Error in speech generation: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return b''
    
    # Add async versions of methods to match the RealTimeAudioProcessor interface
    async def process_audio_stream(self, audio_chunks_generator, content_type: str = "audio/webm"):
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
                conversation_history.insert(0, {
                    "role": "system",
                    "content": "You are an AI assistant for Red Bar Sushi restaurant. "
                              "Be helpful, concise, and friendly. Provide restaurant information "
                              "and take orders accurately."
                })
            
            # Add user message
            messages = conversation_history + [{"role": "user", "content": transcript}]
            
            # Log the request
            log_openai_request("gpt-4o", messages, "process_conversation")
            
            # Create a streaming chat completion
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                stream=True
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
                        "timestamp": time.time()
                    }
            
            # Yield the complete message
            yield {
                "type": "message_complete",
                "text": complete_text,
                "complete": True,
                "timestamp": time.time()
            }
            
            # Log the complete response
            logger.info(f"Complete response: {complete_text[:100]}...")
            
        except Exception as e:
            error_msg = f"Error in conversation processing: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            yield {"type": "error", "error": error_msg}


# Create an alias for BasicAudioProcessor so code that references RealTimeAudioProcessor still works
RealTimeAudioProcessor = BasicAudioProcessor


# Function to get the appropriate processor based on availability
def get_audio_processor():
    """
    Get the appropriate audio processor based on what's available.
    
    Returns:
        BasicAudioProcessor for Docker/headless environments
    """
    processor = None
    
    # First try/except block
    try:
        # Set up a simple basic processor
        processor = BasicAudioProcessor()
        logger.info("Successfully initialized BasicAudioProcessor for headless environment")
        return processor
    except Exception as first_error:
        logger.error(f"First attempt to initialize audio processor failed: {first_error}")
        logger.error(traceback.format_exc())
    
    # Second block with different approach if first fails
    try:
        # Use maximum compatibility approach - don't import anything special
        logger.warning("Trying fallback audio processor approach")
        processor = BasicAudioProcessor()
        return processor
    except Exception as second_error:
        logger.error(f"Second attempt to initialize audio processor failed: {second_error}")
        logger.error(traceback.format_exc())
        
    # If we get here, create a minimal processor
    logger.warning("Using minimal compatibility audio processor")
    return BasicAudioProcessor()