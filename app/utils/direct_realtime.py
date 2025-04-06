# app/utils/direct_realtime.py
import logging
import json
import asyncio
import time
import traceback
from typing import Dict, Any, Optional, List, Generator, AsyncGenerator
import base64
import os
import uuid
import websockets

# Import OpenAI for standard API
import openai
from openai import OpenAI

# Get the OpenAI API key from agent_utils to keep it consistent
from app.utils.agent_utils import OPENAI_API_KEY, log_openai_request, log_openai_response

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create standard OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

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
    
    @classmethod
    def create(cls, api_key: str, session: Dict[str, Any] = None):
        """Class method to create a session - mimics the original API"""
        instance = cls(api_key=api_key)
        # Note: connect must be called separately in an async context
        return instance
    
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
            "Content-Type": "application/json"
        }
        
        try:
            self.websocket = await websockets.connect(
                self.WEBSOCKET_URL,
                extra_headers=headers
            )
            
            # Initialize session
            await self.send_event({
                "type": "session.update",
                "session": session_config
            })
            
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
    
    def events(self):
        """Generator to yield events - this is a sync wrapper, use get_events instead"""
        # This is a placeholder to match the original API
        # The actual implementation must be used with get_events
        return []
        
    async def get_events(self, timeout=30):
        """Async generator to yield events"""
        start_time = time.time()
        try:
            while True:
                if timeout and time.time() - start_time > timeout:
                    logger.warning(f"Timed out waiting for events after {timeout} seconds")
                    break
                    
                event = await self.get_next_event(timeout=1)
                if event:
                    yield event
        except Exception as e:
            logger.error(f"Error in events generator: {e}")
            raise

class DirectRealtimeAudioProcessor:
    """
    An implementation for audio processing using OpenAI's realtime API.
    Uses direct WebSocket communication without the client library.
    """
    
    def __init__(self):
        """Initialize the realtime audio processor."""
        self.openai_client = client
        self.api_key = OPENAI_API_KEY
    
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
            
            # Create and connect to a new session
            session = RealtimeSession(api_key=self.api_key)
            try:
                await session.connect(session_config={
                    "input_audio_format": {
                        "type": content_type
                    },
                    "output_audio_format": {
                        "type": "audio/mp3"
                    }
                })
                
                logger.info(f"Created realtime session: {session.session_id}")
            except Exception as session_error:
                logger.error(f"Error creating OpenAI Realtime session: {session_error}")
                logger.error(traceback.format_exc())
                
                # Fall back to standard processing if session creation fails
                logger.warning("Falling back to standard audio processing")
                all_audio = bytes()
                async for chunk in audio_chunks_generator:
                    all_audio += chunk
                
                # Process with standard API
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
                return
            
            # Collect audio chunks and send to session
            try:
                # Start collecting audio chunks
                async for chunk in audio_chunks_generator:
                    if isinstance(chunk, bytes):
                        # Convert to base64
                        base64_audio = base64.b64encode(chunk).decode('utf-8')
                        
                        # Append to the audio buffer
                        await session.send_event({
                            "type": "input_audio_buffer.append",
                            "audio": base64_audio
                        })
                
                # Signal that we're done sending audio
                await session.send_event({
                    "type": "input_audio_buffer.commit"
                })
                
                # Create a response to get transcription
                await session.send_event({
                    "type": "response.create",
                    "response": {
                        "modalities": ["text"]
                    }
                })
            except Exception as send_error:
                logger.error(f"Error sending data to session: {send_error}")
                logger.error(traceback.format_exc())
                
                # Close session and fall back
                try:
                    await session.close()
                except:
                    pass
                    
                yield {
                    "type": "error",
                    "error": f"Error sending data to session: {str(send_error)}"
                }
                return
            
            # Process events from the session with timeout for safety
            try:
                transcript = ""
                events_received = False
                
                # Use a timeout to prevent hanging if events don't come through
                start_time = time.time()
                timeout = 30  # seconds
                
                async for event in session.get_events(timeout=timeout):
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
                    await session.close()
                except:
                    pass
                    
            except Exception as event_error:
                logger.error(f"Error processing session events: {event_error}")
                logger.error(traceback.format_exc())
                
                # Try to close session
                try:
                    await session.close()
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
            
            # Create and connect to a new session
            session = RealtimeSession(api_key=self.api_key)
            try:
                await session.connect(session_config={
                    "output_audio_format": {
                        "type": "audio/mp3"
                    }
                })
            except Exception as session_error:
                logger.error(f"Error creating session for TTS: {session_error}")
                # Fall back to standard API
                logger.warning("Falling back to standard TTS API")
                response = self.openai_client.audio.speech.create(
                    model="tts-1",
                    voice=voice,
                    input=text
                )
                yield response.content
                return
            
            try:
                # Create a conversation item with the text
                await session.send_event({
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
                await session.send_event({
                    "type": "response.create",
                    "response": {
                        "modalities": ["text", "audio"],
                        "voice": voice
                    }
                })
                
                # Process events from the session
                audio_data = bytearray()
                async for event in session.get_events(timeout=30):
                    if event.get("type") == "response.audio.delta":
                        delta = event.get("delta", "")
                        if delta:
                            audio_chunk = base64.b64decode(delta)
                            audio_data.extend(audio_chunk)
                            yield bytes(audio_chunk)
                    elif event.get("type") == "response.audio.done":
                        if not audio_data:
                            # If no chunks were received, yield the complete audio
                            yield bytes(audio_data)
                        break
                
                # Close session
                await session.close()
            except Exception as e:
                logger.error(f"Error in TTS streaming: {e}")
                await session.close()
                # Fall back to standard API
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
            
            # Create and connect to a new session
            session = RealtimeSession(api_key=self.api_key)
            try:
                await session.connect()
            except Exception as session_error:
                logger.error(f"Error creating session for conversation: {session_error}")
                # Fall back to streaming standard API
                logger.warning("Falling back to standard conversation API with streaming")
                
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
                
                # Create a streaming chat completion
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    stream=True
                )
                
                # Stream the response tokens
                complete_text = ""
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
                return
            
            try:
                # Add system message if not present
                if not any(msg.get("role") == "system" for msg in conversation_history):
                    await session.send_event({
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
                        await session.send_event({
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
                await session.send_event({
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
                await session.send_event({
                    "type": "response.create",
                    "response": {
                        "modalities": ["text"]
                    }
                })
                
                # Process events from the session
                complete_text = ""
                async for event in session.get_events(timeout=30):
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
                        break
                
                # Close session
                await session.close()
            except Exception as e:
                logger.error(f"Error in conversation streaming: {e}")
                # Try to close session if it exists
                try:
                    await session.close()
                except:
                    pass
                
                # Fall back to standard API with streaming
                logger.warning("Falling back to standard conversation API with streaming after error")
                
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
                
                # Create a streaming chat completion
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    stream=True
                )
                
                # Stream the response tokens
                complete_text = ""
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
            
        except Exception as e:
            error_msg = f"Error in realtime conversation processing: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            yield {"type": "error", "error": error_msg}