"""
Audio generator for Realtime API WebSocket streaming.

This module provides an async generator for converting incoming WebSocket
audio chunks into a stream suitable for OpenAI's Realtime API.
"""

import asyncio
import logging
import traceback

# Set up logger
logger = logging.getLogger(__name__)

async def create_audio_generator(incoming_audio_queue, session_id, cancellation_task=None):
    """
    Create an async generator for streaming audio chunks.
    
    Args:
        incoming_audio_queue: Queue containing incoming audio chunks
        session_id: Session identifier for logging
        cancellation_task: Task to monitor for cancellation
        
    Returns:
        An async generator yielding audio chunks
    """
    logger.info(f"[AUDIO_GENERATOR:{session_id}] Creating audio generator")
    chunk_count = 0
    
    try:
        while True:
            try:
                # Check if the cancellation task is done
                if cancellation_task and cancellation_task.done():
                    logger.info(f"[AUDIO_GENERATOR:{session_id}] Cancellation task is done, exiting generator")
                    break
                
                # Wait for the next audio chunk with timeout
                try:
                    audio_chunk = await asyncio.wait_for(incoming_audio_queue.get(), timeout=1.0)
                    
                    # Yield the audio chunk to the Realtime API
                    chunk_count += 1
                    
                    # Log progress periodically
                    if chunk_count % 100 == 0:
                        logger.info(f"[AUDIO_GENERATOR:{session_id}] Generated {chunk_count} audio chunks")
                        
                    # Mark the task as done
                    incoming_audio_queue.task_done()
                    
                    # Return the audio chunk
                    yield audio_chunk
                    
                except asyncio.TimeoutError:
                    # No chunks available, check if we should exit
                    if cancellation_task and cancellation_task.done():
                        logger.info(f"[AUDIO_GENERATOR:{session_id}] Timeout and cancellation task is done, exiting generator")
                        break
                    # Otherwise continue waiting
                    continue
                    
            except asyncio.CancelledError:
                logger.info(f"[AUDIO_GENERATOR:{session_id}] Generator cancelled after {chunk_count} chunks")
                break
                
            except Exception as e:
                logger.error(f"[AUDIO_GENERATOR:{session_id}] Error processing audio chunk: {e}")
                logger.error(traceback.format_exc())
                # Continue to next chunk despite error
                
    except GeneratorExit:
        logger.info(f"[AUDIO_GENERATOR:{session_id}] Generator exited after {chunk_count} chunks")
    
    finally:
        logger.info(f"[AUDIO_GENERATOR:{session_id}] Audio generator completed after {chunk_count} chunks")
