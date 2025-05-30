"""
Async Agent Factory for RedBarSushiAI.
This module provides a factory for creating and managing async agent instances.
"""

import logging
from typing import Dict, Any, Type, Optional

from app.agents.base_async import BaseAsyncAgent
from app.agents.menu_async import AsyncMenuAgent
from app.agents.menu_async_enhanced import AsyncMenuAgentEnhanced
from app.agents.cart_async import AsyncCartAgent
from app.agents.frontline_async_ai import AsyncFrontlineVoiceAgentAI
# Legacy import removed - using AI version only
AsyncFrontlineVoiceAgent = AsyncFrontlineVoiceAgentAI  # Alias for backward compatibility
from app.agents.guardrail_async import AsyncGuardrailAgent
from app.agents.fulfillment_async import AsyncFulfillmentAgent
from app.agents.escalation_async import AsyncEscalationAgent
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
        # Use AI-enhanced frontline agent if enabled
        use_ai_agents = getattr(settings, 'USE_AI_AGENTS', True)
        if use_ai_agents:
            self.register_agent_class("frontline", AsyncFrontlineVoiceAgentAI)
            logger.info("Using AI-enhanced frontline agent")
        else:
            self.register_agent_class("frontline", AsyncFrontlineVoiceAgent)
            logger.info("Using rule-based frontline agent")
            
        # Use enhanced menu agent if AI is enabled
        if use_ai_agents:
            self.register_agent_class("menu", AsyncMenuAgentEnhanced)
        else:
            self.register_agent_class("menu", AsyncMenuAgent)
        self.register_agent_class("cart", AsyncCartAgent)
        self.register_agent_class("guardrail", AsyncGuardrailAgent)
        self.register_agent_class("fulfillment", AsyncFulfillmentAgent)
        self.register_agent_class("escalation", AsyncEscalationAgent)
    
    def register_agent_class(self, agent_type: str, agent_class: Type[BaseAsyncAgent]):
        """
        Register an agent class with the factory.
        
        Args:
            agent_type: The type name for the agent
            agent_class: The agent class to register
        """
        self.agent_classes[agent_type] = agent_class
        logger.info(f"Registered agent class: {agent_type} -> {agent_class.__name__}")
    
    async def get_agent(self, agent_type: str, agent_id: Optional[str] = None, db=None) -> BaseAsyncAgent:
        """
        Get or create an agent instance.
        
        Args:
            agent_type: The type of agent to create
            agent_id: Optional specific agent ID to reuse
            db: Optional database session to pass to agents that need it
            
        Returns:
            The agent instance
            
        Raises:
            ValueError: If the agent type is not registered
        """
        # Create a cache key for this agent
        cache_key = f"{agent_type}:{agent_id}" if agent_id else agent_type
        
        # Check if we already have this agent
        if cache_key in self.agents:
            # Update the db if it's a menu or cart agent
            if (agent_type == "menu" or agent_type == "cart") and db is not None:
                self.agents[cache_key].db = db
            return self.agents[cache_key]
        
        # Create a new agent
        if agent_type in self.agent_classes:
            agent_class = self.agent_classes[agent_type]
            
            # Initialize the agent with appropriate parameters
            if (agent_type == "menu" or agent_type == "cart") and db is not None:
                # Menu and Cart agents need database session for async operations
                agent = agent_class(agent_id=agent_id, db=db)
            elif agent_id:
                agent = agent_class(agent_id=agent_id)
            else:
                agent = agent_class()
            
            # Store in cache
            self.agents[cache_key] = agent
            return agent
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")
    
    async def create_voice_agent_system(self, db=None) -> BaseAsyncAgent:
        """
        Create a complete voice agent system with all specialists.
        
        This sets up a frontline agent with menu, cart, and other specialist agents.
        
        Args:
            db: Optional database session to pass to agents that need it
            
        Returns:
            The configured frontline agent
        """
        # Create the frontline agent
        frontline_agent = await self.get_agent("frontline")
        
        # Create and register specialist agents
        menu_agent = await self.get_agent("menu", db=db)
        cart_agent = await self.get_agent("cart", db=db)
        
        # Register specialists with the frontline agent
        frontline_agent.register_specialist("menu", menu_agent)
        frontline_agent.register_specialist("cart", cart_agent)
        
        # Add more specialists as needed
        # e.g., fulfillment_agent, guardrail_agent, escalation_agent
        
        return frontline_agent

# Singleton instance for easy import
async_agent_factory = AsyncAgentFactory()