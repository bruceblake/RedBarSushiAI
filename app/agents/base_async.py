"""
Base async agent class for the agent system.

This module provides a base class for implementing asynchronous agents
in the RedBarSushiAI system.
"""

import logging
import json
import time
import asyncio
from typing import Dict, Any, Optional, List, Tuple, Union, Callable

from app.config import settings

# Set up logging
logger = logging.getLogger(__name__)

class BaseAsyncAgent:
    """
    Base class for all asynchronous agents in the system.
    
    This class provides common functionality and interfaces for agents,
    such as handling inputs, generating responses, and managing state.
    """
    
    def __init__(self, agent_id: Optional[str] = None, name: str = "BaseAgent"):
        """
        Initialize the agent.
        
        Args:
            agent_id: Optional ID for the agent (used with OpenAI Assistants API)
            name: Name of the agent for logging and identification
        """
        self.agent_id = agent_id or f"agent_{int(time.time())}"
        self.name = name
        self.specialists = {}  # For registering specialist agents
        self.policy_agent = None  # For policy enforcement
        self.context = {}  # For maintaining conversation context
        
    async def process_input(self, input_text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a text input and generate a response.
        
        Args:
            input_text: The text input to process
            context: Optional context information
            
        Returns:
            Dict[str, Any]: The agent's response
        """
        context = context or {}
        self.update_context(context)
        
        # Default implementation - should be overridden by subclasses
        logger.info(f"[{self.name}] Processing input: {input_text}")
        
        # Placeholder for agent-specific processing
        response = {
            "text": f"[{self.name}] Processed: {input_text}",
            "agent": self.name,
            "handled": True,
            "actions": []
        }
        
        return response
    
    async def process_voice_input(self, input_text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a voice input and generate a response.
        
        This is a convenience method that calls process_input, but may be
        overridden for voice-specific processing.
        
        Args:
            input_text: The voice input to process
            context: Optional context information
            
        Returns:
            Dict[str, Any]: The agent's response
        """
        return await self.process_input(input_text, context)
    
    async def validate(self, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate data against policies.
        
        Args:
            data: The data to validate
            context: Optional context information
            
        Returns:
            Tuple[bool, Dict[str, Any]]: Validation result (is_valid, details)
        """
        context = context or {}
        
        # If there's a policy agent, use it
        if self.policy_agent:
            return await self.policy_agent.validate(data, context)
        
        # Default implementation - should be overridden by subclasses
        logger.info(f"[{self.name}] Validating data: {data}")
        
        return True, {"message": "Validation not implemented", "details": {}}
    
    async def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool owned by this agent.
        
        Args:
            tool_name: The name of the tool to execute
            args: Arguments for the tool
            
        Returns:
            Dict[str, Any]: The tool's result
        """
        # Default implementation - should be overridden by subclasses
        logger.warning(f"[{self.name}] Tool '{tool_name}' not implemented")
        
        return {
            "status": "error",
            "message": f"Tool '{tool_name}' not implemented by {self.name}"
        }
    
    def register_specialist(self, role: str, agent: 'BaseAsyncAgent') -> None:
        """
        Register a specialist agent for handling specific tasks.
        
        Args:
            role: The role of the specialist
            agent: The specialist agent
        """
        self.specialists[role] = agent
        logger.info(f"[{self.name}] Registered {agent.name} as {role} specialist")
    
    def register_policy_agent(self, agent: 'BaseAsyncAgent') -> None:
        """
        Register a policy agent for enforcing policies.
        
        Args:
            agent: The policy agent
        """
        self.policy_agent = agent
        logger.info(f"[{self.name}] Registered {agent.name} as policy agent")
    
    async def delegate_to_specialist(self, role: str, input_text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Delegate processing to a specialist agent.
        
        Args:
            role: The role of the specialist to delegate to
            input_text: The text input to process
            context: Optional context information
            
        Returns:
            Dict[str, Any]: The specialist's response
        """
        context = context or {}
        
        if role in self.specialists:
            specialist = self.specialists[role]
            logger.info(f"[{self.name}] Delegating to {specialist.name} ({role}): {input_text}")
            
            # Copy the context to avoid modification
            specialist_context = context.copy()
            specialist_context["delegated_by"] = self.name
            
            # Process with the specialist
            response = await specialist.process_input(input_text, specialist_context)
            
            return response
        else:
            logger.warning(f"[{self.name}] No specialist registered for role '{role}'")
            
            return {
                "text": f"I don't have a specialist for '{role}'.",
                "agent": self.name,
                "handled": False,
                "actions": []
            }
    
    def update_context(self, context: Dict[str, Any]) -> None:
        """
        Update the agent's context with new information.
        
        Args:
            context: New context information to merge
        """
        self.context.update(context)
    
    def get_context(self) -> Dict[str, Any]:
        """
        Get the agent's current context.
        
        Returns:
            Dict[str, Any]: The agent's context
        """
        return self.context.copy()
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Get the tools supported by this agent.
        
        Returns:
            List[Dict[str, Any]]: List of tool definitions
        """
        # Default implementation - should be overridden by subclasses
        return []