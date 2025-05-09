"""
Async Agent Factory for RedBarSushiAI.
This module provides a factory for creating and managing async agent instances.
"""

import logging
from typing import Dict, Any, Type, Optional

from app.agents.base_async import BaseAsyncAgent
from app.agents.menu_async import AsyncMenuAgent
from app.agents.cart_async import AsyncCartAgent
from app.agents.frontline_async import AsyncFrontlineVoiceAgent
from app.config import settings

# Set up logging
logger = logging.getLogger(__name__)

class AsyncAgentFactory:
    """
    Factory for creating and managing async agent instances.
    
    This factory maintains a registry of agent classes and instantiated agents,
    allowing for easy creation and reuse of agent instances.
    """
    
    def __init__(self):
        """Initialize the async agent factory."""
        self.agent_classes: Dict[str, Type[BaseAsyncAgent]] = {}
        self.agents: Dict[str, BaseAsyncAgent] = {}
        
        # Register standard agents
        self.register_agent_class("frontline", AsyncFrontlineVoiceAgent)
        self.register_agent_class("menu", AsyncMenuAgent)
        self.register_agent_class("cart", AsyncCartAgent)
    
    def register_agent_class(self, agent_type: str, agent_class: Type[BaseAsyncAgent]):
        """
        Register an agent class with the factory.
        
        Args:
            agent_type: The type name for the agent
            agent_class: The agent class to register
        """
        self.agent_classes[agent_type] = agent_class
        logger.info(f"Registered agent class: {agent_type} -> {agent_class.__name__}")
    
    async def get_agent(self, agent_type: str, agent_id: Optional[str] = None) -> BaseAsyncAgent:
        """
        Get or create an agent instance.
        
        Args:
            agent_type: The type of agent to create
            agent_id: Optional specific agent ID to reuse
            
        Returns:
            The agent instance
            
        Raises:
            ValueError: If the agent type is not registered
        """
        # Create a cache key for this agent
        cache_key = f"{agent_type}:{agent_id}" if agent_id else agent_type
        
        # Check if we already have this agent
        if cache_key in self.agents:
            return self.agents[cache_key]
        
        # Create a new agent
        if agent_type in self.agent_classes:
            agent_class = self.agent_classes[agent_type]
            
            # Initialize the agent
            if agent_id:
                agent = agent_class(agent_id=agent_id)
            else:
                agent = agent_class()
            
            # Store in cache
            self.agents[cache_key] = agent
            return agent
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")
    
    async def create_voice_agent_system(self) -> BaseAsyncAgent:
        """
        Create a complete voice agent system with all specialists.
        
        This sets up a frontline agent with menu, cart, and other specialist agents.
        
        Returns:
            The configured frontline agent
        """
        # Create the frontline agent
        frontline_agent = await self.get_agent("frontline")
        
        # Create and register specialist agents
        menu_agent = await self.get_agent("menu")
        cart_agent = await self.get_agent("cart")
        
        # Register specialists with the frontline agent
        frontline_agent.register_specialist("menu", menu_agent)
        frontline_agent.register_specialist("cart", cart_agent)
        
        # Add more specialists as needed
        # e.g., fulfillment_agent, guardrail_agent, escalation_agent
        
        return frontline_agent

# Singleton instance for easy import
async_agent_factory = AsyncAgentFactory()