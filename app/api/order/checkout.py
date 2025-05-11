"""
Order checkout API routes for RedBarSushiAI FastAPI application.

This module provides API endpoints for order checkout and final processing.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_async import get_db
from app.models.order_async import Order, OrderItem
from app.utils.helpers_async import commit_with_retry_async, log_info_async
from app.utils.order_utils import mark_unavailable_items, build_order_description, validate_modifiers
from app.utils.deliverect import build_deliverect_order, get_deliverect_headers, send_order_to_deliverect, generate_order_id

# Configure logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# =====================
# Pydantic Models
# =====================

class DeliveryAddress(BaseModel):
    """Model for delivery address"""
    street: str
    city: str
    state: str
    zip_code: str
    notes: Optional[str] = None

class CheckoutRequest(BaseModel):
    """Request model for order checkout"""
    order_items: List[dict]
    customer_name: str
    customer_phone: str
    order_type: str = "pickup"  # pickup or delivery
    delivery_address: Optional[DeliveryAddress] = None
    requested_time: Optional[datetime] = None
    payment_method: Optional[str] = None
    payment_token: Optional[str] = None
    
    @validator('order_type')
    def validate_order_type(cls, v):
        """Validate order type"""
        if v not in ["pickup", "delivery"]:
            raise ValueError("Order type must be either 'pickup' or 'delivery'")
        return v
    
    @validator('delivery_address')
    def validate_delivery_address(cls, v, values):
        """Validate delivery address"""
        if values.get('order_type') == "delivery" and not v:
            raise ValueError("Delivery address is required for delivery orders")
        return v

class CheckoutResponse(BaseModel):
    """Response model for order checkout"""
    order_id: str
    deliverect_order_id: Optional[str] = None
    total_price: float
    status: str
    estimated_time: Optional[datetime] = None
    message: str

# =====================
# API Routes
# =====================

@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(
    request: CheckoutRequest,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Process order checkout.
    
    This endpoint handles the final checkout process for an order,
    validates all details, and submits it to the appropriate systems.
    """
    # Validate order items
    if not request.order_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order must contain at least one item"
        )
    
    # Mark unavailable items
    available_items, unavailable_items = mark_unavailable_items(request.order_items)
    
    # Handle case where all items are unavailable
    if not available_items and unavailable_items:
        unavailable_names = [
            item.get("name").split(" (")[0] for item in unavailable_items
        ]
        unavailable_text = ", ".join(unavailable_names)
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Items unavailable: {unavailable_text}"
        )
    
    # Include both available and unavailable items
    order_items = available_items + unavailable_items
    
    # Validate modifiers
    validation_result = validate_modifiers(order_items)
    
    if not validation_result["valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid order: {validation_result['reason']}"
        )
    
    # Generate a unique order ID
    order_id = str(uuid.uuid4())
    
    # Build the deliverect order payload
    try:
        deliverect_payload = build_deliverect_order(
            order_items=order_items,
            customer_name=request.customer_name,
            customer_phone=request.customer_phone,
            order_type=request.order_type,
            delivery_address=request.delivery_address.dict() if request.delivery_address else None,
            requested_time=request.requested_time,
            channel_order_id=order_id
        )
    except Exception as e:
        logger.error(f"Error building Deliverect payload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error preparing order for processing"
        )
    
    # Send the order to Deliverect
    try:
        deliverect_response = await send_order_to_deliverect(deliverect_payload)
        deliverect_order_id = deliverect_response.get("id")
        
        if not deliverect_order_id:
            logger.error(f"Deliverect order creation failed: {deliverect_response}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Order processing failed"
            )
            
        logger.info(f"Order sent to Deliverect successfully, ID: {deliverect_order_id}")
    except Exception as e:
        logger.error(f"Error sending order to Deliverect: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error submitting order to restaurant"
        )
    
    # Store the order in our database
    try:
        # Calculate total price
        total_price = sum(item.get("price", 0) * item.get("quantity", 1) for item in order_items)
        
        # Create a new Order object
        order = Order(
            id=order_id,
            deliverect_channel_order_id=deliverect_order_id,
            customer_phone=request.customer_phone,
            customer_name=request.customer_name,
            order_type=request.order_type,
            status=10,  # 10 = received
            total_price=total_price,
            placed_at=datetime.now(),
            delivery_address=request.delivery_address.dict() if request.delivery_address else None
        )
        
        # Add order items
        for item_data in order_items:
            item = OrderItem(
                id=str(uuid.uuid4()),
                order_id=order_id,
                menu_item_plu=item_data.get("reference_handler", ""),
                name=item_data.get("name", ""),
                quantity=item_data.get("quantity", 1),
                price=item_data.get("price", 0.0),
                note=item_data.get("notes", "")
            )
            db.add(item)
        
        # Add the order to the session and commit
        db.add(order)
        await commit_with_retry_async(db)
        
        logger.info(f"Order saved to database, ID: {order_id}")
    except Exception as e:
        logger.error(f"Error saving order to database: {e}")
        # We don't raise an exception here because the order has been sent to Deliverect,
        # so it's in progress with the restaurant even if our local save fails
    
    # Build the order description for the response
    order_description = build_order_description(order_items)
    
    # Return success response
    return {
        "order_id": order_id,
        "deliverect_order_id": deliverect_order_id,
        "total_price": total_price,
        "status": "received",
        "estimated_time": None,  # Will be updated later when the restaurant provides an estimate
        "message": f"Your order has been received and is being processed. {order_description}. Total: ${total_price:.2f}"
    }