"""
Enhanced Agent factory for RedBarSushiAI with orchestration support.
This module provides a factory to create and connect all agents in the system,
including support for the advanced agentic patterns.
"""

import os
import json
import logging
from typing import Dict, Any, Optional

from app.agents.frontline import FrontlineVoiceAgent
from app.agents.frontline_with_orchestration import OrchestratedFrontlineAgent
from app.agents.menu import MenuAgent
from app.agents.cart import CartAgent
from app.agents.guardrail import GuardrailAgent
from app.agents.fulfillment import FulfillmentAgent
from app.agents.escalation import EscalationAgent
from app.utils.agents_sdk import agents_client
from app.utils.agent_orchestration import (
    AgentGraph, 
    SlotStore, 
    FSMOrchestrator,
    ModelEscalator,
    initialize_orchestrators
)

logger = logging.getLogger(__name__)

class EnhancedAgentFactory:
    """Factory for creating and connecting agents with orchestration support."""
    
    def __init__(self, use_orchestration: bool = True):
        """
        Initialize the enhanced agent factory.
        
        Args:
            use_orchestration: Whether to use the orchestrated agents (default: True)
        """
        self.agents = {}
        self.frontline_agent = None
        self.menu_agent = None
        self.cart_agent = None
        self.fulfillment_agent = None
        self.escalation_agent = None
        self.guardrail_agent = None
        self.use_orchestration = use_orchestration
        
        # If using orchestration, initialize the orchestration components
        if self.use_orchestration:
            self.agent_graph, self.slot_store, self.fsm_orchestrator, self.model_escalator = initialize_orchestrators()
        else:
            self.agent_graph = None
            self.slot_store = None
            self.fsm_orchestrator = None
            self.model_escalator = None
    
    def create_agents(self):
        """
        Create all agents and connect them.
        
        Returns:
            The frontline agent as the primary entry point
        """
        # Check if we have Agents SDK support
        if not agents_client:
            logger.error("Agents SDK not available. Cannot create agents.")
            return None
        
        # Create the agents
        try:
            # Phase 1: Create main voice agent and menu agent
            self.frontline_agent = self._create_frontline_agent()
            self.menu_agent = self._create_menu_agent()
            
            # Phase 2: Create cart agent
            self.cart_agent = self._create_cart_agent()
            
            # Phase 3: Create fulfillment agent
            self.fulfillment_agent = self._create_fulfillment_agent()
            
            # Phase 4: Create guardrail agent
            self.guardrail_agent = self._create_guardrail_agent()
            
            # Phase 5: Create escalation agent
            self.escalation_agent = self._create_escalation_agent()
            
            # Register specialists with the frontline agent
            if self.frontline_agent:
                if self.menu_agent:
                    self.frontline_agent.register_specialist("menu", self.menu_agent)
                    logger.info("Registered Menu Agent with Frontline Voice Agent")
                
                if self.cart_agent:
                    self.frontline_agent.register_specialist("cart", self.cart_agent)
                    logger.info("Registered Cart Agent with Frontline Voice Agent")
                
                if self.fulfillment_agent:
                    self.frontline_agent.register_specialist("fulfillment", self.fulfillment_agent)
                    logger.info("Registered Fulfillment Agent with Frontline Voice Agent")
                
                if self.guardrail_agent:
                    self.frontline_agent.register_specialist("guardrail", self.guardrail_agent)
                    logger.info("Registered Guardrail Agent with Frontline Voice Agent")
                
                if self.escalation_agent:
                    self.frontline_agent.register_specialist("escalation", self.escalation_agent)
                    logger.info("Registered Escalation Agent with Frontline Voice Agent")
            
            # Register guardrail with specialist agents for policy enforcement
            if self.guardrail_agent:
                if self.menu_agent:
                    self.menu_agent.register_policy_agent(self.guardrail_agent)
                    logger.info("Registered Guardrail Agent with Menu Agent")
                
                if self.cart_agent:
                    self.cart_agent.register_policy_agent(self.guardrail_agent)
                    logger.info("Registered Guardrail Agent with Cart Agent")
                
                if self.fulfillment_agent:
                    self.fulfillment_agent.register_policy_agent(self.guardrail_agent)
                    logger.info("Registered Guardrail Agent with Fulfillment Agent")
            
            # Store all agents in a dictionary for easy access
            self.agents = {
                "frontline": self.frontline_agent,
                "menu": self.menu_agent,
                "cart": self.cart_agent,
                "fulfillment": self.fulfillment_agent,
                "guardrail": self.guardrail_agent,
                "escalation": self.escalation_agent
            }
            
            logger.info("Successfully created and connected all agents")
            return self.frontline_agent
            
        except Exception as e:
            logger.error(f"Error creating agents: {str(e)}")
            return None
    
    def _create_frontline_agent(self) -> Optional[FrontlineVoiceAgent]:
        """
        Create the frontline voice agent.
        
        Returns:
            The frontline voice agent if successful, None otherwise
        """
        try:
            agent_id = os.environ.get("OPENAI_FRONTLINE_AGENT_ID")
            
            if self.use_orchestration:
                agent = OrchestratedFrontlineAgent(agent_id=agent_id)
                logger.info(f"Created Orchestrated Frontline Voice Agent with ID: {agent.agent_id}")
            else:
                agent = FrontlineVoiceAgent(agent_id=agent_id)
                logger.info(f"Created Standard Frontline Voice Agent with ID: {agent.agent_id}")
                
            return agent
        except Exception as e:
            logger.error(f"Failed to create Frontline Voice Agent: {str(e)}")
            return None
    
    def _create_menu_agent(self) -> Optional[MenuAgent]:
        """
        Create the menu agent.
        
        Returns:
            The menu agent if successful, None otherwise
        """
        try:
            agent_id = os.environ.get("OPENAI_MENU_AGENT_ID")
            agent = MenuAgent(agent_id=agent_id)
            logger.info(f"Created Menu Agent with ID: {agent.agent_id}")
            return agent
        except Exception as e:
            logger.error(f"Failed to create Menu Agent: {str(e)}")
            return None
    
    def _create_cart_agent(self) -> Optional[CartAgent]:
        """
        Create the cart agent.
        
        Returns:
            The cart agent if successful, None otherwise
        """
        try:
            agent_id = os.environ.get("OPENAI_CART_AGENT_ID")
            agent = CartAgent(agent_id=agent_id)
            logger.info(f"Created Cart Agent with ID: {agent.agent_id}")
            return agent
        except Exception as e:
            logger.error(f"Failed to create Cart Agent: {str(e)}")
            return None
    
    def _create_fulfillment_agent(self) -> Optional[FulfillmentAgent]:
        """
        Create the fulfillment agent.
        
        Returns:
            The fulfillment agent if successful, None otherwise
        """
        try:
            agent_id = os.environ.get("OPENAI_FULFILLMENT_AGENT_ID")
            agent = FulfillmentAgent(agent_id=agent_id)
            logger.info(f"Created Fulfillment Agent with ID: {agent.agent_id}")
            return agent
        except Exception as e:
            logger.error(f"Failed to create Fulfillment Agent: {str(e)}")
            return None
    
    def _create_guardrail_agent(self) -> Optional[GuardrailAgent]:
        """
        Create the guardrail agent.
        
        Returns:
            The guardrail agent if successful, None otherwise
        """
        try:
            agent_id = os.environ.get("OPENAI_GUARDRAIL_AGENT_ID")
            agent = GuardrailAgent(agent_id=agent_id)
            logger.info(f"Created Guardrail Agent with ID: {agent.agent_id}")
            return agent
        except Exception as e:
            logger.error(f"Failed to create Guardrail Agent: {str(e)}")
            return None
    
    def _create_escalation_agent(self) -> Optional[EscalationAgent]:
        """
        Create the escalation agent.
        
        Returns:
            The escalation agent if successful, None otherwise
        """
        try:
            agent_id = os.environ.get("OPENAI_ESCALATION_AGENT_ID")
            agent = EscalationAgent(agent_id=agent_id)
            logger.info(f"Created Escalation Agent with ID: {agent.agent_id}")
            return agent
        except Exception as e:
            logger.error(f"Failed to create Escalation Agent: {str(e)}")
            return None
    
    def get_agent(self, agent_name: str) -> Any:
        """
        Get an agent by name.
        
        Args:
            agent_name: The name of the agent
            
        Returns:
            The agent if found, None otherwise
        """
        return self.agents.get(agent_name.lower())
    
    def get_frontline_agent(self) -> Optional[FrontlineVoiceAgent]:
        """
        Get the frontline voice agent.
        
        Returns:
            The frontline voice agent
        """
        return self.frontline_agent
    
    def get_menu_agent(self) -> Optional[MenuAgent]:
        """
        Get the menu agent.
        
        Returns:
            The menu agent
        """
        return self.menu_agent
    
    def get_cart_agent(self) -> Optional[CartAgent]:
        """
        Get the cart agent.
        
        Returns:
            The cart agent
        """
        return self.cart_agent
    
    def get_fulfillment_agent(self) -> Optional[FulfillmentAgent]:
        """
        Get the fulfillment agent.
        
        Returns:
            The fulfillment agent
        """
        return self.fulfillment_agent
    
    def get_guardrail_agent(self) -> Optional[GuardrailAgent]:
        """
        Get the guardrail agent.
        
        Returns:
            The guardrail agent
        """
        return self.guardrail_agent
    
    def get_escalation_agent(self) -> Optional[EscalationAgent]:
        """
        Get the escalation agent.
        
        Returns:
            The escalation agent
        """
        return self.escalation_agent

# Singleton instance for easy import
enhanced_agent_factory = EnhancedAgentFactory(use_orchestration=True)