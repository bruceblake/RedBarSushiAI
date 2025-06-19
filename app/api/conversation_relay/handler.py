"""
WebSocket handler for Twilio ConversationRelay.

This module handles text-based communication with Twilio ConversationRelay.
When using <ConversationRelay url="...">, Twilio handles all audio processing:
- Twilio performs STT and sends transcribed text in "prompt" events
- We send text responses back, and Twilio performs TTS
"""

import json
import logging
import asyncio
from typing import Dict, Any, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db_async import get_db
from app.utils.agent_orchestration_async import async_agent_orchestrator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ConversationRelay"])


class ConversationRelayHandler:
    """Handles a ConversationRelay WebSocket connection."""
    
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.session_id: Optional[str] = None
        self.call_sid: Optional[str] = None
        self.is_running = False
        self.is_agent_speaking = False
        
    async def handle_setup(self, message: Dict[str, Any]):
        """Handle the setup event from Twilio ConversationRelay."""
        self.session_id = message.get("sessionId")
        self.call_sid = message.get("callSid")
        self.from_number = message.get("from")
        self.to_number = message.get("to")
        self.call_status = message.get("callStatus")
        
        logger.info(f"ConversationRelay setup - Session: {self.session_id}, Call: {self.call_sid}, Status: {self.call_status}")
        
        try:
            # Start a new conversation with the agent system
            await async_agent_orchestrator.start_new_conversation(
                self.call_sid or self.session_id,
                {"first_interaction": True}
            )
            logger.info(f"Agent orchestrator initialized for {self.call_sid}")
            
            # Check if we're using welcomeGreeting in TwiML
            # If not, send initial greeting
            if not message.get("welcomeGreeting"):
                greeting_response = await async_agent_orchestrator.process_voice_input(
                    self.call_sid or self.session_id, 
                    "", 
                    {"first_interaction": True}
                )
                
                greeting_text = greeting_response.get("text", "")
                if greeting_text:
                    await self.send_text(greeting_text)
                    logger.info(f"Sent initial greeting: {greeting_text[:100]}...")
            else:
                logger.info("Using welcomeGreeting from TwiML, skipping initial greeting")
        except Exception as e:
            logger.error(f"Error initializing agent for {self.call_sid}: {e}", exc_info=True)
    
    async def handle_prompt(self, message: Dict[str, Any]):
        """Handle prompt events containing transcribed caller speech."""
        voice_prompt = message.get("voicePrompt", "")
        lang = message.get("lang", "en-US")
        is_last = message.get("last", False)
        
        logger.info(f"Caller said: '{voice_prompt}' (lang: {lang}, last: {is_last})")
        
        if not voice_prompt:
            return
            
        try:
            # Get FSM state before processing
            fsm = await async_agent_orchestrator.get_fsm(self.call_sid)
            state_before = fsm.current_state.name if fsm else "UNKNOWN"
            logger.info(f"FSM State BEFORE prompt: {state_before}")
            
            # Process the transcribed text with the agent
            response = await async_agent_orchestrator.process_voice_input(
                self.call_sid, voice_prompt
            )
            
            # Get FSM state after processing
            fsm = await async_agent_orchestrator.get_fsm(self.call_sid)
            state_after = fsm.current_state.name if fsm else "UNKNOWN"
            current_agent = response.get("agent", "Unknown")
            
            logger.info(f"FSM State AFTER prompt: {state_after} (handled by {current_agent})")
            
            response_text = response.get("text", "")
            if response_text:
                logger.info(f"Agent response: {response_text[:100]}...")
                # Send the text response back to Twilio for TTS
                await self.send_text(response_text)
            else:
                logger.warning(f"No response from agent for {self.call_sid}")
                
        except Exception as e:
            logger.error(f"Error processing prompt: {e}", exc_info=True)
            # Send a fallback message
            await self.send_text("I'm sorry, I'm having trouble understanding. Could you please repeat that?")
    
    async def handle_interrupt(self, message: Dict[str, Any]):
        """Handle interrupt events when caller speaks during TTS playback."""
        reason = message.get("reason")
        utterance_until_interrupt = message.get("utteranceUntilInterrupt", "")
        
        logger.info(f"Interrupt received - reason: {reason}, AI said up to: '{utterance_until_interrupt}'")
        
        # Signal the agent system about the interruption
        try:
            await async_agent_orchestrator.handle_interruption(self.call_sid)
        except Exception as e:
            logger.error(f"Error handling interruption: {e}")
        
        self.is_agent_speaking = False
    
    async def handle_dtmf(self, message: Dict[str, Any]):
        """Handle DTMF (touch-tone) events."""
        digit = message.get("digit")
        logger.info(f"DTMF digit received: {digit}")
        
        # Process DTMF input if needed
        # For now, just log it
    
    async def handle_error(self, message: Dict[str, Any]):
        """Handle error events from Twilio."""
        error_code = message.get("errorCode")
        error_message = message.get("errorMessage")
        logger.error(f"Twilio error - Code: {error_code}, Message: {error_message}")
    
    async def send_text(self, text: str, is_last: bool = True):
        """
        Send text to Twilio for TTS conversion.
        
        Args:
            text: The text to be spoken
            is_last: Whether this is the last token for this response
        """
        try:
            text_message = {
                "type": "text",
                "token": text,
                "last": is_last
            }
            
            logger.info(f"Sending text to Twilio: '{text[:50]}...' (last: {is_last})")
            await self.websocket.send_json(text_message)
            
            if is_last:
                self.is_agent_speaking = False
            else:
                self.is_agent_speaking = True
                
        except Exception as e:
            logger.error(f"Error sending text: {e}", exc_info=True)
    
    async def send_language_change(self, language: str, tts_language: str = None):
        """Change the language settings mid-call."""
        try:
            language_message = {
                "type": "language",
                "language": language
            }
            if tts_language:
                language_message["ttsLanguage"] = tts_language
                
            await self.websocket.send_json(language_message)
            logger.info(f"Changed language to: {language}")
        except Exception as e:
            logger.error(f"Error changing language: {e}")
    
    async def send_play_audio(self, audio_url: str):
        """Play an audio file (MP3/WAV) from a URL."""
        try:
            play_message = {
                "type": "play",
                "audioUrl": audio_url
            }
            await self.websocket.send_json(play_message)
            logger.info(f"Playing audio: {audio_url}")
        except Exception as e:
            logger.error(f"Error playing audio: {e}")
    
    async def send_end(self):
        """End the conversation gracefully."""
        try:
            end_message = {
                "type": "end"
            }
            await self.websocket.send_json(end_message)
            logger.info("Sent end message to close conversation")
        except Exception as e:
            logger.error(f"Error sending end message: {e}")
    
    async def run(self):
        """Main event loop for handling ConversationRelay messages."""
        self.is_running = True
        
        try:
            logger.info(f"Starting ConversationRelay handler")
            
            while self.is_running:
                try:
                    # Check if WebSocket is still connected
                    if self.websocket.client_state.value != 1:  # 1 = CONNECTED
                        logger.info("WebSocket disconnected, stopping handler")
                        break
                        
                    # Receive JSON messages from Twilio
                    message = await self.websocket.receive_json()
                    
                    # Log the message for debugging
                    logger.debug(f"Received: {json.dumps(message)}")
                    
                    # Route based on message type
                    message_type = message.get("type")
                    
                    if message_type == "setup":
                        await self.handle_setup(message)
                    elif message_type == "prompt":
                        await self.handle_prompt(message)
                    elif message_type == "interrupt":
                        await self.handle_interrupt(message)
                    elif message_type == "dtmf":
                        await self.handle_dtmf(message)
                    elif message_type == "error":
                        await self.handle_error(message)
                    else:
                        logger.warning(f"Unknown message type: {message_type}")
                        
                except WebSocketDisconnect:
                    logger.info(f"WebSocket disconnected for {self.call_sid}")
                    break
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {e}")
                except Exception as e:
                    logger.error(f"Error in message loop: {e}", exc_info=True)
                    
        except Exception as e:
            logger.error(f"Error in ConversationRelay handler: {e}", exc_info=True)
        finally:
            self.is_running = False
            logger.info(f"ConversationRelay handler finished for {self.call_sid}")


@router.websocket("/conversation-relay")
async def conversation_relay_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for Twilio ConversationRelay.
    
    This endpoint handles text-based communication with Twilio's
    ConversationRelay service, where Twilio manages all audio
    processing (STT/TTS).
    """
    try:
        await websocket.accept()
        logger.info("ConversationRelay WebSocket connection accepted")
        
        # Create and run handler
        handler = ConversationRelayHandler(websocket)
        await handler.run()
        
    except WebSocketDisconnect:
        logger.info("ConversationRelay WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error in WebSocket endpoint: {e}", exc_info=True)
    finally:
        logger.info("ConversationRelay WebSocket endpoint finished")