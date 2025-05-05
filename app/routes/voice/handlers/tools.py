"""
Handlers for tool call events in the voice workflow.

This module contains functions for processing tool call events
from the OpenAI Realtime API and executing the appropriate tools.
"""

import logging
import time
import json
import traceback

# Set up logger
logger = logging.getLogger(__name__)

async def handle_tool_call_event(ws, session_id, tool_registry, event, metrics):
    """
    Handle a tool_call event from the Realtime API.
    
    Args:
        ws: The WebSocket connection
        session_id: Session identifier
        tool_registry: The tool registry instance
        event: The tool_call event from the Realtime API
        metrics: Connection metrics dictionary
    """
    # Handle tool calls from the model
    metrics["tool_calls"] += 1
    tool_name = event.get("name", "")
    tool_arguments = event.get("arguments", {})
    tool_id = event.get("id", "")
    
    logger.info(f"[TOOL:{session_id}] Tool call #{metrics['tool_calls']}: {tool_name}")
    logger.debug(f"[TOOL:{session_id}] Tool arguments: {tool_arguments}")
    
    # Execute tool with frontline agent through registry
    try:
        if tool_registry and tool_name in tool_registry.tools:
            logger.info(f"[TOOL:{session_id}] Executing tool {tool_name} via registry")
            start_time = time.time()
            
            tool_result = tool_registry.execute_tool(
                tool_name, 
                tool_arguments, 
                session_id=session_id
            )
            
            execution_time = time.time() - start_time
            logger.info(f"[TOOL:{session_id}] ✅ Tool {tool_name} executed in {execution_time:.2f}s")
            logger.debug(f"[TOOL:{session_id}] Tool result: {tool_result}")
            
            # Send tool result back to WebSocket
            await ws.send(json.dumps({
                "event": "tool_result",
                "name": tool_name,
                "result": tool_result,
                "timestamp": time.time()
            }))
            metrics["events_sent"] += 1
        else:
            logger.warning(f"[TOOL:{session_id}] Tool {tool_name} not found in registry")
            
            # Send error response for missing tool
            await ws.send(json.dumps({
                "event": "error",
                "text": f"Tool '{tool_name}' not found in registry",
                "timestamp": time.time()
            }))
            metrics["events_sent"] += 1
            
    except Exception as tool_error:
        logger.error(f"[TOOL:{session_id}] ❌ Error executing tool {tool_name}: {tool_error}")
        logger.error(f"[TOOL:{session_id}] Tool error trace: {traceback.format_exc()}")
        
        # Send error to client
        await ws.send(json.dumps({
            "event": "error",
            "text": f"Error executing tool {tool_name}: {str(tool_error)}",
            "timestamp": time.time()
        }))
        metrics["events_sent"] += 1