import asyncio
import base64
import json
import logging
import os
from typing import Any, Dict, List, Optional, Union, Callable
import websockets
from websockets.exceptions import ConnectionClosed

logging.basicConfig(level=logging.DEBUG if os.getenv("LOG_LEVEL") == "DEBUG" else logging.INFO)
logger = logging.getLogger("enhanced_realtime")

class OpenAIRealtimeClient:
    """Enhanced client for the OpenAI Realtime API with detailed error handling and logging."""
    
    WEBSOCKET_URL = "wss://api.openai.com/v1/realtime"
    
    def __init__(self, call_sid: str, model: str = "gpt-4o-realtime-preview-2024-10-01"):
        self.call_sid = call_sid
        self.model = model
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.ws = None
        self.connected = False
        self.closing = False
        self.event_processor = None
        self.session_id = None
        logger.info(f"[{call_sid}] Enhanced OpenAI Realtime client initialized with model: {model}")
        logger.debug(f"[{call_sid}] API key configured: {'Yes' if self.api_key else 'NO - WILL FAIL'}")
    
    def register_event_processor(self, event_processor: Any):
        """Register an event processor for OpenAI Realtime events."""
        self.event_processor = event_processor
        logger.info(f"[{self.call_sid}] Event processor registered")
    
    async def connect(self) -> bool:
        """Connect to the OpenAI Realtime API with enhanced error handling."""
        logger.info(f"[{self.call_sid}] Attempting to connect to OpenAI Realtime API at {self.WEBSOCKET_URL}...")
        
        if not self.api_key:
            logger.error(f"[{self.call_sid}] OPENAI_API_KEY is not configured. Cannot connect to OpenAI Realtime API.")
            await self.event_processor.on_error({"error": "OpenAI API Key not configured", "call_sid": self.call_sid})
            return False

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "OpenAI-Beta": "realtime=v1"
        }
        
        params = {"model": self.model}
        url = f"{self.WEBSOCKET_URL}?model={self.model}"
        
        try:
            logger.debug(f"[{self.call_sid}] Opening WebSocket connection to {url}")
            self.ws = await websockets.connect(url, extra_headers=headers)
            logger.info(f"[{self.call_sid}] Successfully connected to OpenAI Realtime API")
            self.connected = True
            return True
        except websockets.exceptions.InvalidStatusCode as e:
            if e.status_code == 401:
                logger.error(f"[{self.call_sid}] Authentication failed: Invalid API key (status 401)")
                await self.event_processor.on_error({"error": "Authentication failed: Invalid API key", "call_sid": self.call_sid})
            else:
                logger.error(f"[{self.call_sid}] Failed to connect to OpenAI Realtime API: Status {e.status_code} - {str(e)}")
                await self.event_processor.on_error({"error": f"Connection failed with status {e.status_code}", "call_sid": self.call_sid})
            return False
        except Exception as e:
            logger.error(f"[{self.call_sid}] Failed to connect to OpenAI Realtime API: {str(e)}")
            await self.event_processor.on_error({"error": f"Connection failed: {str(e)}", "call_sid": self.call_sid})
            return False
    
    async def send_event(self, event: Dict[str, Any]) -> bool:
        """Send an event to the OpenAI Realtime API with error handling."""
        if not self.ws or not self.connected:
            logger.error(f"[{self.call_sid}] Cannot send event: Not connected to OpenAI Realtime API")
            return False
            
        try:
            event_json = json.dumps(event)
            logger.debug(f"[{self.call_sid}] Sending event: {event_json}")
            await self.ws.send(event_json)
            return True
        except Exception as e:
            logger.error(f"[{self.call_sid}] Failed to send event to OpenAI Realtime API: {str(e)}")
            await self.event_processor.on_error({"error": f"Failed to send event: {str(e)}", "call_sid": self.call_sid})
            return False
    
    async def initialize_session(self, tools: Optional[List[Dict[str, Any]]] = None):
        """Initialize the Realtime session with detailed error handling."""
        logger.info(f"[{self.call_sid}] Initializing OpenAI Realtime session with tools: {tools is not None}")
        
        # Prepare session configuration
        session_update = {
            "session": {
                "audio": {
                    "input": {
                        "sample_rate": 8000,
                        "encoding": "mulaw",
                        "channels": 1
                    }
                },
                "vad": {
                    "enabled": True,
                    "speaking_threshold_seconds": 0.5,
                    "silence_threshold_seconds": 1.0
                },
                "output_format": {
                    "audio": {
                        "encoding": "mulaw",
                        "sample_rate": 8000
                    }
                },
                "tts": {
                    "voice": "shimmer"
                }
            }
        }
        
        # Add tools if provided
        if tools:
            session_update["session"]["tools"] = {"tools": tools}
        
        # Send session update event
        success = await self.send_event({"type": "session.update", "data": session_update})
        if not success:
            logger.error(f"[{self.call_sid}] Failed to initialize session")
            return
        
        logger.info(f"[{self.call_sid}] Session initialization request sent successfully")
    
    async def send_audio(self, audio_data: bytes):
        """Send audio data to the OpenAI Realtime API."""
        if not self.ws or not self.connected:
            logger.debug(f"[{self.call_sid}] Cannot send audio: Not connected")
            return
            
        if self.closing:
            logger.debug(f"[{self.call_sid}] Cannot send audio: Connection is closing")
            return
            
        try:
            # Encode audio data to base64
            audio_base64 = base64.b64encode(audio_data).decode("utf-8")
            
            # Send audio event
            await self.send_event({
                "type": "input_audio_buffer.append",
                "data": {
                    "audio_data": audio_base64
                }
            })
        except Exception as e:
            logger.error(f"[{self.call_sid}] Error sending audio: {str(e)}")
    
    async def create_conversation_item(self, role: str, content: str, type_: str = "text"):
        """Create a new conversation item."""
        logger.info(f"[{self.call_sid}] Creating conversation item: {role} - {type_} - {content[:30]}...")
        await self.send_event({
            "type": "conversation.item.create",
            "data": {
                "type": type_,
                "role": role,
                "content": content
            }
        })
    
    async def create_response(self):
        """Request a response from the model."""
        logger.info(f"[{self.call_sid}] Requesting response from model")
        await self.send_event({
            "type": "response.create",
            "data": {}
        })
    
    async def send_function_output(self, function_name: str, output: Dict[str, Any]):
        """Send function output back to the OpenAI Realtime API."""
        logger.info(f"[{self.call_sid}] Sending function output for {function_name}")
        await self.send_event({
            "type": "conversation.item.create",
            "data": {
                "type": "function_call_output",
                "function_name": function_name,
                "content": json.dumps(output)
            }
        })
    
    async def listen_for_events(self):
        """Listen for events from the OpenAI Realtime API with detailed error handling."""
        if not self.ws:
            logger.error(f"[{self.call_sid}] Cannot listen for events: Not connected to OpenAI Realtime API")
            return
            
        logger.info(f"[{self.call_sid}] Starting to listen for events from OpenAI Realtime API")
        
        try:
            async for message in self.ws:
                try:
                    event = json.loads(message)
                    event_type = event.get("type")
                    
                    # Extract and store session ID from the first event
                    if not self.session_id and event.get("session_id"):
                        self.session_id = event.get("session_id")
                        logger.info(f"[{self.call_sid}] Session ID received: {self.session_id}")
                    
                    # Debug log for each event type
                    if event_type == "response.audio.delta":
                        logger.debug(f"[{self.call_sid}] Received audio chunk from OpenAI")
                    elif event_type == "transcript.final":
                        logger.info(f"[{self.call_sid}] Final transcript: {event.get('data', {}).get('text', '')}")
                    else:
                        logger.debug(f"[{self.call_sid}] Received event: {event_type}")
                        if event_type == "error" or (event_type == "session.update" and event.get("status") == "error"):
                            error_data = event.get("data", {})
                            error_msg = error_data.get("message", "Unknown error")
                            logger.error(f"[{self.call_sid}] OpenAI API Error: {error_msg}")
                    
                    # Process event if we have an event processor
                    if self.event_processor:
                        await self.event_processor.process_event(event)
                    
                except json.JSONDecodeError:
                    logger.error(f"[{self.call_sid}] Received invalid JSON from OpenAI Realtime API")
                except Exception as e:
                    logger.error(f"[{self.call_sid}] Error processing event: {str(e)}")
        
        except ConnectionClosed as e:
            if self.closing:
                logger.info(f"[{self.call_sid}] WebSocket connection closed cleanly")
            else:
                logger.error(f"[{self.call_sid}] WebSocket connection closed unexpectedly: code={e.code}, reason={e.reason}")
                await self.event_processor.on_error({"error": "Connection closed unexpectedly", "code": e.code, "reason": e.reason})
        except Exception as e:
            logger.error(f"[{self.call_sid}] Error in event listener: {str(e)}")
            await self.event_processor.on_error({"error": f"Event listener error: {str(e)}"})
        finally:
            logger.info(f"[{self.call_sid}] Event listener stopped")
            self.connected = False
    
    async def close(self):
        """Close the WebSocket connection."""
        logger.info(f"[{self.call_sid}] Closing WebSocket connection")
        self.closing = True
        
        if self.ws:
            try:
                await self.ws.close()
                logger.info(f"[{self.call_sid}] WebSocket connection closed successfully")
            except Exception as e:
                logger.error(f"[{self.call_sid}] Error closing WebSocket connection: {str(e)}")
            finally:
                self.ws = None
                self.connected = False
                self.closing = False