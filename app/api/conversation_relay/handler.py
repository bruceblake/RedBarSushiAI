"""
WebSocket handler for Twilio ConversationRelay.

This module handles bidirectional audio streaming between Twilio and the AI system
using the ConversationRelay protocol.
"""

import json
import logging
import base64
import asyncio
import time
from typing import Dict, Any, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.utils.agent_orchestration_async import async_agent_orchestrator
from .audio import AudioProcessor

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ConversationRelay"])


class ConversationRelayHandler:
    """Handles a ConversationRelay WebSocket connection."""
    
    def __init__(self, websocket: WebSocket, audio_processor: AudioProcessor):
        self.websocket = websocket
        self.audio_processor = audio_processor
        self.relay_id: Optional[str] = None
        self.call_sid: Optional[str] = None
        self.stream_sid: Optional[str] = None
        self.is_running = False
        self.is_playing_tts = False
        self.current_tts_task: Optional[asyncio.Task] = None
        self.last_mark_name: Optional[str] = None
        
    async def handle_start(self, message: Dict[str, Any]):
        """Handle the start event from Twilio ConversationRelay."""
        # ConversationRelay sends these fields directly in the message
        self.relay_id = message.get("relayId")
        self.call_sid = message.get("callSid")
        self.stream_sid = message.get("streamSid")
        
        # Additional fields from ConversationRelay
        self.account_sid = message.get("accountSid")
        audio_config = message.get("audio", {})
        self.content_type = audio_config.get("contentType", "audio/x-mulaw")  # Should be audio/x-mulaw
        self.sample_rate = audio_config.get("sampleRate", 8000)  # Should be 8000
        self.channels = audio_config.get("channels", 1)  # Should be 1 (mono)
        
        logger.info(f"ConversationRelay started - Relay: {self.relay_id}, Call: {self.call_sid}")
        logger.debug(f"Full start message: {json.dumps(message, indent=2)}")
        
        # Start a new conversation
        greeting_response = await async_agent_orchestrator.start_new_conversation(
            self.call_sid,
            {"first_interaction": True}
        )
        
        greeting_text = greeting_response.get("text", "Welcome to Red Bar Sushi. How can I help you today?")
        
        # Send greeting with tracking for barge-in
        self.current_tts_task = asyncio.create_task(
            self._send_tts_with_tracking(greeting_text)
        )
    
    async def handle_media(self, message: Dict[str, Any]):
        """Handle media events containing audio from the caller."""
        media = message.get("media", {})
        audio_payload = media.get("payload", "")
        
        if not audio_payload:
            return
        
        # Check for barge-in: if we receive media while TTS is playing
        if self.is_playing_tts:
            logger.info(f"Barge-in detected for call {self.call_sid}")
            
            # Cancel current TTS task if it exists
            if self.current_tts_task and not self.current_tts_task.done():
                self.current_tts_task.cancel()
                logger.info(f"Cancelled ongoing TTS for call {self.call_sid}")
            
            # Signal the agent orchestrator about barge-in
            await async_agent_orchestrator.handle_interruption(self.call_sid)
            
            self.is_playing_tts = False
            
        try:
            # Decode base64 audio
            audio_bytes = base64.b64decode(audio_payload)
            
            # Process audio through STT
            transcript = await self.audio_processor.speech_to_text(audio_bytes)
            
            if transcript:
                logger.info(f"Transcript received for {self.call_sid}: {transcript}")
                
                # Process with agent
                logger.debug(f"Sending transcript to agent orchestrator for {self.call_sid}")
                response = await async_agent_orchestrator.process_voice_input(
                    self.call_sid, transcript
                )
                logger.debug(f"Agent response for {self.call_sid}: {json.dumps(response, indent=2)}")
                
                response_text = response.get("text", "")
                if response_text:
                    logger.info(f"Sending TTS response for {self.call_sid}: {response_text[:100]}...")
                    # Convert to speech and send in a cancellable task
                    self.current_tts_task = asyncio.create_task(
                        self._send_tts_with_tracking(response_text)
                    )
                else:
                    logger.warning(f"No response text from agent for {self.call_sid}")
                        
        except Exception as e:
            logger.error(f"Error processing media: {e}")
    
    async def handle_mark(self, message: Dict[str, Any]):
        """Handle mark events indicating speech playback completion."""
        mark = message.get("mark", {})
        mark_name = mark.get("name", "")
        logger.debug(f"Mark received: {mark_name}")
        
        # If this mark matches our last TTS mark, TTS playback is complete
        if mark_name == self.last_mark_name:
            self.is_playing_tts = False
            logger.info(f"TTS playback completed for mark: {mark_name}")
    
    async def handle_stop(self, message: Dict[str, Any]):
        """Handle stop event when the call ends."""
        logger.info(f"ConversationRelay stopped for call {self.call_sid}")
        self.is_running = False
    
    async def send_audio(self, audio_data: bytes):
        """Send audio data to Twilio as binary frames."""
        try:
            # Send raw audio as binary WebSocket message
            await self.websocket.send_bytes(audio_data)
        except Exception as e:
            logger.error(f"Error sending audio: {e}")
    
    async def send_mark(self, mark_name: str):
        """Send a mark event to track speech segments."""
        if not self.relay_id:
            return
            
        mark_message = {
            "event": "mark",
            "relayId": self.relay_id,
            "mark": {
                "name": mark_name
            }
        }
        
        try:
            await self.websocket.send_json(mark_message)
        except Exception as e:
            logger.error(f"Error sending mark: {e}")
    
    async def _send_tts_with_tracking(self, text: str):
        """Send TTS audio with tracking for barge-in detection."""
        try:
            # Mark TTS as playing
            self.is_playing_tts = True
            
            # Generate unique mark name
            mark_name = f"tts_{int(time.time() * 1000)}"
            self.last_mark_name = mark_name
            
            # Convert text to speech
            audio_data = await self.audio_processor.text_to_speech(text)
            if audio_data:
                # Send audio
                await self.send_audio(audio_data)
                
                # Send mark to track when playback completes
                await self.send_mark(mark_name)
                
        except asyncio.CancelledError:
            logger.info(f"TTS task cancelled due to barge-in for call {self.call_sid}")
            self.is_playing_tts = False
            raise
        except Exception as e:
            logger.error(f"Error in TTS tracking: {e}")
            self.is_playing_tts = False
    
    async def run(self):
        """Main event loop for handling ConversationRelay messages."""
        self.is_running = True
        
        try:
            async for message in self.websocket.iter_json():
                if not self.is_running:
                    break
                
                # Log the raw message for debugging
                logger.debug(f"Received message: {json.dumps(message)}")
                    
                event_type = message.get("event")
                
                if event_type == "connected":
                    logger.info(f"WebSocket connected event received")
                elif event_type == "start":
                    await self.handle_start(message)
                elif event_type == "media":
                    await self.handle_media(message)
                elif event_type == "mark":
                    await self.handle_mark(message)
                elif event_type == "stop":
                    await self.handle_stop(message)
                elif event_type == "error":
                    logger.error(f"Twilio error: {message}")
                else:
                    logger.warning(f"Unknown event type: {event_type}, full message: {json.dumps(message)}")
                    
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for call {self.call_sid}")
        except Exception as e:
            logger.error(f"Error in ConversationRelay handler: {e}")
        finally:
            self.is_running = False


@router.websocket("/conversation-relay")
async def conversation_relay_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for Twilio ConversationRelay.
    
    This endpoint handles bidirectional audio streaming using the
    ConversationRelay protocol, providing lower latency and better
    reliability than Media Streams.
    """
    await websocket.accept()
    
    # Create audio processor
    audio_processor = AudioProcessor()
    
    # Create and run handler
    handler = ConversationRelayHandler(websocket, audio_processor)
    await handler.run()