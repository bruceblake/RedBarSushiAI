"""
HSM-based Ordering state handlers.

Demonstrates hierarchical state handling for the ORDERING superstate
and its substates: BROWSING, MENU_INQUIRY, ITEM_CUSTOMIZATION, CART_REVIEW.
"""

from typing import Dict, Any, Optional

from app.fsm.hsm_core import HSMStateHandler, HSMEvent, ConversationHSMStates
from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)


class OrderingSuperStateHandler(HSMStateHandler):
    """Handler for the ORDERING superstate."""
    
    def __init__(self):
        super().__init__(ConversationHSMStates.ORDERING)
    
    async def on_enter(self, context: Dict[str, Any], event: Optional[HSMEvent] = None) -> None:
        """Initialize ordering context when entering ORDERING."""
        await super().on_enter(context, event)
        
        # Initialize cart if not present
        if "cart" not in context:
            context["cart"] = {
                "items": [],
                "total_price": 0.0,
                "item_count": 0
            }
            logger.info(f"Initialized cart for ordering")
        
        # Track ordering start time
        import time
        context["ordering_started_at"] = time.time()
    
    async def on_exit(self, context: Dict[str, Any], event: Optional[HSMEvent] = None) -> None:
        """Clean up when exiting ORDERING."""
        await super().on_exit(context, event)
        
        # Log ordering duration
        if "ordering_started_at" in context:
            import time
            duration = time.time() - context["ordering_started_at"]
            logger.info(f"Ordering phase lasted {duration:.1f} seconds")
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """
        Handle events at the ORDERING superstate level.
        
        These are events that can be handled regardless of which substate we're in.
        """
        # Global commands that work from any ORDERING substate
        if event.name == "CLEAR_CART":
            context["cart"]["items"] = []
            context["cart"]["total_price"] = 0.0
            context["cart"]["item_count"] = 0
            logger.info("Cart cleared by user request")
            return ConversationHSMStates.ORDERING_BROWSING  # Return to browsing
        
        elif event.name == "VIEW_CART":
            # Transition to cart review from any substate
            return ConversationHSMStates.ORDERING_CART_REVIEW
        
        elif event.name == "CHECKOUT":
            # Ready to move to confirmation
            if context["cart"]["item_count"] > 0:
                return ConversationHSMStates.CONFIRMATION
            else:
                logger.warning("Cannot checkout with empty cart")
                return None
        
        # Not handled at this level, will bubble down to substates
        return None


class OrderingBrowsingHandler(HSMStateHandler):
    """Handler for ORDERING.BROWSING substate."""
    
    def __init__(self):
        super().__init__(ConversationHSMStates.ORDERING_BROWSING)
    
    async def on_enter(self, context: Dict[str, Any], event: Optional[HSMEvent] = None) -> None:
        """User is browsing the menu."""
        await super().on_enter(context, event)
        context["browsing_context"] = {
            "last_viewed_category": None,
            "shown_recommendations": False
        }
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """Handle browsing-specific events."""
        if event.name == "SELECT_ITEM":
            item_name = event.data.get("item_name")
            logger.info(f"User selected item: {item_name}")
            context["current_item"] = item_name
            # Move to customization
            return ConversationHSMStates.ORDERING_ITEM_CUSTOMIZATION
        
        elif event.name == "ASK_ABOUT_ITEM":
            item_name = event.data.get("item_name")
            context["inquiry_item"] = item_name
            # Move to menu inquiry
            return ConversationHSMStates.ORDERING_MENU_INQUIRY
        
        elif event.name == "REQUEST_RECOMMENDATIONS":
            # Stay in browsing but update context
            context["browsing_context"]["shown_recommendations"] = True
            return None  # No transition
        
        return None


class OrderingMenuInquiryHandler(HSMStateHandler):
    """Handler for ORDERING.MENU_INQUIRY substate."""
    
    def __init__(self):
        super().__init__(ConversationHSMStates.ORDERING_MENU_INQUIRY)
    
    async def on_enter(self, context: Dict[str, Any], event: Optional[HSMEvent] = None) -> None:
        """User is asking about menu items."""
        await super().on_enter(context, event)
        context["inquiry_context"] = {
            "questions_asked": 0,
            "current_topic": context.get("inquiry_item", "menu")
        }
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """Handle menu inquiry events."""
        if event.name == "INQUIRY_COMPLETE":
            # Return to browsing
            context.pop("inquiry_context", None)
            return ConversationHSMStates.ORDERING_BROWSING
        
        elif event.name == "SELECT_ITEM_AFTER_INQUIRY":
            item_name = event.data.get("item_name")
            context["current_item"] = item_name
            # Move directly to customization
            return ConversationHSMStates.ORDERING_ITEM_CUSTOMIZATION
        
        elif event.name == "ASK_ANOTHER_QUESTION":
            # Stay in inquiry
            context["inquiry_context"]["questions_asked"] += 1
            return None
        
        return None


class OrderingItemCustomizationHandler(HSMStateHandler):
    """Handler for ORDERING.ITEM_CUSTOMIZATION substate."""
    
    def __init__(self):
        super().__init__(ConversationHSMStates.ORDERING_ITEM_CUSTOMIZATION)
    
    async def on_enter(self, context: Dict[str, Any], event: Optional[HSMEvent] = None) -> None:
        """User is customizing an item."""
        await super().on_enter(context, event)
        context["customization_context"] = {
            "current_item": context.get("current_item"),
            "modifications": [],
            "quantity": 1
        }
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """Handle customization events."""
        if event.name == "ADD_MODIFICATION":
            mod = event.data.get("modification")
            context["customization_context"]["modifications"].append(mod)
            logger.info(f"Added modification: {mod}")
            return None
        
        elif event.name == "SET_QUANTITY":
            qty = event.data.get("quantity", 1)
            context["customization_context"]["quantity"] = qty
            return None
        
        elif event.name == "CONFIRM_ITEM":
            # Add to cart
            item = {
                "name": context["customization_context"]["current_item"],
                "modifications": context["customization_context"]["modifications"],
                "quantity": context["customization_context"]["quantity"]
            }
            context["cart"]["items"].append(item)
            context["cart"]["item_count"] += item["quantity"]
            
            logger.info(f"Added to cart: {item}")
            
            # Return to browsing
            return ConversationHSMStates.ORDERING_BROWSING
        
        elif event.name == "CANCEL_ITEM":
            # Return to browsing without adding
            return ConversationHSMStates.ORDERING_BROWSING
        
        return None


class OrderingCartReviewHandler(HSMStateHandler):
    """Handler for ORDERING.CART_REVIEW substate."""
    
    def __init__(self):
        super().__init__(ConversationHSMStates.ORDERING_CART_REVIEW)
    
    async def on_enter(self, context: Dict[str, Any], event: Optional[HSMEvent] = None) -> None:
        """User is reviewing their cart."""
        await super().on_enter(context, event)
        
        # Calculate totals (mock)
        total = len(context["cart"]["items"]) * 10.0  # Mock pricing
        context["cart"]["total_price"] = total
        
        logger.info(f"Cart review: {context['cart']['item_count']} items, ${total}")
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """Handle cart review events."""
        if event.name == "REMOVE_ITEM":
            item_index = event.data.get("item_index")
            if 0 <= item_index < len(context["cart"]["items"]):
                removed = context["cart"]["items"].pop(item_index)
                context["cart"]["item_count"] -= removed["quantity"]
                logger.info(f"Removed item from cart: {removed['name']}")
            return None
        
        elif event.name == "MODIFY_ITEM":
            item_index = event.data.get("item_index")
            if 0 <= item_index < len(context["cart"]["items"]):
                context["current_item"] = context["cart"]["items"][item_index]["name"]
                context["modifying_index"] = item_index
                return ConversationHSMStates.ORDERING_ITEM_CUSTOMIZATION
        
        elif event.name == "ADD_MORE_ITEMS":
            # Return to browsing
            return ConversationHSMStates.ORDERING_BROWSING
        
        elif event.name == "PROCEED_TO_CHECKOUT":
            # Move to confirmation
            if context["cart"]["item_count"] > 0:
                return ConversationHSMStates.CONFIRMATION
            else:
                logger.warning("Cannot checkout with empty cart")
                return None
        
        return None