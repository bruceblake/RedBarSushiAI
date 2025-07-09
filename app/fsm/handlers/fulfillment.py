"""
HSM-based Fulfillment state handlers.

This module contains the HSM handlers for all FULFILLMENT states and substates.
"""

import logging
from typing import Dict, Any, Optional

from app.fsm.core import HSMStateHandler, HSMEvent, ConversationHSMStates, ConversationHSMEvents
from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)


class FulfillmentSuperStateHandler(HSMStateHandler):
    """Handler for the FULFILLMENT superstate."""
    
    def __init__(self):
        """Initialize the fulfillment superstate handler."""
        super().__init__(ConversationHSMStates.FULFILLMENT)
    
    async def on_enter(self, context: Dict[str, Any], event: Optional[HSMEvent] = None) -> None:
        """
        Called when entering the FULFILLMENT superstate.
        
        Args:
            context: The conversation context
            event: The event that triggered entry (if any)
        """
        await super().on_enter(context, event)
        
        # Initialize fulfillment context
        if "fulfillment" not in context:
            import time
            context["fulfillment"] = {
                "order_submitted_at": time.time(),
                "status": "processing",
                "estimated_time": 20,  # minutes
                "tracking_id": None
            }
            logger.info("Initialized fulfillment context")
        
        # Log order submission
        cart = context.get("cart", {})
        items_count = len(cart.get("items", []))
        total_price = cart.get("total_price", 0)
        logger.info(f"Starting fulfillment for order: {items_count} items, ${total_price}")
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """
        Handle events at the FULFILLMENT superstate level.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state name if a transition should occur, None otherwise
        """
        # Global events that work from any fulfillment substate
        if event.name == ConversationHSMEvents.COMPLETE_INTERACTION:
            # Order is complete, move to completion
            logger.info("Order fulfillment complete, transitioning to COMPLETION")
            return ConversationHSMStates.COMPLETION
        
        elif event.name == ConversationHSMEvents.REQUEST_ESCALATION:
            # Issue with fulfillment, escalate
            logger.info("Fulfillment issue escalated")
            return ConversationHSMStates.ESCALATION
        
        elif event.name == ConversationHSMEvents.ERROR_OCCURRED:
            # Error during fulfillment
            logger.warning("Error occurred during fulfillment")
            return ConversationHSMStates.ERROR_RECOVERY
        
        # Not handled at this level, will bubble down to substates
        return None


class FulfillmentProcessingHandler(HSMStateHandler):
    """Handler for FULFILLMENT.PROCESSING substate."""
    
    def __init__(self):
        """Initialize the fulfillment processing handler."""
        super().__init__(ConversationHSMStates.FULFILLMENT_PROCESSING)
    
    async def on_enter(self, context: Dict[str, Any], event: Optional[HSMEvent] = None) -> None:
        """
        Called when entering the FULFILLMENT_PROCESSING state.
        
        Args:
            context: The conversation context
            event: The event that triggered entry (if any)
        """
        await super().on_enter(context, event)
        
        # Submit order to POS system if fulfillment agent is available
        if context.get("fulfillment_agent") and context.get("cart"):
            try:
                agent = context["fulfillment_agent"]
                cart = context["cart"]
                
                # Process the order submission
                processing_result = await agent.process_order_submission(cart)
                
                # Store the result in context
                context["fulfillment"]["processing_result"] = processing_result
                context["fulfillment"]["status"] = "submitted"
                
                if processing_result.get("tracking_id"):
                    context["fulfillment"]["tracking_id"] = processing_result["tracking_id"]
                
                logger.info(f"Order submitted to POS system: {processing_result}")
            except Exception as e:
                logger.error(f"Error submitting order to POS: {e}")
                context["fulfillment"]["status"] = "error"
                context["fulfillment"]["error"] = str(e)
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """
        Handle events in the FULFILLMENT_PROCESSING state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state name if a transition should occur, None otherwise
        """
        if event.name == ConversationHSMEvents.FULFILL_ORDER:
            # Order has been submitted successfully, move to tracking
            logger.info("Order submitted, moving to tracking")
            return ConversationHSMStates.FULFILLMENT_TRACKING
        
        elif event.name == ConversationHSMEvents.ERROR_OCCURRED:
            # Error during processing
            logger.error("Error during order processing")
            return ConversationHSMStates.ERROR_RECOVERY
        
        return None


class FulfillmentTrackingHandler(HSMStateHandler):
    """Handler for FULFILLMENT.TRACKING substate."""
    
    def __init__(self):
        """Initialize the fulfillment tracking handler."""
        super().__init__(ConversationHSMStates.FULFILLMENT_TRACKING)
    
    async def on_enter(self, context: Dict[str, Any], event: Optional[HSMEvent] = None) -> None:
        """
        Called when entering the FULFILLMENT_TRACKING state.
        
        Args:
            context: The conversation context
            event: The event that triggered entry (if any)
        """
        await super().on_enter(context, event)
        
        # Provide tracking information to customer
        fulfillment = context.get("fulfillment", {})
        tracking_id = fulfillment.get("tracking_id")
        estimated_time = fulfillment.get("estimated_time", 20)
        
        if tracking_id:
            logger.info(f"Order tracking: ID {tracking_id}, ETA {estimated_time} minutes")
        else:
            logger.warning("No tracking ID available for order")
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """
        Handle events in the FULFILLMENT_TRACKING state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state name if a transition should occur, None otherwise
        """
        if event.name == ConversationHSMEvents.REQUEST_FOLLOW_UP:
            # Customer asking for updates, stay in tracking
            logger.info("Customer requesting order update")
            return None
        
        elif event.name == ConversationHSMEvents.FULFILL_ORDER:
            # Order is ready for delivery/pickup
            logger.info("Order ready, moving to delivery")
            return ConversationHSMStates.FULFILLMENT_DELIVERY
        
        return None


class FulfillmentDeliveryHandler(HSMStateHandler):
    """Handler for FULFILLMENT.DELIVERY substate."""
    
    def __init__(self):
        """Initialize the fulfillment delivery handler."""
        super().__init__(ConversationHSMStates.FULFILLMENT_DELIVERY)
    
    async def on_enter(self, context: Dict[str, Any], event: Optional[HSMEvent] = None) -> None:
        """
        Called when entering the FULFILLMENT_DELIVERY state.
        
        Args:
            context: The conversation context
            event: The event that triggered entry (if any)
        """
        await super().on_enter(context, event)
        
        # Update fulfillment status
        if "fulfillment" in context:
            context["fulfillment"]["status"] = "ready_for_delivery"
            logger.info("Order ready for delivery/pickup")
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """
        Handle events in the FULFILLMENT_DELIVERY state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state name if a transition should occur, None otherwise
        """
        if event.name == ConversationHSMEvents.PROVIDE_DELIVERY_INFO:
            # Delivery information provided/updated
            logger.info("Delivery information provided")
            return None
        
        elif event.name == ConversationHSMEvents.CHOOSE_PICKUP:
            # Customer choosing pickup
            logger.info("Customer chose pickup option")
            context["fulfillment"]["delivery_method"] = "pickup"
            return None
        
        elif event.name == ConversationHSMEvents.COMPLETE_INTERACTION:
            # Delivery/pickup complete
            logger.info("Order delivery/pickup complete")
            return ConversationHSMStates.COMPLETION
        
        return None