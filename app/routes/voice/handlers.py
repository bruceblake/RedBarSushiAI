"""
Event handlers for voice processing WebSocket events.

This module provides handlers for different types of events from the
OpenAI Realtime API, including transcript events, silence events,
tool call events, and audio events.
"""

import asyncio
import json
import logging
import time
from datetime import datetime

from app.utils.enhanced_logging import log_voice_state_transition, log_agent_interaction
from app.utils.agent_orchestration import FSMState

# Set up logger
logger = logging.getLogger(__name__)

async def handle_transcript_event(ws, session_id, frontline, event, metrics, event_timing):
    """
    Handle a transcript event from the Realtime API.
    
    Args:
        ws: WebSocket connection
        session_id: Session identifier
        frontline: Frontline agent instance
        event: Event data
        metrics: Metrics tracking dictionary
        event_timing: Dictionary tracking event timing
    """
    try:
        # Update metrics
        metrics["transcripts_processed"] += 1
        
        # Extract transcript text
        transcript = event.get("text", "")
        
        # Log the transcript
        logger.info(f"[TRANSCRIPT:{session_id}] Received transcript: '{transcript}'")
        
        # If this is the first transcript after greeting, mark it
        if event_timing.get("greeting_sent") and not event_timing.get("post_greeting_transcript"):
            event_timing["post_greeting_transcript"] = time.time()
            time_after_greeting = time.time() - event_timing["greeting_sent"]
            logger.info(f"[TRANSCRIPT:{session_id}] First transcript after greeting: {time_after_greeting:.2f}s")
        
        # Process with frontline agent if available
        if frontline:
            try:
                start_time = time.time()
                response = frontline.process_voice_input(session_id, transcript)
                processing_time = time.time() - start_time
                
                logger.info(f"[AGENT:{session_id}] Agent processed transcript in {processing_time:.3f}s")
                log_agent_interaction("frontline", "process_transcript", transcript, session_id, processing_time * 1000)
                
                # Format response as JSON and send to client
                await ws.send(json.dumps({
                    "event": "agent_response",
                    "text": response,
                    "timestamp": time.time()
                }))
                metrics["events_sent"] += 1
                
                logger.info(f"[AGENT:{session_id}] Agent response sent: '{response}'")
            except Exception as agent_error:
                logger.error(f"[AGENT:{session_id}] Error processing transcript with agent: {agent_error}")
                await ws.send(json.dumps({
                    "event": "error",
                    "text": f"Error processing transcript: {agent_error}",
                    "timestamp": time.time()
                }))
                metrics["events_sent"] += 1
        else:
            logger.warning(f"[TRANSCRIPT:{session_id}] No frontline agent available to process transcript")
            await ws.send(json.dumps({
                "event": "error",
                "text": "System error: Agent unavailable",
                "timestamp": time.time()
            }))
            metrics["events_sent"] += 1
    
    except Exception as e:
        logger.error(f"[TRANSCRIPT:{session_id}] Error handling transcript event: {e}")
        # Try to send error to client
        try:
            await ws.send(json.dumps({
                "event": "error",
                "text": f"Error handling transcript: {e}",
                "timestamp": time.time()
            }))
            metrics["events_sent"] += 1
        except:
            pass

async def handle_silence_event(ws, session_id, frontline, fsm_orchestrator, event_timing, 
                               greeting_sent, greeting_timestamp, metrics):
    """
    Handle a silence event from the Realtime API.
    
    Args:
        ws: WebSocket connection
        session_id: Session identifier
        frontline: Frontline agent instance
        fsm_orchestrator: FSM orchestrator instance
        event_timing: Dictionary tracking event timing
        greeting_sent: Whether greeting has already been sent
        greeting_timestamp: When greeting was sent
        metrics: Metrics tracking dictionary
        
    Returns:
        tuple: (new_greeting_sent, new_greeting_timestamp)
    """
    try:
        # Update metrics
        metrics["silence_events"] += 1
        
        # Log the silence event
        logger.warning(f"[SILENCE:{session_id}] Silence detected (event #{metrics['silence_events']})")
        
        # If this is the first silence event, record its timing
        if not event_timing.get("first_silence"):
            event_timing["first_silence"] = time.time()
            elapsed = time.time() - event_timing.get("stream_start", time.time())
            logger.info(f"[SILENCE:{session_id}] First silence detected after {elapsed:.2f}s")
        
        # If greeting hasn't been sent yet and we're in the GREETING state, send it
        if not greeting_sent:
            # Get current FSM state
            current_state = fsm_orchestrator.get_state(session_id)
            logger.info(f"[FSM:{session_id}] Current state: {current_state}")
            
            if current_state == FSMState.GREETING:
                try:
                    # Use the frontline agent to generate a greeting
                    logger.info(f"[SILENCE:{session_id}] Sending initial greeting")
                    
                    greeting = frontline.generate_greeting(session_id)
                    logger.info(f"[AGENT:{session_id}] Generated greeting: '{greeting}'")
                    
                    # Send the greeting
                    await ws.send(json.dumps({
                        "event": "agent_response",
                        "text": greeting,
                        "timestamp": time.time(),
                        "is_greeting": True
                    }))
                    metrics["events_sent"] += 1
                    
                    # Update variables
                    greeting_sent = True
                    greeting_timestamp = time.time()
                    event_timing["greeting_sent"] = greeting_timestamp
                    
                    # Update FSM state
                    fsm_orchestrator.transition(session_id, FSMState.MAIN_MENU, "greeting_sent")
                    log_voice_state_transition(FSMState.GREETING, FSMState.MAIN_MENU, session_id, "greeting_sent")
                    
                    logger.info(f"[SILENCE:{session_id}] Initial greeting sent, transitioned to MAIN_MENU state")
                except Exception as greeting_error:
                    logger.error(f"[SILENCE:{session_id}] Error sending greeting: {greeting_error}")
            else:
                logger.info(f"[SILENCE:{session_id}] Not sending greeting because state is {current_state}, not GREETING")
        
        # If greeting was already sent, handle post-greeting silence
        elif greeting_sent:
            # Record first post-greeting silence
            if not event_timing.get("post_greeting_silence"):
                event_timing["post_greeting_silence"] = time.time()
                time_after_greeting = time.time() - greeting_timestamp
                logger.warning(f"[SILENCE:{session_id}] First silence after greeting detected {time_after_greeting:.2f}s after greeting")
            
            # Get current FSM state
            current_state = fsm_orchestrator.get_state(session_id)
            
            # Handle silence differently based on FSM state
            if current_state == FSMState.MAIN_MENU:
                # In MAIN_MENU state, prompt user after silence
                logger.info(f"[SILENCE:{session_id}] Silence in MAIN_MENU state, prompting user")
                
                try:
                    # Generate prompt based on current state
                    prompt = frontline.generate_prompt(session_id, current_state)
                    
                    await ws.send(json.dumps({
                        "event": "agent_response",
                        "text": prompt,
                        "timestamp": time.time(),
                        "is_prompt": True
                    }))
                    metrics["events_sent"] += 1
                    
                    logger.info(f"[SILENCE:{session_id}] Sent prompt in MAIN_MENU state: '{prompt}'")
                except Exception as prompt_error:
                    logger.error(f"[SILENCE:{session_id}] Error sending prompt: {prompt_error}")
            else:
                logger.info(f"[SILENCE:{session_id}] Silence in {current_state} state, no specific handling")
                # In other states, we might have different silence handling logic
        
        return greeting_sent, greeting_timestamp
    
    except Exception as e:
        logger.error(f"[SILENCE:{session_id}] Error handling silence event: {e}")
        # Try to send error to client
        try:
            await ws.send(json.dumps({
                "event": "error",
                "text": f"Error handling silence: {e}",
                "timestamp": time.time()
            }))
            metrics["events_sent"] += 1
        except:
            pass
        
        # Return unchanged values
        return greeting_sent, greeting_timestamp

async def handle_tool_call_event(ws, session_id, tool_registry, event, metrics):
    """
    Handle a tool call event from the Realtime API.
    
    Args:
        ws: WebSocket connection
        session_id: Session identifier
        tool_registry: Tool registry instance
        event: Event data
        metrics: Metrics tracking dictionary
    """
    try:
        # Update metrics
        metrics["tool_calls"] += 1
        
        # Extract tool call details
        tool_name = event.get("name", "")
        args = event.get("args", {})
        
        logger.info(f"[TOOL:{session_id}] Tool call: {tool_name}, args: {args}")
        
        # Execute the tool if found in registry
        if tool_registry:
            try:
                start_time = time.time()
                result = tool_registry.execute_tool(tool_name, args, session_id)
                processing_time = time.time() - start_time
                
                logger.info(f"[TOOL:{session_id}] Tool executed in {processing_time:.3f}s")
                
                # Format response as JSON and send to client
                await ws.send(json.dumps({
                    "event": "tool_result",
                    "tool": tool_name,
                    "result": result,
                    "timestamp": time.time()
                }))
                metrics["events_sent"] += 1
                
                logger.info(f"[TOOL:{session_id}] Tool result sent for {tool_name}")
            except Exception as tool_error:
                logger.error(f"[TOOL:{session_id}] Error executing tool {tool_name}: {tool_error}")
                await ws.send(json.dumps({
                    "event": "error",
                    "text": f"Error executing tool {tool_name}: {tool_error}",
                    "timestamp": time.time()
                }))
                metrics["events_sent"] += 1
        else:
            logger.warning(f"[TOOL:{session_id}] No tool registry available")
            await ws.send(json.dumps({
                "event": "error",
                "text": f"System error: Tool registry unavailable",
                "timestamp": time.time()
            }))
            metrics["events_sent"] += 1
    
    except Exception as e:
        logger.error(f"[TOOL:{session_id}] Error handling tool call event: {e}")
        # Try to send error to client
        try:
            await ws.send(json.dumps({
                "event": "error",
                "text": f"Error handling tool call: {e}",
                "timestamp": time.time()
            }))
            metrics["events_sent"] += 1
        except:
            pass

async def handle_audio_event(ws, session_id, event, metrics):
    """
    Handle an audio event from the Realtime API.
    
    Args:
        ws: WebSocket connection
        session_id: Session identifier
        event: Event data
        metrics: Metrics tracking dictionary
    """
    try:
        # Extract audio data
        audio_data = event.get("audio", {})
        content_type = audio_data.get("content_type", "")
        
        # Just forward the audio event to the client
        await ws.send(json.dumps({
            "event": "audio",
            "audio": audio_data,
            "timestamp": time.time()
        }))
        metrics["events_sent"] += 1
        
        # Only log details periodically to reduce noise
        if metrics["events_sent"] % 10 == 0:
            logger.debug(f"[AUDIO:{session_id}] Forwarded audio event ({content_type})")
    
    except Exception as e:
        logger.error(f"[AUDIO:{session_id}] Error handling audio event: {e}")
        # Don't send error to client for audio events to avoid interruption