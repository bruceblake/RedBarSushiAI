"""
Audio processing utilities for ConversationRelay.

This module handles audio format conversions, STT, and TTS operations.
"""

import logging
import base64
import asyncio
from typing import Optional, List
import numpy as np

# OpenAI imports
try:
    from openai import AsyncOpenAI
except ImportError:
    logging.warning("OpenAI module not found. Audio processing will be limited.")
    AsyncOpenAI = None

from app.config import settings
from app.utils.text_normalization import normalize_for_tts

logger = logging.getLogger(__name__)


class AudioProcessor:
    """Handles audio processing for ConversationRelay."""
    
    def __init__(self):
        """Initialize the audio processor."""
        self.client = None
        if AsyncOpenAI and hasattr(settings, 'OPENAI_API_KEY'):
            self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        else:
            logger.warning("OpenAI client not initialized. Check API key configuration.")
    
    async def speech_to_text(self, audio_bytes: bytes) -> Optional[str]:
        """
        Convert speech audio to text using OpenAI Whisper.
        
        Args:
            audio_bytes: Raw audio data in PCMU format
            
        Returns:
            Transcribed text or None if failed
        """
        if not self.client:
            logger.error("OpenAI client not available for STT")
            return None
            
        try:
            # Convert PCMU to WAV format for Whisper
            wav_data = self._pcmu_to_wav(audio_bytes)
            
            # Create a temporary file-like object
            import io
            audio_file = io.BytesIO(wav_data)
            audio_file.name = "audio.wav"
            
            # Transcribe with Whisper
            response = await self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="en"
            )
            
            return response.text
            
        except Exception as e:
            logger.error(f"STT error: {e}")
            return None
    
    async def text_to_speech(self, text: str) -> Optional[bytes]:
        """
        Convert text to speech audio using OpenAI TTS.
        
        Args:
            text: Text to convert to speech
            
        Returns:
            PCMU audio data or None if failed
        """
        if not self.client:
            logger.error("OpenAI client not available for TTS")
            return None
            
        try:
            # Normalize text for natural speech
            normalized_text = normalize_for_tts(text)
            logger.debug(f"Normalized text for TTS: {normalized_text}")
            
            # Generate speech with OpenAI TTS
            response = await self.client.audio.speech.create(
                model="tts-1",
                voice="nova",  # or "alloy", "echo", "fable", "onyx", "shimmer"
                input=normalized_text,
                response_format="pcm",  # Get raw PCM data
                speed=1.0
            )
            
            # Get the audio content
            pcm_data = response.content
            
            # Convert PCM to PCMU for Twilio
            pcmu_data = self._pcm_to_pcmu(pcm_data)
            
            return pcmu_data
            
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return None
    
    def _pcmu_to_wav(self, pcmu_data: bytes) -> bytes:
        """
        Convert PCMU audio to WAV format.
        
        Args:
            pcmu_data: Raw PCMU audio data
            
        Returns:
            WAV format audio data
        """
        # Convert PCMU to PCM
        pcm_data = self._pcmu_to_pcm(pcmu_data)
        
        # Create WAV header
        import struct
        
        sample_rate = 8000
        num_channels = 1
        bits_per_sample = 16
        
        data_size = len(pcm_data)
        file_size = data_size + 44 - 8
        
        wav_header = struct.pack(
            '<4sI4s4sIHHIIHH4sI',
            b'RIFF',
            file_size,
            b'WAVE',
            b'fmt ',
            16,  # fmt chunk size
            1,   # PCM format
            num_channels,
            sample_rate,
            sample_rate * num_channels * bits_per_sample // 8,
            num_channels * bits_per_sample // 8,
            bits_per_sample,
            b'data',
            data_size
        )
        
        return wav_header + pcm_data
    
    def _pcmu_to_pcm(self, pcmu_data: bytes) -> bytes:
        """Convert PCMU to PCM format."""
        # μ-law decoding table
        MULAW_DECODE = [
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
        
        # Convert bytes to PCM samples
        pcm_samples = []
        for mulaw_byte in pcmu_data:
            pcm_sample = MULAW_DECODE[mulaw_byte]
            # Convert to 16-bit little-endian bytes
            pcm_samples.extend(pcm_sample.to_bytes(2, byteorder='little', signed=True))
        
        return bytes(pcm_samples)
    
    def _pcm_to_pcmu(self, pcm_data: bytes) -> bytes:
        """Convert PCM to PCMU format."""
        # Convert PCM bytes to samples
        import struct
        num_samples = len(pcm_data) // 2
        pcm_samples = struct.unpack(f'<{num_samples}h', pcm_data)
        
        # μ-law encoding
        pcmu_data = bytearray()
        for sample in pcm_samples:
            # Clip to valid range
            sample = max(-32768, min(32767, sample))
            
            # μ-law encoding algorithm
            sign = 0
            if sample < 0:
                sign = 0x80
                sample = -sample
            
            # Add bias
            sample = sample + 132
            
            # Find segment
            segment = 0
            for i in range(7):
                if sample >= (256 << i):
                    segment = i + 1
            
            # Compute mantissa
            if segment > 0:
                mantissa = (sample >> (segment + 2)) & 0x0F
            else:
                mantissa = (sample >> 3) & 0x0F
            
            # Combine components
            mulaw_byte = sign | (segment << 4) | mantissa
            mulaw_byte = 255 - mulaw_byte  # Invert per μ-law spec
            
            pcmu_data.append(mulaw_byte)
        
        return bytes(pcmu_data)