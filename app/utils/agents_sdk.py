"""
OpenAI Agents SDK integration for RedBarSushiAI.
This module provides the core infrastructure for working with the OpenAI Agents SDK.
"""

import os
import json
import logging
import time
import asyncio
from typing import Dict, List, Any, Optional, Union, Callable
import openai
from app.utils.openai_compat import tool

# Try importing from the new SDK structure, but fallback if not available
try:
    from openai import AgentsClient
except ImportError:
    # Create a dummy class for compatibility
    AgentsClient = type('AgentsClient', (), {})

# Try to import agent types with fallbacks
try:
    from openai.types.agent import (
        Agent, 
    Tool,
    Message, 
    Run,
    GuardrailSettings,
    ToolOutput
)
from openai.types.agent.thread import Thread
from redis import Redis
from flask import current_app, g

# Configure logging
logger = logging.getLogger(__name__)

# Ensure OpenAI API key is available
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY environment variable not set! Agent features will be limited.")
    # For production: look for a fallback API key
    try:
        api_key_path = "/home/pegasus/mysite/openai_key.txt"
        for path in [
            api_key_path,
            "/home/pegasus/openai_key.txt",
            os.path.join(os.path.dirname(__file__), "..", "..", "openai_key.txt"),
        ]:
            if os.path.exists(path):
                with open(path, "r") as f:
                    OPENAI_API_KEY = f.read().strip()
                    logger.info(f"Found API key in {path}")
                    break
    except Exception as e:
        logger.error(f"Error loading API key from file: {e}")

# Configure the OpenAI client
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY
    # Create the Agents client
    agents_client = AgentsClient()
else:
    agents_client = None
    logger.error("No OpenAI API key available; Agents SDK features will not work")

# Redis configuration - reuse from conversation_store
REDIS_URL = os.environ.get("REDIS_URL") or os.environ.get("CELERY_BROKER_URL") or "redis://localhost:6379/0"
REDIS_TTL = 7200  # 2 hours, matching conversation_store

# Initialize Redis
def get_redis_client():
    """Get or initialize the Redis client."""
    if not hasattr(g, 'redis_client'):
        try:
            g.redis_client = Redis.from_url(REDIS_URL, socket_timeout=2.0)
            # Test connection
            g.redis_client.ping()
        except Exception as e:
            logger.error(f"Failed to initialize Redis connection: {str(e)}")
            g.redis_client = None
    return g.redis_client

# Thread management
def get_thread_id(call_sid: str) -> Optional[str]:
    """
    Get the thread ID for a call SID from Redis.
    
    Args:
        call_sid: The Twilio call SID
        
    Returns:
        The thread ID if found, None otherwise
    """
    redis_client = get_redis_client()
    if not redis_client:
        return None
    
    thread_id = redis_client.get(f"call:{call_sid}")
    if thread_id:
        return thread_id.decode('utf-8')
    return None

def set_thread_id(call_sid: str, thread_id: str) -> bool:
    """
    Store a thread ID for a call SID in Redis.
    
    Args:
        call_sid: The Twilio call SID
        thread_id: The thread ID to store
        
    Returns:
        True if successful, False otherwise
    """
    redis_client = get_redis_client()
    if not redis_client:
        return False
    
    try:
        redis_client.setex(f"call:{call_sid}", REDIS_TTL, thread_id)
        return True
    except Exception as e:
        logger.error(f"Failed to store thread ID: {str(e)}")
        return False

def create_or_get_thread(call_sid: str) -> Optional[Thread]:
    """
    Get an existing thread ID or create a new one if it doesn't exist.
    
    Args:
        call_sid: The Twilio call SID
        
    Returns:
        The thread object if successful, None otherwise
    """
    if not agents_client:
        logger.error("Agents client not available")
        return None
    
    try:
        # Check if we have a thread ID for this call
        thread_id = get_thread_id(call_sid)
        
        if thread_id:
            # Try to use the existing thread
            try:
                return agents_client.threads.retrieve(thread_id)
            except Exception as e:
                logger.error(f"Failed to retrieve thread {thread_id}: {str(e)}")
                # Fall through to create a new thread
        
        # Create a new thread
        thread = agents_client.threads.create()
        if thread and thread.id:
            logger.info(f"Created new thread {thread.id} for call {call_sid}")
            set_thread_id(call_sid, thread.id)
            return thread
        
    except Exception as e:
        logger.error(f"Error in create_or_get_thread: {str(e)}")
    
    return None

# Agent management
def register_agent(
    name: str,
    instructions: str,
    tools: List[Tool],
    model: str = "gpt-4.1-mini",
    description: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
    guardrails: Optional[Dict[str, Any]] = None
) -> Optional[Agent]:
    """
    Register an agent with OpenAI.
    
    Args:
        name: The name of the agent
        instructions: The system instructions for the agent
        tools: List of tools the agent can use
        model: The model to use (default: gpt-4.1-mini)
        description: Optional description
        metadata: Optional metadata
        guardrails: Optional guardrail settings
        
    Returns:
        The agent object if successful, None otherwise
    """
    if not agents_client:
        logger.error("Agents client not available")
        return None
    
    try:
        # Convert guardrails to proper settings if provided
        guardrail_settings = None
        if guardrails:
            guardrail_settings = GuardrailSettings(**guardrails)
        
        # Create the agent
        agent = agents_client.agents.create(
            name=name,
            description=description,
            model=model,
            instructions=instructions,
            tools=tools,
            metadata=metadata,
            guardrails=guardrail_settings
        )
        
        logger.info(f"Registered agent {name} with ID {agent.id}")
        return agent
    
    except Exception as e:
        logger.error(f"Failed to register agent: {str(e)}")
        return None

# Common tool decorators and utilities
def validate_order_total(result: Dict[str, Any]) -> bool:
    """Example validation function for order total."""
    return result.get("total_price", 0) <= 30000  # $300.00

# Create a decorator for guardrails
def guardrail(
    on: str = "tool_response",
    check: Callable = lambda *args, **kwargs: True,
    on_fail: str = "retry",
    max_retries: int = 2,
    message: Optional[str] = None
):
    """
    Decorator for applying guardrails to tools.
    
    Args:
        on: What to check ('tool_response', 'user_message', etc.)
        check: Function that returns True if check passes, False otherwise
        on_fail: What to do if check fails ('retry', 'escalate', etc.)
        max_retries: Maximum number of retries
        message: Message to show if check fails
        
    Returns:
        Decorated function
    """
    def decorator(func):
        # Store guardrail info in function metadata
        func._guardrail = {
            "on": on,
            "check": check,
            "on_fail": on_fail,
            "max_retries": max_retries,
            "message": message
        }
        
        # Wrap the function
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            # Apply the guardrail check
            if on == "tool_response" and not check(result=result):
                if message:
                    logger.warning(f"Guardrail failed: {message}")
                
                # Handle failure according to on_fail strategy
                if on_fail == "retry":
                    # In actual implementation, this would signal the agent to retry
                    # Here we just log the failure
                    logger.warning(f"Guardrail check failed for {func.__name__}")
                elif on_fail == "escalate":
                    # In actual implementation, this would trigger escalation
                    logger.warning(f"Guardrail failure triggering escalation for {func.__name__}")
                
                # For now, still return the result
                # Real implementation would handle this differently based on the SDK
            
            return result
        
        # Keep the original function metadata
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        wrapper._guardrail = func._guardrail
        
        return wrapper
    
    return decorator

# Voice specific utilities
def text_to_speech(text: str, voice: str = "alloy") -> bytes:
    """
    Convert text to speech using OpenAI's API.
    
    Args:
        text: The text to convert to speech
        voice: The voice to use
        
    Returns:
        Audio data as bytes
    """
    try:
        response = openai.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text
        )
        return response.read()
    except Exception as e:
        logger.error(f"Error in text_to_speech: {str(e)}")
        return b""

# Realtime audio processing (will be expanded in later tasks)
async def process_realtime_audio(audio_stream, call_sid: str):
    """
    Process realtime audio through OpenAI.
    
    Args:
        audio_stream: Async generator yielding audio chunks
        call_sid: The Twilio call SID
        
    Returns:
        Async generator yielding response chunks
    """
    # This is a placeholder that will be expanded in task #8
    logger.info(f"Processing realtime audio for call {call_sid}")
    
    # For now, just echo the chunks as a placeholder
    async for chunk in audio_stream:
        yield {"type": "transcript_partial", "text": "Processing..."}
    
    yield {"type": "transcript_complete", "text": "Audio processing not yet implemented"}