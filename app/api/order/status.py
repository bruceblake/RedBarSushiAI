"""
Order status API routes for RedBarSushiAI FastAPI application.

This module provides API endpoints for order status checking and updates.
"""

import json
import logging
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_async import get_db
from app.models.order_async import Order
from app.utils.helpers_async import commit_with_retry_async

# Configure logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Try to import tasks module for status updates
try:
    from tasks import send_order_status_update_task
except ImportError:
    # Create a dummy task for testing
    def send_order_status_update_task(*args, **kwargs):
        logger.warning(
            "Could not import send_order_status_update_task from tasks module. Will try again when needed."
        )

# Global variable to track the channel status
# 0: registered, 1: active, 2: inactive
# This value is used by other modules
# Any changes to this value should be done through the set_channel_status function
channel_status = 1

# Status code to text mapping
STATUS_TEXT_MAP = {
    10: "Received",
    20: "Accepted",
    30: "In Preparation",
    40: "Prepared",
    70: "Ready for Pickup",
    80: "Completed",
    90: "Rejected",
    100: "Cancellation Requested",
    110: "Canceled"
}

# =====================
# Pydantic Models
# =====================

class OrderStatusRequest(BaseModel):
    """Request model for checking order status"""
    body: str = Field(..., description="The message body from SMS")

class OrderStatusResponse(BaseModel):
    """Response model for order status"""
    message: str = Field(..., description="The status message to send back to the user")

class StatusUpdateWebhook(BaseModel):
    """Request model for status update webhook from Deliverect"""
    channelOrderId: str = Field(..., description="The channel order ID")
    status: int = Field(..., description="The order status code")
    estimatedDeliveryTime: Optional[str] = Field(None, description="The estimated delivery time")
    estimatedPickupTime: Optional[str] = Field(None, description="The estimated pickup time")

class WebhookResponse(BaseModel):
    """Response model for webhook endpoints"""
    status: str = Field(..., description="Status of the webhook processing")
    message: str = Field(..., description="Message about the webhook processing")

# =====================
# API Routes
# =====================

@router.post("/check_order_status", response_model=OrderStatusResponse)
async def check_order_status(
    request: OrderStatusRequest,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """
    Check the status of an existing order.
    
    This endpoint is used for SMS-based order status checking.
    """
    # Get the order ID from the request
    user_resp = request.body.strip()
    
    # Try to extract an order ID from the message
    order_id = None
    
    # Check if the message is a number (likely an order ID)
    if user_resp.isdigit():
        order_id = int(user_resp)
    else:
        # Try to find a number in the message
        id_matches = re.findall(r'\\d+', user_resp)
        if id_matches:
            order_id = int(id_matches[0])
    
    # If we couldn't find an order ID, ask for it
    if not order_id:
        return {"message": "To check your order status, please reply with your order number."}
    
    # Try to find the order in our database
    try:
        # Use SQLAlchemy 2.0 async style
        result = await db.execute(
            Order.__table__.select().where(Order.id == order_id)
        )
        order = result.scalars().first()
        
        if not order:
            # Order not found
            return {
                "message": f"Sorry, we couldn't find an order with ID {order_id}. "
                           f"Please verify your order number and try again."
            }
        
        # Get order status
        status_code = order.status
        status_text = get_status_text(status_code)
        
        # Format response based on status
        if status_code == 10:  # Received
            message = (
                f"Your order #{order_id} has been received and is being processed. "
                f"We'll update you when it's accepted by the restaurant."
            )
        elif status_code == 20:  # Accepted
            message = (
                f"Your order #{order_id} has been accepted by Red Bar Sushi. "
                f"We'll update you when it's ready for pickup."
            )
        elif status_code in [30, 40]:  # In preparation or prepared
            message = (
                f"Your order #{order_id} is being prepared by Red Bar Sushi. "
                f"We'll update you when it's ready for pickup."
            )
        elif status_code == 70:  # Ready for pickup
            message = (
                f"Great news! Your order #{order_id} is now ready for pickup at Red Bar Sushi. "
                f"You can pick it up at your convenience."
            )
        elif status_code == 80:  # Delivered/completed
            message = (
                f"Your order #{order_id} has been completed. "
                f"Thank you for choosing Red Bar Sushi!"
            )
        elif status_code in [90, 100, 110]:  # Rejected or canceled
            message = (
                f"Your order #{order_id} has been {status_text}. "
                f"Please contact us if you have any questions."
            )
        else:
            # Unknown status code
            message = (
                f"Your order #{order_id} is in status: {status_text}. "
                f"For more information, please contact us directly."
            )
        
        # Return the response
        return {"message": message}
        
    except Exception as e:
        logger.error(f"Error checking order status: {e}")
        return {
            "message": "Sorry, we encountered an error while checking your order status. "
                       "Please try again later or contact us directly."
        }

@router.post("/update_order_status", response_model=WebhookResponse)
async def update_order_status(
    webhook_data: StatusUpdateWebhook,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """
    Handle webhook for order status updates from Deliverect.
    """
    # Log the incoming webhook data
    logger.info(f"Received status update webhook: {webhook_data.dict()}")
    
    try:
        # Extract the key information
        channel_order_id = webhook_data.channelOrderId
        status = webhook_data.status
        
        # Find the order in our database
        result = await db.execute(
            Order.__table__.select().where(Order.deliverect_channel_order_id == channel_order_id)
        )
        order = result.scalars().first()
        
        if not order:
            logger.warning(f"Order not found for channel order ID: {channel_order_id}")
            # We still return success to acknowledge receipt
            return {"status": "success", "message": "Webhook received, but order not found"}
        
        # Update the order status
        old_status = order.status
        order.status = status
        
        # Add any additional information if available
        if webhook_data.estimatedDeliveryTime:
            try:
                order.estimated_time = datetime.fromisoformat(
                    webhook_data.estimatedDeliveryTime.replace('Z', '+00:00')
                )
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse estimated delivery time: {e}")
        
        if webhook_data.estimatedPickupTime and not webhook_data.estimatedDeliveryTime:
            try:
                order.estimated_time = datetime.fromisoformat(
                    webhook_data.estimatedPickupTime.replace('Z', '+00:00')
                )
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse estimated pickup time: {e}")
        
        # Save the changes
        order.updated_at = datetime.now()
        await commit_with_retry_async(db)
        
        logger.info(f"Updated order status from {old_status} to {status} for order {channel_order_id}")
        
        # If status changed, send notification
        if old_status != status:
            # Trigger notification through Celery task
            if send_order_status_update_task:
                send_order_status_update_task.delay(order.id)
                logger.info(f"Queued status update notification for order {order.id}")
            else:
                # Direct send if Celery not available
                await send_status_notification_async(order)
        
        return {"status": "success", "message": "Order status updated"}
        
    except Exception as e:
        logger.error(f"Error processing status update webhook: {e}")
        # Return 200 even on error to prevent retries
        return {"status": "error", "message": f"Error: {str(e)}"}

# =====================
# Helper Functions
# =====================

def set_channel_status(status: int) -> int:
    """
    Update the channel status.
    
    Args:
        status: New status value (0: registered, 1: active, 2: inactive)
        
    Returns:
        The new status value
    """
    global channel_status
    channel_status = status
    logger.info(f"Channel status updated to {status}")
    return channel_status

def get_status_text(status_code: int) -> str:
    """
    Get human-readable status text from status code.
    
    Args:
        status_code: Numeric status code
        
    Returns:
        String with human-readable status
    """
    return STATUS_TEXT_MAP.get(status_code, f"Unknown Status ({status_code})")

async def send_status_notification_async(order: Order) -> None:
    """
    Send an SMS notification about order status update.
    
    Args:
        order: Order object to send notification for
    """
    try:
        # Import Twilio client - need to import here to avoid circular imports
        from app import twilio_client
        from app.config import TWILIO_PHONE_NUMBER
        
        # Format phone number
        phone_number = order.customer_phone
        if not phone_number.startswith("+"):
            phone_number = f"+{phone_number}"
        
        # Get status text
        status_text = get_status_text(order.status)
        
        # Format message based on status
        if order.status == 20:  # Accepted
            message = (
                f"Red Bar Sushi has accepted your order #{order.id}. "
                f"We'll update you when it's ready for pickup."
            )
        elif order.status == 70:  # Ready for pickup
            message = (
                f"Great news! Your order #{order.id} is now ready for pickup at Red Bar Sushi. "
                f"You can pick it up at your convenience."
            )
        elif order.status == 80:  # Completed
            message = (
                f"Your order #{order.id} has been completed. "
                f"Thank you for choosing Red Bar Sushi!"
            )
        elif order.status in [90, 100, 110]:  # Rejected or canceled
            message = (
                f"Your order #{order.id} has been {status_text}. "
                f"Please contact us if you have any questions."
            )
        else:
            # Other statuses don't need notifications
            return
        
        # Send SMS if Twilio client is available
        if twilio_client:
            twilio_client.messages.create(
                body=message,
                from_=TWILIO_PHONE_NUMBER,
                to=phone_number
            )
            logger.info(f"Sent status update SMS to {phone_number}")
        else:
            logger.error("Twilio client not available for SMS")
            
    except Exception as e:
        logger.error(f"Failed to send status notification: {e}")