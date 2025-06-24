"""
Notification tasks for RedBarSushiAI.

This module handles sending notifications for various events
like POS submission failures, order confirmations, etc.
"""

import logging
from typing import Dict, Any
from datetime import datetime

from celery import shared_task
from app.config import settings

logger = logging.getLogger(__name__)


@shared_task
def send_pos_submission_failure_alert(order_id: str, customer_details: Dict[str, Any]):
    """
    Send alert when POS submission fails.
    
    Args:
        order_id: The order ID that failed
        customer_details: Customer information
    """
    try:
        # Log the failure
        logger.critical(f"POS SUBMISSION FAILURE - Order {order_id}")
        logger.critical(f"Customer: {customer_details.get('name', 'Unknown')} - {customer_details.get('phone', 'Unknown')}")
        logger.critical(f"Time: {datetime.now().isoformat()}")
        
        # TODO: Implement actual notification methods
        # Options:
        # 1. Send email to restaurant staff
        # 2. Send SMS to manager
        # 3. Post to Slack channel
        # 4. Create dashboard alert
        
        # For now, just log
        notification_message = f"""
        URGENT: POS Submission Failed
        
        Order ID: {order_id}
        Customer: {customer_details.get('name', 'Unknown')}
        Phone: {customer_details.get('phone', 'Unknown')}
        Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        This order needs manual intervention!
        """
        
        logger.critical(notification_message)
        
        # If email is configured, send it
        if hasattr(settings, 'ADMIN_EMAIL'):
            # TODO: Implement email sending
            pass
        
        # If Slack webhook is configured, post to Slack
        if hasattr(settings, 'SLACK_WEBHOOK_URL'):
            # TODO: Implement Slack notification
            pass
        
        return {
            "success": True,
            "order_id": order_id,
            "notified_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to send POS submission failure alert: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@shared_task
def retry_pos_submission(order_id: str):
    """
    Retry submitting an order to POS system.
    
    Args:
        order_id: The order ID to retry
    """
    try:
        from app.db_async import async_session_factory
        from app.services.deliverect_service import DeliverectService
        from app.models.order_async import Order
        from sqlalchemy import select
        import asyncio
        
        async def _retry():
            async with async_session_factory() as db:
                # Get the order
                stmt = select(Order).where(Order.id == order_id)
                result = await db.execute(stmt)
                order = result.scalar_one_or_none()
                
                if not order:
                    logger.error(f"Order {order_id} not found for retry")
                    return False
                
                # Check if already submitted
                if order.deliverect_channel_order_id:
                    logger.info(f"Order {order_id} already has Deliverect ID, skipping retry")
                    return True
                
                # Retry submission
                service = DeliverectService()
                result = await service.submit_order(order, db)
                
                if result["success"]:
                    logger.info(f"Successfully retried order {order_id}")
                    
                    # Send success notification
                    # TODO: Notify staff that retry was successful
                    
                    return True
                else:
                    logger.error(f"Retry failed for order {order_id}: {result.get('error')}")
                    return False
        
        # Run the async function
        success = asyncio.run(_retry())
        
        return {
            "success": success,
            "order_id": order_id,
            "retried_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to retry POS submission: {e}")
        return {
            "success": False,
            "error": str(e)
        }