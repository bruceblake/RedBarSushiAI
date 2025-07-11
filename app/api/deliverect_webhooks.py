"""
Deliverect webhook endpoints for order and location management.

This module handles various webhook callbacks from Deliverect.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from datetime import datetime

from app.dependencies import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


# Order Status Update
class OrderStatusUpdate(BaseModel):
    """Order status update from Deliverect - matches official webhook format."""
    orderId: str = Field(..., description="Deliverect order ID")
    status: int = Field(..., description="Order status code")
    timeStamp: str = Field(..., description="Timestamp of status change")
    receiptId: Optional[str] = Field("", description="POS receipt ID")
    reason: Optional[str] = Field("", description="Reason for status change")
    channelOrderId: str = Field(..., description="Channel order ID")
    location: str = Field(..., description="Location ID")
    channelLink: str = Field(..., description="Channel link ID")


# Deliverect status code mappings based on official documentation
DELIVERECT_STATUS_CODES = {
    # POS Order Statuses
    10: "New",
    20: "Accepted", 
    40: "Printed",
    50: "Preparing",
    60: "Prepared", 
    70: "Pickup Ready",
    90: "Finalized",
    95: "Auto_Finalized",
    110: "Canceled",
    120: "Failed",
    
    # Courier Statuses
    81: "Delivery Created",
    83: "En Route to Pickup", 
    85: "Arrived at Pickup",
    87: "En Route To Dropoff",
    89: "Arrived At Drop Off",
    90: "Delivered",
    115: "Delivery Canceled",
    
    # Channel Statuses
    100: "Cancel",
    
    # System Only Statuses
    1: "Parsed",
    2: "Received by POS",
    3: "Sent to DMA",
    4: "Before_Parsed",
    5: "Receipt_Not_Found",
    6: "Received by DMA",
    7: "Printed by DMA",
    25: "Scheduled",
    30: "Duplicate",
    35: "Denied",
    72: "Unknown",
    73: "Courier assigned",
    76: "No Courier Found",
    114: "Delivery Auto Canceled",
    121: "POS Failed",
    122: "Retry Failed",
    123: "Manual Retry",
    124: "Parse Failed",
    125: "Order ignored",
    126: "Cancel Failed",
    129: "Resolved"
}


@router.post("/order/status")
async def handle_order_status_update(
    update: OrderStatusUpdate,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """Handle order status updates from Deliverect."""
    try:
        status_name = DELIVERECT_STATUS_CODES.get(update.status, f"Unknown ({update.status})")
        logger.info(f"Received order status update: orderId={update.orderId}, status={update.status} ({status_name})")
        
        # Update order status in database
        from app.db.crud_order_async import update_order_deliverect_status
        
        # Convert to datetime if needed
        try:
            updated_at = datetime.fromisoformat(update.timeStamp.replace('Z', '+00:00'))
        except Exception:
            updated_at = datetime.utcnow()
        
        await update_order_deliverect_status(
            db=db,
            channel_order_id=update.channelOrderId,
            deliverect_order_id=update.orderId,
            status_code=update.status,
            status_name=status_name,
            receipt_id=update.receiptId,
            reason=update.reason,
            updated_at=updated_at
        )
        
        # Handle special status notifications
        await _handle_status_notifications(update, status_name, db)
        
        # Return required response format
        return {"result": "OK"}
        
    except Exception as e:
        logger.error(f"Error updating order status: {str(e)}", exc_info=True)
        return {"result": "ERROR"}


async def _handle_status_notifications(
    update: OrderStatusUpdate, 
    status_name: str, 
    db: AsyncSession
):
    """Handle notifications based on order status changes."""
    try:
        # Import notification tasks
        from app.tasks.notifications import send_order_ready_notification, send_admin_alert
        
        # Notify customer when order is ready for pickup
        if update.status == 70:  # Pickup Ready
            logger.info(f"Order {update.channelOrderId} is ready for pickup")
            # Get customer phone from order
            from app.db.crud_order_async import get_order_by_channel_id
            order = await get_order_by_channel_id(db, update.channelOrderId)
            if order and order.customer_phone:
                send_order_ready_notification.delay(
                    phone_number=order.customer_phone,
                    order_id=update.channelOrderId
                )
        
        # Alert admin for failed orders
        elif update.status in [110, 120, 121, 35]:  # Canceled, Failed, POS Failed, Denied
            logger.warning(f"Order {update.channelOrderId} failed with status: {status_name}")
            send_admin_alert.delay(
                alert_type="order_failure",
                message=f"Order {update.channelOrderId} failed: {status_name}",
                context={
                    "order_id": update.channelOrderId,
                    "deliverect_order_id": update.orderId,
                    "status": update.status,
                    "reason": update.reason
                }
            )
            
    except Exception as e:
        logger.error(f"Error handling status notifications: {e}")


# Busy Mode Update
class BusyModeUpdate(BaseModel):
    """Busy mode update request."""
    channelLinkId: str
    status: str  # "ONLINE" or "PAUSED"
    reason: Optional[str] = None


@router.post("/location/busy")
async def handle_busy_mode_update(
    update: BusyModeUpdate,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """Handle busy mode updates from Deliverect."""
    try:
        logger.info(f"Received busy mode update: channelLinkId={update.channelLinkId}, status={update.status}")
        
        # Update location busy status in database
        from app.db.crud_location_async import update_location_busy_status
        
        await update_location_busy_status(
            db=db,
            channel_link_id=update.channelLinkId,
            is_busy=(update.status == "busy")
        )
        
        logger.info(f"Updated busy status for location {update.channelLinkId}: {update.status}")
        return {"result": "OK"}
    except Exception as e:
        logger.error(f"Error updating busy mode: {str(e)}", exc_info=True)
        return {"status": "FAILED"}


# Preparation Time Update
class PrepTimeUpdate(BaseModel):
    """Preparation time update request."""
    channelLinkId: str
    prepTime: int  # Minutes
    orderType: Optional[str] = None  # "delivery" or "pickup"


@router.post("/location/preptime")
async def handle_prep_time_update(
    update: PrepTimeUpdate,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """Handle preparation time updates from Deliverect."""
    try:
        logger.info(f"Received prep time update: channelLinkId={update.channelLinkId}, prepTime={update.prepTime}")
        
        # Update location preparation time in database
        from app.db.crud_location_async import update_location_prep_time
        
        await update_location_prep_time(
            db=db,
            channel_link_id=update.channelLinkId,
            prep_time_minutes=update.prepTime,
            order_type=update.orderType
        )
        
        logger.info(f"Updated prep time for location {update.channelLinkId}: {update.prepTime} minutes")
        return {"result": "OK"}
    except Exception as e:
        logger.error(f"Error updating prep time: {str(e)}", exc_info=True)
        return {"status": "FAILED"}


# Courier Update
class CourierUpdate(BaseModel):
    """Courier update information."""
    orderId: str
    channelOrderId: str
    courierName: Optional[str] = None
    courierPhone: Optional[str] = None
    estimatedPickupTime: Optional[datetime] = None
    estimatedDeliveryTime: Optional[datetime] = None
    trackingUrl: Optional[str] = None


@router.post("/order/courier")
async def handle_courier_update(
    update: CourierUpdate,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """Handle courier updates from Deliverect."""
    try:
        logger.info(f"Received courier update for order: {update.orderId}")
        
        # Update courier information in database
        from app.db.crud_order_async import update_order_courier_info
        
        await update_order_courier_info(
            db=db,
            channel_order_id=update.channelOrderId,
            courier_name=update.courierName,
            courier_phone=update.courierPhone,
            estimated_pickup=update.estimatedPickupTime,
            estimated_delivery=update.estimatedDeliveryTime,
            tracking_url=update.trackingUrl
        )
        
        logger.info(f"Updated courier info for order {update.channelOrderId}")
        return {"result": "OK"}
    except Exception as e:
        logger.error(f"Error updating courier info: {str(e)}", exc_info=True)
        return {"status": "FAILED"}


# Payment Update
class PaymentUpdate(BaseModel):
    """Payment update information."""
    orderId: str
    channelOrderId: str
    paymentStatus: str  # "PENDING", "PAID", "FAILED", "REFUNDED"
    paymentMethod: Optional[str] = None
    transactionId: Optional[str] = None
    amount: Optional[float] = None


@router.post("/order/payment")
async def handle_payment_update(
    update: PaymentUpdate,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """Handle payment updates from Deliverect."""
    try:
        logger.info(f"Received payment update for order: {update.orderId}, status={update.paymentStatus}")
        
        # Update payment information in database
        from app.db.crud_order_async import update_order_payment_info
        
        await update_order_payment_info(
            db=db,
            channel_order_id=update.channelOrderId,
            payment_status=update.paymentStatus,
            payment_method=update.paymentMethod,
            transaction_id=update.transactionId,
            amount=update.amount
        )
        
        logger.info(f"Updated payment info for order {update.channelOrderId}: {update.paymentStatus}")
        return {"result": "OK"}
    except Exception as e:
        logger.error(f"Error updating payment info: {str(e)}", exc_info=True)
        return {"status": "FAILED"}