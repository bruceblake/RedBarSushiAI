"""
Contact handling API routes for RedBarSushiAI FastAPI application.

This module provides API endpoints for handling customer contact information and callbacks.
"""

import logging
import re # Added import for re
# import uuid # Removed
# from datetime import datetime # Removed
from typing import Optional

from fastapi import APIRouter

# JSONResponse removed
from pydantic import BaseModel, Field, validator


# Configure logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# =====================
# Pydantic Models
# =====================


class ContactRequestBase(BaseModel):
    """Base model for contact requests"""

    speech_result: str = Field(..., description="The transcribed speech from Twilio")
    call_sid: Optional[str] = Field(None, description="The Twilio call SID")
    caller_number: Optional[str] = Field(None, description="The caller's phone number")


class CallbackRequest(ContactRequestBase):
    """Request model for callback requests"""

    pass


class MenuNotificationRequest(ContactRequestBase):
    """Request model for menu notification requests"""

    pass


class ContactResponse(BaseModel):
    """Response model for contact requests"""

    message: str = Field(..., description="The message to be spoken to the user")
    success: bool = Field(
        ..., description="Whether the contact request was saved successfully"
    )
    extracted_name: Optional[str] = Field(None, description="The extracted name")
    extracted_phone: Optional[str] = Field(
        None, description="The extracted phone number"
    )
    request_id: Optional[str] = Field(
        None, description="The ID of the created contact request"
    )

    @validator("extracted_phone")
    def validate_phone(cls, v):
        """Validate phone number format"""
        if v and not re.match(r"^\d{10}$", v) and not re.match(r"^\+\d{11,15}$", v):
            return None  # Return None if invalid format
        return v


# =====================
# Helper Functions
# =====================

# Functions extract_contact_info and save_contact_request_to_db
# were here. They are removed as they were only used by the Vulture-flagged
# save_callback_request and save_contact_info endpoint functions.

# =====================
# API Routes
# =====================

# Functions save_callback_request and save_contact_info were here,
# but removed as they were flagged as unused by Vulture.
