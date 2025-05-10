"""
Testing and debugging endpoints for voice interactions.

This module contains HTTP endpoints for testing and debugging voice interactions,
including FSM state management, tool execution, and voice input processing without
using WebSockets.
"""

import logging
import time
import traceback
from typing import Dict, Any

from fastapi import Request
from fastapi.responses import JSONResponse

from app.utils.agent_orchestration_async import async_agent_orchestrator
from app.utils.fsm_async import async_fsm_manager, ConversationEvent, ConversationState

# Set up logging
logger = logging.getLogger(__name__)

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