"""
Order status routes for RedBarSushiAI.
This module provides the routes for order status checking and updates.
"""

import json
import logging
import requests
from datetime import datetime
from flask import request, session, Response, jsonify
from twilio.twiml.voice_response import VoiceResponse
from twilio.twiml.messaging_response import MessagingResponse

# Import blueprint reference directly to avoid circular imports
# This assumes order_bp is defined in __init__.py
from app.routes.order.__init__ import order_bp
from app.utils.helpers import log_info, commit_with_retry
from app.utils.deliverect import get_order_status
from app.config import BASE_URL
from app import db, twilio_client
from app.models import Order

# Configure logger
logger = logging.getLogger(__name__)

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
# This value is imported and used by app.routes.voice and other modules
# Any changes to this value should be done through the functions defined below
channel_status = 1

def set_channel_status(status):
    """
    Update the channel status.
    
    Args:
        status: New status value (0: registered, 1: active, 2: inactive)
    """
    global channel_status
    channel_status = status
    logger.info(f"Channel status updated to {status}")
    return channel_status

@order_bp.route("/check_order_status", methods=["POST"])
def check_order_status():
    """
    Check the status of an existing order.
    """
    # Get the order ID from the request
    user_resp = request.form.get("Body", "").strip()
    
    # Build the response for SMS
    response = MessagingResponse()
    
    # Try to extract an order ID from the message
    order_id = None
    
    # Check if the message is a number (likely an order ID)
    if user_resp.isdigit():
        order_id = int(user_resp)
    else:
        # Try to find a number in the message
        import re
        id_matches = re.findall(r'\d+', user_resp)
        if id_matches:
            order_id = int(id_matches[0])
    
    # If we couldn't find an order ID, ask for it
    if not order_id:
        response.message(
            "To check your order status, please reply with your order number."
        )
        return Response(str(response), mimetype="text/xml")
    
    # Try to find the order in our database
    try:
        order = Order.query.filter_by(id=order_id).first()
        
        if not order:
            # Order not found
            response.message(
                f"Sorry, we couldn't find an order with ID {order_id}. Please verify your order number and try again."
            )
            return Response(str(response), mimetype="text/xml")
        
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
        
        # Send the response
        response.message(message)
        return Response(str(response), mimetype="text/xml")
        
    except Exception as e:
        logger.error(f"Error checking order status: {e}")
        response.message(
            "Sorry, we encountered an error while checking your order status. Please try again later or contact us directly."
        )
        return Response(str(response), mimetype="text/xml")

@order_bp.route("/update_order_status", methods=["POST"])
def update_order_status():
    """
    Handle webhook for order status updates from Deliverect.
    """
    # Get the webhook payload
    try:
        webhook_data = request.json
        logger.info(f"Received status update webhook: {json.dumps(webhook_data)}")
        
        # Validate the webhook structure
        if not webhook_data or not isinstance(webhook_data, dict):
            logger.error("Invalid webhook format")
            return jsonify({"status": "error", "message": "Invalid request format"}), 400
        
        # Extract the key information
        channel_order_id = webhook_data.get("channelOrderId")
        status = webhook_data.get("status")
        
        if not channel_order_id or status is None:
            logger.error("Missing required fields in webhook")
            return jsonify({"status": "error", "message": "Missing required fields"}), 400
        
        # Find the order in our database
        order = Order.query.filter_by(deliverect_channel_order_id=channel_order_id).first()
        
        if not order:
            logger.warning(f"Order not found for channel order ID: {channel_order_id}")
            # We still return success to acknowledge receipt
            return jsonify({"status": "success", "message": "Webhook received, but order not found"}), 200
        
        # Update the order status
        old_status = order.status
        order.status = status
        
        # Add any additional information if available
        if "estimatedDeliveryTime" in webhook_data:
            try:
                order.estimated_time = datetime.fromisoformat(
                    webhook_data["estimatedDeliveryTime"].replace('Z', '+00:00')
                )
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse estimated delivery time: {e}")
        
        if "estimatedPickupTime" in webhook_data and "estimatedDeliveryTime" not in webhook_data:
            try:
                order.estimated_time = datetime.fromisoformat(
                    webhook_data["estimatedPickupTime"].replace('Z', '+00:00')
                )
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse estimated pickup time: {e}")
        
        # Save the changes
        order.updated_at = datetime.now()
        commit_with_retry(db.session)
        
        logger.info(f"Updated order status from {old_status} to {status} for order {channel_order_id}")
        
        # If status changed, send notification
        if old_status != status:
            # Trigger notification through Celery task
            if send_order_status_update_task:
                send_order_status_update_task.delay(order.id)
                logger.info(f"Queued status update notification for order {order.id}")
            else:
                # Direct send if Celery not available
                send_status_notification(order)
        
        return jsonify({"status": "success", "message": "Order status updated"}), 200
        
    except Exception as e:
        logger.error(f"Error processing status update webhook: {e}")
        # Return 200 even on error to prevent retries
        return jsonify({"status": "error", "message": f"Error: {str(e)}"}), 200

def get_status_text(status_code):
    """
    Get human-readable status text from status code.
    
    Args:
        status_code: Numeric status code
        
    Returns:
        String with human-readable status
    """
    status_map = {
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
    
    return status_map.get(status_code, f"Unknown Status ({status_code})")

def send_status_notification(order):
    """
    Send an SMS notification about order status update.
    
    Args:
        order: Order object to send notification for
    """
    try:
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
                from_="+18005551234",  # Use your Twilio phone number
                to=phone_number
            )
            logger.info(f"Sent status update SMS to {phone_number}")
        else:
            logger.error("Twilio client not available for SMS")
            
    except Exception as e:
        logger.error(f"Failed to send status notification: {e}")

# Export all functions and variables
__all__ = [
    # Variables
    'channel_status',
    
    # Status management functions
    'set_channel_status',
    
    # API routes
    'check_order_status', 
    'update_order_status',
    
    # Helper functions 
    'get_status_text', 
    'send_status_notification'
]