"""
HSM-based Confirmation state handlers.

This module contains the HSM handlers for all CONFIRMATION states and substates.
"""

import logging
from typing import Dict, Any, Optional

from app.fsm.hsm_core import HSMStateHandler, HSMEvent, ConversationHSMStates, ConversationHSMEvents
from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)


class ConfirmationSuperStateHandler(HSMStateHandler):
    """Handler for the CONFIRMATION superstate."""
    
    def __init__(self):
        """Initialize the confirmation superstate handler."""
        super().__init__(ConversationHSMStates.CONFIRMATION)
    
    async def on_enter(self, context: Dict[str, Any], event: Optional[HSMEvent] = None) -> None:
        """
        Called when entering the CONFIRMATION superstate.
        
        Args:
            context: The conversation context
            event: The event that triggered entry (if any)
        """
        await super().on_enter(context, event)
        
        # Validate that we have cart to confirm
        if not context.get("cart") or not context["cart"].get("items"):
            logger.warning("Entering CONFIRMATION state without valid cart")
            context["confirmation_error"] = "No items to confirm"
        else:
            logger.info(f"Entering CONFIRMATION with {len(context['cart']['items'])} items")
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """
        Handle events at the CONFIRMATION superstate level.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state name if a transition should occur, None otherwise
        """
        # Global events that work from any confirmation substate
        if event.name == ConversationHSMEvents.CONFIRM_ORDER:
            # Transition to FULFILLMENT
            logger.info("Order confirmed, transitioning to FULFILLMENT")
            return ConversationHSMStates.FULFILLMENT
        
        elif event.name == ConversationHSMEvents.REJECT_ORDER:
            # Go back to ORDERING to modify the order
            logger.info("Order rejected, returning to ORDERING")
            return ConversationHSMStates.ORDERING
        
        elif event.name == ConversationHSMEvents.MODIFY_ORDER:
            # Go back to ORDERING to modify
            logger.info("Order modification requested, returning to ORDERING")
            return ConversationHSMStates.ORDERING
        
        elif event.name == ConversationHSMEvents.REQUEST_ESCALATION:
            # Transition to ESCALATION
            logger.info("Escalation requested during confirmation")
            return ConversationHSMStates.ESCALATION
        
        # Not handled at this level, will bubble down to substates
        return None


class ConfirmationReviewHandler(HSMStateHandler):
    """Handler for CONFIRMATION.REVIEW substate."""
    
    def __init__(self):
        """Initialize the confirmation review handler."""
        super().__init__(ConversationHSMStates.CONFIRMATION_REVIEW)
    
    async def on_enter(self, context: Dict[str, Any], event: Optional[HSMEvent] = None) -> None:
        """
        Called when entering the CONFIRMATION_REVIEW state.
        
        Args:
            context: The conversation context
            event: The event that triggered entry (if any)
        """
        await super().on_enter(context, event)
        
        # Generate a confirmation message if there's a frontline agent
        if context.get("frontline_agent") and context.get("cart"):
            try:
                agent = context["frontline_agent"]
                cart = context["cart"]
                confirmation = await agent._generate_confirmation_prompt(cart)
                
                # Store the confirmation message in the context
                context["confirmation_message"] = confirmation
                logger.info("Generated order confirmation message")
            except Exception as e:
                logger.error(f"Error generating confirmation message: {e}")
        else:
            logger.warning("Missing frontline agent or cart for confirmation")
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """
        Handle events in the CONFIRMATION_REVIEW state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state name if a transition should occur, None otherwise
        """
        if event.name == ConversationHSMEvents.MODIFY_ORDER:
            # Transition to modify substate
            logger.info("Moving to order modification")
            return ConversationHSMStates.CONFIRMATION_MODIFY
        
        elif event.name == ConversationHSMEvents.PROVIDE_DELIVERY_INFO:
            # Transition to delivery info
            logger.info("Moving to delivery information")
            return ConversationHSMStates.CONFIRMATION_DELIVERY
        
        # Payment-related events
        elif event.name in [ConversationHSMEvents.CONFIRM_ORDER]:  # Assuming payment confirmation triggers order confirmation
            logger.info("Moving to payment processing")
            return ConversationHSMStates.CONFIRMATION_PAYMENT
        
        return None


class ConfirmationModifyHandler(HSMStateHandler):
    """Handler for CONFIRMATION.MODIFY substate."""
    
    def __init__(self):
        """Initialize the confirmation modify handler."""
        super().__init__(ConversationHSMStates.CONFIRMATION_MODIFY)
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """
        Handle events in the CONFIRMATION_MODIFY state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state name if a transition should occur, None otherwise
        """
        if event.name == ConversationHSMEvents.MODIFY_ITEM:
            # Continue with modifications, stay in this state
            logger.info("Processing item modification")
            return None
        
        elif event.name == ConversationHSMEvents.COMPLETE_ORDER:
            # Done with modifications, back to review
            logger.info("Modifications complete, returning to review")
            return ConversationHSMStates.CONFIRMATION_REVIEW
        
        return None


class ConfirmationPaymentHandler(HSMStateHandler):
    """Handler for CONFIRMATION.PAYMENT substate."""
    
    def __init__(self):
        """Initialize the confirmation payment handler."""
        super().__init__(ConversationHSMStates.CONFIRMATION_PAYMENT)
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """
        Handle events in the CONFIRMATION_PAYMENT state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state name if a transition should occur, None otherwise
        """
        # Payment processing would happen here
        # For now, assume payment is immediate and successful
        logger.info("Processing payment information")
        return None


class ConfirmationDeliveryHandler(HSMStateHandler):
    """Handler for CONFIRMATION.DELIVERY substate."""
    
    def __init__(self):
        """Initialize the confirmation delivery handler."""
        super().__init__(ConversationHSMStates.CONFIRMATION_DELIVERY)
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """
        Handle events in the CONFIRMATION_DELIVERY state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state name if a transition should occur, None otherwise
        """
        if event.name == ConversationHSMEvents.PROVIDE_DELIVERY_INFO:
            # Delivery info provided, return to review
            logger.info("Delivery info provided, returning to review")
            return ConversationHSMStates.CONFIRMATION_REVIEW
        
        elif event.name == ConversationHSMEvents.CHOOSE_PICKUP:
            # User chose pickup instead, return to review
            logger.info("Pickup chosen, returning to review")
            return ConversationHSMStates.CONFIRMATION_REVIEW
        
        return None