"""
Enhanced async OpenAI Realtime Client for RedBarSushiAI with improved debugging.

This module provides an enhanced async client for interacting with OpenAI's Realtime API,
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
from websockets.exceptions import ConnectionClosed, ConnectionClosedError, InvalidStatusCode

from app.config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Ensure the logs directory exists
log_dir = os.path.join(os.getcwd(), 'logs')
os.makedirs(log_dir, exist_ok=True)

# Add a file handler for this module
file_handler = logging.FileHandler(os.path.join(log_dir, 'realtime_audio.log'))
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.info("======= ENHANCED ASYNC REALTIME AUDIO CLIENT LOGGING INITIALIZED =======")

@dataclass
class RealtimeConfig:
    """Configuration for the OpenAI Realtime API."""
    
    model: str = "gpt-4o-realtime-preview-2024-10-01"
    instructions: Optional[str] = None
    voice: str = "shimmer"
    voice_id: str = "shimmer"  # Alias for voice to ensure compatibility
    sample_rate_hz: int = 8000
    input_audio_format_container: str = "mulaw"
    input_audio_format_encoding: str = "mulaw"
    input_audio_format_sample_rate: int = 8000
    output_audio_format: str = "mulaw"
    vad_enabled: bool = True
    vad_silence_threshold_ms: int = 1000
    vad_speech_threshold_ms: int = 8000
    max_tokens: Optional[int] = None
    vad_config: Optional[Dict[str, Any]] = None
    tts_speed: float = 1.0
    buffer_ms: Optional[int] = None
    response_expected: bool = True
    stream_priority: Optional[str] = "high"
    interrupt_types: Optional[List[str]] = None
    language: str = "en"
    connection_timeout: float = 15.0  # Connection timeout in seconds
    ping_interval: Optional[float] = 30.0  # WebSocket ping interval in seconds


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
        logger.info(f"[{self.client.call_sid}] RealtimeEventProcessor initialized")
    
    def register_handler(self, event_type: str, handler: Callable):
        """
        Register a handler for an event type.
        
        Args:
            event_type: The event type to handle
            handler: The handler function
        """
        self.handlers[event_type] = handler
        logger.debug(f"[{self.client.call_sid}] Registered handler for event type: {event_type}")
    
    def register_default_handlers(self):
        """Register default handlers for common event types."""
        self.register_handler("transcript.final", self._handle_transcript)
        self.register_handler("response.audio.delta", self._handle_audio_delta)
        self.register_handler("tool_call", self._handle_tool_call)
        self.register_handler("input_audio_buffer.speech_started", self._handle_speech_started)
        self.register_handler("input_audio_buffer.speech_stopped", self._handle_speech_stopped)
        self.register_handler("error", self._handle_error)
        self.register_handler("session.error", self._handle_session_error)
        self.register_handler("session.created", self._handle_session_created)
        logger.info(f"[{self.client.call_sid}] Registered default event handlers")
    
    async def process_event(self, event: Dict[str, Any]):
        """
        Process an event from the OpenAI Realtime API.
        
        Args:
            event: The event to process
        """
        event_type = event.get("type", "unknown")
        
        if event_type in self.handlers:
            logger.debug(f"[{self.client.call_sid}] Processing event: {event_type}")
            await self.handlers[event_type](event)
        else:
            logger.debug(f"[{self.client.call_sid}] No handler for event type: {event_type}")
    
    async def _handle_transcript(self, event: Dict[str, Any]):
        """
        Handle a transcript.final event.
        
        Args:
            event: The transcript event
        """
        transcript = event.get("transcript", "")
        logger.info(f"[{self.client.call_sid}] Transcript: {transcript}")
        
        if self.client.transcript_callback:
            try:
                await self.client.transcript_callback(transcript)
            except Exception as e:
                logger.error(f"[{self.client.call_sid}] Error in transcript callback: {e}", exc_info=True)
    
    async def _handle_audio_delta(self, event: Dict[str, Any]):
        """
        Handle a response.audio.delta event.
        
        Args:
            event: The audio delta event
        """
        audio_data = event.get("delta", "")
        logger.debug(f"[{self.client.call_sid}] Received audio delta, length: {len(audio_data) if audio_data else 0} chars")
        
        if self.client.audio_callback:
            try:
                # The audio data is base64-encoded
                audio_bytes = base64.b64decode(audio_data)
                await self.client.audio_callback(audio_bytes)
            except Exception as e:
                logger.error(f"[{self.client.call_sid}] Error in audio callback: {e}", exc_info=True)
    
    async def _handle_tool_call(self, event: Dict[str, Any]):
        """
        Handle a tool_call event.
        
        Args:
            event: The tool call event
        """
        tool_name = event.get("name", "")
        arguments = event.get("arguments", {})
        tool_id = event.get("id", "")
        
        logger.info(f"[{self.client.call_sid}] Tool call: {tool_name} with ID {tool_id}")
        logger.debug(f"[{self.client.call_sid}] Tool arguments: {json.dumps(arguments)}")
        
        if self.client.tool_call_callback:
            try:
                result = await self.client.tool_call_callback(tool_name, arguments, tool_id)
                
                # Send the tool response back
                await self.client.send_tool_response(tool_id, result)
            except Exception as e:
                logger.error(f"[{self.client.call_sid}] Error in tool call callback: {e}", exc_info=True)
                
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
        logger.info(f"[{self.client.call_sid}] Speech started event")
        
        if self.client.speech_started_callback:
            try:
                await self.client.speech_started_callback()
            except Exception as e:
                logger.error(f"[{self.client.call_sid}] Error in speech started callback: {e}", exc_info=True)
    
    async def _handle_speech_stopped(self, event: Dict[str, Any]):
        """
        Handle an input_audio_buffer.speech_stopped event.
        
        Args:
            event: The speech stopped event
        """
        logger.info(f"[{self.client.call_sid}] Speech stopped event")
        
        if self.client.speech_stopped_callback:
            try:
                await self.client.speech_stopped_callback()
            except Exception as e:
                logger.error(f"[{self.client.call_sid}] Error in speech stopped callback: {e}", exc_info=True)
    
    async def _handle_error(self, event: Dict[str, Any]):
        """
        Handle an error event.
        
        Args:
            event: The error event
        """
        error_message = event.get("message", "Unknown error")
        logger.error(f"[{self.client.call_sid}] Error event: {error_message}")
        
        if self.client.error_callback:
            try:
                await self.client.error_callback(error_message)
            except Exception as e:
                logger.error(f"[{self.client.call_sid}] Error in error callback: {e}", exc_info=True)

    async def _handle_session_error(self, event: Dict[str, Any]):
        """
        Handle a session.error event.
        
        Args:
            event: The session error event
        """
        error_message = event.get("message", "Unknown session error")
        error_code = event.get("code", "unknown")
        logger.error(f"[{self.client.call_sid}] Session error: {error_code} - {error_message}")
        
        if self.client.error_callback:
            try:
                await self.client.error_callback(f"Session error {error_code}: {error_message}")
            except Exception as e:
                logger.error(f"[{self.client.call_sid}] Error in session error callback: {e}", exc_info=True)

    async def _handle_session_created(self, event: Dict[str, Any]):
        """
        Handle a session.created event.
        
        Args:
            event: The session created event
        """
        session_id = event.get("session", {}).get("id")
        logger.info(f"[{self.client.call_sid}] Session created with ID: {session_id}")
        
        # You can store the session ID and other session details here if needed
        self.client.session_id = session_id
        
        # No callback for this event currently, but you could add one if needed

    async def on_open(self, data: Dict[str, Any]):
        """
        Handle WebSocket connection opened event.
        
        Args:
            data: Event data
        """
        logger.info(f"[{self.client.call_sid}] WebSocket connection opened")
        
    async def on_close(self, data: Dict[str, Any]):
        """
        Handle WebSocket connection closed event.
        
        Args:
            data: Event data with code and reason
        """
        code = data.get("code", "unknown")
        reason = data.get("reason", "unknown")
        logger.info(f"[{self.client.call_sid}] WebSocket connection closed: code={code}, reason={reason}")
        
    async def on_error(self, data: Dict[str, Any]):
        """
        Handle WebSocket error event.
        
        Args:
            data: Error data
        """
        error = data.get("error", "Unknown error")
        details = data.get("details", "")
        logger.error(f"[{self.client.call_sid}] WebSocket error: {error}, details: {details}")
        
        if self.client.error_callback:
            try:
                await self.client.error_callback(f"WebSocket error: {error}")
            except Exception as e:
                logger.error(f"[{self.client.call_sid}] Error in WebSocket error callback: {e}", exc_info=True)


class OpenAIRealtimeClient:
    """
    Async client for the OpenAI Realtime API, supporting WebSocket communication
    for real-time audio streaming, transcription, and TTS.
    """
    
    # OpenAI Realtime API endpoint
    WEBSOCKET_URL = "wss://api.openai.com/v1/realtime"
    
    def __init__(
        self,
        call_sid: str,
        config: RealtimeConfig,
        api_key: Optional[str] = None
    ):
        """
        Initialize the OpenAI Realtime client.
        
        Args:
            call_sid: The call SID or session ID
            config: The Realtime configuration
            api_key: The OpenAI API key (defaults to settings.OPENAI_API_KEY)
        """
        self.call_sid = call_sid
        self.config = config
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.session_id = None
        
        self.websocket = None
        self.event_processor = RealtimeEventProcessor(self)
        self.is_connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 3
        self.model_is_speaking = False
        
        # Callbacks
        self.transcript_callback = None
        self.audio_callback = None
        self.tool_call_callback = None
        self.speech_started_callback = None
        self.speech_stopped_callback = None
        self.error_callback = None
        
        logger.info(f"[{self.call_sid}] OpenAIRealtimeClient instance created")
    
    async def connect(self) -> bool:
        """
        Connect to the OpenAI Realtime API.
        
        Returns:
            True if connection is successful, False otherwise
        """
        logger.info(f"[{self.call_sid}] Attempting to connect to OpenAI Realtime API at {self.WEBSOCKET_URL}...")
        
        if not self.api_key:
            logger.error(f"[{self.call_sid}] OPENAI_API_KEY is not configured. Cannot connect to OpenAI Realtime API.")
            await self.event_processor.on_error({"error": "OpenAI API Key not configured", "call_sid": self.call_sid})
            return False

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "OpenAI-Beta": "realtime=v1"
        }
        
        # Construct URL with parameters
        params = {
            "model": self.config.model,
            "voice": self.config.voice_id,
            "language": self.config.language,
        }
        connect_url = f"{self.WEBSOCKET_URL}?{'&'.join([f'{k}={v}' for k, v in params.items() if v is not None])}"
        logger.debug(f"[{self.call_sid}] Connecting with URL: {connect_url} and headers: {list(headers.keys())}")
        
        try:
            # Add timeout for connection attempt
            self.websocket = await asyncio.wait_for(
                websockets.connect(connect_url, extra_headers=headers, ping_interval=self.config.ping_interval),
                timeout=self.config.connection_timeout
            )
            self.is_connected = True
            self.reconnect_attempts = 0
            logger.info(f"[{self.call_sid}] Successfully connected to OpenAI Realtime API")
            
            # Send session configuration
            await self._send_session_config()
            
            await self.event_processor.on_open({"call_sid": self.call_sid})
            return True
        except InvalidStatusCode as e:
            logger.error(f"[{self.call_sid}] Failed to connect to OpenAI: Invalid status code {e.status_code}. Response body: {getattr(e, 'response_body', 'N/A')}", exc_info=True)
            if e.status_code == 401:
                logger.error(f"[{self.call_sid}] Authentication failed (401). Check your OPENAI_API_KEY.")
            await self.event_processor.on_error({"error": f"OpenAI connection failed: Status {e.status_code}", "details": str(e), "call_sid": self.call_sid})
        except asyncio.TimeoutError:
            logger.error(f"[{self.call_sid}] Timeout connecting to OpenAI Realtime API", exc_info=True)
            await self.event_processor.on_error({"error": "OpenAI connection timeout", "call_sid": self.call_sid})
        except Exception as e:
            logger.error(f"[{self.call_sid}] Failed to connect to OpenAI Realtime API: {type(e).__name__} - {e}", exc_info=True)
            await self.event_processor.on_error({"error": f"OpenAI connection error: {type(e).__name__}", "details": str(e), "call_sid": self.call_sid})
        
        self.is_connected = False
        return False
    
    async def _send_session_config(self):
        """Configure the OpenAI Realtime session."""
        if not self.websocket or not self.is_connected:
            logger.warning(f"[{self.call_sid}] Cannot send session config, WebSocket not connected")
            return
        
        # Prepare VAD configuration
        vad_config = self.config.vad_config
        if not vad_config and self.config.vad_enabled:
            vad_config = {
                "mode": "server",
                "silence_threshold_ms": self.config.vad_silence_threshold_ms,
                "speech_threshold_ms": self.config.vad_speech_threshold_ms
            }
        
        # Prepare session configuration
        session_config = {
            "type": "session.update",
            "session": {
                "stream_priority": self.config.stream_priority,
                "interrupt_types": self.config.interrupt_types,
                "language": self.config.language,
                "input_audio_format": {
                    "container": self.config.input_audio_format_container,
                    "encoding": self.config.input_audio_format_encoding,
                    "sample_rate": self.config.input_audio_format_sample_rate,
                },
                "output_audio_format": {
                    "container": "mulaw",
                    "encoding": "pcm_mulaw",
                    "sample_rate": 8000,
                },
                "vad": vad_config,
                "model": self.config.model,
                "voice": self.config.voice_id,
                "speed": self.config.tts_speed,
                "buffer_ms": self.config.buffer_ms,
                "response_expected": self.config.response_expected,
            }
        }
        
        # Add instructions if provided
        if self.config.instructions:
            session_config["session"]["instructions"] = self.config.instructions
        
        # Filter out None values from the session config
        session_config["session"] = {k: v for k, v in session_config["session"].items() if v is not None}
        if "vad" in session_config["session"] and session_config["session"]["vad"] is None:
            del session_config["session"]["vad"]
        
        logger.info(f"[{self.call_sid}] Sending OpenAI session configuration: {json.dumps(session_config, indent=2)}")
        await self.send_json(session_config)
    
    async def send_json(self, data: Dict[str, Any]):
        """
        Send JSON data to the OpenAI Realtime API.
        
        Args:
            data: The JSON data to send
        """
        if self.websocket and self.is_connected:
            try:
                message_str = json.dumps(data)
                logger.debug(f"[{self.call_sid}] Sending JSON to OpenAI: {message_str[:500]}{'...' if len(message_str) > 500 else ''}")
                await self.websocket.send(message_str)
            except ConnectionClosed:
                logger.warning(f"[{self.call_sid}] OpenAI WebSocket connection closed while trying to send JSON")
                self.is_connected = False
                await self.event_processor.on_close({"code": "N/A", "reason": "Connection closed during send", "call_sid": self.call_sid})
            except Exception as e:
                logger.error(f"[{self.call_sid}] Error sending JSON to OpenAI: {e}", exc_info=True)
        else:
            logger.warning(f"[{self.call_sid}] Cannot send JSON, OpenAI WebSocket not connected. Data type: {data.get('type', 'unknown')}")
    
    async def send_audio_chunk(self, audio_chunk: bytes):
        """
        Send an audio chunk to the OpenAI Realtime API.
        
        Args:
            audio_chunk: The audio chunk to send
        """
        if self.websocket and self.is_connected:
            try:
                logger.debug(f"[{self.call_sid}] Sending audio chunk to OpenAI, size: {len(audio_chunk)} bytes")
                # Send as input_audio_buffer.append
                payload = {
                    "type": "input_audio_buffer.append",
                    "input_audio_buffer": {
                        "payload": base64.b64encode(audio_chunk).decode("utf-8")
                    }
                }
                await self.send_json(payload)
            except Exception as e:
                logger.error(f"[{self.call_sid}] Error sending audio chunk to OpenAI: {e}", exc_info=True)
        else:
            logger.warning(f"[{self.call_sid}] Cannot send audio chunk, OpenAI WebSocket not connected")
    
    async def process_messages(self):
        """
        Process messages from the OpenAI Realtime API.
        This runs as a background task while the client is connected.
        """
        if not self.websocket or not self.is_connected:
            logger.error(f"[{self.call_sid}] Cannot process messages, OpenAI WebSocket not connected")
            return
        
        logger.info(f"[{self.call_sid}] Starting to process messages from OpenAI Realtime API")
        
        try:
            async for message_str in self.websocket:
                try:
                    # Parse the message as JSON
                    event = json.loads(message_str)
                    event_type = event.get("type", "unknown")
                    
                    # Log the event (with different log levels based on type)
                    if event_type in ["error", "session.error"]:
                        logger.error(f"[{self.call_sid}] Received error event: {json.dumps(event)}")
                    elif event_type.startswith("response.audio"):
                        logger.debug(f"[{self.call_sid}] Received audio event: {event_type}")
                    else:
                        logger.info(f"[{self.call_sid}] Received event: {event_type}")
                        logger.debug(f"[{self.call_sid}] Event details: {json.dumps(event)}")
                    
                    # Process the event
                    await self.event_processor.process_event(event)
                
                except json.JSONDecodeError:
                    logger.error(f"[{self.call_sid}] Error decoding JSON from OpenAI message: {message_str[:1000]}{'...' if len(message_str) > 1000 else ''}")
                except Exception as e:
                    logger.error(f"[{self.call_sid}] Error processing OpenAI message: {e}", exc_info=True)
        except ConnectionClosed as e:
            logger.info(f"[{self.call_sid}] OpenAI WebSocket connection closed normally: {e}")
            await self.event_processor.on_close({"code": str(e.code) if hasattr(e, 'code') else "1000", "reason": str(e.reason) if hasattr(e, 'reason') else "normal", "call_sid": self.call_sid})
        except ConnectionClosedError as e:
            logger.warning(f"[{self.call_sid}] OpenAI WebSocket connection closed with error: Code {e.code}, Reason: {e.reason}", exc_info=True)
            await self.event_processor.on_close({"code": str(e.code), "reason": str(e.reason), "call_sid": self.call_sid})
        except Exception as e:
            logger.critical(f"[{self.call_sid}] Critical error in OpenAI message processing loop: {type(e).__name__} - {e}", exc_info=True)
            await self.event_processor.on_error({"error": f"Critical error in message processing: {type(e).__name__}", "details": str(e), "call_sid": self.call_sid})
        finally:
            logger.info(f"[{self.call_sid}] Exited OpenAI message processing loop")
            self.is_connected = False
            # Ensure on_close is called if not already handled
            await self.event_processor.on_close({"code": "N/A", "reason": "Processing loop ended", "call_sid": self.call_sid})
    
    async def request_response(self, text: str, response_id: Optional[str] = None):
        """
        Request a response from the OpenAI Realtime API.
        This is used to generate TTS audio for a text prompt.
        
        Args:
            text: The text to generate a response for
            response_id: Optional response ID
        """
        if not self.websocket or not self.is_connected:
            logger.warning(f"[{self.call_sid}] Cannot request response from OpenAI, WebSocket not connected")
            return
        
        try:
            # Step 1: Create conversation item
            conversation_item = {
                "type": "conversation.item.create",
                "conversation.item": {
                    "type": "assistant.turn.started",
                }
            }
            logger.info(f"[{self.call_sid}] Creating conversation item for TTS: {json.dumps(conversation_item)}")
            await self.send_json(conversation_item)
            
            # Step 2: Create response
            response = {
                "type": "response.create",
                "response": {
                    "responder": {
                        "type": "model",
                        "model": {
                            "instructions": text
                        }
                    }
                }
            }
            
            # Add response_id if provided
            if response_id:
                response["response"]["response_id"] = response_id
            
            logger.info(f"[{self.call_sid}] Requesting OpenAI TTS response for text: '{text[:100]}{'...' if len(text) > 100 else ''}'")
            await self.send_json(response)
        except Exception as e:
            logger.error(f"[{self.call_sid}] Error requesting response from OpenAI: {e}", exc_info=True)
    
    async def send_tool_response(self, tool_id: str, result: Dict[str, Any]):
        """
        Send a tool response to the OpenAI Realtime API.
        
        Args:
            tool_id: The ID of the tool call
            result: The result to send
        """
        if not self.websocket or not self.is_connected:
            logger.warning(f"[{self.call_sid}] Cannot send tool response to OpenAI, WebSocket not connected")
            return
        
        try:
            # Create conversation item with tool output
            tool_output = {
                "type": "conversation.item.create",
                "conversation.item": {
                    "type": "function_call_output",
                    "function_call_output": {
                        "content": json.dumps(result),
                        "id": tool_id
                    }
                }
            }
            logger.info(f"[{self.call_sid}] Sending tool response for tool ID: {tool_id}")
            logger.debug(f"[{self.call_sid}] Tool response content: {json.dumps(result)}")
            await self.send_json(tool_output)
            
            # Request a response
            await self.send_json({
                "type": "response.create",
                "response": {}
            })
        except Exception as e:
            logger.error(f"[{self.call_sid}] Error sending tool response to OpenAI: {e}", exc_info=True)
    
    async def close(self):
        """Close the connection to the OpenAI Realtime API."""
        logger.info(f"[{self.call_sid}] Closing OpenAI Realtime client connection")
        
        self.is_connected = False
        
        if self.websocket:
            try:
                await self.websocket.close(code=1000, reason="Closing connection")
                self.websocket = None
                logger.info(f"[{self.call_sid}] OpenAI WebSocket connection closed")
            except Exception as e:
                logger.error(f"[{self.call_sid}] Error closing OpenAI WebSocket connection: {e}", exc_info=True)
                self.websocket = None
        else:
            logger.info(f"[{self.call_sid}] OpenAI WebSocket already closed or not connected")
        
        logger.info(f"[{self.call_sid}] OpenAI Realtime client closed")
    
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
            logger.debug(f"[{self.call_sid}] Registered transcript callback")
        
        if audio_callback:
            self.audio_callback = audio_callback
            logger.debug(f"[{self.call_sid}] Registered audio callback")
        
        if tool_call_callback:
            self.tool_call_callback = tool_call_callback
            logger.debug(f"[{self.call_sid}] Registered tool call callback")
        
        if speech_started_callback:
            self.speech_started_callback = speech_started_callback
            logger.debug(f"[{self.call_sid}] Registered speech started callback")
        
        if speech_stopped_callback:
            self.speech_stopped_callback = speech_stopped_callback
            logger.debug(f"[{self.call_sid}] Registered speech stopped callback")
        
        if error_callback:
            self.error_callback = error_callback
            logger.debug(f"[{self.call_sid}] Registered error callback")


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
            voice_id="shimmer",
            sample_rate_hz=8000,
            input_audio_format_container="mulaw",
            input_audio_format_encoding="mulaw",
            input_audio_format_sample_rate=8000,
            output_audio_format="mulaw",
            vad_enabled=True,
            vad_silence_threshold_ms=1000,
            vad_speech_threshold_ms=8000,
        )
        
        logger.info("RealtimeClientManager initialized")
    
    async def create_client(
        self,
        call_sid: str,
        config: Optional[RealtimeConfig] = None,
        api_key: Optional[str] = None,
        connect_immediately: bool = False
    ) -> OpenAIRealtimeClient:
        """
        Create a new OpenAI Realtime client.
        
        Args:
            call_sid: The call SID or session ID
            config: The Realtime configuration (defaults to self.default_config)
            api_key: The OpenAI API key (defaults to settings.OPENAI_API_KEY)
            connect_immediately: Whether to connect to OpenAI immediately
            
        Returns:
            The created client
        """
        # Use default config if not provided
        if not config:
            config = self.default_config
        
        # Create the client
        client = OpenAIRealtimeClient(
            call_sid=call_sid,
            api_key=api_key,
            config=config
        )
        
        # Store the client
        self.clients[call_sid] = client
        logger.info(f"Created OpenAI Realtime client for call SID: {call_sid}")
        
        # Connect to the API if requested
        if connect_immediately:
            is_connected = await client.connect()
            if is_connected:
                logger.info(f"OpenAI Realtime client for call SID {call_sid} connected successfully")
            else:
                logger.error(f"Failed to connect OpenAI Realtime client for call SID {call_sid}")
        
        return client
    
    def get_client(self, call_sid: str) -> Optional[OpenAIRealtimeClient]:
        """
        Get an existing OpenAI Realtime client.
        
        Args:
            call_sid: The call SID or session ID
            
        Returns:
            The client if found, None otherwise
        """
        client = self.clients.get(call_sid)
        if client:
            logger.debug(f"Retrieved OpenAI Realtime client for call SID: {call_sid}")
        else:
            logger.warning(f"OpenAI Realtime client not found for call SID: {call_sid}")
        return client
    
    async def close_client(self, call_sid: str) -> bool:
        """
        Close and remove an OpenAI Realtime client.
        
        Args:
            call_sid: The call SID or session ID
            
        Returns:
            True if the client was closed, False otherwise
        """
        client = self.clients.get(call_sid)
        
        if client:
            logger.info(f"Closing OpenAI Realtime client for call SID: {call_sid}")
            await client.close()
            del self.clients[call_sid]
            return True
        
        logger.warning(f"Cannot close OpenAI Realtime client for call SID {call_sid} - client not found")
        return False
    
    async def close_all(self):
        """Close all OpenAI Realtime clients."""
        logger.info(f"Closing all OpenAI Realtime clients ({len(self.clients)} clients)")
        for call_sid, client in list(self.clients.items()):
            await client.close()
        
        self.clients.clear()
        logger.info("All OpenAI Realtime clients closed")


# Create a global instance of the client manager
realtime_client_manager = RealtimeClientManager()


# Export the enhanced client for use as a drop-in replacement
# Simply import from this module instead of app.utils.realtime_audio_async
OpenAIRealtimeClient
RealtimeClientManager
realtime_client_manager
RealtimeConfig