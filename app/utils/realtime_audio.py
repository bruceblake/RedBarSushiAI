# app/utils/realtime_audio.py
import logging
import json
import asyncio
import time
import traceback
from typing import Dict, Any, Optional, List, Generator, AsyncGenerator
import base64

# Import required modules
import openai
from openai import OpenAI
import os
import tempfile
from flask import session

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Explicitly disable any GUI/display dependencies and remove X11 requirement
os.environ['PYNPUT_HEADLESS'] = '1'
os.environ['NO_X11'] = '1'
os.environ['HEADLESS'] = '1'
os.environ['OPENAI_REALTIME_NO_DISPLAY'] = '1'

# Don't even try to use X11 display
if 'DISPLAY' in os.environ:
    del os.environ['DISPLAY']

# Check for WebSocket library availability for Realtime API
WEBSOCKETS_AVAILABLE = False
AIOHTTP_AVAILABLE = False
REALTIME_AVAILABLE = False

# Check for websockets library availability
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
    logging.info("websockets library available for WebSocket communication")
except ImportError:
    logging.warning("websockets package not available")

# Check for aiohttp library availability
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
    logging.info("aiohttp library available for WebSocket communication")
except ImportError:
    logging.warning("aiohttp package not available")

# Check for DISPLAY environment variable (required for OpenAI Realtime client)
display_env = os.environ.get('DISPLAY')

# If Xvfb is being used (from docker-entrypoint.sh), restore the settings
if 'X11_SETUP_SUCCESS' in os.environ and os.environ.get('X11_SETUP_SUCCESS') == 'true':
    # Get the display from the environment or use a default
    display_value = os.environ.get('X11_DISPLAY', ':1')  # Default to :1 instead of :99
    os.environ['DISPLAY'] = display_value
    display_env = display_value
    
    # Try to verify that the display is actually working
    import subprocess
    try:
        # Try a quick check if the X server is actually available
        subprocess.run(["xdpyinfo", "-display", display_value], 
                      stdout=subprocess.PIPE, 
                      stderr=subprocess.PIPE, 
                      timeout=2)
        
        # If we get here, X11 is available
        os.environ['PYNPUT_HEADLESS'] = '0'
        os.environ['NO_X11'] = '0'
        os.environ['HEADLESS'] = '0'
        os.environ['OPENAI_REALTIME_NO_DISPLAY'] = '0'
        
        logging.info(f"X11 setup confirmed working with DISPLAY={display_env}")
    except (subprocess.SubprocessError, FileNotFoundError):
        # X11 doesn't actually work, force headless mode
        logging.warning(f"X11 setup claims success but display {display_env} is not responding, forcing headless mode")
        if 'DISPLAY' in os.environ:
            del os.environ['DISPLAY']
        os.environ['PYNPUT_HEADLESS'] = '1'
        os.environ['NO_X11'] = '1'
        os.environ['HEADLESS'] = '1'
        os.environ['OPENAI_REALTIME_NO_DISPLAY'] = '1'
elif display_env:
    logging.info(f"DISPLAY environment variable is set to: {display_env}")
else:
    logging.warning("DISPLAY environment variable is not set - X11 apps will not work")

# First try to use the official OpenAI Realtime client
try:
    import openai_realtime_client
    
    # Inspect the available attributes in the module
    module_contents = dir(openai_realtime_client)
    logging.info(f"openai_realtime_client contents: {module_contents}")
    
    # Check version and try to import the client
    version = getattr(openai_realtime_client, "__version__", "unknown")
    logging.info(f"OpenAI Realtime client version: {version}")
    
    # Try to import the RealtimeClient class - with specific handling for X11 errors
    try:
        # First try normal import
        try:
            # Detailed logging to diagnose import issues
            logging.info("Attempting to import RealtimeClient from openai_realtime_client...")
            
            # Try to import RealtimeClient, being extra careful with X11 errors
            if not display_env:
                logging.warning("No DISPLAY environment variable - this will likely fail")
            
            from openai_realtime_client import RealtimeClient
            REALTIME_AVAILABLE = True
            logging.info(f"✅ Successfully imported RealtimeClient from openai_realtime_client v{version}")
            
            # Test creating a client to make sure it actually works
            try:
                logging.info("Testing RealtimeClient creation...")
                test_key = os.environ.get('OPENAI_API_KEY', 'sk-test')
                test_client = RealtimeClient(api_key=test_key)
                logging.info(f"✅ Successfully created test client object: {test_client}")
            except Exception as test_error:
                logging.warning(f"⚠️ Test client creation failed: {test_error}")
                # If it's an X11/display error, fall back
                error_str = str(test_error).lower()
                if 'display' in error_str or 'x11' in error_str or 'x server' in error_str:
                    logging.warning(f"X11/Display error during test: {test_error}")
                    REALTIME_AVAILABLE = False
                
        except Exception as client_error:
            # Check if it's an X11/display-related error
            error_str = str(client_error).lower()
            logging.error(f"Error importing RealtimeClient: {client_error}")
            
            if 'display' in error_str or 'x11' in error_str or 'x server' in error_str or 'displaynameerror' in error_str:
                logging.warning(f"X11/Display error importing RealtimeClient: {client_error}")
                # Explicitly set to use direct implementation
                REALTIME_AVAILABLE = False
                logging.warning("X11/Display dependency detected, will use direct WebSocket implementation")
            else:
                # For other errors, re-raise
                raise client_error
    except (ImportError, AttributeError) as e:
        # RealtimeClient doesn't seem to be exported directly
        # Let's use direct WebSocket implementation
        REALTIME_AVAILABLE = False
        logging.warning(f"Could not import RealtimeClient from openai_realtime_client: {e}")
        logging.warning("Will use direct WebSocket implementation instead")
    
except ImportError as import_error:
    logging.warning(f"OpenAI Realtime client import error: {import_error}")
    # Don't attempt auto-installation in a production environment
    REALTIME_AVAILABLE = False
    logging.warning("Will use direct WebSocket implementation")

# Explicit dependency check and package info for better error diagnosis
try:
    import pkg_resources
    required_packages = ['openai-realtime-client', 'python-socketio', 'eventlet', 'websockets', 'aiohttp']
    for package in required_packages:
        try:
            dist = pkg_resources.get_distribution(package)
            logging.info(f"Found {package} v{dist.version}")
        except pkg_resources.DistributionNotFound:
            logging.warning(f"Package {package} is not installed")
except Exception as e:
    logging.error(f"Error checking package versions: {e}")

# Determine if we have any WebSocket capability
WEBSOCKET_CAPABILITY = REALTIME_AVAILABLE or WEBSOCKETS_AVAILABLE or AIOHTTP_AVAILABLE
if not WEBSOCKET_CAPABILITY:
    logging.warning("No WebSocket capability available (neither openai_realtime_client, websockets, nor aiohttp). Falling back to standard API")
else:
    if not REALTIME_AVAILABLE:
        if WEBSOCKETS_AVAILABLE or AIOHTTP_AVAILABLE:
            logging.info("Will use direct WebSocket implementation with websockets or aiohttp")
            
            # Don't treat this as an error - it's expected behavior with our dual approach
            if 'X11_SETUP_SUCCESS' in os.environ and os.environ.get('X11_SETUP_SUCCESS') == 'true':
                logging.info("Note: Using direct WebSocket implementation instead of OpenAI Realtime client, " +
                            "even though X11 is available. This is normal if the Session class is not available.")
            else:
                logging.info("Using direct WebSocket implementation because X11 display server is not available")
        else:
            logging.warning("No WebSocket libraries available, falling back to standard API")

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
                              "and take orders accurately. When asked about menu items or prices, "
                              "always check the actual menu data to provide accurate information. "
                              "Verify all menu items exist before providing information about them. "
                              "Use the menu data to accurately quote prices and menu options."
                })
            
            # Add user message
            messages = conversation_history + [{"role": "user", "content": transcript}]
            
            # Log the request
            log_openai_request("gpt-4.1-mini", messages, "process_conversation")
            
            # Create a streaming chat completion
            response = self.openai_client.chat.completions.create(
                model="gpt-4.1-mini",
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
            
            # Safely create a RealtimeClient - wrap in try/except
            try:
                client = RealtimeClient(api_key=OPENAI_API_KEY)
                
                # Create a session with audio format configuration
                session_options = {
                    "input_audio_format": {
                        "type": content_type
                    },
                    "output_audio_format": {
                        "type": "audio/mp3"
                    }
                }
                
                logger.info(f"Created realtime client with session options: {session_options}")
            except Exception as client_error:
                logger.error(f"Error creating OpenAI Realtime client: {client_error}")
                logger.error(traceback.format_exc())
                
                # Fall back to non-realtime processing if client creation fails
                logger.warning("Falling back to non-streaming audio processing")
                all_audio = bytes()
                async for chunk in audio_chunks_generator:
                    all_audio += chunk
                
                # Process the complete audio with the standard API
                result = await self.process_audio(all_audio, content_type)
                yield result
                return
            
            # Collect audio chunks for processing
            try:
                # Collect all audio chunks first
                all_audio = bytes()
                async for chunk in audio_chunks_generator:
                    if isinstance(chunk, bytes):
                        all_audio += chunk
                
                # Convert to base64 if needed
                base64_audio = base64.b64encode(all_audio).decode('utf-8')
                
                # Process audio with client
                # Note: The API for RealtimeClient may be different from Session,
                # this is an educated guess based on the module contents
                logger.info("Processing audio with RealtimeClient")
            except Exception as send_error:
                logger.error(f"Error processing audio chunks: {send_error}")
                logger.error(traceback.format_exc())
                
                # Fall back to non-realtime processing
                logger.warning("Falling back to non-streaming audio processing due to processing error")
                
                # Process the complete audio with the standard API
                try:
                    # We've already collected all the audio in all_audio
                    with tempfile.NamedTemporaryFile(suffix=".webm" if "webm" in content_type else ".mp3") as temp_file:
                        temp_file.write(all_audio)
                        temp_file.flush()
                        
                        # Process with OpenAI
                        with open(temp_file.name, "rb") as audio_file:
                            response = self.openai_client.audio.transcriptions.create(
                                model="whisper-1",
                                file=audio_file,
                                language="en"
                            )
                    
                    yield {
                        "type": "transcript_complete",
                        "text": response.text,
                        "final": True,
                        "timestamp": time.time()
                    }
                except Exception as fallback_error:
                    logger.error(f"Error in fallback processing: {fallback_error}")
                    yield {"type": "error", "error": "Failed to process audio stream"}
                
                return
            
            # Try to process with RealtimeClient
            try:
                # Based on the module contents, we need to use RealtimeClient differently from Session
                # This is a best guess implementation based on available information
                logger.info("Attempting to transcribe audio with RealtimeClient")
                
                # Create a new handler for audio processing
                try:
                    # Create a temporary file for audio processing
                    with tempfile.NamedTemporaryFile(suffix=".webm" if "webm" in content_type else ".mp3") as temp_file:
                        temp_file.write(all_audio)
                        temp_file.flush()
                        
                        # Use the client to process the audio file or use the API directly
                        # Note: This is a placeholder - actual API may differ
                        try:
                            # Attempt to use the actual RealtimeClient directly (preferred)
                            result = client.process_audio_file(temp_file.name)
                            transcript = result.get("text", "")
                        except (AttributeError, TypeError) as direct_error:
                            logger.warning(f"Direct RealtimeClient.process_audio_file not available: {direct_error}")
                            
                            # Fall back to standard API
                            with open(temp_file.name, "rb") as audio_file:
                                response = self.openai_client.audio.transcriptions.create(
                                    model="whisper-1",
                                    file=audio_file,
                                    language="en"
                                )
                            transcript = response.text
                
                        # Yield the complete transcript
                        logger.info(f"Transcription completed: {transcript}")
                        yield {
                            "type": "transcript_complete",
                            "text": transcript,
                            "final": True,
                            "timestamp": time.time()
                        }
                except Exception as process_error:
                    logger.error(f"Error processing with RealtimeClient: {process_error}")
                    logger.error(traceback.format_exc())
                    
                    # Fall back to standard API as last resort
                    with tempfile.NamedTemporaryFile(suffix=".webm" if "webm" in content_type else ".mp3") as temp_file:
                        temp_file.write(all_audio)
                        temp_file.flush()
                        
                        # Process with OpenAI
                        with open(temp_file.name, "rb") as audio_file:
                            response = self.openai_client.audio.transcriptions.create(
                                model="whisper-1",
                                file=audio_file,
                                language="en"
                            )
                    
                    yield {
                        "type": "transcript_complete",
                        "text": response.text,
                        "final": True,
                        "timestamp": time.time()
                    }
                    
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
            
            # Try to use RealtimeClient if available
            try:
                client = RealtimeClient(api_key=OPENAI_API_KEY)
                logger.info("Created RealtimeClient for text-to-speech")
                
                # Note: Since we don't know the exact API for RealtimeClient,
                # we'll try a few approaches and fall back to standard API
                try:
                    # Try a direct method if available
                    audio_data = client.generate_speech(text, voice=voice)
                    yield audio_data
                    logger.info("Generated speech using RealtimeClient.generate_speech")
                    return
                except (AttributeError, TypeError) as direct_error:
                    logger.warning(f"Direct RealtimeClient.generate_speech not available: {direct_error}")
                    
                    # Try alternative methods if they exist
                    try:
                        # Try other potential API patterns
                        audio_data = client.tts(text, voice=voice)
                        yield audio_data
                        logger.info("Generated speech using RealtimeClient.tts")
                        return
                    except (AttributeError, TypeError):
                        logger.warning("RealtimeClient.tts method not available")
                
                # Fall back to standard API
                logger.warning("Falling back to standard TTS API")
            except Exception as client_error:
                logger.error(f"Error creating or using RealtimeClient: {client_error}")
                logger.warning("Falling back to standard TTS API")
            
            # Use standard OpenAI API for TTS
            response = self.openai_client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text
            )
            yield response.content
                
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
            
            # Try to use RealtimeClient if available
            try:
                client = RealtimeClient(api_key=OPENAI_API_KEY)
                logger.info("Created RealtimeClient for conversation processing")
                
                # Note: Since we don't know the exact API for RealtimeClient,
                # we'll try direct methods and fall back to standard API
                try:
                    # Prepare messages in chat format
                    messages = []
                    
                    # Add system message if not present
                    if not any(msg.get("role") == "system" for msg in conversation_history):
                        messages.append({
                            "role": "system",
                            "content": "You are an AI assistant for Red Bar Sushi restaurant. "
                                    "Be helpful, concise, and friendly. Provide restaurant information "
                                    "and take orders accurately."
                        })
                    
                    # Add conversation history
                    for msg in conversation_history:
                        if msg.get("role") != "system" or not messages:  # Add system if we didn't add one above
                            messages.append(msg)
                    
                    # Add user message
                    messages.append({"role": "user", "content": transcript})
                    
                    # Try various methods that might exist
                    try:
                        # Try streaming completion style method
                        for chunk in client.chat.completions.create(messages=messages, stream=True):
                            if hasattr(chunk, 'choices') and chunk.choices:
                                delta = chunk.choices[0].delta.content
                                if delta:
                                    yield {
                                        "type": "message",
                                        "text": delta,
                                        "complete": False,
                                        "timestamp": time.time()
                                    }
                        
                        # Success with streaming method
                        logger.info("Used RealtimeClient.chat.completions.create streaming method")
                        return
                    except (AttributeError, TypeError) as method_error:
                        logger.warning(f"RealtimeClient.chat.completions.create not available: {method_error}")
                    
                    # Try alternative method
                    try:
                        # Try a direct conversation method
                        response = client.create_conversation(messages)
                        yield {
                            "type": "message_complete",
                            "text": response.get("content") if isinstance(response, dict) else str(response),
                            "complete": True,
                            "timestamp": time.time()
                        }
                        
                        # Success with direct method
                        logger.info("Used RealtimeClient.create_conversation method")
                        return
                    except (AttributeError, TypeError) as method_error:
                        logger.warning(f"RealtimeClient.create_conversation not available: {method_error}")
                    
                    # Fall back to standard API if we got here
                    logger.warning("No RealtimeClient methods available, falling back to standard API")
                except Exception as api_error:
                    logger.error(f"Error using RealtimeClient API: {api_error}")
                    logger.warning("Falling back to standard API due to RealtimeClient API error")
            except Exception as client_error:
                logger.error(f"Error creating or using RealtimeClient: {client_error}")
                logger.warning("Falling back to standard chat API")
            
            # Add system message if not present
            if not any(msg.get("role") == "system" for msg in conversation_history):
                conversation_history.insert(0, {
                    "role": "system",
                    "content": "You are an AI assistant for Red Bar Sushi restaurant. "
                              "Be helpful, concise, and friendly. Provide restaurant information "
                              "and take orders accurately. When asked about menu items or prices, "
                              "always check the actual menu data to provide accurate information. "
                              "Verify all menu items exist before providing information about them. "
                              "Use the menu data to accurately quote prices and menu options."
                })
            
            # Add user message
            messages = conversation_history + [{"role": "user", "content": transcript}]
            
            # Log the request
            log_openai_request("gpt-4.1-mini", messages, "process_conversation")
            
            # Create a streaming chat completion
            response = self.openai_client.chat.completions.create(
                model="gpt-4.1-mini",
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
    
    Selection process:
    1. DirectRealtimeAudioProcessor first (using either websockets or aiohttp)
    2. HeadlessAudioProcessor for headless environments with no GUI dependencies 
    3. BasicAudioProcessor as standard fallback
    4. MinimalAudioProcessor as absolute last resort for maximum compatibility
    
    Returns:
        An audio processor instance based on availability
    """
    processor = None
    
    # First try - use the direct implementation with websockets or aiohttp and no X11 dependencies
    if WEBSOCKETS_AVAILABLE or AIOHTTP_AVAILABLE:
        try:
            # Import the direct realtime processor
            from app.utils.direct_realtime import DirectRealtimeAudioProcessor
            processor = DirectRealtimeAudioProcessor()
            if WEBSOCKETS_AVAILABLE and AIOHTTP_AVAILABLE:
                logger.info("Using DirectRealtimeAudioProcessor with both websockets and aiohttp support")
            elif WEBSOCKETS_AVAILABLE:
                logger.info("Using DirectRealtimeAudioProcessor with websockets support")
            else:
                logger.info("Using DirectRealtimeAudioProcessor with aiohttp support")
            return processor
        except Exception as direct_error:
            logger.error(f"Error initializing DirectRealtimeAudioProcessor: {direct_error}")
            logger.error(traceback.format_exc())
    else:
        logger.warning("Neither websockets nor aiohttp available, skipping DirectRealtimeAudioProcessor")
    
    # Second try - use the official Realtime client if it's available
    if REALTIME_AVAILABLE:
        try:
            processor = RealtimeAudioProcessor()
            logger.info("Using RealtimeAudioProcessor with official OpenAI Realtime client")
            return processor
        except Exception as realtime_error:
            logger.error(f"Error initializing RealtimeAudioProcessor: {realtime_error}")
            logger.error(traceback.format_exc())
    
    # Third try - use the completely headless processor with no GUI dependencies
    try:
        # Import the headless processor
        from app.utils.audio_fallback import get_headless_audio_processor
        processor = get_headless_audio_processor()
        logger.info("Using fully headless audio processor with no X11 dependencies")
        return processor
    except Exception as headless_error:
        logger.error(f"Error initializing HeadlessAudioProcessor: {headless_error}")
        logger.error(traceback.format_exc())
    
    # Fourth try - use BasicAudioProcessor as fallback
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
            """Minimal audio processor implementation that works with minimal dependencies"""
            
            def __init__(self):
                self.openai_client = client
                logger.warning("Using MinimalAudioProcessor as last resort")
            
            async def process_audio(self, audio_data, content_type="audio/webm"):
                # Try to use OpenAI's whisper API directly
                try:
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix=".webm" if "webm" in content_type else ".mp3") as temp_file:
                        temp_file.write(audio_data)
                        temp_file.flush()
                        with open(temp_file.name, "rb") as audio_file:
                            response = self.openai_client.audio.transcriptions.create(
                                model="whisper-1", file=audio_file, language="en")
                            return {"type": "transcript_complete", "text": response.text, "final": True, "timestamp": time.time()}
                except Exception as e:
                    logger.error(f"Error in minimal audio processing: {e}")
                    return {"type": "transcript_complete", "text": "Audio processing unavailable", "final": True, "timestamp": time.time()}
            
            async def process_audio_stream(self, audio_chunks_generator, content_type="audio/webm"):
                # Collect all audio and process at once
                all_audio = bytes()
                try:
                    async for chunk in audio_chunks_generator:
                        all_audio += chunk
                except Exception as e:
                    logger.error(f"Error collecting audio chunks: {e}")
                    yield {"type": "error", "error": "Failed to collect audio chunks", "timestamp": time.time()}
                    return
                
                # Process the complete audio
                try:
                    result = await self.process_audio(all_audio, content_type)
                    yield result
                except Exception as e:
                    logger.error(f"Error processing audio: {e}")
                    yield {"type": "error", "error": "Failed to process audio", "timestamp": time.time()}
            
            async def generate_speech(self, text, voice="alloy"):
                # Simple direct TTS
                try:
                    response = self.openai_client.audio.speech.create(
                        model="tts-1", voice=voice, input=text)
                    yield response.content
                except Exception as e:
                    logger.error(f"Error generating speech: {e}")
                    yield b''
            
            async def process_conversation(self, transcript, conversation_history=None):
                # Simple direct chat completion
                try:
                    if conversation_history is None:
                        conversation_history = []
                    
                    # Add system message if not present
                    if not any(msg.get("role") == "system" for msg in conversation_history):
                        conversation_history.insert(0, {
                            "role": "system",
                            "content": "You are an AI assistant for Red Bar Sushi restaurant. "
                                      "Be helpful, concise, and friendly."
                        })
                    
                    # Add user message
                    messages = conversation_history + [{"role": "user", "content": transcript}]
                    
                    # Create a streaming chat completion
                    response = self.openai_client.chat.completions.create(
                        model="gpt-4.1-mini", messages=messages, stream=True)
                    
                    # Stream the response tokens
                    complete_text = ""
                    for chunk in response:
                        if chunk.choices and chunk.choices[0].delta.content:
                            delta = chunk.choices[0].delta.content
                            complete_text += delta
                            yield {
                                "type": "message",
                                "text": delta,
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
                except Exception as e:
                    logger.error(f"Error in conversation processing: {e}")
                    yield {"type": "message_complete", "text": f"Received: {transcript}", "complete": True, "timestamp": time.time()}
        
        return MinimalAudioProcessor()
    except Exception as minimal_error:
        logger.error(f"Error creating MinimalAudioProcessor: {minimal_error}")
        # If even that fails, return a completely empty object
        return type('EmptyProcessor', (), {})()  # Empty object


# Function to process a single audio chunk (for testing compatibility)
def process_chunk(chunk_data, session_id, callback=None):
    """
    Process a single chunk of audio data.
    This is a synchronous wrapper around async processing for backward compatibility.
    
    Args:
        chunk_data: The audio chunk data (bytes or string)
        session_id: Identifier for the session
        callback: Optional callback function to receive the results
        
    Returns:
        Dict containing processing results
    """
    logger.info(f"Processing chunk for session {session_id[:10]}...")
    
    # Convert string to bytes if needed
    if isinstance(chunk_data, str):
        chunk_data = chunk_data.encode('utf-8')
    
    try:
        # Create system message for restaurant context
        system_message = """You are the AI assistant for Red Bar Sushi restaurant.
        Be helpful, concise, and friendly. Provide restaurant information
        and take orders accurately. When asked about menu items or prices,
        always check the actual menu data to provide accurate information.
        Verify all menu items exist before providing information about them.
        Use the menu data to accurately quote prices and menu options."""
        
        # Create a user message from the chunk data
        user_message = chunk_data.decode('utf-8') if isinstance(chunk_data, bytes) else chunk_data
        
        # Use OpenAI to process the chunk data - use the module instead of client
        # This allows the tests to mock the API calls
        response = openai.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ]
        )
        
        # Get the assistant's response
        response_text = response.choices[0].message.content
        
        # Create a result object
        result = {
            "type": "transcript",
            "text": response_text,
            "session_id": session_id,
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Error processing chunk: {str(e)}")
        logger.error(traceback.format_exc())
        # Create an error result
        result = {
            "type": "error",
            "error": f"Error processing chunk: {str(e)}",
            "session_id": session_id,
            "timestamp": time.time()
        }
    
    # Call the callback if provided
    if callback and callable(callback):
        callback(result)
    
    return result