"""
Order modification API routes for RedBarSushiAI FastAPI application.

This module provides API endpoints for modifying orders.
"""

import json
import logging
from typing import Dict, Any, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_async import get_db
from app.models.order_async import Order
from app.utils.helpers_async import commit_with_retry_async, log_info_async
# Removed hardcoded agent_utils - using AI orchestrator instead
# Use async versions of order utilities for FastAPI routes
from app.utils.order_utils_async import (
    build_order_description_async,
    calculate_bill_amount_async, 
    validate_modifiers_async, 
    mark_unavailable_items_async
)

# Configure logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# =====================
# Pydantic Models
# =====================

class ModificationRequest(BaseModel):
    """Request model for order modification"""
    speech_result: str = Field(..., description="The transcribed speech from Twilio")
    call_sid: Optional[str] = Field(None, description="The Twilio call SID")
    silence_retry: Optional[int] = Field(0, description="The number of silence retries")

class ModificationResponse(BaseModel):
    """Response model for order modification"""
    message: str = Field(..., description="The message to be spoken to the user")
    redirect_to: Optional[str] = Field(None, description="The endpoint to redirect to")
    updated_order_items: Optional[List[dict]] = Field(None, description="The updated order items")
    modifications_applied: Optional[bool] = Field(None, description="Whether modifications were applied")
    
# =====================
# API Routes
# =====================

@router.post("/modify_order", response_model=ModificationResponse)
async def modify_order(
    request: ModificationRequest,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Process order modifications from the user.
    
    This endpoint handles requests to modify an existing order.
    """
    # Get the speech result from the request
    user_resp = request.speech_result.strip()
    
    # Handle silence (no speech)
    if not user_resp:
        # Use the provided silence retry count or default to 0
        silence_retry = request.silence_retry
        
        # If too many retries, redirect to fallback
        if silence_retry >= 2:
            logger.info("Multiple silence retries in modify, sending to fallback")
            return {
                "message": "I'm having trouble hearing your modifications. Let me connect you with a team member who can help.",
                "redirect_to": "/modification_silence_fallback"
            }
        
        # First retry with better instructions
        return {
            "message": "I'm sorry, I didn't hear any modifications. Please tell me what changes you'd like to make to your order. For example, you can say 'remove the spicy tuna roll' or 'change the quantity of California rolls to two'.",
            "redirect_to": "/new_modify_order",
            "modifications_applied": False
        }
    
    # Check if we have order items in the request context
    # In a real implementation, this would come from a database or state manager
    # For now, we'll simulate it with a placeholder
    order_items = []  # This would be retrieved from the database or session storage
    
    if not order_items:
        return {
            "message": "I'm sorry, I couldn't find your order details. Let's start again with a new order.",
            "redirect_to": "/take_order",
            "modifications_applied": False
        }
    
    # Parse the modification request using AI orchestrator
    try:
        from app.utils.agent_orchestration_async import async_agent_orchestrator
        
        # Initialize orchestrator with database session
        await async_agent_orchestrator.initialize(db=db)
        
        # Process the modification request using AI
        response = await async_agent_orchestrator.process_voice_input(
            call_sid,
            user_resp,
            {
                "session_id": call_sid,
                "modification_mode": True,
                "existing_order": order_items
            }
        )
        
        # Check if modifications were successful
        modifications = response.get("actions", [])
        modifications_applied = any(action.get("type") == "cart_updated" for action in modifications)
        
        if not modifications_applied:
            return {
                "message": "I'm sorry, I couldn't understand the modifications you want to make. Could you please try again with specific changes? For example, 'remove the California roll' or 'add one more spicy tuna roll'.",
                "redirect_to": "/new_modify_order",
                "modifications_applied": False
            }
        
        # Apply the modifications to the order
        updated_order = agent.apply_modifications(order_items, modifications)
        
        if not updated_order:
            return {
                "message": "I'm sorry, I couldn't apply your modifications. Could you please try again with different changes?",
                "redirect_to": "/new_modify_order",
                "modifications_applied": False
            }
        
        # Process and mark any unavailable items
        available_items, unavailable_items = await mark_unavailable_items_async(db, updated_order)
        
        # Handle case where all items are unavailable
        if not available_items and unavailable_items:
            unavailable_text = ", ".join(unavailable_items)
            
            return {
                "message": f"I'm sorry, the item(s) you requested ({unavailable_text}) are currently unavailable. Please make a different modification.",
                "redirect_to": "/new_modify_order",
                "modifications_applied": False
            }
        
        # Include both available and unavailable items
        updated_order = available_items
        
        # Validate modifiers
        is_valid, error_messages = await validate_modifiers_async(db, updated_order)
        
        if not is_valid:
            error_msg = "; ".join(error_messages)
            return {
                "message": f"There's an issue with your order: {error_msg}. Please make a different modification.",
                "redirect_to": "/new_modify_order",
                "modifications_applied": False
            }
        
        # Calculate bill amount
        total_price = await calculate_bill_amount_async(updated_order)
        
        # Build order description
        order_description = await build_order_description_async(updated_order)
        total_price = sum(item.get("price", 0) * item.get("quantity", 1) for item in updated_order)
        
        # Return the updated order for confirmation
        return {
            "message": f"I've updated your order. {order_description}. Your new total is ${total_price:.2f}. Is this correct?",
            "redirect_to": "/confirm_modified_order",
            "updated_order_items": updated_order,
            "modifications_applied": True
        }
        
    except Exception as e:
        logger.error(f"Error processing order modification: {e}")
        return {
            "message": "I'm sorry, I encountered an error while trying to modify your order. Let's try again. What changes would you like to make?",
            "redirect_to": "/new_modify_order",
            "modifications_applied": False
        }