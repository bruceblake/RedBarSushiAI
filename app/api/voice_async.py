"""
FastAPI routes for handling async voice interactions in RedBarSushiAI.
This module provides routes for handling Twilio voice calls and WebSocket connections.
"""

import json
import logging
import time
import base64
import traceback
import asyncio
from typing import Dict, List, Any, Optional, Union
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, Request, Response, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.status import HTTP_200_OK

from app.utils.agent_orchestration_async import async_agent_orchestrator
from app.utils.fsm_async import async_fsm_manager, ConversationState, ConversationEvent
from app.utils.twilio_twiml import generate_media_streams_twiml
from app.dependencies import get_connection_manager, ConnectionManager
from app.utils.twilio_twiml import TwimlParameter
from app.models.api import VoiceResponseModel as VoiceResponse
from twilio.twiml.voice_response import VoiceResponse as TwilioVoiceResponse
from app.config import settings

# Set up logging
logger = logging.getLogger(__name__)

# Create the router
router = APIRouter(prefix="/voice", tags=["voice"])

@router.on_event("startup")
async def startup_event():
    """Initialize the voice routes on startup."""
    await async_agent_orchestrator.initialize()
    logger.info("Voice routes initialized")

@router.post("/")
@router.post("/voice")
@router.post("/webhook/voice")
async def receive_call(request: Request) -> Response:
    """
    Primary webhook endpoint for Twilio calls with enhanced logging and TwiML generation.
    
    This endpoint receives incoming call information from Twilio and
    generates TwiML to establish the WebSocket connection for real-time audio.
    Implements comprehensive logging and optimized TwiML generation based on
    the production-proven Flask implementation.
    
    Args:
        request: The HTTP request from Twilio
        
    Returns:
        The TwiML response to send back to Twilio
    """
    import uuid
    import os
    import traceback
    from datetime import datetime
    
    # Create a log file for this specific call
    call_sid = (await request.form()).get("CallSid", str(uuid.uuid4()))
    
    # Set up extensive logging for call tracing
    try:
        # Log critical information about the webhook access
        logger.critical(f"***** WEBHOOK ENDPOINT ACCESSED SUCCESSFULLY: {request.url.path} *****")
        logger.info("==== INCOMING REALTIME CALL DETAILS ====")
        logger.info(f"Call SID: {call_sid}")
        logger.info(f"Request came from: {request.client.host}")
        logger.info(f"User agent: {request.headers.get('user-agent', 'unknown')}")
        logger.info(f"Host header: {request.headers.get('host', 'unknown')}")
        logger.info(f"URL: {request.url}")
        logger.info(f"Path: {request.url.path}")
        logger.info(f"Request method: {request.method}")
        logger.info(f"Environment: {os.environ.get('FASTAPI_ENV', 'undefined')}")
        logger.info(f"Current working directory: {os.getcwd()}")
        
        # Log all request headers for debugging (excluding sensitive ones)
        logger.info("Full request headers:")
        for header, value in request.headers.items():
            if header.lower() not in ("authorization", "cookie", "x-auth-token"):
                logger.info(f"  - {header}: {value}")
        
        # Get form data
        form_data = await request.form()
        
        # Log all request form values for debugging
        logger.info("Full request values:")
        for key, value in form_data.items():
            logger.info(f"  - {key}: {value}")
        
        # Extract call information
        call_sid = form_data.get("CallSid", "")
        caller = form_data.get("Caller", "")
        called = form_data.get("Called", "")
        
        logger.info(f"Received call: {call_sid} from {caller} to {called}")
        
        # Get environment name for greeting
        from app.utils.twilio_twiml import get_environment_name
        environment_name = get_environment_name()
        logger.info(f"Environment identified as: {environment_name}")
        
        # Determine the WebSocket host with extensive fallback logic
        host = request.headers.get("host", "localhost")
        
        # Check for ngrok tunnels
        if 'ngrok' in host:
            logger.info(f"[WEBSOCKET_HOST] Detected ngrok tunnel: Using actual host: {host}")
        
        # For development environment, use the actual host
        elif os.environ.get("FASTAPI_ENV") == "development":
            logger.info(f"[WEBSOCKET_HOST] Development mode: Using actual host: {host}")
        
        # For Render, use the public-facing hostname if available
        elif render_external_hostname := os.environ.get("RENDER_EXTERNAL_HOSTNAME"):
            logger.info(f"[WEBSOCKET_HOST] Using RENDER_EXTERNAL_HOSTNAME: {render_external_hostname}")
            host = render_external_hostname
        
        # For staging environment, use hardcoded hostname
        elif os.environ.get("IS_STAGING") or os.environ.get("FASTAPI_ENV") == "staging":
            staging_hostname = "redbarsushiai-staging.onrender.com"
            logger.info(f"[WEBSOCKET_HOST] Using hardcoded staging hostname: {staging_hostname}")
            host = staging_hostname
        
        # For production, also hardcode to ensure consistency
        elif os.environ.get("FASTAPI_ENV") == "production":
            production_hostname = "redbarsushi-web.onrender.com"
            logger.info(f"[WEBSOCKET_HOST] Using hardcoded production hostname: {production_hostname}")
            host = production_hostname
        
        # Get the URL scheme (http or https)
        scheme = request.url.scheme
        
        # Determine WebSocket scheme (ws or wss)
        ws_scheme = "wss" if scheme == "https" else "ws"
        
        # Generate optimized WebSocket URL with CallSid as path parameter for reliability
        websocket_url = f"{ws_scheme}://{host}/ws/media/{call_sid}"
        logger.critical(f"WebSocket URL for Twilio: {websocket_url}")
        
        # Create Stream parameters with production settings
        stream_params = TwimlStreamParameter(
            url=websocket_url,
            track="inbound_track",  # Only use inbound track for bidirectional streaming (Twilio best practice)
            name="media_stream"     # Consistent name for stream tracking
        )
        
        # Create welcome message based on environment
        greeting_msg = f"Welcome to {environment_name} Red Bar Sushi AI!"
        
        # Create TwiML parameters
        twiml_params = TwimlParameter(
            voice="Polly.Amy-Neural",
            language="en-US",
            greeting_text=greeting_msg,
            fallback_text="Sorry, we couldn't connect you to our AI assistant. Please try again later.",
            stream_params=stream_params,
            call_sid=call_sid
        )
        
        # Generate TwiML response
        from app.utils.twilio_twiml import generate_media_streams_twiml
        twiml = generate_media_streams_twiml(twiml_params)
        
        # Log generated TwiML (truncated for readability)
        logger.info(f"Generated TwiML: {twiml[:500]}...")
        logger.critical(f"***** SUCCESSFULLY RETURNING TWIML FOR CALL {call_sid} *****")
        
        # Return the TwiML response
        return PlainTextResponse(
            content=twiml,
            media_type="application/xml",
            status_code=HTTP_200_OK
        )
        
    except Exception as e:
        # Log the full error with traceback
        logger.critical(f"***** ERROR HANDLING INCOMING CALL *****")
        logger.error(f"Error handling incoming call: {str(e)}")
        logger.error(f"Error class: {e.__class__.__name__}")
        logger.error(f"Error traceback: {traceback.format_exc()}")
        
        # Try to generate an error response
        try:
            # Generate simple fallback TwiML
            error_twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Amy-Neural">We're sorry, but an error occurred while processing your call. Please try again later.</Say>
</Response>
"""
            logger.info(f"Generated error TwiML: {error_twiml}")
            return PlainTextResponse(
                content=error_twiml,
                media_type="application/xml",
                status_code=HTTP_200_OK
            )
        except Exception as fallback_error:
            logger.critical(f"Failed to generate error TwiML: {fallback_error}")
            return PlainTextResponse(
                content="Error processing call",
                status_code=500
            )

@router.websocket("/ws/media/{call_sid}")
async def handle_media_stream(
    websocket: WebSocket, 
    call_sid: str,
    connection_mgr: ConnectionManager = Depends(get_connection_manager)
):
    """
    WebSocket endpoint for handling Twilio media streams.
    
    This endpoint receives and processes real-time audio from Twilio,
    and returns AI-generated responses in real-time. Uses the FSM for conversation state management.
    
    Args:
        websocket: The WebSocket connection
        call_sid: The Twilio call SID
        connection_mgr: The WebSocket connection manager
    """
    # Local references to track active tasks and resources
    openai_task = None
    transcript_queue = asyncio.Queue()
    event_queue = asyncio.Queue()
    tasks = []
    
    # Set up the WebSocket connection
    await connection_mgr.connect(websocket, call_sid)
    logger.info(f"[{call_sid}] WebSocket connection established")
    
    try:
        # Process messages from the WebSocket
        async for message in websocket.iter_json():
            event = message.get("event")
            
            if event == "connected":
                # Handle connected event
                logger.info(f"[{call_sid}] Received connected event")
                await connection_mgr.update_call_data(call_sid, {"connected_at": time.time()})
                
            elif event == "start":
                # Handle start event - this is where we start processing
                logger.info(f"[{call_sid}] Received start event, stream SID: {message.get('streamSid')}")
                await connection_mgr.update_call_data(call_sid, {
                    "stream_sid": message.get("streamSid"),
                    "started_at": time.time()
                })
                
                # Start a new conversation with the FSM
                greeting_response = await async_agent_orchestrator.start_new_conversation(
                    call_sid,
                    {"first_interaction": True}
                )
                
                # Extract the greeting text
                greeting_text = greeting_response.get("text", "Welcome to Red Bar Sushi. How can I assist you today?")
                
                # Send greeting to Twilio using OpenAI Text-to-Speech
                # In a real implementation, this would connect to the OpenAI Realtime API
                # and send the text-to-speech audio back to Twilio
                
                # Start OpenAI Realtime WebSocket connection
                from app.utils.realtime_audio_async import (
                    OpenAIRealtimeClient, RealtimeConfig, RealtimeEventProcessor
                )
                
                # Initialize the OpenAI Realtime client with the configuration
                realtime_config = RealtimeConfig(
                    model="gpt-4o-realtime-preview-2024-10-01",
                    instructions="You are an AI assistant for Red Bar Sushi restaurant, helping customers place orders over the phone. Be friendly, helpful, and concise.",
                    voice="shimmer",
                    input_audio_format="mulaw",
                    output_audio_format="mulaw",
                    vad_enabled=True,
                    vad_silence_threshold_ms=1000,
                    vad_speech_threshold_ms=8000
                )
                
                # Define event handlers
                async def on_transcript_final(transcript_data):
                    """Handle final transcript events from OpenAI."""
                    transcript = transcript_data.get("text", "")
                    if transcript:
                        # Add to transcript queue for processing
                        await transcript_queue.put(transcript)
                
                async def on_audio_delta(audio_data):
                    """Handle audio delta events from OpenAI."""
                    audio_chunk = audio_data.get("audio", "")
                    if audio_chunk:
                        # Base64 decode and send to Twilio
                        try:
                            audio_bytes = base64.b64decode(audio_chunk)
                            await websocket.send_bytes(audio_bytes)
                        except Exception as e:
                            logger.error(f"[{call_sid}] Error sending audio to Twilio: {e}")
                
                async def on_tool_call(tool_data):
                    """Handle tool call events from OpenAI."""
                    # Add to event queue for processing
                    await event_queue.put({
                        "type": "tool_call",
                        "data": tool_data
                    })
                
                # Create the event processor
                event_processor = RealtimeEventProcessor()
                event_processor.register_handler("transcript.final", on_transcript_final)
                event_processor.register_handler("response.audio.delta", on_audio_delta)
                event_processor.register_handler("conversation.function_call", on_tool_call)
                
                # Initialize the OpenAI Realtime client
                openai_client = OpenAIRealtimeClient(
                    api_key=settings.OPENAI_API_KEY,
                    config=realtime_config,
                    event_processor=event_processor
                )
                
                # Define the task for processing transcripts
                async def process_transcripts():
                    """Process transcripts as they arrive."""
                    while True:
                        try:
                            # Get the next transcript
                            transcript = await transcript_queue.get()
                            
                            # Process with the agent orchestrator
                            response = await async_agent_orchestrator.process_voice_input(
                                call_sid, transcript
                            )
                            
                            # Send response text to OpenAI for TTS
                            response_text = response.get("text", "")
                            if response_text:
                                await openai_client.request_response(response_text)
                            
                            # Mark task as done
                            transcript_queue.task_done()
                            
                        except asyncio.CancelledError:
                            logger.info(f"[{call_sid}] Transcript processing task cancelled")
                            break
                        except Exception as e:
                            logger.error(f"[{call_sid}] Error processing transcript: {e}")
                
                # Define the task for processing events
                async def process_events():
                    """Process events as they arrive."""
                    while True:
                        try:
                            # Get the next event
                            event_data = await event_queue.get()
                            
                            if event_data.get("type") == "tool_call":
                                # Extract tool call details
                                tool_call = event_data.get("data", {})
                                tool_name = tool_call.get("name", "")
                                tool_args = tool_call.get("arguments", {})
                                
                                # Process the tool call
                                if tool_name:
                                    result = await async_agent_orchestrator.process_tool_call(
                                        call_sid, tool_name, tool_args
                                    )
                                    
                                    # Return the result to OpenAI
                                    await openai_client.return_tool_result(
                                        tool_call.get("id", ""), result.get("result", {})
                                    )
                            
                            # Mark task as done
                            event_queue.task_done()
                            
                        except asyncio.CancelledError:
                            logger.info(f"[{call_sid}] Event processing task cancelled")
                            break
                        except Exception as e:
                            logger.error(f"[{call_sid}] Error processing event: {e}")
                
                # Connect to OpenAI Realtime API
                await openai_client.connect()
                
                # Start the OpenAI WebSocket processing task
                openai_task = asyncio.create_task(openai_client.process_messages())
                
                # Start the transcript and event processing tasks
                transcript_task = asyncio.create_task(process_transcripts())
                event_task = asyncio.create_task(process_events())
                
                # Add tasks to the task list for cleanup
                tasks.extend([openai_task, transcript_task, event_task])
                
                # Send the greeting to OpenAI for TTS
                await openai_client.request_response(greeting_text)
                
            elif event == "media":
                # Handle media event with audio data
                media = message.get("media", {})
                payload = media.get("payload", "")
                
                # Forward the audio data to OpenAI Realtime API if connected
                if payload and openai_task and not openai_task.done():
                    # In a real implementation, this would send the audio to OpenAI
                    pass
                
            elif event == "stop":
                # Handle stop event
                logger.info(f"[{call_sid}] Received stop event")
                await connection_mgr.update_call_data(call_sid, {"stopped_at": time.time()})
                
                # Cancel all tasks
                for task in tasks:
                    if task and not task.done():
                        task.cancel()
                
                # Disconnect
                await connection_mgr.disconnect(call_sid)
                break
            
            else:
                # Handle unknown event
                logger.warning(f"[{call_sid}] Received unknown event: {event}")
    
    except WebSocketDisconnect:
        logger.info(f"[{call_sid}] WebSocket disconnected")
    
    except Exception as e:
        logger.error(f"[{call_sid}] Error in WebSocket handler: {str(e)}")
        logger.error(traceback.format_exc())
    
    finally:
        # Clean up all tasks
        for task in tasks:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"[{call_sid}] Error cancelling task: {e}")
        
        # Disconnect the WebSocket
        try:
            await connection_mgr.disconnect(call_sid)
        except Exception as close_error:
            logger.error(f"[{call_sid}] Error closing WebSocket connection: {str(close_error)}")

@router.post("/process")
async def process_voice_input(request: Request) -> JSONResponse:
    """
    Process voice input text without using WebSockets.
    
    This endpoint is useful for testing and debugging voice interactions with the FSM.
    
    Args:
        request: The HTTP request with voice input
        
    Returns:
        The agent's response with FSM state information
    """
    try:
        # Parse request body
        data = await request.json()
        call_sid = data.get("call_sid", f"test_{int(time.time())}")
        input_text = data.get("input", "")
        context = data.get("context", {})
        
        # Check if this is a new conversation
        is_new = data.get("new_conversation", False)
        
        if is_new:
            # Start a new conversation with the FSM
            result = await async_agent_orchestrator.start_new_conversation(call_sid, context)
        else:
            # Process the input with the FSM
            result = await async_agent_orchestrator.process_voice_input(call_sid, input_text, context)
        
        # Get current FSM state
        state_info = await async_agent_orchestrator.get_session_state(call_sid)
        
        # Add FSM state information to the response
        result.update({
            "fsm_state": state_info.get("fsm_state", "UNKNOWN"),
            "fsm_context": state_info.get("fsm_context", {})
        })
        
        # Return the enhanced response
        return JSONResponse(content=result)
    
    except Exception as e:
        logger.error(f"Error processing voice input: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            content={"error": str(e)},
            status_code=500
        )

@router.post("/tool")
async def execute_tool(request: Request) -> JSONResponse:
    """
    Execute a tool call without using WebSockets.
    
    This endpoint is useful for testing and debugging tool calls with the FSM.
    
    Args:
        request: The HTTP request with tool call details
        
    Returns:
        The tool execution result with FSM state information
    """
    try:
        # Parse request body
        data = await request.json()
        call_sid = data.get("call_sid", f"test_{int(time.time())}")
        tool_name = data.get("tool_name", "")
        args = data.get("args", {})
        context = data.get("context", {})
        
        # Execute the tool with the FSM
        result = await async_agent_orchestrator.process_tool_call(call_sid, tool_name, args, context)
        
        # Get current FSM state
        state_info = await async_agent_orchestrator.get_session_state(call_sid)
        
        # Add FSM state information to the response
        result.update({
            "fsm_state": state_info.get("fsm_state", "UNKNOWN"),
            "fsm_context": state_info.get("fsm_context", {})
        })
        
        # Return the enhanced response
        return JSONResponse(content=result)
    
    except Exception as e:
        logger.error(f"Error executing tool: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            content={"error": str(e)},
            status_code=500
        )

@router.get("/sessions/{call_sid}")
async def get_session_state(call_sid: str) -> JSONResponse:
    """
    Get the state of a voice session.
    
    Args:
        call_sid: The Twilio call SID
        
    Returns:
        The session state
    """
    try:
        # Get the session state
        state = await async_agent_orchestrator.get_session_state(call_sid)
        
        # Return the state
        return JSONResponse(content=state)
    
    except Exception as e:
        logger.error(f"Error getting session state: {str(e)}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=500
        )

@router.post("/fsm/{call_sid}/event")
async def trigger_fsm_event(call_sid: str, request: Request) -> JSONResponse:
    """
    Trigger an event in the FSM for a voice session.
    
    This endpoint allows direct manipulation of the FSM state through events,
    which is useful for testing and debugging the conversation flow.
    
    Args:
        call_sid: The Twilio call SID
        request: The HTTP request with event details
        
    Returns:
        The updated FSM state
    """
    try:
        # Parse request body
        data = await request.json()
        event_name = data.get("event", "")
        
        if not event_name:
            return JSONResponse(
                content={"error": "No event name provided"},
                status_code=400
            )
        
        # Get the FSM for this call
        fsm = await async_fsm_manager.get_fsm(call_sid)
        
        # Ensure the FSM has access to all agents
        fsm.update_context({
            "frontline_agent": async_agent_orchestrator.frontline_agent,
            "menu_agent": async_agent_orchestrator.menu_agent,
            "cart_agent": async_agent_orchestrator.cart_agent,
            "guardrail_agent": async_agent_orchestrator.guardrail_agent,
            "fulfillment_agent": async_agent_orchestrator.fulfillment_agent,
            "escalation_agent": async_agent_orchestrator.escalation_agent
        })
        
        # Trigger the event
        try:
            event = ConversationEvent[event_name]
            await fsm.trigger(event)
        except KeyError:
            return JSONResponse(
                content={"error": f"Invalid event name: {event_name}"},
                status_code=400
            )
        
        # Get the updated state
        state_info = await async_agent_orchestrator.get_session_state(call_sid)
        
        # Return the updated state
        return JSONResponse(content={
            "success": True,
            "message": f"Triggered event {event_name} in FSM for {call_sid}",
            "previous_state": data.get("previous_state", "UNKNOWN"),
            "current_state": fsm.current_state.name,
            "fsm_context": state_info.get("fsm_context", {})
        })
    
    except Exception as e:
        logger.error(f"Error triggering FSM event: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            content={"error": str(e)},
            status_code=500
        )

@router.get("/fsm/{call_sid}")
async def get_fsm_state(call_sid: str) -> JSONResponse:
    """
    Get the state of the FSM for a voice session.
    
    Args:
        call_sid: The Twilio call SID
        
    Returns:
        The FSM state
    """
    try:
        # Get the FSM for this call
        fsm = await async_fsm_manager.get_fsm(call_sid)
        
        # Get the serializable context
        context = {k: v for k, v in fsm.context.items() 
                  if isinstance(v, (str, int, float, bool, list, dict)) or v is None}
        
        # Return the state
        return JSONResponse(content={
            "call_sid": call_sid,
            "state": fsm.current_state.name,
            "context": context,
            "available_events": [e.name for e in ConversationEvent],
            "valid_transitions": [e.name for e in 
                               fsm.transitions.get(fsm.current_state, {}).keys()]
        })
    
    except Exception as e:
        logger.error(f"Error getting FSM state: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            content={"error": str(e)},
            status_code=500
        )

@router.delete("/sessions/{call_sid}")
async def cleanup_session(call_sid: str) -> JSONResponse:
    """
    Clean up a voice session.
    
    Args:
        call_sid: The Twilio call SID
        
    Returns:
        Success message
    """
    try:
        # Remove from active sessions
        if call_sid in async_agent_orchestrator.active_sessions:
            del async_agent_orchestrator.active_sessions[call_sid]
        
        # Clean up from conversation stores
        await async_agent_orchestrator.conversation_store.delete_conversation(call_sid)
        
        # Remove from FSM manager
        async_fsm_manager.remove_fsm(call_sid)
        
        # Return success
        return JSONResponse(content={"success": True, "message": f"Session {call_sid} cleaned up"})
    
    except Exception as e:
        logger.error(f"Error cleaning up session: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            content={"error": str(e)},
            status_code=500
        )