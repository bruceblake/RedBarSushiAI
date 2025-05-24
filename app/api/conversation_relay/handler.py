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
        
    async def handle_start(self, message: Dict[str, Any]):
        """Handle the start event from Twilio."""
        self.relay_id = message.get("relayId")
        self.call_sid = message.get("callSid")
        self.stream_sid = message.get("streamSid")
        
        logger.info(f"ConversationRelay started - Relay: {self.relay_id}, Call: {self.call_sid}")
        
        # Start a new conversation
        greeting_response = await async_agent_orchestrator.start_new_conversation(
            self.call_sid,
            {"first_interaction": True}
        )
        
        greeting_text = greeting_response.get("text", "Welcome to Red Bar Sushi. How can I help you today?")
        
        # Convert greeting to audio and send
        audio_data = await self.audio_processor.text_to_speech(greeting_text)
        if audio_data:
            await self.send_audio(audio_data)
    
    async def handle_media(self, message: Dict[str, Any]):
        """Handle media events containing audio from the caller."""
        media = message.get("media", {})
        audio_payload = media.get("payload", "")
        
        if not audio_payload:
            return
            
        try:
            # Decode base64 audio
            audio_bytes = base64.b64decode(audio_payload)
            
            # Process audio through STT
            transcript = await self.audio_processor.speech_to_text(audio_bytes)
            
            if transcript:
                logger.info(f"Transcript: {transcript}")
                
                # Process with agent
                response = await async_agent_orchestrator.process_voice_input(
                    self.call_sid, transcript
                )
                
                response_text = response.get("text", "")
                if response_text:
                    # Convert to speech and send
                    audio_data = await self.audio_processor.text_to_speech(response_text)
                    if audio_data:
                        await self.send_audio(audio_data)
                        
        except Exception as e:
            logger.error(f"Error processing media: {e}")
    
    async def handle_mark(self, message: Dict[str, Any]):
        """Handle mark events indicating speech playback completion."""
        mark = message.get("mark", {})
        mark_name = mark.get("name", "")
        logger.debug(f"Mark received: {mark_name}")
    
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
    
    async def run(self):
        """Main event loop for handling ConversationRelay messages."""
        self.is_running = True
        
        try:
            async for message in self.websocket.iter_json():
                if not self.is_running:
                    break
                    
                event_type = message.get("event")
                
                if event_type == "start":
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
                    logger.warning(f"Unknown event type: {event_type}")
                    
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