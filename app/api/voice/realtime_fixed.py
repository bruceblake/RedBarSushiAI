"""
OpenAI Realtime API integration for voice interactions.

This module handles the integration with OpenAI's Realtime API for
real-time audio processing, including speech-to-text and text-to-speech.
"""

import asyncio
import logging
import os
import traceback
import base64
from typing import Dict, Any, Optional, Union, Callable

from fastapi import WebSocket
from app.utils.agent_orchestration_async import async_agent_orchestrator
from app.utils.realtime_audio_async import (
    OpenAIRealtimeClient, 
    RealtimeConfig, 
    RealtimeEventProcessor
)
from app.config import settings

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

async def create_openai_client(
    call_sid: str,
    websocket: WebSocket,
    transcript_queue: asyncio.Queue,
    event_queue: asyncio.Queue
) -> OpenAIRealtimeClient:
    """
    Create and initialize an OpenAI Realtime API client.
    
    Args:
        call_sid: The Twilio call SID
        websocket: The WebSocket connection to Twilio
        transcript_queue: Queue for passing transcripts to processing
        event_queue: Queue for passing events to processing
        
    Returns:
        The initialized OpenAI Realtime client
    """
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
    
    # Initialize the OpenAI Realtime client first
    print(f"\n!!! DEBUG: [{call_sid}] Initializing OpenAI Realtime client", flush=True)
    logger.critical(f"🔴 [{call_sid}] Initializing OpenAI Realtime client with API_KEY {'SET' if settings.OPENAI_API_KEY else 'MISSING!!!'}")
    
    # Verify critical environment variables
    logger.critical(f"🔄 [{call_sid}] ENVIRONMENT VERIFICATION")
    logger.critical(f"🔄 [{call_sid}] OPENAI_API_KEY present: {bool(settings.OPENAI_API_KEY)}")
    logger.critical(f"🔄 [{call_sid}] OPENAI_REALTIME_MODEL: {settings.OPENAI_REALTIME_MODEL}")
    logger.critical(f"🔄 [{call_sid}] Environment: {os.environ.get('FASTAPI_ENV', 'undefined')}")
    logger.critical(f"🔄 [{call_sid}] Running on Render: {os.environ.get('RENDER', 'false')}")
    
    print(f"\n!!! DEBUG: [{call_sid}] CRITICAL ENV CHECK - OPENAI_API_KEY present: {bool(settings.OPENAI_API_KEY)}", flush=True)
    print(f"\n!!! DEBUG: [{call_sid}] OPENAI_REALTIME_MODEL: {settings.OPENAI_REALTIME_MODEL}", flush=True)
    
    # Safe logging of API key first/last few characters
    if settings.OPENAI_API_KEY:
        key_preview = settings.OPENAI_API_KEY[:4] + '...' + settings.OPENAI_API_KEY[-4:] if len(settings.OPENAI_API_KEY) > 8 else '[TOO SHORT]'
        key_length = len(settings.OPENAI_API_KEY)
        logger.critical(f"🔶 [{call_sid}] OpenAI API Key preview: {key_preview}, length: {key_length}")
        print(f"\n!!! DEBUG: [{call_sid}] OpenAI API Key preview: {key_preview}, length: {key_length}", flush=True)
        
        if not settings.OPENAI_API_KEY.startswith('sk-'):
            logger.critical(f"🔴 [{call_sid}] WARNING: API key doesn't start with 'sk-', may be invalid!")
            print(f"\n!!! DEBUG: [{call_sid}] WARNING: API key format is INVALID! Doesn't start with 'sk-'", flush=True)
    else:
        logger.critical(f"🔴 [{call_sid}] CRITICAL ERROR: OPENAI_API_KEY IS MISSING!")
        print(f"\n!!! DEBUG: [{call_sid}] CRITICAL ERROR: OPENAI_API_KEY IS MISSING!", flush=True)
    
    # Initialize the configuration
    realtime_config = RealtimeConfig(
        model=settings.OPENAI_REALTIME_MODEL,
        instructions="You are an AI assistant for Red Bar Sushi restaurant, helping customers place orders over the phone. Be friendly, helpful, and concise.",
        voice=settings.OPENAI_REALTIME_VOICE or "shimmer",
        input_audio_format="mulaw",
        output_audio_format="mulaw",
        vad_enabled=True,
        vad_silence_threshold_ms=1000,
        vad_speech_threshold_ms=8000
    )
    
    # Create client
    logger.critical(f"🔄 [{call_sid}] Creating OpenAIRealtimeClient instance...")
    print(f"\n!!! DEBUG: [{call_sid}] Creating OpenAIRealtimeClient instance...", flush=True)
    
    openai_client = OpenAIRealtimeClient(
        api_key=settings.OPENAI_API_KEY,
        config=realtime_config,
        session_id=call_sid
    )
    
    # Now create and configure the event processor with the client
    event_processor = RealtimeEventProcessor(client=openai_client)
    event_processor.register_handler("transcript.final", on_transcript_final)
    event_processor.register_handler("response.audio.delta", on_audio_delta)
    event_processor.register_handler("conversation.function_call", on_tool_call)
    
    # Set the event processor on the client
    openai_client.event_processor = event_processor
    
    logger.critical(f"🔄 [{call_sid}] OpenAIRealtimeClient instance created and configured")
    print(f"\n!!! DEBUG: [{call_sid}] OpenAIRealtimeClient instance created and configured", flush=True)
    
    return openai_client

async def process_transcripts(
    call_sid: str,
    transcript_queue: asyncio.Queue,
    openai_client: OpenAIRealtimeClient
) -> None:
    """
    Process transcripts as they arrive from OpenAI.
    
    Args:
        call_sid: The Twilio call SID
        transcript_queue: Queue of transcripts to process
        openai_client: The OpenAI Realtime client
    """
    logger.critical(f"🔄 [{call_sid}] Starting transcript processing task")
    print(f"\n!!! DEBUG: [{call_sid}] Starting transcript processing task", flush=True)
    
    while True:
        try:
            # Get the next transcript
            transcript = await transcript_queue.get()
            logger.critical(f"🔄 [{call_sid}] Processing transcript: {transcript}")
            
            # Process with the agent orchestrator
            response = await async_agent_orchestrator.process_voice_input(
                call_sid, transcript
            )
            
            # Send response text to OpenAI for TTS
            response_text = response.get("text", "")
            if response_text:
                logger.critical(f"🔄 [{call_sid}] Sending response to TTS: {response_text}")
                await openai_client.request_response(response_text)
            
            # Mark task as done
            transcript_queue.task_done()
            
        except asyncio.CancelledError:
            logger.critical(f"🔴 [{call_sid}] Transcript processing task cancelled")
            print(f"\n!!! DEBUG: [{call_sid}] Transcript processing task cancelled", flush=True)
            break
        except Exception as e:
            logger.critical(f"🔴 [{call_sid}] Error processing transcript: {e}")
            logger.critical(traceback.format_exc())
            print(f"\n!!! DEBUG: [{call_sid}] Error processing transcript: {e}", flush=True)
            print(f"\n!!! DEBUG: {traceback.format_exc()}", flush=True)

async def process_events(
    call_sid: str,
    event_queue: asyncio.Queue,
    openai_client: OpenAIRealtimeClient
) -> None:
    """
    Process events as they arrive from OpenAI.
    
    Args:
        call_sid: The Twilio call SID
        event_queue: Queue of events to process
        openai_client: The OpenAI Realtime client
    """
    logger.critical(f"🔄 [{call_sid}] Starting event processing task")
    print(f"\n!!! DEBUG: [{call_sid}] Starting event processing task", flush=True)
    
    while True:
        try:
            # Get the next event
            event_data = await event_queue.get()
            logger.debug(f"[{call_sid}] Processing event: {event_data.get('type')}")
            
            if event_data.get("type") == "tool_call":
                # Extract tool call details
                tool_call = event_data.get("data", {})
                tool_name = tool_call.get("name", "")
                tool_args = tool_call.get("arguments", {})
                logger.info(f"[{call_sid}] Tool call: {tool_name}")
                
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
            logger.critical(f"🔴 [{call_sid}] Event processing task cancelled")
            print(f"\n!!! DEBUG: [{call_sid}] Event processing task cancelled", flush=True)
            break
        except Exception as e:
            logger.critical(f"🔴 [{call_sid}] Error processing event: {e}")
            logger.critical(traceback.format_exc())
            print(f"\n!!! DEBUG: [{call_sid}] Error processing event: {e}", flush=True)
            print(f"\n!!! DEBUG: {traceback.format_exc()}", flush=True)
