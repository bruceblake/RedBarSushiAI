"""
Notification tasks for Celery background processing.

This module contains Celery tasks for sending notifications via SMS and email.
"""

import logging
from typing import Dict, Any, Optional

from app.config import settings

logger = logging.getLogger(__name__)

# Try to import Twilio, fall back to logging if not available
try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = bool(settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN)
except ImportError:
    logger.warning("Twilio not available - SMS notifications will be logged only")
    TWILIO_AVAILABLE = False

# Try to import Celery, fall back to direct execution if not available
try:
    from celery import current_app as celery_app
    def task(name: str = None, **kwargs):
        """Real Celery task decorator."""
        return celery_app.task(name=name, **kwargs)
except ImportError:
    logger.warning("Celery not available - tasks will execute synchronously")
    def task(name: str = None, **kwargs):
        """Fallback task decorator."""
        def decorator(func):
            func.delay = lambda *args, **kwargs: func(*args, **kwargs)
            return func
        return decorator


@task(name="send_pos_submission_failure_alert")
def send_pos_submission_failure_alert(
    order_id: str,
    error_message: str,
    order_details: Optional[Dict[str, Any]] = None
):
    """
    Send POS submission failure alert.
    
    Args:
        order_id: The order ID that failed
        error_message: Error message from POS system
        order_details: Optional order details for context
    """
    logger.error(f"POS submission failed for order {order_id}: {error_message}")
    
    # In a real implementation, this would send SMS/email alerts
    # For now, just log the failure
    if order_details:
        logger.error(f"Order details: {order_details}")
    
    # Log admin alert - in production this could send to Slack, email, etc.
    logger.critical(f"ADMIN ALERT - POS submission failed for order {order_id}: {error_message}")
    return {"status": "logged", "order_id": order_id}


@task(name="send_order_confirmation_sms")
def send_order_confirmation_sms(
    phone_number: str,
    order_id: str,
    order_details: Dict[str, Any]
):
    """
    Send order confirmation SMS to customer.
    
    Args:
        phone_number: Customer phone number
        order_id: Order ID
        order_details: Order details for SMS content
    """
    logger.info(f"Sending order confirmation SMS to {phone_number} for order {order_id}")
    
    if not TWILIO_AVAILABLE:
        logger.warning(f"SMS not sent - Twilio not configured. Order {order_id} confirmed.")
        return {"status": "logged", "phone_number": phone_number, "order_id": order_id}
    
    try:
        client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        
        # Format order details for SMS
        items = order_details.get('items', [])
        total = order_details.get('total', 0)
        
        message_body = f"Order confirmed! Order #{order_id}\n"
        message_body += f"Items: {len(items)} item(s)\n"
        message_body += f"Total: ${total:.2f}\n"
        message_body += f"Thank you for ordering from {settings.RESTAURANT_NAME}!"
        
        message = client.messages.create(
            body=message_body,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone_number
        )
        
        logger.info(f"SMS sent successfully: {message.sid}")
        return {"status": "sent", "phone_number": phone_number, "order_id": order_id, "message_sid": message.sid}
        
    except Exception as e:
        logger.error(f"Failed to send SMS: {e}")
        return {"status": "failed", "phone_number": phone_number, "order_id": order_id, "error": str(e)}


@task(name="send_order_ready_notification")
def send_order_ready_notification(
    phone_number: str,
    order_id: str,
    estimated_pickup_time: Optional[str] = None
):
    """
    Send order ready notification to customer.
    
    Args:
        phone_number: Customer phone number
        order_id: Order ID
        estimated_pickup_time: Optional estimated pickup time
    """
    logger.info(f"Sending order ready notification to {phone_number} for order {order_id}")
    
    if not TWILIO_AVAILABLE:
        logger.warning(f"SMS not sent - Twilio not configured. Order {order_id} ready.")
        return {"status": "logged", "phone_number": phone_number, "order_id": order_id}
    
    try:
        client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        
        message_body = f"Your order #{order_id} is ready for pickup!"
        if estimated_pickup_time:
            message_body += f"\nEstimated pickup: {estimated_pickup_time}"
        message_body += f"\nThank you for choosing {settings.RESTAURANT_NAME}!"
        
        message = client.messages.create(
            body=message_body,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone_number
        )
        
        logger.info(f"Order ready SMS sent successfully: {message.sid}")
        return {"status": "sent", "phone_number": phone_number, "order_id": order_id, "message_sid": message.sid}
        
    except Exception as e:
        logger.error(f"Failed to send order ready SMS: {e}")
        return {"status": "failed", "phone_number": phone_number, "order_id": order_id, "error": str(e)}


@task(name="send_admin_alert")
def send_admin_alert(
    alert_type: str,
    message: str,
    context: Optional[Dict[str, Any]] = None
):
    """
    Send alert to system administrators.
    
    Args:
        alert_type: Type of alert (error, warning, info)
        message: Alert message
        context: Optional context data
    """
    logger.warning(f"Admin alert [{alert_type}]: {message}")
    
    if context:
        logger.warning(f"Alert context: {context}")
    
    # Log admin alert - in production this could send to Slack, email, PagerDuty, etc.
    logger.critical(f"ADMIN ALERT [{alert_type.upper()}]: {message}")
    return {"status": "logged", "alert_type": alert_type}