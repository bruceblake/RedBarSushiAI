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
import os

# Explicitly disable any GUI/display dependencies and remove X11 requirement
os.environ['PYNPUT_HEADLESS'] = '1'
os.environ['NO_X11'] = '1'
os.environ['HEADLESS'] = '1'
os.environ['OPENAI_REALTIME_NO_DISPLAY'] = '1'

# Don't even try to use X11 display
if 'DISPLAY' in os.environ:
    del os.environ['DISPLAY']

# Import OpenAI Realtime client for WebSocket functionality
REALTIME_AVAILABLE = False

# First inspect what's actually in the package to help with diagnosis
try:
    import openai_realtime_client
    
    # Inspect the available attributes in the module
    module_contents = dir(openai_realtime_client)
    logging.info(f"openai_realtime_client contents: {module_contents}")
    
    # Check version and try to import the session
    version = getattr(openai_realtime_client, "__version__", "unknown")
    
    # Try to import the Session class - with specific handling for X11 errors
    try:
        # First try normal import
        try:
            from openai_realtime_client.client import Session
            REALTIME_AVAILABLE = True
            logging.info(f"Successfully imported Session from openai_realtime_client v{version}")
        except Exception as session_error:
            # Check if it's an X11/display-related error
            error_str = str(session_error).lower()
            if 'display' in error_str or 'x11' in error_str or 'x server' in error_str:
                logging.warning(f"X11/Display error importing Session: {session_error}")
                # Explicitly set to use standard client
                REALTIME_AVAILABLE = False
                logging.warning("X11/Display dependency detected, forcing fallback to standard API")
            else:
                # For other errors, re-raise
                raise session_error
    except (ImportError, AttributeError) as e:
        # Session doesn't seem to be exported directly
        # Let's use streaming in the standard client 
        REALTIME_AVAILABLE = False
        logging.warning(f"Could not import Session from openai_realtime_client: {e}")
        logging.warning(f"Using OpenAI client with streaming instead of realtime client")
    
except ImportError as import_error:
    logging.warning(f"OpenAI Realtime client import error: {import_error}")
    # Don't attempt auto-installation in a production environment
    REALTIME_AVAILABLE = False

# Explicit dependency check and package info
try:
    import pkg_resources
    required_packages = ['openai-realtime-client', 'python-socketio', 'eventlet', 'websockets']
    for package in required_packages:
        try:
            dist = pkg_resources.get_distribution(package)
            logging.info(f"Found {package} v{dist.version}")
        except pkg_resources.DistributionNotFound:
            logging.warning(f"Package {package} is not installed")
except Exception as e:
    logging.error(f"Error checking package versions: {e}")
        
if not REALTIME_AVAILABLE:
    logging.warning("OpenAI Realtime client not available, falling back to standard API")

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


# Realtime implementation using OpenAI's WebSocket API
class RealtimeAudioProcessor:
    """
    An implementation for audio processing using OpenAI's WebSocket API.
    Uses the openai-realtime-client which works in headless environments.
    """
    
    def __init__(self):
        """Initialize the realtime audio processor."""
        self.openai_client = client
    
    async def process_audio_stream(self, audio_chunks_generator, content_type: str = "audio/webm"):
        """
        Process streaming audio data using OpenAI's realtime API.
        
        Args:
            audio_chunks_generator: An async generator yielding audio chunks
            content_type: The content type of the audio
            
        Yields:
            Dict containing the transcript segments
        """
        try:
            logger.info(f"Processing audio stream with content type: {content_type}")
            
            # Safely create a Session - wrap in try/except
            try:
                session = Session.create(
                    api_key=OPENAI_API_KEY,
                    session={
                        "input_audio_format": {
                            "type": content_type
                        },
                        "output_audio_format": {
                            "type": "audio/mp3"
                        }
                    }
                )
                
                logger.info(f"Created realtime session: {session.id}")
            except Exception as session_error:
                logger.error(f"Error creating OpenAI Realtime session: {session_error}")
                logger.error(traceback.format_exc())
                
                # Fall back to non-realtime processing if session creation fails
                logger.warning("Falling back to non-streaming audio processing")
                all_audio = bytes()
                async for chunk in audio_chunks_generator:
                    all_audio += chunk
                
                # Process the complete audio with the standard API
                result = await self.process_audio(all_audio, content_type)
                yield result
                return
            
            # Collect audio chunks and send to session
            try:
                # Start collecting audio chunks
                async for chunk in audio_chunks_generator:
                    if isinstance(chunk, bytes):
                        # Convert to base64
                        base64_audio = base64.b64encode(chunk).decode('utf-8')
                        
                        # Append to the audio buffer
                        session.send_event({
                            "type": "input_audio_buffer.append",
                            "audio": base64_audio
                        })
                
                # Signal that we're done sending audio
                session.send_event({
                    "type": "input_audio_buffer.commit"
                })
                
                # Create a response to get transcription
                session.send_event({
                    "type": "response.create",
                    "response": {
                        "modalities": ["text"]
                    }
                })
            except Exception as send_error:
                logger.error(f"Error sending data to session: {send_error}")
                logger.error(traceback.format_exc())
                session.close()
                
                # Fall back to non-realtime processing
                logger.warning("Falling back to non-streaming audio processing due to send error")
                all_audio = bytes()
                # Reset the generator if possible
                try:
                    async for chunk in audio_chunks_generator:
                        all_audio += chunk
                except:
                    # If we can't restart the generator, just yield an error
                    yield {"type": "error", "error": "Failed to process audio stream"}
                    return
                
                # Process the complete audio with the standard API
                result = await self.process_audio(all_audio, content_type)
                yield result
                return
            
            # Process events from the session with timeout for safety
            try:
                transcript = ""
                events_received = False
                
                # Use a timeout to prevent hanging if events don't come through
                start_time = time.time()
                timeout = 30  # seconds
                
                for event in session.events():
                    events_received = True
                    
                    # Check for timeout
                    if time.time() - start_time > timeout:
                        logger.warning("Session event processing timed out")
                        break
                        
                    if event.get("type") == "response.audio_transcript.delta":
                        delta = event.get("delta", "")
                        transcript += delta
                        yield {
                            "type": "transcript",
                            "text": transcript,
                            "final": False,
                            "timestamp": time.time()
                        }
                    elif event.get("type") == "response.audio_transcript.done":
                        yield {
                            "type": "transcript_complete",
                            "text": transcript,
                            "final": True,
                            "timestamp": time.time()
                        }
                        break
                
                # If we didn't receive any events, yield empty result
                if not events_received:
                    logger.warning("No events received from session")
                    yield {
                        "type": "transcript_complete",
                        "text": "",
                        "final": True,
                        "timestamp": time.time()
                    }
                
                # Close session
                try:
                    session.close()
                except:
                    pass
                    
            except Exception as event_error:
                logger.error(f"Error processing session events: {event_error}")
                logger.error(traceback.format_exc())
                
                # Try to close session
                try:
                    session.close()
                except:
                    pass
                
                # Yield an error
                yield {"type": "error", "error": f"Error processing session events: {str(event_error)}"}
                
        except Exception as e:
            error_msg = f"Error in realtime audio processing: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            yield {"type": "error", "error": error_msg}
    
    async def generate_speech(self, text: str, voice: str = "alloy"):
        """
        Generate speech from text using OpenAI's realtime API.
        
        Args:
            text: The text to convert to speech
            voice: The voice to use
            
        Yields:
            Audio data chunks
        """
        try:
            logger.info(f"Generating speech for text: '{text[:50]}...' using voice: {voice}")
            
            # Create a new session
            session = Session.create(
                api_key=OPENAI_API_KEY,
                session={
                    "output_audio_format": {
                        "type": "audio/mp3"
                    }
                }
            )
            
            # Create a conversation item with the text
            session.send_event({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": text
                        }
                    ]
                }
            })
            
            # Create a response with TTS
            session.send_event({
                "type": "response.create",
                "response": {
                    "modalities": ["text", "audio"],
                    "voice": voice
                }
            })
            
            # Process events from the session
            audio_data = bytearray()
            for event in session.events():
                if event.get("type") == "response.audio.delta":
                    audio_chunk = base64.b64decode(event.get("delta", ""))
                    audio_data.extend(audio_chunk)
                    yield bytes(audio_chunk)
                elif event.get("type") == "response.audio.done":
                    if not audio_data:
                        # If no chunks were received, yield the complete audio
                        yield bytes(audio_data)
            
            # Close session
            session.close()
                
        except Exception as e:
            error_msg = f"Error in realtime speech generation: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            yield b''
            
    async def process_conversation(self, transcript: str, conversation_history=None):
        """
        Process a conversation message using OpenAI's realtime API.
        
        Args:
            transcript: The user's message transcript
            conversation_history: Previous conversation history
            
        Yields:
            Response tokens as they arrive
        """
        try:
            if conversation_history is None:
                conversation_history = []
            
            # Create a new session
            session = Session.create(
                api_key=OPENAI_API_KEY
            )
            
            # Add system message if not present
            if not any(msg.get("role") == "system" for msg in conversation_history):
                session.send_event({
                    "type": "conversation.item.create",
                    "item": {
                        "type": "message",
                        "role": "system",
                        "content": [
                            {
                                "type": "input_text",
                                "text": "You are an AI assistant for Red Bar Sushi restaurant. "
                                     "Be helpful, concise, and friendly. Provide restaurant information "
                                     "and take orders accurately."
                            }
                        ]
                    }
                })
            
            # Add previous conversation history
            for msg in conversation_history:
                if msg.get("role") != "system":  # Skip system message as we already added it
                    session.send_event({
                        "type": "conversation.item.create",
                        "item": {
                            "type": "message",
                            "role": msg.get("role"),
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": msg.get("content")
                                }
                            ]
                        }
                    })
            
            # Add the user's message
            session.send_event({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": transcript
                        }
                    ]
                }
            })
            
            # Create a response
            session.send_event({
                "type": "response.create",
                "response": {
                    "modalities": ["text"]
                }
            })
            
            # Process events from the session
            complete_text = ""
            for event in session.events():
                if event.get("type") == "response.text.delta":
                    delta = event.get("delta", "")
                    complete_text += delta
                    yield {
                        "type": "message",
                        "text": delta,
                        "complete": False,
                        "timestamp": time.time()
                    }
                elif event.get("type") == "response.text.done":
                    yield {
                        "type": "message_complete",
                        "text": complete_text,
                        "complete": True,
                        "timestamp": time.time()
                    }
            
            # Close session
            session.close()
            
        except Exception as e:
            error_msg = f"Error in realtime conversation processing: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            yield {"type": "error", "error": error_msg}


# Enhanced streaming implementation using OpenAI's standard API
class EnhancedAudioProcessor(BasicAudioProcessor):
    """
    An implementation for audio processing using OpenAI's standard API with streaming.
    This is a replacement for the realtime client which doesn't seem to have the expected Session class.
    """
    
    def __init__(self):
        """Initialize the enhanced audio processor."""
        super().__init__()
        self.openai_client = client
        
    # Enhanced methods are the same as BasicAudioProcessor - we're using inheritance
    # but we're optimizing the fallback process
    pass

# Create a class alias for backward compatibility - prioritize fully headless implementation
RealTimeAudioProcessor = BasicAudioProcessor  # Always use BasicAudioProcessor since realtime client isn't working


# Function to get the appropriate processor based on availability
def get_audio_processor():
    """
    Get the appropriate audio processor based on what's available.
    
    Returns:
        HeadlessAudioProcessor first (most reliable in containers),
        then EnhancedAudioProcessor or BasicAudioProcessor for standard API usage.
    """
    processor = None
    
    # First try - use the completely headless processor with no GUI dependencies
    # This is now our preferred approach because it has no X11 dependency
    try:
        # Import the headless processor
        from app.utils.audio_fallback import get_headless_audio_processor
        processor = get_headless_audio_processor()
        logger.info("Using fully headless audio processor with no X11 dependencies")
        return processor
    except Exception as headless_error:
        logger.error(f"Error initializing HeadlessAudioProcessor: {headless_error}")
        logger.error(traceback.format_exc())
    
    # Second try - use BasicAudioProcessor as fallback
    try:
        processor = BasicAudioProcessor()
        logger.info("Successfully initialized BasicAudioProcessor for audio processing")
        return processor
    except Exception as error:
        logger.error(f"Error initializing BasicAudioProcessor: {error}")
        logger.error(traceback.format_exc())
    
    # Absolute last resort - create a minimal processor that will at least handle basic operations
    logger.warning("Using minimal compatibility audio processor")
    try:
        # Create a new instance of MinimalAudioProcessor that works without any dependencies
        class MinimalAudioProcessor:
            def __init__(self):
                self.openai_client = client
            
            async def process_audio(self, audio_data, content_type="audio/webm"):
                # Try to use OpenAI's whisper API directly
                try:
                    with tempfile.NamedTemporaryFile(suffix=".webm" if "webm" in content_type else ".mp3") as temp_file:
                        temp_file.write(audio_data)
                        temp_file.flush()
                        with open(temp_file.name, "rb") as audio_file:
                            response = self.openai_client.audio.transcriptions.create(
                                model="whisper-1", file=audio_file, language="en")
                            return {"type": "transcript_complete", "text": response.text, "final": True}
                except:
                    return {"type": "transcript_complete", "text": "Audio processing unavailable", "final": True}
            
            async def process_audio_stream(self, audio_chunks_generator, content_type="audio/webm"):
                # Collect all audio and process at once
                all_audio = bytes()
                async for chunk in audio_chunks_generator:
                    all_audio += chunk
                result = await self.process_audio(all_audio, content_type)
                yield result
            
            async def generate_speech(self, text, voice="alloy"):
                # Simple direct TTS
                try:
                    response = self.openai_client.audio.speech.create(
                        model="tts-1", voice=voice, input=text)
                    yield response.content
                except:
                    yield b''
            
            async def process_conversation(self, transcript, conversation_history=None):
                # Simple direct chat completion
                try:
                    if conversation_history is None:
                        conversation_history = []
                    messages = conversation_history + [{"role": "user", "content": transcript}]
                    response = self.openai_client.chat.completions.create(
                        model="gpt-4o", messages=messages, stream=True)
                    complete_text = ""
                    for chunk in response:
                        if chunk.choices and chunk.choices[0].delta.content:
                            delta = chunk.choices[0].delta.content
                            complete_text += delta
                            yield {"type": "message", "text": delta, "complete": False}
                    yield {"type": "message_complete", "text": complete_text, "complete": True}
                except:
                    yield {"type": "message_complete", "text": f"Received: {transcript}", "complete": True}
        
        return MinimalAudioProcessor()
    except:
        # If even that fails, return a completely empty object
        return type('EmptyProcessor', (), {})()  # Empty object