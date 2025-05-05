"""
Handlers for transcript events in the voice workflow.

This module contains functions for processing transcript events
from the OpenAI Realtime API and generating appropriate responses.
"""

import logging
import time
import base64
import json
import traceback

# Set up logger
logger = logging.getLogger(__name__)

async def handle_transcript_event(ws, session_id, frontline_agent, event, metrics, event_timing=None):
    """
    Handle a transcript_complete event from the Realtime API.
    
    Args:
        ws: The WebSocket connection
        session_id: Session identifier
        frontline_agent: The frontline agent instance
        event: The transcript event from the Realtime API
        metrics: Connection metrics dictionary
        event_timing: Dictionary of timing metrics (optional)
    """
    # Process complete transcript with frontline agent
    transcript = event.get("text", "")
    if transcript:
        metrics["transcripts_processed"] += 1
        logger.info(f"[TRANSCRIPT:{session_id}] Processing transcript #{metrics['transcripts_processed']}: {transcript}")
        
        # Check if this is the first transcript after greeting
        if event_timing and "greeting_sent" in event_timing:
            greeting_timestamp = event_timing.get("greeting_sent")
            # If this is the first transcript after greeting, log it as a critical event
            if greeting_timestamp:
                time_since_greeting = time.time() - greeting_timestamp
                # Log this as a critical post-greeting event
                try:
                    from app.utils.enhanced_diagnostics import log_connection_event
                    log_connection_event(
                        "post_greeting_transcript",
                        {
                            "text": transcript,
                            "time_since_greeting": time_since_greeting,
                            "transcript_count": metrics["transcripts_processed"],
                            "audio_chunks": metrics.get("audio_chunks_received", 0),
                            "events_processed": metrics.get("events_processed", 0)
                        },
                        session_id
                    )
                except Exception as e:
                    logger.error(f"[TRANSCRIPT:{session_id}] Failed to log post-greeting transcript event: {e}")
        
        # Process with orchestrated agent
        try:
            logger.info(f"[TRANSCRIPT:{session_id}] Sending transcript to frontline agent")
            start_time = time.time()
            agent_response = frontline_agent.process_voice_input(session_id, transcript)
            processing_time = time.time() - start_time
            logger.info(f"[TRANSCRIPT:{session_id}] ✅ Agent processed transcript in {processing_time:.2f}s")
            logger.info(f"[TRANSCRIPT:{session_id}] Agent response: {agent_response}")
            
            # Send transcript to client
            await ws.send(json.dumps({
                "event": "transcript",
                "transcript": transcript,
                "timestamp": time.time()
            }))
            metrics["events_sent"] += 1
            
            # Send agent response to client
            await ws.send(json.dumps({
                "event": "message",
                "text": agent_response,
                "timestamp": time.time()
            }))
            metrics["events_sent"] += 1
            
            # Generate TTS audio from response
            logger.info(f"[TRANSCRIPT:{session_id}] Sending agent response as TTS audio")
            await ws.send(json.dumps({
                "event": "media",
                "streamSid": session_id,
                "media": {
                    "payload": base64.b64encode(agent_response.encode('utf-8')).decode('utf-8')
                }
            }))
            metrics["events_sent"] += 1
            
        except Exception as agent_error:
            logger.error(f"[TRANSCRIPT:{session_id}] ❌ Error processing transcript with agent: {agent_error}")
            logger.error(f"[TRANSCRIPT:{session_id}] Agent error trace: {traceback.format_exc()}")
            
            # Send error to client
            await ws.send(json.dumps({
                "event": "error",
                "text": f"Error processing your input: {str(agent_error)}",
                "timestamp": time.time()
            }))
            metrics["events_sent"] += 1
    else:
        logger.warning(f"[TRANSCRIPT:{session_id}] Received empty transcript_complete event")