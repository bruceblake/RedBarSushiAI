"""
ConversationRelay WebSocket handler for Twilio voice calls.

This module implements the WebSocket handler for Twilio's ConversationRelay service,
which provides AI-powered voice interactions with built-in STT, TTS, and session management.
"""

import json
import asyncio
import time
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Path
from app.config import settings
from app.utils.enhanced_logging import get_logger
from app.utils.correlation_id import set_correlation_id, get_correlation_id

logger = get_logger(__name__)

router = APIRouter(tags=["ConversationRelay WebSocket"])


class ConversationRelayHandler:
    """Handles a Twilio ConversationRelay WebSocket connection."""
    
    def __init__(self, websocket: WebSocket, call_sid: str):
        self.websocket = websocket
        self.call_sid = call_sid
        self.session_id: Optional[str] = None
        self.is_running = False
        self.orchestrator = None
        
    async def send_text_response(self, text: str, final: bool = True) -> None:
        """
        Send a text response back to ConversationRelay for TTS.
        
        Args:
            text: The text to be converted to speech
            final: Whether this is the final response in the conversation turn
        """
        message = {
            "type": "text",
            "token": text,
            "last": final
        }
        
        await self.websocket.send_text(json.dumps(message))
        logger.info(f"[{self.call_sid}] Sent text response: '{text[:100]}...'")
    
    async def send_language_change(self, language_code: str) -> None:
        """
        Send a language change message to ConversationRelay.
        
        Args:
            language_code: The new language code (e.g., "en-US", "es-ES")
        """
        message = {
            "type": "language",
            "transcriptionLanguage": language_code,
            "ttsLanguage": language_code
        }
        
        await self.websocket.send_text(json.dumps(message))
        logger.info(f"[{self.call_sid}] Changed language to: {language_code}")
    
    async def send_dtmf_response(self, dtmf_digits: str) -> None:
        """
        Send a DTMF response (if needed for menu navigation).
        
        Args:
            dtmf_digits: The DTMF digits to send
        """
        message = {
            "type": "dtmf",
            "digit": dtmf_digits
        }
        
        await self.websocket.send_text(json.dumps(message))
        logger.info(f"[{self.call_sid}] Sent DTMF: {dtmf_digits}")
    
    async def end_session(self, handoff_data: Optional[Dict[str, Any]] = None) -> None:
        """
        End the ConversationRelay session.
        
        Args:
            handoff_data: Optional data to pass when ending the session
        """
        message = {
            "type": "end",
            "handoffData": handoff_data or {}
        }
        
        await self.websocket.send_text(json.dumps(message))
        logger.info(f"[{self.call_sid}] Ended session with handoff data: {handoff_data}")
    
    async def handle_setup_message(self, message: Dict[str, Any]) -> None:
        """Handle the initial setup message from ConversationRelay."""
        self.session_id = message.get("sessionId")
        custom_params = message.get("customParameters", {})
        
        logger.info(f"[{self.call_sid}] ConversationRelay session setup")
        logger.info(f"[{self.call_sid}] Session ID: {self.session_id}")
        logger.info(f"[{self.call_sid}] Custom Parameters: {custom_params}")
        logger.info(f"[{self.call_sid}] Language: {message.get('language', 'en-US')}")
        logger.info(f"[{self.call_sid}] TTS Provider: {message.get('ttsProvider', 'ElevenLabs')}")
        logger.info(f"[{self.call_sid}] Transcription Provider: {message.get('transcriptionProvider', 'Google')}")
        
        # Initialize the agent orchestrator
        try:
            from app.utils.agent_orchestration_async import async_agent_orchestrator
            self.orchestrator = async_agent_orchestrator
            
            # Start a new conversation
            await self.orchestrator.start_new_conversation(
                self.call_sid,
                {
                    "voice_mode": "conversation_relay",
                    "session_id": self.session_id,
                    "custom_parameters": custom_params,
                    "first_interaction": True
                }
            )
            logger.info(f"[{self.call_sid}] Conversation initialized with orchestrator")
            
            # Send initial greeting immediately after setup
            initial_response = await self.orchestrator.process_voice_input(
                self.call_sid,
                "",  # Empty input for initial greeting
                {
                    "voice_mode": "conversation_relay",
                    "session_id": self.session_id,
                    "first_interaction": True,
                    "skip_input_validation": True
                }
            )
            
            # Send the initial greeting to the customer
            response_text = initial_response.get("text", "")
            if response_text:
                await self.send_text_response(response_text)
                logger.info(f"[{self.call_sid}] Sent initial greeting: '{response_text[:100]}...'")
            else:
                # Fallback greeting if orchestrator doesn't provide one
                fallback_greeting = "Hello and welcome to Red Bar Sushi! How can I help you today?"
                await self.send_text_response(fallback_greeting)
                logger.warning(f"[{self.call_sid}] Used fallback greeting")
            
        except Exception as e:
            logger.error(f"[{self.call_sid}] Failed to initialize orchestrator: {e}", exc_info=True)
            # Send error response
            # AI is required - don't send hardcoded error messages
            logger.critical(f"[{self.call_sid}] System initialization failed - cannot continue without AI")
    
    async def handle_prompt_message(self, message: Dict[str, Any]) -> None:
        """Handle user speech transcripts from ConversationRelay."""
        transcript = message.get("voicePrompt", "")
        is_partial = message.get("partial", False)
        
        # Only process final transcripts, ignore partial ones for now
        if is_partial:
            logger.debug(f"[{self.call_sid}] Partial transcript: '{transcript}'")
            return
        
        logger.info(f"[{self.call_sid}] Final transcript received: '{transcript}'")
        
        if not self.orchestrator:
            logger.error(f"[{self.call_sid}] No orchestrator available")
            await self.send_text_response(
                "I'm sorry, I'm not ready to process your request yet."
            )
            return
        
        try:
            # Process the transcript with the orchestrator
            response = await self.orchestrator.process_voice_input(
                self.call_sid,
                transcript,
                {
                    "session_id": self.session_id,
                    "voice_mode": "conversation_relay"
                }
            )
            
            # Send the response back to ConversationRelay
            response_text = response.get("text", "")
            if response_text:
                await self.send_text_response(response_text)
            else:
                logger.warning(f"[{self.call_sid}] No response text from orchestrator")
                await self.send_text_response(
                    "I'm sorry, I didn't catch that. Could you repeat your request?"
                )
                
            # Handle any special actions
            actions = response.get("actions", [])
            for action in actions:
                if action.get("type") == "end_conversation":
                    await self.end_session({"reason": action.get("reason", "Conversation completed")})
                elif action.get("type") == "transfer_to_human":
                    await self.end_session({"reason": "Transfer to human agent requested"})
                    
        except Exception as e:
            logger.error(f"[{self.call_sid}] Error processing transcript: {e}", exc_info=True)
            await self.send_text_response(
                "I'm sorry, I encountered an error processing your request. Please try again."
            )
    
    async def handle_dtmf_message(self, message: Dict[str, Any]) -> None:
        """Handle DTMF input from ConversationRelay."""
        digit = message.get("digit", "")
        logger.info(f"[{self.call_sid}] DTMF received: {digit}")
        
        # Process DTMF with orchestrator if needed
        if self.orchestrator:
            try:
                response = await self.orchestrator.process_voice_input(
                    self.call_sid,
                    f"DTMF:{digit}",
                    {
                        "session_id": self.session_id,
                        "voice_mode": "conversation_relay",
                        "input_type": "dtmf"
                    }
                )
                
                response_text = response.get("text", "")
                if response_text:
                    await self.send_text_response(response_text)
                    
            except Exception as e:
                logger.error(f"[{self.call_sid}] Error processing DTMF: {e}", exc_info=True)
    
    async def handle_interrupt_message(self, message: Dict[str, Any]) -> None:
        """Handle user interruption during TTS playback."""
        logger.info(f"[{self.call_sid}] User interruption detected")
        
        # Notify orchestrator about interruption
        if self.orchestrator and hasattr(self.orchestrator, 'handle_interruption'):
            try:
                await self.orchestrator.handle_interruption(self.call_sid)
            except Exception as e:
                logger.error(f"[{self.call_sid}] Error handling interruption: {e}", exc_info=True)
    
    async def handle_debug_message(self, message: Dict[str, Any]) -> None:
        """Handle debug messages from ConversationRelay."""
        debug_type = message.get("debugType", "")
        debug_data = message.get("debugData", {})
        
        logger.debug(f"[{self.call_sid}] Debug message - Type: {debug_type}, Data: {debug_data}")
        
        # Handle specific debug events
        if debug_type == "agentSpeaking":
            logger.info(f"[{self.call_sid}] Agent started speaking")
        elif debug_type == "clientSpeaking":
            logger.info(f"[{self.call_sid}] Client started speaking")
        elif debug_type == "tokensPlayed":
            logger.info(f"[{self.call_sid}] TTS tokens played: {debug_data}")
    
    async def run(self):
        """Main event loop for handling ConversationRelay messages."""
        self.is_running = True
        logger.info(f"[{self.call_sid}] ConversationRelayHandler started")
        
        try:
            while self.is_running:
                message_json = await self.websocket.receive_text()
                message = json.loads(message_json)
                
                message_type = message.get("type")
                logger.debug(f"[{self.call_sid}] Received message type: {message_type}")
                
                # Route to appropriate handler
                if message_type == "setup":
                    await self.handle_setup_message(message)
                elif message_type == "prompt":
                    await self.handle_prompt_message(message)
                elif message_type == "dtmf":
                    await self.handle_dtmf_message(message)
                elif message_type == "interrupt":
                    await self.handle_interrupt_message(message)
                elif message_type == "debug":
                    await self.handle_debug_message(message)
                else:
                    logger.debug(f"[{self.call_sid}] Unknown message type: {message_type}")
                    
        except WebSocketDisconnect:
            logger.info(f"[{self.call_sid}] WebSocket disconnected by client")
        except Exception as e:
            logger.error(f"[{self.call_sid}] Error in ConversationRelayHandler: {e}", exc_info=True)
        finally:
            self.is_running = False
            
            # Clean up orchestrator session
            if self.orchestrator:
                try:
                    await self.orchestrator.cleanup_inactive_sessions(max_idle_time=0)  # Immediate cleanup
                except Exception as e:
                    logger.error(f"[{self.call_sid}] Error during orchestrator cleanup: {e}")
                    
            logger.info(f"[{self.call_sid}] ConversationRelayHandler finished")


@router.websocket("/conversation-relay/{call_sid}")
async def conversation_relay_endpoint(websocket: WebSocket, call_sid: str = Path(...)):
    """
    WebSocket endpoint for Twilio ConversationRelay.
    
    This endpoint handles AI-powered voice interactions using Twilio's
    ConversationRelay service, which provides built-in STT, TTS, and session management.
    
    Args:
        websocket: FastAPI WebSocket instance
        call_sid: Twilio call SID from the path parameter
    """
    logger.info(f"[{call_sid}] New ConversationRelay WebSocket connection attempt")
    
    try:
        await websocket.accept()
        logger.info(f"[{call_sid}] ConversationRelay WebSocket connection accepted")
        
        # Set correlation ID for this call
        set_correlation_id(call_sid)
        
        # Create handler
        handler = ConversationRelayHandler(
            websocket=websocket,
            call_sid=call_sid
        )
        
        logger.info(f"[{call_sid}] Starting ConversationRelayHandler.run()")
        
        # Run the handler
        await handler.run()
        
    except WebSocketDisconnect:
        logger.info(f"[{call_sid}] ConversationRelay WebSocket disconnected during endpoint handling")
    except Exception as e:
        logger.error(f"[{call_sid}] Error in ConversationRelay WebSocket endpoint: {e}", exc_info=True)
    finally:
        logger.info(f"[{call_sid}] ConversationRelay WebSocket endpoint cleanup complete")