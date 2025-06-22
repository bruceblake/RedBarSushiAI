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
import traceback
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.db_async import get_db
from app.utils.agent_orchestration_async import async_agent_orchestrator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ConversationRelay"])

# Log router creation
logger.critical("🚀 ConversationRelay router created at module load time")


@router.get("/test")
async def test_endpoint():
    """
    Simple test endpoint to verify the router is working.
    """
    logger.critical("🧪 TEST HTTP ENDPOINT CALLED")
    logger.critical(f"  - Timestamp: {datetime.now().isoformat()}")
    
    return {
        "status": "ok",
        "message": "ConversationRelay router is working!",
        "timestamp": datetime.now().isoformat(),
        "endpoints": [
            "/api/test (GET) - This endpoint",
            "/api/conversation-relay (WebSocket) - Main ConversationRelay endpoint",
            "/api/test-websocket (WebSocket) - Test WebSocket endpoint"
        ]
    }


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
        logger.critical("=" * 80)
        logger.critical("🎯 SETUP EVENT RECEIVED")
        logger.critical(f"Timestamp: {datetime.now().isoformat()}")
        logger.critical(f"Full setup message JSON: {json.dumps(message, indent=2)}")
        logger.critical("=" * 80)
        
        self.session_id = message.get("sessionId")
        self.call_sid = message.get("callSid")
        self.from_number = message.get("from")
        self.to_number = message.get("to")
        self.call_status = message.get("callStatus")
        
        logger.critical(f"📋 Setup details extracted:")
        logger.critical(f"  - Session ID: {self.session_id}")
        logger.critical(f"  - Call SID: {self.call_sid}")
        logger.critical(f"  - From Number: {self.from_number}")
        logger.critical(f"  - To Number: {self.to_number}")
        logger.critical(f"  - Call Status: {self.call_status}")
        logger.critical(f"  - Welcome Greeting: {message.get('welcomeGreeting')}")
        
        try:
            # Start a new conversation with the agent system
            logger.critical(f"🎬 Starting new conversation with orchestrator...")
            await async_agent_orchestrator.start_new_conversation(
                self.call_sid or self.session_id,
                {"first_interaction": True}
            )
            logger.critical(f"✅ Agent orchestrator initialized successfully for call SID: {self.call_sid}")
            
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
                    logger.critical(f"💬 Greeting response from orchestrator:")
                    logger.critical(f"  - Full text: {greeting_text}")
                    logger.critical(f"  - Response data: {json.dumps(greeting_response, indent=2)}")
                    await self.send_text(greeting_text)
                    logger.critical(f"✅ Initial greeting sent successfully")
            else:
                logger.info("Using welcomeGreeting from TwiML, skipping initial greeting")
        except Exception as e:
            logger.critical(f"❌ ERROR initializing agent for {self.call_sid}")
            logger.critical(f"  - Error type: {type(e).__name__}")
            logger.critical(f"  - Error message: {str(e)}")
            logger.critical(f"  - Stack trace:\n{traceback.format_exc()}")
    
    async def handle_prompt(self, message: Dict[str, Any]):
        """Handle prompt events containing transcribed caller speech."""
        logger.critical("=" * 80)
        logger.critical("🎙️ PROMPT EVENT RECEIVED - CALLER SPOKE!")
        logger.critical(f"Timestamp: {datetime.now().isoformat()}")
        logger.critical(f"Full prompt message JSON: {json.dumps(message, indent=2)}")
        
        voice_prompt = message.get("voicePrompt", "")
        lang = message.get("lang", "en-US")
        is_last = message.get("last", False)
        
        logger.critical(f"📝 Extracted prompt details:")
        logger.critical(f"  - Voice Prompt (TRANSCRIPT): '{voice_prompt}'")
        logger.critical(f"  - Language: {lang}")
        logger.critical(f"  - Is Last: {is_last}")
        logger.critical(f"  - Prompt Length: {len(voice_prompt)} chars")
        logger.critical("=" * 80)
        
        if not voice_prompt:
            logger.critical("⚠️ Empty voice prompt received, skipping processing")
            return
            
        try:
            # Get FSM state before processing
            logger.critical("🔍 Getting FSM state BEFORE processing...")
            try:
                fsm = await async_agent_orchestrator.get_fsm(self.call_sid)
                state_before = fsm.current_state.name if fsm else "UNKNOWN"
                logger.critical(f"📊 FSM State BEFORE: {state_before}")
            except Exception as e:
                logger.critical(f"❌ Error getting FSM state: {e}")
                state_before = "ERROR"
            
            logger.critical(f"📤 Sending to orchestrator: '{voice_prompt}'")
            
            # Process the transcribed text with the agent
            logger.critical(f"🤖 Processing voice input with orchestrator...")
            response = await async_agent_orchestrator.process_voice_input(
                self.call_sid, voice_prompt
            )
            logger.critical(f"✅ Orchestrator processing complete")
            
            # Get FSM state after processing
            logger.critical("🔍 Getting FSM state AFTER processing...")
            try:
                fsm = await async_agent_orchestrator.get_fsm(self.call_sid)
                state_after = fsm.current_state.name if fsm else "UNKNOWN"
            except Exception as e:
                logger.critical(f"❌ Error getting FSM state: {e}")
                state_after = "ERROR"
                
            current_agent = response.get("agent", "Unknown")
            
            logger.critical(f"📊 Orchestrator response received:")
            logger.critical(f"  - FSM State AFTER: {state_after}")
            logger.critical(f"  - Agent Used: {current_agent}")
            logger.critical(f"  - Full Response: {json.dumps(response, indent=2)}")
            
            response_text = response.get("text", "")
            if response_text:
                logger.critical(f"🗣️ Agent response text to be spoken:")
                logger.critical(f"  - Full text: {response_text}")
                logger.critical(f"  - Text length: {len(response_text)} chars")
                # Send the text response back to Twilio for TTS
                await self.send_text(response_text)
                logger.critical(f"✅ Response sent to Twilio for TTS")
            else:
                logger.critical(f"⚠️ NO RESPONSE TEXT from agent for call SID: {self.call_sid}")
                logger.critical(f"  - Response object: {json.dumps(response)}")
                
        except Exception as e:
            logger.critical(f"❌ ERROR processing prompt for call {self.call_sid}")
            logger.critical(f"  - Error type: {type(e).__name__}")
            logger.critical(f"  - Error message: {str(e)}")
            logger.critical(f"  - Voice prompt was: '{voice_prompt}'")
            logger.critical(f"  - Full stack trace:\n{traceback.format_exc()}")
            # Send a fallback message
            try:
                await self.send_text("I'm sorry, I'm having trouble understanding. Could you please repeat that?")
                logger.critical("✅ Sent fallback message due to error")
            except Exception as send_error:
                logger.critical(f"❌ Failed to send fallback message: {send_error}")
    
    async def handle_interrupt(self, message: Dict[str, Any]):
        """Handle interrupt events when caller speaks during TTS playback."""
        logger.critical("=" * 80)
        logger.critical("🛑 INTERRUPT EVENT RECEIVED - CALLER INTERRUPTED!")
        logger.critical(f"Timestamp: {datetime.now().isoformat()}")
        logger.critical(f"Full interrupt message JSON: {json.dumps(message, indent=2)}")
        
        reason = message.get("reason")
        utterance_until_interrupt = message.get("utteranceUntilInterrupt", "")
        
        logger.critical(f"🛑 Interrupt details:")
        logger.critical(f"  - Reason: {reason}")
        logger.critical(f"  - AI said up to: '{utterance_until_interrupt}'")
        logger.critical(f"  - Length of interrupted speech: {len(utterance_until_interrupt)} chars")
        logger.critical("=" * 80)
        
        # Signal the agent system about the interruption
        try:
            logger.critical("📤 Signaling orchestrator about interruption...")
            await async_agent_orchestrator.handle_interruption(self.call_sid)
            logger.critical("✅ Interruption handled by orchestrator")
        except Exception as e:
            logger.critical(f"❌ Error handling interruption: {e}\n{traceback.format_exc()}")
        
        self.is_agent_speaking = False
    
    async def handle_dtmf(self, message: Dict[str, Any]):
        """Handle DTMF (touch-tone) events."""
        digit = message.get("digit")
        logger.critical(f"☎️ DTMF digit received: {digit}")
        logger.critical(f"Full DTMF message: {json.dumps(message, indent=2)}")
        
        # Process DTMF input if needed
        # For now, just log it
    
    async def handle_error(self, message: Dict[str, Any]):
        """Handle error events from Twilio."""
        error_code = message.get("errorCode")
        error_message = message.get("errorMessage")
        logger.critical(f"❌ TWILIO ERROR EVENT")
        logger.critical(f"  - Error Code: {error_code}")
        logger.critical(f"  - Error Message: {error_message}")
        logger.critical(f"  - Full error data: {json.dumps(message, indent=2)}")
    
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
                "text": text,  # Corrected from "token" to "text"
                "last": is_last
            }
            
            logger.critical(f"📤 Sending text message to Twilio:")
            logger.critical(f"  - Message type: text")
            logger.critical(f"  - Full text: {text}")
            logger.critical(f"  - Text length: {len(text)} chars")
            logger.critical(f"  - Is last token: {is_last}")
            logger.critical(f"  - JSON being sent: {json.dumps(text_message, indent=2)}")
            logger.critical(f"  - WebSocket state before send: {self.websocket.client_state}")
            await self.websocket.send_json(text_message)
            logger.critical(f"  - WebSocket state after send: {self.websocket.client_state}")
            
            if is_last:
                self.is_agent_speaking = False
            else:
                self.is_agent_speaking = True
                
        except Exception as e:
            logger.critical(f"❌ ERROR sending text to Twilio")
            logger.critical(f"  - Error type: {type(e).__name__}")
            logger.critical(f"  - Error message: {str(e)}")
            logger.critical(f"  - Text attempted: {text}")
            logger.critical(f"  - Stack trace:\n{traceback.format_exc()}")
    
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
        logger.critical("="*80)
        logger.critical("🏃 HANDLER RUN() METHOD STARTED")
        logger.critical(f"Timestamp: {datetime.now().isoformat()}")
        logger.critical(f"WebSocket state: {self.websocket.client_state}")
        logger.critical("="*80)
        self.is_running = True
        
        try:
            logger.critical(f"🚀 Starting ConversationRelay handler message loop")
            message_count = 0
            
            while self.is_running:
                try:
                    # Receive JSON messages from Twilio
                    logger.critical(f"⏳ Waiting for message #{message_count + 1} from WebSocket...")
                    logger.critical(f"  - WebSocket state: {self.websocket.client_state}")
                    message = await self.websocket.receive_json()
                    message_count += 1
                    
                    # Log the message for debugging
                    logger.critical("="*60)
                    logger.critical(f"📨 MESSAGE #{message_count} RECEIVED")
                    logger.critical(f"  - Timestamp: {datetime.now().isoformat()}")
                    logger.critical(f"  - Event loop time: {asyncio.get_event_loop().time()}")
                    logger.critical(f"  - Message type: {message.get('type', 'UNKNOWN')}")
                    logger.critical(f"  - Full message: {json.dumps(message, indent=2)}")
                    logger.critical("="*60)
                    
                    # Route based on message type
                    message_type = message.get("type")
                    logger.critical(f"🔀 Routing message type: {message_type}")
                    
                    try:
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
                            logger.critical(f"⚠️ UNKNOWN MESSAGE TYPE: {message_type}")
                            logger.critical(f"Full unknown message: {json.dumps(message, indent=2)}")
                    except Exception as handler_error:
                        logger.critical(f"❌ Error in message handler for type {message_type}")
                        logger.critical(f"  - Error: {handler_error}")
                        logger.critical(f"  - Stack trace:\n{traceback.format_exc()}")
                        
                except WebSocketDisconnect:
                    logger.critical(f"🔌 WebSocket DISCONNECTED for call {self.call_sid}")
                    logger.critical(f"  - Total messages processed: {message_count}")
                    break
                except json.JSONDecodeError as e:
                    logger.critical(f"❌ Invalid JSON received: {e}")
                    logger.critical(f"  - Raw data: {e.doc if hasattr(e, 'doc') else 'N/A'}")
                except Exception as e:
                    logger.critical(f"❌ ERROR in message loop")
                    logger.critical(f"  - Error type: {type(e).__name__}")
                    logger.critical(f"  - Error message: {str(e)}")
                    logger.critical(f"  - Stack trace:\n{traceback.format_exc()}")
                    
        except Exception as e:
            logger.critical(f"❌ FATAL ERROR in ConversationRelay handler")
            logger.critical(f"  - Error type: {type(e).__name__}")
            logger.critical(f"  - Error message: {str(e)}")
            logger.critical(f"  - Stack trace:\n{traceback.format_exc()}")
        finally:
            self.is_running = False
            logger.critical(f"🏁 ConversationRelay handler FINISHED for call {self.call_sid}")
            logger.critical(f"  - Final WebSocket state: {getattr(self.websocket, 'client_state', 'UNKNOWN')}")


@router.websocket("/test-websocket")
async def test_websocket_endpoint(websocket: WebSocket):
    """
    Simple test WebSocket endpoint to verify WebSocket functionality.
    """
    logger.critical("🧪 TEST WEBSOCKET ENDPOINT CALLED")
    logger.critical(f"  - Timestamp: {datetime.now().isoformat()}")
    
    try:
        await websocket.accept()
        logger.critical("✅ Test WebSocket connection accepted")
        
        # Send a test message
        test_message = {
            "type": "test",
            "message": "WebSocket connection is working!",
            "timestamp": datetime.now().isoformat()
        }
        await websocket.send_json(test_message)
        logger.critical(f"📤 Sent test message: {json.dumps(test_message)}")
        
        # Wait for and echo any messages
        while True:
            try:
                data = await websocket.receive_json()
                logger.critical(f"📨 Test WebSocket received: {json.dumps(data)}")
                
                # Echo back with timestamp
                echo_message = {
                    "type": "echo",
                    "original": data,
                    "timestamp": datetime.now().isoformat()
                }
                await websocket.send_json(echo_message)
                logger.critical(f"🔁 Echoed back: {json.dumps(echo_message)}")
                
            except WebSocketDisconnect:
                logger.critical("🔌 Test WebSocket disconnected")
                break
                
    except Exception as e:
        logger.critical(f"❌ Test WebSocket error: {e}\n{traceback.format_exc()}")
    finally:
        logger.critical("🏁 Test WebSocket endpoint finished")


@router.websocket("/conversation-relay")
async def conversation_relay_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for Twilio ConversationRelay.
    
    This endpoint handles text-based communication with Twilio's
    ConversationRelay service, where Twilio manages all audio
    processing (STT/TTS).
    """
    logger.critical("🎯 WEBSOCKET ENDPOINT CALLED - BEFORE ACCEPT")
    logger.critical(f"  - Timestamp: {datetime.now().isoformat()}")
    logger.critical(f"  - WebSocket object: {websocket}")
    logger.critical(f"  - Initial state: {getattr(websocket, 'client_state', 'NO STATE')}")
    
    try:
        logger.critical("🔌 Attempting to accept WebSocket connection...")
        await websocket.accept()
        logger.critical("★" * 80)
        logger.critical("✅ NEW CONVERSATIONRELAY WEBSOCKET CONNECTION ACCEPTED")
        logger.critical(f"  - Timestamp: {datetime.now().isoformat()}")
        logger.critical(f"  - Event loop time: {asyncio.get_event_loop().time()}")
        logger.critical(f"  - WebSocket state after accept: {websocket.client_state}")
        logger.critical(f"  - WebSocket headers: {dict(websocket.headers) if hasattr(websocket, 'headers') else 'N/A'}")
        logger.critical("★" * 80)
        
        # Create and run handler
        logger.critical("🏗️ Creating ConversationRelayHandler...")
        handler = ConversationRelayHandler(websocket)
        logger.critical(f"✅ Handler created: {handler}")
        
        logger.critical("🚀 Starting handler.run()...")
        await handler.run()
        logger.critical("✅ Handler.run() completed successfully")
        
    except WebSocketDisconnect:
        logger.critical("🔌 ConversationRelay WebSocket DISCONNECTED (in endpoint)")
    except Exception as e:
        logger.critical(f"❌ ERROR in WebSocket endpoint")
        logger.critical(f"  - Error type: {type(e).__name__}")
        logger.critical(f"  - Error message: {str(e)}")
        logger.critical(f"  - Stack trace:\n{traceback.format_exc()}")
    finally:
        logger.critical("🏁 ConversationRelay WebSocket endpoint FINISHED")
        logger.critical(f"  - Final timestamp: {datetime.now().isoformat()}")


@router.post("/debug-webhook")
async def debug_webhook(request: Request):
    """
    Debug endpoint to log any webhook calls from Twilio.
    This can help diagnose if Twilio is trying HTTP instead of WebSocket.
    """
    logger.critical("🔔 DEBUG WEBHOOK CALLED (HTTP POST)")
    logger.critical(f"  - Timestamp: {datetime.now().isoformat()}")
    
    # Try to get request body
    try:
        body = await request.body()
        logger.critical(f"  - Request body (raw): {body}")
        
        # Try to parse as JSON
        try:
            json_data = await request.json()
            logger.critical(f"  - Request data (JSON): {json.dumps(json_data, indent=2)}")
        except:
            logger.critical("  - Could not parse body as JSON")
            
    except Exception as e:
        logger.critical(f"  - Error reading request body: {e}")
    
    # Log headers
    logger.critical(f"  - Headers: {dict(request.headers)}")
    logger.critical(f"  - Method: {request.method}")
    logger.critical(f"  - URL: {request.url}")
    
    return {
        "error": "This is an HTTP endpoint, but ConversationRelay requires WebSocket",
        "websocket_url": "wss://<your-domain>/api/conversation-relay",
        "test_websocket_url": "wss://<your-domain>/api/test-websocket",
        "timestamp": datetime.now().isoformat()
    }