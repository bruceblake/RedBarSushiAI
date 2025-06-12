"""
Order status API routes for RedBarSushiAI FastAPI application.

This module provides API endpoints for order status checking and updates.
"""

import logging
from typing import Optional

from fastapi import APIRouter  # Depends, HTTPException, Request, Response removed

# JSONResponse import removed
from pydantic import BaseModel, Field

from app.models.order_async import Order

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
    110: "Canceled",
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
    estimatedDeliveryTime: Optional[str] = Field(
        None, description="The estimated delivery time"
    )
    estimatedPickupTime: Optional[str] = Field(
        None, description="The estimated pickup time"
    )


class WebhookResponse(BaseModel):
    """Response model for webhook endpoints"""

    status: str = Field(..., description="Status of the webhook processing")
    message: str = Field(..., description="Message about the webhook processing")


# =====================
# API Routes
# =====================

# Functions check_order_status, update_order_status were here, removed as unused.

# =====================
# Helper Functions
# =====================

# Function set_channel_status was here, removed as unused.


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
                body=message, from_=TWILIO_PHONE_NUMBER, to=phone_number
            )
            logger.info(f"Sent status update SMS to {phone_number}")
        else:
            logger.error("Twilio client not available for SMS")

    except Exception as e:
        logger.error(f"Failed to send status notification: {e}")
