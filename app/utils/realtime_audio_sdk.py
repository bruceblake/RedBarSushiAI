# app/utils/realtime_audio_sdk.py
import os
import json
import asyncio
import logging
import uuid
import base64
import traceback
import time
from typing import Dict, Any, Optional, AsyncGenerator

# Import WebSocket libraries
import websockets

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Import OpenAI API key from agent_utils
from app.utils.agent_utils import OPENAI_API_KEY

# Audio format conversion utilities for Twilio integration
def ulaw_to_pcm(ulaw_data):
    """
    Convert μ-law encoded audio data to PCM format.
    
    Args:
        ulaw_data: μ-law encoded audio data (8kHz)
        
    Returns:
        PCM format audio data (16kHz)
    """
    import numpy as np
    from scipy.io import wavfile
    from scipy import signal
    
    # Convert to numpy array
    ulaw_array = np.frombuffer(ulaw_data, dtype=np.uint8)
    
    # μ-law decoding
    # Implement standard μ-law to linear PCM conversion
    # This is a standard audio engineering algorithm
    sign = np.ones_like(ulaw_array)
    sign[ulaw_array & 0x80 != 0] = -1
    exponent = ((ulaw_array & 0x70) >> 4)
    mantissa = ulaw_array & 0x0f
    sample = sign * (((mantissa + 16.5) * (2 ** exponent)) - 16.5)
    pcm_data = (sample / 128.0 * 32768).astype(np.int16)
    
    # Resample from 8kHz to 16kHz using scipy
    # Calculate the resampling ratio
    original_rate = 8000  # Twilio μ-law is 8kHz
    target_rate = 16000   # OpenAI expects 16kHz
    
    # Resample the audio
    resampled_pcm = signal.resample(pcm_data, int(len(pcm_data) * target_rate / original_rate))
    
    # Convert back to bytes
    return resampled_pcm.astype(np.int16).tobytes()

def pcm_to_ulaw(pcm_data):
    """
    Convert PCM audio data to μ-law format for Twilio.
    
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
    original_rate = 16000  # OpenAI output is 16kHz
    target_rate = 8000     # Twilio expects 8kHz
    
    # Resample the audio
    resampled_pcm = signal.resample(pcm_array, int(len(pcm_array) * target_rate / original_rate))
    
    # μ-law encoding
    # Normalize to values between -1 and 1
    normalized = resampled_pcm.astype(np.float32) / 32768.0
    
    # Apply μ-law compression
    # This is a standard audio engineering algorithm
    mu = 255  # μ-law parameter
    sign = np.sign(normalized)
    amplitude = np.minimum(np.abs(normalized), 1.0)
    compressed = sign * np.log(1 + mu * amplitude) / np.log(1 + mu)
    
    # Scale to 8 bits and convert to uint8
    ulaw_array = ((compressed + 1) * 127.5).astype(np.uint8)
    
    # Convert back to bytes
    return ulaw_array.tobytes()

class RealtimeSession:
    """Direct implementation of OpenAI's Realtime API for voice processing"""
    
    # OpenAI Realtime API endpoint
    WEBSOCKET_URL = "wss://api.openai.com/v1/realtime"
    
    def __init__(self, api_key: str):
        """Initialize the Realtime session"""
        self.api_key = api_key
        self.session_id = None
        self.websocket = None
        self.events_queue = asyncio.Queue()
        self._listening_task = None
    
    @classmethod
    def create(cls, api_key: str):
        """Class method to create a session"""
        instance = cls(api_key=api_key)
        return instance
    
    async def connect(self, session_config: Dict[str, Any] = None):
        """Connect to the OpenAI Realtime API"""
        if session_config is None:
            session_config = {}
        
        # Configure turn detection if not set
        if "turn_detection" not in session_config:
            # Set reasonable defaults for phone conversations
            session_config["turn_detection"] = {
                "mode": "dynamic_threshold",  # Better for phone calls
                "timeout": 2.0,               # 2-second silence timeout
                "interrupt_assistant": True,  # Allow interruptions
                "create_response": True,      # Auto-create responses on turn change
                "speech_started_delay": 0.3,  # Slight delay for better detection
            }
        
        # Create a new session
        self.session_id = str(uuid.uuid4())
        logger.info(f"Creating new realtime session with ID: {self.session_id}")
        
        # Connect to the WebSocket
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        try:
            logger.info("Connecting to OpenAI Realtime WebSocket API")
            self.websocket = await websockets.connect(
                self.WEBSOCKET_URL, extra_headers=headers
            )
            logger.info("WebSocket connection established")
            
            # Initialize session with the provided configuration
            await self.send_event({"type": "session.update", "session": session_config})
            
            # Start listening for events
            self._listening_task = asyncio.create_task(self._listen_for_events())
            
            # Wait for the session.created event
            session_created = False
            timeout = 15  # Seconds
            start_time = time.time()
            
            while not session_created and time.time() - start_time < timeout:
                try:
                    event = await asyncio.wait_for(self.events_queue.get(), timeout=5)
                    
                    if event.get("type") == "session.created":
                        session_created = True
                        self.session_id = event.get("session", {}).get("id")
                        logger.info(f"Session created successfully with ID: {self.session_id}")
                    elif event.get("type") == "error":
                        logger.error(f"Error event received during session creation: {event}")
                        raise ConnectionError(f"Error creating session: {event.get('message', 'Unknown error')}")
                except asyncio.TimeoutError:
                    logger.warning("Timeout waiting for events during session creation")
            
            if not session_created:
                raise ConnectionError("Timed out waiting for session.created event")
            
            return self.session_id
        except Exception as e:
            logger.error(f"Error connecting to OpenAI Realtime API: {e}")
            logger.error(traceback.format_exc())
            raise
    
    async def send_event(self, event: Dict[str, Any]):
        """Send an event to the OpenAI Realtime API"""
        if not self.websocket:
            raise RuntimeError("Not connected to OpenAI Realtime API")
        
        try:
            event_json = json.dumps(event)
            await self.websocket.send(event_json)
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

class RealtimeAudioProcessor:
    """Real-time audio processor using OpenAI's Realtime API."""
    
    def __init__(self):
        """Initialize the processor."""
        self.api_key = OPENAI_API_KEY
        self.openai_client = True  # Simple flag for health check
    
    async def process_realtime_session(self, session_id, audio_generator, content_type="audio/mulaw"):
        """
        Process a real-time session with streaming audio from Twilio.
        
        Args:
            session_id: The session ID
            audio_generator: Async generator yielding audio chunks
            content_type: Audio content type (usually mulaw for Twilio)
            
        Yields:
            Dict containing events from the Realtime session
        """
        try:
            # Create a Realtime session
            session = RealtimeSession.create(api_key=self.api_key)
            
            # Configure input and output audio formats based on content type
            input_format = {"type": content_type}
            output_format = {"type": "audio/mp3"}
            
            # Add sampling rate for mulaw (Twilio)
            if "mulaw" in content_type or "ulaw" in content_type:
                input_format["sampling_rate"] = 8000
                
            # Connect to the Realtime API with optimal configurations
            await session.connect(
                session_config={
                    "input_audio_format": input_format,
                    "output_audio_format": output_format,
                    "turn_detection": {
                        "mode": "dynamic_threshold",  # Better for phone calls
                        "timeout": 2.0,               # 2-second timeout for silence
                        "interrupt_assistant": True,  # Allow interruptions
                        "create_response": True,      # Auto-create responses
                        "speech_started_delay": 0.3,  # Slight delay for better detection
                    }
                }
            )
            
            # Create a task to process audio chunks
            async def process_audio_chunks():
                chunks_sent = 0
                
                async for chunk in audio_generator:
                    try:
                        # Process the audio chunk
                        if isinstance(chunk, bytes):
                            # Convert μ-law to PCM if needed
                            if "mulaw" in content_type or "ulaw" in content_type:
                                # Don't actually convert for now, as we're including content_type in session config
                                pass
                            
                            # Encode as base64
                            base64_audio = base64.b64encode(chunk).decode("utf-8")
                            
                            # Send to the Realtime API
                            await session.send_event({
                                "type": "input_audio_buffer.append",
                                "audio": base64_audio
                            })
                            
                            chunks_sent += 1
                            
                            # Log progress
                            if chunks_sent % 10 == 0:
                                logger.debug(f"Sent {chunks_sent} audio chunks")
                    except Exception as e:
                        logger.error(f"Error processing audio chunk: {e}")
                        logger.error(traceback.format_exc())
                
                # Signal end of audio
                try:
                    await session.send_event({"type": "input_audio_buffer.commit"})
                    logger.info(f"Committed audio buffer after sending {chunks_sent} chunks")
                except Exception as e:
                    logger.error(f"Error committing audio buffer: {e}")
            
            # Start processing audio chunks in the background
            audio_task = asyncio.create_task(process_audio_chunks())
            
            # Process events from the Realtime API
            try:
                async for event in session.get_events():
                    # Pass through relevant events based on type
                    event_type = event.get("type", "")
                    
                    if event_type in [
                        "response.audio_transcript.delta",
                        "response.audio_transcript.done",
                        "response.text.delta",
                        "response.text.done",
                        "response.audio.delta",
                        "response.audio.done",
                        "tool_call",
                        "speech.started",
                        "speech.finished",
                        "silence_detected"
                    ]:
                        yield event
                    
                    # Handle silence detection specifically
                    if event_type == "silence_detected":
                        # When silence is detected, we need to commit the buffer
                        try:
                            await session.send_event({"type": "input_audio_buffer.commit"})
                            logger.info("Committed audio buffer due to silence detection")
                            
                            # Request a response
                            await session.send_event({
                                "type": "response.create",
                                "response": {"modalities": ["text", "audio"]}
                            })
                        except Exception as e:
                            logger.error(f"Error handling silence: {e}")
                    
                    # Handle speech.finished events
                    if event_type == "speech.finished":
                        # When speech finishes, we should commit and request a response
                        try:
                            await session.send_event({"type": "input_audio_buffer.commit"})
                            logger.info("Committed audio buffer due to speech finished")
                            
                            # Request a response
                            await session.send_event({
                                "type": "response.create",
                                "response": {"modalities": ["text", "audio"]}
                            })
                        except Exception as e:
                            logger.error(f"Error handling speech finished: {e}")
            
            except Exception as e:
                logger.error(f"Error processing Realtime events: {e}")
                logger.error(traceback.format_exc())
                yield {"type": "error", "error": str(e)}
            
            finally:
                # Clean up resources
                if not audio_task.done():
                    audio_task.cancel()
                
                try:
                    await session.close()
                except Exception as e:
                    logger.error(f"Error closing session: {e}")
        
        except Exception as e:
            logger.error(f"Error in process_realtime_session: {e}")
            logger.error(traceback.format_exc())
            yield {"type": "error", "error": str(e)}
    
    async def process_media_stream(self, twilio_media_stream, session_id=None):
        """
        Process a media stream from Twilio.
        
        Args:
            twilio_media_stream: The Twilio media stream
            session_id: Optional session ID
            
        Yields:
            Dict containing events for client consumption
        """
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        async def audio_generator():
            async for message in twilio_media_stream:
                if isinstance(message, dict):
                    # Handle Twilio Media Streams API message format
                    if message.get("event") == "media":
                        payload = message.get("media", {}).get("payload")
                        if payload:
                            # Decode base64 audio from Twilio
                            audio_chunk = base64.b64decode(payload)
                            yield audio_chunk
                elif isinstance(message, bytes):
                    # Handle raw audio bytes
                    yield message
        
        # Process the Realtime session
        async for event in self.process_realtime_session(
            session_id, 
            audio_generator(), 
            content_type="audio/mulaw"
        ):
            # Transform events for client consumption
            event_type = event.get("type", "")
            
            if event_type == "response.audio_transcript.delta":
                yield {
                    "type": "transcript",
                    "text": event.get("delta", ""),
                    "final": False,
                    "timestamp": time.time()
                }
            
            elif event_type == "response.audio_transcript.done":
                yield {
                    "type": "transcript_complete",
                    "text": event.get("text", ""),
                    "final": True,
                    "timestamp": time.time()
                }
            
            elif event_type == "response.text.delta":
                yield {
                    "type": "message",
                    "text": event.get("delta", ""),
                    "complete": False,
                    "timestamp": time.time()
                }
            
            elif event_type == "response.text.done":
                yield {
                    "type": "message_complete",
                    "text": event.get("text", ""),
                    "complete": True,
                    "timestamp": time.time()
                }
            
            elif event_type == "response.audio.delta":
                # Pass through audio data as is - we'll convert it in the voice route
                yield {
                    "type": "audio",
                    "data": event.get("delta", ""),
                    "timestamp": time.time()
                }
            
            elif event_type == "response.audio.done":
                yield {
                    "type": "audio_complete",
                    "timestamp": time.time()
                }
            
            elif event_type == "tool_call":
                yield {
                    "type": "tool_call",
                    "name": event.get("name", ""),
                    "arguments": event.get("arguments", {}),
                    "id": event.get("id", ""),
                    "timestamp": time.time()
                }
            
            elif event_type == "speech.started":
                yield {
                    "type": "speech_started",
                    "timestamp": time.time()
                }
            
            elif event_type == "speech.finished":
                yield {
                    "type": "speech_finished",
                    "timestamp": time.time()
                }
            
            elif event_type == "silence_detected":
                yield {
                    "type": "silence_detected",
                    "timestamp": time.time()
                }
            
            elif event_type == "error":
                yield {
                    "type": "error",
                    "error": event.get("message", "Unknown error"),
                    "timestamp": time.time()
                }
    
    async def send_tool_response(self, session, tool_id, result):
        """
        Send a tool response to the Realtime API.
        
        Args:
            session: The Realtime session
            tool_id: The tool call ID
            result: The result to send
            
        Returns:
            True if successful, False otherwise
        """
        try:
            await session.send_event({
                "type": "tool_response",
                "id": tool_id,
                "status": "success",
                "result": result
            })
            return True
        except Exception as e:
            logger.error(f"Error sending tool response: {e}")
            logger.error(traceback.format_exc())
            return False

# Create a global instance of the processor
realtime_processor = RealtimeAudioProcessor()

# Function to create a processor (kept for backward compatibility)
def get_realtime_processor():
    """Get a RealtimeAudioProcessor instance."""
    return realtime_processor