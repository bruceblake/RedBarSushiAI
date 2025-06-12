"""
Base async agent class for the agent system.

This module provides a base class for implementing asynchronous agents
in the RedBarSushiAI system.
"""

import logging
import time
from typing import Dict, Any, Optional, List, Tuple  # Callable removed


# Set up logging
logger = logging.getLogger(__name__)


class BaseAsyncAgent:
    """
    Base class for all asynchronous agents in the system.

    This class provides common functionality and interfaces for agents,
    such as handling inputs, generating responses, and managing state.
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
        name: str = "BaseAgent",
        agent_name: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize the agent.

        Args:
            agent_id: Optional ID for the agent (used with OpenAI Assistants API)
            name: Name of the agent for logging and identification
            agent_name: Alternative name parameter (for compatibility with subclasses)
            **kwargs: Additional keyword arguments for extended functionality
        """
        self.agent_id = agent_id or f"agent_{int(time.time())}"
        # Handle both name and agent_name for backward compatibility
        self.name = agent_name or name
        self.agent_name = self.name  # Add agent_name as an alias for name
        self.specialists = {}  # For registering specialist agents
        self.policy_agent = None  # For policy enforcement
        self.context = {}  # For maintaining conversation context

        logger.info(f"BaseAsyncAgent initialized with name: {self.name}")

    async def process_input(
        self, input_text: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
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
            "actions": [],
        }

        return response

    async def process_voice_input(
        self, input_text: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
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

    async def validate(
        self, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Dict[str, Any]]:
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

    async def execute_tool(
        self, tool_name: str, args: Dict[str, Any]
    ) -> Dict[str, Any]:
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
            "message": f"Tool '{tool_name}' not implemented by {self.name}",
        }

    def register_specialist(self, role: str, agent: "BaseAsyncAgent") -> None:
        """
        Register a specialist agent for handling specific tasks.

        Args:
            role: The role of the specialist
            agent: The specialist agent
        """
        self.specialists[role] = agent
        logger.info(f"[{self.name}] Registered {agent.name} as {role} specialist")

    def update_context(self, context: Dict[str, Any]) -> None:
        """
        Update the agent's context with new information.

        Args:
            context: New context information to merge
        """
        if context is not None and isinstance(context, dict):
            self.context.update(context)

    def get_context(self) -> Dict[str, Any]:
        """
        Get the agent's current context.

        Returns:
            Dict[str, Any]: A deep copy of the agent's context
        """
        import copy

        return copy.deepcopy(self.context)

    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Get the tools supported by this agent.

        Returns:
            List[Dict[str, Any]]: List of tool definitions
        """
        # Default implementation - should be overridden by subclasses
        return []
