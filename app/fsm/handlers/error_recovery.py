"""
HSM-based Error Recovery state handlers.

This module contains the HSM handlers for error recovery states.
"""

import logging
import time
from typing import Dict, Any, Optional

from app.fsm.core import HSMStateHandler, HSMEvent, ConversationHSMStates, ConversationHSMEvents
from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)


class ErrorRecoverySuperStateHandler(HSMStateHandler):
    """Handler for the ERROR_RECOVERY superstate."""
    
    def __init__(self):
        """Initialize the error recovery superstate handler."""
        super().__init__(ConversationHSMStates.ERROR_RECOVERY)
    
    async def on_enter(self, context: Dict[str, Any], event: Optional[HSMEvent] = None) -> None:
        """
        Called when entering the ERROR_RECOVERY superstate.
        
        Args:
            context: The conversation context
            event: The event that triggered entry (if any)
        """
        await super().on_enter(context, event)
        
        # Initialize error recovery context
        if "error_recovery" not in context:
            context["error_recovery"] = {
                "error_count": 0,
                "last_error_time": time.time(),
                "recovery_attempts": 0,
                "max_recovery_attempts": 3
            }
        
        # Increment error count
        context["error_recovery"]["error_count"] += 1
        context["error_recovery"]["last_error_time"] = time.time()
        
        # Get error details from event
        error_details = event.data.get("error") if event and event.data else "Unknown error"
        context["error_recovery"]["last_error"] = error_details
        
        logger.error(f"Entering error recovery: {error_details}")
        logger.info(f"Error count: {context['error_recovery']['error_count']}")
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """
        Handle events at the ERROR_RECOVERY superstate level.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state name if a transition should occur, None otherwise
        """
        # Global events that work from any error recovery substate
        if event.name == ConversationHSMEvents.FALLBACK_TO_MAIN_MENU:
            # Give up on current task, return to main menu
            logger.info("Falling back to main menu after error")
            context["error_recovery"]["recovery_attempts"] = 0
            return ConversationHSMStates.MAIN_MENU
        
        elif event.name == ConversationHSMEvents.ESCALATE_DUE_TO_ERROR:
            # Error requires human intervention
            logger.info("Escalating due to unrecoverable error")
            return ConversationHSMStates.ESCALATION
        
        elif event.name == ConversationHSMEvents.REQUEST_ESCALATION:
            # User requests escalation
            logger.info("User requesting escalation during error recovery")
            return ConversationHSMStates.ESCALATION
        
        # Not handled at this level, will bubble down to substates
        return None


class ErrorRetryHandler(HSMStateHandler):
    """Handler for ERROR_RECOVERY.RETRY substate."""
    
    def __init__(self):
        """Initialize the error retry handler."""
        super().__init__(ConversationHSMStates.ERROR_RETRY)
    
    async def on_enter(self, context: Dict[str, Any], event: Optional[HSMEvent] = None) -> None:
        """
        Called when entering the ERROR_RETRY state.
        
        Args:
            context: The conversation context
            event: The event that triggered entry (if any)
        """
        await super().on_enter(context, event)
        
        recovery = context.get("error_recovery", {})
        recovery["recovery_attempts"] += 1
        
        logger.info(f"Attempting error recovery (attempt {recovery['recovery_attempts']})")
        
        # Check if we've exceeded maximum retry attempts
        max_attempts = recovery.get("max_recovery_attempts", 3)
        if recovery["recovery_attempts"] >= max_attempts:
            logger.warning(f"Maximum retry attempts ({max_attempts}) exceeded")
            context["error_recovery"]["should_escalate"] = True
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """
        Handle events in the ERROR_RETRY state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state name if a transition should occur, None otherwise
        """
        recovery = context.get("error_recovery", {})
        
        if event.name == ConversationHSMEvents.RETRY_LAST_ACTION:
            # Attempt to retry the last action
            max_attempts = recovery.get("max_recovery_attempts", 3)
            current_attempts = recovery.get("recovery_attempts", 0)
            
            if current_attempts < max_attempts:
                logger.info("Retrying last action")
                # Reset error state and return to previous state
                # Implementation would depend on what the previous state was
                return ConversationHSMStates.MAIN_MENU  # Safe fallback
            else:
                logger.warning("Too many retry attempts, moving to fallback")
                return ConversationHSMStates.ERROR_FALLBACK
        
        elif recovery.get("should_escalate", False):
            # Automatic escalation due to too many failures
            logger.info("Auto-escalating due to repeated failures")
            return ConversationHSMStates.ERROR_ESCALATION
        
        return None


class ErrorFallbackHandler(HSMStateHandler):
    """Handler for ERROR_RECOVERY.FALLBACK substate."""
    
    def __init__(self):
        """Initialize the error fallback handler."""
        super().__init__(ConversationHSMStates.ERROR_FALLBACK)
    
    async def on_enter(self, context: Dict[str, Any], event: Optional[HSMEvent] = None) -> None:
        """
        Called when entering the ERROR_FALLBACK state.
        
        Args:
            context: The conversation context
            event: The event that triggered entry (if any)
        """
        await super().on_enter(context, event)
        
        logger.info("Using fallback error recovery strategy")
        
        # Generate fallback response if frontline agent available
        if context.get("frontline_agent"):
            try:
                agent = context["frontline_agent"]
                error_msg = await agent._generate_error_recovery_message(context)
                context["error_recovery"]["fallback_message"] = error_msg
                logger.info("Generated fallback error message")
            except Exception as e:
                logger.error(f"Error generating fallback message: {e}")
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """
        Handle events in the ERROR_FALLBACK state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state name if a transition should occur, None otherwise
        """
        if event.name == ConversationHSMEvents.FALLBACK_TO_MAIN_MENU:
            # Return to main menu with clean slate
            logger.info("Fallback complete, returning to main menu")
            # Clear error context
            context.pop("error_recovery", None)
            return ConversationHSMStates.MAIN_MENU
        
        elif event.name == ConversationHSMEvents.START_OVER:
            # User wants to start over
            logger.info("User requested start over from fallback")
            context.pop("error_recovery", None)
            context.pop("cart", None)
            return ConversationHSMStates.MAIN_MENU
        
        return None


class ErrorEscalationHandler(HSMStateHandler):
    """Handler for ERROR_RECOVERY.ESCALATION substate."""
    
    def __init__(self):
        """Initialize the error escalation handler."""
        super().__init__(ConversationHSMStates.ERROR_ESCALATION)
    
    async def on_enter(self, context: Dict[str, Any], event: Optional[HSMEvent] = None) -> None:
        """
        Called when entering the ERROR_ESCALATION state.
        
        Args:
            context: The conversation context
            event: The event that triggered entry (if any)
        """
        await super().on_enter(context, event)
        
        logger.warning("Error escalation triggered")
        
        # Prepare escalation context
        recovery = context.get("error_recovery", {})
        escalation_context = {
            "reason": "technical_error",
            "error_count": recovery.get("error_count", 0),
            "last_error": recovery.get("last_error", "Unknown"),
            "conversation_context": context.get("conversation", {}),
            "cart_context": context.get("cart", {})
        }
        
        context["escalation"] = escalation_context
        
        # Generate escalation message if escalation agent available
        if context.get("escalation_agent"):
            try:
                agent = context["escalation_agent"]
                escalation_msg = await agent.initiate_escalation(escalation_context)
                context["escalation"]["message"] = escalation_msg
                logger.info("Generated escalation message")
            except Exception as e:
                logger.error(f"Error generating escalation message: {e}")
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """
        Handle events in the ERROR_ESCALATION state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state name if a transition should occur, None otherwise
        """
        if event.name == ConversationHSMEvents.REQUEST_ESCALATION:
            # Already in escalation, transition to main escalation state
            logger.info("Moving to main escalation flow")
            return ConversationHSMStates.ESCALATION
        
        return None