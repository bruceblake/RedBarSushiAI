"""
Order taking API routes for RedBarSushiAI FastAPI application.

This module provides API endpoints for initial order taking and processing.
"""

import logging
from typing import List, Optional
from datetime import datetime

from fastapi import (
    APIRouter,
)  # Response removed

# JSONResponse removed
from pydantic import BaseModel, Field

# from app.models.order_async import OrderItem # Removed unused import
# commit_with_retry_async, log_info_async removed
# from app.utils.agent_utils import OrderParsingAgent  # TODO: Create async version if needed
# NOTE: Temporarily disabled - using async agents instead

# Configure logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Busy mode flag - can be toggled through the admin interface
BUSY_MODE_ACTIVE = False

# =====================
# Pydantic Models
# =====================


class ModifierDetails(BaseModel):
    """Model for modifier details"""

    name: str
    reference_handler: Optional[str] = None
    price_change: float = 0.0
    quantity: int = 1


class OrderItem(BaseModel):
    """Model for an item in an order"""

    name: str
    reference_handler: Optional[str] = None
    price: float = 0.0
    quantity: int = 1
    modifier: Optional[List[ModifierDetails]] = None
    notes: Optional[str] = None


class OrderRequest(BaseModel):
    """Request model for creating an order"""

    customer_phone: str
    customer_name: Optional[str] = None
    items: List[OrderItem]
    order_type: str = "pickup"
    delivery_address: Optional[str] = None


class OrderResponse(BaseModel):
    """Response model for order creation"""

    order_id: str
    total_price: float
    order_description: str
    status: str
    estimated_time: Optional[datetime] = None


# OrderResponse class removed.


class VoiceOrderRequest(BaseModel):
    """Request model for voice order creation"""

    speech_result: str = Field(..., description="The transcribed speech from Twilio")
    call_sid: Optional[str] = Field(None, description="The Twilio call SID")
    caller: Optional[str] = Field(None, description="The caller's phone number")


class VoiceOrderResponse(BaseModel):
    """Response model for voice order creation"""

    message: str = Field(..., description="The message to be spoken to the user")
    redirect_to: Optional[str] = Field(None, description="The endpoint to redirect to")
    order_items: Optional[List[dict]] = Field(
        None, description="The parsed order items"
    )
    needs_modifiers: Optional[bool] = Field(
        None, description="Whether modifiers are needed"
    )
    busy_mode: Optional[bool] = Field(
        None, description="Whether the system is in busy mode"
    )


class ConstraintDetails(BaseModel):
    """Model for modifier constraint details"""

    needs_modifiers: bool = False
    min_selection: Optional[int] = None
    max_selection: Optional[int] = None
    available_modifiers: Optional[List[str]] = None
    prompt: Optional[str] = None


# ConstraintDetails class removed.

# =====================
# Helper Functions
# =====================

# Function check_for_missing_modifiers was here, removed as unused.
# Function custom_suggest_modifiers was here (or intended to be), removed as unused.

# =====================
# API Routes
# =====================

# Function take_order was here, removed as unused.
# Function suggest_modifiers was here, removed as unused.
