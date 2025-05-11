"""
Order taking API routes for RedBarSushiAI FastAPI application.

This module provides API endpoints for initial order taking and processing.
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_async import get_db
from app.models.order_async import Order, OrderItem
from app.utils.helpers_async import commit_with_retry_async, log_info_async
from app.utils.menu_utils_db_async import load_menu_data  # Using async version
from app.utils.agent_utils import OrderParsingAgent  # TODO: Create async version if needed

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

class VoiceOrderRequest(BaseModel):
    """Request model for voice order creation"""
    speech_result: str = Field(..., description="The transcribed speech from Twilio")
    call_sid: Optional[str] = Field(None, description="The Twilio call SID")
    caller: Optional[str] = Field(None, description="The caller's phone number")

class VoiceOrderResponse(BaseModel):
    """Response model for voice order creation"""
    message: str = Field(..., description="The message to be spoken to the user")
    redirect_to: Optional[str] = Field(None, description="The endpoint to redirect to")
    order_items: Optional[List[dict]] = Field(None, description="The parsed order items")
    needs_modifiers: Optional[bool] = Field(None, description="Whether modifiers are needed")
    busy_mode: Optional[bool] = Field(None, description="Whether the system is in busy mode")

class ConstraintDetails(BaseModel):
    """Model for modifier constraint details"""
    needs_modifiers: bool = False
    min_selection: Optional[int] = None
    max_selection: Optional[int] = None
    available_modifiers: Optional[List[str]] = None
    prompt: Optional[str] = None

# =====================
# Helper Functions
# =====================

async def check_for_missing_modifiers(order_items: List[dict]) -> tuple:
    """
    Check if any items are missing required modifiers.
    
    Args:
        order_items: List of order items to check
    
    Returns:
        Tuple of (items_needing_modifiers, constraint_details)
    """
    items_needing_modifiers = []
    constraint_details = {}
    
    # Create an agent to help with menu operations
    agent = OrderParsingAgent()
    
    for item in order_items:
        item_name = item.get("name", "")
        
        # Skip items that already have modifiers
        if item.get("modifier") and len(item.get("modifier", [])) > 0:
            continue
            
        # Use the agent to check if this item needs modifiers
        modifier_details = agent.menu_tool.check_required_modifiers(item_name)
        
        if modifier_details.get("needs_modifiers", False):
            items_needing_modifiers.append(item)
            constraint_details[item_name] = modifier_details
    
    return items_needing_modifiers, constraint_details

async def custom_suggest_modifiers(item_name: str) -> str:
    """
    Generate custom modifier suggestions for an item.
    
    Args:
        item_name: Name of the item to suggest modifiers for
        
    Returns:
        String with the suggestions
    """
    agent = OrderParsingAgent()
    return agent.menu_tool.generate_modifier_prompt(item_name)

# =====================
# API Routes
# =====================

@router.post("/take_order", response_model=VoiceOrderResponse)
async def take_order(
    request: VoiceOrderRequest,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Process a new order request from voice.
    
    This endpoint handles the initial order request, including menu validation
    and checking for required modifiers.
    """
    # Check if we're in busy mode
    if BUSY_MODE_ACTIVE:
        return {
            "message": "We're currently busy and not accepting new orders right now. "
                      "Press 1 to get menu information, press 2 to leave your name and "
                      "number for a callback, or press 3 to end the call.",
            "redirect_to": "/handle_busy_options",
            "busy_mode": True
        }
    
    # Load menu and check availability - force refresh to ensure we have latest data
    try:
        # This should eventually be replaced with an async version
        menu_data = load_menu_data(force_refresh=True)

        # Debug logging to see if menu data is loaded correctly
        item_count = len(menu_data.get("items", []) or [])
        logger.info(f"Menu data loaded: {item_count} items found")

        # Check if any items have valid names
        valid_name_count = sum(
            1 for item in menu_data.get("items", []) if item.get("name")
        )
        if valid_name_count == 0 and item_count > 0:
            logger.error(f"Menu has {item_count} items but none have names!")
            # Create an empty menu structure instead of default menu
            menu_data = {
                "items": [],
                "modifiers": [],
                "modifierGroups": [],
                "name_variants": {},
            }
            logger.info("Using default menu instead")

        # Get available items - items with names and not snoozed
        available_items = [
            item
            for item in menu_data.get("items", [])
            if item.get("name")
            and item.get("snoozed", False) is False
            and item.get("available", True) is True
        ]

        logger.info(f"Available (not snoozed) items: {len(available_items)}")

        if not available_items:
            # Try to process the menu directly - it might be in Deliverect format
            from app.utils.menu_utils import process_deliverect_menu

            if "categories" in menu_data:
                logger.info("Attempting to process Deliverect format directly")
                try:
                    menu_data = process_deliverect_menu(menu_data)
                    # Try again with the processed data
                    available_items = [
                        item
                        for item in menu_data.get("items", [])
                        if item.get("name") and item.get("snoozed", False) is False
                    ]
                    logger.info(
                        f"After processing: {len(available_items)} available items"
                    )
                except Exception as e:
                    logger.error(f"Error processing Deliverect format: {e}")

        # If still no items, return appropriate message
        if not available_items:
            logger.warning("No available items found - menu unavailable")
            return {
                "message": "I'm sorry, our menu is currently unavailable. "
                          "Press 1 to speak with a team member about our daily specials, "
                          "press 2 to leave your contact information for when our menu is back online, "
                          "or press 3 to end the call.",
                "redirect_to": "/handle_menu_unavailable"
            }

    except Exception as e:
        logger.error(f"Error loading menu: {e}")
        return {
            "message": "I'm sorry, we're experiencing technical difficulties. "
                      "Press 1 to speak with a team member who can take your order manually, "
                      "press 2 to leave your contact information for a callback, "
                      "or press 3 to end the call.",
            "redirect_to": "/handle_technical_difficulties"
        }

    # Get the user's speech
    user_resp = request.speech_result.strip()
    
    # Check if the user was silent or speech wasn't captured
    if not user_resp:
        # In FastAPI, we would handle session data differently
        # For now, returning response with guidance
        return {
            "message": "I'm waiting for your order. Please tell me what sushi items "
                      "you'd like to order. For example, you can say 'I'd like two "
                      "California rolls and one spicy tuna roll'.",
            "redirect_to": "/take_order"
        }

    # Use the agent to analyze the order
    from app.utils.agent_utils import analyze_user_input
    analysis = analyze_user_input(user_resp)
    intent = analysis.get("intent", "other")

    # If we couldn't understand the order, ask again
    if intent != "order_food" or not analysis.get("menu_items"):
        return {
            "message": "I'm sorry, I couldn't understand your order. Please tell me again "
                      "what items you'd like to order from our menu. For example, you can "
                      "say 'I'd like a California roll and a spicy tuna roll'.",
            "redirect_to": "/take_order"
        }

    # Create an order parsing agent
    agent = OrderParsingAgent()

    menu_items = []
    # Parse the input
    logger.info(f"[ANALYZE-INPUT] Analyzing user input: '{user_resp}'")
    parsed_order = agent.parse_order(user_resp)
    logger.info(f"[PARSED-ORDER]: {parsed_order}")

    # If we found menu items, this is likely an order
    if parsed_order.get("items"):
        menu_items = parsed_order.get("items", [])
        intent = "order_food"
        logger.info(
            f"[ANALYZE-RESULT] Found {len(menu_items)} items, intent: 'order_food'"
        )

        # Ensure modifiers are preserved for each item
        for item in menu_items:
            if "modifier" in item and item["modifier"]:
                logger.info(
                    f"[ANALYZE-MODS] Item '{item.get('name')}' has {len(item['modifier'])} modifiers"
                )
                # Log each modifier for debugging
                for mod in item["modifier"]:
                    if isinstance(mod, dict):
                        logger.info(
                            f"[ANALYZE-MOD-DETAIL] Modifier for {item.get('name')}: {mod.get('name')} (ref: {mod.get('reference_handler', 'none')})"
                        )
                    else:
                        logger.warning(
                            f"[ANALYZE-MOD-ERROR] Invalid modifier format: {mod}"
                        )

    order_items = menu_items
    logger.info(f"order_items: {order_items}")
    
    # Process and mark any unavailable items
    from app.utils.order_utils import mark_unavailable_items
    available_items, unavailable_items = mark_unavailable_items(order_items)

    # Handle case where all items are unavailable
    if not available_items and unavailable_items:
        unavailable_names = [
            item.get("name").split(" (")[0] for item in unavailable_items
        ]
        unavailable_text = ", ".join(unavailable_names)

        return {
            "message": f"I'm sorry, the item(s) you requested ({unavailable_text}) are "
                     f"currently unavailable. Would you like to order something else? "
                     f"Please tell me what else you would like to order.",
            "redirect_to": "/take_order"
        }

    # Include both available and unavailable items in the order
    # (unavailable items will be shown separately in the order description)
    order_items = available_items + unavailable_items

    # Check if any items need modifier suggestions
    # Before proceeding to order confirmation, check if we should suggest modifiers
    items_needing_modifiers, constraint_details = await check_for_missing_modifiers(
        available_items
    )

    if items_needing_modifiers:
        # Get the first item that needs modifiers
        item_to_modify = items_needing_modifiers[0]
        item_name = item_to_modify.get("name", "")

        # Get modifier suggestions using the agent
        agent = OrderParsingAgent()
        modifier_prompt = agent.menu_tool.generate_modifier_prompt(item_name)

        # If we have a good prompt, ask the customer
        if modifier_prompt:
            logger.info(f"Suggesting modifiers for {item_name}: {modifier_prompt}")
            return {
                "message": modifier_prompt,
                "redirect_to": "/handle_modifier_suggestion",
                "order_items": order_items,
                "needs_modifiers": True,
                "constraint_details": constraint_details
            }

    # If no items need modifiers, or we couldn't generate a prompt, continue with standard flow
    # Calculate total and prepare confirmation
    from app.utils.order_utils import calculate_bill_amount, build_order_description
    calculate_bill_amount(order_items)
    order_description = build_order_description(order_items)
    total_price = sum(item.get("price", 0) * item.get("quantity", 1) for item in order_items)
    
    return {
        "message": f"{order_description}\nYour total is ${total_price:.2f}. "
                  f"If correct, say yes or press 1. If you need changes, say no or press 2.",
        "redirect_to": "/confirm_order_from_initial",
        "order_items": order_items
    }

@router.post("/suggest_modifiers", response_model=str)
async def suggest_modifiers(
    item_name: str,
    db: AsyncSession = Depends(get_db)
) -> str:
    """
    Generate modifier suggestions for an item.
    
    Args:
        item_name: Name of the item to suggest modifiers for
    
    Returns:
        String with modifier suggestions
    """
    agent = OrderParsingAgent()
    return agent.menu_tool.generate_modifier_prompt(item_name)