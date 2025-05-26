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
    """Order status update from Deliverect."""
    orderId: str
    channelOrderId: str
    status: int  # Deliverect status codes
    statusMessage: Optional[str] = None
    updatedAt: Optional[datetime] = None


@router.post("/order/status")
async def handle_order_status_update(
    update: OrderStatusUpdate,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """Handle order status updates from Deliverect."""
    try:
        logger.info(f"Received order status update: orderId={update.orderId}, status={update.status}")
        
        # TODO: Update order status in database
        # Status codes: 10=NEW, 20=ACCEPTED, 30=PREPARING, 40=READY, 50=PICKED_UP, 60=DELIVERED, 70=CANCELLED
        
        return {"status": "SUCCESS"}
    except Exception as e:
        logger.error(f"Error updating order status: {str(e)}", exc_info=True)
        return {"status": "FAILED"}


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
        
        # TODO: Update location busy status in database
        
        return {"status": "SUCCESS"}
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
        
        # TODO: Update location prep time in database
        
        return {"status": "SUCCESS"}
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
        
        # TODO: Update courier information in database
        
        return {"status": "SUCCESS"}
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
        
        # TODO: Update payment information in database
        
        return {"status": "SUCCESS"}
    except Exception as e:
        logger.error(f"Error updating payment info: {str(e)}", exc_info=True)
        return {"status": "FAILED"}