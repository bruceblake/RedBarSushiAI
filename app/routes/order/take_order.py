"""
Order taking routes for RedBarSushiAI.
This module provides the routes for initial order taking and processing.
"""

import json
import logging
from flask import request, session, Response
from twilio.twiml.voice_response import VoiceResponse

from app.routes.order import order_bp
from app.utils.menu_utils_db import load_menu_data
from app.utils.agent_utils import analyze_user_input, OrderParsingAgent
from app.utils.order_utils import build_order_description, calculate_bill_amount, mark_unavailable_items

# Busy mode flag - can be toggled through the admin interface
BUSY_MODE_ACTIVE = False

# Configure logger
logger = logging.getLogger(__name__)

def check_for_missing_modifiers(order_items):
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

def custom_suggest_modifiers(item_name):
    """
    Generate custom modifier suggestions for an item.
    
    Args:
        item_name: Name of the item to suggest modifiers for
        
    Returns:
        String with the suggestions
    """
    agent = OrderParsingAgent()
    return agent.menu_tool.generate_modifier_prompt(item_name)

@order_bp.route("/take_order", methods=["POST"])
def take_order():
    """Process a new order request from voice"""
    # Check if we're in busy mode
    if BUSY_MODE_ACTIVE:
        response = VoiceResponse()
        # Instead of hanging up, offer options when busy
        response.say("We're currently busy and not accepting new orders right now.")

        # Gather input to let them choose an option
        with response.gather(
            input="speech dtmf",
            action="/handle_busy_options",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=5,
            timeout=7,
            num_digits=1,
        ) as g:
            g.say(
                "Press 1 to get menu information, press 2 to leave your name and number for a callback, or press 3 to end the call."
            )

        # If they don't input anything, repeat the options
        response.redirect("/handle_busy_options")
        return Response(str(response), mimetype="text/xml")

    # Load menu and check availability - force refresh to ensure we have latest data
    try:
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

        # If still no items, use an empty menu structure
        if not available_items:
            logger.warning("No available items found - creating empty menu structure")
            # Create an empty menu structure instead of default menu
            menu_data = {
                "items": [],
                "modifiers": [],
                "modifierGroups": [],
            }

            # Get available items from menu structure (will be empty)
            available_items = [
                item
                for item in menu_data.get("items", [])
                if item.get("name") and item.get("snoozed", False) is False
            ]
            logger.info(f"Using default menu with {len(available_items)} items")

        # Final check - if still no items, report menu unavailable
        if not available_items:
            response = VoiceResponse()
            response.say("I'm sorry, our menu is currently unavailable.")

            # Instead of hanging up, offer some alternatives
            with response.gather(
                input="speech dtmf",
                action="/handle_menu_unavailable",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout=5,
                timeout=7,
                num_digits=1,
            ) as g:
                g.say(
                    "Press 1 to speak with a team member about our daily specials, press 2 to leave your contact information for when our menu is back online, or press 3 to end the call."
                )

            # If they don't input anything, redirect to the handler
            response.redirect("/handle_menu_unavailable")
            return Response(str(response), mimetype="text/xml")

    except Exception as e:
        logger.error(f"Error loading menu: {e}")
        response = VoiceResponse()
        response.say("I'm sorry, we're experiencing technical difficulties.")

        # Instead of hanging up, give them options
        with response.gather(
            input="speech dtmf",
            action="/handle_technical_difficulties",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=5,
            timeout=7,
            num_digits=1,
        ) as g:
            g.say(
                "Press 1 to speak with a team member who can take your order manually, press 2 to leave your contact information for a callback, or press 3 to end the call."
            )

        # Fallback if no input received
        response.redirect("/handle_technical_difficulties")
        return Response(str(response), mimetype="text/xml")

    # Get the user's speech
    user_resp = request.form.get("SpeechResult", "").strip()

    # Check if the user was silent or speech wasn't captured
    if not user_resp:
        # Track silence retries for this specific part of the flow
        order_silence_retry = session.get("order_silence_retry", 0)
        session["order_silence_retry"] = order_silence_retry + 1

        response = VoiceResponse()

        # Change the message based on how many retries
        if order_silence_retry >= 3:
            # After too many attempts, go to fallback automatically
            logger.info("Too many silence retries in order taking, sending to fallback")
            response.redirect("/main_menu_fallback")
            return Response(str(response), mimetype="text/xml")
        elif order_silence_retry >= 1:
            # After first or second retry, provide more guidance and DTMF options
            with response.gather(
                input="speech dtmf",
                action="/take_order",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout=8,  # Shortened timeout but still longer than initial
                timeout=10,  # Shortened but still longer than initial
                hints="california roll, spicy tuna roll, dragon roll, menu",  # Help Twilio recognize common items
            ) as g:
                g.say(
                    "I'm having trouble hearing you. Speak clearly and tell me what sushi items you'd like to order. For example, say 'two California rolls and one spicy tuna roll'. Or press any key to return to the main menu."
                )

            # If we still don't get anything after the gather, go to fallback
            response.redirect("/main_menu_fallback")
        else:
            # Normal or first retry prompt
            with response.gather(
                input="speech",
                action="/take_order",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout=5,  # Reduced timeout for better responsiveness
                timeout=7,  # Still give time to think but reduce waiting
            ) as g:
                g.say(
                    "I'm waiting for your order. Please tell me what sushi items you'd like to order. For example, you can say 'I'd like two California rolls and one spicy tuna roll'."
                )

            # Make sure we have a fallback if gather doesn't catch anything
            response.redirect("/take_order")
        return Response(str(response), mimetype="text/xml")

    # Use the agent to analyze the order
    analysis = analyze_user_input(user_resp)
    intent = analysis.get("intent", "other")

    # Build the voice response
    response = VoiceResponse()

    # If we couldn't understand the order, ask again
    if intent != "order_food" or not analysis.get("menu_items"):
        # Track understanding retries separately from silence
        understand_retry = session.get("understand_retry", 0)
        session["understand_retry"] = understand_retry + 1

        # Reset silence counter since we got some speech
        session["order_silence_retry"] = 0

        # Change approach based on retry count
        if understand_retry >= 2:
            # After multiple failed attempts, offer more options
            with response.gather(
                input="speech dtmf",
                action="/understanding_fallback",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout=5,  # Fixed timeout instead of "auto" for more consistency
                num_digits=1,
                timeout=7,  # Adjusted for better responsiveness
            ) as g:
                g.say(
                    "I'm having trouble understanding your order. You can try again by speaking clearly, press 1 to hear our popular menu items, or press 2 to return to the main menu."
                )
        else:
            # First retry with better guidance
            with response.gather(
                input="speech",
                action="/take_order",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout=5,  # Fixed timeout for better responsiveness
                timeout=7,  # Reduced waiting time
            ) as g:
                g.say(
                    "I'm sorry, I couldn't understand your order. Please tell me again what items you'd like to order from our menu. For example, you can say 'I'd like a California roll and a spicy tuna roll'."
                )
        return Response(str(response), mimetype="text/xml")

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
    available_items, unavailable_items = mark_unavailable_items(order_items)

    # Handle case where all items are unavailable
    if not available_items and unavailable_items:
        unavailable_names = [
            item.get("name").split(" (")[0] for item in unavailable_items
        ]
        unavailable_text = ", ".join(unavailable_names)

        response.say(
            f"I'm sorry, the item(s) you requested ({unavailable_text}) are currently unavailable. Would you like to order something else?"
        )
        # Gather a new response instead of hanging up
        with response.gather(
            input="speech",
            action="/take_order",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto",
        ) as g:
            g.say("Please tell me what else you would like to order.")
        return Response(str(response), mimetype="text/xml")

    # Include both available and unavailable items in the order
    # (unavailable items will be shown separately in the order description)
    order_items = available_items + unavailable_items

    # Check if any items need modifier suggestions
    # Before proceeding to order confirmation, check if we should suggest modifiers
    items_needing_modifiers, constraint_details = check_for_missing_modifiers(
        available_items
    )

    # Store constraint details in session for use in the modifier suggestion flow
    session["constraint_details"] = json.dumps(constraint_details)

    if items_needing_modifiers:
        # Store current order in session for the modifier suggestion flow
        session["order_items_without_modifiers_json"] = json.dumps(order_items)

        # Get the first item that needs modifiers
        item_to_modify = items_needing_modifiers[0]
        item_name = item_to_modify.get("name", "")

        # Store which item we're currently suggesting modifiers for
        session["current_modifier_item"] = item_name
        session["remaining_modifier_items"] = (
            json.dumps(items_needing_modifiers[1:])
            if len(items_needing_modifiers) > 1
            else "[]"
        )

        # Get modifier suggestions using the agent
        agent = OrderParsingAgent()
        modifier_prompt = agent.menu_tool.generate_modifier_prompt(item_name)

        # If we have a good prompt, ask the customer
        if modifier_prompt:
            logger.info(f"Suggesting modifiers for {item_name}: {modifier_prompt}")
            with response.gather(
                input="speech dtmf",
                action="/handle_modifier_suggestion",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout=5,
                timeout=7,
                num_digits=1,
            ) as g:
                g.say(modifier_prompt)
            return Response(str(response), mimetype="text/xml")

    # If no items need modifiers, or we couldn't generate a prompt, continue with standard flow
    # Calculate total and prepare confirmation
    calculate_bill_amount(order_items)
    order_description = build_order_description(order_items)
    session["bill_amount"] = int(session.get("total_price", 0) * 100)
    session["order_items_json"] = json.dumps(order_items)
    session["order_message"] = (
        f"{order_description}\nYour total is ${session.get('total_price', 0):.2f}."
    )

    # Ask for confirmation
    with response.gather(
        input="speech dtmf",
        action="/confirm_order_from_initial",
        enhanced=True,
        speech_model="phone_call",
        language="en-US",
        speech_timeout=5,
        timeout=7,
        num_digits=1,
    ) as g:
        g.say(
            session["order_message"]
            + " If correct, say yes or press 1. If you need changes, say no or press 2."
        )

    return Response(str(response), mimetype="text/xml")

# Export all functions
__all__ = ['take_order', 'check_for_missing_modifiers', 'custom_suggest_modifiers']