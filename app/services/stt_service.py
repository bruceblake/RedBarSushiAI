"""
Speech-to-Text (STT) Service for voice transcription.

This module provides interfaces for streaming audio to various STT providers
and retrieving transcripts. Supports multiple backends including Google Speech-to-Text,
Deepgram, and others.
"""

import asyncio
from typing import Optional, Tuple, Dict, Any
from abc import ABC, abstractmethod
from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)


class STTStream(ABC):
    """Abstract base class for STT stream implementations."""
    
    @abstractmethod
    async def process_audio(self, audio_chunk: bytes) -> None:
        """Process an audio chunk."""
        pass
    
    @abstractmethod
    async def get_results(self) -> Tuple[Optional[str], Optional[str]]:
        """Get interim and final transcripts."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close the stream and clean up resources."""
        pass


class MockSTTStream(STTStream):
    """Mock STT stream for development and testing."""
    
    def __init__(self, call_sid: str):
        self.call_sid = call_sid
        self.audio_buffer = bytearray()
        self.chunk_count = 0
        self.total_audio_processed = 0
        self.is_active = False
        
    async def start_stream(self) -> None:
        """Initialize the STT stream."""
        self.is_active = True
        logger.info(f"[{self.call_sid}] Mock STT stream started")
        
    async def process_audio(self, audio_chunk: bytes) -> None:
        """Mock audio processing - accumulate and count chunks."""
        if not self.is_active:
            logger.warning(f"[{self.call_sid}] Attempting to process audio on inactive STT stream")
            return
            
        self.audio_buffer.extend(audio_chunk)
        self.chunk_count += 1
        self.total_audio_processed += len(audio_chunk)
        
        logger.debug(f"[{self.call_sid}] Processed audio chunk {self.chunk_count}, total bytes: {self.total_audio_processed}")
    
    async def get_results(self) -> Tuple[Optional[str], Optional[str]]:
        """Return mock transcripts based on chunks received."""
        if not self.is_active:
            return None, None
            
        # Return interim transcript on first chunk
        if self.chunk_count == 1:
            interim = "I'm starting to hear something..."
            logger.info(f"[{self.call_sid}] Mock STT interim transcript: '{interim}'")
            return interim, None
        
        # Return final transcript after 3 chunks or 8KB of audio
        if self.chunk_count >= 3 or len(self.audio_buffer) > 8000:
            # Generate a mock transcript based on audio size
            words = ["hello", "I'd like", "to order", "some sushi", "please", "thank you"]
            word_count = min(len(words), self.chunk_count)
            final = " ".join(words[:word_count])
            
            logger.info(f"[{self.call_sid}] Mock STT final transcript: '{final}'")
            
            # Reset for next utterance
            self.chunk_count = 0
            self.audio_buffer.clear()
            
            return None, final
        
        return None, None
    
    async def stop_stream(self) -> None:
        """Stop the STT stream."""
        self.is_active = False
        logger.info(f"[{self.call_sid}] Mock STT stream stopped")
        
    async def close(self) -> None:
        """Clean up mock resources."""
        await self.stop_stream()
        self.audio_buffer.clear()
        self.chunk_count = 0
        logger.info(f"[{self.call_sid}] Mock STT stream closed")


# TODO_AI_IMPLEMENT_GOOGLE_STT: Implement GoogleSTTStream class
# class GoogleSTTStream(STTStream):
#     """Google Speech-to-Text stream implementation."""
#     pass


# TODO_AI_IMPLEMENT_DEEPGRAM_STT: Implement DeepgramSTTStream class  
# class DeepgramSTTStream(STTStream):
#     """Deepgram STT stream implementation."""
#     pass


async def initialize_stt_stream(call_sid: str, config: Dict[str, Any]) -> STTStream:
    """
    Initialize an STT stream based on the provider configuration.
    
    Args:
        call_sid: The Twilio call SID
        config: STT provider configuration
        
    Returns:
        An initialized STTStream instance
    """
    provider = config.get("provider", "mock").lower()
    
    if provider == "mock":
        logger.info(f"[{call_sid}] Initializing mock STT stream")
        return MockSTTStream(call_sid)
    # TODO_AI_IMPLEMENT_PROVIDER_SELECTION: Add real provider selection
    # elif provider == "google":
    #     return GoogleSTTStream(call_sid, config)
    # elif provider == "deepgram":
    #     return DeepgramSTTStream(call_sid, config)
    else:
        logger.warning(f"[{call_sid}] Unknown STT provider '{provider}', using mock")
        return MockSTTStream(call_sid)


async def stream_audio_to_stt(stt_stream: STTStream, audio_chunk: bytes) -> None:
    """
    Stream audio chunk to the STT service.
    
    Args:
        stt_stream: The STT stream instance
        audio_chunk: Raw audio bytes to process
    """
    await stt_stream.process_audio(audio_chunk)


async def get_stt_results(stt_stream: STTStream) -> Tuple[Optional[str], Optional[str]]:
    """
    Get transcription results from the STT stream.
    
    Args:
        stt_stream: The STT stream instance
        
    Returns:
        Tuple of (interim_transcript, final_transcript)
    """
    return await stt_stream.get_results()