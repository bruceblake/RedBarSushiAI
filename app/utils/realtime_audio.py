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

# Import real-time processing
try:
    # First try the exact import
    try:
        from openai_realtime_client import RealTimeManager
        from openai_realtime_client.events import MessageStreamEvent, MessageDeltaEvent, MessageEvent
        from openai_realtime_client.audio import AudioTranscript, AudioTranscriptSegment, AudioGenerator, AudioContent
        REALTIME_AVAILABLE = True
        logging.info("Successfully imported openai_realtime_client")
    except ImportError as e1:
        # If that fails, try pip installing it
        logging.warning(f"First import attempt failed: {e1}")
        import subprocess
        import sys
        
        # Try to install the package
        logging.info("Attempting to install openai-realtime-client")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "openai-realtime-client==0.1.0"])
        
        # Try importing again
        from openai_realtime_client import RealTimeManager
        from openai_realtime_client.events import MessageStreamEvent, MessageDeltaEvent, MessageEvent
        from openai_realtime_client.audio import AudioTranscript, AudioTranscriptSegment, AudioGenerator, AudioContent
        REALTIME_AVAILABLE = True
        logging.info("Successfully installed and imported openai_realtime_client")
except Exception as e:
    logging.warning(f"OpenAI real-time module not available. Real-time audio streaming will be disabled. Error: {str(e)}")
    REALTIME_AVAILABLE = False

# Get the OpenAI API key from agent_utils to keep it consistent
from app.utils.agent_utils import OPENAI_API_KEY, log_openai_request, log_openai_response

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

class RealTimeAudioProcessor:
    """
    Handles real-time audio processing using OpenAI's real-time APIs.
    This class manages audio streaming for both speech-to-text and text-to-speech.
    """
    
    def __init__(self):
        """Initialize the real-time audio processor."""
        if not REALTIME_AVAILABLE:
            logger.error("Real-time audio processing is not available. Install openai-real-time package.")
            raise ImportError("openai-real-time package is required for real-time audio processing")
        
        self.manager = RealTimeManager(api_key=OPENAI_API_KEY)
        self.openai_client = client
    
    async def process_audio_stream(self, audio_chunks_generator: AsyncGenerator[bytes, None], 
                               content_type: str = "audio/webm") -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process streaming audio to text using OpenAI's real-time speech-to-text API.
        
        Args:
            audio_chunks_generator: An async generator that yields audio chunks
            content_type: The content type of the audio chunks (e.g., 'audio/webm')
            
        Yields:
            Dict containing transcript segments as they arrive
        """
        try:
            logger.info(f"Starting real-time audio processing with content type: {content_type}")
            
            # Create audio content from the streaming source
            audio_content = AudioContent.from_streaming_source(audio_chunks_generator, content_type=content_type)
            
            # Start the transcription process
            async with self.manager.speech_to_text(
                audio=audio_content,
                model="whisper-1",
                options={"language": "en"}
            ) as transcription:
                # Process transcript segments as they arrive
                async for segment in transcription.segments():
                    result = {
                        "type": "transcript",
                        "text": segment.text,
                        "final": segment.is_final,
                        "timestamp": time.time()
                    }
                    logger.debug(f"Transcript segment: {result}")
                    yield result
                
                # Get the final transcript
                complete_transcript = await transcription.complete()
                final_result = {
                    "type": "transcript_complete",
                    "text": complete_transcript.text,
                    "final": True,
                    "timestamp": time.time()
                }
                logger.info(f"Completed transcription: {final_result['text'][:100]}...")
                yield final_result
                
        except Exception as e:
            error_msg = f"Error in audio stream processing: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            yield {"type": "error", "error": error_msg}
    
    async def generate_speech(self, text: str, voice: str = "alloy") -> AsyncGenerator[bytes, None]:
        """
        Generate streaming speech from text using OpenAI's text-to-speech API.
        
        Args:
            text: The text to convert to speech
            voice: The voice to use (alloy, echo, fable, onyx, nova, shimmer)
            
        Yields:
            Audio chunks as bytes
        """
        try:
            logger.info(f"Generating speech for text: '{text[:50]}...' using voice: {voice}")
            
            # Create a generator for text-to-speech
            audio_generator = AudioGenerator.from_text(text=text, model="tts-1", voice=voice)
            
            # Stream the audio chunks
            async with self.manager.text_to_speech(audio_generator) as speech:
                async for chunk in speech.stream():
                    yield chunk
                    
        except Exception as e:
            error_msg = f"Error in speech generation: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            # We can't yield an error message here since the client expects audio data
            # The connection will just close with an error
            return
    
    async def process_conversation(self, 
                               transcript: str, 
                               conversation_history: Optional[List[Dict[str, str]]] = None) -> AsyncGenerator[Dict[str, Any], None]:
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


# Simpler fallback implementation when real-time package is not available
class BasicAudioProcessor:
    """
    A fallback implementation for audio processing without real-time capabilities.
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


# Function to get the appropriate processor based on availability
def get_audio_processor():
    """
    Get the appropriate audio processor based on what's available.
    
    Returns:
        RealTimeAudioProcessor if available, otherwise BasicAudioProcessor
    """
    if REALTIME_AVAILABLE:
        try:
            return RealTimeAudioProcessor()
        except ImportError:
            logger.warning("Failed to initialize RealTimeAudioProcessor, falling back to BasicAudioProcessor")
            return BasicAudioProcessor()
    else:
        return BasicAudioProcessor()