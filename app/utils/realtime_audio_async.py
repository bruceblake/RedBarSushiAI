"""
Async OpenAI Realtime Client for RedBarSushiAI.

This module provides an async client for interacting with OpenAI's Realtime API,
designed for real-time voice interactions in FastAPI applications.
"""

import os
import json
import logging
import asyncio
import time
import uuid
import base64
import traceback
from typing import Dict, Any, Optional, List, AsyncGenerator, Callable, Union
from dataclasses import dataclass

import websockets
from websockets.exceptions import ConnectionClosed, ConnectionClosedError

from app.config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Ensure the logs directory exists
log_dir = os.path.join(os.getcwd(), 'logs')
os.makedirs(log_dir, exist_ok=True)

# Add a file handler for this module
file_handler = logging.FileHandler(os.path.join(log_dir, 'realtime_audio_async.log'))
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.info("======= ASYNC REALTIME AUDIO CLIENT LOGGING INITIALIZED =======")

@dataclass
class RealtimeConfig:
    """Configuration for the OpenAI Realtime API."""
    
    model: str = "gpt-4o-realtime-preview-2024-10-01"
    instructions: Optional[str] = None
    voice: str = "shimmer"
    sample_rate_hz: int = 8000
    input_audio_format: str = "mulaw"
    output_audio_format: str = "mulaw"
    vad_enabled: bool = True
    vad_silence_threshold_ms: int = 1000
    vad_speech_threshold_ms: int = 8000
    max_tokens: Optional[int] = None


class AudioUtils:
    """Utility functions for audio processing."""
    
    @staticmethod
    def ulaw_to_pcm(ulaw_data: bytes) -> bytes:
        """
        Convert μ-law encoded audio data to PCM format.
        
        Args:
            ulaw_data: μ-law encoded audio data (8kHz)
            
        Returns:
            PCM format audio data (16kHz)
        """
        import numpy as np
        from scipy import signal
        
        # Convert to numpy array
        ulaw_array = np.frombuffer(ulaw_data, dtype=np.uint8)
        
        # μ-law decoding
        sign = np.ones_like(ulaw_array)
        sign[ulaw_array & 0x80 != 0] = -1
        exponent = ((ulaw_array & 0x70) >> 4)
        mantissa = ulaw_array & 0x0f
        sample = sign * (((mantissa + 16.5) * (2 ** exponent)) - 16.5)
        pcm_data = (sample / 128.0 * 32768).astype(np.int16)
        
        # Resample from 8kHz to 16kHz
        original_rate = 8000
        target_rate = 16000
        
        # Resample the audio
        resampled_pcm = signal.resample(pcm_data, int(len(pcm_data) * target_rate / original_rate))
        
        # Convert back to bytes
        return resampled_pcm.astype(np.int16).tobytes()
    
    @staticmethod
    def pcm_to_ulaw(pcm_data: bytes) -> bytes:
        """
        Convert PCM audio data to μ-law format.
        
        Args:
            pcm_data: PCM format audio data (16kHz)
            
        Returns:
            μ-law encoded audio data (8kHz)
        """
        import numpy as np
        from scipy import signal
        
        # Convert to numpy array
        pcm_array = np.frombuffer(pcm_data, dtype=np.int16)
        
        # Resample from 16kHz to 8kHz
        original_rate = 16000
        target_rate = 8000
        
        # Resample the audio
        resampled_pcm = signal.resample(pcm_array, int(len(pcm_array) * target_rate / original_rate))
        
        # Normalize to values between -1 and 1
        normalized = resampled_pcm.astype(np.float32) / 32768.0
        
        # Apply μ-law compression
        mu = 255  # μ-law parameter
        sign = np.sign(normalized)
        amplitude = np.minimum(np.abs(normalized), 1.0)
        compressed = sign * np.log(1 + mu * amplitude) / np.log(1 + mu)
        
        # Scale to 8 bits and convert to uint8
        ulaw_array = ((compressed + 1) * 127.5).astype(np.uint8)
        
        # Convert back to bytes
        return ulaw_array.tobytes()


class RealtimeEventProcessor:
    """
    Processes events from the OpenAI Realtime API, dispatching them to
    appropriate handlers based on event type.
    """
    
    def __init__(self, client: 'OpenAIRealtimeClient'):
        """
        Initialize the event processor.
        
        Args:
            client: The OpenAI Realtime client
        """
        self.client = client
        self.handlers = {}
        self.register_default_handlers()
    
    def register_handler(self, event_type: str, handler: Callable):
        """
        Register a handler for an event type.
        
        Args:
            event_type: The event type to handle
            handler: The handler function
        """
        self.handlers[event_type] = handler
    
    def register_default_handlers(self):
        """Register default handlers for common event types."""
        self.register_handler("transcript.final", self._handle_transcript)
        self.register_handler("response.audio.delta", self._handle_audio_delta)
        self.register_handler("tool_call", self._handle_tool_call)
        self.register_handler("input_audio_buffer.speech_started", self._handle_speech_started)
        self.register_handler("input_audio_buffer.speech_stopped", self._handle_speech_stopped)
        self.register_handler("error", self._handle_error)
    
    async def process_event(self, event: Dict[str, Any]):
        """
        Process an event from the OpenAI Realtime API.
        
        Args:
            event: The event to process
        """
        event_type = event.get("type", "unknown")
        
        if event_type in self.handlers:
            await self.handlers[event_type](event)
        else:
            logger.debug(f"No handler for event type: {event_type}")
    
    async def _handle_transcript(self, event: Dict[str, Any]):
        """
        Handle a transcript.final event.
        
        Args:
            event: The transcript event
        """
        transcript = event.get("transcript", "")
        logger.info(f"Transcript: {transcript}")
        
        if self.client.transcript_callback:
            await self.client.transcript_callback(transcript)
    
    async def _handle_audio_delta(self, event: Dict[str, Any]):
        """
        Handle a response.audio.delta event.
        
        Args:
            event: The audio delta event
        """
        audio_data = event.get("delta", "")
        logger.debug("Received audio delta")
        
        if self.client.audio_callback:
            try:
                # The audio data is base64-encoded
                audio_bytes = base64.b64decode(audio_data)
                await self.client.audio_callback(audio_bytes)
            except Exception as e:
                logger.error(f"Error in audio callback: {e}")
                logger.error(traceback.format_exc())
    
    async def _handle_tool_call(self, event: Dict[str, Any]):
        """
        Handle a tool_call event.
        
        Args:
            event: The tool call event
        """
        tool_name = event.get("name", "")
        arguments = event.get("arguments", {})
        tool_id = event.get("id", "")
        
        logger.info(f"Tool call: {tool_name} with ID {tool_id}")
        logger.debug(f"Tool arguments: {arguments}")
        
        if self.client.tool_call_callback:
            try:
                result = await self.client.tool_call_callback(tool_name, arguments, tool_id)
                
                # Send the tool response back
                await self.client.send_tool_response(tool_id, result)
            except Exception as e:
                logger.error(f"Error in tool call callback: {e}")
                logger.error(traceback.format_exc())
                
                # Send an error response
                await self.client.send_tool_response(
                    tool_id, 
                    {"status": "error", "message": f"Error: {str(e)}"}
                )
    
    async def _handle_speech_started(self, event: Dict[str, Any]):
        """
        Handle an input_audio_buffer.speech_started event.
        
        Args:
            event: The speech started event
        """
        logger.info("Speech started event")
        
        if self.client.speech_started_callback:
            await self.client.speech_started_callback()
    
    async def _handle_speech_stopped(self, event: Dict[str, Any]):
        """
        Handle an input_audio_buffer.speech_stopped event.
        
        Args:
            event: The speech stopped event
        """
        logger.info("Speech stopped event")
        
        if self.client.speech_stopped_callback:
            await self.client.speech_stopped_callback()
    
    async def _handle_error(self, event: Dict[str, Any]):
        """
        Handle an error event.
        
        Args:
            event: The error event
        """
        error_message = event.get("message", "Unknown error")
        logger.error(f"Error event: {error_message}")
        
        if self.client.error_callback:
            await self.client.error_callback(error_message)


class OpenAIRealtimeClient:
    """
    Async client for the OpenAI Realtime API, supporting WebSocket communication
    for real-time audio streaming, transcription, and TTS.
    """
    
    # OpenAI Realtime API endpoint
    WEBSOCKET_URL = "wss://api.openai.com/v1/realtime"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        config: Optional[RealtimeConfig] = None,
        session_id: Optional[str] = None
    ):
        """
        Initialize the OpenAI Realtime client.
        
        Args:
            api_key: The OpenAI API key (defaults to settings.OPENAI_API_KEY)
            config: The Realtime configuration
            session_id: The session ID (defaults to a generated UUID)
        """
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.config = config or RealtimeConfig()
        self.session_id = session_id or str(uuid.uuid4())
        
        self.websocket = None
        self.event_processor = RealtimeEventProcessor(self)
        self.connected = False
        self.running = False
        
        # Event processing task
        self._event_processing_task = None
        
        # Callbacks
        self.transcript_callback = None
        self.audio_callback = None
        self.tool_call_callback = None
        self.speech_started_callback = None
        self.speech_stopped_callback = None
        self.error_callback = None
        
        # Audio buffer for TTS
        self.audio_buffer = []
    
    async def connect(self) -> bool:
        """
        Connect to the OpenAI Realtime API.
        
        Returns:
            True if connection is successful, False otherwise
        """
        # CRITICAL DEBUG: Log OpenAI API key status with high visibility
        if not self.api_key:
            logger.critical(f"🔴 OPENAI API KEY MISSING! Session: {self.session_id}")
            logger.critical(f"🔴 Cannot connect to OpenAI Realtime API without an API key")
            logger.critical(f"🔴 Check your environment variables or config settings")
            logger.critical(f"🔴 Current environment has OPENAI_API_KEY: {'YES' if settings.OPENAI_API_KEY else 'NO!!!'}")
            self.connected = False
            return False

        # Log API key first few characters for debugging (safely)
        if self.api_key:
            key_preview = self.api_key[:4] + '...' + self.api_key[-4:] if len(self.api_key) > 8 else '[TOO SHORT]'
            logger.critical(f"🔶 OpenAI API Key configured, preview: {key_preview}")
            if not self.api_key.startswith('sk-'):
                logger.critical(f"🔴 WARNING: API key doesn't start with 'sk-', may be invalid: {key_preview}")
        
        if self.connected:
            logger.warning("Already connected to OpenAI Realtime API")
            return True
        
        logger.critical(f"🔄 CONNECTING to OpenAI Realtime API with session ID: {self.session_id}")
        logger.critical(f"🔄 WebSocket URL: {self.WEBSOCKET_URL}")
        
        try:
            # Prepare headers
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "OpenAI-Beta": "realtime=v1",
                "Content-Type": "application/json"
            }
            
            # Log the attempt with complete details
            logger.critical(f"🔄 Connection attempt with headers: Authorization: Bearer {key_preview}, OpenAI-Beta: realtime=v1")
            
            # Connect to the WebSocket
            self.websocket = await websockets.connect(
                self.WEBSOCKET_URL,
                extra_headers=headers
            )
            
            logger.critical("🟢 SUCCESSFULLY CONNECTED to OpenAI Realtime API")
            self.connected = True
            
            # Configure the session
            await self._configure_session()
            
            # Start event processing
            self.running = True
            self._event_processing_task = asyncio.create_task(self._process_events())
            
            return True
        except websockets.exceptions.InvalidStatusCode as e:
            # CRITICAL: Handle HTTP status code errors specifically
            status_code = getattr(e, 'status_code', 'unknown')
            logger.critical(f"🔴 CONNECTION FAILED with HTTP status {status_code}: {str(e)}")
            
            if status_code == 401:
                logger.critical(f"🔴 AUTHENTICATION ERROR (401): Invalid API key or insufficient permissions")
                logger.critical(f"🔴 Please check that your API key is correct and has access to the Realtime API")
            elif status_code == 403:
                logger.critical(f"🔴 AUTHORIZATION ERROR (403): Account does not have access to the Realtime API")
                logger.critical(f"🔴 Your OpenAI account might need to be explicitly granted access to this API")
            elif status_code == 429:
                logger.critical(f"🔴 RATE LIMIT ERROR (429): Too many requests or quota exceeded")
            else:
                logger.critical(f"🔴 CONNECTION ERROR with status {status_code}: {str(e)}")
            
            logger.error(traceback.format_exc())
            self.connected = False
            return False
        except websockets.exceptions.ConnectionClosedError as e:
            logger.critical(f"🔴 WebSocket CONNECTION CLOSED ERROR: code={e.code}, reason={e.reason}")
            logger.error(traceback.format_exc())
            self.connected = False
            return False
        except Exception as e:
            logger.critical(f"🔴 UNEXPECTED ERROR connecting to OpenAI Realtime API: {e}")
            logger.critical(f"🔴 Error type: {type(e).__name__}")
            logger.error(traceback.format_exc())
            self.connected = False
            return False
    
    async def _configure_session(self):
        """Configure the OpenAI Realtime session."""
        logger.critical("🔄 Configuring OpenAI Realtime session - CRITICAL STEP")
        
        # Prepare VAD configuration
        vad_config = {
            "mode": "server",
            "silence_threshold_ms": self.config.vad_silence_threshold_ms,
            "speech_threshold_ms": self.config.vad_speech_threshold_ms
        } if self.config.vad_enabled else None
        
        # Prepare session configuration
        session_config = {
            "type": "session.update",
            "session": {
                "model": self.config.model,
                "modalities": ["text", "audio"],
                "voice": self.config.voice,
                "sample_rate_hz": self.config.sample_rate_hz,
                "inputAudioFormat": {
                    "type": self.config.input_audio_format
                },
                "outputAudioFormat": {
                    "type": self.config.output_audio_format
                }
            }
        }
        
        # Add optional parameters
        if self.config.instructions:
            session_config["session"]["instructions"] = self.config.instructions
        
        if self.config.max_tokens:
            session_config["session"]["max_tokens"] = self.config.max_tokens
        
        if vad_config:
            session_config["session"]["vad"] = vad_config
        
        # Log the complete session configuration for debugging
        logger.critical(f"🔄 Sending session configuration: {json.dumps(session_config)}")
        
        try:
            # Send session configuration
            await self.send_event(session_config)
            logger.critical("🟢 Session configuration sent successfully")
        except Exception as e:
            logger.critical(f"🔴 FAILED to send session configuration: {e}")
            logger.critical(traceback.format_exc())
            raise
    
    async def send_event(self, event: Dict[str, Any]):
        """
        Send an event to the OpenAI Realtime API.
        
        Args:
            event: The event to send
        
        Raises:
            RuntimeError: If not connected to the API
        """
        if not self.connected or not self.websocket:
            raise RuntimeError("Not connected to OpenAI Realtime API")
        
        try:
            event_json = json.dumps(event)
            await self.websocket.send(event_json)
        except Exception as e:
            logger.error(f"Error sending event: {e}")
            logger.error(traceback.format_exc())
            raise
    
    async def _process_events(self):
        """
        Process events from the OpenAI Realtime API.
        This runs as a background task while the client is connected.
        """
        if not self.websocket:
            logger.critical("🔴 WebSocket not connected, cannot process events - CRITICAL FAILURE")
            return
        
        logger.critical("🟢 Starting event processing loop - CONNECTION SUCCESSFUL")
        
        try:
            while self.running and self.connected:
                try:
                    # Receive a message from the WebSocket
                    message = await self.websocket.recv()
                    
                    # Parse the message as JSON
                    event = json.loads(message)
                    event_type = event.get("type", "unknown")
                    
                    # Log the event (with different log levels based on type)
                    if event_type in ["error", "session.error"]:
                        logger.critical(f"🔴 RECEIVED ERROR EVENT: {json.dumps(event)}")
                    elif event_type == "session.update":
                        status = event.get("status", "unknown")
                        if status == "error":
                            logger.critical(f"🔴 SESSION UPDATE ERROR: {json.dumps(event)}")
                        else:
                            logger.critical(f"🟢 SESSION UPDATE SUCCESS: {status}")
                    elif event_type == "transcript.final":
                        transcript_text = event.get("data", {}).get("text", "")
                        logger.critical(f"🟢 RECEIVED TRANSCRIPT: {transcript_text}")
                    elif event_type.startswith("response.audio"):
                        logger.debug(f"Received audio event: {event_type}")
                    else:
                        logger.info(f"Received event: {event_type}")
                        logger.debug(f"Event details: {json.dumps(event)}")
                    
                    # Process the event
                    await self.event_processor.process_event(event)
                    
                except ConnectionClosed as e:
                    logger.critical(f"🔴 WebSocket CONNECTION CLOSED: code={e.code}, reason={e.reason}")
                    self.connected = False
                    break
                except ConnectionClosedError as e:
                    logger.critical(f"🔴 WebSocket CONNECTION CLOSED WITH ERROR: code={e.code}, reason={e.reason}")
                    self.connected = False
                    break
                except json.JSONDecodeError as e:
                    logger.critical(f"🔴 ERROR DECODING JSON: {e}")
                    logger.critical(f"🔴 Raw message: {message}")
                except Exception as e:
                    logger.critical(f"🔴 ERROR PROCESSING EVENT: {e}")
                    logger.critical(traceback.format_exc())
        finally:
            logger.critical("🔴 EVENT PROCESSING STOPPED - Connection may have been lost")
            self.running = False
    
    async def send_audio(self, audio_data: bytes):
        """
        Send audio data to the OpenAI Realtime API.
        
        Args:
            audio_data: The audio data to send
        """
        if not self.connected:
            logger.warning("Not connected to OpenAI Realtime API, cannot send audio")
            return
        
        try:
            # Encode the audio as base64
            base64_audio = base64.b64encode(audio_data).decode("utf-8")
            
            # Send the audio event
            await self.send_event({
                "type": "input_audio_buffer.append",
                "audio": base64_audio
            })
        except Exception as e:
            logger.error(f"Error sending audio: {e}")
            logger.error(traceback.format_exc())
    
    async def send_text_for_tts(self, text: str):
        """
        Send text to be converted to speech (TTS).
        
        Args:
            text: The text to convert to speech
        """
        if not self.connected:
            logger.warning("Not connected to OpenAI Realtime API, cannot send text for TTS")
            return
        
        try:
            # First, create a conversation item with the text
            await self.send_event({
                "type": "conversation.item.create",
                "conversationItem": {
                    "role": "assistant",
                    "content": text
                }
            })
            
            # Then, create a response for that item
            await self.send_event({
                "type": "response.create",
                "response": {
                    "modalities": ["audio"]
                }
            })
            
            logger.info(f"Sent text for TTS: {text}")
        except Exception as e:
            logger.error(f"Error sending text for TTS: {e}")
            logger.error(traceback.format_exc())
    
    async def send_tool_response(self, tool_id: str, result: Dict[str, Any]):
        """
        Send a tool response to the OpenAI Realtime API.
        
        Args:
            tool_id: The ID of the tool call
            result: The result to send
        """
        if not self.connected:
            logger.warning("Not connected to OpenAI Realtime API, cannot send tool response")
            return
        
        try:
            # Create a conversation item with the tool output
            await self.send_event({
                "type": "conversation.item.create",
                "conversationItem": {
                    "role": "function_call_output",
                    "content": json.dumps(result),
                    "id": tool_id
                }
            })
            
            # Generate a response
            await self.send_event({
                "type": "response.create",
                "response": {
                    "modalities": ["text", "audio"]
                }
            })
            
            logger.info(f"Sent tool response for tool ID: {tool_id}")
        except Exception as e:
            logger.error(f"Error sending tool response: {e}")
            logger.error(traceback.format_exc())
    
    async def close(self):
        """Close the connection to the OpenAI Realtime API."""
        logger.info("Closing OpenAI Realtime client")
        
        self.running = False
        
        # Cancel the event processing task
        if self._event_processing_task:
            self._event_processing_task.cancel()
            try:
                await self._event_processing_task
            except asyncio.CancelledError:
                pass
        
        # Close the WebSocket connection
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
        
        self.connected = False
        logger.info("OpenAI Realtime client closed")
    
    def register_callbacks(
        self,
        transcript_callback: Optional[Callable] = None,
        audio_callback: Optional[Callable] = None,
        tool_call_callback: Optional[Callable] = None,
        speech_started_callback: Optional[Callable] = None,
        speech_stopped_callback: Optional[Callable] = None,
        error_callback: Optional[Callable] = None
    ):
        """
        Register callbacks for different event types.
        
        Args:
            transcript_callback: Called when a transcript event is received
            audio_callback: Called when an audio event is received
            tool_call_callback: Called when a tool call event is received
            speech_started_callback: Called when speech starts
            speech_stopped_callback: Called when speech stops
            error_callback: Called when an error event is received
        """
        if transcript_callback:
            self.transcript_callback = transcript_callback
        
        if audio_callback:
            self.audio_callback = audio_callback
        
        if tool_call_callback:
            self.tool_call_callback = tool_call_callback
        
        if speech_started_callback:
            self.speech_started_callback = speech_started_callback
        
        if speech_stopped_callback:
            self.speech_stopped_callback = speech_stopped_callback
        
        if error_callback:
            self.error_callback = error_callback


class RealtimeClientManager:
    """
    Manages OpenAI Realtime clients for multiple sessions.
    
    This class provides a centralized way to create, retrieve, and manage
    OpenAI Realtime clients for different sessions.
    """
    
    def __init__(self):
        """Initialize the Realtime client manager."""
        self.clients: Dict[str, OpenAIRealtimeClient] = {}
        
        # Default configuration
        self.default_config = RealtimeConfig(
            model="gpt-4o-realtime-preview-2024-10-01",
            voice="shimmer",
            sample_rate_hz=8000,
            input_audio_format="mulaw",
            output_audio_format="mulaw",
            vad_enabled=True,
            vad_silence_threshold_ms=1000,
            vad_speech_threshold_ms=8000
        )
    
    async def create_client(
        self,
        session_id: Optional[str] = None,
        config: Optional[RealtimeConfig] = None,
        api_key: Optional[str] = None
    ) -> OpenAIRealtimeClient:
        """
        Create a new OpenAI Realtime client.
        
        Args:
            session_id: The session ID (defaults to a generated UUID)
            config: The Realtime configuration (defaults to self.default_config)
            api_key: The OpenAI API key (defaults to settings.OPENAI_API_KEY)
            
        Returns:
            The created client
        """
        # Generate a session ID if not provided
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # Use default config if not provided
        if not config:
            config = self.default_config
        
        # Create the client
        client = OpenAIRealtimeClient(
            api_key=api_key,
            config=config,
            session_id=session_id
        )
        
        # Store the client
        self.clients[session_id] = client
        
        # Connect to the API
        await client.connect()
        
        return client
    
    def get_client(self, session_id: str) -> Optional[OpenAIRealtimeClient]:
        """
        Get an existing OpenAI Realtime client.
        
        Args:
            session_id: The session ID
            
        Returns:
            The client if found, None otherwise
        """
        return self.clients.get(session_id)
    
    async def close_client(self, session_id: str) -> bool:
        """
        Close and remove an OpenAI Realtime client.
        
        Args:
            session_id: The session ID
            
        Returns:
            True if the client was closed, False otherwise
        """
        client = self.clients.get(session_id)
        
        if client:
            await client.close()
            del self.clients[session_id]
            return True
        
        return False
    
    async def close_all(self):
        """Close all OpenAI Realtime clients."""
        for session_id, client in list(self.clients.items()):
            await client.close()
        
        self.clients.clear()
        
        logger.info("All Realtime clients closed")


# Create a global instance of the client manager
realtime_client_manager = RealtimeClientManager()


async def process_realtime_audio(
    call_sid: str,
    audio_generator: AsyncGenerator[bytes, None],
    instructions: Optional[str] = None,
    transcripts_callback: Optional[Callable] = None,
    audio_callback: Optional[Callable] = None,
    tool_callback: Optional[Callable] = None
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Process real-time audio through the OpenAI Realtime API.
    
    Args:
        call_sid: The call SID or session ID
        audio_generator: A generator yielding audio chunks
        instructions: Custom instructions for the model
        transcripts_callback: Callback for transcripts
        audio_callback: Callback for TTS audio
        tool_callback: Callback for tool calls
        
    Yields:
        Events from the OpenAI Realtime API
    """
    logger.info(f"Starting real-time audio processing for call: {call_sid}")
    
    # Create client configuration
    config = RealtimeConfig(
        model="gpt-4o-realtime-preview-2024-10-01",
        instructions=instructions,
        voice="shimmer",
        sample_rate_hz=8000,
        input_audio_format="mulaw",
        output_audio_format="mulaw",
        vad_enabled=True
    )
    
    # Create a client
    client = await realtime_client_manager.create_client(call_sid, config)
    
    # Register callbacks
    client.register_callbacks(
        transcript_callback=transcripts_callback,
        audio_callback=audio_callback,
        tool_call_callback=tool_callback
    )
    
    # Create a queue for events
    event_queue = asyncio.Queue()
    
    # Register event handler callbacks
    async def handle_transcript(transcript):
        await event_queue.put({
            "type": "transcript",
            "text": transcript,
            "timestamp": time.time()
        })
    
    async def handle_audio(audio_data):
        await event_queue.put({
            "type": "audio",
            "data": base64.b64encode(audio_data).decode("utf-8"),
            "timestamp": time.time()
        })
    
    async def handle_tool_call(tool_name, arguments, tool_id):
        event = {
            "type": "tool_call",
            "name": tool_name,
            "arguments": arguments,
            "id": tool_id,
            "timestamp": time.time()
        }
        await event_queue.put(event)
        
        # Return a placeholder result
        # The actual result should be provided by the tool callback
        return {"status": "pending", "message": "Tool call received"}
    
    async def handle_speech_started():
        await event_queue.put({
            "type": "speech_started",
            "timestamp": time.time()
        })
    
    async def handle_speech_stopped():
        await event_queue.put({
            "type": "speech_stopped",
            "timestamp": time.time()
        })
    
    async def handle_error(error_message):
        await event_queue.put({
            "type": "error",
            "message": error_message,
            "timestamp": time.time()
        })
    
    # Register all callbacks
    client.register_callbacks(
        transcript_callback=handle_transcript,
        audio_callback=handle_audio,
        tool_call_callback=handle_tool_call,
        speech_started_callback=handle_speech_started,
        speech_stopped_callback=handle_speech_stopped,
        error_callback=handle_error
    )
    
    # Create a task to process audio chunks
    async def process_audio():
        try:
            async for chunk in audio_generator:
                # Check if client is still connected
                if not client.connected:
                    logger.warning("Client disconnected, stopping audio processing")
                    break
                
                # Send the audio chunk to the client
                await client.send_audio(chunk)
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            logger.error(traceback.format_exc())
            await event_queue.put({
                "type": "error",
                "message": f"Error processing audio: {str(e)}",
                "timestamp": time.time()
            })
    
    # Start the audio processing task
    audio_task = asyncio.create_task(process_audio())
    
    try:
        # Yield events from the queue
        while True:
            try:
                # Wait for an event with a timeout
                event = await asyncio.wait_for(event_queue.get(), timeout=5.0)
                yield event
                event_queue.task_done()
            except asyncio.TimeoutError:
                # Check if audio task is done
                if audio_task.done():
                    # Check for exceptions
                    if audio_task.exception():
                        logger.error(f"Audio task raised an exception: {audio_task.exception()}")
                        yield {
                            "type": "error",
                            "message": f"Audio processing error: {str(audio_task.exception())}",
                            "timestamp": time.time()
                        }
                    
                    logger.info("Audio task complete, ending processing")
                    break
                
                # Check if client is still connected
                if not client.connected:
                    logger.warning("Client disconnected, ending processing")
                    break
                
                # Continue waiting for events
                continue
    finally:
        # Clean up resources
        if not audio_task.done():
            audio_task.cancel()
            try:
                await audio_task
            except asyncio.CancelledError:
                pass
        
        # Close the client
        await realtime_client_manager.close_client(call_sid)
        
        logger.info(f"Real-time audio processing complete for call: {call_sid}")