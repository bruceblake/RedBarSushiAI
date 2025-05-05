"""
Realtime audio processing for RedBarSushiAI using OpenAI Agents SDK.
This module provides the core functionality for processing realtime audio streams.
"""

import os
import json
import logging
import asyncio
import time
import base64
import array
import struct
from typing import Dict, List, Any, Optional, AsyncGenerator, Tuple, Union, BinaryIO

import openai
from openai import OpenAI
from app.utils.agents_sdk import agents_client
from app.utils.conversation_store_sdk import agents_conversation_store
from app.utils.voice_controller import voice_controller

logger = logging.getLogger(__name__)

# OpenAI API key for realtime audio processing
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

class RealtimeAudioProcessor:
    """Processor for realtime audio streams with OpenAI."""
    
    def __init__(self):
        """Initialize the realtime audio processor."""
        self.openai_client = openai_client
        self.voice_controller = voice_controller
    
    async def ulaw_to_pcm(self, ulaw_data: bytes) -> bytes:
        """
        Convert μ-law 8 kHz audio to PCM 16 kHz format.
        
        Args:
            ulaw_data: The μ-law encoded audio data
            
        Returns:
            PCM encoded audio data
        """
        # μ-law to linear PCM conversion table for 8-bit samples
        ulaw_to_linear = [
            -32124, -31100, -30076, -29052, -28028, -27004, -25980, -24956,
            -23932, -22908, -21884, -20860, -19836, -18812, -17788, -16764,
            -15996, -15484, -14972, -14460, -13948, -13436, -12924, -12412,
            -11900, -11388, -10876, -10364, -9852, -9340, -8828, -8316,
            -7932, -7676, -7420, -7164, -6908, -6652, -6396, -6140,
            -5884, -5628, -5372, -5116, -4860, -4604, -4348, -4092,
            -3900, -3772, -3644, -3516, -3388, -3260, -3132, -3004,
            -2876, -2748, -2620, -2492, -2364, -2236, -2108, -1980,
            -1884, -1820, -1756, -1692, -1628, -1564, -1500, -1436,
            -1372, -1308, -1244, -1180, -1116, -1052, -988, -924,
            -876, -844, -812, -780, -748, -716, -684, -652,
            -620, -588, -556, -524, -492, -460, -428, -396,
            -372, -356, -340, -324, -308, -292, -276, -260,
            -244, -228, -212, -196, -180, -164, -148, -132,
            -120, -112, -104, -96, -88, -80, -72, -64,
            -56, -48, -40, -32, -24, -16, -8, 0,
            32124, 31100, 30076, 29052, 28028, 27004, 25980, 24956,
            23932, 22908, 21884, 20860, 19836, 18812, 17788, 16764,
            15996, 15484, 14972, 14460, 13948, 13436, 12924, 12412,
            11900, 11388, 10876, 10364, 9852, 9340, 8828, 8316,
            7932, 7676, 7420, 7164, 6908, 6652, 6396, 6140,
            5884, 5628, 5372, 5116, 4860, 4604, 4348, 4092,
            3900, 3772, 3644, 3516, 3388, 3260, 3132, 3004,
            2876, 2748, 2620, 2492, 2364, 2236, 2108, 1980,
            1884, 1820, 1756, 1692, 1628, 1564, 1500, 1436,
            1372, 1308, 1244, 1180, 1116, 1052, 988, 924,
            876, 844, 812, 780, 748, 716, 684, 652,
            620, 588, 556, 524, 492, 460, 428, 396,
            372, 356, 340, 324, 308, 292, 276, 260,
            244, 228, 212, 196, 180, 164, 148, 132,
            120, 112, 104, 96, 88, 80, 72, 64,
            56, 48, 40, 32, 24, 16, 8, 0
        ]
        
        # Extract 8-bit values from the μ-law data
        ulaw_values = array.array('B', ulaw_data)
        
        # Convert to 16-bit PCM
        pcm_values = array.array('h')
        for ulaw_byte in ulaw_values:
            pcm_values.append(ulaw_to_linear[ulaw_byte])
        
        # Return as bytes
        return pcm_values.tobytes()
    
    async def pcm_to_ulaw(self, pcm_data: bytes) -> bytes:
        """
        Convert PCM 16 kHz audio to μ-law 8 kHz format.
        
        Args:
            pcm_data: The PCM encoded audio data
            
        Returns:
            μ-law encoded audio data
        """
        # PCM to μ-law conversion (simplified approach)
        # In a real implementation, you'd want to properly filter and downsample
        
        # Extract 16-bit values from the PCM data
        pcm_values = array.array('h')
        pcm_values.frombytes(pcm_data)
        
        # Bias of 132 for 16-bit samples
        BIAS = 132
        
        # Convert to 8-bit μ-law
        ulaw_values = array.array('B')
        for pcm_sample in pcm_values:
            # Find the absolute value
            value = abs(pcm_sample)
            sign = (pcm_sample < 0) and 0x80 or 0
            
            # Add bias
            value += BIAS
            
            # Limit to 16 bits
            if value > 32767:
                value = 32767
            
            # Find the μ-law code
            exponent = 7
            for exp_value in (0x4000, 0x2000, 0x1000, 0x800, 0x400, 0x200, 0x100, 0x80):
                if value < exp_value:
                    exponent -= 1
                else:
                    break
            
            # Combine mantissa and exponent
            mantissa = (value >> (exponent + 3)) & 0x0F
            comp_value = ~(sign | (exponent << 4) | mantissa)
            
            ulaw_values.append(comp_value & 0xFF)
        
        # Take every second sample to downsample from 16 kHz to 8 kHz
        # This is a very simple approach - a proper implementation would use a filter
        downsampled = array.array('B', [ulaw_values[i] for i in range(0, len(ulaw_values), 2)])
        
        # Return as bytes
        return downsampled.tobytes()
    
    async def process_media_stream(
        self, 
        call_sid: str, 
        stream: AsyncGenerator[bytes, None]
    ) -> AsyncGenerator[Union[Dict[str, Any], bytes], None]:
        """
        Process a stream of media from Twilio.
        
        Args:
            call_sid: The Twilio call SID
            stream: An async generator yielding raw media frames
            
        Returns:
            Async generator yielding responses (JSON data or raw audio)
        """
        if not self.openai_client:
            logger.error("OpenAI client not available")
            yield {"type": "error", "message": "OpenAI client not available"}
            return
        
        logger.info(f"Processing media stream for call {call_sid}")
        
        # Buffer for collecting audio chunks
        audio_buffer = bytearray()
        
        # Timestamp for tracking
        stream_start_time = time.time()
        
        # Flag to manage the state
        have_sent_connection_message = False
        
        try:
            # Setup the OpenAI WebSocket stream
            # In a real implementation, this would use the OpenAI API directly
            # For now, we'll just simulate the process with what we have available
            
            if not have_sent_connection_message:
                # Send initial connection message
                yield {"type": "connected", "timestamp": time.time() - stream_start_time}
                have_sent_connection_message = True
            
            # Process incoming audio chunks
            async for chunk in stream:
                # Decode the base64 audio data
                if not chunk:
                    continue
                
                try:
                    # Parse the chunk as JSON
                    data = json.loads(chunk)
                    
                    # Extract the media data if this is a media message
                    if data.get("event") == "media":
                        media_data = data.get("media", {})
                        if media_data.get("payload"):
                            # Decode base64 audio data
                            audio_chunk = base64.b64decode(media_data["payload"])
                            # Convert μ-law to PCM
                            pcm_chunk = await self.ulaw_to_pcm(audio_chunk)
                            # Add to buffer
                            audio_buffer.extend(pcm_chunk)
                            
                            # If we have enough audio, process it
                            if len(audio_buffer) >= 16000:  # About 1 second of audio at 16 kHz
                                # For now, just simulate transcription
                                yield {
                                    "type": "transcript_partial",
                                    "text": "Processing...",
                                    "timestamp": time.time() - stream_start_time
                                }
                                
                                # Reset the buffer
                                audio_buffer = bytearray()
                except json.JSONDecodeError:
                    # Not JSON, treat as raw binary data
                    # Convert μ-law to PCM
                    pcm_chunk = await self.ulaw_to_pcm(chunk)
                    # Add to buffer
                    audio_buffer.extend(pcm_chunk)
                    
                    # If we have enough audio, process it
                    if len(audio_buffer) >= 16000:  # About 1 second of audio at 16 kHz
                        # For now, just simulate transcription
                        yield {
                            "type": "transcript_partial",
                            "text": "Processing...",
                            "timestamp": time.time() - stream_start_time
                        }
                        
                        # Reset the buffer
                        audio_buffer = bytearray()
            
            # Once we're done collecting audio, simulate final processing
            # In a real implementation, this would use the OpenAI API
            yield {
                "type": "transcript_complete",
                "text": "Simulated transcription: How can I help you today?",
                "timestamp": time.time() - stream_start_time
            }
            
            # Simulate agent response
            response_text = "Hello! This is a simulated response from the agent. How can I help you with our menu today?"
            yield {
                "type": "agent_response",
                "text": response_text,
                "timestamp": time.time() - stream_start_time
            }
            
            # Simulate TTS audio
            # Generate 5 seconds of silence as a placeholder
            silence_data = bytes([128] * 8000 * 5)  # 5 seconds of silence at 8 kHz
            for i in range(0, len(silence_data), 1000):
                chunk = silence_data[i:i+1000]
                yield {
                    "type": "audio",
                    "format": "ulaw",
                    "sample_rate": 8000,
                    "data": base64.b64encode(chunk).decode("utf-8"),
                    "timestamp": time.time() - stream_start_time
                }
            
            # Final message
            yield {
                "type": "complete",
                "timestamp": time.time() - stream_start_time
            }
        
        except Exception as e:
            logger.error(f"Error processing media stream: {str(e)}")
            logger.error(traceback.format_exc())
            yield {"type": "error", "message": str(e)}
    
    async def process_realtime_session(
        self, 
        call_sid: str, 
        audio_stream: AsyncGenerator[bytes, None]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process a realtime session with OpenAI's API.
        This is a placeholder for the real implementation.
        
        Args:
            call_sid: The Twilio call SID
            audio_stream: Async generator yielding audio chunks
            
        Returns:
            Async generator yielding response chunks
        """
        logger.info(f"Starting realtime session for call {call_sid}")
        
        # Get or create the thread ID for this call
        thread_id = agents_conversation_store.get_thread_id(call_sid)
        
        # Placeholder implementation - in a real system, this would use the OpenAI Realtime API
        yield {"type": "info", "message": "Starting realtime session"}
        
        # Simulate processing the audio stream
        buffer = bytearray()
        
        async for chunk in audio_stream:
            # Add to buffer
            buffer.extend(chunk)
            
            # Simulated partial transcript
            if len(buffer) > 8000:  # Arbitrary threshold
                yield {"type": "transcript_partial", "text": "Processing your request..."}
                buffer = bytearray()
        
        # Simulated final transcript
        yield {"type": "transcript_complete", "text": "How can I help you today?"}
        
        # Simulated agent response
        yield {"type": "agent_response", "text": "Hello! I'm the Red Bar Sushi assistant. How can I help you?"}
        
        # End of session
        yield {"type": "session_complete"}

# Singleton instance for easy import
realtime_processor = RealtimeAudioProcessor()