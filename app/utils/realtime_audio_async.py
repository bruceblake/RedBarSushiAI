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
# Force DEBUG level for this module specifically
logger.setLevel(logging.DEBUG)

# Ensure the logs directory exists
log_dir = os.path.join(os.getcwd(), 'logs')
os.makedirs(log_dir, exist_ok=True)

# Add a file handler for this module
file_handler = logging.FileHandler(os.path.join(log_dir, 'realtime_audio_async.log'))
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Add a console handler too for immediate visibility
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Ensure our logs are seen even if parent loggers have higher levels
logger.propagate = False

logger.critical("======= ASYNC REALTIME AUDIO CLIENT LOGGING INITIALIZED WITH FORCED DEBUG LEVEL =======")

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
        # The event could be in one of these formats:
        # 1. {"type": "transcript.final", "text": "..."}
        # 2. {"type": "transcript.final", "data": {"text": "..."}}
        # 3. {"type": "transcript.final", "transcript": "..."} (old format)
        
        # Try all possible locations for the transcript text
        transcript = event.get("text", "")
        if not transcript and "data" in event:
            transcript = event.get("data", {}).get("text", "")
        if not transcript:
            transcript = event.get("transcript", "")
            
        logger.info(f"Transcript: {transcript}")
        
        if self.client.transcript_callback:
            await self.client.transcript_callback(transcript)
    
    async def _handle_audio_delta(self, event: Dict[str, Any]):
        """
        Handle a response.audio.delta event.
        
        Args:
            event: The audio delta event from OpenAI
        """
        # Extract the response_id to track which TTS request this is for
        response_id = event.get("response_id", "unknown")
        
        # Extract audio data according to OpenAI documentation format
        # https://platform.openai.com/docs/guides/realtime-conversations
        audio = event.get("audio", {})
        
        # The payload contains the base64-encoded audio chunk
        audio_payload = audio.get("payload", "")
        
        # Check if this is the end of the audio stream
        is_end_of_stream = audio.get("end_of_stream", False)
        
        if is_end_of_stream:
            logger.info(f"End of audio stream for response_id: {response_id}")
            # You might want to notify the client that this audio stream is complete
            return
        
        logger.debug(f"Received audio delta for response_id: {response_id}, payload length: {len(audio_payload)}")
        
        if not audio_payload:
            logger.debug("Empty audio payload received, skipping")
            return
            
        if self.client.audio_callback:
            try:
                # The audio data is base64-encoded
                audio_bytes = base64.b64decode(audio_payload)
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
    
    async def on_close(self, close_info: Dict[str, Any]):
        """
        Handle WebSocket close event.
        
        Args:
            close_info: Information about the close event
        """
        logger.info(f"WebSocket closed: {close_info}")
        
        # Any additional cleanup or notification can be done here
        pass


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
        session_id: Optional[str] = None,
        event_processor: Optional['RealtimeEventProcessor'] = None
    ):
        """
        Initialize the OpenAI Realtime client.
        
        Args:
            api_key: The OpenAI API key (defaults to settings.OPENAI_API_KEY)
            config: The Realtime configuration
            session_id: The session ID (defaults to a generated UUID)
            event_processor: An optional custom event processor
        """
        # Track if API key was explicitly provided
        if api_key is not None:
            self._explicit_api_key_provided = True
            self.api_key = api_key
        else:
            self._explicit_api_key_provided = False
            self.api_key = settings.OPENAI_API_KEY
        
        self.config = config or RealtimeConfig()
        self.session_id = session_id or str(uuid.uuid4())
        
        # Log initialization details
        logger.critical(f"🔄 Initializing OpenAIRealtimeClient for session {self.session_id}")
        logger.critical(f"🔄 Using model: {self.config.model}")
        logger.critical(f"🔄 API key present: {bool(self.api_key)}")
        logger.critical(f"🔄 API key source: {'INSTANCE PARAMETER' if self._explicit_api_key_provided else 'SETTINGS'}")
        
        print(f"\n!!! DEBUG: Initializing OpenAIRealtimeClient for session {self.session_id}", flush=True)
        print(f"\n!!! DEBUG: API key present: {bool(self.api_key)}", flush=True)
        print(f"\n!!! DEBUG: API key source: {'INSTANCE PARAMETER' if self._explicit_api_key_provided else 'SETTINGS'}", flush=True)
        
        self.websocket = None
        self.event_processor = event_processor or RealtimeEventProcessor(self)
        self.connected = False
        self.running = False
        
        # Event processing task - crucial for task management
        self._event_processing_task = None
        self.is_processing_loop_active = False
        
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
        # Call SID for consistent logging
        call_sid = getattr(self, 'session_id', 'UNKNOWN_CALL')
        
        # Extra debug to stderr using print (in case log configuration is broken)
        print(f"\n!!! DEBUG: OpenAIRealtimeClient.connect() called for session {call_sid}", flush=True)
        
        # CRITICAL DEBUG: Log OpenAI API key status with high visibility
        logger.critical(f"🔴 [{call_sid}] CONNECT ATTEMPT STARTED for model: {self.config.model}")
        
        if not self.api_key:
            logger.critical(f"🔴 [{call_sid}] OPENAI API KEY MISSING!")
            logger.critical(f"🔴 [{call_sid}] Cannot connect to OpenAI Realtime API without an API key")
            logger.critical(f"🔴 Check your environment variables or config settings")
            logger.critical(f"🔴 Current environment has OPENAI_API_KEY: {'YES' if settings.OPENAI_API_KEY else 'NO!!!'}")
            print(f"\n!!! DEBUG: OpenAI API Key is MISSING for session {self.session_id}!", flush=True)
            self.connected = False
            return False

        # Log API key first few characters for debugging (safely)
        if self.api_key:
            key_preview = self.api_key[:4] + '...' + self.api_key[-4:] if len(self.api_key) > 8 else '[TOO SHORT]'
            key_length = len(self.api_key)
            logger.critical(f"🔶 [{self.session_id}] OpenAI API Key configured, preview: {key_preview}, length: {key_length}")
            logger.critical(f"🔶 [{self.session_id}] OpenAI API Key source: {'INSTANCE PARAMETER' if hasattr(self, '_explicit_api_key_provided') else 'SETTINGS'}")
            print(f"\n!!! DEBUG: OpenAI API Key present (preview: {key_preview}, length: {key_length})", flush=True)
            
            # Advanced key validation checks
            if not self.api_key.startswith('sk-'):
                logger.critical(f"🔴 [{self.session_id}] WARNING: API key doesn't start with 'sk-', may be invalid: {key_preview}")
                print(f"\n!!! DEBUG: API key format warning - doesn't start with 'sk-'", flush=True)
                
            # Check for test/dummy key patterns
            test_key_patterns = ['mytestapikey', 'test', 'dummy', 'sample', 'example']
            if any(pattern in self.api_key.lower() for pattern in test_key_patterns):
                logger.critical(f"🔴 [{self.session_id}] CRITICAL WARNING: API key appears to be a test/dummy key: {key_preview}")
                logger.critical(f"🔴 [{self.session_id}] This key will NOT work with OpenAI. Please use a real API key!")
                print(f"\n!!! DEBUG: CRITICAL WARNING: API key appears to be a test/dummy key!", flush=True)
                print(f"\n!!! DEBUG: Connection will initially succeed but then be rejected by OpenAI!", flush=True)
        
        if self.connected:
            logger.critical("🟢 Already connected to OpenAI Realtime API")
            return True
        
        # Construct URL with query parameters as per OpenAI documentation
        from urllib.parse import urlencode
        
        # Add required and optional parameters to URL as specified in OpenAI docs
        url_query_params_dict = {
            "model": self.config.model,
            "voice": self.config.voice,
        }
        
        # Add language parameter if it exists in the config
        if hasattr(self.config, 'language'):
            url_query_params_dict["language"] = self.config.language
        
        # Filter out None values
        url_query_params_dict = {k: v for k, v in url_query_params_dict.items() if v is not None}
        
        # Ensure model is present, as it's absolutely required
        if not url_query_params_dict.get("model"):
            logger.critical(f"🔴 [{call_sid}] CRITICAL: Model not configured for OpenAIRealtimeClient. Cannot form connection URL.")
            if hasattr(self, 'event_processor') and self.event_processor:
                try:
                    await self.event_processor.on_error({"error": "OpenAI model not configured", "call_sid": call_sid})
                except Exception as e:
                    logger.error(f"Error during event processor error call: {e}")
            self.connected = False
            return False
        
        # Encode parameters for URL
        encoded_url_query_params = urlencode(url_query_params_dict)
        
        # Construct final URL with query parameters
        connect_url = f"{self.WEBSOCKET_URL}?{encoded_url_query_params}"
        
        logger.critical(f"🔄 [{call_sid}] OpenAIRealtimeClient: Connecting with effective URL: {connect_url}")
        print(f"!!! PRINT DEBUG: OpenAI Connect URL (with query params): {connect_url} !!!", flush=True)
        
        logger.critical(f"🔄 CONNECTING to OpenAI Realtime API with session ID: {self.session_id}")
        logger.critical(f"🔄 WebSocket URL: {connect_url}")
        print(f"\n!!! DEBUG: Attempting WebSocket connection to: {connect_url}", flush=True)
        
        try:
            # Prepare headers
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "OpenAI-Beta": "realtime=v1",
                "Content-Type": "application/json"
            }
            
            # Log the attempt with complete details
            logger.critical(f"🔄 Connection attempt with headers: Authorization: Bearer {key_preview}, OpenAI-Beta: realtime=v1")
            logger.critical(f"🔄 WEBSOCKETS CONNECT ATTEMPT: {connect_url} (about to execute)")
            
            # Connect to the WebSocket with the URL including query parameters
            print(f"\n!!! DEBUG: About to execute websockets.connect() with URL: {connect_url}", flush=True)
            
            # Set timeouts for connection to avoid hanging indefinitely
            try:
                self.websocket = await asyncio.wait_for(
                    websockets.connect(
                        connect_url,
                        extra_headers=headers,
                        ping_interval=30,  # Send ping every 30 seconds
                        close_timeout=5    # Allow 5 seconds for graceful close
                    ),
                    timeout=15.0  # 15-second connection timeout
                )
                logger.critical("🟢 SUCCESSFULLY CONNECTED to OpenAI Realtime API")
            except asyncio.TimeoutError:
                logger.critical(f"🔴 [{call_sid}] CONNECTION TIMEOUT: Failed to connect to OpenAI Realtime API within timeout")
                print(f"\n!!! DEBUG: CONNECTION TIMEOUT: Failed to connect to OpenAI Realtime API", flush=True)
                self.connected = False
                return False
            print(f"\n!!! DEBUG: WebSocket connection SUCCESSFUL!", flush=True)
            self.connected = True
            
            # Configure the session
            logger.critical("🔄 About to configure OpenAI Realtime session")
            try:
                await self._configure_session()
                logger.critical("🟢 Session configuration successful")
                print(f"\n!!! DEBUG: Session configuration successful", flush=True)
            except Exception as config_error:
                logger.critical(f"🔴 SESSION CONFIGURATION FAILED: {str(config_error)}")
                print(f"\n!!! DEBUG: SESSION CONFIGURATION FAILED: {str(config_error)}", flush=True)
                logger.critical(traceback.format_exc())
                # Continue despite configuration error - we'll try to work with the default config
            
            # Start event processing - with proper task management
            self.running = True
            
            # Cancel any existing event processing task before starting a new one
            if self._event_processing_task and not self._event_processing_task.done():
                logger.warning(f"Event processing task already exists. Cancelling old one.")
                self._event_processing_task.cancel()
                try:
                    await self._event_processing_task
                except asyncio.CancelledError:
                    logger.info("Old event processing task cancelled.")
                except Exception as e:
                    logger.error(f"Error awaiting cancelled event task: {e}")
            
            logger.critical("🔄 Starting event processing task")
            self.is_processing_loop_active = True
            self._event_processing_task = asyncio.create_task(self.process_messages())
            logger.critical("🟢 Event processing task started")
            
            return True
        except websockets.exceptions.InvalidStatusCode as e:
            # CRITICAL: Handle HTTP status code errors specifically
            status_code = getattr(e, 'status_code', 'unknown')
            response_body = getattr(e, 'response_body', 'no response body available')
            
            logger.critical(f"🔴 CONNECTION FAILED with HTTP status {status_code}: {str(e)}")
            logger.critical(f"🔴 Response body: {response_body}")
            print(f"\n!!! DEBUG: CONNECTION FAILED with HTTP status {status_code}: {str(e)}", flush=True)
            print(f"\n!!! DEBUG: Response body: {response_body}", flush=True)
            
            if status_code == 401:
                logger.critical(f"🔴 AUTHENTICATION ERROR (401): Invalid API key or insufficient permissions")
                logger.critical(f"🔴 Please check that your API key is correct and has access to the Realtime API")
                print(f"\n!!! DEBUG: AUTHENTICATION ERROR (401) - Invalid API key", flush=True)
            elif status_code == 403:
                logger.critical(f"🔴 AUTHORIZATION ERROR (403): Account does not have access to the Realtime API")
                logger.critical(f"🔴 Your OpenAI account might need to be explicitly granted access to this API")
                print(f"\n!!! DEBUG: AUTHORIZATION ERROR (403) - No access to Realtime API", flush=True)
            elif status_code == 429:
                logger.critical(f"🔴 RATE LIMIT ERROR (429): Too many requests or quota exceeded")
                print(f"\n!!! DEBUG: RATE LIMIT ERROR (429)", flush=True)
            else:
                logger.critical(f"🔴 CONNECTION ERROR with status {status_code}: {str(e)}")
                print(f"\n!!! DEBUG: CONNECTION ERROR with status {status_code}", flush=True)
            
            logger.critical(f"Full error: {traceback.format_exc()}")
            self.connected = False
            return False
        except websockets.exceptions.ConnectionClosedError as e:
            logger.critical(f"🔴 WebSocket CONNECTION CLOSED ERROR: code={e.code}, reason={e.reason}")
            logger.critical(traceback.format_exc())
            print(f"\n!!! DEBUG: WebSocket CONNECTION CLOSED ERROR: code={e.code}, reason={e.reason}", flush=True)
            self.connected = False
            return False
        except Exception as e:
            logger.critical(f"🔴 UNEXPECTED ERROR connecting to OpenAI Realtime API: {e}")
            logger.critical(f"🔴 Error type: {type(e).__name__}")
            logger.critical(traceback.format_exc())
            print(f"\n!!! DEBUG: UNEXPECTED ERROR connecting to OpenAI Realtime API: {str(e)}", flush=True)
            print(f"\n!!! DEBUG: Error type: {type(e).__name__}", flush=True)
            print(f"\n!!! DEBUG: {traceback.format_exc()}", flush=True)
            self.connected = False
            return False
    
    async def _configure_session(self):
        """Configure the OpenAI Realtime session following OpenAI documentation format."""
        call_sid = getattr(self, 'session_id', 'UNKNOWN_CALL')
        logger.critical(f"🔄 [{call_sid}] Configuring OpenAI Realtime session - CRITICAL STEP")
        
        # Prepare VAD configuration according to OpenAI docs
        vad_config = {
            "mode": "server",
            "silence_threshold_ms": self.config.vad_silence_threshold_ms,
            "speech_threshold_ms": self.config.vad_speech_threshold_ms
        } if self.config.vad_enabled else None
        
        # Prepare input and output audio formats according to OpenAI docs
        # For μ-law audio format (8kHz), we'll use explicit format specification
        input_audio_format = {
            "container": "mulaw",  # Could also be "raw" depending on OpenAI's expectation
            "encoding": "pcm_mulaw",
            "sample_rate": self.config.sample_rate_hz  # Should be 8000 for μ-law
        }
        
        output_audio_format = {
            "container": "mulaw",  # Could also be "raw" depending on OpenAI's expectation
            "encoding": "pcm_mulaw",
            "sample_rate": self.config.sample_rate_hz  # Should be 8000 for μ-law
        }
        
        # Fallback to simple format if detailed format causes issues
        # This can be toggled based on testing results
        use_simple_audio_format = True  # Set to False to use detailed format above
        
        if use_simple_audio_format:
            input_audio_format = {
                "type": self.config.input_audio_format
            }
            output_audio_format = {
                "type": self.config.output_audio_format
            }
        
        # Prepare session configuration with all fields from OpenAI documentation
        session_config = {
            "type": "session.update",
            "session": {
                # Basic configuration - some redundant with URL but included as per docs
                "model": self.config.model,
                "voice": self.config.voice,
                "modalities": ["text", "audio"],
                
                # Audio format configuration
                "input_audio_format": input_audio_format,
                "output_audio_format": output_audio_format,
                
                # Stream configuration
                "stream_priority": getattr(self.config, "stream_priority", "default"),
                "interrupt_types": getattr(self.config, "interrupt_types", ["speech_start", "speech_stop"]),
                
                # TTS configuration
                "speed": getattr(self.config, "tts_speed", 1.0),
                "buffer_ms": getattr(self.config, "buffer_ms", 200),
                
                # Instruction and response configuration
                "instructions": self.config.instructions if hasattr(self.config, "instructions") else None,
                "response_expected": getattr(self.config, "response_expected", True),
                
                # Optional VAD configuration
                "vad": vad_config,
                
                # Optional token limit
                "max_tokens": self.config.max_tokens if hasattr(self.config, "max_tokens") else None,
                
                # Optional language (if configured and not in URL)
                "language": getattr(self.config, "language", "en"),
                
                # Optional tools for function calling
                "tools": getattr(self.config, "tools", [])
            }
        }
        
        # Filter out None values to keep the configuration clean
        session_data = session_config["session"]
        session_config["session"] = {k: v for k, v in session_data.items() if v is not None}
        
        # Some lists like empty tools should be preserved
        if "tools" not in session_config["session"] and hasattr(self.config, "tools"):
            session_config["session"]["tools"] = []
        
        # Log the complete session configuration for debugging
        logger.critical(f"🔄 [{call_sid}] Sending session configuration: {json.dumps(session_config, indent=2)}")
        
        try:
            # Send session configuration
            await self.send_event(session_config)
            logger.critical(f"🟢 [{call_sid}] Session configuration sent successfully")
        except Exception as e:
            logger.critical(f"🔴 [{call_sid}] FAILED to send session configuration: {e}")
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
    
    async def process_messages(self):
        """
        Process messages from the OpenAI Realtime API.
        This runs as a background task while the client is connected.
        Public method called by handlers.py.
        """
        # Call SID for logging context
        call_sid = getattr(self, 'session_id', 'UNKNOWN_CALL')
        
        if not self.websocket or not self.connected:
            logger.critical(f"🔴 [{call_sid}] WebSocket not connected or is_connected is False. Cannot process messages - CRITICAL FAILURE")
            print(f"\n!!! DEBUG: WebSocket not connected, cannot process messages", flush=True)
            self.is_processing_loop_active = False
            return
        
        logger.critical(f"🟢 [{call_sid}] Starting event processing loop - CONNECTION SUCCESSFUL. self.is_processing_loop_active={self.is_processing_loop_active}")
        print(f"\n!!! DEBUG: Event processing loop STARTING", flush=True)
        
        self.is_processing_loop_active = True
        
        try:
            logger.critical(f"🔄 [{call_sid}] Entering main event loop")
            print(f"\n!!! DEBUG: Entering main event processing loop", flush=True)
            
            # Using async for is safer to prevent multiple recv() calls
            # However, we need to handle the case where the connection is closed forcibly
            async for message in self.websocket:
                if not self.is_processing_loop_active or not self.running:
                    logger.info(f"[{call_sid}] Event loop flagged to stop externally. Breaking.")
                    break
                
                logger.debug(f"🟢 [{call_sid}] Received WebSocket message")
                
                try:
                    # Parse the message as JSON
                    event = json.loads(message)
                    event_type = event.get("type", "unknown")
                    
                    # Log the event (with different log levels based on type)
                    if event_type in ["error", "session.error"]:
                        logger.critical(f"🔴 [{call_sid}] RECEIVED ERROR EVENT FROM OPENAI: {json.dumps(event)}")
                        print(f"\n!!! DEBUG: RECEIVED ERROR EVENT: {json.dumps(event)}", flush=True)
                        
                        # Check for specific error types that should trigger a clean shutdown
                        if "error" in event:
                            error_info = event.get("error", {})
                            error_code = error_info.get("code", "")
                            
                            if error_code == "invalid_api_key":
                                logger.critical(f"🔴 [{call_sid}] INVALID API KEY ERROR FROM OPENAI - Signaling stop and will close connection.")
                                self.is_processing_loop_active = False
                                
                                # Don't call self.close_connection() directly from here
                                # Let the loop exit cleanly and handle the cleanup in finally
                                # Breaking here ensures we don't try to process more messages
                                break
                            
                    elif event_type == "session.update":
                        status = event.get("status", "unknown")
                        if status == "error":
                            logger.critical(f"🔴 [{call_sid}] SESSION UPDATE ERROR: {json.dumps(event)}")
                            print(f"\n!!! DEBUG: SESSION UPDATE ERROR: {json.dumps(event)}", flush=True)
                        else:
                            logger.critical(f"🟢 [{call_sid}] SESSION UPDATE SUCCESS: {status}")
                            print(f"\n!!! DEBUG: SESSION UPDATE SUCCESS: {status}", flush=True)
                    elif event_type == "transcript.final":
                        # Extract the transcript text from the correct location in the structure
                        # The transcript.final event has this structure: {"type": "transcript.final", "text": "..."}
                        # But it might also be {"type": "transcript.final", "data": {"text": "..."}}
                        transcript_text = event.get("text", "")
                        if not transcript_text and "data" in event:
                            transcript_text = event.get("data", {}).get("text", "")
                        
                        logger.critical(f"🟢 [{call_sid}] RECEIVED TRANSCRIPT: {transcript_text}")
                        print(f"\n!!! DEBUG: RECEIVED TRANSCRIPT: {transcript_text}", flush=True)
                    elif event_type.startswith("response.audio"):
                        logger.debug(f"[{call_sid}] Received audio event: {event_type}")
                    elif event_type == "tool_calls":
                        logger.info(f"[{call_sid}] Received tool calls event")
                        logger.debug(f"[{call_sid}] Tool calls details: {json.dumps(event)}")
                    else:
                        logger.info(f"[{call_sid}] Received event: {event_type}")
                        logger.debug(f"[{call_sid}] Event details: {json.dumps(event)}")
                    
                    # Process the event
                    if self.event_processor:
                        await self.event_processor.process_event(event)
                    else:
                        logger.warning(f"[{call_sid}] No event processor available to process event: {event_type}")
                    
                except json.JSONDecodeError as e:
                    logger.critical(f"🔴 [{call_sid}] ERROR DECODING JSON: {e}")
                    logger.critical(f"🔴 [{call_sid}] Raw message: {message}")
                    print(f"\n!!! DEBUG: ERROR DECODING JSON: {e}", flush=True)
                except Exception as e:
                    logger.critical(f"🔴 [{call_sid}] ERROR PROCESSING EVENT: {e}")
                    logger.critical(traceback.format_exc())
                    print(f"\n!!! DEBUG: ERROR PROCESSING EVENT: {e}", flush=True)
                    print(f"\n!!! DEBUG: {traceback.format_exc()}", flush=True)
        except websockets.exceptions.ConnectionClosedOK as e:
            # Normal closure - log at info level
            logger.info(f"[{call_sid}] WebSocket CONNECTION CLOSED NORMALLY: code={e.code}, reason={e.reason}")
            print(f"\n!!! DEBUG: WebSocket CONNECTION CLOSED NORMALLY: code={e.code}, reason={e.reason}", flush=True)
            if self.event_processor and hasattr(self.event_processor, 'on_close'):
                await self.event_processor.on_close({"code": e.code, "reason": e.reason, "call_sid": call_sid})
        except websockets.exceptions.ConnectionClosedError as e:
            # Abnormal closure - log at critical level
            logger.critical(f"🔴 [{call_sid}] WebSocket CONNECTION CLOSED WITH ERROR: code={e.code}, reason={e.reason}")
            print(f"\n!!! DEBUG: WebSocket CONNECTION CLOSED WITH ERROR: code={e.code}, reason={e.reason}", flush=True)
            if self.event_processor and hasattr(self.event_processor, 'on_close'):
                await self.event_processor.on_close({"code": e.code, "reason": e.reason, "call_sid": call_sid})
        except asyncio.CancelledError:
            logger.info(f"[{call_sid}] OpenAI WebSocket task cancelled.")
            # Connection might still be open if cancelled externally, ensure it's closed
            if self.websocket and self.websocket.open:
                try:
                    await self.websocket.close(code=1001, reason="Task cancelled")
                except Exception as e:
                    logger.error(f"[{call_sid}] Error closing WebSocket after task cancellation: {e}")
            
            if self.event_processor and hasattr(self.event_processor, 'on_close'):
                await self.event_processor.on_close({"code": 1000, "reason": "Task cancelled", "call_sid": call_sid})
        except Exception as e:
            logger.critical(f"🔴 [{call_sid}] ERROR IN PROCESS_MESSAGES: {e}")
            logger.critical(traceback.format_exc())
            print(f"\n!!! DEBUG: ERROR IN PROCESS_MESSAGES: {e}", flush=True)
            
            # Specifically catch and log the recv() error
            if isinstance(e, RuntimeError) and "cannot call recv while another coroutine is already waiting" in str(e):
                logger.critical(f"🔴 [{call_sid}] DETECTED MULTIPLE RECV CALLS ERROR. This indicates a problem with the websockets library handling. The event loop will be terminated.")
            
            if self.event_processor and hasattr(self.event_processor, 'on_close'):
                await self.event_processor.on_close({"code": 1011, "reason": str(e), "call_sid": call_sid})
            
            # Try to close the WebSocket if it's still open
            if self.websocket and getattr(self.websocket, 'open', False):
                try:
                    await self.websocket.close(code=1011, reason=f"Error: {str(e)[:50]}")
                except Exception as close_error:
                    logger.error(f"[{call_sid}] Error closing WebSocket after exception: {close_error}")
                    
        finally:
            logger.critical(f"🔴 [{call_sid}] EVENT PROCESSING STOPPED - was_connected={self.connected}, is_processing_loop_active={self.is_processing_loop_active}")
            print(f"\n!!! DEBUG: EVENT PROCESSING STOPPED - Connection may have been lost", flush=True)
            self.running = False
            self.connected = False
            self.is_processing_loop_active = False
            logger.info(f"[{call_sid}] OpenAIRealtimeClient: Cleaned up from process_messages.")
    
    async def send_audio(self, audio_data: bytes):
        """
        Send audio data to the OpenAI Realtime API.
        
        Args:
            audio_data: The audio data to send
        """
        if not self.connected:
            logger.warning("Not connected to OpenAI Realtime API, cannot send audio")
            return
        
        call_sid = getattr(self, 'session_id', 'UNKNOWN_CALL')
        
        try:
            # Encode the audio as base64
            base64_audio = base64.b64encode(audio_data).decode("utf-8")
            
            # Create proper payload format according to OpenAI documentation
            # https://platform.openai.com/docs/guides/realtime-conversations
            audio_payload = {
                "type": "input_audio_buffer.append",
                "input_audio_buffer": {
                    "payload": base64_audio,
                    "end_of_stream": False
                }
            }
            
            # Send the audio event
            await self.send_event(audio_payload)
            
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"[{call_sid}] Sent audio data ({len(audio_data)} bytes) to OpenAI")
                
        except Exception as e:
            logger.error(f"[{call_sid}] Error sending audio: {e}")
            logger.error(traceback.format_exc())
    
    async def send_text_for_tts(self, text: str, response_id: Optional[str] = None):
        """
        Send text to be converted to speech (TTS).
        
        Args:
            text: The text to convert to speech
            response_id: Optional unique ID for the response
        """
        if not self.connected:
            logger.warning("Not connected to OpenAI Realtime API, cannot send text for TTS")
            return
        
        call_sid = getattr(self, 'session_id', 'UNKNOWN_CALL')
        
        # Generate a response ID if not provided
        if not response_id:
            response_id = str(uuid.uuid4())
        
        try:
            # First, create a conversation item with the text (to provide context)
            conversation_item = {
                "type": "conversation.item.create",
                "conversationItem": {
                    "role": "assistant",
                    "content": text
                }
            }
            
            logger.debug(f"[{call_sid}] Sending conversation.item.create: {json.dumps(conversation_item)}")
            await self.send_event(conversation_item)
            
            # Then, create a response with the text to be spoken
            # This follows the OpenAI Realtime API documentation format
            # https://platform.openai.com/docs/guides/realtime-conversations
            response_create = {
                "type": "response.create",
                "response_id": response_id,
                "response": {
                    "text": text,  # Include text explicitly as per the docs
                    "responder": {"type": "model"},  # Uses the voice from session config
                    "end_of_response": True,
                    "modalities": ["audio"]  # Request audio output
                }
            }
            
            logger.debug(f"[{call_sid}] Sending response.create: {json.dumps(response_create)}")
            await self.send_event(response_create)
            
            logger.info(f"[{call_sid}] Sent text for TTS: \"{text}\" with response_id: {response_id}")
            return response_id
            
        except Exception as e:
            logger.error(f"[{call_sid}] Error sending text for TTS: {e}")
            logger.error(traceback.format_exc())
            raise
            
    async def request_response(self, text: str, response_id: Optional[str] = None):
        """
        Requests OpenAI to generate TTS for the given text.
        Primary method used by handlers to request voice responses.
        
        Args:
            text: The text to convert to speech
            response_id: Optional unique ID for the response
        
        Returns:
            The response_id for tracking audio events from OpenAI
        """
        call_sid = getattr(self, 'session_id', 'UNKNOWN_CALL')
        logger.critical(f"🔄 [{call_sid}] request_response CALLED for text: \"{text}\"")
        
        # Verify connection state first
        if not self.connected or not self.websocket:
            logger.critical(f"🔴 [{call_sid}] Cannot request_response - WebSocket not connected! Text: \"{text}\"")
            raise RuntimeError(f"Cannot request TTS response - WebSocket not connected to OpenAI")
        
        # Check if websocket is open
        is_open = getattr(self.websocket, 'open', False)
        if not is_open:
            logger.critical(f"🔴 [{call_sid}] Cannot request_response - WebSocket closed! Text: \"{text}\"")
            raise RuntimeError(f"Cannot request TTS response - WebSocket connection is closed")
            
        logger.critical(f"🟢 [{call_sid}] Sending TTS request for text: \"{text}\"")
        
        try:
            # Call the actual implementation with proper response_id tracking
            response_id = await self.send_text_for_tts(text, response_id)
            logger.critical(f"🟢 [{call_sid}] Successfully sent TTS request for text: \"{text}\" (response_id: {response_id})")
            return response_id
        except Exception as e:
            logger.critical(f"🔴 [{call_sid}] EXCEPTION in request_response: {str(e)}")
            logger.critical(traceback.format_exc())
            raise
    
    async def send_tool_response(self, tool_id: str, result: Dict[str, Any], response_id: Optional[str] = None):
        """
        Send a tool response to the OpenAI Realtime API.
        
        Args:
            tool_id: The ID of the tool call
            result: The result to send
            response_id: Optional unique ID for the response
        
        Returns:
            The response_id for tracking response events from OpenAI
        """
        if not self.connected:
            logger.warning("Not connected to OpenAI Realtime API, cannot send tool response")
            return
        
        call_sid = getattr(self, 'session_id', 'UNKNOWN_CALL')
        
        # Generate a response ID if not provided
        if not response_id:
            response_id = str(uuid.uuid4())
        
        try:
            # Convert result to JSON string if it's not already
            result_content = json.dumps(result) if not isinstance(result, str) else result
            
            # Create a conversation item with the tool output
            # This follows the OpenAI Realtime API documentation format
            conversation_item = {
                "type": "conversation.item.create",
                "conversationItem": {
                    "role": "function_call_output",
                    "content": result_content,
                    "id": tool_id
                }
            }
            
            logger.debug(f"[{call_sid}] Sending function_call_output: {json.dumps(conversation_item)}")
            await self.send_event(conversation_item)
            
            # Generate a response that includes both text and audio modalities
            response_create = {
                "type": "response.create",
                "response_id": response_id,
                "response": {
                    "responder": {"type": "model"},
                    "end_of_response": True,
                    "modalities": ["text", "audio"]
                }
            }
            
            logger.debug(f"[{call_sid}] Sending response.create after tool: {json.dumps(response_create)}")
            await self.send_event(response_create)
            
            logger.info(f"[{call_sid}] Sent tool response for tool ID: {tool_id} with response_id: {response_id}")
            return response_id
        except Exception as e:
            logger.error(f"[{call_sid}] Error sending tool response: {e}")
            logger.error(traceback.format_exc())
            raise
    
    async def close(self):
        """Close the connection to the OpenAI Realtime API."""
        call_sid = getattr(self, 'session_id', 'UNKNOWN_CALL')
        logger.info(f"[{call_sid}] Closing OpenAI Realtime client")
        
        # Signal the processing loop to stop FIRST
        self.running = False
        self.is_processing_loop_active = False
        logger.info(f"[{call_sid}] Signaled processing loop to stop: is_processing_loop_active={self.is_processing_loop_active}")
        
        # Give the loop a chance to exit gracefully (with a short timeout)
        if self._event_processing_task and not self._event_processing_task.done():
            logger.info(f"[{call_sid}] Waiting briefly for event processing task to exit gracefully")
            try:
                # Wait a short time for the loop to exit gracefully
                await asyncio.wait_for(asyncio.shield(self._event_processing_task), timeout=0.5)
                logger.info(f"[{call_sid}] Event processing task exited gracefully")
            except asyncio.TimeoutError:
                # If it doesn't exit within the timeout, cancel it
                logger.info(f"[{call_sid}] Graceful exit timed out, cancelling event processing task")
                self._event_processing_task.cancel()
                try:
                    await asyncio.wait_for(self._event_processing_task, timeout=1.0)
                    logger.info(f"[{call_sid}] Event processing task successfully cancelled during close")
                except asyncio.CancelledError:
                    logger.info(f"[{call_sid}] Event processing task successfully cancelled during close")
                except asyncio.TimeoutError:
                    logger.warning(f"[{call_sid}] Timeout waiting for event processing task to cancel during close")
                except Exception as e:
                    logger.error(f"[{call_sid}] Error awaiting cancelled event task: {e}")
                    logger.error(traceback.format_exc())
            except Exception as e:
                logger.error(f"[{call_sid}] Error while waiting for task to complete: {e}")
                logger.error(traceback.format_exc())
        
        # Clear the task reference to prevent memory leaks
        self._event_processing_task = None
        
        # Now close the WebSocket connection
        if self.websocket:
            try:
                is_open = getattr(self.websocket, 'open', False)
                if is_open:
                    logger.info(f"[{call_sid}] Closing WebSocket connection with code 1000")
                    await self.websocket.close(1000, "Closing connection normally")
                else:
                    logger.info(f"[{call_sid}] WebSocket already closed")
            except Exception as e:
                logger.error(f"[{call_sid}] Error closing WebSocket: {e}")
                logger.error(traceback.format_exc())
        
        self.connected = False
        logger.info(f"[{call_sid}] OpenAI Realtime client connection resources explicitly released")
    
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