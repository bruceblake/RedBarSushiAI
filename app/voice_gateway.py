"""
WebSocket Voice Gateway for Twilio Media Streams.

This module implements real-time, low-latency voice handling using Twilio Media Streams
with WebSocket connections. It replaces the ConversationRelay approach for better
control over audio streaming, interruption handling, and latency.
"""

import json
import base64
import asyncio
import time
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Path
from app.config import settings
from app.utils.enhanced_logging import get_logger
from app.utils.correlation_id import set_correlation_id

# Import mock services for now
from app.services.stt_service import initialize_stt_stream, stream_audio_to_stt, get_stt_results
from app.services.tts_service import text_to_speech_audio_generator
from app.agent_orchestrator import mock_orchestrator

# TODO_AI_REPLACE_WITH_ACTUAL_ORCHESTRATOR: Import actual orchestrator
# from app.utils.agent_orchestration_async import async_agent_orchestrator

logger = get_logger(__name__)

router = APIRouter(tags=["Voice WebSocket"])


class MediaStreamHandler:
    """Handles a Twilio Media Stream WebSocket connection."""
    
    def __init__(self, websocket: WebSocket, call_sid: str, stt_service=None, tts_service=None, orchestrator=None):
        self.websocket = websocket
        self.call_sid = call_sid
        self.stream_sid: Optional[str] = None
        self.is_running = False
        self.current_tts_task: Optional[asyncio.Task] = None
        self.is_tts_active = False
        self.stt_service = stt_service
        self.tts_service = tts_service
        self.orchestrator = orchestrator
        self.audio_buffer = bytearray()
        self.tts_utterance_counter = 0
        
    async def _send_to_twilio(self, message: Dict[str, Any]) -> None:
        """Send a message to Twilio via WebSocket."""
        await self.websocket.send_text(json.dumps(message))
        logger.debug(f"[{self.call_sid}] Sent to Twilio: {message.get('event')} event")
        
    async def _stream_tts_to_twilio(self, text_to_speak: str, utterance_id: str = None):
        """
        Stream TTS audio to Twilio via WebSocket.
        
        Args:
            text_to_speak: The text to convert to speech and stream
            utterance_id: Unique identifier for this TTS utterance
        """
        if not self.stream_sid:
            logger.error(f"[{self.call_sid}] Cannot stream TTS - streamSid not set")
            return
            
        self.is_tts_active = True
        utterance_id = utterance_id or f"utterance_{self.tts_utterance_counter}"
        self.tts_utterance_counter += 1
        
        logger.info(f"[{self.call_sid}] Starting TTS stream for utterance '{utterance_id}': {text_to_speak[:50]}...")
        
        try:
            # Use the mock TTS service to generate audio
            chunk_count = 0
            async for audio_chunk in text_to_speech_audio_generator(text_to_speak, {"provider": "mock"}):
                if not self.is_tts_active:
                    logger.info(f"[{self.call_sid}] TTS interrupted, stopping stream for '{utterance_id}'")
                    break
                    
                # Send audio chunk to Twilio
                payload = base64.b64encode(audio_chunk).decode('utf-8')
                await self._send_to_twilio({
                    "event": "media",
                    "streamSid": self.stream_sid,
                    "media": {
                        "payload": payload
                    }
                })
                chunk_count += 1
                logger.debug(f"[{self.call_sid}] Sent TTS media chunk {chunk_count} for '{utterance_id}'")
            
            # Send mark event to indicate TTS completion
            if self.is_tts_active:  # Only send mark if not interrupted
                mark_name = f"{utterance_id}_finished"
                await self._send_to_twilio({
                    "event": "mark",
                    "streamSid": self.stream_sid,
                    "mark": {
                        "name": mark_name
                    }
                })
                logger.info(f"[{self.call_sid}] TTS mark sent: {mark_name}")
            else:
                logger.info(f"[{self.call_sid}] TTS was interrupted, not sending mark for '{utterance_id}'")
                
        except asyncio.CancelledError:
            logger.info(f"[{self.call_sid}] TTS task cancelled for '{utterance_id}'")
            self.is_tts_active = False
            raise
        except Exception as e:
            logger.error(f"[{self.call_sid}] Error streaming TTS for '{utterance_id}': {e}", exc_info=True)
        finally:
            self.is_tts_active = False
            logger.info(f"[{self.call_sid}] TTS stream completed for '{utterance_id}'")
    
    async def _handle_user_interruption(self):
        """Handle user interruption during TTS playback."""
        if self.is_tts_active and self.current_tts_task and not self.current_tts_task.done():
            logger.info(f"[{self.call_sid}] User interruption detected during TTS")
            self.is_tts_active = False  # Signal the TTS loop to stop
            self.current_tts_task.cancel()  # Cancel the TTS task
            try:
                await self.current_tts_task
            except asyncio.CancelledError:
                logger.info(f"[{self.call_sid}] TTS task successfully cancelled")
            self.current_tts_task = None
    
    async def handle_media_event(self, message: Dict[str, Any]):
        """Handle incoming audio from the user."""
        # Check for interruption first
        await self._handle_user_interruption()
        
        payload = message["media"]["payload"]
        # Audio is base64 encoded mulaw
        audio_chunk_bytes = base64.b64decode(payload)
        
        # Process with STT service
        if self.stt_service:
            # Send audio chunk to STT
            await self.stt_service.process_audio(audio_chunk_bytes)
            
            # Try to get transcripts
            interim_transcript, final_transcript = await self.stt_service.get_results()
            
            # Log interim transcript if available
            if interim_transcript:
                logger.info(f"[{self.call_sid}] STT Interim Transcript: '{interim_transcript}'")
            
            # Process final transcript
            if final_transcript:
                logger.info(f"[{self.call_sid}] STT Final Transcript: '{final_transcript}'")
                
                # Send to orchestrator
                if self.orchestrator:
                    logger.info(f"[{self.call_sid}] Sending transcript to orchestrator")
                    ai_response = await self.orchestrator.handle_input(self.call_sid, final_transcript)
                    
                    if ai_response:
                        logger.info(f"[{self.call_sid}] Orchestrator response: '{ai_response}'")
                        
                        # Start TTS task for AI response
                        utterance_id = f"response_{int(time.time())}"
                        logger.info(f"[{self.call_sid}] Initiating TTS for utterance '{utterance_id}'")
                        
                        self.current_tts_task = asyncio.create_task(
                            self._stream_tts_to_twilio(ai_response, utterance_id)
                        )
                    else:
                        logger.warning(f"[{self.call_sid}] No response from orchestrator")
                else:
                    logger.warning(f"[{self.call_sid}] No orchestrator configured, using fallback")
                    # Fallback response without orchestrator
                    fallback_response = f"I heard you say: {final_transcript}"
                    self.current_tts_task = asyncio.create_task(
                        self._stream_tts_to_twilio(fallback_response, f"fallback_{int(time.time())}")
                    )
        else:
            # No STT service, just log audio received
            logger.debug(f"[{self.call_sid}] Received {len(audio_chunk_bytes)} bytes of audio (no STT configured)")
    
    async def handle_connected(self, message: Dict[str, Any]):
        """Handle the connected event."""
        logger.info(f"[{self.call_sid}] WebSocket connected to Twilio Media Stream")
        logger.info(f"[{self.call_sid}] Protocol: {message.get('protocol')}")
        logger.info(f"[{self.call_sid}] Version: {message.get('version')}")
        
    async def handle_start(self, message: Dict[str, Any]):
        """Handle the start event and send greeting."""
        self.stream_sid = message.get("streamSid")
        logger.info(f"[{self.call_sid}] Media stream started. Stream SID: {self.stream_sid}")
        logger.info(f"[{self.call_sid}] Media format: {message.get('mediaFormat')}")
        
        # Initialize STT if not already provided
        if not self.stt_service:
            self.stt_service = await initialize_stt_stream(self.call_sid, {"provider": "mock"})
            logger.info(f"[{self.call_sid}] Initialized mock STT service")
        
        # Start STT stream
        if hasattr(self.stt_service, 'start_stream'):
            await self.stt_service.start_stream()
            logger.info(f"[{self.call_sid}] STT stream started")
        
        # Initialize conversation with orchestrator
        if self.orchestrator:
            await self.orchestrator.start_new_conversation(
                self.call_sid,
                {"voice_mode": "media_streams", "first_interaction": True}
            )
            logger.info(f"[{self.call_sid}] Conversation initialized with orchestrator")
        
        # Send greeting
        greeting_text = "Hello! Welcome to Red Bar Sushi AI. How can I help you today?"
        self.current_tts_task = asyncio.create_task(
            self._stream_tts_to_twilio(greeting_text, "greeting")
        )
        
    async def handle_stop(self, message: Dict[str, Any]):
        """Handle the stop event."""
        logger.info(f"[{self.call_sid}] Media stream stopped")
        
        # Cancel any active TTS
        if self.current_tts_task and not self.current_tts_task.done():
            self.current_tts_task.cancel()
            try:
                await self.current_tts_task
            except asyncio.CancelledError:
                pass
                
        # Stop and clean up STT
        if self.stt_service:
            if hasattr(self.stt_service, 'stop_stream'):
                await self.stt_service.stop_stream()
                logger.info(f"[{self.call_sid}] STT stream stopped")
            await self.stt_service.close()
            logger.info(f"[{self.call_sid}] STT service closed")
            
        # End conversation with orchestrator
        if self.orchestrator:
            await self.orchestrator.end_conversation(self.call_sid)
            logger.info(f"[{self.call_sid}] Conversation ended with orchestrator")
            
        self.is_running = False
        
    async def handle_mark(self, message: Dict[str, Any]):
        """Handle mark events from Twilio."""
        mark_name = message.get("mark", {}).get("name", "")
        logger.info(f"[{self.call_sid}] Mark received: {mark_name}")
        
        # Reset TTS active flag when mark is received
        if "_finished" in mark_name:
            self.is_tts_active = False
            logger.info(f"[{self.call_sid}] TTS playback confirmed complete for {mark_name}")
    
    async def run(self):
        """Main event loop for handling Media Stream messages."""
        self.is_running = True
        logger.info(f"[{self.call_sid}] MediaStreamHandler started")
        
        try:
            while self.is_running:
                message_json = await self.websocket.receive_text()
                message = json.loads(message_json)
                
                event_type = message.get("event")
                logger.debug(f"[{self.call_sid}] Received event: {event_type}")
                
                # Route to appropriate handler
                if event_type == "connected":
                    await self.handle_connected(message)
                elif event_type == "start":
                    await self.handle_start(message)
                elif event_type == "media":
                    await self.handle_media_event(message)
                elif event_type == "stop":
                    await self.handle_stop(message)
                elif event_type == "mark":
                    await self.handle_mark(message)
                else:
                    logger.debug(f"[{self.call_sid}] Unknown event type: {event_type}")
                    
        except WebSocketDisconnect:
            logger.info(f"[{self.call_sid}] WebSocket disconnected by client")
        except Exception as e:
            logger.error(f"[{self.call_sid}] Error in MediaStreamHandler: {e}", exc_info=True)
        finally:
            self.is_running = False
            # Cleanup
            if self.current_tts_task and not self.current_tts_task.done():
                self.current_tts_task.cancel()
            if self.stt_service:
                await self.stt_service.close()
            logger.info(f"[{self.call_sid}] MediaStreamHandler finished")


@router.websocket("/ws/voice/{call_sid}")
async def websocket_voice_endpoint(websocket: WebSocket, call_sid: str = Path(...)):
    """
    WebSocket endpoint for Twilio Media Streams.
    
    This endpoint handles real-time bidirectional audio streaming with Twilio,
    enabling low-latency voice interactions with support for interruptions.
    
    Args:
        websocket: FastAPI WebSocket instance
        call_sid: Twilio call SID from the path parameter
    """
    logger.info(f"[{call_sid}] New WebSocket connection attempt for Media Streams")
    
    try:
        await websocket.accept()
        logger.info(f"[{call_sid}] WebSocket connection accepted")
        
        # Set correlation ID for this call
        set_correlation_id(call_sid)
        
        # Initialize services (using mocks for now)
        stt_service = None  # Will be initialized when stream starts
        tts_service = None  # Using the global text_to_speech_audio_generator function
        orchestrator = mock_orchestrator  # Using mock orchestrator
        
        logger.info(f"[{call_sid}] Creating MediaStreamHandler instance")
        
        # Create handler with dependencies
        handler = MediaStreamHandler(
            websocket=websocket,
            call_sid=call_sid,
            stt_service=stt_service,
            tts_service=tts_service,
            orchestrator=orchestrator
        )
        
        # TODO_AI: Initialize conversation with agent orchestrator
        # if orchestrator:
        #     await orchestrator.start_new_conversation(
        #         call_sid,
        #         {"voice_mode": "media_streams", "first_interaction": True}
        #     )
        
        logger.info(f"[{call_sid}] Starting MediaStreamHandler.run()")
        
        # Run the handler
        await handler.run()
        
    except WebSocketDisconnect:
        logger.info(f"[{call_sid}] WebSocket disconnected during endpoint handling")
    except Exception as e:
        logger.error(f"[{call_sid}] Error in WebSocket endpoint: {e}", exc_info=True)
    finally:
        # TODO_AI: Notify orchestrator that conversation ended
        # if orchestrator:
        #     await orchestrator.end_conversation(call_sid)
        logger.info(f"[{call_sid}] WebSocket endpoint cleanup complete")