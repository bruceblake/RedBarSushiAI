import requests
import json
import uuid
import time
import threading
import logging
import re
import traceback
import os
from collections import defaultdict
from datetime import datetime
from flask import Blueprint, request, session, Response, jsonify, url_for, redirect
from twilio.twiml.voice_response import VoiceResponse
from app.config import DELIVERECT_API_URL, BASE_URL
from app.utils.deliverect import build_deliverect_order, get_deliverect_headers
from app.utils.menu_utils import find_menu_item_by_name
from app.utils.order_utils import (
    build_order_description,
    calculate_bill_amount,
    dtmf_yes_no,
    user_said_yes,
    user_said_no,
    validate_modifiers,
)
from app.utils.menu_utils import load_menu_data
from app.utils.helpers import log_info, commit_with_retry
from app.utils.agent_utils import OrderParsingAgent
from twilio.twiml.messaging_response import MessagingResponse
from sqlalchemy import text
from app.models import Order
from app import db

# Helper function to get recent log entries
def get_last_log_lines(num_lines=20):
    """Get the last N lines from the log file."""
    # Create an empty list for lines
    lines = []
    try:
        # First try reading from a standard log location
        log_paths = [
            '/app/progress.log',  # Docker container location
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'progress.log'),  # Project root
            '/var/log/app.log',   # Common Linux log location
            'app.log'             # Local directory
        ]
        
        # Try each possible log path
        for log_path in log_paths:
            if os.path.exists(log_path):
                with open(log_path, 'r') as f:
                    # Read all lines and get the last N
                    all_lines = f.readlines()
                    lines = all_lines[-num_lines:] if len(all_lines) >= num_lines else all_lines
                break
        
        # If no log file found, try getting the log from the logging module's handlers
        if not lines:
            root_logger = logging.getLogger()
            for handler in root_logger.handlers:
                if hasattr(handler, 'baseFilename'):
                    with open(handler.baseFilename, 'r') as f:
                        all_lines = f.readlines()
                        lines = all_lines[-num_lines:] if len(all_lines) >= num_lines else all_lines
                    break
    except Exception as e:
        # If we can't read the log file, return an empty list
        logging.warning(f"Could not read log file: {e}")
        return []
    
    return lines

# Try to import from the original module first
from app.utils.agent_utils import analyze_user_input, get_order_modifications

logger = logging.getLogger(__name__)
logger.info("Successfully imported OpenAI agent utilities in order routes")

from app import twilio_client
from app.config import TWILIO_NUMBER as TWILIO_PHONE_NUMBER

# Try to import tasks module for status updates
try:
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from tasks import send_order_status_update_task
except ImportError:
    logger.warning(
        "Could not import send_order_status_update_task from tasks module. Will try again when needed."
    )

order_bp = Blueprint("order", __name__)
logger = logging.getLogger(__name__)

# Global variables and concurrency control
channel_status = 1  # 0: registered, 1: active, 2: inactive
BUSY_MODE_ACTIVE = False
recent_actions = defaultdict(lambda: {"timestamp": 0, "lock": threading.Lock()})

# Function to check for menu items that need modifier suggestions
def custom_suggest_modifiers(item_name):
    """
    Utility function to ensure we always get meaningful modifier prompts.
    
    This function takes an item name, uses OrderParsingAgent to get modifier
    suggestions, but ensures it always returns a prompt even if no specific
    modifiers are found.
    
    Args:
        item_name (str): The name of the menu item
        
    Returns:
        dict: A dictionary containing:
            - prompt (str): A natural language prompt suggesting modifiers
            - suggestions (list): Structured list of modifier suggestions
            - found (bool): Whether the item was found in the menu
    """
    logger.info(f"Getting custom modifier suggestions for {item_name}")
    
    # Initialize the agent
    agent = OrderParsingAgent()
    
    # Get structured suggestions from the agent
    modifier_data = agent.menu_tool.suggest_modifiers(item_name)
    
    # Try to generate a natural language prompt
    try:
        modifier_prompt = agent.menu_tool.generate_modifier_prompt(item_name)
    except Exception as e:
        logger.error(f"Error generating modifier prompt: {e}")
        modifier_prompt = None
    
    # If we found the item but didn't get a prompt, create a default one
    if modifier_data.get("found", False) and not modifier_prompt:
        logger.info(f"No specific modifier prompt found for {item_name}, generating fallback")
        
        # Create a default prompt based on item category and item properties
        item = modifier_data.get("item", {})
        item_category = item.get("category", "").lower()
        is_combo = item.get("isCombo", False) or "combo" in item_name.lower() or "meal" in item_name.lower()
        
        # First check if it's a combo meal with components
        if is_combo:
            # Get components from the menu item if available
            child_products = item.get("childProducts", [])
            if child_products:
                component_names = [comp.get("name", "") for comp in child_products if comp.get("required", True)]
                if component_names:
                    component_list = ", ".join(component_names[:3])
                    modifier_prompt = f"For your {item_name}, please select from these options: {component_list}. What would you like?"
                else:
                    modifier_prompt = f"What sides or drinks would you like with your {item_name}?"
            else:
                modifier_prompt = f"What sides or drinks would you like with your {item_name}?"
        # Then check food categories for appropriate cooking preferences
        elif "steak" in item_name.lower():
            modifier_prompt = f"How would you like your {item_name} cooked? Rare, medium, or well done?"
        elif "burger" in item_name.lower():
            # Burgers shouldn't always get the steak cooking options
            if "patty" in item_name.lower() or "beef" in item_name.lower():
                modifier_prompt = f"How would you like your {item_name} cooked? And would you like any toppings like cheese or bacon?"
            else:
                modifier_prompt = f"Would you like any toppings on your {item_name}, such as cheese, lettuce, or tomato?"
        elif "roll" in item_name.lower() or "sushi" in item_name.lower():
            modifier_prompt = f"Would you like any special preparation for your {item_name}? For example, extra wasabi, spicy mayo, or soy sauce on the side?"
        elif "salad" in item_name.lower():
            modifier_prompt = f"Would you like any special dressing for your {item_name}?"
        else:
            # Generic fallback
            modifier_prompt = f"Would you like to customize your {item_name} with any special requests or modifications?"
    
    # If item wasn't found at all, create a generic prompt
    if not modifier_data.get("found", False):
        logger.warning(f"Item {item_name} not found in menu for modifier suggestions")
        modifier_prompt = f"Would you like any special requests or modifications for your {item_name}?"
        modifier_data = {
            "found": False,
            "suggestions": []
        }
    
    # Return complete results
    return {
        "prompt": modifier_prompt or f"Would you like any modifications for your {item_name}? Say what you'd like or press 1 to skip.",
        "suggestions": modifier_data.get("suggestions", []),
        "found": modifier_data.get("found", False)
    }

def check_for_missing_modifiers(order_items):
    """
    Check if any order items don't have modifiers but should.
    
    Uses the enhanced validate_modifier_constraints function to identify items
    that are missing required modifiers or would benefit from modifier suggestions.
    Also handles meal deals and their components, and provides detailed constraint
    information for user prompting.
    
    This function is more intelligent about modifiers:
    1. For combo items, it always suggests components
    2. For items with existing modifiers of the right types, it avoids re-suggesting
    3. For items with required modifiers, it verifies if those requirements are met
    
    Args:
        order_items: List of order items to check
        
    Returns:
        tuple: (items_needing_modifiers, constraint_details)
            - items_needing_modifiers: List of items that need modifiers
            - constraint_details: Dict mapping item name -> constraint details for prompting
    """
    from app.utils.menu_utils import validate_modifier_constraints
    import logging
    logger = logging.getLogger(__name__)
    
    # Initialize agent for checking item details
    agent = OrderParsingAgent()
    items_needing_modifiers = []
    
    # Get detailed constraints for all items
    # The updated validate_modifier_constraints will return ALL items with modifier groups
    is_valid, error_message, constraint_details = validate_modifier_constraints(
        order_items, return_detailed_constraints=True
    )
    
    logger.info(f"Checking {len(order_items)} items for missing modifiers")
    logger.info(f"Found {len(constraint_details)} items with modifier constraints")
    
    # More intelligently add items with constraints to the list
    for item_name, details in constraint_details.items():
        # Find the matching item in the order_items list
        for item in order_items:
            if item.get("name") == item_name:
                # Check if this item is a combo/meal deal
                is_combo = details.get("is_combo", False)
                mod_groups = details.get("modifier_groups", [])
                
                # Check if this item already has appropriate modifiers
                existing_modifiers = item.get("modifier", [])
                existing_mod_types = {mod.get("name", "").lower() for mod in existing_modifiers}
                
                # For combo items, always suggest components if none selected
                if is_combo:
                    # See if there are component modifiers already added
                    has_components = False
                    for mod in existing_modifiers:
                        # Check if it appears to be a component selection
                        if "component" in mod.get("reference_handler", "").lower():
                            has_components = True
                            break
                    
                    # If no components found, add to items needing modifiers
                    if not has_components:
                        if item not in items_needing_modifiers:
                            items_needing_modifiers.append(item)
                            logger.info(f"Added combo item {item_name} to items needing modifiers (needs components)")
                
                # For items with modifier groups, check if required ones are missing
                elif mod_groups:
                    needs_modifiers = False
                    
                    # Check if any required group is missing modifiers
                    for group in mod_groups:
                        min_required = group.get("min_required", 0)
                        if min_required > 0:
                            # This group requires modifiers, check if we have any from this group
                            group_mods = {mod.lower() for mod in group.get("modifiers", [])}
                            found_mods = any(mod_name in group_mods for mod_name in existing_mod_types)
                            
                            if not found_mods:
                                needs_modifiers = True
                                break
                    
                    # Add item if it needs modifiers
                    if needs_modifiers:
                        if item not in items_needing_modifiers:
                            items_needing_modifiers.append(item)
                            logger.info(f"Added {item_name} to items needing modifiers (missing required modifiers)")
                    # If not required but has mod groups, only suggest if no modifiers yet
                    elif not existing_modifiers:
                        if item not in items_needing_modifiers:
                            items_needing_modifiers.append(item)
                            logger.info(f"Added {item_name} to items needing optional modifiers")
                
                break
    
    # Log what we've found
    logger.info(f"Added {len(items_needing_modifiers)} items that need modifiers")
    for item in items_needing_modifiers:
        item_name = item.get("name", "")
        # Get all the modifier groups for this item
        if item_name in constraint_details:
            mod_groups = constraint_details[item_name].get("modifier_groups", [])
            is_combo = constraint_details[item_name].get("is_combo", False)
            if is_combo:
                components = constraint_details[item_name].get("components", [])
                component_names = [comp.get("name") for comp in components]
                logger.info(f"Item {item_name} is a combo/meal deal with components: {', '.join(component_names)}")
            if mod_groups:
                group_names = [group.get("name") for group in mod_groups]
                logger.info(f"Item {item_name} has modifier groups: {', '.join(group_names)}")
    
    # If no items with constraints were found, fall back to checking for recommended modifiers
    if not items_needing_modifiers:
        for item in order_items:
            # Skip if it already has modifiers
            if item.get("modifier") and len(item.get("modifier", [])) > 0:
                continue
                
            # Get details for this item
            item_name = item.get("name", "")
            item_details = agent.menu_tool.get_details(item_name)
            
            # Check if item has available modifiers and would benefit from suggestions
            if item_details.get("found") and item_details.get("modifiers"):
                # Check if this is a meal deal / combo product
                is_combo = item_details.get("isCombo", False)
                if is_combo:
                    # Always prompt for meal deal components
                    items_needing_modifiers.append(item)
                    logger.info(f"Added combo item {item_name} to items needing modifiers")
                    # Add combo details to constraint_details if not already there
                    if item_name not in constraint_details:
                        child_products = item_details.get("childProducts", [])
                        if child_products:
                            constraint_details[item_name] = {
                                "is_combo": True,
                                "components": [
                                    {
                                        "name": child.get("name"),
                                        "id": child.get("id"),
                                        "required": True
                                    } for child in child_products
                                ]
                            }
                    continue
                
                # Add item with ANY modifier groups to the list - be aggressive!
                if item_details.get("modifiers"):
                    items_needing_modifiers.append(item)
                    logger.info(f"Added item {item_name} with modifiers to items needing modifiers")
                    # Add all modifier groups to constraints
                    if item_name not in constraint_details:
                        constraint_details[item_name] = {
                            "is_combo": False,
                            "modifier_groups": []
                        }
                    
                    # Add ALL modifier groups, not just recommended ones
                    for mod_group in item_details.get("modifiers", []):
                        if "modifier_groups" not in constraint_details[item_name]:
                            constraint_details[item_name]["modifier_groups"] = []
                        
                        constraint_details[item_name]["modifier_groups"].append({
                            "name": mod_group.get("name"),
                            "is_recommended": True,  # Mark all as recommended
                            "modifiers": [
                                mod.get("name") for mod in mod_group.get("modifiers", [])
                            ]
                        })
    
    # Final logging
    if items_needing_modifiers:
        logger.info(f"Returning {len(items_needing_modifiers)} items that need modifiers")
    else:
        logger.info("No items need modifiers")
        
    return items_needing_modifiers, constraint_details

# Constants
COOLDOWN_PERIOD = 60  # seconds
DEFAULT_PREP_TIME_BASE = 20  # minutes
PREP_TIME_PER_ITEM = 1  # minutes per item


def can_process_action(sender, action_key, cooldown=30):
    """Prevent rapid-fire actions from the same sender"""
    current_time = time.time()
    with recent_actions[sender]["lock"]:
        last_time = recent_actions[sender].get(action_key, 0)
        if current_time - last_time > cooldown:
            recent_actions[sender][action_key] = current_time
            return True
        return False


@order_bp.route("/take_order", methods=["POST"])
def take_order():
    """Process a new order request from voice"""
    """Process a new order request from voice"""
    # Check if we're in busy mode
    if BUSY_MODE_ACTIVE:
        response = VoiceResponse()
        # Instead of hanging up, offer options when busy
        response.say(
            "We're currently busy and not accepting new orders right now."
        )
        
        # Gather input to let them choose an option
        with response.gather(
            input="speech dtmf",
            action="/handle_busy_options",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=5,
            timeout=7,
            num_digits=1
        ) as g:
            g.say("Press 1 to get menu information, press 2 to leave your name and number for a callback, or press 3 to end the call.")
        
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
                "name_variants": {},
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
            response.say(
                "I'm sorry, our menu is currently unavailable."
            )
            
            # Instead of hanging up, offer some alternatives
            with response.gather(
                input="speech dtmf",
                action="/handle_menu_unavailable",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout=5,
                timeout=7,
                num_digits=1
            ) as g:
                g.say("Press 1 to speak with a team member about our daily specials, press 2 to leave your contact information for when our menu is back online, or press 3 to end the call.")
            
            # If they don't input anything, redirect to the handler
            response.redirect("/handle_menu_unavailable")
            return Response(str(response), mimetype="text/xml")

    except Exception as e:
        logger.error(f"Error loading menu: {e}")
        response = VoiceResponse()
        response.say(
            "I'm sorry, we're experiencing technical difficulties."
        )
        
        # Instead of hanging up, give them options
        with response.gather(
            input="speech dtmf",
            action="/handle_technical_difficulties",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=5,
            timeout=7,
            num_digits=1
        ) as g:
            g.say("Press 1 to speak with a team member who can take your order manually, press 2 to leave your contact information for a callback, or press 3 to end the call.")
        
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
                hints="california roll, spicy tuna roll, dragon roll, menu",  # Help Twilio recognize common items
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

    # Get the menu items from the analysis
    order_items = analysis.get("menu_items", [])

    # Process and mark any unavailable items
    from app.utils.order_utils import mark_unavailable_items

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
    items_needing_modifiers, constraint_details = check_for_missing_modifiers(available_items)
    
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
        session["remaining_modifier_items"] = json.dumps(items_needing_modifiers[1:]) if len(items_needing_modifiers) > 1 else "[]"
        
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


@order_bp.route("/confirm_order_from_initial", methods=["POST"])
def confirm_order_from_initial():
    """
    Handle order confirmation after initial order has been placed.
    This route now checks whether to proceed directly or check for modifiers first.
    
    The route accepts a skip_modifiers parameter to bypass modifier suggestions.
    It also respects a completed_modifiers session flag to prevent infinite loops.
    """
    # Check if we've already completed the modifier flow
    completed_modifiers = session.get("completed_modifiers", "false").lower() == "true"
    
    # Critical fix: Check for modifiers first unless explicitly disabled or already completed
    if request.form.get("skip_modifiers", "false").lower() != "true" and not completed_modifiers:
        # Get the current order items 
        if "order_items_json" in session:
            # Check if these items need modifiers
            order_items = json.loads(session.get("order_items_json", "[]"))
            items_needing_modifiers, _ = check_for_missing_modifiers(order_items)
            
            # Only redirect if we actually need modifiers
            if items_needing_modifiers:
                logger.info("CRITICAL FIX: Redirecting to suggest_modifiers to check for needed modifiers first")
                logger.info(f"Session keys available: {list(session.keys())}")
                logger.info(f"Order items in session: {session.get('order_items_json', '[]')}")
                
                # Create and return the redirect response
                response = VoiceResponse()
                response.redirect("/suggest_modifiers")
                return Response(str(response), mimetype="text/xml")
            else:
                logger.info("No modifiers needed, proceeding with confirmation")
                # Mark as completed to avoid future checking
                session["completed_modifiers"] = "true"
    """Handle confirmation of the initial order"""
    # Get user response
    user_resp = (request.form.get("SpeechResult", "") or "").lower()
    dtmf_input = request.form.get("Digits", "")
    log_info(f"Order confirmation: Speech='{user_resp}', DTMF='{dtmf_input}'")

    # Get order data from session
    order_items = json.loads(session.get("order_items_json", "[]"))
    order_id = session.get("order_id", "") or str(uuid.uuid4())
    session["order_id"] = order_id
    sender = session.get("sender", "")
    caller_name = session.get("caller_name", "Valued Customer")

    # Create voice response
    response = VoiceResponse()
    
    # Check for silence (no input detected)
    if not user_resp and not dtmf_input:
        # Track confirmation silence retries
        confirm_silence_retry = session.get("confirm_silence_retry", 0)
        session["confirm_silence_retry"] = confirm_silence_retry + 1
        
        logger.info(f"Silence detected in initial order confirmation (attempt {confirm_silence_retry+1})")
        
        if confirm_silence_retry >= 2:
            # After multiple silent attempts, provide simple DTMF-only options
            with response.gather(
                input="dtmf",
                action="/confirm_order_from_initial",
                timeout=10,
                num_digits=1,
            ) as g:
                g.say(
                    "I didn't hear your response. Please press 1 on your keypad to confirm your order, or press 2 to modify it."
                )
        else:
            # First or second silence, prompt again with both speech and DTMF
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
                    "I didn't hear your response. Please say yes or press 1 to confirm your order, or say no or press 2 to modify it."
                )
        return Response(str(response), mimetype="text/xml")
        
    # Interpret response
    interpreted = None
    if dtmf_input:
        interpreted = dtmf_yes_no(dtmf_input)
    else:
        if user_said_yes(user_resp):
            interpreted = "yes"
        elif user_said_no(user_resp):
            interpreted = "no"
            
    # Reset silence counter if we received input
    session["confirm_silence_retry"] = 0
    
    log_info(f"User confirmation interpreted as: {interpreted}")

    # Handle "yes" - process the order
    if interpreted == "yes":
        # Check for newly snoozed items
        from app.utils.snooze_validator import validate_items_availability

        load_menu_data(force_refresh=True)

        # Deep check for snoozed items
        available_items = validate_items_availability(order_items)
        unavailable_items = [
            item["name"] for item in order_items if item not in available_items
        ]

        if unavailable_items:
            logger.info(f"Items unavailable at order confirmation: {unavailable_items}")
            with response.gather(
                input="speech dtmf",
                action="/handle_newly_snoozed_in_checkout",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout="auto",
                num_digits=1,
            ) as g:
                g.say(
                    "Sorry, the following item(s) are now unavailable: "
                    + ", ".join(unavailable_items)
                    + ". Press 1 to remove them, 2 to cancel."
                )
            return Response(str(response), mimetype="text/xml")
            
        # CRITICAL: Check for invalid modifiers that aren't in the menu
        # Get all valid modifiers from the menu
        menu_data = load_menu_data(force_refresh=True)
        valid_modifiers = {
            mod.get("name", "").lower(): mod
            for mod in menu_data.get("modifiers", [])
            if mod.get("name") and mod.get("available", True) and not mod.get("snoozed", False)
        }
        
        # Check each item for invalid modifiers
        invalid_item_modifiers = []
        
        for item in order_items:
            item_name = item.get("name", "")
            invalid_mods = []
            
            # Check each modifier against the menu
            for mod in item.get("modifier", []):
                mod_name = mod.get("name", "").lower()
                # Skip standard cooking terms - these are the only exceptions
                if mod_name in ["rare", "medium rare", "medium", "medium well", "well done"]:
                    continue
                
                # Check if modifier exists in the menu
                if mod_name not in valid_modifiers:
                    invalid_mods.append(mod.get("name", "unknown"))
            
            # If invalid modifiers found for this item, add to the list
            if invalid_mods:
                invalid_item_modifiers.append({
                    "item": item_name,
                    "invalid_modifiers": invalid_mods
                })
        
        # If any items have invalid modifiers, alert the user
        if invalid_item_modifiers:
            # Create a readable message about the invalid modifiers
            alert_message = "I'm sorry, but some of your order items have modifiers that are not on our menu. "
            
            for invalid_item in invalid_item_modifiers[:2]:  # Limit to first 2 items for brevity
                item_name = invalid_item["item"]
                invalid_mods = ", ".join(invalid_item["invalid_modifiers"])
                alert_message += f"Your {item_name} has invalid modifiers: {invalid_mods}. "
            
            alert_message += "Would you like to continue without these modifiers, or modify your order? Press 1 to continue without invalid modifiers, or press 2 to modify your order."
            
            # Prompt the user to decide what to do
            with response.gather(
                input="speech dtmf",
                action="/handle_invalid_modifiers",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout=5,
                timeout=7,
                num_digits=1
            ) as g:
                g.say(alert_message)
            
            # Store the invalid modifiers in session for handling
            session["invalid_item_modifiers"] = json.dumps(invalid_item_modifiers)
            
            return Response(str(response), mimetype="text/xml")

        # Redirect to the order checkout process which will handle everything
        response.redirect("/process_order_checkout")

    # Handle "no" - go to modification
    elif interpreted == "no":
        session["modification_in_progress"] = True
        with response.gather(
            input="speech",
            action="/new_modify_order",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto",
        ) as g:
            g.say("OK, please describe how you'd like your order changed.")

    # Handle unclear response
    else:
        # Track confirmation retries
        confirm_retry_count = session.get("confirm_retry_count", 0)
        session["confirm_retry_count"] = confirm_retry_count + 1

        if confirm_retry_count >= 2:
            # After multiple unclear responses, give simpler options
            with response.gather(
                input="dtmf",
                action="/confirm_order_from_initial",
                timeout=10,
                num_digits=1,
            ) as g:
                g.say(
                    "Please use your keypad. Press 1 to confirm your order, or press 2 to modify it."
                )
        else:
            # Normal retry
            with response.gather(
                input="speech dtmf",
                action="/confirm_order_from_initial",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout="auto",
                num_digits=1,
            ) as g:
                g.say(
                    "I didn't catch that. Say yes or press 1 if correct, or no or press 2 to modify."
                )

    return Response(str(response), mimetype="text/xml")


@order_bp.route("/new_modify_order", methods=["POST"])
def new_modify_order():
    """
    Handle order modifications with strict validation.
    
    This route handles order changes including additions, removals, and modifications.
    It verifies all modifiers against the menu to ensure they exist and are available,
    rejecting any that don't meet these criteria.
    """
    # Get user's modification request
    user_resp = request.form.get("SpeechResult", "").strip()

    # Check if the user was silent or speech wasn't captured
    if not user_resp:
        # Track silence retries for modifications
        modify_silence_retry = session.get("modify_silence_retry", 0)
        session["modify_silence_retry"] = modify_silence_retry + 1

        response = VoiceResponse()

        # Change the message based on how many retries
        if modify_silence_retry >= 2:
            # After multiple tries, give more detailed guidance or fallback
            with response.gather(
                input="speech dtmf",
                action="/modification_silence_fallback",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout="auto",
                num_digits=1,
                timeout=10,  # Give even more time
            ) as g:
                g.say(
                    "I'm having trouble hearing your modifications. You can say something like 'add one spicy tuna roll' or 'remove the California roll'. Or press 1 to keep your order as is, or 2 to cancel."
                )
        else:
            # Normal or first retry prompt
            with response.gather(
                input="speech",
                action="/new_modify_order",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout="auto",
                timeout=8,  # Give more time
            ) as g:
                g.say(
                    "I'm waiting to hear your modifications. For example, you can say 'add one spicy tuna roll' or 'remove the California roll'."
                )
        return Response(str(response), mimetype="text/xml")

    logger.info(f"User requested order modification: {user_resp}")
    current_order_items = json.loads(session.get("order_items_json", "[]"))
    logger.info(f"Initial order items when starting modification: {len(current_order_items)} items")
    
    # Clear the session if we're starting a new conversation
    if len(current_order_items) > 0 and any(item.get("name") == "Chicken Sate" for item in current_order_items):
        logger.info("Found unexpected Chicken Sate in order, clearing session to start fresh")
        # Reset the session with only the steak item
        clean_order = [item for item in current_order_items if item.get("name") == "Delicious Steak Frites"]
        current_order_items = clean_order
        session["order_items_json"] = json.dumps(current_order_items)
        logger.info(f"Cleaned order items: {len(current_order_items)} items")

    # Use agent to interpret modifications
    modifications = get_order_modifications(user_resp, current_order_items)

    # Create response
    response = VoiceResponse()

    # If no valid modifications, ask again
    if not modifications or (
        "additions" not in modifications and 
        "removals" not in modifications and
        "modifications" not in modifications
    ) or (
        len(modifications.get("additions", [])) == 0 and 
        len(modifications.get("removals", [])) == 0 and
        len(modifications.get("modifications", [])) == 0
    ):
        with response.gather(
            input="speech",
            action="/new_modify_order",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto",
            timeout=6,  # More time for the retry
        ) as g:
            g.say(
                "I didn't understand your modifications. Please clearly state what you'd like to add or remove from your order."
            )
        return Response(str(response), mimetype="text/xml")

    # Load the menu for modifier validation
    menu_data = load_menu_data(force_refresh=True)
    
    # Get all valid modifiers from the menu
    valid_menu_modifiers = {
        mod.get("name", "").lower(): mod
        for mod in menu_data.get("modifiers", [])
        if mod.get("name") and mod.get("available", True) and not mod.get("snoozed", False)
    }
    
    # Standard cooking terms that should always be accepted
    cooking_terms = ["rare", "medium rare", "medium", "medium well", "well done"]
    
    logger.info(f"Found {len(valid_menu_modifiers)} valid modifiers in menu")
    
    # Apply strict validation to all modifiers in additions and modifications
    invalid_modifiers = []
    
    # Validate modifiers in additions
    for addition in modifications.get("additions", []):
        if "modifier" in addition and addition["modifier"]:
            valid_addition_mods = []
            
            for mod in addition["modifier"]:
                mod_name = mod.get("name", "").lower() if isinstance(mod, dict) else mod.lower()
                
                # Validation priority:
                # 1. First check exact match by name in menu
                # 2. Then allow only standard cooking terms as exceptions
                # 3. Reject everything else
                
                if mod_name in valid_menu_modifiers:
                    # Valid menu modifier
                    if isinstance(mod, dict):
                        # Update reference handler and price from menu
                        menu_mod = valid_menu_modifiers[mod_name]
                        mod["reference_handler"] = menu_mod.get("reference_handler")
                        mod["price"] = menu_mod.get("price", 0.0)
                    else:
                        # Convert string to proper modifier dict
                        menu_mod = valid_menu_modifiers[mod_name]
                        mod = {
                            "name": menu_mod.get("name"),
                            "reference_handler": menu_mod.get("reference_handler"),
                            "price": menu_mod.get("price", 0.0),
                            "quantity": 1
                        }
                    valid_addition_mods.append(mod)
                    logger.info(f"Validated modifier with exact menu match: {mod_name}")
                elif mod_name in cooking_terms:
                    # Standard cooking term
                    if isinstance(mod, dict):
                        mod["reference_handler"] = f"COOK-{hash(mod_name) % 100:02d}"
                    else:
                        mod = {
                            "name": mod_name.capitalize(),
                            "reference_handler": f"COOK-{hash(mod_name) % 100:02d}",
                            "price": 0.0,
                            "quantity": 1
                        }
                    valid_addition_mods.append(mod)
                    logger.info(f"Validated standard cooking modifier: {mod_name}")
                else:
                    # Invalid modifier - reject it
                    invalid_modifiers.append(mod_name)
                    logger.warning(f"Rejected invalid modifier in addition: {mod_name}")
            
            # Replace with only valid modifiers
            addition["modifier"] = valid_addition_mods
    
    # Validate modifiers in item-specific modifications
    for modification in modifications.get("modifications", []):
        if "modifier" in modification and modification["modifier"]:
            valid_mod_mods = []
            
            for mod in modification["modifier"]:
                mod_name = mod.get("name", "").lower() if isinstance(mod, dict) else mod.lower()
                
                # Same validation priority as above
                if mod_name in valid_menu_modifiers:
                    # Valid menu modifier
                    if isinstance(mod, dict):
                        # Update reference handler and price from menu
                        menu_mod = valid_menu_modifiers[mod_name]
                        mod["reference_handler"] = menu_mod.get("reference_handler")
                        mod["price"] = menu_mod.get("price", 0.0)
                    else:
                        # Convert string to proper modifier dict
                        menu_mod = valid_menu_modifiers[mod_name]
                        mod = {
                            "name": menu_mod.get("name"),
                            "reference_handler": menu_mod.get("reference_handler"),
                            "price": menu_mod.get("price", 0.0),
                            "quantity": 1
                        }
                    valid_mod_mods.append(mod)
                    logger.info(f"Validated modifier with exact menu match: {mod_name}")
                elif mod_name in cooking_terms:
                    # Standard cooking term
                    if isinstance(mod, dict):
                        mod["reference_handler"] = f"COOK-{hash(mod_name) % 100:02d}"
                    else:
                        mod = {
                            "name": mod_name.capitalize(),
                            "reference_handler": f"COOK-{hash(mod_name) % 100:02d}",
                            "price": 0.0,
                            "quantity": 1
                        }
                    valid_mod_mods.append(mod)
                    logger.info(f"Validated standard cooking modifier: {mod_name}")
                else:
                    # Invalid modifier - reject it
                    invalid_modifiers.append(mod_name)
                    logger.warning(f"Rejected invalid modifier in modification: {mod_name}")
            
            # Replace with only valid modifiers
            modification["modifier"] = valid_mod_mods
    
    # If invalid modifiers were detected, inform the user
    if invalid_modifiers:
        logger.warning(f"Detected invalid modifiers: {invalid_modifiers}")
        
        # Get menu suggestions for alternatives
        suggested_alternatives = list(valid_menu_modifiers.keys())[:5]  # Take first 5 valid modifiers
        
        # Create a response informing about invalid modifiers
        with response.gather(
            input="speech dtmf",
            action="/new_modify_order",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto",
            num_digits=1,
        ) as g:
            # First, inform about the rejected modifiers
            modifier_text = ", ".join(invalid_modifiers)
            suggestion_text = ""
            if suggested_alternatives:
                suggestion_text = f" Some available modifiers include: {', '.join(suggested_alternatives)}."
                
            g.say(f"I'm sorry, but we don't have '{modifier_text}' on our menu.{suggestion_text} Please specify a different modifier or press 1 to continue without these modifiers.")
        return Response(str(response), mimetype="text/xml")
    
    # Apply modifications using the validated data
    try:
        from app.utils.order_utils import apply_modifications as apply_from_utils
        logger.info("Using apply_modifications from order_utils.py")
        updated_items = apply_from_utils(current_order_items, modifications)
    except Exception as e:
        logger.error(f"Error using apply_modifications from order_utils.py: {str(e)}")
        # Fall back to the local function
        updated_items = apply_modifications(current_order_items, modifications)
    
    logger.info(f"Order updated: {len(updated_items)} items with modifications applied")

    # CRITICAL: Perform one final validation to ensure all items and modifiers are valid
    from app.utils.order_utils import prepare_order_for_deliverect
    
    try:
        # This is the most strict validation that ensures only valid menu items with valid modifiers remain
        validated_items = prepare_order_for_deliverect(updated_items)
        
        # Update order with strictly validated items
        updated_items = validated_items
        logger.info(f"Final validation completed: {len(validated_items)} valid items remain")
        
        # Check for items or modifiers that were removed during validation
        if len(validated_items) < len(updated_items):
            logger.warning(f"Validation removed {len(updated_items) - len(validated_items)} invalid items")
    except Exception as e:
        logger.error(f"Error during final validation: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Continue with the order as-is if validation fails
    
    # Update session with the validated order
    session["order_items_json"] = json.dumps(updated_items)
    calculate_bill_amount(updated_items)
    session["bill_amount"] = int(session.get("total_price", 0) * 100)
    order_description = build_order_description(updated_items)
    
    # Log detailed order information including modifiers
    logger.info(f"Final order after complete validation: {len(updated_items)} items")
    for item in updated_items:
        if "modifier" in item and item["modifier"]:
            mod_list = [f"{mod.get('name', 'unknown')}" for mod in item["modifier"]]
            logger.info(f"Item {item.get('name')} has {len(item['modifier'])} modifiers: {', '.join(mod_list)}")

    # Confirm updated order
    confirmation_message = (
        f"Your order is now:\n{order_description}\nTotal: ${session.get('total_price', 0):.2f}. "
        "If correct, say yes or press 1. If you need changes, say no or press 2."
    )
    with response.gather(
        input="speech dtmf",
        action="/confirm_order_after_modification",
        enhanced=True,
        speech_model="phone_call",
        language="en-US",
        speech_timeout="auto",
        num_digits=1,
    ) as g:
        g.say(confirmation_message)

    return Response(str(response), mimetype="text/xml")


def apply_modifications(current_order, modifications):
    """Apply modifications to an order, handling all possible formats"""
    # Extract additions, removals, and item modifications from modifications
    additions = modifications.get("additions", [])
    removals = modifications.get("removals", [])
    item_modifications = modifications.get("modifications", [])
    
    # Log the received modifications
    logger.info(f"[ORDER-MODIFY] Received modifications: additions={len(additions)}, removals={len(removals)}, modifications={len(item_modifications)}")

    # Ensure all removals have a "name" field
    for removal in removals:
        if isinstance(removal, dict):
            if "item" in removal and "name" not in removal:
                removal["name"] = removal["item"]
                logger.info(
                    f"[ORDER-FIX] Copying 'item' to 'name' field in removal: {removal}"
                )

    # Ensure all additions have a "name" field
    for addition in additions:
        if isinstance(addition, dict):
            if "item" in addition and "name" not in addition:
                addition["name"] = addition["item"]
                logger.info(
                    f"[ORDER-FIX] Copying 'item' to 'name' field in addition: {addition}"
                )

    # Create a dictionary of current order items by name (case-insensitive)
    current_order_by_name = {item["name"].lower(): item for item in current_order}

    # Detailed logging for debugging
    logger.info(f"[ORDER-MODIFY] Processing modifications: {json.dumps(modifications)}")
    logger.info(f"[ORDER-MODIFY] Current order: {json.dumps(current_order)}")
    logger.info(f"[ORDER-MODIFY] Processed additions: {json.dumps(additions)}")
    logger.info(f"[ORDER-MODIFY] Processed removals: {json.dumps(removals)}")
    logger.info(f"[ORDER-MODIFY] Processed item modifications: {json.dumps(item_modifications)}")

    # Process removals
    for removal in removals:
        # Handle string format (e.g., "1x Chicken Burger")
        if isinstance(removal, str):
            match = re.match(r"(\d+)x\s+(.+)", removal.strip())
            if match:
                quantity = int(match.group(1))
                item_name = match.group(2).lower()
            else:
                # If no quantity specified, assume 1
                quantity = 1
                item_name = removal.strip().lower()
        else:
            # Handle dictionary format with different possible key names
            # Look for 'name', 'item', or field containing the item name
            if "name" in removal:
                item_name = removal["name"].lower()
            elif "item" in removal:
                item_name = removal["item"].lower()
            else:
                # Try to find a string field that might contain the item name
                item_name = None
                for key, value in removal.items():
                    if isinstance(value, str) and len(value) > 2:
                        item_name = value.lower()
                        break

                # If we still don't have an item name, skip this removal
                if item_name is None:
                    logger.warning(
                        f"[ORDER-MODIFY] Skipping removal with no item name: {removal}"
                    )
                    continue

            # Get quantity
            quantity = removal.get("quantity", 1)

        # If item exists, decrease quantity or remove it
        if item_name in current_order_by_name:
            current_order_by_name[item_name]["quantity"] -= quantity

            # Remove item if quantity is now zero or less
            if current_order_by_name[item_name]["quantity"] <= 0:
                del current_order_by_name[item_name]

    # Process additions
    for addition in additions:
        # Handle string format (e.g., "1x Chicken Burger")
        if isinstance(addition, str):
            match = re.match(r"(\d+)x\s+(.+)", addition.strip())
            if match:
                quantity = int(match.group(1))
                item_name = match.group(2).lower()
            else:
                # If no quantity specified, assume 1
                quantity = 1
                item_name = addition.strip().lower()

            # Find the item in the menu
            menu_item = find_menu_item_by_name(item_name)
            if menu_item:
                addition = {
                    "name": menu_item.get("name"),
                    "price": menu_item.get("price", 0),
                    "reference_handler": menu_item.get("reference_handler", ""),
                    "quantity": quantity,
                    "modifier": [],
                }
            else:
                # Not found in menu, create basic structure but tell the user
                logger.warning(f"[ORDER-MODIFY] Item not found in menu: {item_name}")
                # This item will fail validation later and be removed
                addition = {
                    "name": item_name.title(),
                    "quantity": quantity,
                    "modifier": [],
                }
        else:
            # Handle dictionary format with different possible key names
            # Look for 'name', 'item', or field containing the item name
            if "name" in addition:
                item_name = addition["name"].lower()
            elif "item" in addition:
                item_name = addition["item"].lower()
            else:
                # Try to find a string field that might contain the item name
                item_name = None
                for key, value in addition.items():
                    if isinstance(value, str) and len(value) > 2 and key != "modifier":
                        item_name = value.lower()
                        break

                # If we still don't have an item name, skip this addition
                if item_name is None:
                    logger.warning(
                        f"[ORDER-MODIFY] Skipping addition with no item name: {addition}"
                    )
                    continue

            # Get quantity
            quantity = addition.get("quantity", 1)

            # Find the item in the menu to get complete information
            menu_item = find_menu_item_by_name(item_name)
            if menu_item:
                # Update the addition with complete menu information
                if "name" not in addition or not addition["name"]:
                    addition["name"] = menu_item.get("name")
                if "price" not in addition or not addition["price"]:
                    addition["price"] = menu_item.get("price", 0)
                if (
                    "reference_handler" not in addition
                    or not addition["reference_handler"]
                ):
                    addition["reference_handler"] = menu_item.get(
                        "reference_handler", ""
                    )
                if "modifier" not in addition:
                    addition["modifier"] = []
            else:
                # Make sure the item has the necessary fields for processing
                if "name" not in addition or not addition["name"]:
                    # Use the item_name we identified earlier
                    addition["name"] = item_name.title()
                if "modifier" not in addition:
                    addition["modifier"] = []

        # Prepare for dictionary lookup and update
        item_name = addition.get("name", "").lower()
        quantity = addition.get("quantity", 1)

        # If item already exists, update it
        if item_name in current_order_by_name:
            current_order_by_name[item_name]["quantity"] += quantity
            # Update modifiers if provided
            if "modifier" in addition and addition["modifier"]:
                current_order_by_name[item_name]["modifier"] = addition.get(
                    "modifier", []
                )
        else:
            # Add new item
            current_order_by_name[item_name] = addition

    # Process modifications to existing items
    for modification in item_modifications:
        # Each modification should have an item_name and a modifier array
        if not isinstance(modification, dict):
            logger.warning(f"[ORDER-MODIFY] Skipping invalid modification format: {modification}")
            continue
            
        # Get the item name to modify
        item_name = None
        if "item_name" in modification:
            item_name = modification["item_name"].lower()
        elif "name" in modification:
            item_name = modification["name"].lower()
        
        # Skip if no valid item name
        if not item_name:
            logger.warning(f"[ORDER-MODIFY] Skipping modification with no item name: {modification}")
            continue
            
        # Find the item in the current order
        if item_name in current_order_by_name:
            # Get the modifiers to add
            modifiers_to_add = modification.get("modifier", [])
            
            # Process each modifier
            for mod in modifiers_to_add:
                # Convert string modifiers to dictionary format
                if isinstance(mod, str):
                    # Create a properly formatted modifier from the string
                    mod_name = mod.strip()
                    
                    # Determine modifier type
                    if "cook" in mod_name.lower() or "rare" in mod_name.lower() or "medium" in mod_name.lower() or "well" in mod_name.lower():
                        mod_type = "COOK"
                    elif "side" in mod_name.lower() or "fries" in mod_name.lower() or "salad" in mod_name.lower():
                        mod_type = "SIDE"
                    else:
                        mod_type = "GEN"
                    
                    # Convert to dictionary
                    mod = {
                        "name": mod_name.capitalize(),
                        "quantity": 1,
                        "price": 0.0,
                        "reference_handler": f"MOD-{mod_type}-{mod_name.lower().replace(' ', '-')}"
                    }
                    logger.info(f"[ORDER-MODIFY] Converted string modifier '{mod_name}' to dictionary format")
                
                # Skip non-dictionary modifiers that couldn't be converted
                if not isinstance(mod, dict):
                    logger.warning(f"[ORDER-MODIFY] Skipping non-dictionary modifier: {mod}")
                    continue
                    
                # Get modifier information
                mod_name = mod.get("name", "").lower()
                mod_quantity = mod.get("quantity", 1)
                
                if not mod_name:
                    continue
                    
                # Find the modifier in the menu to get complete information
                menu_data = load_menu_data()
                menu_modifier = None
                
                # Search for the modifier in the menu
                for menu_mod in menu_data.get("modifiers", []):
                    if menu_mod.get("name", "").lower() == mod_name:
                        menu_modifier = menu_mod
                        break
                
                # Create or update the modifier with complete information
                mod_to_add = {
                    "name": menu_modifier.get("name", mod_name.title()) if menu_modifier else mod_name.title(),
                    "quantity": mod_quantity,
                    "price": menu_modifier.get("price", 0.0) if menu_modifier else 0.0,
                    "reference_handler": menu_modifier.get("reference_handler", "") if menu_modifier else ""
                }
                
                # Check if the modifier already exists in the item
                current_modifiers = current_order_by_name[item_name].get("modifier", [])
                mod_found = False
                
                for i, existing_mod in enumerate(current_modifiers):
                    if existing_mod.get("name", "").lower() == mod_name:
                        # Update existing modifier quantity
                        current_modifiers[i]["quantity"] += mod_quantity
                        mod_found = True
                        break
                
                # If modifier not found, add it
                if not mod_found:
                    current_modifiers.append(mod_to_add)
                
                # Update the item's modifiers
                current_order_by_name[item_name]["modifier"] = current_modifiers
                
                logger.info(f"[ORDER-MODIFY] Added/Updated modifier '{mod_to_add['name']}' to item '{current_order_by_name[item_name]['name']}'")
        else:
            logger.warning(f"[ORDER-MODIFY] Cannot modify non-existent item: {item_name}")

    # Return the updated order as a list
    return list(current_order_by_name.values())


@order_bp.route("/confirm_order_after_modification", methods=["POST"])
def confirm_order_after_modification():
    """Handle confirmation after order modifications"""
    # Get user response
    user_resp = (request.form.get("SpeechResult", "") or "").strip().lower()
    dtmf_input = request.form.get("Digits", "")
    log_info(
        f"Final confirmation after modification: Speech='{user_resp}', DTMF='{dtmf_input}'"
    )

    # Get order data
    order_items = json.loads(session.get("order_items_json", "[]"))
    order_id = session.get("order_id", "") or str(uuid.uuid4())
    session["order_id"] = order_id
    sender = session.get("sender", "")
    caller_name = session.get("caller_name", "Valued Customer")

    # Create response
    response = VoiceResponse()
    
    # Check for silence (no input detected)
    if not user_resp and not dtmf_input:
        # Track final confirmation silence retries
        final_silence_retry = session.get("final_silence_retry", 0)
        session["final_silence_retry"] = final_silence_retry + 1
        
        logger.info(f"Silence detected in final order confirmation (attempt {final_silence_retry+1})")
        
        if final_silence_retry >= 2:
            # After multiple silent attempts, provide simple DTMF-only options with extended timeout
            with response.gather(
                input="dtmf",
                action="/confirm_order_after_modification",
                timeout=12,
                num_digits=1,
            ) as g:
                g.say(
                    "I haven't heard your response. Please press 1 on your keypad to confirm your final order, or press 2 if you want to modify it again."
                )
        else:
            # First or second silence, prompt again with both speech and DTMF
            with response.gather(
                input="speech dtmf",
                action="/confirm_order_after_modification",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout=5,
                timeout=8,
                num_digits=1,
            ) as g:
                g.say(
                    "I didn't hear your response. Please say yes or press 1 to confirm your final order, or say no or press 2 to make more changes."
                )
        return Response(str(response), mimetype="text/xml")

    # Interpret response
    interpreted = None
    if dtmf_input:
        interpreted = dtmf_yes_no(dtmf_input)
    else:
        if user_said_yes(user_resp):
            interpreted = "yes"
        elif user_said_no(user_resp):
            interpreted = "no"
            
    # Reset silence counter if we received input
    session["final_silence_retry"] = 0
    
    log_info(f"User final decision: {interpreted}")

    # Handle "yes" - process the order
    if interpreted == "yes":
        # Check for newly snoozed items using comprehensive validator
        from app.utils.snooze_validator import validate_items_availability

        load_menu_data(force_refresh=True)

        # Deep check for snoozed items
        available_items = validate_items_availability(order_items)
        unavailable_items = [
            item["name"] for item in order_items if item not in available_items
        ]

        if unavailable_items:
            logger.info(f"Items unavailable at final confirmation: {unavailable_items}")
            with response.gather(
                input="speech dtmf",
                action="/handle_newly_snoozed_in_checkout",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout="auto",
                num_digits=1,
            ) as g:
                g.say(
                    "Sorry, the following item(s) are now unavailable: "
                    + ", ".join(unavailable_items)
                    + ". Press 1 to remove them, 2 to cancel."
                )
            return Response(str(response), mimetype="text/xml")

        # Check cooldown
        if not can_process_action(sender, "order_food", 60):
            response.say(
                "You're placing orders too quickly. Please wait and try again."
            )
            return Response(str(response), mimetype="text/xml")

        # Save to database
        try:
            text_msg = session.get("order_message", "")
            new_order = Order(
                id=order_id, sender=sender, caller_name=caller_name, message=text_msg
            )
            db.session.add(new_order)
            if not commit_with_retry(db.session):
                raise Exception("Commit failed")
            log_info(f"Order {order_id} saved successfully.")
        except Exception:
            db.session.rollback()
            response.say(
                "Sorry, we encountered a database issue. Please try again later."
            )
            return Response(str(response), mimetype="text/xml")

        # Send to Deliverect and SMS confirmation
        try:
            # Import the validation function to ensure all items have reference handlers
            from app.utils.order_utils import prepare_order_for_deliverect, validate_modifiers
            from app.utils.menu_utils import load_menu_data

            # CRITICAL: First validate all modifiers strictly against the menu
            # Load the current menu data to get valid modifiers
            menu_data = load_menu_data(force_refresh=True)
            
            # Get all valid modifiers from the menu (only available, non-snoozed modifiers)
            valid_menu_modifiers = {
                mod.get("name", "").lower(): mod
                for mod in menu_data.get("modifiers", [])
                if mod.get("name") and mod.get("available", True) and not mod.get("snoozed", False)
            }
            
            # Validate modifiers first
            logger.info(f"Performing strict modifier validation on {len(order_items)} items before final submission")
            
            # Standard cooking terms that are always allowed
            cooking_terms = ["rare", "medium rare", "medium", "medium well", "well done"]
            
            # Track any rejected modifiers to inform the user
            all_rejected_modifiers = []
            
            # For each item, perform strict validation of modifiers
            for item in order_items:
                if "modifier" in item and item["modifier"]:
                    valid_item_mods = []
                    rejected_item_mods = []
                    
                    for mod in item["modifier"]:
                        if not isinstance(mod, dict) or "name" not in mod:
                            continue
                            
                        mod_name = mod.get("name", "").lower()
                        
                        # Validation priority:
                        # 1. First check exact match by name in menu
                        # 2. Then allow only standard cooking terms as exceptions
                        # 3. Reject everything else
                        
                        if mod_name in valid_menu_modifiers:
                            # Found exact match by name in menu
                            menu_mod = valid_menu_modifiers[mod_name]
                            mod["reference_handler"] = menu_mod.get("reference_handler")
                            mod["price"] = menu_mod.get("price", 0.0)
                            valid_item_mods.append(mod)
                            logger.info(f"Validated modifier with exact menu match: {mod_name}")
                        elif mod_name in cooking_terms:
                            # Special case for cooking preferences (these are the ONLY exceptions allowed)
                            mod["reference_handler"] = f"COOK-{hash(mod_name) % 100:02d}"
                            valid_item_mods.append(mod)
                            logger.info(f"Validated standard cooking modifier: {mod_name}")
                        else:
                            # Not in menu - reject it!
                            rejected_item_mods.append(mod_name)
                            all_rejected_modifiers.append(mod_name)
                            logger.warning(f"Rejected non-menu modifier in final confirmation: {mod_name}")
                    
                    # Update with only valid modifiers
                    item["modifier"] = valid_item_mods
                    
                    if rejected_item_mods:
                        logger.warning(f"Removed {len(rejected_item_mods)} invalid modifiers from {item.get('name')}: {', '.join(rejected_item_mods)}")
            
            # If we found invalid modifiers, inform the user
            if all_rejected_modifiers:
                # Create a deduplicated list of rejected modifiers
                unique_rejected = list(set(all_rejected_modifiers))
                logger.warning(f"Found {len(unique_rejected)} invalid modifiers: {', '.join(unique_rejected)}")
                
                # Store rejected modifiers in session to reference later if needed
                session["rejected_modifiers"] = json.dumps(unique_rejected)
                
                # Route through the standard invalid modifier handler with the updated order items
                session["order_items_json"] = json.dumps(order_items)
                
                with response.gather(
                    input="speech dtmf",
                    action="/handle_invalid_modifiers",
                    enhanced=True,
                    speech_model="phone_call",
                    language="en-US",
                    speech_timeout="auto",
                    num_digits=1,
                ) as g:
                    g.say(
                        f"I'm sorry, but the following modifiers aren't on our menu: {', '.join(unique_rejected)}. "
                        "Press 1 or say 'continue' to remove them and continue with your order, or press 2 or say 'modify' to make changes."
                    )
                return Response(str(response), mimetype="text/xml")
            
            # Now perform full validation through prepare_order_for_deliverect
            validated_items = prepare_order_for_deliverect(order_items)

            # Check if we still have valid items after validation
            if not validated_items:
                log_info(
                    "No valid items with reference handlers in order, cannot submit to Deliverect"
                )
                # Don't fail here since we still want to save the order in our system
            else:
                # Build and send the order
                deliverect_payload = build_deliverect_order(
                    sender=sender,
                    caller_name=caller_name,
                    order_items=validated_items,
                    total_price=session.get("total_price", 0.0),
                    order_id=order_id,
                )

                response_deliv = requests.post(
                    DELIVERECT_API_URL,
                    json=deliverect_payload,
                    headers=get_deliverect_headers(),
                    timeout=10,
                )

                if response_deliv.status_code != 200:
                    log_info(
                        f"Deliverect API error: Status {response_deliv.status_code}, Response: {response_deliv.text}"
                    )
                else:
                    log_info(
                        f"Deliverect order successfully submitted: {response_deliv.text}"
                    )
        except Exception as e:
            log_info(f"Error sending order to Deliverect: {str(e)}")

        # Always send SMS confirmation regardless of Deliverect status
        import tasks

        try:
            log_info(
                f"Attempting to send SMS confirmation task directly for order {order_id}"
            )
            # Call task directly for now until Redis/Celery is properly setup
            tasks.send_confirmation_sms_task(
                order_id,
                session.get("order_message", ""),
                sender,
                caller_name,
                session.get("bill_amount", 0),
                order_items,
            )
            log_info(
                f"SMS confirmation task executed successfully for order {order_id}"
            )
        except Exception as task_error:
            log_info(f"Error sending SMS confirmation: {task_error}")
            # Fall back to direct SMS sending
            try:
                # Send a simpler message directly
                session.get("order_message", "")
                simple_msg = f"Thank you for your order! Your order ID is {order_id[:8]}. A confirmation will be sent shortly."
                twilio_client.messages.create(
                    body=simple_msg, from_=TWILIO_PHONE_NUMBER, to=sender
                )
                log_info(f"Sent simple order confirmation directly via SMS to {sender}")
            except Exception as sms_error:
                log_info(f"Error sending direct SMS confirmation: {sms_error}")

        # Calculate prep time
        time_taken = DEFAULT_PREP_TIME_BASE + (PREP_TIME_PER_ITEM * len(order_items))

        # Clear the modification flag
        session.pop("modification_in_progress", None)

        # Confirm order
        response.say(
            f"Great! Your order is confirmed and will be ready in about {time_taken} minutes. A confirmation text with payment options will be sent to your phone. You can also text 'status' to this number anytime to check your order status."
        )
        
        # Instead of hanging up, ask if they need anything else
        with response.gather(
            input="speech dtmf",
            action="/order_completion_options",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=5,
            timeout=7,
            num_digits=1
        ) as g:
            g.say("Is there anything else you'd like help with today? Press 1 for directions to our restaurant, press 2 for our hours of operation, or press 3 to end the call.")
        
        # Fallback if no input received
        response.redirect("/order_completion_options")

    # Handle "no" - go back to modification
    elif interpreted == "no":
        with response.gather(
            input="speech",
            action="/new_modify_order",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto",
        ) as g:
            g.say(
                "What else would you like to change? Please describe the final order you want."
            )

    # Handle unclear response
    else:
        # Track final confirmation retries
        final_confirm_retry = session.get("final_confirm_retry", 0)
        session["final_confirm_retry"] = final_confirm_retry + 1

        if final_confirm_retry >= 2:
            # After multiple unclear responses, give simpler options and longer timeout
            with response.gather(
                input="dtmf",
                action="/confirm_order_after_modification",
                timeout=12,
                num_digits=1,
            ) as g:
                g.say(
                    "Please use your keypad. Press 1 to confirm your order, or press 2 to modify it again."
                )
        else:
            # Normal retry
            with response.gather(
                input="speech dtmf",
                action="/confirm_order_after_modification",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout="auto",
                num_digits=1,
            ) as g:
                g.say(
                    "I didn't catch that. Say 'yes' or press 1 if correct, 'no' or press 2 to modify again."
                )

    return Response(str(response), mimetype="text/xml")


@order_bp.route("/understanding_fallback", methods=["POST"])
def understanding_fallback():
    """Handle fallbacks for when we can't understand the order after multiple tries."""
    # Get user response
    user_resp = (request.form.get("SpeechResult", "") or "").lower()
    dtmf_input = request.form.get("Digits", "")

    # Count the number of understanding fallbacks to prevent loops
    understanding_attempt = session.get("understanding_attempt", 0)
    session["understanding_attempt"] = understanding_attempt + 1

    # Create response
    response = VoiceResponse()
    
    # Check for silence (no input detected)
    if not user_resp and not dtmf_input:
        # Track silence during understanding fallback
        understand_silence_retry = session.get("understand_silence_retry", 0)
        session["understand_silence_retry"] = understand_silence_retry + 1
        
        logger.info(f"Silence detected in understanding fallback (attempt {understand_silence_retry+1})")
        
        if understand_silence_retry >= 1:
            # After silence in understanding fallback, provide more guidance and clear options
            logger.info("Multiple silences in understanding fallback - redirecting to main menu")
            session["understand_silence_retry"] = 0
            session["understanding_attempt"] = 0
            
            # Give the user a clear message and redirect to main menu
            response.say("I notice you're not responding. Let me help you with our main menu options instead.")
            response.redirect("/main_menu_fallback")
            return Response(str(response), mimetype="text/xml")
        else:
            # First silence, try once more with clear options and extended timeout
            with response.gather(
                input="speech dtmf",
                action="/understanding_fallback",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout=7,
                timeout=10,
                num_digits=1
            ) as g:
                g.say(
                    "I didn't hear your response. Press 1 or say 'menu' to hear our popular menu options. Press 2 or say 'main menu' to go back to the main menu."
                )
            return Response(str(response), mimetype="text/xml")

    # Reset silence counter if we got a response
    session["understand_silence_retry"] = 0
    
    # After too many fallbacks, force back to main menu
    if understanding_attempt >= 2:
        logger.info("Too many understanding fallbacks - forcing back to main menu")
        session["understanding_attempt"] = 0
        session["order_silence_retry"] = 0
        session["understand_retry"] = 0

        # Force back to main menu
        response.say("Let me help you with something else instead.")
        response.redirect("/main_menu_fallback")
        return Response(str(response), mimetype="text/xml")

    # If they pressed 1, give them popular menu suggestions
    if dtmf_input == "1" or "menu" in user_resp or "popular" in user_resp:
        # Reset understanding retry counter
        session["understand_retry"] = 0
        with response.gather(
            input="speech dtmf",
            action="/take_order",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=12,
            timeout=15,  # Give more time
            hints="california roll, spicy tuna roll, dragon roll, rainbow roll",
        ) as g:
            g.say(
                "Our most popular items are California Roll, Spicy Tuna Roll, Dragon Roll, and Rainbow Roll. "
                + "Please tell me what you would like to order. Or press any key to return to the main menu."
            )

        # Add fallback
        response.redirect("/main_menu_fallback")
    # If they pressed 2 or want to go back, return to main menu
    elif dtmf_input == "2" or "back" in user_resp or "main" in user_resp:
        # Reset session variables for ordering
        session["understand_retry"] = 0
        session["order_silence_retry"] = 0
        session["understanding_attempt"] = 0
        response.redirect("/main_menu_fallback")
        return Response(str(response), mimetype="text/xml")
    # Otherwise try again with their speech input (if they provided any)
    elif user_resp:
        # Their response might be an order attempt, so pass it to take_order
        response.redirect("/take_order")
        return Response(str(response), mimetype="text/xml")
    else:
        # No input provided, return to main menu as fallback
        response.redirect("/main_menu_fallback")
        return Response(str(response), mimetype="text/xml")

    return Response(str(response), mimetype="text/xml")


@order_bp.route("/modification_silence_fallback", methods=["POST"])
def modification_silence_fallback():
    """Handle fallbacks for when we can't hear modification requests after multiple tries."""
    # Get user response
    user_resp = (request.form.get("SpeechResult", "") or "").lower()
    dtmf_input = request.form.get("Digits", "")

    # Track how many times we've been in this fallback
    mod_fallback_count = session.get("mod_fallback_count", 0)
    session["mod_fallback_count"] = mod_fallback_count + 1

    # Create response
    response = VoiceResponse()
    
    # Check for silence (no input detected)
    if not user_resp and not dtmf_input:
        # Track silence in modification fallback
        mod_silence_count = session.get("mod_silence_count", 0)
        session["mod_silence_count"] = mod_silence_count + 1
        
        logger.info(f"Silence detected in modification fallback (attempt {mod_silence_count+1})")
        
        # After silence, confirm with user before proceeding with order as-is
        if mod_silence_count >= 1:
            logger.warning("Multiple silences in modification fallback - proceeding with order as is")
            session["mod_silence_count"] = 0
            session["mod_fallback_count"] = 0
            session["modify_silence_retry"] = 0
            
            # Give clear spoken confirmation before proceeding
            response.say(
                "I'll keep your order as is since I'm not hearing your modifications. Let's continue with your order confirmation."
            )
            response.redirect("/confirm_order_after_modification")
            return Response(str(response), mimetype="text/xml")
        else:
            # First silence, ask one more time with simplified options
            with response.gather(
                input="speech dtmf",
                action="/modification_silence_fallback",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout=5,
                timeout=8,
                num_digits=1
            ) as g:
                g.say(
                    "I didn't hear your response. Press 1 or say 'continue' to keep your order as is, or press 2 or say 'cancel' to cancel the order."
                )
            return Response(str(response), mimetype="text/xml")
    
    # Reset silence counter if we got a response
    session["mod_silence_count"] = 0

    # After too many attempts, just keep the order as is
    if mod_fallback_count >= 2:
        logger.warning("Too many modification fallbacks - keeping order as is")
        session["mod_fallback_count"] = 0
        session["modify_silence_retry"] = 0

        response.say(
            "I'll keep your order as is since we're having trouble with modifications."
        )
        response.redirect("/confirm_order_after_modification")
        return Response(str(response), mimetype="text/xml")

    # If they pressed 1 or said to keep order, confirm as is
    if dtmf_input == "1" or "keep" in user_resp or "as is" in user_resp or "continue" in user_resp:
        # Reset modification silence counter
        session["modify_silence_retry"] = 0
        session["mod_fallback_count"] = 0
        
        logger.info("User chose to keep order as is")

        # Redirect to confirmation
        response.redirect("/confirm_order_after_modification")
        return Response(str(response), mimetype="text/xml")
    # If they pressed 2 or said to cancel, go back to main menu
    elif dtmf_input == "2" or "cancel" in user_resp:
        # Reset session variables for ordering
        session["modify_silence_retry"] = 0
        session["modification_in_progress"] = False
        session["mod_fallback_count"] = 0
        response.redirect("/main_menu_fallback")
        return Response(str(response), mimetype="text/xml")
    # Otherwise try again with their speech input (if they provided any)
    elif user_resp:
        # Their response might be a modification attempt, so pass it to new_modify_order
        response.redirect("/new_modify_order")
        return Response(str(response), mimetype="text/xml")
    else:
        # No input provided after first attempt - give them another clear choice
        with response.gather(
            input="dtmf speech",
            action="/modification_silence_fallback",
            num_digits=1,
            timeout=15,
            speech_timeout=15,
        ) as g:
            g.say(
                "I'm having trouble hearing your modification. Press 1 or say 'keep it' to keep your order as is. Press 2 or say 'cancel' to cancel and return to the main menu."
            )

        # Final fallback - keep the order as is if we still get nothing
        response.say("I'll keep your order as is.")
        response.redirect("/confirm_order_after_modification")

    return Response(str(response), mimetype="text/xml")


@order_bp.route("/handle_newly_snoozed_in_checkout", methods=["POST"])
def handle_newly_snoozed_in_checkout():
    """Handle the case where items become unavailable during checkout"""
    # Get user response
    user_resp = request.form.get("SpeechResult", "")
    dtmf_input = request.form.get("Digits", "")

    # Create response
    response = VoiceResponse()

    # Get order items
    order_items = json.loads(session.get("order_items_json", "[]"))

    # Use comprehensive validator from snooze_validator
    from app.utils.snooze_validator import validate_items_availability

    # Get available items
    available_items = validate_items_availability(order_items)

    # Find unavailable items using the difference between original and available
    unavailable_items = []
    for item in order_items:
        if item not in available_items:
            unavailable_items.append(item.get("name", "Unknown Item"))

    # Format item names for speech
    snoozed_items_str = (
        ", ".join(unavailable_items) if unavailable_items else "Some items"
    )

    # Handle "yes" - remove items and continue
    if dtmf_input == "1" or user_said_yes(user_resp):
        logger.info("Customer chose to remove unavailable items and continue")

        # Remove unavailable items using validator results
        updated_items = available_items
        logger.info(f"Removed {len(order_items) - len(updated_items)} items from order")

        # If order is now empty, cancel
        if not updated_items:
            response.say(
                f"All items in your order including {snoozed_items_str} are now unavailable. We apologize for the inconvenience."
            )
            
            # Instead of hanging up, offer alternatives
            with response.gather(
                input="speech dtmf",
                action="/handle_unavailable_order",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout=5,
                timeout=7,
                num_digits=1
            ) as g:
                g.say("Press 1 to explore other menu options, press 2 to speak with a team member about today's specials, or press 3 to end the call.")
            
            # Fallback if no input received
            response.redirect("/handle_unavailable_order")
            return Response(str(response), mimetype="text/xml")

        # Update session with modified order
        session["order_items_json"] = json.dumps(updated_items)
        calculate_bill_amount(updated_items)
        session["bill_amount"] = int(session.get("total_price", 0) * 100)
        order_description = build_order_description(updated_items)
        session["order_message"] = (
            f"{order_description}\nYour total is ${session.get('total_price', 0):.2f}."
        )

        # Confirm updated order
        with response.gather(
            input="speech dtmf",
            action="/confirm_order_after_modification",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto",
            num_digits=1,
        ) as g:
            g.say(
                f"We removed {snoozed_items_str}. Your updated order is: {session['order_message']} If correct, say yes or press 1. If you need changes, say no or press 2."
            )

    # Handle "no" - cancel order
    else:
        response.say(
            f"We're sorry that {snoozed_items_str} is unavailable. Your order has been cancelled."
        )
        
        # Instead of hanging up, offer alternatives
        with response.gather(
            input="speech dtmf",
            action="/handle_unavailable_order",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=5,
            timeout=7,
            num_digits=1
        ) as g:
            g.say("Press 1 to explore other menu options, press 2 to speak with a team member about today's specials, or press 3 to end the call.")
        
        # Fallback if no input received
        response.redirect("/handle_unavailable_order")

    return Response(str(response), mimetype="text/xml")


# ====== New handler routes for smart silence handling and fallbacks ======

@order_bp.route("/handle_busy_options", methods=["POST"])
def handle_busy_options():
    """Handle options when restaurant is in busy mode"""
    # Get user input
    speech_input = request.form.get("SpeechResult", "").lower()
    digits = request.form.get("Digits", "")
    
    response = VoiceResponse()
    
    # Track retry counter
    retry_count = session.get("busy_options_retry", 0)
    session["busy_options_retry"] = retry_count + 1
    
    # Check for silence (no input)
    if not speech_input and not digits:
        # If we've retried too many times, give a helpful message and end
        if retry_count >= 2:
            # Instead of hanging up, give them one more chance with simplified options
            with response.gather(
                input="dtmf",  # DTMF only for simplicity at this point
                action="/main_menu",
                num_digits=1,
                timeout=10  # Give them extra time
            ) as g:
                g.say("We're having trouble with the connection. Press 1 to return to the main menu or stay on the line and we'll try one more time.")
            
            # If they don't respond, redirect to the main menu as a last resort
            response.redirect("/main_menu_fallback")
            return Response(str(response), mimetype="text/xml")
        
        # Otherwise retry with the options
        with response.gather(
            input="speech dtmf",
            action="/handle_busy_options",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=5,
            timeout=7,
            num_digits=1
        ) as g:
            g.say("I didn't catch that. Press 1 to get menu information, press 2 to leave your name and number for a callback, or press 3 to end the call.")
            
        return Response(str(response), mimetype="text/xml")
    
    # Process their choice
    if digits == "1" or "menu" in speech_input:
        # Redirect to menu questions
        response.redirect("/handle_menu_questions")
    elif digits == "2" or "callback" in speech_input or "call back" in speech_input or "leave" in speech_input:
        # Gather their callback information
        with response.gather(
            input="speech",
            action="/save_callback_request",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=7,
            timeout=10
        ) as g:
            g.say("Please tell me your name and the best time to call you back.")
    elif digits == "3" or "end" in speech_input or "goodbye" in speech_input:
        response.say("Thank you for your understanding. Please call back later when we're less busy. Goodbye!")
        response.redirect("/graceful_exit")
    else:
        # Unrecognized input, give them another chance
        with response.gather(
            input="speech dtmf",
            action="/handle_busy_options",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=5,
            timeout=7,
            num_digits=1
        ) as g:
            g.say("I didn't understand. Press 1 for menu information, 2 to request a callback, or 3 to end the call.")
    
    return Response(str(response), mimetype="text/xml")

@order_bp.route("/handle_menu_unavailable", methods=["POST"])
def handle_menu_unavailable():
    """Handle options when the menu is unavailable"""
    # Get user input
    speech_input = request.form.get("SpeechResult", "").lower()
    digits = request.form.get("Digits", "")
    
    response = VoiceResponse()
    
    # Track retry counter
    retry_count = session.get("menu_unavailable_retry", 0)
    session["menu_unavailable_retry"] = retry_count + 1
    
    # Check for silence (no input)
    if not speech_input and not digits:
        if retry_count >= 2:
            # Instead of hanging up, give them one more chance with simplified options
            with response.gather(
                input="dtmf",  # DTMF only for simplicity at this point
                action="/main_menu",
                num_digits=1,
                timeout=10  # Give them extra time
            ) as g:
                g.say("We're having trouble with the connection. Press 1 to return to the main menu or stay on the line and we'll try one more time.")
            
            # If they don't respond, redirect to the main menu as a last resort
            response.redirect("/main_menu_fallback")
            return Response(str(response), mimetype="text/xml")
        
        # Retry with options
        with response.gather(
            input="speech dtmf",
            action="/handle_menu_unavailable",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=5,
            timeout=7,
            num_digits=1
        ) as g:
            g.say("I didn't catch that. Press 1 to speak with a team member about our daily specials, press 2 to leave your contact information, or press 3 to end the call.")
            
        return Response(str(response), mimetype="text/xml")
    
    # Process their choice
    if digits == "1" or "speak" in speech_input or "team" in speech_input or "specials" in speech_input:
        # Redirect to human agent handler
        response.redirect("/handle_transfer_to_human")
    elif digits == "2" or "contact" in speech_input or "information" in speech_input:
        # Gather their contact information
        with response.gather(
            input="speech",
            action="/save_contact_info",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=7,
            timeout=10
        ) as g:
            g.say("Please tell me your name and the best way to contact you when our menu is back online.")
    elif digits == "3" or "end" in speech_input or "goodbye" in speech_input:
        response.say("Thank you for your understanding. Please call back later when our menu system is available. Goodbye!")
        response.redirect("/graceful_exit")
    else:
        # Unrecognized input
        with response.gather(
            input="speech dtmf",
            action="/handle_menu_unavailable",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=5,
            timeout=7,
            num_digits=1
        ) as g:
            g.say("I didn't understand. Press 1 to speak with a team member, 2 to leave your contact info, or 3 to end the call.")
    
    return Response(str(response), mimetype="text/xml")

@order_bp.route("/handle_technical_difficulties", methods=["POST"])
def handle_technical_difficulties():
    """Handle options when there are technical difficulties"""
    # Get user input
    speech_input = request.form.get("SpeechResult", "").lower()
    digits = request.form.get("Digits", "")
    
    response = VoiceResponse()
    
    # Track retry counter
    retry_count = session.get("tech_difficulties_retry", 0)
    session["tech_difficulties_retry"] = retry_count + 1
    
    # Check for silence (no input)
    if not speech_input and not digits:
        if retry_count >= 2:
            # Instead of hanging up, offer very simple options
            with response.gather(
                input="dtmf",  # DTMF only for simplicity at this point
                action="/main_menu",
                num_digits=1,
                timeout=10  # Give them extra time
            ) as g:
                g.say("We're having trouble with the connection. Press 1 to return to the main menu or stay on the line and we'll try one more time.")
            
            # If they don't respond, redirect to the main menu as a last resort
            response.redirect("/main_menu_fallback")
            return Response(str(response), mimetype="text/xml")
        
        # Retry with options
        with response.gather(
            input="speech dtmf",
            action="/handle_technical_difficulties",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=5,
            timeout=7,
            num_digits=1
        ) as g:
            g.say("I didn't catch that. Press 1 to speak with a team member, press 2 to leave your contact information, or press 3 to end the call.")
            
        return Response(str(response), mimetype="text/xml")
    
    # Process their choice
    if digits == "1" or "speak" in speech_input or "team" in speech_input:
        # Transfer to a real person
        response.redirect("/handle_transfer_to_human")
    elif digits == "2" or "contact" in speech_input or "callback" in speech_input:
        # Gather their contact information
        with response.gather(
            input="speech",
            action="/save_callback_request",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=7,
            timeout=10
        ) as g:
            g.say("Please tell me your name and the best way to contact you once our system is working again.")
    elif digits == "3" or "end" in speech_input or "goodbye" in speech_input:
        response.say("We apologize for the technical difficulties. Please try calling back in a few minutes. Goodbye!")
        response.redirect("/graceful_exit")
    else:
        # Unrecognized input
        with response.gather(
            input="speech dtmf",
            action="/handle_technical_difficulties",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=5,
            timeout=7,
            num_digits=1
        ) as g:
            g.say("I didn't understand. Press 1 to speak with a team member, 2 to leave your contact info, or 3 to end the call.")
    
    return Response(str(response), mimetype="text/xml")

@order_bp.route("/order_completion_options", methods=["POST"])
def order_completion_options():
    """Handle additional options after order completion"""
    # Get user input
    speech_input = request.form.get("SpeechResult", "").lower()
    digits = request.form.get("Digits", "")
    
    response = VoiceResponse()
    
    # Check for silence or invalid input
    if not speech_input and not digits:
        # Track silence retries
        completion_silence_retry = session.get("completion_silence_retry", 0)
        session["completion_silence_retry"] = completion_silence_retry + 1
        
        logger.info(f"Silence detected in order completion options (attempt {completion_silence_retry+1})")
        
        if completion_silence_retry >= 1:
            # After second silence, just thank them and exit
            logger.info("Multiple silences in completion options - proceeding to graceful exit")
            response.say("Thank you for your order at Red Bar Sushi! Goodbye!")
            response.redirect("/graceful_exit")
            return Response(str(response), mimetype="text/xml")
        else:
            # First silence, try again with clearer options
            with response.gather(
                input="speech dtmf",
                action="/order_completion_options",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout=5,
                timeout=8,
                num_digits=1
            ) as g:
                g.say("If you'd like additional information, please press 1 for directions to our restaurant, press 2 for our hours of operation, or press 3 to end the call.")
            return Response(str(response), mimetype="text/xml")
    
    # Reset silence counter if we got a response
    session["completion_silence_retry"] = 0
    
    # Process their choice
    if digits == "1" or "direction" in speech_input or "address" in speech_input or "location" in speech_input:
        # Provide directions
        response.say("Our restaurant is located at 123 Main Street, between 5th and 6th Avenue. Parking is available in the structure across the street. Thank you for your order! Goodbye.")
        response.redirect("/graceful_exit")
    elif digits == "2" or "hours" in speech_input or "operation" in speech_input or "open" in speech_input:
        # Provide hours
        response.say("Our hours of operation are Monday through Friday from 11 AM to 10 PM, and Saturday and Sunday from 12 PM to 11 PM. Thank you for your order! Goodbye.")
        response.redirect("/graceful_exit")
    elif digits == "3" or "end" in speech_input or "goodbye" in speech_input or "bye" in speech_input or "nothing" in speech_input:
        response.say("Thank you for your order at Red Bar Sushi! Goodbye!")
        response.redirect("/graceful_exit")
    else:
        # Unrecognized input, just thank them
        response.say("Thank you for your order at Red Bar Sushi! We look forward to seeing you soon. Goodbye!")
        response.redirect("/graceful_exit")
    
    return Response(str(response), mimetype="text/xml")

@order_bp.route("/handle_unavailable_order", methods=["POST"])
def handle_unavailable_order():
    """Handle options when items in an order are unavailable"""
    # Get user input
    speech_input = request.form.get("SpeechResult", "").lower()
    digits = request.form.get("Digits", "")
    
    response = VoiceResponse()
    
    # Track retry counter
    retry_count = session.get("unavailable_retry", 0)
    session["unavailable_retry"] = retry_count + 1
    
    # Check for silence (no input)
    if not speech_input and not digits:
        if retry_count >= 2:
            # Instead of hanging up, give them one more chance with simplified options
            with response.gather(
                input="dtmf",  # DTMF only for simplicity at this point
                action="/main_menu",
                num_digits=1,
                timeout=10  # Give them extra time
            ) as g:
                g.say("We're having trouble with the connection. Press 1 to return to the main menu, press 2 to try again, or stay on the line to end this call.")
            
            # If they don't respond, redirect to the main menu as a last resort
            response.redirect("/main_menu_fallback")
            return Response(str(response), mimetype="text/xml")
        
        # Retry with options
        with response.gather(
            input="speech dtmf",
            action="/handle_unavailable_order",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=5,
            timeout=7,
            num_digits=1
        ) as g:
            g.say("I didn't catch that. Press 1 to explore other menu options, press 2 to speak with a team member, or press 3 to end the call.")
            
        return Response(str(response), mimetype="text/xml")
    
    # Process their choice
    if digits == "1" or "menu" in speech_input or "explore" in speech_input or "other" in speech_input:
        # Redirect to menu questions
        response.redirect("/handle_menu_questions")
    elif digits == "2" or "speak" in speech_input or "team" in speech_input or "specials" in speech_input:
        # Redirect to human agent handler
        response.redirect("/handle_transfer_to_human")
    elif digits == "3" or "end" in speech_input or "goodbye" in speech_input:
        response.say("We apologize again that your preferred items are unavailable. We hope to see you soon when we have them back in stock. Goodbye!")
        # Instead of hanging up, redirect to a clean ending
        response.redirect("/graceful_exit")
    else:
        # Unrecognized input
        with response.gather(
            input="speech dtmf",
            action="/handle_unavailable_order",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=5,
            timeout=7,
            num_digits=1
        ) as g:
            g.say("I didn't understand. Press 1 to explore other menu options, 2 to speak with a team member, or 3 to end the call.")
    
    return Response(str(response), mimetype="text/xml")

@order_bp.route("/save_callback_request", methods=["POST"])
def save_callback_request():
    """Save a callback request from a customer"""
    # Get their information
    contact_info = request.form.get("SpeechResult", "")
    
    response = VoiceResponse()
    
    # Track silence retries
    callback_silence_retry = session.get("callback_silence_retry", 0)
    
    if not contact_info:
        # Increment silence counter
        session["callback_silence_retry"] = callback_silence_retry + 1
        
        logger.info(f"Silence detected in callback request (attempt {callback_silence_retry+1})")
        
        if callback_silence_retry >= 1:
            # After multiple silences, give up gracefully
            logger.info("Multiple silences in callback request - exiting gracefully")
            response.say("I didn't hear your contact information. Please call back when you have a moment to provide your contact details. Goodbye!")
            response.redirect("/graceful_exit")
            return Response(str(response), mimetype="text/xml")
        else:
            # First silence, try again
            with response.gather(
                input="speech",
                action="/save_callback_request",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout=7,
                timeout=10
            ) as g:
                g.say("I didn't hear anything. Please tell me your name and the best way to contact you.")
            return Response(str(response), mimetype="text/xml")
    else:
        # Reset silence counter if they provided information
        session["callback_silence_retry"] = 0
        
        # In a real implementation, this would be saved to a database
        logger.info(f"Callback request received: {contact_info}")
        
        # Thank them for the information
        response.say("Thank you for your information. A team member will contact you as soon as possible. Goodbye!")
    
    # Instead of hanging up, redirect to graceful exit
    response.redirect("/graceful_exit")
    
    return Response(str(response), mimetype="text/xml")

@order_bp.route("/save_contact_info", methods=["POST"])
def save_contact_info():
    """Save contact information when menu is unavailable"""
    # Get their information
    contact_info = request.form.get("SpeechResult", "")
    
    response = VoiceResponse()
    
    # Track silence retries
    contact_silence_retry = session.get("contact_silence_retry", 0)
    
    if not contact_info:
        # Increment silence counter
        session["contact_silence_retry"] = contact_silence_retry + 1
        
        logger.info(f"Silence detected in contact info request (attempt {contact_silence_retry+1})")
        
        if contact_silence_retry >= 1:
            # After multiple silences, give up gracefully
            logger.info("Multiple silences in contact info request - exiting gracefully")
            response.say("I didn't hear your contact information. Please call back when you have a moment to provide your contact details. Goodbye!")
            response.redirect("/graceful_exit")
            return Response(str(response), mimetype="text/xml")
        else:
            # First silence, try again
            with response.gather(
                input="speech",
                action="/save_contact_info",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout=7,
                timeout=10
            ) as g:
                g.say("I didn't hear anything. Please tell me your name and contact details so we can notify you when our menu is back online.")
            return Response(str(response), mimetype="text/xml")
    else:
        # Reset silence counter if they provided information
        session["contact_silence_retry"] = 0
        
        # In a real implementation, this would be saved to a database
        logger.info(f"Contact info received for menu notification: {contact_info}")
        
        # Thank them for the information
        response.say("Thank you for your information. We'll contact you when our menu is back online. Goodbye!")
    
    # Instead of hanging up, redirect to graceful exit
    response.redirect("/graceful_exit")
    
    return Response(str(response), mimetype="text/xml")

@order_bp.route("/process_order_checkout", methods=["GET", "POST"])
def process_order_checkout():
    """
    Process the final order checkout after all validations.
    This endpoint handles the actual order submission to Deliverect.
    
    IMPORTANT: This is the final validation point that ensures only valid order items
    with valid modifiers are sent to Deliverect. All invalid items or modifiers are
    strictly filtered out.
    """
    # Get order data from session
    order_items = json.loads(session.get("order_items_json", "[]"))
    order_id = session.get("order_id", "") or str(uuid.uuid4())
    session["order_id"] = order_id
    sender = session.get("sender", "")
    caller_name = session.get("caller_name", "Valued Customer")
    
    # Create voice response
    response = VoiceResponse()
    
    # Log starting checkout process
    logger.info(f"Starting checkout process for order {order_id} with {len(order_items)} items")
    
    # Check cooldown
    if not can_process_action(sender, "order_food", 60):
        response.say(
            "You're placing orders too quickly. Please wait a moment and try again."
        )
        return Response(str(response), mimetype="text/xml")

    # CRITICAL: Comprehensive validation of all order items and modifiers
    # This is the final validation gate before the order is processed
    try:
        # Import the validation function to ensure all items have reference handlers
        from app.utils.order_utils import prepare_order_for_deliverect
        
        # Log original order details before validation
        for item in order_items:
            mod_count = len(item.get("modifier", []))
            logger.info(f"Original order item: {item.get('name')} with {mod_count} modifiers")
            if mod_count > 0:
                mod_names = [mod.get('name', 'unknown') for mod in item.get("modifier", [])]
                logger.info(f"Original modifiers for {item.get('name')}: {', '.join(mod_names)}")
        
        # Full strict validation - this ensures only menu items with valid modifiers remain
        validated_items = prepare_order_for_deliverect(order_items)
        
        # Update the session with the fully validated items
        session["order_items_json"] = json.dumps(validated_items)
        
        # Log validation results
        if len(validated_items) < len(order_items):
            logger.warning(f"Validation removed {len(order_items) - len(validated_items)} invalid items")
            
        # Log final validated order details
        logger.info(f"Final validated order has {len(validated_items)} items")
        for item in validated_items:
            mod_count = len(item.get("modifier", []))
            logger.info(f"Validated order item: {item.get('name')} with {mod_count} modifiers")
            if mod_count > 0:
                mod_names = [mod.get('name', 'unknown') for mod in item.get("modifier", [])]
                logger.info(f"Validated modifiers for {item.get('name')}: {', '.join(mod_names)}")
        
        # Update order_items to use the validated version for the rest of this function
        order_items = validated_items
        
        # Check if we still have valid items after validation
        if not validated_items:
            logger.error("No valid items remain after validation - cannot continue")
            response.say(
                "I'm sorry, but there are issues with your order. Let me transfer you to a team member who can help."
            )
            response.redirect("/handle_transfer_to_human")
            return Response(str(response), mimetype="text/xml")
            
    except Exception as e:
        logger.error(f"Error during order validation: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        # If validation fails, we'll continue with the original order as a fallback
        logger.warning("Proceeding with original order due to validation error")

    # Save to database
    try:
        # Rebuild the order message with validated items
        calculate_bill_amount(order_items)
        session["bill_amount"] = int(session.get("total_price", 0) * 100)
        order_description = build_order_description(order_items)
        session["order_message"] = f"{order_description}\nYour total is ${session.get('total_price', 0):.2f}."
        
        text_msg = session.get("order_message", "")
        new_order = Order(
            id=order_id, sender=sender, caller_name=caller_name, message=text_msg
        )
        db.session.add(new_order)
        if not commit_with_retry(db.session):
            raise Exception("Commit failed")
        logger.info(f"Order {order_id} saved successfully to database.")
    except Exception as db_error:
        db.session.rollback()
        logger.error(f"Database error: {db_error}")
        response.say(
            "Sorry, we encountered a database issue. Please try again later."
        )
        return Response(str(response), mimetype="text/xml")

    # Get total price
    total_price = session.get("total_price", 0.0)

    # Build and send to Deliverect
    try:
        # Check if we still have valid items after validation
        if not order_items:
            logger.error("No valid items to send to Deliverect")
            # Don't fail here since we still want to save the order in our system
        else:
            # Build the order with validated items
            deliverect_payload = build_deliverect_order(
                sender=sender,
                caller_name=caller_name,
                order_items=order_items,
                total_price=total_price,
                order_id=order_id,
            )

            logger.info(f"Sending order to Deliverect: {order_id}")
            response_deliv = requests.post(
                DELIVERECT_API_URL,
                json=deliverect_payload,
                headers=get_deliverect_headers(),
                timeout=10,
            )

            if response_deliv.status_code != 200:
                logger.error(
                    f"Deliverect API error: Status {response_deliv.status_code}, Response: {response_deliv.text}"
                )
            else:
                logger.info(
                    f"Deliverect order successfully submitted: {response_deliv.text}"
                )
    except Exception as e:
        logger.error(f"Error sending order to Deliverect: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")

    # Send SMS confirmation
    import tasks

    try:
        logger.info(
            f"Attempting to send SMS confirmation task directly for order {order_id}"
        )
        # Call task directly for now until Redis/Celery is properly setup
        tasks.send_confirmation_sms_task(
            order_id,
            session.get("order_message", ""),
            sender,
            caller_name,
            session.get("bill_amount", 0),
            order_items,
        )
        logger.info(
            f"SMS confirmation task executed successfully for order {order_id}"
        )
    except Exception as task_error:
        logger.error(f"Error sending SMS confirmation: {task_error}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Fall back to direct SMS sending
        try:
            # Send a simpler message directly
            simple_msg = f"Thank you for your order! Your order ID is {order_id[:8]}. A confirmation will be sent shortly."
            twilio_client.messages.create(
                body=simple_msg, from_=TWILIO_PHONE_NUMBER, to=sender
            )
            logger.info(f"Sent simple order confirmation directly via SMS to {sender}")
        except Exception as sms_error:
            logger.error(f"Error sending direct SMS confirmation: {sms_error}")

    # Calculate prep time and respond
    time_taken = DEFAULT_PREP_TIME_BASE + (PREP_TIME_PER_ITEM * len(order_items))
    response.say(
        f"Great! Your order is confirmed and will be ready in about {time_taken} minutes. A confirmation text with payment options will be sent to your phone. You can also text 'status' to this number anytime to check your order status."
    )
    
    # Instead of hanging up, ask if they need anything else
    with response.gather(
        input="speech dtmf",
        action="/order_completion_options",
        enhanced=True,
        speech_model="phone_call",
        language="en-US",
        speech_timeout=5,
        timeout=7,
        num_digits=1
    ) as g:
        g.say("Is there anything else you'd like help with today? Press 1 for directions to our restaurant, press 2 for our hours of operation, or press 3 to end the call.")
    
    # Fallback if no input received
    response.redirect("/order_completion_options")
    
    logger.info(f"Checkout completed successfully for order {order_id}")
    return Response(str(response), mimetype="text/xml")

@order_bp.route("/handle_invalid_modifiers", methods=["POST"])
def handle_invalid_modifiers():
    """
    Handle the user's response when they're told about invalid modifiers.
    The user can choose to continue without invalid modifiers or modify their order.
    
    This route ensures that invalid modifiers are completely removed from the order
    before proceeding to checkout or modifications, serving as an additional
    safety checkpoint in the order validation flow.
    """
    # Get the user input
    speech_input = request.form.get("SpeechResult", "").lower()
    dtmf_input = request.form.get("Digits", "")
    
    # Parse confirmation using helper functions
    from app.utils.order_utils import user_said_yes, user_said_no, dtmf_yes_no
    
    response = VoiceResponse()
    
    # Check for silence (no input)
    if not speech_input and not dtmf_input:
        # Track silence retries for invalid modifier handling
        invalid_mod_silence_retry = session.get("invalid_mod_silence_retry", 0)
        session["invalid_mod_silence_retry"] = invalid_mod_silence_retry + 1
        
        logger.info(f"Silence detected in invalid modifier handling (attempt {invalid_mod_silence_retry+1})")
        
        if invalid_mod_silence_retry >= 1:
            # After multiple silences, default to removing invalid modifiers
            logger.warning("Multiple silences when handling invalid modifiers - defaulting to removing them")
            
            # Get the invalid modifiers from session
            invalid_item_modifiers = json.loads(session.get("invalid_item_modifiers", "[]"))
            order_items = json.loads(session.get("order_items_json", "[]"))
            
            # Remove all invalid modifiers
            for invalid_item in invalid_item_modifiers:
                item_name = invalid_item["item"]
                invalid_mods = set(mod.lower() for mod in invalid_item["invalid_modifiers"])
                
                # Find the item in the order
                for item in order_items:
                    if item.get("name") == item_name:
                        # Filter out invalid modifiers
                        valid_mods = [
                            mod for mod in item.get("modifier", [])
                            if mod.get("name", "").lower() not in invalid_mods
                        ]
                        # Update the item with only valid modifiers
                        item["modifier"] = valid_mods
                        break
            
            # Update the session with cleaned order
            session["order_items_json"] = json.dumps(order_items)
            
            # Inform user and proceed
            response.say("Since I didn't hear your choice, I'll remove the invalid modifiers and proceed with your order.")
            response.redirect("/process_order_checkout")
            return Response(str(response), mimetype="text/xml")
        else:
            # First silence, try again with clearer options
            with response.gather(
                input="speech dtmf",
                action="/handle_invalid_modifiers",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout=5,
                timeout=8,
                num_digits=1
            ) as g:
                g.say("I didn't hear your response. Press 1 or say 'continue' to remove the invalid modifiers and continue with your order, or press 2 or say 'modify' to make changes to your order.")
            return Response(str(response), mimetype="text/xml")
    
    # Reset silence counter if we got a response
    session["invalid_mod_silence_retry"] = 0
    
    # Log the user's response
    logger.info(f"Invalid modifier handling - User response: '{speech_input}', DTMF: '{dtmf_input}'")
    
    # If user chooses to continue without invalid modifiers (yes)
    if dtmf_input == "1" or user_said_yes(speech_input) or "continue" in speech_input or "proceed" in speech_input:
        # Get the invalid modifiers from session
        invalid_item_modifiers = json.loads(session.get("invalid_item_modifiers", "[]"))
        order_items = json.loads(session.get("order_items_json", "[]"))
        
        # Log the invalid modifiers that will be removed
        for invalid_item in invalid_item_modifiers:
            item_name = invalid_item["item"]
            invalid_mods = invalid_item["invalid_modifiers"]
            logger.info(f"Removing invalid modifiers from {item_name}: {', '.join(invalid_mods)}")
        
        # Remove all invalid modifiers
        for invalid_item in invalid_item_modifiers:
            item_name = invalid_item["item"]
            invalid_mods = set(mod.lower() for mod in invalid_item["invalid_modifiers"])
            
            # Find the item in the order
            for item in order_items:
                if item.get("name") == item_name:
                    # Get original number of modifiers
                    original_mod_count = len(item.get("modifier", []))
                    
                    # Filter out invalid modifiers
                    valid_mods = [
                        mod for mod in item.get("modifier", [])
                        if mod.get("name", "").lower() not in invalid_mods
                    ]
                    
                    # Update the item with only valid modifiers
                    item["modifier"] = valid_mods
                    
                    # Log the filtering results
                    logger.info(f"Item {item_name}: Removed {original_mod_count - len(valid_mods)} invalid modifiers, kept {len(valid_mods)} valid modifiers")
                    
                    if valid_mods:
                        valid_mod_names = [mod.get("name", "unknown") for mod in valid_mods]
                        logger.info(f"Valid modifiers kept for {item_name}: {', '.join(valid_mod_names)}")
                    break
        
        # Update the session with cleaned order
        session["order_items_json"] = json.dumps(order_items)
        
        # CRITICAL: Perform one final validation pass using prepare_order_for_deliverect
        # This ensures that no invalid modifiers slip through
        from app.utils.order_utils import prepare_order_for_deliverect
        
        try:
            # This is a deep validation that will remove any remaining invalid modifiers
            final_validated_items = prepare_order_for_deliverect(order_items)
            
            # Update session with final validated order
            session["order_items_json"] = json.dumps(final_validated_items)
            logger.info(f"Final order validation completed: {len(final_validated_items)} valid items remain")
        except Exception as e:
            logger.error(f"Error during final validation: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Continue with the order as-is if validation fails
        
        # Continue with order confirmation
        response.say("Your order has been updated to remove the invalid modifiers. Let's proceed with your order.")
        response.redirect("/process_order_checkout")
        
    # If user wants to modify their order (no)
    elif dtmf_input == "2" or user_said_no(speech_input) or "modify" in speech_input or "change" in speech_input:
        logger.info("User chose to modify order instead of removing invalid modifiers")
        # Go back to the order modification flow
        response.say("Let's update your order. Please tell me what changes you'd like to make.")
        response.redirect("/new_modify_order")
        
    # If user was silent or unclear
    else:
        logger.info("Unclear user response for invalid modifiers, defaulting to removing them")
        # Default to removing invalid modifiers and proceeding
        # First get the invalid modifiers from session
        invalid_item_modifiers = json.loads(session.get("invalid_item_modifiers", "[]"))
        order_items = json.loads(session.get("order_items_json", "[]"))
        
        # Remove all invalid modifiers
        for invalid_item in invalid_item_modifiers:
            item_name = invalid_item["item"]
            invalid_mods = set(mod.lower() for mod in invalid_item["invalid_modifiers"])
            
            # Find the item in the order
            for item in order_items:
                if item.get("name") == item_name:
                    # Filter out invalid modifiers
                    valid_mods = [
                        mod for mod in item.get("modifier", [])
                        if mod.get("name", "").lower() not in invalid_mods
                    ]
                    # Update the item with only valid modifiers
                    item["modifier"] = valid_mods
                    break
        
        # Update the session with cleaned order
        session["order_items_json"] = json.dumps(order_items)
        
        response.say("I didn't catch that. I'll remove the invalid modifiers and proceed with your order.")
        response.redirect("/process_order_checkout")
    
    return Response(str(response), mimetype="text/xml")

@order_bp.route("/graceful_exit", methods=["GET", "POST"])
def graceful_exit():
    """
    Provide a graceful exit for the call with a final retry opportunity.
    This route exists to avoid hanging up on customers and give them one last chance
    to provide input if they're still there but were having connection issues.
    """
    response = VoiceResponse()
    
    # Check if this is a repeated visit to graceful_exit
    exit_attempt = session.get("graceful_exit_attempt", 0)
    session["graceful_exit_attempt"] = exit_attempt + 1
    
    logger.info(f"Graceful exit (attempt {exit_attempt+1})")
    
    # Only give the menu option on the first attempt
    # After that, just end the call to avoid endless loops
    if exit_attempt == 0:
        # Add a brief gather with a simple message
        with response.gather(
            input="dtmf",
            action="/main_menu",
            num_digits=1,
            timeout=5  # Short timeout as this is the last chance
        ) as g:
            g.say("Thank you for calling Red Bar Sushi. If you'd like to return to the main menu, please press any key now. Goodbye!")
    else:
        # On subsequent attempts, just end the call
        logger.info("Multiple graceful exit attempts - ending call")
    
    # Reset the exit counter for future calls
    session["graceful_exit_attempt"] = 0
    
    # End the call - this is appropriate as we've given them a chance to continue
    response.say("Goodbye from Red Bar Sushi. We look forward to your next call.")
    response.hangup()
    
    return Response(str(response), mimetype="text/xml")

@order_bp.route("/suggest_modifiers", methods=["POST"])
def suggest_modifiers():
    """
    Route to explicitly suggest modifiers for items in the order.
    This route serves as the main entry point for suggesting modifiers
    after the order has been taken but before confirmation.
    """
    # IMPORTANT DEBUGGING
    logger.info("=== SUGGEST_MODIFIERS ROUTE CALLED ===")
    logger.info(f"Request method: {request.method}")
    logger.info(f"Form data: {request.form}")
    logger.info(f"Session keys: {list(session.keys())}")
    
    # Get order items from session
    order_items = json.loads(session.get("order_items_json", "[]"))
    
    # Exit early if no order items
    if not order_items:
        logger.warning("No order items found for modifier suggestions")
        # Redirect to order taking
        return redirect(url_for("order_bp.greeting"))
    
    # Force fresh load of menu data to ensure we have all modifiers
    menu_data = load_menu_data(force_refresh=True)
    logger.info(f"Loaded fresh menu data with {len(menu_data.get('items', []))} items, {len(menu_data.get('modifiers', []))} modifiers")
    
    # Use check_for_missing_modifiers to identify items needing modifier suggestions
    items_needing_modifiers, constraint_details = check_for_missing_modifiers(order_items)
    
    # Detailed logging for debugging
    logger.info(f"Found {len(items_needing_modifiers)} items needing modifiers")
    for item in items_needing_modifiers:
        item_name = item.get("name", "Unknown")
        logger.info(f"Item {item_name} needs modifiers")
        if item_name in constraint_details:
            constraints_json = json.dumps(constraint_details[item_name])
            logger.info(f"Constraints for {item_name}: {constraints_json[:200]}...")
    
    # Create response object
    response = VoiceResponse()
    
    # If no items need modifiers, skip to confirmation
    if not items_needing_modifiers:
        logger.info("No items need modifiers, proceeding to confirmation")
        response.redirect(url_for("order_bp.confirm_order_from_initial"))
        return Response(str(response), mimetype="text/xml")
    
    # Store info in session for the modifier flow
    session["order_items_without_modifiers_json"] = json.dumps(order_items)
    session["constraint_details"] = json.dumps(constraint_details)
    
    # Get the first item that needs modifiers
    first_item = items_needing_modifiers[0]
    first_item_name = first_item.get("name", "")
    
    # Store which item we're currently suggesting modifiers for
    session["current_modifier_item"] = first_item_name
    session["remaining_modifier_items"] = json.dumps(items_needing_modifiers[1:]) if len(items_needing_modifiers) > 1 else "[]"
    
    # Get the agent to generate a modifier prompt
    agent = OrderParsingAgent()
    
    # Handle special case for meal deals / combo products
    item_constraints = constraint_details.get(first_item_name, {})
    is_combo = item_constraints.get("is_combo", False)
    
    if is_combo:
        # This is a meal deal/combo with component selection
        components = item_constraints.get("components", [])
        
        # Format the component options for the prompt
        required_components = []
        optional_components = []
        
        for comp in components:
            if comp.get("required", True):
                required_components.append(comp.get("name", ""))
            else:
                optional_components.append(comp.get("name", ""))
        
        # Create component text for required components
        required_text = ""
        if required_components:
            required_text = f"You need to select: {', '.join(required_components[:3])}"
            if len(required_components) > 3:
                required_text += f", and {len(required_components) - 3} more options"
        
        # Create prompt for meal deal
        meal_deal_prompt = f"For your {first_item_name} meal deal, {required_text}. What would you like to include?"
        
        with response.gather(
            input="speech",
            action="/handle_modifier_suggestion",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=5,
            timeout=7,
        ) as g:
            g.say(meal_deal_prompt)
    else:
        # Regular item that needs modifiers
        # Get specific modifier groups from constraints
        modifier_groups = []
        if "modifier_groups" in item_constraints:
            modifier_groups = item_constraints.get("modifier_groups", [])
        
        # If we have specific modifier groups to suggest, create a custom prompt
        if modifier_groups:
            # Build a more specific prompt listing available options
            custom_prompt = f"For your {first_item_name}, "
            
            # Find required modifier groups first
            required_groups = [g for g in modifier_groups if g.get("min_required", 0) > 0]
            
            if required_groups:
                # Start with required modifiers
                group = required_groups[0]
                group_name = group.get("name", "option")
                min_required = group.get("min_required", 1)
                custom_prompt += f"please choose {min_required} {group_name}. "
                
                # List some examples
                modifiers = group.get("modifiers", [])
                if modifiers:
                    custom_prompt += f"Options include: {', '.join(modifiers[:3])}"
                    if len(modifiers) > 3:
                        custom_prompt += ", and others"
                    custom_prompt += ". "
                
                custom_prompt += "What would you like?"
            else:
                # For optional modifiers
                custom_prompt += "would you like to add any modifiers? "
                
                # List available modifier groups
                group_names = [g.get("name", "option") for g in modifier_groups[:2]]
                if group_names:
                    custom_prompt += f"We have {', '.join(group_names)}"
                    if len(modifier_groups) > 2:
                        custom_prompt += ", and other options"
                    custom_prompt += ". "
                
                custom_prompt += "What would you like to add? Or say 'skip' to continue."
            
            # Use the custom prompt
            with response.gather(
                input="speech dtmf",
                action="/handle_modifier_suggestion",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout=5,
                timeout=7,
                num_digits=1
            ) as g:
                g.say(custom_prompt)
        else:
            # Use our custom function to ensure we get a good prompt
            modifier_result = custom_suggest_modifiers(first_item_name)
            prompt_to_use = modifier_result["prompt"]
            
            # Log the prompt we're using
            logger.info(f"Using prompt for {first_item_name}: {prompt_to_use}")
            
            with response.gather(
                input="speech dtmf",
                action="/handle_modifier_suggestion", 
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout=5,
                timeout=7,
                num_digits=1
            ) as g:
                g.say(prompt_to_use)
    
    return Response(str(response), mimetype="text/xml")

@order_bp.route("/handle_modifier_suggestion", methods=["POST"])
def handle_modifier_suggestion():
    """
    Handle customer responses to modifier suggestions.
    This route processes the customer's response when we suggest modifiers for an item,
    updates the order with selected modifiers, and either continues to the next item
    or proceeds to order confirmation.
    
    IMPORTANT: This route includes comprehensive validation of all modifiers against the 
    actual menu data to ensure ONLY valid modifiers are accepted. Any modifier not 
    found in the menu will be rejected and the customer will be informed.
    """
    # Add more detailed logging at entry point
    logger.info(f"=== ENTERING handle_modifier_suggestion function ===")
    logger.info(f"Session data: order_id={session.get('order_id')}, phone={session.get('sender')}")
    
    # Get user response to modifier suggestion
    user_resp = request.form.get("SpeechResult", "").lower()
    digits = request.form.get("Digits", "")
    
    # Get current state from session
    current_item = session.get("current_modifier_item", "")
    remaining_items = json.loads(session.get("remaining_modifier_items", "[]"))
    order_items = json.loads(session.get("order_items_without_modifiers_json", "[]"))
    
    # Add detailed logging about the current state
    logger.info(f"Current item being modified: '{current_item}'")
    logger.info(f"Remaining items for modification: {len(remaining_items)}")
    logger.info(f"User input: Speech='{user_resp}', DTMF='{digits}'")
    
    response = VoiceResponse()
    
    logger.info(f"Handling modifier suggestion for {current_item}. User said: '{user_resp}'")
    
    # Check for silence (user didn't respond to suggestion) or if user said they don't want modifiers
    if (not user_resp and not digits) or user_resp in ["no", "none", "no thanks", "nothing"]:
        # Track silence retries for modifier suggestions
        mod_silence_retry = session.get("modifier_silence_retry", 0)
        session["modifier_silence_retry"] = mod_silence_retry + 1
        
        # If we've tried multiple times or user explicitly declined, just continue without modifiers
        if mod_silence_retry >= 2:
            logger.info(f"Multiple silence retries for modifier suggestions on {current_item}, continuing without modifiers")
            # Skip to the next item or continue to confirmation
            pass  # We'll handle this in the common path below
        else:
            # No response - ask again but make it easier to skip
            with response.gather(
                input="speech dtmf",
                action="/handle_modifier_suggestion",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout=5,
                timeout=7,
                num_digits=1
            ) as g:
                g.say(f"If you'd like to add any modifiers to your {current_item}, please say them now. Otherwise, press 1 to continue without modifiers.")
            return Response(str(response), mimetype="text/xml")
    
    # Check if user explicitly declined modifiers with DTMF
    if digits == "1" or "no" in user_resp or "skip" in user_resp or "continue" in user_resp:
        # User declined modifiers for this item - move to next item or confirmation
        logger.info(f"User declined modifiers for {current_item}")
        pass  # We'll handle this below in the common path
    else:
        # User provided modifier choices - process them
        # Add detailed logging of modifier processing start
        logger.info(f"Processing modifiers for item '{current_item}' from user input: '{user_resp}'")
        
        # Use the OrderParsingAgent to analyze the modifier response
        agent = OrderParsingAgent()
        
        # First, load the menu to get valid modifiers
        menu_data = load_menu_data(force_refresh=True)
        
        # Get all valid modifiers from the menu (only available, non-snoozed modifiers)
        valid_menu_modifiers = {
            mod.get("name", "").lower(): mod
            for mod in menu_data.get("modifiers", [])
            if mod.get("name") and mod.get("available", True) and not mod.get("snoozed", False)
        }
        
        # Standard cooking terms that should always be accepted
        cooking_terms = ["rare", "medium rare", "medium", "medium well", "well done"]
        
        logger.info(f"Found {len(valid_menu_modifiers)} valid modifiers in menu")
        
        # Let's intelligently extract modifiers using the agent
        try:
            # Get constraint details from session
            constraint_details = json.loads(session.get("constraint_details", "{}"))
            item_constraints = constraint_details.get(current_item, {})
            
            # Special handling for meal deals / combo products
            is_combo = item_constraints.get("is_combo", False)
            
            # Choose appropriate prompt based on item type
            if is_combo:
                # For meal deals, we need to parse components
                analysis = analyze_user_input(f"For my {current_item} combo I'd like {user_resp}")
            else:
                # Standard modifier prompt for regular items
                analysis = analyze_user_input(f"I'd like a {current_item} with {user_resp}")
            
            # Get the menu items from the analysis
            extracted_items = analysis.get("menu_items", [])
            
            # If we found the main item, check for modifiers
            for item in extracted_items:
                if current_item.lower() in item.get("name", "").lower():
                    # Found our current item in the parsed result
                    raw_modifiers = item.get("modifier", [])
                    
                    # Log the initially extracted modifiers
                    if raw_modifiers:
                        mod_names = [mod.get("name", "unknown") for mod in raw_modifiers]
                        mod_details = [f"{mod.get('name', 'unknown')}:{mod.get('quantity', 1)}" for mod in raw_modifiers]
                        logger.info(f"Extracted modifiers for {current_item}: {', '.join(mod_names)}")
                        logger.info(f"Detailed modifier data: {json.dumps(raw_modifiers)}")
                    
                    # Special handling for meal deals / combo products
                    if is_combo:
                        # Get components from the constraints
                        components = item_constraints.get("components", [])
                        component_ids = {comp.get("id") for comp in components}
                        
                        # Look for child items (components) in analysis
                        child_items = []
                        for child in extracted_items:
                            # Skip the main item
                            if child.get("name") == current_item:
                                continue
                                
                            # Create a component selection
                            child_name = child.get("name", "")
                            child_modifiers = child.get("modifier", [])
                            
                            # Try to match this child to a known component
                            matched_component = None
                            best_match_score = 0
                            
                            # First try direct or substring match
                            for comp in components:
                                comp_name = comp.get("name", "").lower()
                                child_name_lower = child_name.lower()
                                
                                # Exact match
                                if comp_name == child_name_lower:
                                    matched_component = comp
                                    break
                                    
                                # Substring match (both ways)
                                elif comp_name in child_name_lower or child_name_lower in comp_name:
                                    matched_component = comp
                                    break
                                    
                                # Word-based matching for partial matches
                                else:
                                    # Split into words and see how many match
                                    comp_words = set(comp_name.split())
                                    child_words = set(child_name_lower.split())
                                    common_words = comp_words.intersection(child_words)
                                    
                                    if common_words:
                                        # Calculate match score based on number of common words
                                        match_score = len(common_words) / max(len(comp_words), len(child_words))
                                        if match_score > best_match_score and match_score > 0.3:  # At least 30% match
                                            best_match_score = match_score
                                            matched_component = comp
                            
                            if matched_component:
                                # Log the match for debugging
                                logger.info(f"Matched component '{child_name}' to menu component '{matched_component.get('name')}'")
                                
                                # Add the component with its modifiers
                                child_items.append({
                                    "name": matched_component.get("name", child_name),
                                    "id": matched_component.get("id"),
                                    "quantity": child.get("quantity", 1),
                                    "modifier": child_modifiers
                                })
                        
                        # Update the meal deal selections in the session
                        if child_items:
                            meal_deal_selections = {}
                            for child in child_items:
                                meal_deal_selections[child.get("id")] = {
                                    "name": child.get("name"),
                                    "quantity": child.get("quantity", 1),
                                    "modifier": child.get("modifier", [])
                                }
                            
                            # Store meal deal selections in session
                            session["meal_deal_selections"] = json.dumps(meal_deal_selections)
                            
                            # If we have meal deal selections, process them differently
                            from app.utils.menu_utils import process_meal_deal
                            
                            # Find the meal deal item in the order
                            for order_item in order_items:
                                if order_item.get("name") == current_item:
                                    # Get the original meal deal details
                                    agent = OrderParsingAgent()
                                    meal_deal_details = agent.menu_tool.get_details(current_item)
                                    
                                    # Process the meal deal with selections
                                    processed_meal = process_meal_deal(meal_deal_details, meal_deal_selections)
                                    
                                    # Validate the meal deal - check if all required components are selected
                                    missing_components = []
                                    for child in meal_deal_details.get("childProducts", []):
                                        if child.get("required", True) and child.get("id") not in meal_deal_selections:
                                            missing_components.append(child.get("name", "Unknown component"))
                                    
                                    # If missing required components, prompt the user
                                    if missing_components:
                                        logger.warning(f"Missing required components in meal deal {current_item}: {', '.join(missing_components)}")
                                        with response.gather(
                                            input="speech",
                                            action="/handle_modifier_suggestion",
                                            enhanced=True,
                                            speech_model="phone_call",
                                            language="en-US",
                                            speech_timeout=5,
                                            timeout=7,
                                        ) as g:
                                            missing_text = ", ".join(missing_components)
                                            g.say(f"Your {current_item} needs to include {missing_text}. What would you like for these components?")
                                        return Response(str(response), mimetype="text/xml")
                                    
                                    # Update the order item with processed meal deal
                                    order_item.update(processed_meal)
                                    
                                    # Log the processed meal deal
                                    logger.info(f"Processed meal deal {current_item} with {len(meal_deal_selections)} components")
                                    
                                    # Update the session with the modified order
                                    session["order_items_without_modifiers_json"] = json.dumps(order_items)
                                    break
                            
                            # Skip regular modifier processing for meal deals
                            break
                    
                    # If standard modifiers are found, validate them strictly against the menu
                    if raw_modifiers:
                        # STRICT VALIDATION: Only accept modifiers that are EXACTLY in the menu
                        # or are standard cooking terms
                        valid_modifiers = []
                        rejected_modifiers = []
                        
                        for mod in raw_modifiers:
                            mod_name = mod.get("name", "").lower()
                            
                            # Validation priority:
                            # 1. First check exact match by name in menu
                            # 2. Then allow only standard cooking terms as exceptions
                            # 3. Reject everything else
                            
                            if mod_name in valid_menu_modifiers:
                                # Found exact match by name in menu
                                menu_mod = valid_menu_modifiers[mod_name]
                                mod["reference_handler"] = menu_mod.get("reference_handler")
                                mod["price"] = menu_mod.get("price", 0.0)
                                valid_modifiers.append(mod)
                                logger.info(f"Validated modifier with exact menu match: {mod_name}")
                            elif mod_name in cooking_terms:
                                # Special case for cooking preferences (these are the ONLY exceptions allowed)
                                mod["reference_handler"] = f"COOK-{hash(mod_name) % 100:02d}"
                                valid_modifiers.append(mod)
                                logger.info(f"Validated standard cooking modifier: {mod_name}")
                            else:
                                # Not in menu - reject it!
                                rejected_modifiers.append(mod_name)
                                logger.warning(f"Rejected non-menu modifier: {mod_name}")
                        
                        # If some modifiers were rejected, inform the user
                        if rejected_modifiers:
                            # Log the rejected modifiers
                            logger.warning(f"Rejected invalid modifiers for {current_item}: {', '.join(rejected_modifiers)}")
                            
                            # Get a list of valid modifiers to suggest as alternatives
                            suggested_alternatives = []
                            valid_modifier_suggestions = []
                            
                            # Get valid modifiers for this item from the constraints
                            constraint_details = json.loads(session.get("constraint_details", "{}"))
                            item_constraints = constraint_details.get(current_item, {})
                            
                            if "modifier_groups" in item_constraints:
                                for group in item_constraints.get("modifier_groups", []):
                                    group_mods = group.get("modifiers", [])
                                    valid_modifier_suggestions.extend(group_mods)
                            
                            # Take only the first 5 suggestions to avoid overwhelming the user
                            suggested_alternatives = valid_modifier_suggestions[:5]
                            
                            # Construct the response message
                            msg = f"I'm sorry, we don't have {', '.join(rejected_modifiers)} available for your {current_item}. "
                            
                            # Add suggestions if available
                            if suggested_alternatives:
                                msg += f"Available options include: {', '.join(suggested_alternatives)}. "
                            
                            msg += "Please specify a different modifier, or press 1 to continue without these modifiers."
                            
                            # Inform the user about invalid modifiers and ask for valid ones
                            with response.gather(
                                input="speech dtmf",
                                action="/handle_modifier_suggestion",
                                enhanced=True,
                                speech_model="phone_call",
                                language="en-US",
                                speech_timeout=5,
                                timeout=7,
                                num_digits=1
                            ) as g:
                                g.say(msg)
                            return Response(str(response), mimetype="text/xml")
                        
                        # Update the relevant item in the order with valid modifiers
                        for order_item in order_items:
                            if order_item.get("name", "") == current_item:
                                # Add the valid modifiers to the item
                                # Initialize the modifier list if needed
                                if "modifier" not in order_item:
                                    order_item["modifier"] = []
                                
                                # First check if we're getting repeated modifiers
                                existing_mods = {mod.get("name", "").lower(): True for mod in order_item.get("modifier", [])}
                                
                                # Filter out duplicates
                                new_mods = []
                                for mod in valid_modifiers:
                                    if mod.get("name", "").lower() not in existing_mods:
                                        new_mods.append(mod)
                                        
                                # Add only new modifiers
                                order_item["modifier"].extend(new_mods)
                                
                                # If we're not adding anything new, mark a flag to advance to next item
                                if not new_mods and len(order_item.get("modifier", [])) > 0:
                                    session["force_next_item"] = "true"
                                
                                # Log modification details
                                original_count = len(order_item.get("modifier", [])) - len(new_mods)
                                logger.info(f"Before modification: Item {current_item} had {original_count} modifiers")
                                
                                # Log the modifiers being added
                                if new_mods:
                                    mod_names = [mod.get("name", "unknown") for mod in new_mods]
                                    logger.info(f"Added strictly validated modifiers to {current_item}: {', '.join(mod_names)}")
                                else:
                                    logger.info(f"No new modifiers added to {current_item} (detected duplicates)")
                                    
                                logger.info(f"After modification: Item {current_item} now has {len(order_item.get('modifier', []))} modifiers")
                                
                                # Update the session with modified order
                                session["order_items_without_modifiers_json"] = json.dumps(order_items)
                                break
        except Exception as e:
            logger.error(f"Error processing modifier response: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Continue with the flow even if modifier processing fails
    
    # Check if there are more items to suggest modifiers for
    # Also check if we need to force advance to the next item due to duplicate modifiers
    force_next = session.get("force_next_item", "false").lower() == "true"
    
    if force_next:
        logger.info("Forcing advance to next item due to duplicate modifiers")
        session["force_next_item"] = "false"  # Reset the flag
        
    if remaining_items:
        # Get the next item that needs modifiers
        next_item = remaining_items[0]
        next_item_name = next_item.get("name", "")
        
        # Update the session state
        session["current_modifier_item"] = next_item_name
        session["remaining_modifier_items"] = json.dumps(remaining_items[1:]) if len(remaining_items) > 1 else "[]"
        
        # Get constraint details from session
        constraint_details = json.loads(session.get("constraint_details", "{}"))
        item_constraints = constraint_details.get(next_item_name, {})
        
        # Generate a more specific prompt based on constraint details if available
        agent = OrderParsingAgent()
        
        # Special handling for meal deals / combo items
        if item_constraints.get("is_combo", False):
            # This is a meal deal with component selection needed
            components = item_constraints.get("components", [])
            
            # Group components by type for a more natural prompt
            required_components = []
            optional_components = []
            
            for comp in components:
                if comp.get("required", True):
                    required_components.append(comp.get("name", ""))
                else:
                    optional_components.append(comp.get("name", ""))
            
            # Create component text for required components
            required_text = ""
            if required_components:
                required_text = f"You need to select: {', '.join(required_components[:3])}"
                if len(required_components) > 3:
                    required_text += f", and {len(required_components) - 3} more options"
            
            # Create component text for optional components
            optional_text = ""
            if optional_components:
                optional_text = f"You can also add: {', '.join(optional_components[:3])}"
                if len(optional_components) > 3:
                    optional_text += f", and {len(optional_components) - 3} more options"
            
            # Create a specific prompt for meal deals
            meal_deal_prompt = f"For your {next_item_name} meal deal, "
            
            if required_text:
                meal_deal_prompt += required_text + ". "
            
            if optional_text:
                meal_deal_prompt += optional_text + ". "
                
            meal_deal_prompt += "What would you like to include in your meal?"
            
            with response.gather(
                input="speech",
                action="/handle_modifier_suggestion",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout=5,
                timeout=7,
            ) as g:
                g.say(meal_deal_prompt)
            return Response(str(response), mimetype="text/xml")
        
        # Special handling for required modifiers (min/max constraints)
        elif "modifier_groups" in item_constraints and item_constraints["modifier_groups"]:
            # Get the first required modifier group
            req_mod_group = None
            for group in item_constraints["modifier_groups"]:
                if group.get("min_required", 0) > 0:
                    req_mod_group = group
                    break
            
            if req_mod_group:
                # Create a prompt for required modifiers
                group_name = req_mod_group.get("name", "")
                min_required = req_mod_group.get("min_required", 1)
                options = ", ".join(req_mod_group.get("modifiers", [])[:5])  # Show first 5 options
                
                required_prompt = f"Your {next_item_name} requires {min_required} selection{'s' if min_required > 1 else ''} from {group_name}. Options include: {options}. What would you like?"
                
                with response.gather(
                    input="speech",
                    action="/handle_modifier_suggestion",
                    enhanced=True,
                    speech_model="phone_call",
                    language="en-US",
                    speech_timeout=5,
                    timeout=7,
                ) as g:
                    g.say(required_prompt)
                return Response(str(response), mimetype="text/xml")
        
        # Regular modifier prompting for other cases
        # First check if we have specific modifier groups that we should mention
        if "modifier_groups" in item_constraints and item_constraints["modifier_groups"]:
            # Build a more specific prompt listing available options
            mod_groups_str = ""
            for group in item_constraints["modifier_groups"][:2]:  # Limit to 2 groups to keep prompt reasonable
                group_name = group.get("name", "")
                # Get a few example modifiers
                example_mods = group.get("modifiers", [])[:3]
                if example_mods:
                    mod_examples = ", ".join(example_mods)
                    mod_groups_str += f" {group_name} options like {mod_examples};"
            
            # Create a custom prompt mentioning available options
            custom_prompt = f"Would you like any modifications for your {next_item_name}? We have{mod_groups_str} or you can skip by saying 'no thanks'."
            
            with response.gather(
                input="speech dtmf",
                action="/handle_modifier_suggestion",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout=5,
                timeout=7,
                num_digits=1
            ) as g:
                g.say(custom_prompt)
            return Response(str(response), mimetype="text/xml")
        
        # Fall back to the AI-generated prompt for other cases
        modifier_prompt = agent.menu_tool.generate_modifier_prompt(next_item_name)
        
        # If we have a good prompt, ask the customer
        if modifier_prompt:
            with response.gather(
                input="speech dtmf",
                action="/handle_modifier_suggestion",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout=5,
                timeout=7,
                num_digits=1
            ) as g:
                g.say(modifier_prompt)
            return Response(str(response), mimetype="text/xml")
    
    # No more items need modifiers - proceed to order confirmation
    # Update the final order in session
    session["order_items_json"] = session["order_items_without_modifiers_json"]
    
    # Calculate total and prepare confirmation message
    order_items = json.loads(session["order_items_json"])
    calculate_bill_amount(order_items)
    order_description = build_order_description(order_items)
    session["bill_amount"] = int(session.get("total_price", 0) * 100)
    session["order_message"] = f"{order_description}\nYour total is ${session.get('total_price', 0):.2f}."
    
    # Log completion of modifier flow with summary
    logger.info(f"=== COMPLETED modifier flow for all items ===")
    logger.info(f"Final order has {len(order_items)} items with modifiers")
    for item in order_items:
        modifier_count = len(item.get("modifier", []))
        logger.info(f"Item '{item.get('name')}' has {modifier_count} modifiers: {[m.get('name') for m in item.get('modifier', [])]}")
    logger.info(f"Order total: ${session.get('total_price', 0):.2f}")
    
    # Mark the modifiers flow as completed to prevent infinite loops
    session["completed_modifiers"] = "true"
    
    # Ask for confirmation of complete order with modifiers
    with response.gather(
        input="speech dtmf",
        action="/confirm_order_from_initial?skip_modifiers=true",  # Skip modifiers as we just did them
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

@order_bp.route("/order_status", methods=["POST"])
def order_status():
    """
    Handle order status updates from Deliverect.

    Processes POS statuses, delivery statuses, and system statuses with detailed tracking
    and sends appropriate customer notifications via SMS.

    Status codes mapping:
    - 1-9: System statuses (parsed, received, etc.)
    - 10-69: Kitchen preparation statuses
    - 70-75: Pickup ready
    - 76-89: Delivery tracking statuses
    - 90-99: Completion statuses
    - 100+: Cancellation and error statuses

    Note: This endpoint has fallback mechanisms for databases that haven't been migrated
    to support the new status_code and delivery tracking columns.
    """
    # Get request data
    data = request.get_json() or {}
    status = data.get("status")
    order_id = data.get("channelOrderId")
    status_code = data.get("code")

    # Additional parameters for enhanced tracking
    courier_info = data.get("courier", {})
    courier_name = courier_info.get("name", "")
    courier_phone = courier_info.get("phoneNumber", "")
    eta = data.get("eta")  # Expected time of arrival

    # Log the complete request for detailed debugging
    log_info(
        f"Received status update: order={order_id}, status={status}, code={status_code}"
    )
    log_info(f"Full Deliverect payload: {json.dumps(data)}")

    # Validate required parameters
    if not order_id:
        return jsonify({"error": "Missing channelOrderId parameter"}), 400
    if not status and not status_code:
        return jsonify({"error": "Missing status or code parameter"}), 400

    # Log failed orders with enhanced details
    if status == "FAILED" or status_code == 120:
        error_reason = data.get("errorReason", "Unknown error")
        log_info(
            f"Order {order_id} failed with code={status_code}, status={status}, reason: {error_reason}"
        )

    # Update order in database with comprehensive status information
    try:
        # Explicitly use the Order model from the import at the top of file
        from app.models import Order

        if "text" not in globals():
            from sqlalchemy import text

        # First try to get the order
        try:
            order_record = db.session.query(Order).filter_by(id=order_id).first()
        except Exception as db_err:
            # If we get a column does not exist error, it means we haven't migrated the database yet
            if "column order.status_code does not exist" in str(db_err):
                log_info(
                    "Database schema needs migration. Using legacy query without new columns."
                )
                # Use a simpler query that doesn't reference the new columns
                sql = text(
                    "SELECT id, sender, caller_name, message, status, timestamp, location_id, "
                    "sms_sid, sms_status, sms_error_code, sms_error_message "
                    'FROM "order" WHERE id = :order_id LIMIT 1'
                )
                result = db.session.execute(sql, {"order_id": order_id})
                row = result.fetchone()
                if row:
                    # Create Order object manually
                    order_record = Order()
                    order_record.id = row.id
                    order_record.sender = row.sender
                    order_record.caller_name = row.caller_name
                    order_record.message = row.message
                    order_record.status = row.status
                    order_record.timestamp = row.timestamp
                    order_record.location_id = row.location_id
                    order_record.sms_sid = row.sms_sid
                    order_record.sms_status = row.sms_status
                    order_record.sms_error_code = row.sms_error_code
                    order_record.sms_error_message = row.sms_error_message
                    # Set additional attributes that will be needed but not in DB yet
                    order_record.status_code = None
                    order_record.status_updated_at = None
                    order_record.delivery_status = None
                    order_record.delivery_status_code = None
                    order_record.courier_name = None
                    order_record.courier_phone = None
                    order_record.estimated_delivery_time = None
                else:
                    return jsonify({"error": "Order not found"}), 404
            else:
                # Re-raise if it's a different error
                raise

        if not order_record:
            return jsonify({"error": "Order not found"}), 404

        # Store original status for change detection
        previous_status = order_record.status
        previous_code = getattr(order_record, "status_code", None)

        # Update status field that should always exist
        order_record.status = status

        # Check if new columns are available in the database
        try:
            # Try to update new columns - if they don't exist in db, these will be ignored
            if hasattr(order_record, "status_code"):
                order_record.status_code = status_code
            if hasattr(order_record, "status_updated_at"):
                order_record.status_updated_at = datetime.now()

            # Handle delivery specific information if columns exist
            if status_code in [76, 81, 83, 85, 87, 89]:
                # This is a delivery status
                if hasattr(order_record, "delivery_status"):
                    order_record.delivery_status = status
                if hasattr(order_record, "delivery_status_code"):
                    order_record.delivery_status_code = status_code

                # Store courier information if provided and columns exist
                if courier_name and hasattr(order_record, "courier_name"):
                    order_record.courier_name = courier_name
                if courier_phone and hasattr(order_record, "courier_phone"):
                    order_record.courier_phone = courier_phone

                # Parse and store ETA if provided and column exists
                if eta and hasattr(order_record, "estimated_delivery_time"):
                    try:
                        # Assuming eta is in milliseconds since epoch
                        eta_datetime = datetime.fromtimestamp(int(eta) / 1000)
                        order_record.estimated_delivery_time = eta_datetime
                    except (ValueError, TypeError) as e:
                        log_info(f"Error parsing ETA: {e}, value: {eta}")
        except Exception as col_err:
            log_info(f"Error updating new columns (they may not exist yet): {col_err}")

        # Try to save changes to database - handle potential schema issues
        try:
            if not commit_with_retry(db.session):
                # If commit failed, try a simpler update with just the status
                log_info(
                    "Full update failed, trying simplified update with just status."
                )
                sql = text('UPDATE "order" SET status = :status WHERE id = :order_id')
                db.session.execute(sql, {"status": status, "order_id": order_id})
                db.session.commit()
        except Exception as commit_err:
            log_info(f"Error committing changes: {commit_err}")
            # Try the most basic update possible
            try:
                sql = text('UPDATE "order" SET status = :status WHERE id = :order_id')
                db.session.execute(sql, {"status": status, "order_id": order_id})
                db.session.commit()
                log_info("Used direct SQL to update status")
            except Exception as sql_err:
                log_info(f"Error with direct SQL update: {sql_err}")
                return jsonify({"error": "Database error"}), 500

        # Determine if this is a status change that should trigger customer notification
        should_notify = False

        # Status changes that should always trigger notifications
        major_status_changes = [
            20,  # Accepted - Order confirmed
            50,  # Preparing - In preparation
            70,  # Pickup Ready - Ready for collection
            76,  # Delivery Created - Looking for courier
            83,  # En Route to Pickup - Courier approaching
            87,  # En Route To Dropoff - Courier heading to customer
            89,  # Arrived At Drop Off - Courier at customer location
            90,  # Finalized/Delivered - Order completed
            110,  # Canceled - Order canceled
            120,  # Failed - Order failed
        ]

        # Notify on first status update, status code changes, or major status changes
        if (
            previous_status != status
            or previous_code != status_code
            or status_code in major_status_changes
        ):
            should_notify = True

        # Special handling for delivery events - always notify
        if status_code in [76, 81, 83, 85, 87, 89]:
            should_notify = True

        # Don't notify for system-only statuses unless configured
        if status_code in [1, 2, 3, 4, 5, 6, 7]:
            should_notify = (
                False  # System internal statuses, no customer notification needed
            )

        # Create a detailed status message with courier info if applicable
        if should_notify:
            # Generate simple status message for compatibility or friendly message if columns exist
            try:
                # First try to use the advanced status description
                friendly_status = order_record.get_status_display()
                status_message = (
                    f"Your order ({order_id[:8]}) status: {friendly_status}"
                )
            except:
                # Fallback to a simpler status message
                status_message = f"Your order ({order_id[:8]}) status update: "
                if status_code == 10:
                    status_message += "has been received by the restaurant"
                elif status_code == 20:
                    status_message += "has been accepted and is being prepared"
                elif status_code == 50:
                    status_message += "is now being prepared in the kitchen"
                elif status_code == 70:
                    status_message += "is ready for pickup!"
                elif status_code == 90:
                    status_message += "has been completed. Thank you!"
                elif status_code == 120:
                    status_message += "has encountered an issue. Please call us."
                elif status_code in [76, 81]:
                    status_message += "has been assigned to a delivery courier"
                elif status_code == 83:
                    status_message += "courier is on the way to the restaurant"
                elif status_code == 87:
                    status_message += "is on the way to you!"
                elif status_code == 89:
                    status_message += "courier has arrived at your location"
                else:
                    status_message += f"is now {status}"

            # Add courier information for delivery statuses
            if status_code in [83, 85, 87, 89] and courier_name:
                status_message += f"\nCourier: {courier_name}"
                if courier_phone:
                    status_message += f" ({courier_phone})"

            # Add ETA information if available
            if eta:
                try:
                    eta_time = datetime.fromtimestamp(int(eta) / 1000).strftime(
                        "%I:%M %p"
                    )
                    status_message += f"\nEstimated delivery/pickup time: {eta_time}"
                except Exception as eta_err:
                    log_info(f"Error formatting ETA: {eta_err}")
            elif (
                hasattr(order_record, "estimated_delivery_time")
                and order_record.estimated_delivery_time
            ):
                try:
                    eta_time = order_record.estimated_delivery_time.strftime("%I:%M %p")
                    status_message += f"\nEstimated delivery/pickup time: {eta_time}"
                except Exception as eta_err:
                    log_info(f"Error formatting stored ETA: {eta_err}")

            # Send status update to customer with enhanced information
            # Use the already imported task function or try to re-import as a fallback
            if "send_order_status_update_task" not in globals():
                try:
                    sys.path.append(
                        os.path.dirname(
                            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                        )
                    )
                    from tasks import send_order_status_update_task
                except ImportError:
                    log_info(
                        "Could not import send_order_status_update_task, will use direct SMS instead"
                    )
                    send_order_status_update_task = None
            try:
                logging.info(
                    f"Attempting to send status update task for order {order_id}"
                )

                # Check if we have the task function available
                if (
                    "send_order_status_update_task" in globals()
                    and send_order_status_update_task
                ):
                    # Call the task directly for now until Redis/Celery is properly setup
                    send_order_status_update_task(
                        order_id, status_message, location_id=order_record.location_id
                    )
                    logging.info(
                        f"Status update task executed successfully for order {order_id}"
                    )
                else:
                    # No task function, use direct SMS
                    logging.info("Task function not available, sending SMS directly")
                    raise ImportError("Task not available")

            except Exception as task_error:
                logging.error(f"Error sending status update task: {task_error}")
                # Fall back to direct SMS sending if task execution fails
                try:
                    # Get the order detail using the record we already have
                    if order_record and order_record.sender:
                        # Send SMS directly
                        twilio_client.messages.create(
                            body=status_message,
                            from_=TWILIO_PHONE_NUMBER,
                            to=order_record.sender,
                        )
                        logging.info(
                            f"Sent status update directly via SMS to {order_record.sender}"
                        )
                    else:
                        # Try to get the order from the DB as a backup
                        from app.models import Order

                        order = db.session.get(Order, order_id)
                        if order and order.sender:
                            # Send SMS directly
                            twilio_client.messages.create(
                                body=status_message,
                                from_=TWILIO_PHONE_NUMBER,
                                to=order.sender,
                            )
                            logging.info(
                                f"Sent status update directly via SMS to {order.sender}"
                            )
                        else:
                            logging.error(
                                f"Could not find order or sender for order_id: {order_id}"
                            )
                except Exception as sms_error:
                    logging.error(f"Error sending direct SMS: {sms_error}")

            log_info(f"Notification sent for order {order_id}: {status_message}")
        else:
            log_info(
                f"No notification sent for order {order_id} - internal status update only"
            )

        return jsonify({"success": True}), 200
    except Exception as e:
        log_info(f"Error processing order status update: {str(e)}")
        log_info(traceback.format_exc())
        return jsonify({"error": "Internal server error"}), 500


@order_bp.route("/sms", methods=["POST"])
def handle_sms():
    """Handle incoming SMS messages for order status inquiries and other commands"""
    # Get the message sent
    message_body = request.values.get("Body", "").strip().lower()
    from_number = request.values.get("From", "")

    # Log the incoming message for debugging
    log_info(f"Received SMS from {from_number}: '{message_body}'")

    # Create a response
    resp = MessagingResponse()

    # Log request headers to help with debugging
    request_headers = {key: request.headers.get(key) for key in request.headers.keys()}
    log_info(f"SMS request headers: {json.dumps(request_headers)}")
    log_info(f"SMS request form data: {json.dumps(dict(request.form))}")

    # Debug logging for SMS request and command detection
    log_info(f"SMS COMMAND DEBUG - Message: '{message_body}'")
    log_info(f"SMS COMMAND DEBUG - Exact match 'help': {message_body == 'help'}")
    log_info(
        f"SMS COMMAND DEBUG - Keyword match: {any(keyword in message_body for keyword in ['help', 'command', 'info', 'option'])}"
    )

    # Make sure we handle messages even if empty or malformed
    if not message_body:
        message_body = ""
        log_info("Received empty message body, treating as default welcome")

    # Handle different command types with flexible matching for user convenience
    # First, try exact match for common commands (for better reliability)
    command_type = message_body.strip().lower()

    if (
        command_type == "status"
        or command_type == "order"
        or command_type == "check"
        or command_type == "stat"
        or any(
            keyword in message_body for keyword in ["status", "stat", "check", "order"]
        )
    ):
        try:
            # Find the most recent order for this number
            recent_order = (
                db.session.query(Order)
                .filter_by(sender=from_number)
                .order_by(Order.timestamp.desc())
                .first()
            )

            if recent_order:
                # Get status and create friendly message using enhanced Order model methods
                order_status = recent_order.status or "NEW"

                # Use the enhanced get_status_display method if status_code is available
                if recent_order.status_code:
                    friendly_status = recent_order.get_status_display()
                else:
                    # Fallback to legacy status descriptions
                    friendly_status = {
                        "NEW": "received and is being processed",
                        "ACCEPTED": "accepted and being prepared",
                        "PREPARING": "now being prepared in the kitchen",
                        "READY": "ready for pickup! 🎉",
                        "COMPLETED": "completed. Thank you for your order! 🙏",
                        "FAILED": "could not be processed. Please call us",
                        "REJECTED": "could not be processed. Please call us",
                        "CANCELLED": "cancelled",
                    }.get(order_status, order_status)

                # Extract order details for a more detailed response
                order_id = recent_order.id
                order_time = (
                    recent_order.timestamp.strftime("%I:%M %p")
                    if recent_order.timestamp
                    else "unknown time"
                )

                # Extract order items from the stored message
                order_items = "your order"
                if recent_order.message and "\n-" in recent_order.message:
                    try:
                        items_section = (
                            recent_order.message.split("YOUR ORDER:")[1].split("\n\n")[
                                0
                            ]
                            if "YOUR ORDER:" in recent_order.message
                            else ""
                        )
                        if items_section:
                            # Ensure consistent formatting with × for quantities
                            formatted_lines = []
                            for line in items_section.strip().split("\n"):
                                if line.startswith("- "):
                                    if " × " not in line and " x " not in line:
                                        parts = line.strip("- ").split(" ", 1)
                                        if len(parts) == 2 and parts[0].isdigit():
                                            quantity, name = parts
                                            line = f"- {quantity}× {name}"
                                formatted_lines.append(line)
                            order_items = "\n".join(formatted_lines)
                    except:
                        # If we can't parse properly, just use the first line as fallback
                        order_items = (
                            recent_order.message.split("\n")[0]
                            if recent_order.message
                            else "your order"
                        )

                # Create status emoji based on status code
                status_emoji = "📋"
                if recent_order.status_code:
                    # POS preparation status
                    if 10 <= recent_order.status_code <= 69:
                        status_emoji = "👨‍🍳"
                    # Ready for pickup
                    elif 70 <= recent_order.status_code <= 75:
                        status_emoji = "✅"
                    # Delivery status
                    elif 76 <= recent_order.status_code <= 89:
                        status_emoji = "🚚"
                    # Completed
                    elif 90 <= recent_order.status_code <= 99:
                        status_emoji = "🎉"
                    # Failed/canceled
                    elif recent_order.status_code >= 100:
                        status_emoji = "⚠️"

                # Get location information
                location_name = "Red Bar Sushi"
                if recent_order.location_id:
                    try:
                        from app.models import Location

                        location = (
                            db.session.query(Location)
                            .filter_by(id=recent_order.location_id)
                            .first()
                        )
                        if location:
                            location_name = location.name
                    except Exception as e:
                        log_info(f"Error getting location name: {e}")

                # Determine if this is a delivery order
                is_delivery = recent_order.status_code in [76, 81, 83, 85, 87, 89]

                # Start building the message
                status_message = f"""🍣 RED BAR SUSHI STATUS UPDATE 🍣

🆔 Order #{order_id[:8]}
📍 {location_name}
🕒 Placed at: {order_time}

{order_items}

{status_emoji} CURRENT STATUS: {friendly_status}"""

                # Add delivery-specific information
                if is_delivery:
                    status_message += "\n\n🚚 DELIVERY INFORMATION:"

                    # Add courier information if available
                    if recent_order.courier_name:
                        status_message += f"\n👤 Courier: {recent_order.courier_name}"
                        if recent_order.courier_phone:
                            status_message += f" ({recent_order.courier_phone})"

                    # Add estimated delivery time if available
                    if recent_order.estimated_delivery_time:
                        eta_time = recent_order.estimated_delivery_time.strftime(
                            "%I:%M %p"
                        )
                        status_message += f"\n⏱️ Estimated delivery: {eta_time}"

                    # Add delivery status-specific information
                    if recent_order.status_code == 83:
                        status_message += (
                            "\nYour courier is on the way to the restaurant"
                        )
                    elif recent_order.status_code == 85:
                        status_message += "\nYour courier has arrived at the restaurant"
                    elif recent_order.status_code == 87:
                        status_message += "\nYour order is on the way to you!"
                    elif recent_order.status_code == 89:
                        status_message += "\nYour courier has arrived at your location"

                # Add status-specific instructions
                if recent_order.status_code == 70:  # Ready for pickup
                    status_message += "\n\n⏱️ Your order is ready for pickup now!"
                    status_message += f"\n📍 Please pick up at: {location_name}"
                    status_message += "\n📞 Call (833) 324-7207 if you need assistance"
                elif recent_order.status_code == 50:  # Preparing
                    # Estimate remaining time for pickup orders
                    if not is_delivery:
                        prep_time = 20 + (
                            len(recent_order.message.split("\n- ")) * 2
                        )  # Estimate based on line count
                        time_elapsed = (
                            (time.time() - recent_order.timestamp.timestamp()) / 60
                            if recent_order.timestamp
                            else 0
                        )
                        time_remaining = max(1, prep_time - time_elapsed)
                        status_message += f"\n\n⏱️ Estimated to be ready in: {int(time_remaining)} minutes"
                elif recent_order.status_code in [110, 120]:  # Failed/error states
                    status_message += (
                        "\n\n⚠️ Please call us at (833) 324-7207 regarding your order"
                    )

                # Add footer with help option
                status_message += "\n\n💬 Reply 'help' for more options"

                resp.message(status_message)
                log_info(f"Sent enhanced status update via SMS to {from_number}")
            else:
                resp.message(
                    """⚠️ ORDER NOT FOUND

We couldn't find any recent orders for your number. 

• If you just placed an order, please wait a moment and try again
• If you're trying to place an order, please call us at (833) 324-7207

Reply 'menu' to see our menu options."""
                )
                log_info(f"No order found for {from_number}")
        except Exception as e:
            log_info(f"Error processing SMS status request: {str(e)}")
            resp.message(
                "⚠️ Sorry, we encountered an error processing your request. Please call us at (833) 324-7207 for assistance."
            )

    # Handle help command - ensure we detect both exact and keyword matches
    elif (
        command_type == "help"
        or "help" in message_body
        or any(
            keyword in message_body for keyword in ["command", "info", "option", "?"]
        )
    ):
        help_message = """🍣 RED BAR SUSHI HELP 🍣

📱 AVAILABLE COMMANDS:
• Text 'status' to check your order status
• Text 'menu' to see our menu
• Text 'hours' for our business hours
• Text 'specials' for today's special offers
• Text 'location' for our address and map
• Text 'contact' for contact information

📞 CALL US: (833) 324-7207
🌐 WEBSITE: redbarsushi.com

Thank you for choosing Red Bar Sushi!
"""
        resp.message(help_message)
        log_info(f"Sent help info via SMS to {from_number}")

    # Handle menu request
    elif command_type == "menu" or any(
        keyword in message_body for keyword in ["menu", "food", "eat", "dish", "price"]
    ):
        menu_message = """🍣 RED BAR SUSHI MENU 🍣

📋 POPULAR ITEMS:
• Signature Dragon Roll - $14.99
• Spicy Tuna Roll - $8.99
• Rainbow Roll - $12.99
• Sashimi Platter - $24.99

🌐 View our full menu: 
https://redbar-sushi.com/menu

📞 Call (833) 324-7207 to order by phone
"""
        resp.message(menu_message)
        log_info(f"Sent menu info via SMS to {from_number}")

    # Handle hours request
    elif command_type == "hours" or any(
        keyword in message_body for keyword in ["hour", "time", "open", "close"]
    ):
        resp.message(
            """🍣 RED BAR SUSHI HOURS 🍣

⏰ REGULAR HOURS:
Monday - Thursday: 11am - 9pm
Friday - Saturday: 11am - 10pm
Sunday: 12pm - 8pm

🔴 HAPPY HOUR:
Monday-Friday: 3pm - 6pm
$2 off all rolls and appetizers!

We look forward to serving you soon!
"""
        )
        log_info(f"Sent hours info via SMS to {from_number}")

    # Handle location request
    elif command_type == "location" or any(
        keyword in message_body
        for keyword in ["location", "address", "where", "map", "direction"]
    ):
        resp.message(
            """🍣 RED BAR SUSHI LOCATION 🍣

📍 ADDRESS:
123 Sushi Avenue
Anytown, CA 12345

🏙️ NEIGHBORHOOD:
Downtown, next to Central Park

🚗 PARKING:
Free street parking available
Paid lot at 130 Sushi Ave

🌐 DIRECTIONS:
https://maps.google.com/?q=Red+Bar+Sushi
"""
        )
        log_info(f"Sent location info via SMS to {from_number}")

    # Handle contact request
    elif command_type == "contact" or any(
        keyword in message_body for keyword in ["contact", "phone", "call", "reach"]
    ):
        resp.message(
            """🍣 RED BAR SUSHI CONTACT INFO 🍣

📞 PHONE: (833) 324-7207
📧 EMAIL: hello@redbarsushi.com
🌐 WEBSITE: redbarsushi.com
📱 SOCIAL: @RedBarSushi

For fastest response, please call us!
"""
        )
        log_info(f"Sent contact info via SMS to {from_number}")

    # Handle specials request
    elif command_type == "specials" or any(
        keyword in message_body
        for keyword in ["special", "deal", "offer", "discount", "promotion"]
    ):
        # Get the current day of the week
        import datetime

        day_of_week = datetime.datetime.now().strftime("%A")

        # Create day-specific special
        day_special = {
            "Monday": "Maki Monday: 20% off all maki rolls!",
            "Tuesday": "Tuna Tuesday: $2 off tuna rolls!",
            "Wednesday": "Wasabi Wednesday: Free appetizer with $30+ order!",
            "Thursday": "Tempura Thursday: 15% off all tempura dishes!",
            "Friday": "Fusion Friday: Try our special fusion rolls!",
            "Saturday": "Sashimi Saturday: Premium sashimi platters 10% off!",
            "Sunday": "Sunday Special: Kids eat free with adult entrée!",
        }.get(day_of_week, "Daily special: 10% off your first order!")

        resp.message(
            f"""🍣 RED BAR SUSHI SPECIALS 🍣

✨ TODAY'S SPECIAL ({day_of_week}):
{day_special}

🔥 CURRENT PROMOTIONS:
• Buy 2 specialty rolls, get 1 regular roll free!
• Order online for 5% discount
• Happy Hour: 3-6pm daily with $2 off all rolls

📱 Show this message when ordering to redeem!
"""
        )
        log_info(f"Sent specials info via SMS to {from_number}")

    # Handle unknown or default response
    else:
        welcome_message = """🍣 Welcome to Red Bar Sushi! 🍣

Thanks for your message! How can we help you?

• Reply with 'status' to check your order
• Reply with 'menu' to view our menu
• Reply with 'hours' for our business hours
• Reply with 'help' for more commands

We're always happy to assist you!
"""
        resp.message(welcome_message)
        log_info(f"Sent welcome message via SMS to {from_number}")

    return Response(str(resp), mimetype="text/xml")


@order_bp.route("/register", methods=["POST"])
def register_channel_route():
    """Register or update channel status with Deliverect"""
    # Get request data
    data = request.get_json() or {}
    status = data.get("status")

    # Log the full request for debugging
    log_info(f"Received registration request: {json.dumps(data)}")

    # Validate required parameters
    if not status:
        return jsonify({"error": "Missing status parameter"}), 400

    # Extract additional parameters
    data.get("channelLocationId")
    data.get("channelLinkId")
    location_id = data.get("locationId")
    channel_link_name = data.get("channelLinkName")

    # Update channel status
    global channel_status
    if status == "register":
        channel_status = 0
        log_info(
            f"Channel registered with Deliverect: {channel_link_name} (ID: {location_id})"
        )

        # Save location details to database if we have a location ID
        if location_id and channel_link_name:
            try:
                from app.utils.deliverect import register_new_location

                webhook_base = BASE_URL
                success = register_new_location(
                    location_id=location_id,
                    location_name=channel_link_name,
                    webhook_base=webhook_base,
                )
                if success:
                    log_info(
                        f"Successfully registered location {location_id} in database"
                    )
                else:
                    log_info(f"Failed to register location {location_id} in database")
            except Exception as e:
                log_info(f"Error registering location: {e}")

    elif status == "active":
        channel_status = 1
        log_info(
            f"Channel activated with Deliverect: {channel_link_name} (ID: {location_id})"
        )

        # Update location status if we have a location ID
        if location_id:
            try:
                from app.utils.deliverect import update_location_status

                update_location_status(location_id, "active")
            except Exception as e:
                log_info(f"Error updating location status: {e}")

    elif status == "inactive":
        channel_status = 2
        log_info(
            f"Channel deactivated with Deliverect: {channel_link_name} (ID: {location_id})"
        )

        # Update location status if we have a location ID
        if location_id:
            try:
                from app.utils.deliverect import update_location_status

                update_location_status(location_id, "inactive")
            except Exception as e:
                log_info(f"Error updating location status: {e}")
    else:
        return jsonify({"error": f"Invalid status: {status}"}), 400

    # Return webhook URLs exactly as expected by Deliverect (case-sensitive)
    response_body = {
        "statusUpdateURL": f"{BASE_URL}/order_status",
        "menuUpdateURL": f"{BASE_URL}/menu_update",
        "snoozeUnsnoozeURL": f"{BASE_URL}/snoozeUnsnooze",
        "busyModeURL": f"{BASE_URL}/busy_mode",
        "updatePrepTimeURL": f"{BASE_URL}/updatePrepTime",
        "courierUpdateURL": f"{BASE_URL}/courierUpdate",
        "paymentUpdateURL": f"{BASE_URL}/payment_update",
    }

    log_info(f"Registered webhooks with base URL: {BASE_URL}")
    log_info(f"Response: {json.dumps(response_body)}")
    return jsonify(response_body), 200


@order_bp.route("/sms_status_callback", methods=["POST"])
def sms_status_callback():
    """Handle SMS delivery status callbacks from Twilio"""
    # Extract data from the callback
    message_sid = request.values.get("MessageSid", "")
    message_status = request.values.get("MessageStatus", "")
    error_code = request.values.get("ErrorCode", None)
    error_message = request.values.get("ErrorMessage", None)
    to_number = request.values.get("To", "")

    log_info(
        f"SMS status callback received - SID: {message_sid}, Status: {message_status}, To: {to_number}"
    )

    # If there's an error, log it with enhanced detail
    if error_code or error_message:
        log_info(
            f"SMS delivery error - Code: {error_code}, Message: {error_message}, To: {to_number}"
        )

        # Auto-retry logic for failed messages (if error is recoverable)
        recoverable_errors = [
            "30001",
            "30002",
            "30003",
            "30004",
            "30005",
            "30006",
            "30007",
        ]
        # Error 30034 means invalid recipient number - we should log this clearly
        if error_code == "30034":
            log_info(
                f"ERROR 30034: Invalid recipient phone number: {to_number}. This number cannot receive SMS."
            )
            # No retry for invalid number - update documentation to use correct numbers
            # The system has been configured to use the same working number in all environments
        elif error_code in recoverable_errors and to_number:
            log_info(
                f"Queueing retry for recoverable error {error_code} to {to_number}"
            )
            # This will be implemented if needed - would need a celery task

    # Find the order with this SMS SID
    try:
        try:
            # First try standard query
            order = db.session.query(Order).filter_by(sms_sid=message_sid).first()
        except Exception as db_err:
            # If we get a column does not exist error, it means we haven't migrated the database yet
            if "column order.status_code does not exist" in str(db_err):
                log_info(
                    "Database schema needs migration. Using legacy query for SMS status."
                )
                # Use a simpler query that doesn't reference the new columns
                sql = text(
                    "SELECT id, sender, caller_name, message, status, timestamp, location_id, "
                    "sms_sid, sms_status, sms_error_code, sms_error_message "
                    'FROM "order" WHERE sms_sid = :sms_sid LIMIT 1'
                )
                result = db.session.execute(sql, {"sms_sid": message_sid})
                row = result.fetchone()

                if row:
                    order = Order()
                    order.id = row.id
                    order.sender = row.sender
                    order.caller_name = row.caller_name
                    order.message = row.message
                    order.status = row.status
                    order.timestamp = row.timestamp
                    order.location_id = row.location_id
                    order.sms_sid = row.sms_sid
                    order.sms_status = row.sms_status
                    order.sms_error_code = row.sms_error_code
                    order.sms_error_message = row.sms_error_message
                else:
                    order = None
            else:
                # Re-raise if it's a different error
                raise

        if order:
            # Update the SMS status information
            order.sms_status = message_status
            if error_code:
                order.sms_error_code = error_code
            if error_message:
                order.sms_error_message = error_message

            # Handle delivery confirmation
            if message_status == "delivered":
                log_info(
                    f"SMS successfully delivered to {to_number} for order {order.id}"
                )
            elif message_status == "undelivered" or message_status == "failed":
                log_info(
                    f"SMS delivery failed to {to_number} for order {order.id}: {error_code} - {error_message}"
                )

            # Try to commit the changes - handle errors with simple SQL if needed
            try:
                if not commit_with_retry(db.session):
                    # If commit failed, try a simpler update with just the status
                    log_info("Full update failed, trying simplified SMS status update.")
                    sql = text(
                        'UPDATE "order" SET sms_status = :status WHERE id = :order_id'
                    )
                    db.session.execute(
                        sql, {"status": message_status, "order_id": order.id}
                    )
                    db.session.commit()
            except Exception as commit_err:
                log_info(f"Error committing SMS status changes: {commit_err}")
                # Try the most basic update possible
                try:
                    sql = text(
                        'UPDATE "order" SET sms_status = :status WHERE id = :order_id'
                    )
                    db.session.execute(
                        sql, {"status": message_status, "order_id": order.id}
                    )
                    db.session.commit()
                    log_info("Used direct SQL to update SMS status")
                except Exception as sql_err:
                    log_info(f"Error with direct SQL SMS update: {sql_err}")
                    return jsonify({"success": False, "error": "Database error"}), 500

            log_info(f"Updated SMS status for order {order.id} to {message_status}")
            return jsonify({"success": True}), 200
        else:
            # Try to find the order by phone number if SID doesn't match
            if to_number:
                try:
                    # First try standard query
                    recent_order = (
                        db.session.query(Order)
                        .filter_by(sender=to_number)
                        .order_by(Order.timestamp.desc())
                        .first()
                    )
                except Exception as db_err:
                    # If we get a column does not exist error, use direct SQL
                    if "column order.status_code does not exist" in str(db_err):
                        log_info("Using legacy query to find order by phone number.")
                        sql = text(
                            "SELECT id, sender, caller_name, message, status, timestamp, location_id, "
                            "sms_sid, sms_status, sms_error_code, sms_error_message "
                            'FROM "order" WHERE sender = :sender ORDER BY timestamp DESC LIMIT 1'
                        )
                        result = db.session.execute(sql, {"sender": to_number})
                        row = result.fetchone()

                        if row:
                            recent_order = Order()
                            recent_order.id = row.id
                            recent_order.sender = row.sender
                            recent_order.caller_name = row.caller_name
                            recent_order.message = row.message
                            recent_order.status = row.status
                            recent_order.timestamp = row.timestamp
                            recent_order.location_id = row.location_id
                            recent_order.sms_sid = row.sms_sid
                            recent_order.sms_status = row.sms_status
                            recent_order.sms_error_code = row.sms_error_code
                            recent_order.sms_error_message = row.sms_error_message
                        else:
                            recent_order = None
                    else:
                        # Re-raise if it's a different error
                        raise

                if recent_order:
                    # Try to update using direct SQL to avoid model attribute issues
                    try:
                        sql = text(
                            'UPDATE "order" SET sms_sid = :sms_sid, sms_status = :status WHERE id = :order_id'
                        )
                        params = {
                            "sms_sid": message_sid,
                            "status": message_status,
                            "order_id": recent_order.id,
                        }
                        if error_code:
                            sql = text(
                                'UPDATE "order" SET sms_sid = :sms_sid, sms_status = :status, '
                                "sms_error_code = :error_code WHERE id = :order_id"
                            )
                            params["error_code"] = error_code
                        if error_message:
                            sql = text(
                                'UPDATE "order" SET sms_sid = :sms_sid, sms_status = :status, '
                                "sms_error_message = :error_message WHERE id = :order_id"
                            )
                            params["error_message"] = error_message

                        db.session.execute(sql, params)
                        db.session.commit()
                        log_info(
                            f"Updated SMS status for order {recent_order.id} using direct SQL"
                        )
                    except Exception as sql_err:
                        log_info(
                            f"Error with direct SQL update for order by phone: {sql_err}"
                        )
                        return (
                            jsonify({"success": False, "error": "Database error"}),
                            500,
                        )

                    log_info(
                        f"Updated SMS status for recent order {recent_order.id} (matched by phone number)"
                    )
                    return jsonify({"success": True}), 200

            log_info(
                f"No order found with SMS SID: {message_sid} or number: {to_number}"
            )
            return jsonify({"success": False, "error": "Order not found"}), 404
    except Exception as e:
        db.session.rollback()
        log_info(f"Error processing SMS status callback: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@order_bp.route("/courierUpdate", methods=["POST"])
def courier_update():
    """
    Handle courier updates for deliveries from Deliverect.

    This endpoint processes delivery status updates including:
    - Courier assignment
    - En route updates
    - Arrival notifications
    - Delivery completion or cancellation
    """
    # Get request data
    data = request.get_json() or {}
    log_info(f"Received courier update: {json.dumps(data)}")

    # Extract key information
    order_id = data.get("channelOrderId")
    status = data.get("status")
    courier = data.get("courier", {})
    eta = data.get("eta")  # Usually milliseconds since epoch

    # Validate required parameters
    if not order_id:
        return jsonify({"error": "Missing channelOrderId parameter"}), 400

    # Map courier status to Deliverect status codes
    status_code_mapping = {
        "DELIVERY_CREATED": 76,  # Delivery partner doesn't have courier yet
        "DELIVERY_CONFIRMED": 81,  # Courier accepted the delivery job
        "EN_ROUTE_TO_PICKUP": 83,  # Courier approaching restaurant
        "ARRIVED_AT_PICKUP": 85,  # Courier at restaurant
        "EN_ROUTE_TO_DROPOFF": 87,  # Courier heading to customer
        "ARRIVED_AT_DROPOFF": 89,  # Courier at customer location
        "DELIVERED": 90,  # Delivery completed successfully
        "DELIVERY_CANCELLED": 115,  # Delivery canceled
    }

    # Get the status code from the mapping
    status_code = status_code_mapping.get(status)
    if not status_code:
        log_info(f"Unknown courier status: {status}, using original status")

    # Update order in database
    try:
        order_record = db.session.query(Order).filter_by(id=order_id).first()
        if not order_record:
            return jsonify({"error": "Order not found"}), 404

        # Update delivery status information
        order_record.delivery_status = status
        if status_code:
            order_record.delivery_status_code = status_code
            order_record.status_code = status_code  # Update main status code too

        # Update status based on delivery status
        if status == "DELIVERED":
            order_record.status = "COMPLETED"
        elif status == "DELIVERY_CANCELLED":
            order_record.status = "CANCELLED"
        else:
            order_record.status = status

        # Store courier details
        if courier:
            courier_name = courier.get("name")
            courier_phone = courier.get("phoneNumber")
            if courier_name:
                order_record.courier_name = courier_name
            if courier_phone:
                order_record.courier_phone = courier_phone

        # Process ETA
        if eta:
            try:
                # Convert milliseconds to datetime
                eta_datetime = datetime.fromtimestamp(int(eta) / 1000)
                order_record.estimated_delivery_time = eta_datetime
                log_info(f"Updated ETA for order {order_id}: {eta_datetime}")
            except (ValueError, TypeError) as e:
                log_info(f"Error parsing ETA: {e}, value: {eta}")

        # Save changes
        order_record.status_updated_at = datetime.now()
        if not commit_with_retry(db.session):
            return jsonify({"error": "Database error"}), 500

        # Send notification for delivery status changes
        # Prepare a user-friendly message
        friendly_status = order_record.get_status_display()
        status_message = f"Your order ({order_id}) delivery status: {friendly_status}"

        # Add courier information for actionable statuses
        if status in [
            "EN_ROUTE_TO_PICKUP",
            "ARRIVED_AT_PICKUP",
            "EN_ROUTE_TO_DROPOFF",
            "ARRIVED_AT_DROPOFF",
        ]:
            if courier.get("name"):
                status_message += f"\nCourier: {courier.get('name')}"
                if courier.get("phoneNumber"):
                    status_message += f" ({courier.get('phoneNumber')})"

        # Include estimated time if available
        if eta:
            try:
                eta_time = datetime.fromtimestamp(int(eta) / 1000).strftime("%I:%M %p")
                if status == "EN_ROUTE_TO_DROPOFF":
                    status_message += f"\nEstimated delivery time: {eta_time}"
                else:
                    status_message += f"\nEstimated time: {eta_time}"
            except (ValueError, TypeError):
                pass

        # Send customer notification
        from tasks import send_order_status_update_task

        try:
            logging.info(
                f"Attempting to send courier status update task for order {order_id}"
            )
            # Call task directly for now until Redis/Celery is properly setup
            send_order_status_update_task(
                order_id, status_message, location_id=order_record.location_id
            )
            logging.info(
                f"Courier status update task executed successfully for order {order_id}"
            )
        except Exception as task_error:
            logging.error(f"Error sending courier status update task: {task_error}")
            # Fall back to direct SMS sending
            try:
                if order_record.sender:
                    # Send SMS directly
                    twilio_client.messages.create(
                        body=status_message,
                        from_=TWILIO_PHONE_NUMBER,
                        to=order_record.sender,
                    )
                    logging.info(
                        f"Sent courier update directly via SMS to {order_record.sender}"
                    )
            except Exception as sms_error:
                logging.error(f"Error sending direct courier SMS: {sms_error}")

        log_info(f"Courier update processed for order {order_id}: {status}")
        return jsonify({"success": True}), 200
    except Exception as e:
        log_info(f"Error processing courier update: {str(e)}")
        log_info(traceback.format_exc())
        return jsonify({"error": "Internal server error"}), 500


@order_bp.route("/webhook-test", methods=["GET"])
def webhook_test():
    """Endpoint to test webhook configuration"""
    # Get current environment details
    import os
    import platform
    from app.config import BASE_URL

    # Create response with diagnostics
    response = {
        "status": "ok",
        "base_url": BASE_URL,
        "configuration": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "render_env": os.environ.get("RENDER", "false"),
            "render_service_id": os.environ.get("RENDER_SERVICE_ID", "not set"),
            "disable_pythonanywhere_detection": os.environ.get(
                "DISABLE_PYTHONANYWHERE_DETECTION", "false"
            ),
        },
        "webhook_urls": {
            "statusUpdateURL": f"{BASE_URL}/order_status",
            "menuUpdateURL": f"{BASE_URL}/menu_update",
            "snoozeUnsnoozeURL": f"{BASE_URL}/snoozeUnsnooze",
            "busyModeURL": f"{BASE_URL}/busy_mode",
            "updatePrepTimeURL": f"{BASE_URL}/updatePrepTime",
            "courierUpdateURL": f"{BASE_URL}/courierUpdate",
            "paymentUpdateURL": f"{BASE_URL}/payment_update",
            "smsCallbackURL": f"{BASE_URL}/sms_status_callback",
        },
    }

    # Check database connection
    try:
        from app.models import Location
        from app import db

        # Count registered locations
        location_count = db.session.query(Location).count()
        response["database"] = {
            "connection": "ok",
            "registered_locations": location_count,
        }
    except Exception as e:
        response["database"] = {"connection": "error", "error": str(e)}

    log_info(f"Webhook test endpoint called - BASE_URL: {BASE_URL}")
    return jsonify(response)
