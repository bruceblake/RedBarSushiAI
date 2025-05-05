"""
Audio generator for streaming to the OpenAI Realtime API.

This module provides an asynchronous generator that processes audio chunks
from the Twilio Media Stream and forwards them to the OpenAI Realtime API.
"""

import asyncio
import logging
import time
import traceback
import json

# Set up logger
logger = logging.getLogger(__name__)

async def create_audio_generator(incoming_audio_queue, session_id, twilio_task):
    """
    Create an asynchronous generator that yields audio chunks for the Realtime API.
    
    Args:
        incoming_audio_queue: Queue containing incoming audio chunks
        session_id: Unique identifier for the session
        twilio_task: Reference to the Twilio message processing task
        
    Returns:
        An asynchronous generator yielding audio chunks
    """
    async def audio_generator():
        logger.info(f"[AUDIO:{session_id}] Starting audio generator")
        chunks_yielded = 0
        last_yield_time = time.time()
        generator_start_time = time.time()
        
        # Add a function to log generator stats
        def log_generator_stats(reason="periodic"):
            duration = time.time() - generator_start_time
            rate = chunks_yielded / duration if duration > 0 else 0
            time_since_last = time.time() - last_yield_time
            
            logger.info(f"[AUDIO:{session_id}] Generator stats ({reason}): {chunks_yielded} chunks yielded, "
                        f"{duration:.1f}s running, {rate:.1f} chunks/sec")
            logger.info(f"[AUDIO:{session_id}] Time since last yield: {time_since_last:.1f}s")
            
        try:
            # Log the initial state
            logger.info(f"[AUDIO:{session_id}] Audio generator ready, queue size: {incoming_audio_queue.qsize()}")
            
            while True:
                try:
                    # Use a timeout to prevent blocking forever
                    audio_chunk = await asyncio.wait_for(incoming_audio_queue.get(), timeout=15.0)
                    chunks_yielded += 1
                    last_yield_time = time.time()
                    
                    # Log progress with different frequencies based on count
                    if chunks_yielded == 1:
                        # Always log the first chunk
                        logger.info(f"[AUDIO:{session_id}] ✅ First audio chunk yielded, size: {len(audio_chunk)} bytes")
                    elif chunks_yielded <= 10 and chunks_yielded % 2 == 0:
                        # Log early chunks more frequently
                        logger.debug(f"[AUDIO:{session_id}] Audio generator yielded chunk #{chunks_yielded}, size: {len(audio_chunk)} bytes")
                    elif chunks_yielded % 100 == 0:
                        # Log periodic statistics
                        log_generator_stats("periodic")
                    
                    # Yield the audio chunk to the Realtime API
                    yield audio_chunk
                    
                    # Mark the task as done
                    incoming_audio_queue.task_done()
                
                except asyncio.TimeoutError:
                    # Log timeout with increasing severity based on time since last yield
                    time_since_last = time.time() - last_yield_time
                    
                    if time_since_last < 20:
                        logger.debug(f"[AUDIO:{session_id}] No audio received for {time_since_last:.1f}s in generator")
                    elif time_since_last < 30:
                        logger.info(f"[AUDIO:{session_id}] No audio received for {time_since_last:.1f}s in generator")
                    else:
                        logger.warning(f"[AUDIO:{session_id}] ⚠️ No audio received for {time_since_last:.1f}s in generator")
                    
                    # Log generator stats on timeout
                    log_generator_stats("timeout")
                    
                    # Check if we should exit due to inactivity
                    if twilio_task.done():
                        logger.warning(f"[AUDIO:{session_id}] Exiting audio generator - Twilio task is complete")
                        break
                        
                    if time_since_last > 60:
                        logger.warning(f"[AUDIO:{session_id}] Exiting audio generator - no audio for 60+ seconds")
                        break
                        
                    # Otherwise keep waiting
                    continue
                
                except Exception as chunk_error:
                    logger.error(f"[AUDIO:{session_id}] ❌ Error getting audio chunk: {chunk_error}")
                    logger.error(traceback.format_exc())
                    
                    # Continue trying to get more chunks - more resilient
                    continue
                    
        except Exception as gen_error:
            logger.error(f"[AUDIO:{session_id}] ❌ Fatal audio generator error: {gen_error}")
            logger.error(traceback.format_exc())
            
        finally:
            # Log final stats
            duration = time.time() - generator_start_time
            rate = chunks_yielded / duration if duration > 0 else 0
            logger.info(f"[AUDIO:{session_id}] Audio generator exiting after yielding "
                        f"{chunks_yielded} chunks over {duration:.1f}s ({rate:.1f} chunks/sec)")
    
    return audio_generator()