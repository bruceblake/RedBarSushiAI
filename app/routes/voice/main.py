"""
Main module for voice routes and integration with Flask.

This module provides integration points for the voice routes in the RedBarSushiAI 
application, implementing real-time audio processing with orchestrated agents.
"""

import logging
import os
import importlib

# Set up logger
logger = logging.getLogger(__name__)

def initialize_voice_routes(app):
    """
    Initialize voice routes and components.
    
    Args:
        app: The Flask application instance
    """
    logger.info("[VOICE] Initializing voice routes and components")
    
    # Import voice routes package
    from app.routes.voice import init_voice_routes
    
    # Initialize voice routes
    init_voice_routes(app)
    
    # Initialize the agents and tool registry
    from app.agents.factory_with_orchestration import enhanced_agent_factory
    from app.utils.agent_orchestration import (
        AgentGraph, SlotStore, FSMOrchestrator, ModelEscalator,
        initialize_orchestrators
    )
    from app.routes.voice.utils.tools_registry import ToolRegistry, register_default_tools
    
    # Get or create agent components
    frontline_agent = enhanced_agent_factory.create_agents()
    agent_graph, slot_store, fsm_orchestrator, model_escalator = initialize_orchestrators()
    
    # Create and register tools
    tool_registry = ToolRegistry()
    register_default_tools(frontline_agent, tool_registry)
    
    # Make components available globally
    from app.routes.voice import set_global_components
    set_global_components(
        frontline_agent=frontline_agent,
        agent_graph=agent_graph,
        slot_store=slot_store,
        fsm_orchestrator=fsm_orchestrator,
        model_escalator=model_escalator,
        tool_registry=tool_registry
    )
    
    # Log successful initialization
    logger.info("[VOICE] Voice routes and components initialized successfully")
    
    # Return the initialized components
    return {
        "status": "initialized",
        "frontline_agent": frontline_agent is not None,
        "fsm_orchestrator": fsm_orchestrator is not None,
        "tool_registry": tool_registry is not None
    }

def get_voice_bp():
    """
    Get the voice blueprint.
    
    Returns:
        The voice realtime blueprint
    """
    from app.routes.voice.blueprints import realtime_voice_bp
    return realtime_voice_bp