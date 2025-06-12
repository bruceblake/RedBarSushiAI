"""
Order confirmation API routes for RedBarSushiAI FastAPI application.

This module provides API endpoints for order confirmation and processing.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter

# JSONResponse removed
from pydantic import BaseModel, Field, validator


# Use async versions of order utilities for FastAPI routes

# Import from async deliverect module for FastAPI routes

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
    session_id: Optional[str] = Field(
        None, description="Session ID for retrieving cart from session"
    )
    speech_result: Optional[str] = Field(
        None, description="The transcribed speech from Twilio"
    )
    dtmf_digits: Optional[str] = Field(None, description="DTMF digits entered by user")

    @validator("order_id", "session_id")
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
    deliverect_order_id: Optional[str] = Field(
        None, description="Deliverect order ID if submitted"
    )


class ModifiedConfirmationRequest(ConfirmationRequest):
    """Model for confirming an order after modification"""

    modified_items: Optional[List[dict]] = Field(
        None, description="Modified order items"
    )


# =====================
# Helper Functions
# =====================

# Functions user_confirmed, retrieve_order_details, submit_order_to_deliverect
# were here. They are removed as they were only used by the Vulture-flagged
# confirm_initial_order and confirm_modified_order endpoint functions.

# =====================
# API Routes
# =====================

# Functions confirm_initial_order and confirm_modified_order were here,
# but removed as they were flagged as unused by Vulture.
