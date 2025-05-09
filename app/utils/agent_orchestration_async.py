"""
Async Agent Orchestration for RedBarSushiAI.
This module provides tools for orchestrating async agent interactions and handling session state.
"""

import asyncio
import logging
import json
import time
from typing import Dict, List, Any, Optional, Union, Callable, Tuple

from app.agents.factory_async import async_agent_factory
from app.utils.conversation_store_async import async_conversation_store
from app.utils.conversation_store_sdk_async import async_agents_conversation_store
from app.utils.fsm_async import (
    async_fsm_manager, ConversationState, ConversationEvent, 
    AsyncConversationFSM
)
from app.config import settings

# Set up logging
logger = logging.getLogger(__name__)

class AsyncAgentOrchestrator:
    """
    Orchestrates interactions between async agents and manages conversation state.
    
    This class coordinates the flow of messages between different agent types,
    tracks conversation state, and maintains session context using an FSM.
    """
    
    def __init__(self):
        """Initialize the async agent orchestrator."""
        self.frontline_agent = None
        self.menu_agent = None
        self.cart_agent = None
        self.guardrail_agent = None
        self.fulfillment_agent = None
        self.escalation_agent = None
        self.active_sessions = {}
        self.conversation_store = async_conversation_store
    
    async def initialize(self):
        """Initialize the orchestrator and its agents."""
        # Create the complete voice agent system and get specialist agents
        self.frontline_agent = await async_agent_factory.create_voice_agent_system()
        self.menu_agent = await async_agent_factory.get_agent("menu")
        self.cart_agent = await async_agent_factory.get_agent("cart")
        self.guardrail_agent = await async_agent_factory.get_agent("guardrail")
        self.fulfillment_agent = await async_agent_factory.get_agent("fulfillment")
        self.escalation_agent = await async_agent_factory.get_agent("escalation")
        
        logger.info("Initialized async agent orchestrator with voice agent system")
    
    async def get_fsm(self, call_sid: str) -> AsyncConversationFSM:
        """
        Get or create an FSM for a session.
        
        Args:
            call_sid: The Twilio call SID for this session
            
        Returns:
            The FSM instance
        """
        # Get or create FSM from manager
        fsm = await async_fsm_manager.get_fsm(call_sid)
        
        # Ensure the FSM has access to all agents
        fsm.update_context({
            "frontline_agent": self.frontline_agent,
            "menu_agent": self.menu_agent,
            "cart_agent": self.cart_agent,
            "guardrail_agent": self.guardrail_agent,
            "fulfillment_agent": self.fulfillment_agent,
            "escalation_agent": self.escalation_agent
        })
        
        return fsm
    
    async def process_voice_input(
        self, 
        call_sid: str, 
        input_text: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a voice input with the FSM and appropriate agents.
        
        Args:
            call_sid: The Twilio call SID for this session
            input_text: The text input from the voice transcript
            context: Optional additional context
            
        Returns:
            The agent's response
        """
        if not self.frontline_agent:
            await self.initialize()
        
        # Ensure we have a context object
        if context is None:
            context = {}
        
        # Add call_sid to context
        context["call_sid"] = call_sid
        
        # Track active session
        if call_sid not in self.active_sessions:
            self.active_sessions[call_sid] = {
                "started_at": time.time(),
                "last_activity": time.time(),
                "state": ConversationState.GREETING.name
            }
        
        # Update last activity time
        self.active_sessions[call_sid]["last_activity"] = time.time()
        
        # Add the user message to conversation store
        await self.conversation_store.add_message(call_sid, "user", input_text)
        
        # Get or create FSM for this call
        fsm = await self.get_fsm(call_sid)
        
        # Process the transcript with the FSM
        start_time = time.time()
        
        # Add the transcript to FSM context
        fsm.update_context({"transcript": input_text})
        
        # Process with FSM
        await fsm.process_transcript(input_text)
        
        # Select the appropriate agent based on FSM state
        agent, response = await self._process_with_appropriate_agent(fsm, input_text, context)
        
        duration = time.time() - start_time
        
        # Extract information from response
        response_text = response.get("text", "")
        handled = response.get("handled", True)
        agent_name = response.get("agent", agent.__class__.__name__)
        actions = response.get("actions", [])
        
        # Add the assistant response to conversation store
        await self.conversation_store.add_message(call_sid, "assistant", response_text)
        
        # Update session state to match FSM state
        self.active_sessions[call_sid]["state"] = fsm.current_state.name
        
        # Log processing stats
        logger.info(f"Processed voice input in {duration:.2f}s through FSM state {fsm.current_state} with {agent_name}: {input_text[:50]}...")
        
        return {
            "text": response_text,
            "handled": handled,
            "agent": agent_name,
            "processing_time": duration,
            "actions": actions,
            "state": fsm.current_state.name,
            "fsm_context": {k: v for k, v in fsm.context.items() if isinstance(v, (str, int, float, bool, list, dict)) or v is None}
        }
    
    async def _process_with_appropriate_agent(
        self, 
        fsm: AsyncConversationFSM, 
        input_text: str, 
        context: Dict[str, Any]
    ) -> Tuple[Any, Dict[str, Any]]:
        """
        Process the input with the appropriate agent based on FSM state.
        
        Args:
            fsm: The FSM instance
            input_text: The text input from the user
            context: Additional context
            
        Returns:
            A tuple of (agent, response)
        """
        # Clone context to avoid modifying the FSM context directly
        agent_context = context.copy()
        agent_context.update({k: v for k, v in fsm.context.items() 
                             if not k.startswith("_") and k not in 
                             ["frontline_agent", "menu_agent", "cart_agent", 
                              "guardrail_agent", "fulfillment_agent", "escalation_agent"]})
        
        # Select the appropriate agent based on FSM state
        if fsm.current_state == ConversationState.MAIN_MENU:
            if fsm.context.get("requesting_menu_info", False):
                # Use menu agent for menu inquiries
                agent = self.menu_agent
                response = await agent.process_input(input_text, agent_context)
            else:
                # Use frontline agent for main menu
                agent = self.frontline_agent
                response = await agent.process_voice_input(input_text, agent_context)
        
        elif fsm.current_state == ConversationState.ORDERING:
            # Use cart agent for order management
            agent = self.cart_agent
            response = await agent.process_input(input_text, agent_context)
            
            # Check if order is complete
            if response.get("cart_complete", False):
                await fsm.trigger(ConversationEvent.COMPLETE_ORDER)
        
        elif fsm.current_state == ConversationState.VALIDATION:
            # Use guardrail agent for validation
            agent = self.guardrail_agent
            response = await agent.process_input(input_text, agent_context)
        
        elif fsm.current_state == ConversationState.CONFIRMATION:
            # Use frontline agent for confirmation
            agent = self.frontline_agent
            response = await agent.process_voice_input(input_text, agent_context)
            
            # Check if order is confirmed or rejected
            if response.get("order_confirmed", False):
                await fsm.trigger(ConversationEvent.CONFIRM_ORDER)
            elif response.get("order_rejected", False):
                await fsm.trigger(ConversationEvent.REJECT_ORDER)
        
        elif fsm.current_state == ConversationState.FULFILLMENT:
            # Use fulfillment agent for order processing
            agent = self.fulfillment_agent
            response = await agent.process_input(input_text, agent_context)
            
            # Check if fulfillment is complete
            if response.get("fulfillment_complete", False):
                await fsm.trigger(ConversationEvent.COMPLETE_INTERACTION)
        
        elif fsm.current_state == ConversationState.COMPLETION:
            # Use frontline agent for completion
            agent = self.frontline_agent
            response = await agent.process_voice_input(input_text, agent_context)
        
        elif fsm.current_state == ConversationState.FOLLOW_UP:
            # Use frontline agent for follow-up
            agent = self.frontline_agent
            response = await agent.process_voice_input(input_text, agent_context)
        
        elif fsm.current_state == ConversationState.ESCALATION:
            # Use escalation agent for escalation
            agent = self.escalation_agent
            response = await agent.process_input(input_text, agent_context)
        
        elif fsm.current_state == ConversationState.ERROR:
            # Use frontline agent for error recovery
            agent = self.frontline_agent
            response = await agent.process_voice_input(input_text, agent_context)
        
        else:  # GREETING or INITIAL
            # Use frontline agent as default
            agent = self.frontline_agent
            response = await agent.process_voice_input(input_text, agent_context)
        
        return agent, response
    
    async def process_tool_call(
        self, 
        call_sid: str, 
        tool_name: str, 
        args: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a tool call from the voice interface.
        
        Args:
            call_sid: The Twilio call SID for this session
            tool_name: The name of the tool to execute
            args: Arguments for the tool
            context: Optional additional context
            
        Returns:
            The tool execution result
        """
        if not self.frontline_agent:
            await self.initialize()
        
        # Ensure we have a context object
        if context is None:
            context = {}
        
        # Add call_sid to context
        context["call_sid"] = call_sid
        
        # Log the tool call
        logger.info(f"Processing tool call for {call_sid}: {tool_name} with args: {args}")
        
        # Update last activity time
        if call_sid in self.active_sessions:
            self.active_sessions[call_sid]["last_activity"] = time.time()
        
        # Get FSM for this call
        fsm = await self.get_fsm(call_sid)
        
        # Choose the right agent for the tool based on its name
        agent = self.frontline_agent  # Default
        
        if tool_name.startswith("menu_"):
            agent = self.menu_agent
        elif tool_name.startswith("cart_"):
            agent = self.cart_agent
        elif tool_name.startswith("guardrail_"):
            agent = self.guardrail_agent
        elif tool_name.startswith("fulfillment_"):
            agent = self.fulfillment_agent
        elif tool_name.startswith("escalation_"):
            agent = self.escalation_agent
        
        # Execute the tool
        start_time = time.time()
        result = await agent.execute_tool(tool_name, args)
        duration = time.time() - start_time
        
        # Handle FSM events based on tool results
        if tool_name == "cart_complete_order" and result.get("success", False):
            await fsm.trigger(ConversationEvent.COMPLETE_ORDER)
        elif tool_name == "confirm_order" and result.get("confirmed", False):
            await fsm.trigger(ConversationEvent.CONFIRM_ORDER)
        elif tool_name == "reject_order" and result.get("rejected", False):
            await fsm.trigger(ConversationEvent.REJECT_ORDER)
        elif tool_name == "process_order" and result.get("success", False):
            await fsm.trigger(ConversationEvent.COMPLETE_INTERACTION)
        elif tool_name == "escalate" and result.get("escalated", False):
            await fsm.trigger(ConversationEvent.REQUEST_ESCALATION)
        
        # Log tool execution stats
        logger.info(f"Executed tool {tool_name} in {duration:.2f}s for {call_sid}")
        
        return {
            "tool_name": tool_name,
            "result": result,
            "processing_time": duration,
            "fsm_state": fsm.current_state.name
        }
    
    async def get_session_state(self, call_sid: str) -> Dict[str, Any]:
        """
        Get the current session state.
        
        Args:
            call_sid: The Twilio call SID for this session
            
        Returns:
            The session state
        """
        # Get session info
        session_info = self.active_sessions.get(call_sid, {
            "started_at": time.time(),
            "last_activity": time.time(),
            "state": "UNKNOWN"
        })
        
        # Get FSM state if available
        try:
            fsm = await async_fsm_manager.get_fsm(call_sid)
            fsm_state = fsm.current_state.name
            fsm_context = {k: v for k, v in fsm.context.items() 
                         if isinstance(v, (str, int, float, bool, list, dict)) or v is None}
        except Exception as e:
            logger.error(f"Error getting FSM for {call_sid}: {str(e)}")
            fsm_state = "UNKNOWN"
            fsm_context = {}
        
        # Get conversation history
        conversation = await self.conversation_store.get_conversation(call_sid)
        
        # Get cart info if available
        try:
            cart = await async_agents_conversation_store.get_cart(call_sid)
        except Exception as e:
            logger.error(f"Error getting cart for {call_sid}: {str(e)}")
            cart = {"items": [], "total_price": 0}
        
        # Combine into complete state
        return {
            "call_sid": call_sid,
            "state": session_info.get("state", "UNKNOWN"),
            "fsm_state": fsm_state,
            "started_at": session_info.get("started_at"),
            "last_activity": session_info.get("last_activity"),
            "duration": time.time() - session_info.get("started_at", time.time()),
            "idle_time": time.time() - session_info.get("last_activity", time.time()),
            "conversation": conversation,
            "cart": cart,
            "fsm_context": fsm_context
        }
    
    async def start_new_conversation(self, call_sid: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Start a new conversation with initial greeting.
        
        Args:
            call_sid: The Twilio call SID
            context: Optional initial context
            
        Returns:
            The initial greeting response
        """
        if not self.frontline_agent:
            await self.initialize()
        
        # Create a new session
        self.active_sessions[call_sid] = {
            "started_at": time.time(),
            "last_activity": time.time(),
            "state": ConversationState.GREETING.name
        }
        
        # Create a new FSM and start it
        context_with_agents = {
            "frontline_agent": self.frontline_agent,
            "menu_agent": self.menu_agent,
            "cart_agent": self.cart_agent,
            "guardrail_agent": self.guardrail_agent,
            "fulfillment_agent": self.fulfillment_agent,
            "escalation_agent": self.escalation_agent,
            "call_sid": call_sid
        }
        
        if context:
            context_with_agents.update(context)
        
        fsm = await async_fsm_manager.start_conversation(call_sid, context_with_agents)
        
        # Get greeting from FSM context
        greeting_response = fsm.context.get("greeting_response", {})
        
        # If no greeting in FSM, generate one with frontline agent
        if not greeting_response:
            greeting_response = await self.frontline_agent.process_voice_input(
                "", {"first_interaction": True, "call_sid": call_sid}
            )
        
        # Extract greeting text
        greeting_text = greeting_response.get("text", "Welcome to Red Bar Sushi. How can I assist you today?")
        
        # Add to conversation store
        await self.conversation_store.add_message(call_sid, "assistant", greeting_text)
        
        return {
            "text": greeting_text,
            "handled": True,
            "agent": "FrontlineVoice",
            "state": fsm.current_state.name,
            "is_greeting": True
        }
    
    async def cleanup_inactive_sessions(self, max_idle_time: int = 3600) -> int:
        """
        Clean up inactive sessions.
        
        Args:
            max_idle_time: Maximum idle time in seconds before cleanup (default: 1 hour)
            
        Returns:
            Number of sessions cleaned up
        """
        current_time = time.time()
        sessions_to_remove = []
        
        # Find inactive sessions
        for call_sid, session in self.active_sessions.items():
            idle_time = current_time - session.get("last_activity", current_time)
            if idle_time > max_idle_time:
                sessions_to_remove.append(call_sid)
        
        # Clean up sessions
        for call_sid in sessions_to_remove:
            # Remove from active sessions
            if call_sid in self.active_sessions:
                del self.active_sessions[call_sid]
            
            # Remove from conversation store
            await self.conversation_store.delete_conversation(call_sid)
            
            # Remove from agents conversation store
            await async_agents_conversation_store.delete_conversation(call_sid)
            
            # Remove from FSM manager
            async_fsm_manager.remove_fsm(call_sid)
            
            logger.info(f"Cleaned up inactive session: {call_sid}")
        
        return len(sessions_to_remove)

# Singleton instance for easy import
async_agent_orchestrator = AsyncAgentOrchestrator()