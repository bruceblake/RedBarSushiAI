"""
Audio processing utilities for voice interactions.

This module contains functions for processing and forwarding audio data
between Twilio and the OpenAI Realtime API.
"""

import logging
import base64
import asyncio
from typing import Any, Dict

# Set up logging
logger = logging.getLogger(__name__)

async def forward_audio_to_openai(call_sid: str, payload: str, openai_task: asyncio.Task) -> None:
    """
    Forward audio data from Twilio to OpenAI Realtime API.
    
    Args:
        call_sid: The Twilio call SID
        payload: The base64-encoded audio data
        openai_task: The active OpenAI processing task
    """
    if not payload or not openai_task or openai_task.done():
        return
        
    try:
        # Decode base64 payload
        audio_data = base64.b64decode(payload)
        
        # Access the OpenAI client via attribute on the task's coro
        # This is a hack to get the client object from the running task
        openai_client = getattr(openai_task.get_coro(), 'openai_client', None)
        
        if openai_client:
            # Send the audio data to OpenAI
            await openai_client.send_audio(audio_data)
        else:
            logger.warning(f"[{call_sid}] Cannot forward audio: OpenAI client not available")
            
    except Exception as e:
        logger.error(f"[{call_sid}] Error forwarding audio: {str(e)}")

async def audio_to_twilio(websocket: Any, audio_data: str) -> None:
    """
    Send audio data from OpenAI to Twilio WebSocket.
    
    Args:
        websocket: The WebSocket connection to Twilio
        audio_data: The base64-encoded audio data
    """
    if not audio_data:
        return
        
    try:
        # Decode base64 audio
        audio_bytes = base64.b64decode(audio_data)
        
        # Send to Twilio WebSocket
        await websocket.send_bytes(audio_bytes)
    except Exception as e:
        logger.error(f"Error sending audio to Twilio: {e}")

def convert_audio_format(audio_data: bytes, source_format: str, target_format: str) -> bytes:
    """
    Convert audio between different formats.
    
    Args:
        audio_data: The audio data to convert
        source_format: The source audio format (e.g., 'mulaw', 'wav', 'pcm')
        target_format: The target audio format to convert to
        
    Returns:
        The converted audio data
    """
    # Currently only supports mulaw as source or target
    if source_format == 'mulaw' and target_format == 'pcm':
        return mulaw_to_pcm(audio_data)
    elif source_format == 'pcm' and target_format == 'mulaw':
        return pcm_to_mulaw(audio_data)
    else:
        # For now, just return the original data if formats are the same
        # or conversion not supported
        return audio_data
        
def mulaw_to_pcm(ulaw_data: bytes) -> bytes:
    """
    Convert μ-law encoded audio data to PCM format.
    
    Args:
        ulaw_data: μ-law encoded audio data (8kHz)
        
    Returns:
        PCM format audio data
    """
    try:
        import numpy as np
        
        # Convert to numpy array
        ulaw_array = np.frombuffer(ulaw_data, dtype=np.uint8)
        
        # μ-law decoding
        # Convert 8-bit mulaw to 16-bit PCM
        sign = np.ones_like(ulaw_array)
        sign[ulaw_array & 0x80 != 0] = -1
        exponent = ((ulaw_array & 0x70) >> 4)
        mantissa = ulaw_array & 0x0f
        sample = sign * (((mantissa + 16.5) * (2 ** exponent)) - 16.5)
        pcm_data = (sample / 128.0 * 32768).astype(np.int16)
        
        # Convert back to bytes
        return pcm_data.tobytes()
    except ImportError:
        logger.warning("NumPy not available, returning original data")
        return ulaw_data
    except Exception as e:
        logger.error(f"Error converting mulaw to PCM: {e}")
        return ulaw_data
        
def pcm_to_mulaw(pcm_data: bytes) -> bytes:
    """
    Convert PCM audio data to μ-law format.
    
    Args:
        pcm_data: PCM audio data
        
    Returns:
        μ-law encoded audio data
    """
    try:
        import numpy as np
        
        # Convert to numpy array
        pcm_array = np.frombuffer(pcm_data, dtype=np.int16)
        
        # μ-law encoding
        # Convert 16-bit PCM to 8-bit mulaw
        # Normalize to range [-1, 1]
        pcm_normalized = pcm_array.astype(np.float32) / 32768.0
        
        # Apply μ-law transformation
        mu = 255
        # Add small number to prevent log(0)
        magnitude = np.log(1 + mu * np.abs(pcm_normalized)) / np.log(1 + mu)
        
        # Keep original sign
        result = np.sign(pcm_normalized) * magnitude
        
        # Scale to [0, 255] range and convert to uint8
        result = (result * 127.5 + 127.5).astype(np.uint8)
        
        # Convert back to bytes
        return result.tobytes()
    except ImportError:
        logger.warning("NumPy not available, returning original data")
        return pcm_data
    except Exception as e:
        logger.error(f"Error converting PCM to mulaw: {e}")
        return pcm_data