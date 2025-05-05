"""
Handlers for silence events in the voice workflow.

This module contains functions for processing silence events
from the OpenAI Realtime API and generating appropriate responses.
"""

import logging
import time
import base64
import json
import traceback

# Set up logger
logger = logging.getLogger(__name__)

async def handle_silence_event(ws, session_id, frontline_agent, fsm_orchestrator, event_timing, 
                               greeting_sent, greeting_timestamp, metrics):
    """
    Handle a silence event from the Realtime API.
    
    Args:
        ws: The WebSocket connection
        session_id: Session identifier
        frontline_agent: The frontline agent instance
        fsm_orchestrator: The FSM orchestrator instance
        event_timing: Dictionary of timing metrics
        greeting_sent: Whether a greeting has been sent
        greeting_timestamp: When the greeting was sent (if applicable)
        metrics: Connection metrics dictionary
        
    Returns:
        updated greeting_sent status, updated greeting_timestamp
    """
    # Handle silence detection
    metrics["silence_events"] += 1
    logger.info(f"[SILENCE:{session_id}] Silence detected (event #{metrics['silence_events']})")
    
    # If this is after the greeting, log as a critical event
    if greeting_sent and greeting_timestamp:
        time_since_greeting = time.time() - greeting_timestamp
        # Try to import and use the enhanced diagnostics module
        try:
            from app.utils.enhanced_diagnostics import log_connection_event
            log_connection_event(
                "post_greeting_silence",
                {
                    "time_since_greeting": time_since_greeting,
                    "silence_count": metrics["silence_events"],
                    "audio_chunks": metrics["audio_chunks_received"],
                    "events_processed": metrics["events_processed"],
                    "greeting_timestamp": greeting_timestamp,
                    "fsm_state": fsm_orchestrator.get_current_state(session_id) if fsm_orchestrator else "unknown"
                },
                session_id
            )
        except Exception as e:
            logger.error(f"[SILENCE:{session_id}] Failed to log post-greeting silence event: {e}")
    
    try:
        # Get current FSM state
        current_state = fsm_orchestrator.get_current_state(session_id)
        logger.info(f"[SILENCE:{session_id}] Current FSM state: {current_state}")
        
        # Generate appropriate response based on state
        if not greeting_sent:
            # Send initial greeting if none sent yet
            new_greeting_timestamp = time.time()
            event_timing["greeting_sent"] = new_greeting_timestamp
            
            logger.critical(f"[GREETING:{session_id}] ⚠️ SENDING INITIAL GREETING after {new_greeting_timestamp - event_timing['stream_start']:.3f}s of processing")
            greeting = "Welcome to Red Bar Sushi. How can I help you today?"
            
            # Send greeting to client
            try:
                greeting_msg = {
                    "event": "message",
                    "text": greeting,
                    "timestamp": new_greeting_timestamp,
                    "session_id": session_id
                }
                await ws.send(json.dumps(greeting_msg))
                metrics["events_sent"] += 1
                
                # Convert greeting to audio (base64 for now)
                audio_msg = {
                    "event": "media",
                    "streamSid": session_id,
                    "media": {
                        "payload": base64.b64encode(greeting.encode('utf-8')).decode('utf-8')
                    },
                    "timestamp": time.time()
                }
                await ws.send(json.dumps(audio_msg))
                metrics["events_sent"] += 1
                
                # Send a diagnostic event with key metrics
                diagnostic_msg = {
                    "type": "diagnostic",
                    "event": "greeting_sent",
                    "timestamp": time.time(),
                    "session_id": session_id,
                    "audio_chunks_received": metrics["audio_chunks_received"],
                    "events_processed": metrics["events_processed"],
                    "time_since_start": time.time() - event_timing["stream_start"],
                    "time_since_first_event": event_timing["first_event"] and (time.time() - event_timing["first_event"])
                }
                await ws.send(json.dumps(diagnostic_msg))
                
                # Enhanced logging of greeting event
                from app.utils.enhanced_diagnostics import log_connection_event
                log_connection_event(
                    "greeting_sent",
                    {
                        "text": greeting,
                        "time_since_connection": time.time() - event_timing["stream_start"],
                        "audio_chunks": metrics["audio_chunks_received"],
                        "events_processed": metrics["events_processed"],
                        "greeting_timestamp": new_greeting_timestamp,
                        "fsm_state": fsm_orchestrator.get_current_state(session_id) if fsm_orchestrator else "unknown"
                    },
                    session_id
                )
                
                greeting_sent = True
                greeting_timestamp = new_greeting_timestamp
                logger.critical(f"[GREETING:{session_id}] ✅ INITIAL GREETING SUCCESSFULLY SENT")
            except Exception as greeting_error:
                # If we fail to send the greeting, this is critical
                logger.critical(f"[GREETING:{session_id}] ❌ CRITICAL: Failed to send initial greeting: {greeting_error}")
                logger.critical(traceback.format_exc())
                
                # Try to log this error back to Twilio to help with diagnostics
                try:
                    error_msg = {
                        "type": "error",
                        "error_type": "greeting_failure",
                        "text": f"Failed to send greeting: {str(greeting_error)}",
                        "timestamp": time.time(),
                        "session_id": session_id
                    }
                    await ws.send(json.dumps(error_msg))
                except:
                    pass
                    
        elif current_state and current_state.value == "greeting":
            # In greeting state, prompt for name
            logger.info(f"[SILENCE:{session_id}] In GREETING state, prompting for name")
            prompt = "Could you please tell me your name?"
            
            # Send prompt to client
            await ws.send(json.dumps({
                "event": "message",
                "text": prompt,
                "timestamp": time.time()
            }))
            metrics["events_sent"] += 1
            
            # Convert prompt to audio (base64 for now)
            await ws.send(json.dumps({
                "event": "media",
                "streamSid": session_id,
                "media": {
                    "payload": base64.b64encode(prompt.encode('utf-8')).decode('utf-8')
                }
            }))
            metrics["events_sent"] += 1
            logger.info(f"[SILENCE:{session_id}] ✅ Name prompt sent")
            
        else:
            # Generic prompt based on state
            logger.info(f"[SILENCE:{session_id}] In state {current_state}, sending generic prompt")
            prompt = "Is there anything else I can help you with?"
            
            # Send prompt to client
            await ws.send(json.dumps({
                "event": "message",
                "text": prompt,
                "timestamp": time.time()
            }))
            metrics["events_sent"] += 1
            
            # Convert prompt to audio (base64 for now)
            await ws.send(json.dumps({
                "event": "media",
                "streamSid": session_id,
                "media": {
                    "payload": base64.b64encode(prompt.encode('utf-8')).decode('utf-8')
                }
            }))
            metrics["events_sent"] += 1
            logger.info(f"[SILENCE:{session_id}] ✅ Generic prompt sent")
            
    except Exception as silence_error:
        logger.error(f"[SILENCE:{session_id}] ❌ Error processing silence event: {silence_error}")
        logger.error(f"[SILENCE:{session_id}] Silence error trace: {traceback.format_exc()}")
    
    return greeting_sent, greeting_timestamp