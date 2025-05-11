"""
Contact handling API routes for RedBarSushiAI FastAPI application.

This module provides API endpoints for handling customer contact information and callbacks.
"""

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_async import get_db
from app.models.order_async import ContactRequest  # We need to create this
from app.utils.helpers_async import commit_with_retry_async, log_info_async

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
    success: bool = Field(..., description="Whether the contact request was saved successfully")
    extracted_name: Optional[str] = Field(None, description="The extracted name")
    extracted_phone: Optional[str] = Field(None, description="The extracted phone number")
    request_id: Optional[str] = Field(None, description="The ID of the created contact request")

    @validator('extracted_phone')
    def validate_phone(cls, v):
        """Validate phone number format"""
        if v and not re.match(r'^\d{10}$', v) and not re.match(r'^\+\d{11,15}$', v):
            return None  # Return None if invalid format
        return v

# =====================
# Helper Functions
# =====================

async def extract_contact_info(user_resp: str, caller_number: str) -> tuple:
    """
    Extract name and phone number from user response.
    
    Args:
        user_resp: The user's speech response
        caller_number: The caller's phone number
        
    Returns:
        Tuple of (name, phone_number)
    """
    name = ""
    phone_number = ""
    
    # Try to extract a phone number using regex
    phone_pattern = re.compile(r'(\d{3}[-\.\s]??\d{3}[-\.\s]??\d{4}|\(\d{3}\)\s*\d{3}[-\.\s]??\d{4}|\d{10})')
    phone_matches = phone_pattern.findall(user_resp)
    
    if phone_matches:
        # Use the first match
        phone_match = phone_matches[0]
        phone_number = re.sub(r'[^0-9]', '', phone_match)
        
        # Remove the phone number from the response to extract the name
        name_text = user_resp.replace(phone_match, "").strip()
    else:
        # No phone number found, treat the whole response as the name
        name_text = user_resp
        
        # Use the caller's number as fallback
        if caller_number and caller_number.startswith("+"):
            phone_number = caller_number[1:]  # Remove the + prefix
    
    # Use a simple heuristic to extract the name
    # Just take the first two words as the name if it's not too long
    name_parts = name_text.split()
    if len(name_parts) >= 2:
        name = " ".join(name_parts[:2])
    else:
        name = name_text
    
    return name, phone_number

async def save_contact_request_to_db(db: AsyncSession, name: str, phone_number: str, 
                           call_sid: str, request_type: str) -> Optional[str]:
    """
    Save a contact request to the database.
    
    Args:
        db: Database session
        name: Customer name
        phone_number: Customer phone number
        call_sid: Twilio call SID
        request_type: Type of request (callback, menu_notification)
        
    Returns:
        The ID of the created contact request or None if failed
    """
    try:
        # Create a new ContactRequest object
        contact_request = ContactRequest(
            id=str(uuid.uuid4()),
            customer_name=name,
            customer_phone=phone_number,
            call_sid=call_sid,
            request_type=request_type,
            created_at=datetime.now(),
            status="pending"
        )
        
        # Add to session and commit
        db.add(contact_request)
        await commit_with_retry_async(db)
        
        logger.info(f"Saved contact request ID: {contact_request.id}")
        return contact_request.id
    except Exception as e:
        logger.error(f"Failed to save contact request: {e}")
        return None

# =====================
# API Routes
# =====================

@router.post("/save_callback_request", response_model=ContactResponse)
async def save_callback_request(
    request: CallbackRequest,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Save customer callback request information.
    
    This endpoint processes a callback request from a customer, extracts their
    contact information, and stores it for follow-up.
    """
    # Get the user's speech
    user_resp = request.speech_result.strip()
    call_sid = request.call_sid or "unknown"
    caller_number = request.caller_number or "unknown"
    
    # Handle silence (no speech)
    if not user_resp:
        return {
            "message": "I didn't catch that. Please tell me your name and the best phone number to reach you.",
            "success": False,
            "extracted_name": None,
            "extracted_phone": None
        }
    
    # Extract name and phone number
    name, phone_number = await extract_contact_info(user_resp, caller_number)
    
    # Log the extracted information
    logger.info(f"Extracted callback info - Name: '{name}', Phone: '{phone_number}'")
    
    # Save to database
    request_id = await save_contact_request_to_db(
        db, name, phone_number, call_sid, "callback"
    )
    
    # Build the response
    success = request_id is not None
    return {
        "message": f"Thank you, {name}. We've received your callback request. A member of our team will call you back as soon as possible. Thank you for your patience.",
        "success": success,
        "extracted_name": name,
        "extracted_phone": phone_number,
        "request_id": request_id
    }

@router.post("/save_contact_info", response_model=ContactResponse)
async def save_contact_info(
    request: MenuNotificationRequest,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Save customer contact information for menu notifications.
    
    This endpoint processes a contact information request from a customer,
    extracts their contact details, and stores it for future menu notifications.
    """
    # Get the user's speech
    user_resp = request.speech_result.strip()
    call_sid = request.call_sid or "unknown"
    caller_number = request.caller_number or "unknown"
    
    # Handle silence (no speech)
    if not user_resp:
        return {
            "message": "I didn't catch that. Please tell me your name and the best phone number to reach you.",
            "success": False,
            "extracted_name": None,
            "extracted_phone": None
        }
    
    # Extract name and phone number
    name, phone_number = await extract_contact_info(user_resp, caller_number)
    
    # Log the extracted information
    logger.info(f"Extracted contact info - Name: '{name}', Phone: '{phone_number}'")
    
    # Save to database
    request_id = await save_contact_request_to_db(
        db, name, phone_number, call_sid, "menu_notification"
    )
    
    # Build the response
    success = request_id is not None
    return {
        "message": f"Thank you, {name}. We've saved your contact information. We'll notify you when our menu is back online. Thank you for your interest in Red Bar Sushi!",
        "success": success,
        "extracted_name": name,
        "extracted_phone": phone_number,
        "request_id": request_id
    }