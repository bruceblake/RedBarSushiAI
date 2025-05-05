"""
Frontline Voice Agent with Advanced Orchestration for RedBarSushiAI.
This module provides the primary voice interface agent that integrates with the orchestration system
to enable sequential handoffs, background escalation, and state-machine slot filling.
"""

import os
import json
import logging
import time
from typing import Dict, List, Any, Optional, Union
from openai import tool
from openai.types.agent import Tool

from app.agents.base import HandoffCapableAgent
from app.utils.agents_sdk import guardrail
from app.utils.conversation_store import conversation_store
from app.utils.agent_monitoring import (
    log_agent_call, 
    log_tool_call, 
    tool_monitoring, 
    log_voice_call_event,
    trace_call
)
from app.utils.agent_orchestration import (
    AgentGraph,
    SlotStore,
    FSMOrchestrator,
    ModelEscalator,
    initialize_orchestrators
)

logger = logging.getLogger(__name__)

class OrchestratedFrontlineAgent(HandoffCapableAgent):
    """
    Enhanced Frontline Voice Agent that integrates with the agent orchestration system.
    Provides advanced agentic patterns including sequential handoffs, background model
    escalation, and state-machine slot filling.
    """
    
    def __init__(
        self,
        name: str = "Orchestrated Frontline Agent",
        model: str = "gpt-4.1-mini",
        agent_id: Optional[str] = None
    ):
        """Initialize the Orchestrated Frontline Agent."""
        
        instructions = """
        You are the voice of Red Bar Sushi restaurant, answering phone calls from customers.
        Your primary responsibilities are:
        
        1. Provide a friendly, welcoming, and professional greeting
        2. Help customers with menu questions by routing to the Menu Agent
        3. Take customer orders by routing to the Cart Agent
        4. Handle general restaurant questions (hours, location, etc.)
        5. Authenticate customers when needed for orders
        6. Escalate to staff when necessary or when confidence is low
        
        COMMUNICATION STYLE:
        - Be concise but friendly - phone customers don't want long explanations
        - Speak naturally as if you're having a live conversation
        - Use a casual but professional tone
        - Respond to small talk appropriately but briefly
        - Keep responses under 2-3 sentences when possible
        
        IMPORTANT RULES:
        - Never make up information about the menu or restaurant
        - Never invent items that aren't on our menu
        - Use the route_to_menu tool for ALL menu-related questions
        - Use the route_to_order tool for ALL order-taking
        - Use the authenticate_customer tool when a customer needs to be authenticated
        - Use the escalate_to_staff tool if a customer requests a human or has a complaint
        - Use the check_confidence tool whenever you're unsure about a response
        - Use the goodbye tool when the conversation is complete
        
        CALL FLOW:
        1. Greet the customer and ask how you can help them
        2. Authenticate the customer if needed (orders require authentication)
        3. Based on their response, route to the appropriate specialist agent
        4. When the specialist returns control, continue the conversation naturally
        5. Always maintain context between turns
        6. End with a friendly goodbye when appropriate
        
        You will receive customer utterances one at a time and should respond to each.
        """
        
        # Define the tools this agent can use
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "route_to_menu",
                    "description": "Route a menu-related question to the Menu Agent",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "question": {
                                "type": "string",
                                "description": "The customer's menu question"
                            }
                        },
                        "required": ["question"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "route_to_order",
                    "description": "Route an order request to the Cart Agent",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_text": {
                                "type": "string",
                                "description": "The customer's order text"
                            }
                        },
                        "required": ["order_text"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "authenticate_customer",
                    "description": "Authenticate a customer through a series of questions",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "purpose": {
                                "type": "string",
                                "description": "Why authentication is needed (e.g., 'order', 'account')"
                            }
                        },
                        "required": ["purpose"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_restaurant_info",
                    "description": "Get information about the restaurant like hours, location, etc.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "info_type": {
                                "type": "string",
                                "description": "The type of information requested (hours, location, etc.)",
                                "enum": ["hours", "location", "contact", "reservations", "delivery", "general"]
                            }
                        },
                        "required": ["info_type"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_confidence",
                    "description": "Check your confidence level about the current response",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "confidence_level": {
                                "type": "number",
                                "description": "Your confidence level from 0.0 to 1.0",
                                "minimum": 0,
                                "maximum": 1
                            },
                            "explanation": {
                                "type": "string",
                                "description": "Brief explanation of why you have this confidence level"
                            }
                        },
                        "required": ["confidence_level"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "escalate_to_staff",
                    "description": "Escalate the call to a human staff member",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "reason": {
                                "type": "string",
                                "description": "The reason for escalation"
                            },
                            "urgency": {
                                "type": "string",
                                "description": "The urgency level",
                                "enum": ["low", "medium", "high"]
                            }
                        },
                        "required": ["reason"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "goodbye",
                    "description": "End the conversation with a goodbye",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message": {
                                "type": "string",
                                "description": "Optional custom goodbye message"
                            }
                        }
                    }
                }
            }
        ]
        
        # Initialize the agent
        super().__init__(
            name=name,
            instructions=instructions,
            model=model,
            description="Orchestrated frontline voice agent for Red Bar Sushi",
            tools=tools,
            agent_id=agent_id
        )
        
        # Set up the orchestration components
        self.agent_graph, self.slot_store, self.fsm_orchestrator, self.model_escalator = initialize_orchestrators()
        
        # Store conversation state
        self.active_calls = {}
        self.current_agent = {}  # Track current agent for each call
    
    @tool
    @tool_monitoring(agent_name="Orchestrated Frontline Agent", tool_name="route_to_menu")
    def route_to_menu(self, question: str) -> Dict[str, Any]:
        """
        Route a menu-related question to the Menu Agent.
        
        Args:
            question: The customer's menu question
            
        Returns:
            The Menu Agent's response
        """
        # Get the current call SID from context
        call_sid = self._get_current_call_sid()
        if not call_sid:
            logger.error("No call SID found in context")
            return {"answer": "I'm having trouble accessing the menu information. Let me connect you with a team member."}
        
        logger.info(f"Routing menu question to Menu Agent: {question}")
        
        # Update state to indicate menu intent
        self.slot_store.set_slot(call_sid, "last_intent", "menu_inquiry")
        
        # Create a state object for the agent graph
        state = {
            "slots": self.slot_store.get_all_slots(call_sid),
            "tool_results": {
                "intent_classifier": {
                    "intent": "menu_inquiry",
                    "confidence": 0.9
                }
            }
        }
        
        # Check if we should transition to the Menu Agent
        next_agent = self.agent_graph.get_next_agent("Frontline", state)
        if next_agent == "Menu":
            # Update current agent
            self.current_agent[call_sid] = "Menu"
            logger.info(f"Agent transition: Frontline → Menu for call {call_sid}")
        
        # Check if we have a Menu Agent registered
        menu_agent = self.specialist_agents.get("menu")
        if not menu_agent:
            logger.error("Menu Agent not registered")
            return {"answer": "I'm having trouble accessing our menu system right now. Let me help you with something else."}
        
        start_time = time.time()
        try:
            # Call the Menu Agent
            response = menu_agent.process_message(call_sid, question)
            success = True
            
            # Default response if Menu Agent fails
            if not response:
                response = "I'm having trouble accessing our menu details. Could you rephrase your question?"
                success = False
                
            result = {"answer": response}
        except Exception as e:
            logger.error(f"Error routing to Menu Agent: {str(e)}")
            result = {"answer": "I'm having trouble accessing our menu details. Could you rephrase your question?"}
            success = False
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Log the specialist agent call
        log_tool_call(
            agent_name=self.name,
            tool_name="route_to_menu",
            arguments={"question": question},
            result=result,
            duration_ms=duration_ms,
            success=success,
            context={"call_sid": call_sid}
        )
        
        # After Menu Agent completes, transition back to Frontline
        self.current_agent[call_sid] = "Frontline"
        logger.info(f"Agent transition: Menu → Frontline for call {call_sid}")
        
        return result
    
    @tool
    @guardrail(
        on="tool_response",
        check=lambda result, **_: result.get("total_price", 0) <= 30000,
        on_fail="retry",
        max_retries=2,
        message="Order total exceeds maximum allowable amount"
    )
    def route_to_order(self, order_text: str) -> Dict[str, Any]:
        """
        Route an order request to the Cart Agent.
        
        Args:
            order_text: The customer's order text
            
        Returns:
            The Cart Agent's response with order details
        """
        # Get the current call SID from context
        call_sid = self._get_current_call_sid()
        if not call_sid:
            logger.error("No call SID found in context")
            return {
                "status": "error",
                "message": "I'm having trouble with our ordering system. Let me connect you with a team member."
            }
        
        logger.info(f"Routing order to Cart Agent: {order_text}")
        
        # Update state to indicate order intent
        self.slot_store.set_slot(call_sid, "last_intent", "place_order")
        
        # Check if customer is authenticated
        is_authenticated = self.slot_store.get_slot(call_sid, "authenticated")
        if not is_authenticated:
            logger.info(f"Customer not authenticated for order, initiating authentication for call {call_sid}")
            # Use authentication FSM to get customer info
            return {
                "status": "auth_required",
                "message": "Before we place your order, I need to get a few details from you. Let's start with your name."
            }
        
        # Create a state object for the agent graph
        state = {
            "slots": self.slot_store.get_all_slots(call_sid),
            "tool_results": {
                "intent_classifier": {
                    "intent": "place_order",
                    "confidence": 0.9
                }
            }
        }
        
        # Check if we should transition to the Cart Agent
        next_agent = self.agent_graph.get_next_agent("Frontline", state)
        if next_agent == "Cart":
            # Update current agent
            self.current_agent[call_sid] = "Cart"
            logger.info(f"Agent transition: Frontline → Cart for call {call_sid}")
        
        # Check if we have a Cart Agent registered
        cart_agent = self.specialist_agents.get("cart")
        if not cart_agent:
            logger.error("Cart Agent not registered")
            return {
                "status": "error",
                "message": "I'm having trouble with our ordering system right now. Let me help you with something else."
            }
        
        # Process the order with the Cart Agent
        result = cart_agent.process_order_request(call_sid, order_text)
        
        # After Cart Agent completes, transition back to Frontline
        self.current_agent[call_sid] = "Frontline"
        logger.info(f"Agent transition: Cart → Frontline for call {call_sid}")
        
        # If processing succeeded
        if result.get("success"):
            # Get the current cart state
            cart = result.get("cart", {})
            items = cart.get("items", [])
            total_price = cart.get("total_price", 0)
            
            # Format the total price as a string
            total_price_str = f"${total_price/100:.2f}" if isinstance(total_price, (int, float)) else "$0.00"
            
            # Get the agent's response
            response = result.get("response", "I've processed your order.")
            
            return {
                "status": "success",
                "message": response,
                "items": items,
                "total_price": total_price,
                "formatted_total": total_price_str,
                "item_count": len(items)
            }
        else:
            # If processing failed
            return {
                "status": "error",
                "message": "I had trouble processing your order. Could you please repeat that?"
            }
    
    @tool
    def authenticate_customer(self, purpose: str) -> Dict[str, Any]:
        """
        Authenticate a customer through a series of questions.
        Uses the FSM orchestrator for authentication flow.
        
        Args:
            purpose: Why authentication is needed (e.g., 'order', 'account')
            
        Returns:
            Status of the authentication process
        """
        # Get the current call SID from context
        call_sid = self._get_current_call_sid()
        if not call_sid:
            logger.error("No call SID found in context")
            return {
                "status": "error",
                "message": "I'm having trouble with authentication. Let me connect you with a team member."
            }
        
        logger.info(f"Starting authentication for {purpose}, call {call_sid}")
        
        # Update the authentication purpose
        self.slot_store.set_slot(call_sid, "auth_purpose", purpose)
        
        # Check current authentication state
        current_state = self.fsm_orchestrator.get_current_state(call_sid)
        
        # If already authenticated, return success
        if current_state == FSMState.AUTHENTICATED:
            return {
                "status": "success",
                "message": "You're already authenticated.",
                "is_authenticated": True
            }
        
        # If not at the beginning of authentication flow, return current state
        if current_state != FSMState.INITIAL:
            # Set for initial prompt
            prompt_result = self.fsm_orchestrator.process_user_input(call_sid, "")
            
            return {
                "status": "in_progress",
                "message": prompt_result["user_prompt"],
                "state": current_state.value,
                "is_authenticated": False
            }
        
        # Set to initial state and prepare first prompt
        self.fsm_orchestrator.set_current_state(call_sid, FSMState.INITIAL)
        next_prompt = self.fsm_orchestrator.process_user_input(call_sid, "")
        
        return {
            "status": "started",
            "message": next_prompt["user_prompt"],
            "state": FSMState.ASK_NAME.value,
            "is_authenticated": False
        }
    
    @tool
    def get_restaurant_info(self, info_type: str) -> Dict[str, Any]:
        """
        Get information about the restaurant.
        
        Args:
            info_type: The type of information requested
            
        Returns:
            Information about the restaurant
        """
        # Restaurant information
        restaurant_info = {
            "hours": {
                "monday": "11:00 AM - 10:00 PM",
                "tuesday": "11:00 AM - 10:00 PM",
                "wednesday": "11:00 AM - 10:00 PM",
                "thursday": "11:00 AM - 10:00 PM",
                "friday": "11:00 AM - 11:00 PM",
                "saturday": "11:00 AM - 11:00 PM",
                "sunday": "12:00 PM - 9:00 PM"
            },
            "location": {
                "address": "123 Main Street, Anytown, USA",
                "directions": "Located in the Main Street Shopping Center, next to City Park",
                "parking": "Free parking available in the shopping center lot"
            },
            "contact": {
                "phone": "(555) 123-4567",
                "email": "info@redbarsushi.com",
                "website": "https://www.redbarsushi.com"
            },
            "reservations": {
                "policy": "Reservations recommended for parties of 5 or more",
                "methods": "Call us or book online through our website"
            },
            "delivery": {
                "availability": "Available within a 5-mile radius",
                "platforms": "Order through our website or popular delivery apps",
                "minimum": "$20 minimum order for delivery"
            },
            "general": {
                "about": "Red Bar Sushi offers authentic Japanese cuisine with a modern twist. Our expert chefs prepare fresh sushi, sashimi, and cooked dishes daily.",
                "specialties": "Known for our signature Red Bar Roll and fresh daily fish selections",
                "atmosphere": "Modern, casual dining with both indoor and outdoor seating options"
            }
        }
        
        # Get the current call SID for logging
        call_sid = self._get_current_call_sid()
        if call_sid:
            logger.info(f"Providing restaurant info about {info_type} for call {call_sid}")
        
        # Return the requested information
        if info_type in restaurant_info:
            return {
                "info_type": info_type,
                "data": restaurant_info[info_type]
            }
        
        # Default to general information
        return {
            "info_type": "general",
            "data": restaurant_info["general"]
        }
    
    @tool
    def check_confidence(self, confidence_level: float, explanation: str = "") -> Dict[str, Any]:
        """
        Check confidence level and decide if escalation is needed.
        
        Args:
            confidence_level: The confidence level from 0.0 to 1.0
            explanation: Brief explanation of confidence level
            
        Returns:
            Decision about whether to escalate
        """
        # Get the current call SID from context
        call_sid = self._get_current_call_sid()
        if not call_sid:
            logger.error("No call SID found in context")
            return {
                "should_escalate": True,
                "message": "Unable to determine context, recommended escalation."
            }
        
        logger.info(f"Confidence check for call {call_sid}: {confidence_level}")
        
        # Store the confidence level in the state
        self.slot_store.set_slot(call_sid, "last_confidence", confidence_level)
        
        # Get the current agent
        current_agent_name = self.current_agent.get(call_sid, "Frontline")
        
        # Get the current agent's model from the graph
        current_model = self.agent_graph.nodes.get(current_agent_name, {}).get("model", self.model)
        
        # Check if we should escalate based on confidence
        should_escalate = self.model_escalator.should_escalate(
            confidence=confidence_level,
            current_model=current_model,
            is_critical=False,
            threshold=0.7  # Default threshold
        )
        
        if should_escalate:
            # Create a state object for the agent graph
            state = {
                "slots": self.slot_store.get_all_slots(call_sid),
                "last_confidence": confidence_level
            }
            
            # Check if we should transition to Escalation agent
            next_agent = self.agent_graph.get_next_agent(current_agent_name, state)
            if next_agent == "Escalation":
                # Mark for escalation
                self.slot_store.set_slot(call_sid, "needs_escalation", True)
                
                return {
                    "should_escalate": True,
                    "message": "Confidence is low, recommend escalation to a stronger model or human staff.",
                    "confidence_level": confidence_level,
                    "recommended_model": self.model_escalator.get_escalation_model(current_model)
                }
        
        return {
            "should_escalate": False,
            "message": "Confidence is sufficient, no escalation needed.",
            "confidence_level": confidence_level
        }
    
    @tool
    def escalate_to_staff(self, reason: str, urgency: str = "medium") -> Dict[str, Any]:
        """
        Escalate the call to a human staff member.
        
        Args:
            reason: The reason for escalation
            urgency: The urgency level
            
        Returns:
            Status of the escalation
        """
        # Get the current call SID from context
        call_sid = self._get_current_call_sid()
        if not call_sid:
            logger.error("No call SID found in context")
            return {
                "status": "error",
                "message": "I'm having trouble connecting you with a team member."
            }
        
        logger.info(f"Escalating call {call_sid} to staff: {reason} (urgency: {urgency})")
        
        # Update state for escalation
        self.slot_store.set_slot(call_sid, "escalation_reason", reason)
        self.slot_store.set_slot(call_sid, "escalation_urgency", urgency)
        self.slot_store.set_slot(call_sid, "needs_human", True)
        
        # Create a state object for the agent graph
        state = {
            "slots": self.slot_store.get_all_slots(call_sid),
        }
        
        # Check if we should transition to Escalation agent
        current_agent_name = self.current_agent.get(call_sid, "Frontline")
        next_agent = self.agent_graph.get_next_agent(current_agent_name, state)
        
        if next_agent == "Escalation":
            # Update current agent
            self.current_agent[call_sid] = "Escalation"
            logger.info(f"Agent transition: {current_agent_name} → Escalation for call {call_sid}")
            
            # Check if we have an Escalation Agent registered
            escalation_agent = self.specialist_agents.get("escalation")
            if escalation_agent:
                # Call the Escalation Agent to handle the handoff
                try:
                    handoff_result = escalation_agent.handle_escalation(
                        call_sid=call_sid, 
                        reason=reason, 
                        urgency=urgency
                    )
                    
                    # After Escalation Agent completes, transition back to Frontline
                    self.current_agent[call_sid] = "Frontline"
                    
                    return handoff_result
                except Exception as e:
                    logger.error(f"Error in escalation agent: {str(e)}")
        
        # In a real implementation, this would trigger Twilio <Dial> to a staff member
        # For now, just return a success status
        return {
            "status": "success",
            "message": "I'll connect you with a team member right away. Please hold.",
            "estimated_wait": "2-3 minutes"
        }
    
    @tool
    def goodbye(self, message: Optional[str] = None) -> Dict[str, Any]:
        """
        End the conversation with a goodbye.
        
        Args:
            message: Optional custom goodbye message
            
        Returns:
            Status of the goodbye
        """
        # Get the current call SID from context
        call_sid = self._get_current_call_sid()
        if call_sid:
            logger.info(f"Ending call {call_sid} with goodbye")
            
            # Clear all slots for this call
            self.slot_store.clear_slots(call_sid)
            
            # Remove from active calls
            if call_sid in self.active_calls:
                del self.active_calls[call_sid]
            
            # Remove from current_agent tracking
            if call_sid in self.current_agent:
                del self.current_agent[call_sid]
        
        # Use the provided message or a default
        goodbye_message = message or "Thank you for calling Red Bar Sushi. Have a great day!"
        
        return {
            "status": "ended",
            "message": goodbye_message
        }
    
    def _get_current_call_sid(self) -> Optional[str]:
        """
        Get the current call SID from context.
        In a real implementation, this would be passed from the voice controller.
        
        Returns:
            The call SID if available, None otherwise
        """
        # This is a placeholder that will be replaced when implementing the voice controller
        return self.active_calls.get("current_call_sid")
    
    def set_current_call(self, call_sid: str):
        """
        Set the current call SID for context.
        
        Args:
            call_sid: The Twilio call SID
        """
        self.active_calls["current_call_sid"] = call_sid
        
        # Initialize agent tracking if not already set
        if call_sid not in self.current_agent:
            self.current_agent[call_sid] = "Frontline"
    
    @trace_call(call_sid="dynamic")
    def process_voice_input(self, call_sid: str, user_input: str) -> str:
        """
        Process voice input from a caller.
        Integrates with the FSM for authentication and orchestration for agent handoffs.
        
        Args:
            call_sid: The Twilio call SID
            user_input: The user's input text
            
        Returns:
            The agent's response
        """
        start_time = time.time()
        
        # Log the voice call input event
        log_voice_call_event(
            call_sid=call_sid,
            event_type="input",
            details={
                "input_text": user_input,
                "input_length": len(user_input)
            }
        )
        
        # Set the current call for context
        self.set_current_call(call_sid)
        
        # Store the user input in the conversation store
        conversation_store.add_message(call_sid, "user", user_input)
        
        # Check if we're in authentication flow
        current_state = self.fsm_orchestrator.get_current_state(call_sid)
        if current_state not in [FSMState.INITIAL, FSMState.AUTHENTICATED]:
            logger.info(f"Call {call_sid} is in authentication flow, state: {current_state.value}")
            
            # Process the input through the FSM orchestrator
            fsm_result = self.fsm_orchestrator.process_user_input(call_sid, user_input)
            
            # Use the prompt for response
            response = fsm_result["user_prompt"]
            
            # Store the assistant's response in the conversation store
            conversation_store.add_message(call_sid, "assistant", response)
            
            # If authentication is now complete, mark it in state
            if fsm_result["state"] == FSMState.AUTHENTICATED.value:
                self.slot_store.set_slot(call_sid, "authenticated", True)
                
                # After authentication, continue with the original intent
                original_intent = self.slot_store.get_slot(call_sid, "last_intent")
                if original_intent == "place_order":
                    response += " Now, let's continue with your order. What would you like to order?"
                
            success = True
        else:
            # If authenticated or not in authentication flow, process normally
            try:
                # Check if we need to escalate based on previous confidence check
                needs_escalation = self.slot_store.get_slot(call_sid, "needs_escalation")
                
                if needs_escalation:
                    # If escalation is needed, update the model for this request
                    current_agent_name = self.current_agent.get(call_sid, "Frontline")
                    current_model = self.agent_graph.nodes.get(current_agent_name, {}).get("model", self.model)
                    escalation_model = self.model_escalator.get_escalation_model(current_model)
                    
                    logger.info(f"Escalating model from {current_model} to {escalation_model} for call {call_sid}")
                    
                    # Process with escalated model
                    response = self.process_message(call_sid, user_input, model_override=escalation_model)
                    
                    # Clear the escalation flag after handling
                    self.slot_store.set_slot(call_sid, "needs_escalation", False)
                else:
                    # Process normally with current model
                    response = self.process_message(call_sid, user_input)
                
                success = True
                
                # Default response if processing fails
                if not response:
                    response = "I'm sorry, I didn't catch that. Could you please repeat?"
                    success = False
            except Exception as e:
                logger.error(f"Error processing voice input: {str(e)}")
                response = "I'm having trouble understanding. Let me connect you with a team member."
                success = False
        
        # Store the assistant's response in the conversation store
        conversation_store.add_message(call_sid, "assistant", response)
        
        # Calculate processing time
        duration_ms = (time.time() - start_time) * 1000
        
        # Log the agent call with results
        thread_id = getattr(self, "_last_thread_id", "unknown")
        log_agent_call(
            agent_name=self.name,
            call_sid=call_sid,
            thread_id=thread_id,
            message=f"Processed voice input: {user_input[:50]}{'...' if len(user_input) > 50 else ''}",
            duration_ms=duration_ms,
            success=success,
            context={
                "input_length": len(user_input),
                "response_length": len(response)
            }
        )
        
        # Log the voice call output event
        log_voice_call_event(
            call_sid=call_sid,
            event_type="output",
            details={
                "output_text": response,
                "output_length": len(response)
            },
            duration_ms=duration_ms
        )
        
        return response