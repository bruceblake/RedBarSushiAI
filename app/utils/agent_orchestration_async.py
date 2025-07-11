"""
Async Agent Orchestration for RedBarSushiAI.
This module provides tools for orchestrating async agent interactions and handling session state.
"""

import asyncio
import logging
import json
import time
from decimal import Decimal
from typing import Dict, List, Any, Optional, Union, Callable, Tuple, AsyncGenerator

from app.agents.factory_async import async_agent_factory
from app.utils.conversation_store_async import async_conversation_store
from app.utils.conversation_store_async import async_agents_conversation_store
from app.fsm.manager import hsm_manager
from app.fsm.core import (
    ConversationHSMStates, ConversationHSMEvents, HSMEvent
)
from app.config import settings
from app.utils.global_commands import (
    GlobalCommand, global_command_detector, global_command_context
)
from app.utils.intent_detector_async import intent_detector
from app.utils.json_utils import safe_json_dumps

# Set up logging
from app.utils.enhanced_logging import get_logger
from app.utils.correlation_id import set_correlation_id, get_correlation_id

logger = get_logger(__name__)

# safe_json_dumps moved to app.utils.json_utils to avoid circular imports

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
    
    async def initialize(self, db=None):
        """Initialize the orchestrator and its agents.
        
        Args:
            db: Optional database session to pass to agents that need it
        """
        logger.info(f"Initializing orchestrator with database session: {db is not None}")
        # Create the complete voice agent system and get specialist agents
        self.frontline_agent = await async_agent_factory.create_voice_agent_system(db=db)
        self.menu_agent = await async_agent_factory.get_agent("menu", db=db)
        self.cart_agent = await async_agent_factory.get_agent("cart", db=db)
        self.guardrail_agent = await async_agent_factory.get_agent("guardrail")
        self.fulfillment_agent = await async_agent_factory.get_agent("fulfillment")
        self.escalation_agent = await async_agent_factory.get_agent("escalation")
        
        logger.info("Initialized async agent orchestrator with voice agent system")
    
    async def initialize_hsm(self, call_sid: str, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize HSM for a session.
        
        Args:
            call_sid: The Twilio call SID for this session
            context: Optional initial context
        """
        # Initialize conversation HSM
        await hsm_manager.initialize_conversation(call_sid, ConversationHSMStates.INITIAL)
        
        logger.info(f"[{call_sid}] HSM initialized")
    
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
        logger.critical("★" * 80)
        logger.critical("ORCHESTRATOR: process_voice_input called")
        logger.critical(f"Call SID: {call_sid}")
        logger.critical(f"Input Text: '{input_text}'")
        logger.critical(f"Context: {json.dumps(context, indent=2)}")
        logger.critical("★" * 80)
        
        if not self.frontline_agent:
            # Get a database session for initialization
            from app.db_async import get_db
            async for db in get_db():
                await self.initialize(db=db)
                break
        
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
                "state": ConversationHSMStates.INITIAL
            }
            # Initialize HSM for new session
            await self.initialize_hsm(call_sid, context)
        
        # Update last activity time
        self.active_sessions[call_sid]["last_activity"] = time.time()
        
        # Add the user message to conversation store
        logger.info(f"Adding user message to conversation store: '{input_text}'")
        await self.conversation_store.add_message(call_sid, "user", input_text)
        
        # Get current HSM state for this call
        logger.critical(f"Getting HSM state for call: {call_sid}")
        current_states = await hsm_manager.get_current_states(call_sid)
        current_leaf = current_states[-1] if current_states else ConversationHSMStates.INITIAL
        logger.critical(f"HSM retrieved - Current states: {current_states}")
        logger.critical(f"Current leaf state: {current_leaf}")
        
        # If this is first interaction and HSM is in INITIAL state, trigger START_CONVERSATION
        if context.get("first_interaction") and current_leaf == ConversationHSMStates.INITIAL:
            logger.critical("First interaction detected - triggering START_CONVERSATION event")
            start_event = HSMEvent(ConversationHSMEvents.START_CONVERSATION, context)
            await hsm_manager.handle_event(call_sid, start_event, context)
            current_states = await hsm_manager.get_current_states(call_sid)
            current_leaf = current_states[-1] if current_states else ConversationHSMStates.INITIAL
            logger.critical(f"HSM state after START_CONVERSATION: {current_states}")
        
        # Check for global commands first (but not on first interaction)
        if not context.get("first_interaction") and input_text.strip():
            global_cmd, confidence = await intent_detector.detect_global_command(input_text)
            if global_cmd != GlobalCommand.NONE and confidence >= 0.8:
                logger.info(
                    f"Global command detected: {global_cmd.value} (confidence: {confidence})"
                )
                
                # Handle special global commands that don't map to events
                if global_cmd in [GlobalCommand.REPEAT, GlobalCommand.START_OVER, GlobalCommand.GO_BACK]:
                    response = await self._handle_global_command(global_cmd, call_sid, context)
                    if response:
                        # Add response to conversation store
                        await self.conversation_store.add_message(call_sid, "assistant", response["text"])
                        
                        # Update global command context
                        global_command_context.update_last_response(response["text"], time.time())
                        
                        return response
        
        # Process the transcript with the HSM
        start_time = time.time()
        
        # Store the state BEFORE HSM processing
        state_before_hsm = current_leaf
        logger.critical(f"State BEFORE HSM processing: {state_before_hsm}")
        
        # Add the transcript to context
        logger.critical(f"Adding transcript to context: '{input_text}'")
        context["transcript"] = input_text
        
        # Process with HSM using intent detection
        logger.critical(f"Processing transcript with HSM...")
        try:
            # Use intent detection to determine appropriate event
            event = await self._detect_hsm_event(input_text, current_leaf, context)
            if event:
                logger.critical(f"Detected HSM event: {event.name}")
                new_leaf = await hsm_manager.handle_event(call_sid, event, context)
                if new_leaf:
                    current_leaf = new_leaf
                    logger.critical(f"HSM processing complete - New leaf state: {current_leaf}")
                else:
                    logger.critical(f"HSM event processed but no state change")
            else:
                logger.critical(f"No HSM event detected from transcript")
        except Exception as e:
            logger.error(f"HSM processing error: {str(e)}", exc_info=True)
            # Transition to ERROR state
            error_event = HSMEvent(ConversationHSMEvents.ERROR_OCCURRED, {"error": str(e)})
            await hsm_manager.handle_event(call_sid, error_event, context)
        
        logger.critical(f"State changed: {state_before_hsm} -> {current_leaf}")
        
        # Select the appropriate agent based on HSM state
        logger.critical(f"Selecting appropriate agent for state: {current_leaf}")
        try:
            agent, response = await self._process_with_appropriate_agent(current_leaf, input_text, context)
        except Exception as e:
            logger.error(f"Agent processing error: {str(e)}", exc_info=True)
            # Transition to ERROR state
            error_event = HSMEvent(ConversationHSMEvents.ERROR_OCCURRED, {"error": str(e)})
            await hsm_manager.handle_event(call_sid, error_event, context)
            
            # Use AI to generate error response instead of hardcoded message
            try:
                from app.agents.ai_mixin import AIIntelligenceMixin
                ai_mixin = AIIntelligenceMixin()
                
                error_context = {
                    "error_type": "agent_processing_error",
                    "original_error": str(e),
                    "call_sid": call_sid,
                    "input_text": input_text
                }
                
                error_response = await ai_mixin.process_with_ai(
                    "Generate customer-friendly error recovery message for agent processing failure",
                    error_context
                )
                
                return {
                    "text": error_response.get("text", "Processing error occurred"),
                    "handled": True,
                    "agent": "ErrorHandler",
                    "error": str(e),
                    "state": ConversationHSMStates.ERROR_RECOVERY,
                    "ai_generated": True
                }
            except Exception as ai_error:
                logger.error(f"AI error response generation failed: {ai_error}")
                # If AI fails, we must raise the original exception
                raise e
        logger.critical(f"Agent processing complete:")
        logger.critical(f"  - Agent used: {agent.__class__.__name__}")
        logger.critical(f"  - Response text: '{response.get('text', '')}'")
        logger.critical(f"  - Full response: {safe_json_dumps(response, indent=2)}")
        
        duration = time.time() - start_time
        
        # Extract information from response
        response_text = response.get("text", "")
        handled = response.get("handled", True)
        agent_name = response.get("agent", agent.__class__.__name__)
        actions = response.get("actions", [])
        
        # Check for actions that should trigger HSM transitions
        for action in actions:
            if action.get("type") == "TRANSFER_CALL":
                # This is where you would generate the TwiML for call transfer.
                # The final response returned to the voice processing layer
                # should contain the appropriate TwiML <Dial> verb.
                # This example assumes you have a function to generate this.
                response["twiML"] = self._generate_transfer_twiml(getattr(settings, 'HUMAN_HANDOFF_NUMBER', None))
                # Mark that the call should end from the AI's perspective
                response["end_call"] = True
                logger.info(f"Call transfer initiated for {call_sid}")
            elif action.get("type") == "set_customer_name":
                # Agent detected customer name - trigger HSM transition
                customer_name = action.get("name")
                logger.critical(f"Agent detected customer name: {customer_name}")
                
                # CRITICAL FIX: Save customer name to conversation store
                try:
                    await self.conversation_store.update_conversation(
                        call_sid, 
                        {"context": {"customer_name": customer_name}}
                    )
                    logger.critical(f"✅ Customer name '{customer_name}' saved to conversation store")
                except Exception as e:
                    logger.error(f"❌ Failed to save customer name to conversation store: {e}")
                
                if current_leaf == ConversationHSMStates.GREETING:
                    name_event = HSMEvent(ConversationHSMEvents.USER_PROVIDES_NAME, {"name": customer_name})
                    new_leaf = await hsm_manager.handle_event(call_sid, name_event, context)
                    if new_leaf:
                        current_leaf = new_leaf
                        logger.critical(f"HSM transitioned to {current_leaf} after customer name detection")
        
        # Customer name persistence is now handled above when set_customer_name action is detected
        
        # Update session state to match HSM state
        self.active_sessions[call_sid]["state"] = current_leaf
        
        # Update global command context with the last response
        if response_text:
            global_command_context.update_last_response(response_text, time.time())
        
        # Log processing stats
        logger.critical(f"ORCHESTRATOR PROCESSING COMPLETE:")
        logger.critical(f"  - Duration: {duration:.2f}s")
        logger.critical(f"  - HSM State: {current_leaf}")
        logger.critical(f"  - Agent: {agent_name}")
        logger.critical(f"  - Input: '{input_text}'")
        logger.critical(f"  - Response Text: '{response_text}'")
        logger.critical(f"  - Actions: {actions}")
        logger.critical(f"  - State transitions: {state_before_hsm} -> {current_leaf}")
        
        return {
            "text": response_text,
            "handled": handled,
            "agent": agent_name,
            "processing_time": duration,
            "actions": actions,
            "state": current_leaf,
            "hsm_context": {k: v for k, v in context.items() if isinstance(v, (str, int, float, bool, list, dict)) or v is None}
        }
    
    async def _process_with_appropriate_agent(
        self, 
        current_state: str, 
        input_text: str, 
        context: Dict[str, Any]
    ) -> Tuple[Any, Dict[str, Any]]:
        """
        Select the appropriate agent based on HSM state. The Frontline agent
        is the primary handler for the main conversation flow and will delegate
        to specialists (Menu, Cart) via tool calls.
        """
        logger.critical("=" * 60)
        logger.critical("AGENT SELECTION LOGIC")
        logger.critical(f"HSM State: {current_state}")
        logger.critical(f"Input text: '{input_text}'")
        logger.critical("=" * 60)
        
        # Clone context to avoid modifying it directly
        agent_context = context.copy()
        
        # Load conversation history from the conversation store
        call_sid = context.get("call_sid")
        if call_sid:
            conversation = await self.conversation_store.get_conversation(call_sid)
            conversation_history = []
            
            # Convert stored messages to conversation history format
            for message in conversation.get("messages", []):
                conversation_history.append({
                    "role": message.get("role", "user"),
                    "content": message.get("content", "")
                })
            
            agent_context["conversation_history"] = conversation_history
            logger.info(f"Loaded {len(conversation_history)} messages from conversation history")
            
            # Also load any stored customer data
            stored_context = conversation.get("context", {})
            if stored_context.get("customer_name") and not agent_context.get("customer_name"):
                agent_context["customer_name"] = stored_context["customer_name"]
                logger.info(f"Loaded customer name from store: {stored_context['customer_name']}")
        
        # Simplified agent selection logic - Frontline agent handles most states
        # Specific agents can be selected for terminal or special states
        if current_state == ConversationHSMStates.ESCALATION:
            # Use escalation agent for escalation
            logger.info(f"Selecting ESCALATION AGENT for ESCALATION state")
            agent = self.escalation_agent
            response = await agent.process_input(input_text, agent_context)
        else:
            # Default to the Frontline agent for all other active states.
            # It is responsible for orchestrating with specialists.
            logger.info(f"Selecting FRONTLINE AGENT (default) for state: {current_state}")
            # Ensure the agent knows the current HSM state
            agent_context["hsm_state"] = current_state
            agent_context["state_transition_occurred"] = True
            agent = self.frontline_agent
            response = await agent.process_voice_input(input_text, agent_context)
        
        # Skip conversation store saving here - agents handle it themselves to avoid duplication
        
        logger.info(f"Agent selection complete: {agent.__class__.__name__}")
        return agent, response
    
    async def _detect_hsm_event(self, input_text: str, current_state: str, context: Dict[str, Any]) -> Optional[HSMEvent]:
        """
        Detect an HSM event from the input text based on current state and context.
        
        Args:
            input_text: The user's input text
            current_state: Current HSM leaf state
            context: Conversation context
            
        Returns:
            HSM event if detected, None otherwise
        """
        try:
            # Use the intent detector which now works directly with HSM
            from app.utils.intent_detector_async import intent_detector
            
            # Detect intent using the HSM-compatible intent detector
            detected_event = await intent_detector.detect_intent(
                transcript=input_text,
                current_state=current_state,
                context=context
            )
            
            return detected_event
            
        except Exception as e:
            logger.error(f"Error detecting HSM event: {e}", exc_info=True)
            return None
    
    async def process_voice_input_streaming(
        self,
        call_sid: str,
        input_text: str,
        stream_callback: Callable[[str, bool], None],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process voice input with streaming support for faster response times.
        
        Args:
            call_sid: The Twilio call SID
            input_text: The text input from voice transcript
            stream_callback: Async callback to send streamed chunks
            context: Optional additional context
            
        Returns:
            Final complete response dict
        """
        logger.critical("🌊 ORCHESTRATOR: process_voice_input_streaming called")
        logger.critical(f"Call SID: {call_sid}")
        logger.critical(f"Input: '{input_text}'")
        
        if not self.frontline_agent:
            from app.db_async import get_db
            async for db in get_db():
                await self.initialize(db=db)
                break
        
        if context is None:
            context = {}
        
        context["call_sid"] = call_sid
        
        # Track session
        if call_sid not in self.active_sessions:
            self.active_sessions[call_sid] = {
                "started_at": time.time(),
                "last_activity": time.time(),
                "state": ConversationHSMStates.INITIAL
            }
            # Initialize HSM for new session
            await self.initialize_hsm(call_sid, context)
        
        self.active_sessions[call_sid]["last_activity"] = time.time()
        
        # Store user message
        await self.conversation_store.add_message(
            call_sid, 
            "user",
            input_text
        )
        
        # Get current HSM state
        current_states = await hsm_manager.get_current_states(call_sid)
        current_leaf = current_states[-1] if current_states else ConversationHSMStates.INITIAL
        
        # Process input through HSM
        try:
            # Detect and handle HSM event
            event = await self._detect_hsm_event(input_text, current_leaf, context)
            if event:
                await hsm_manager.handle_event(call_sid, event, context)
                # Get updated state
                updated_states = await hsm_manager.get_current_states(call_sid)
                updated_leaf = updated_states[-1] if updated_states else current_leaf
                state_transition_occurred = updated_leaf != current_leaf
                current_leaf = updated_leaf
            else:
                state_transition_occurred = False
        except Exception as e:
            logger.error(f"HSM event handling error: {e}")
            state_transition_occurred = False
        
        # Update context
        context.update({
            "hsm_state": current_leaf,
            "state_transition_occurred": state_transition_occurred,
            "customer_name": context.get("customer_name"),
            "order_items": context.get("order_items", [])
        })
        
        # Get appropriate agent
        agent_context = context.copy()
        
        # For now, streaming is only supported by frontline agent in certain states
        if current_leaf in [ConversationHSMStates.GREETING, ConversationHSMStates.MAIN_MENU] and not context.get("first_interaction"):
            logger.critical("Using FRONTLINE AGENT with streaming support")
            response = await self.frontline_agent.process_voice_input(
                input_text, agent_context, stream_callback
            )
        else:
            # Fall back to non-streaming for other states/agents
            logger.critical("Falling back to non-streaming (tools or complex state)")
            try:
                agent, response = await self._process_with_appropriate_agent(current_leaf, input_text, context)
            except Exception as e:
                logger.error(f"Agent processing error: {str(e)}", exc_info=True)
                # Transition to ERROR state
                error_event = HSMEvent(ConversationHSMEvents.ERROR_OCCURRED, {"error": str(e)})
                await hsm_manager.handle_event(call_sid, error_event, context)
                # Return error response
                return {
                    "text": "System error occurred - AI will generate appropriate response",
                    "handled": True,
                    "agent": "ErrorHandler",
                    "error": str(e),
                    "state": ConversationHSMStates.ERROR_RECOVERY
                }
            
            # Send complete response via callback
            if response.get("text"):
                logger.critical(f"Sending non-streaming response via callback: {response['text'][:100]}...")
                await stream_callback(response["text"], True)
            else:
                logger.critical("No text in response to send via stream_callback")
        
        # Store response
        await self.conversation_store.add_message(
            call_sid,
            "assistant",
            response.get("text", "")
        )
        
        # Update HSM context
        for action in response.get("actions", []):
            if action.get("type") == "set_customer_name":
                context["customer_name"] = action.get("name")
        
        response["state"] = current_leaf
        response["hsm_context"] = {k: v for k, v in context.items() 
                                   if isinstance(v, (str, int, float, bool, list, dict)) or v is None}
        
        return response
    
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
            # Get a database session for initialization
            from app.db_async import get_db
            async for db in get_db():
                await self.initialize(db=db)
                break
        
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
        
        # Get HSM state for this call
        current_states = await hsm_manager.get_current_states(call_sid)
        current_leaf = current_states[-1] if current_states else ConversationHSMStates.INITIAL
        
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
        
        # Handle HSM events based on tool results
        if tool_name == "cart_complete_order" and result.get("success", False):
            complete_event = HSMEvent(ConversationHSMEvents.COMPLETE_ORDER, context)
            await hsm_manager.handle_event(call_sid, complete_event, context)
        elif tool_name == "confirm_order" and result.get("confirmed", False):
            confirm_event = HSMEvent(ConversationHSMEvents.CONFIRM_ORDER, context)
            await hsm_manager.handle_event(call_sid, confirm_event, context)
        elif tool_name == "reject_order" and result.get("rejected", False):
            reject_event = HSMEvent(ConversationHSMEvents.REJECT_ORDER, context)
            await hsm_manager.handle_event(call_sid, reject_event, context)
        elif tool_name == "process_order" and result.get("success", False):
            complete_event = HSMEvent(ConversationHSMEvents.COMPLETE_INTERACTION, context)
            await hsm_manager.handle_event(call_sid, complete_event, context)
        elif tool_name == "escalate" and result.get("escalated", False):
            escalate_event = HSMEvent(ConversationHSMEvents.REQUEST_ESCALATION, context)
            await hsm_manager.handle_event(call_sid, escalate_event, context)
        
        # Log tool execution stats
        logger.info(f"Executed tool {tool_name} in {duration:.2f}s for {call_sid}")
        
        return {
            "tool_name": tool_name,
            "result": result,
            "processing_time": duration,
            "hsm_state": current_leaf
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
        
        # Get HSM state if available
        try:
            current_states = await hsm_manager.get_current_states(call_sid)
            hsm_state = current_states[-1] if current_states else ConversationHSMStates.INITIAL
            hsm_context = {"states": current_states}
        except Exception as e:
            logger.error(f"Error getting HSM for {call_sid}: {str(e)}")
            hsm_state = "UNKNOWN"
            hsm_context = {}
        
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
            "hsm_state": hsm_state,
            "started_at": session_info.get("started_at"),
            "last_activity": session_info.get("last_activity"),
            "duration": time.time() - session_info.get("started_at", time.time()),
            "idle_time": time.time() - session_info.get("last_activity", time.time()),
            "conversation": conversation,
            "cart": cart,
            "hsm_context": hsm_context
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
        # Set correlation ID from call_sid
        set_correlation_id(call_sid)
        
        logger.info("★" * 80, call_sid=call_sid)
        logger.info(f"[call_sid] ORCHESTRATOR: start_new_conversation called")
        logger.info(f"[call_sid] Call SID: {call_sid}")
        logger.info(f"[call_sid] Initial context: {json.dumps(context, indent=2)}")
        logger.info(f"[call_sid] Correlation ID: {get_correlation_id()}")
        logger.info("★" * 80, call_sid=call_sid)
        if not self.frontline_agent:
            # Get a database session for initialization
            from app.db_async import get_db
            async for db in get_db():
                await self.initialize(db=db)
                break
        
        # Create a new session
        self.active_sessions[call_sid] = {
            "started_at": time.time(),
            "last_activity": time.time(),
            "state": ConversationHSMStates.INITIAL
        }
        
        # Initialize HSM for new conversation
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
        
        logger.info(f"Starting HSM conversation with context...")
        await self.initialize_hsm(call_sid, context_with_agents)
        
        # Trigger start conversation event
        start_event = HSMEvent(ConversationHSMEvents.START_CONVERSATION, context_with_agents)
        await hsm_manager.handle_event(call_sid, start_event, context_with_agents)
        
        current_states = await hsm_manager.get_current_states(call_sid)
        current_leaf = current_states[-1] if current_states else ConversationHSMStates.INITIAL
        logger.info(f"HSM started - State: {current_leaf}")
        
        # Get greeting from HSM context
        greeting_response = context_with_agents.get("greeting_response", {})
        logger.info(f"Greeting response from HSM: {json.dumps(greeting_response, indent=2)}")
        
        # If no greeting in HSM, generate one with frontline agent
        if not greeting_response:
            logger.info("No greeting in HSM, generating with frontline agent...")
            greeting_response = await self.frontline_agent.process_voice_input(
                "", {"first_interaction": True, "call_sid": call_sid}
            )
            logger.info(f"Frontline agent greeting response: {json.dumps(greeting_response, indent=2)}")
        
        # Extract greeting text
        from app.config import settings
        greeting_text = greeting_response.get("text", f"Welcome to {settings.RESTAURANT_NAME}. How can I assist you today?")
        logger.info(f"Final greeting text: '{greeting_text}'")
        
        # Add to conversation store
        logger.info(f"Adding greeting to conversation store...")
        await self.conversation_store.add_message(call_sid, "assistant", greeting_text)
        
        result = {
            "text": greeting_text,
            "handled": True,
            "agent": "FrontlineVoice",
            "state": current_leaf,
            "is_greeting": True
        }
        logger.info(f"Returning greeting result: {json.dumps(result, indent=2)}")
        return result
    
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
            
            # Remove from HSM manager
            await hsm_manager.state_store.clear_state(call_sid)
            
            logger.info(f"Cleaned up inactive session: {call_sid}")
        
        return len(sessions_to_remove)
    
    async def _handle_global_command(
        self,
        command: GlobalCommand,
        call_sid: str,
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Handle global commands that require special processing.
        
        Args:
            command: The detected global command
            call_sid: The call session ID
            fsm: The FSM instance
            
        Returns:
            Response dict or None
        """
        if command == GlobalCommand.REPEAT:
            # Get the last assistant message from conversation history
            history = await self.conversation_store.get_conversation(call_sid)
            last_assistant_msg = None
            
            # Find the most recent assistant message
            for msg in reversed(history):
                if msg.get("role") == "assistant":
                    last_assistant_msg = msg.get("content")
                    break
            
            if last_assistant_msg:
                logger.info(f"[call_sid] Repeating last message")
                return {
                    "text": last_assistant_msg,
                    "handled": True,
                    "agent": "GlobalCommand",
                    "is_repeat": True
                }
            else:
                return {
                    "text": "I'm sorry, I don't have anything to repeat yet.",
                    "handled": True,
                    "agent": "GlobalCommand"
                }
        
        elif command == GlobalCommand.START_OVER:
            logger.info(f"[call_sid] Starting over conversation")
            
            # Clear conversation history except system messages
            await self.conversation_store.delete_conversation(call_sid)
            
            # Clear global command context
            global_command_context.clear_history()
            
            # Reset FSM to INITIAL state
            fsm.current_state = ConversationState.INITIAL
            fsm.context = {
                "call_sid": call_sid,
                "frontline_agent": self.frontline_agent,
                "menu_agent": self.menu_agent,
                "cart_agent": self.cart_agent,
                "guardrail_agent": self.guardrail_agent,
                "fulfillment_agent": self.fulfillment_agent,
                "escalation_agent": self.escalation_agent
            }
            
            # Trigger start conversation
            await fsm.trigger(ConversationEvent.START_CONVERSATION)
            
            # Get greeting from frontline agent
            greeting_response = await self.frontline_agent.process_voice_input(
                "", {"first_interaction": True, "call_sid": call_sid}
            )
            
            greeting_text = greeting_response.get("text", f"Let's start fresh. {settings.RESTAURANT_NAME} here. How can I help you today?")
            
            return {
                "text": greeting_text,
                "handled": True,
                "agent": "GlobalCommand",
                "is_restart": True
            }
        
        elif command == GlobalCommand.GO_BACK:
            # Check if we have state history
            previous_state_info = fsm.context.get("previous_fsm_state")
            
            if previous_state_info:
                logger.info(
                    f"Going back to previous state: {previous_state_info}",
                    call_sid=call_sid
                )
                
                # Transition back to previous state
                try:
                    previous_state = ConversationState[previous_state_info]
                    fsm.current_state = previous_state
                    
                    # Get appropriate response for the previous state
                    if previous_state == ConversationState.ORDERING:
                        return {
                            "text": "Okay, let's go back to your order. What would you like to add or change?",
                            "handled": True,
                            "agent": "GlobalCommand"
                        }
                    elif previous_state == ConversationState.MAIN_MENU:
                        return {
                            "text": "Sure, let's go back. Would you like to place an order or do you have questions about our menu?",
                            "handled": True,
                            "agent": "GlobalCommand"
                        }
                    else:
                        return {
                            "text": "Okay, let's go back to where we were.",
                            "handled": True,
                            "agent": "GlobalCommand"
                        }
                        
                except Exception as e:
                    logger.error(f"[call_sid] Error going back to previous state: {e}")
            
            # No previous state to go back to
            return {
                "text": "I'm sorry, there's nowhere to go back to right now. How can I help you?",
                "handled": True,
                "agent": "GlobalCommand"
            }
        
        return None
    
    async def handle_interruption(self, call_sid: str):
        """
        Handle user interruption (barge-in) during TTS playback.
        
        This method is called when the user starts speaking while the system
        is still playing TTS audio, indicating they want to interrupt.
        
        Args:
            call_sid: The Twilio call SID for this session
        """
        logger.info(f"Handling interruption for call {call_sid}")
        
        # Update session activity
        if call_sid in self.active_sessions:
            self.active_sessions[call_sid]["last_activity"] = time.time()
            self.active_sessions[call_sid]["interruption_count"] = \
                self.active_sessions[call_sid].get("interruption_count", 0) + 1
        
        # Get HSM and update context
        try:
            await hsm_manager.update_context(call_sid, {
                "user_interrupted": True,
                "last_interruption_time": time.time()
            })
        except Exception as e:
            logger.warning(f"Could not update HSM context for interruption: {e}")
        
        # Signal frontline agent about interruption if available
        if self.frontline_agent and hasattr(self.frontline_agent, "handle_interruption"):
            await self.frontline_agent.handle_interruption(call_sid)
        
        # Log interruption event in conversation history
        await self.conversation_store.add_message(
            call_sid,
            role="system",
            content="[User interrupted TTS playback]"
        )
        
        logger.info(f"Interruption handled for call {call_sid}")

    def _generate_transfer_twiml(self, transfer_number: str) -> str:
        """
        Generate TwiML for call transfer to human support.
        
        Args:
            transfer_number: The phone number to transfer to
            
        Returns:
            TwiML string for call transfer
        """
        if hasattr(settings, 'HUMAN_HANDOFF_NUMBER') and settings.HUMAN_HANDOFF_NUMBER:
            transfer_number = settings.HUMAN_HANDOFF_NUMBER
        else:
            # Fallback to a configured number or default
            transfer_number = transfer_number or "+1234567890"  # Replace with actual number
        
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Connecting you with a team member.</Say>
    <Dial timeout="30" action="/voice/transfer-complete">
        <Number>{transfer_number}</Number>
    </Dial>
    <Say>I'm sorry, but no one is available right now. Please try again later or leave a message.</Say>
</Response>"""
        
        return twiml

# Singleton instance for easy import
async_agent_orchestrator = AsyncAgentOrchestrator()