"""
Async Fulfillment Agent for processing orders in RedBarSushiAI.

This agent handles the final stages of order processing including submission to Deliverect,
order confirmation, and notification handling.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base_async import BaseAsyncAgent
from app.models.order_async import Order
from app.services.deliverect_service import DeliverectService
from app.tasks.notifications import send_pos_submission_failure_alert
from app.db.crud_order_async import update_order_status

logger = logging.getLogger(__name__)

class AsyncFulfillmentAgent(BaseAsyncAgent):
    """
    Async agent for order fulfillment and submission.
    
    This agent handles:
    - Order submission to Deliverect
    - Order confirmation processing
    - Customer notifications
    - Payment handling (if applicable)
    """
    
    def __init__(self, agent_name: str = "FulfillmentAgent", **kwargs):
        """Initialize the fulfillment agent."""
        super().__init__(agent_name=agent_name, **kwargs)
        logger.info(f"AsyncFulfillmentAgent initialized with name: {self.agent_name}")
        self._db_session = None

    async def initialize(self):
        """Initialize any resources needed by the agent."""
        logger.info(f"AsyncFulfillmentAgent: Initializing resources")

    async def submit_order(
        self, 
        call_sid: str, 
        order_details: Dict[str, Any],
        hsm_context_data: Dict[str, Any],
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        Submit an order to Deliverect and process confirmation.
        
        Args:
            call_sid: The call session ID
            order_details: The validated order details to submit
            hsm_context_data: The full HSM context
            db: Database session
            
        Returns:
            Dict with submission results and next actions
        """
        logger.info(f"[{call_sid}] AsyncFulfillmentAgent: Submitting order: {order_details}")
        
        # Validate order has items
        if not order_details.get("items"):
            # AI must handle empty order scenarios - no hardcoded responses
            raise Exception("Empty order detected - AI intelligence required for handling")
        
        # Get or create order ID
        order_id = order_details.get("id", f"ORD-{call_sid[-8:]}")
        
        try:
            # Create DeliverectService instance
            deliverect_service = DeliverectService()
            
            # If we have an Order object, use it directly
            if isinstance(order_details.get("order_object"), Order) and db:
                order = order_details["order_object"]
            else:
                # Otherwise, we need to create/fetch the order from DB
                # This is a simplified version - in production you'd have proper order creation
                logger.warning("Order object not provided, using simplified submission")
                submission_result = {
                    "success": False,
                    "error": "Order object required for submission",
                    "needs_manual_intervention": True
                }
            
            # Submit to Deliverect
            if db and hasattr(locals(), 'order'):
                submission_result = await deliverect_service.submit_order(order, db)
            else:
                submission_result = {
                    "success": False,
                    "error": "Database session required for order submission",
                    "needs_manual_intervention": True
                }
            
            # Handle submission result
            if submission_result.get("success"):
                deliverect_id = submission_result.get("deliverect_order_id", "")
                estimated_time = order_details.get("estimated_time", 20)
                
                # Use AI to generate success response
                from app.agents.ai_mixin import AIIntelligenceMixin
                ai_mixin = AIIntelligenceMixin()
                
                success_context = {
                    "order_id": order_id,
                    "estimated_time": estimated_time,
                    "deliverect_id": deliverect_id,
                    "restaurant_name": getattr(settings, 'RESTAURANT_NAME', 'our restaurant')
                }
                
                success_response = await ai_mixin.process_with_ai(
                    "Generate order success confirmation message",
                    success_context
                )
                
                tts_response = success_response.get("text", f"Order {order_id} submitted successfully")
                
                # Signal to FSM that order is submitted
                hsm_context_data.get("call_specific_data", {})["next_hsm_event_name"] = "COMPLETE_INTERACTION"
                hsm_context_data.get("call_specific_data", {})["order_id"] = order_id
                hsm_context_data.get("call_specific_data", {})["deliverect_order_id"] = deliverect_id
                hsm_context_data.get("call_specific_data", {})["estimated_time"] = estimated_time
                
                return {
                    "text": tts_response,
                    "success": True,
                    "order_id": order_id,
                    "deliverect_order_id": deliverect_id,
                    "estimated_time": estimated_time,
                    "handled": True,
                    "agent": self.agent_name
                }
            
            else:
                # Submission failed - handle gracefully
                logger.error(f"Order submission failed: {submission_result}")
                
                # Update order status in DB if we have it
                if db and hasattr(locals(), 'order'):
                    try:
                        order.status = "pending_pos_submission_failed"
                        await db.commit()
                    except Exception as e:
                        logger.error(f"Failed to update order status: {e}")
                
                # Send alert for manual intervention
                if submission_result.get("needs_manual_intervention"):
                    customer_details = {
                        "name": order_details.get("customer_name", "Unknown"),
                        "phone": order_details.get("customer_phone", call_sid)
                    }
                    
                    # Queue the notification task
                    try:
                        send_pos_submission_failure_alert.delay(order_id, customer_details)
                    except Exception as e:
                        logger.error(f"Failed to queue notification: {e}")
                
                # Use AI to generate failure handling response
                failure_context = {
                    "order_id": order_id,
                    "submission_error": submission_result.get("error", "Unknown error"),
                    "restaurant_name": getattr(settings, 'RESTAURANT_NAME', 'our restaurant')
                }
                
                failure_response = await ai_mixin.process_with_ai(
                    "Generate order submission failure customer message (non-alarming)",
                    failure_context
                )
                
                tts_response = failure_response.get("text", f"Order {order_id} received, processing shortly")
                
                # Signal to FSM - still complete but with a flag
                hsm_context_data.get("call_specific_data", {})["next_hsm_event_name"] = "ERROR_OCCURRED"
                hsm_context_data.get("call_specific_data", {})["order_id"] = order_id
                hsm_context_data.get("call_specific_data", {})["pos_submission_failed"] = True
                
                return {
                    "text": tts_response,
                    "success": False,  # Internal flag
                    "customer_success": True,  # Customer-facing success
                    "order_id": order_id,
                    "errors": [submission_result.get("error", "POS submission failed")],
                    "needs_manual_intervention": True,
                    "handled": True,
                    "agent": self.agent_name
                }
                
        except Exception as e:
            logger.error(f"Unexpected error during order submission: {e}", exc_info=True)
            
            # Use AI for exception handling response
            exception_context = {
                "order_id": order_id,
                "error_type": "system_exception",
                "restaurant_name": getattr(settings, 'RESTAURANT_NAME', 'our restaurant')
            }
            
            try:
                exception_response = await ai_mixin.process_with_ai(
                    "Generate system exception customer message (non-alarming)",
                    exception_context
                )
                tts_response = exception_response.get("text", f"Order {order_id} received, processing")
            except:
                # If even AI fails, we must raise the original exception
                raise e
            
            return {
                "text": tts_response,
                "success": False,
                "customer_success": True,
                "order_id": order_id,
                "errors": [str(e)],
                "needs_manual_intervention": True,
                "handled": True,
                "agent": self.agent_name
            }

    async def process_input(self, input_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process input in the fulfillment state.
        
        This might be called if a user directly interacts while in the FULFILLMENT state,
        but more likely the FulfillmentHandler will call submit_order() directly.
        
        Args:
            input_text: User input text
            context: Current FSM context
            
        Returns:
            Response with fulfillment results
        """
        call_sid = context.get("call_sid", "unknown_call")
        logger.info(f"[{call_sid}] AsyncFulfillmentAgent process_input called. Input: '{input_text}'")
        
        # Extract order details from context - try multiple locations
        order_data_from_context = context.get("cart", {})
        if not order_data_from_context or not order_data_from_context.get("items"):
            # Try call_specific_data as fallback
            order_data_from_context = context.get("call_specific_data", {}).get("validated_cart", {})
        
        logger.info(f"[{call_sid}] Order data extracted: {order_data_from_context}")
        
        # Submit the order
        return await self.submit_order(call_sid, order_data_from_context, context)