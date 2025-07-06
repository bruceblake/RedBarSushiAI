"""
Order confirmation API routes for RedBarSushiAI FastAPI application.

This module provides API endpoints for order confirmation and processing.
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
from sqlalchemy import select

from app.db_async import get_db
from app.models.order_async import Order, OrderItem
from app.utils.helpers_async import commit_with_retry_async, log_info_async
# Use async versions of order utilities for FastAPI routes
from app.utils.order_utils_async import build_order_description_async, calculate_bill_amount_async
# Import from async deliverect module for FastAPI routes
from app.utils.deliverect_async import build_deliverect_order, send_order_to_deliverect_async, generate_order_id
# Removed hardcoded agent_utils - using AI orchestrator instead

# Configure logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# =====================
# Pydantic Models
# =====================

class ConfirmationRequest(BaseModel):
    """Base model for order confirmation requests"""
    order_id: Optional[str] = Field(None, description="Order ID to confirm")
    session_id: Optional[str] = Field(None, description="Session ID for retrieving cart from session")
    speech_result: Optional[str] = Field(None, description="The transcribed speech from Twilio")
    dtmf_digits: Optional[str] = Field(None, description="DTMF digits entered by user")
    
    @validator('order_id', 'session_id')
    def validate_identifiers(cls, v):
        """Validate that at least one identifier is provided"""
        # Allow None values but check later that at least one identifier is provided
        return v

class OrderConfirmationResponse(BaseModel):
    """Response model for order confirmation"""
    confirmed: bool = Field(..., description="Whether the order was confirmed")
    order_id: Optional[str] = Field(None, description="The ID of the confirmed order")
    message: str = Field(..., description="Message to be spoken to the user")
    redirect_to: Optional[str] = Field(None, description="Endpoint to redirect to")
    total_price: Optional[float] = Field(None, description="Total price of the order")
    deliverect_order_id: Optional[str] = Field(None, description="Deliverect order ID if submitted")

class ModifiedConfirmationRequest(ConfirmationRequest):
    """Model for confirming an order after modification"""
    modified_items: Optional[List[dict]] = Field(None, description="Modified order items")

# =====================
# Helper Functions
# =====================

async def user_confirmed(speech_result: str, dtmf_digits: str) -> bool:
    """
    Determine if the user confirmed the order based on speech or DTMF input.
    
    Args:
        speech_result: The transcribed speech from the user
        dtmf_digits: DTMF digits entered by the user
        
    Returns:
        True if confirmed, False if denied or unclear
    """
    # Check DTMF first (more reliable)
    if dtmf_digits:
        return dtmf_digits == "1"  # 1 for yes, 2 for no
    
    # Check speech
    if not speech_result:
        return False
    
    speech_lower = speech_result.lower()
    
    # Look for clear affirmative phrases
    affirmative = [
        "yes", "yeah", "yep", "correct", "right", "confirm", "confirmed",
        "that's right", "that's correct", "looks good", "sounds good",
        "approve", "good", "perfect", "okay", "ok", "sure", "absolutely"
    ]
    
    # Check for affirmative phrases
    for phrase in affirmative:
        if phrase in speech_lower:
            return True
    
    # If we didn't find an affirmative, check for negatives
    negative = [
        "no", "nope", "not", "incorrect", "wrong", "don't", "do not",
        "cancel", "change", "modify", "different", "wait", "stop"
    ]
    
    # Check for negative phrases
    for phrase in negative:
        if phrase in speech_lower:
            return False
    
    # If neither clear yes nor clear no, default to asking again
    return False

async def retrieve_order_details(db: AsyncSession, order_id: str) -> Optional[Dict]:
    """
    Retrieve order details from the database.
    
    Args:
        db: Database session
        order_id: Order ID to retrieve
        
    Returns:
        Dictionary with order details or None if not found
    """
    try:
        # Query the order
        result = await db.execute(
            select(Order).where(Order.id == order_id)
        )
        order = result.scalars().first()
        
        if not order:
            logger.warning(f"Order not found: {order_id}")
            return None
        
        # Query order items
        result = await db.execute(
            select(OrderItem).where(OrderItem.order_id == order_id)
        )
        items = result.scalars().all()
        
        # Convert items to a standard format
        order_items = []
        for item in items:
            order_items.append({
                "name": item.name,
                "price": item.price,
                "quantity": item.quantity,
                "reference_handler": item.menu_item_plu,
                "notes": item.note
            })
        
        return {
            "id": order.id,
            "customer_name": order.customer_name,
            "customer_phone": order.customer_phone,
            "order_type": order.order_type,
            "status": order.status,
            "total_price": order.total_price,
            "items": order_items,
            "delivery_address": order.delivery_address
        }
    except Exception as e:
        logger.error(f"Error retrieving order details: {e}")
        return None

async def submit_order_to_deliverect(db: AsyncSession, order_details: Dict) -> Dict:
    """
    Submit the order to Deliverect.
    
    Args:
        db: Database session
        order_details: Order details dictionary
        
    Returns:
        Dictionary with submission result
    """
    try:
        # Build Deliverect payload
        deliverect_payload = build_deliverect_order(
            order_items=order_details["items"],
            customer_name=order_details["customer_name"],
            customer_phone=order_details["customer_phone"],
            order_type=order_details["order_type"],
            delivery_address=order_details.get("delivery_address"),
            channel_order_id=order_details["id"]
        )
        
        # Send to Deliverect
        deliverect_response = await send_order_to_deliverect(deliverect_payload)
        
        # Get Deliverect order ID
        deliverect_order_id = deliverect_response.get("id")
        
        if not deliverect_order_id:
            logger.error(f"Deliverect order creation failed: {deliverect_response}")
            return {
                "success": False,
                "error": "Failed to create order in restaurant system"
            }
        
        # Update order status in database
        order_id = order_details["id"]
        result = await db.execute(
            select(Order).where(Order.id == order_id)
        )
        order = result.scalars().first()
        
        if order:
            order.deliverect_channel_order_id = deliverect_order_id
            order.status = 20  # 20 = accepted
            order.updated_at = datetime.now()
            await commit_with_retry_async(db)
            logger.info(f"Order {order_id} submitted to Deliverect with ID {deliverect_order_id}")
        
        return {
            "success": True,
            "deliverect_order_id": deliverect_order_id
        }
        
    except Exception as e:
        logger.error(f"Error submitting order to Deliverect: {e}")
        return {
            "success": False,
            "error": str(e)
        }

# =====================
# API Routes
# =====================

@router.post("/confirm_initial_order", response_model=OrderConfirmationResponse)
async def confirm_initial_order(
    request: ConfirmationRequest,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Handle order confirmation after initial order has been placed.
    
    This endpoint processes the user's confirmation of their order
    and submits it to the restaurant system if confirmed.
    """
    # Ensure we have a way to identify the order
    if not request.order_id and not request.session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either order_id or session_id must be provided"
        )
    
    # Check if the user confirmed the order
    confirmed = await user_confirmed(
        speech_result=request.speech_result or "",
        dtmf_digits=request.dtmf_digits or ""
    )
    
    if not confirmed:
        return {
            "confirmed": False,
            "message": "I understand you want to make changes to your order. Let me know what you'd like to change.",
            "redirect_to": "/new_modify_order"
        }
    
    # Get order details
    order_details = None
    if request.order_id:
        order_details = await retrieve_order_details(db, request.order_id)
    
    if not order_details:
        return {
            "confirmed": False,
            "message": "I'm sorry, I couldn't find your order details. Let's start again with a new order.",
            "redirect_to": "/take_order"
        }
    
    # Submit order to Deliverect
    submission_result = await submit_order_to_deliverect(db, order_details)
    
    if not submission_result.get("success", False):
        return {
            "confirmed": False,
            "order_id": order_details["id"],
            "message": f"I'm sorry, we encountered an issue submitting your order. Please try again or speak with our staff for assistance.",
            "redirect_to": "/order_submission_error"
        }
    
    # Build order description for the message
    order_description = build_order_description(order_details["items"])
    
    # Return success response
    return {
        "confirmed": True,
        "order_id": order_details["id"],
        "message": f"Thank you! Your order has been confirmed and sent to our kitchen. {order_description}. Your total is ${order_details['total_price']:.2f}. We'll start preparing your order right away.",
        "redirect_to": "/order_complete",
        "total_price": order_details["total_price"],
        "deliverect_order_id": submission_result.get("deliverect_order_id")
    }

@router.post("/confirm_modified_order", response_model=OrderConfirmationResponse)
async def confirm_modified_order(
    request: ModifiedConfirmationRequest,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Handle confirmation after order modifications.
    
    This endpoint processes the user's confirmation of their modified order
    and updates the order in the system.
    """
    # Check if the user confirmed the order
    confirmed = await user_confirmed(
        speech_result=request.speech_result or "",
        dtmf_digits=request.dtmf_digits or ""
    )
    
    if not confirmed:
        return {
            "confirmed": False,
            "message": "I understand you want to make more changes to your order. Let me know what else you'd like to change.",
            "redirect_to": "/new_modify_order"
        }
    
    # Get order details
    order_details = None
    if request.order_id:
        order_details = await retrieve_order_details(db, request.order_id)
    
    if not order_details:
        return {
            "confirmed": False,
            "message": "I'm sorry, I couldn't find your order details. Let's start again with a new order.",
            "redirect_to": "/take_order"
        }
    
    # If modified items are provided, update the order
    if request.modified_items:
        # Calculate bill amount
        calculate_bill_amount(request.modified_items)
        total_price = sum(item.get("price", 0) * item.get("quantity", 1) for item in request.modified_items)
        
        # Update order items
        try:
            # First, remove existing items
            result = await db.execute(
                select(OrderItem).where(OrderItem.order_id == request.order_id)
            )
            existing_items = result.scalars().all()
            
            for item in existing_items:
                await db.delete(item)
            
            # Add the modified items
            for item_data in request.modified_items:
                item = OrderItem(
                    id=str(uuid.uuid4()),
                    order_id=request.order_id,
                    menu_item_plu=item_data.get("reference_handler", ""),
                    name=item_data.get("name", ""),
                    quantity=item_data.get("quantity", 1),
                    price=item_data.get("price", 0.0),
                    note=item_data.get("notes", "")
                )
                db.add(item)
            
            # Update the order total
            result = await db.execute(
                select(Order).where(Order.id == request.order_id)
            )
            order = result.scalars().first()
            
            if order:
                order.total_price = total_price
                order.updated_at = datetime.now()
            
            await commit_with_retry_async(db)
            logger.info(f"Order {request.order_id} updated with modified items")
            
            # Use the modified items for the order details
            order_details["items"] = request.modified_items
            order_details["total_price"] = total_price
            
        except Exception as e:
            logger.error(f"Error updating order with modified items: {e}")
            return {
                "confirmed": False,
                "order_id": request.order_id,
                "message": f"I'm sorry, we encountered an issue updating your order. Please try again or speak with our staff for assistance.",
                "redirect_to": "/order_update_error"
            }
    
    # Submit updated order to Deliverect
    submission_result = await submit_order_to_deliverect(db, order_details)
    
    if not submission_result.get("success", False):
        return {
            "confirmed": False,
            "order_id": order_details["id"],
            "message": f"I'm sorry, we encountered an issue submitting your order. Please try again or speak with our staff for assistance.",
            "redirect_to": "/order_submission_error"
        }
    
    # Build order description for the message
    order_description = build_order_description(order_details["items"])
    
    # Return success response
    return {
        "confirmed": True,
        "order_id": order_details["id"],
        "message": f"Great! Your updated order has been confirmed and sent to our kitchen. {order_description}. Your new total is ${order_details['total_price']:.2f}. We'll start preparing your order right away.",
        "redirect_to": "/order_complete",
        "total_price": order_details["total_price"],
        "deliverect_order_id": submission_result.get("deliverect_order_id")
    }