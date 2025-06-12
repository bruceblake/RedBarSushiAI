"""
Order checkout API routes for RedBarSushiAI FastAPI application.

This module provides API endpoints for order checkout and final processing.
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter

# JSONResponse removed
from pydantic import BaseModel, validator


# Use async versions of order utilities for FastAPI routes

# Import from async deliverect module for FastAPI routes

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

    @validator("order_type")
    def validate_order_type(cls, v):
        """Validate order type"""
        if v not in ["pickup", "delivery"]:
            raise ValueError("Order type must be either 'pickup' or 'delivery'")
        return v

    @validator("delivery_address")
    def validate_delivery_address(cls, v, values):
        """Validate delivery address"""
        if values.get("order_type") == "delivery" and not v:
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

# The 'checkout' function was here, but removed as it was flagged as unused by Vulture.
