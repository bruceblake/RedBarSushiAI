"""
Escalation Agent for RedBarSushiAI.
This module provides the escalation agent that handles staff handoff for complex situations.
"""

import os
import json
import logging
import time
from typing import Dict, List, Any, Optional, Union
from openai import tool
from openai.types.agent import Tool
from twilio.twiml.voice_response import VoiceResponse, Dial

from app.agents.base import BaseAgent
from app.utils.conversation_store_sdk import agents_conversation_store

logger = logging.getLogger(__name__)

# Staff phone numbers (would be in environment variables or database in production)
STAFF_PHONE_NUMBER = os.environ.get("STAFF_PHONE_NUMBER", "+15551234567")
MANAGER_PHONE_NUMBER = os.environ.get("MANAGER_PHONE_NUMBER", "+15551234568")

# Timeout configuration for handoffs
DIAL_TIMEOUT = 30  # seconds to ring staff before falling back

class EscalationAgent(BaseAgent):
    """
    Escalation Agent that handles staff handoff when AI cannot resolve an issue.
    Provides seamless transition to human staff when needed.
    """
    
    def __init__(
        self,
        name: str = "Escalation Agent",
        model: str = "gpt-4.1-mini",
        agent_id: Optional[str] = None
    ):
        """Initialize the Escalation Agent."""
        
        instructions = """
        You are an escalation specialist for Red Bar Sushi restaurant's voice ordering system.
        Your primary responsibilities are:
        
        1. Determine when situations require human staff intervention
        2. Handle the handoff process to human staff members
        3. Summarize the conversation history for staff
        4. Provide appropriate context when transferring a call
        5. Handle failures gracefully if staff cannot be reached
        
        ESCALATION PRINCIPLES:
        - Last Resort: Only escalate when AI agents cannot resolve the issue
        - Transparency: Always explain to the customer why they're being transferred
        - Preparation: Provide staff with complete context about the conversation
        - Appropriate Level: Transfer to the right staff member based on issue type
        - Graceful Fallback: If staff can't be reached, collect information for callback
        
        COMMON ESCALATION SCENARIOS:
        - Multiple failed attempts to understand the customer's order
        - Repeated silence or unclear audio
        - Explicitly requested to speak with a human
        - Complex modifications or special requests not in the menu
        - Complaints or dissatisfaction
        - Technical difficulties with order processing
        
        HANDOFF PROCESS:
        1. Inform the customer they'll be transferred to staff
        2. Prepare a brief summary for the staff member
        3. Initiate the call transfer
        4. Monitor for transfer status
        5. Handle fallback if transfer fails
        
        You will be called by other agents when escalation is needed.
        You should use your tools to properly transfer the call and provide context.
        """
        
        # Define the tools this agent can use
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_conversation_summary",
                    "description": "Get a summary of the conversation history",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "call_sid": {
                                "type": "string",
                                "description": "The Twilio call SID"
                            }
                        },
                        "required": ["call_sid"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "transfer_to_staff",
                    "description": "Transfer the call to a staff member",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "call_sid": {
                                "type": "string",
                                "description": "The Twilio call SID"
                            },
                            "staff_type": {
                                "type": "string",
                                "description": "The type of staff to transfer to",
                                "enum": ["general", "manager"]
                            },
                            "reason": {
                                "type": "string",
                                "description": "The reason for the transfer"
                            },
                            "summary": {
                                "type": "string",
                                "description": "Summary to provide to staff"
                            }
                        },
                        "required": ["call_sid", "staff_type", "reason"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "collect_callback_info",
                    "description": "Collect callback information if staff cannot be reached",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "call_sid": {
                                "type": "string",
                                "description": "The Twilio call SID"
                            },
                            "issue_type": {
                                "type": "string",
                                "description": "The type of issue requiring callback",
                                "enum": ["order_problem", "menu_question", "complaint", "other"]
                            },
                            "callback_time": {
                                "type": "string",
                                "description": "Preferred callback time (morning, afternoon, evening)"
                            }
                        },
                        "required": ["call_sid", "issue_type"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_handoff_twiml",
                    "description": "Generate TwiML for transferring the call",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "transfer_to": {
                                "type": "string",
                                "description": "Phone number to transfer to"
                            },
                            "timeout": {
                                "type": "integer",
                                "description": "Timeout in seconds for the dial"
                            },
                            "pre_transfer_message": {
                                "type": "string",
                                "description": "Message to say before transferring"
                            },
                            "fallback_message": {
                                "type": "string",
                                "description": "Message to say if transfer fails"
                            }
                        },
                        "required": ["transfer_to", "pre_transfer_message"]
                    }
                }
            }
        ]
        
        # Initialize the agent
        super().__init__(
            name=name,
            instructions=instructions,
            model=model,
            description="Escalation agent for Red Bar Sushi",
            tools=tools,
            agent_id=agent_id
        )
    
    @tool
    def get_conversation_summary(self, call_sid: str) -> Dict[str, Any]:
        """
        Get a summary of the conversation history.
        
        Args:
            call_sid: The Twilio call SID
            
        Returns:
            Summary of the conversation
        """
        logger.info(f"Getting conversation summary for call {call_sid}")
        
        try:
            # Get the conversation history
            conversation_data = agents_conversation_store.get_conversation(call_sid)
            
            # Get the thread ID
            thread_id = agents_conversation_store.get_thread_id(call_sid)
            
            # In a real implementation, we would get messages from the thread
            # Here's a placeholder that would be replaced with real implementation
            messages = []
            
            # Extract key information
            customer_name = conversation_data.get("customer_name", "unknown customer")
            state = conversation_data.get("state", "unknown")
            total_silences = conversation_data.get("silence_count", 0)
            
            # Get cart data
            cart = agents_conversation_store.get_cart(call_sid)
            has_cart = bool(cart and cart.get("items"))
            total_cart_items = len(cart.get("items", []))
            cart_total = cart.get("total_price", 0) if cart else 0
            formatted_cart_total = f"${cart_total/100:.2f}" if cart_total else "$0.00"
            
            # Create a summary
            summary = f"Call with {customer_name} in {state} phase. "
            
            if has_cart:
                summary += f"Cart contains {total_cart_items} items totaling {formatted_cart_total}. "
            else:
                summary += "No items in cart. "
            
            if total_silences > 0:
                summary += f"Customer has been silent {total_silences} times. "
            
            if messages:
                # In a real implementation, we would summarize the messages
                # This is a placeholder
                summary += "Last few exchanges: [would show conversation summary]. "
            
            return {
                "success": True,
                "call_sid": call_sid,
                "customer_name": customer_name,
                "current_state": state,
                "has_cart": has_cart,
                "cart_items": total_cart_items,
                "cart_total": formatted_cart_total,
                "total_silences": total_silences,
                "summary": summary
            }
            
        except Exception as e:
            logger.error(f"Error getting conversation summary: {str(e)}")
            return {
                "success": False,
                "message": "Error retrieving conversation history",
                "call_sid": call_sid
            }
    
    @tool
    def transfer_to_staff(
        self,
        call_sid: str,
        staff_type: str,
        reason: str,
        summary: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transfer the call to a staff member.
        
        Args:
            call_sid: The Twilio call SID
            staff_type: The type of staff to transfer to (general or manager)
            reason: The reason for the transfer
            summary: Optional summary to provide to staff
            
        Returns:
            Transfer result with TwiML
        """
        logger.info(f"Initiating transfer to {staff_type} staff for call {call_sid}")
        
        # Determine which staff phone number to use
        if staff_type == "manager":
            transfer_to = MANAGER_PHONE_NUMBER
            staff_title = "a manager"
        else:
            transfer_to = STAFF_PHONE_NUMBER
            staff_title = "a staff member"
        
        # Create pre-transfer message
        pre_transfer_message = f"I'll transfer you to {staff_title} who can help you. "
        pre_transfer_message += f"Reason for transfer: {reason}. "
        pre_transfer_message += "Please hold while I connect you."
        
        # Create fallback message
        fallback_message = (
            f"I'm sorry, but {staff_title} is not available at the moment. "
            "Would you like to leave your number for a callback, "
            "or should I take a message for them?"
        )
        
        # Update conversation state
        agents_conversation_store.update_conversation(
            call_sid,
            {
                "state": "escalation",
                "escalation_reason": reason,
                "escalation_type": staff_type,
                "escalation_timestamp": time.time()
            }
        )
        
        # Generate TwiML
        try:
            twiml_result = self.generate_handoff_twiml(
                transfer_to=transfer_to,
                timeout=DIAL_TIMEOUT,
                pre_transfer_message=pre_transfer_message,
                fallback_message=fallback_message
            )
            
            return {
                "success": True,
                "call_sid": call_sid,
                "staff_type": staff_type,
                "transfer_to": transfer_to,
                "reason": reason,
                "twiml": twiml_result.get("twiml")
            }
            
        except Exception as e:
            logger.error(f"Error generating transfer TwiML: {str(e)}")
            return {
                "success": False,
                "message": "Failed to generate transfer instructions",
                "call_sid": call_sid
            }
    
    @tool
    def collect_callback_info(
        self,
        call_sid: str,
        issue_type: str,
        callback_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Collect callback information if staff cannot be reached.
        
        Args:
            call_sid: The Twilio call SID
            issue_type: The type of issue requiring callback
            callback_time: Preferred callback time
            
        Returns:
            Callback information result
        """
        logger.info(f"Collecting callback info for call {call_sid}")
        
        try:
            # Get the conversation data
            conversation_data = agents_conversation_store.get_conversation(call_sid)
            
            # Get key information
            customer_name = conversation_data.get("customer_name", "unknown")
            phone_number = conversation_data.get("customer_phone")
            
            if not phone_number:
                # Use the From parameter from the call
                # In a real implementation, this would be available in the conversation data
                phone_number = "Unknown - check Twilio logs"
            
            # Update the conversation with callback info
            agents_conversation_store.update_conversation(
                call_sid,
                {
                    "state": "callback_requested",
                    "callback_issue": issue_type,
                    "callback_time": callback_time,
                    "callback_requested_at": time.time()
                }
            )
            
            # In a real implementation, this would create a task or notification
            # For now, just log the callback request
            logger.info(
                f"Callback requested - Name: {customer_name}, "
                f"Phone: {phone_number}, Issue: {issue_type}, "
                f"Time: {callback_time or 'Any time'}"
            )
            
            return {
                "success": True,
                "call_sid": call_sid,
                "customer_name": customer_name,
                "phone_number": phone_number,
                "issue_type": issue_type,
                "callback_time": callback_time,
                "message": "Callback information collected"
            }
            
        except Exception as e:
            logger.error(f"Error collecting callback info: {str(e)}")
            return {
                "success": False,
                "message": "Failed to collect callback information",
                "call_sid": call_sid
            }
    
    @tool
    def generate_handoff_twiml(
        self,
        transfer_to: str,
        pre_transfer_message: str,
        timeout: int = DIAL_TIMEOUT,
        fallback_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate TwiML for transferring the call.
        
        Args:
            transfer_to: Phone number to transfer to
            timeout: Timeout in seconds for the dial
            pre_transfer_message: Message to say before transferring
            fallback_message: Message to say if transfer fails
            
        Returns:
            Generated TwiML
        """
        logger.info(f"Generating handoff TwiML to {transfer_to}")
        
        try:
            # Create a new TwiML response
            response = VoiceResponse()
            
            # Add the pre-transfer message
            response.say(pre_transfer_message, voice="Polly.Amy-Neural")
            
            # Add a pause before dialing
            response.pause(length=1)
            
            # Create the Dial verb
            dial = Dial(
                timeout=timeout,
                action="/voice_sdk/escalation/handle_dial_status",
                method="POST"
            )
            
            # Add the transfer number to the Dial verb
            dial.number(transfer_to)
            
            # Add the Dial to the response
            response.append(dial)
            
            # If fallback message is provided, add it to the response
            # This will only execute if the dial fails and no action URL is provided
            if fallback_message:
                response.say(fallback_message, voice="Polly.Amy-Neural")
                
                # Add a gather to get the user's preference for callback
                gather = response.gather(
                    input="speech",
                    action="/voice_sdk/escalation/handle_callback_request",
                    method="POST",
                    timeout=5,
                    speech_timeout="auto",
                    enhanced=True,
                    language="en-US"
                )
                gather.say(
                    "Would you like us to call you back? Please say yes or no.",
                    voice="Polly.Amy-Neural"
                )
            
            # Convert the TwiML to a string
            twiml_str = str(response)
            
            return {
                "success": True,
                "twiml": twiml_str,
                "transfer_to": transfer_to,
                "timeout": timeout
            }
            
        except Exception as e:
            logger.error(f"Error generating handoff TwiML: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to generate handoff TwiML: {str(e)}"
            }
    
    def handle_escalation_request(self, call_sid: str, reason: str, staff_type: str = "general") -> Dict[str, Any]:
        """
        Handle an escalation request from another agent.
        
        Args:
            call_sid: The Twilio call SID
            reason: The reason for escalation
            staff_type: The type of staff to escalate to
            
        Returns:
            Escalation result
        """
        # Set the current call for context
        self.current_call_sid = call_sid
        
        # Process the escalation with the agent
        start_time = time.time()
        
        try:
            # First, get a conversation summary
            summary_result = self.get_conversation_summary(call_sid)
            
            if not summary_result.get("success", False):
                logger.error(f"Failed to get conversation summary for call {call_sid}")
                return {
                    "success": False,
                    "message": "Failed to get conversation summary",
                    "call_sid": call_sid
                }
            
            # Create a summary for staff
            summary = summary_result.get("summary", "")
            
            # Transfer to staff
            transfer_result = self.transfer_to_staff(
                call_sid=call_sid,
                staff_type=staff_type,
                reason=reason,
                summary=summary
            )
            
            duration = time.time() - start_time
            logger.info(f"Processed escalation request in {duration:.2f}s")
            
            return transfer_result
            
        except Exception as e:
            logger.error(f"Error processing escalation request: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to process escalation: {str(e)}",
                "call_sid": call_sid
            }