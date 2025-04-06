import requests
import json
import uuid
import time
import threading
import logging
import re
from collections import defaultdict
from flask import Blueprint, request, session, Response, jsonify
from twilio.twiml.voice_response import VoiceResponse
from app.config import DELIVERECT_API_URL
from app.utils.deliverect import build_deliverect_order, get_deliverect_headers
from app.utils.menu_utils import find_menu_item_by_name
from app.utils.order_utils import (
    build_order_description,
    calculate_bill_amount,
    dtmf_yes_no,
    user_said_yes,
    user_said_no
)
from app.utils.menu_utils import load_menu_data, is_item_snoozed_timebased
from app.utils.helpers import log_info, commit_with_retry
from twilio.twiml.messaging_response import MessagingResponse
# Try to import from the original module first 
try:
    from app.utils.agent_utils import analyze_user_input, get_order_modifications
    logger = logging.getLogger(__name__)
    logger.info("Successfully imported OpenAI agent utilities in order routes")
except ImportError:
    # If that fails, use our simplified implementation
    from app.utils.agent_utils_simple import analyze_user_input, get_order_modifications
    logger = logging.getLogger(__name__)
    logger.warning("Using simplified agent utilities in order routes (OpenAI not available)")
from app import db
from app.models import Order

order_bp = Blueprint('order', __name__)
logger = logging.getLogger(__name__)

# Global variables and concurrency control
channel_status = 1  # 0: registered, 1: active, 2: inactive
BUSY_MODE_ACTIVE = False
recent_actions = defaultdict(
    lambda: {'timestamp': 0, 'lock': threading.Lock()})

# Constants
COOLDOWN_PERIOD = 60  # seconds
DEFAULT_PREP_TIME_BASE = 20  # minutes
PREP_TIME_PER_ITEM = 1  # minutes per item


def can_process_action(sender, action_key, cooldown=30):
    """Prevent rapid-fire actions from the same sender"""
    current_time = time.time()
    with recent_actions[sender]['lock']:
        last_time = recent_actions[sender].get(action_key, 0)
        if current_time - last_time > cooldown:
            recent_actions[sender][action_key] = current_time
            return True
        return False


@order_bp.route('/take_order', methods=['POST'])
def take_order():
    """Process a new order request from voice"""
    # Check if we're in busy mode
    if BUSY_MODE_ACTIVE:
        response = VoiceResponse()
        response.say(
            "We're currently busy and not accepting new orders right now. Goodbye!")
        response.hangup()
        return Response(str(response), mimetype='text/xml')

    # Load menu and check availability - force refresh to ensure we have latest data
    try:
        menu_data = load_menu_data(force_refresh=True)
        
        # Debug logging to see if menu data is loaded correctly
        item_count = len(menu_data.get('items', []) or [])
        logger.info(f"Menu data loaded: {item_count} items found")
        
        # Check if any items have valid names
        valid_name_count = sum(1 for item in menu_data.get('items', []) 
                               if item.get('name'))
        if valid_name_count == 0 and item_count > 0:
            logger.error(f"Menu has {item_count} items but none have names!")
            # Create an empty menu structure instead of default menu
            menu_data = {"items": [], "modifiers": [], "modifierGroups": [], "name_variants": {}}
            logger.info("Using default menu instead")
        
        # Get available items - items with names and not snoozed
        available_items = [
            item for item in menu_data.get('items', [])
            if item.get('name') and item.get("snoozed", False) == False and 
            item.get("available", True) == True
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
                        item for item in menu_data.get('items', [])
                        if item.get('name') and item.get("snoozed", False) == False
                    ]
                    logger.info(f"After processing: {len(available_items)} available items")
                except Exception as e:
                    logger.error(f"Error processing Deliverect format: {e}")
                    
        # If still no items, use an empty menu structure
        if not available_items:
            logger.warning("No available items found - creating empty menu structure")
            # Create an empty menu structure instead of default menu
            menu_data = {"items": [], "modifiers": [], "modifierGroups": [], "name_variants": {}}
            
            # Get available items from menu structure (will be empty)
            available_items = [
                item for item in menu_data.get('items', [])
                if item.get('name') and item.get("snoozed", False) == False
            ]
            logger.info(f"Using default menu with {len(available_items)} items")
            
        # Final check - if still no items, report menu unavailable  
        if not available_items:
            response = VoiceResponse()
            response.say(
                "I'm sorry, our menu is currently unavailable. Please try again later.")
            response.hangup()
            return Response(str(response), mimetype='text/xml')
            
    except Exception as e:
        logger.error(f"Error loading menu: {e}")
        response = VoiceResponse()
        response.say(
            "I'm sorry, we're experiencing technical difficulties. Please try again later.")
        response.hangup()
        return Response(str(response), mimetype='text/xml')

    # Get the user's speech
    user_resp = request.form.get('SpeechResult', '').strip()
    
    # Use the agent to analyze the order
    analysis = analyze_user_input(user_resp)
    intent = analysis.get('intent', 'other')
    
    # Build the voice response
    response = VoiceResponse()
    
    # If we couldn't understand the order, ask again
    if intent != 'order_food' or not analysis.get('menu_items'):
        with response.gather(
            input='speech',
            action='/take_order',
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto",
            timeout=3
        ) as g:
            g.say(
                "I'm sorry, I couldn't understand that request. Please repeat your order.")
        return Response(str(response), mimetype='text/xml')

    # Process menu items found by the agent
    order_items = []
    for item in analysis['menu_items']:
        # Check item availability
        if item.get("reference_handler") and any(
            menu_item.get("reference_handler") == item.get("reference_handler") and
            menu_item.get("snoozed", False)
            for menu_item in menu_data.get("items", [])
        ):
            response.say(
                f"Sorry, {item.get('name')} is not available right now. Goodbye!")
            response.hangup()
            return Response(str(response), mimetype='text/xml')
        
        order_items.append(item)

    # Calculate total and prepare confirmation
    calculate_bill_amount(order_items)
    order_description = build_order_description(order_items)
    session['bill_amount'] = int(session.get('total_price', 0) * 100)
    session['order_items_json'] = json.dumps(order_items)
    session['order_message'] = f"{order_description}\nYour total is ${session.get('total_price', 0):.2f}."
    
    # Ask for confirmation
    with response.gather(
        input='speech dtmf',
        action='/confirm_order_from_initial',
        enhanced=True,
        speech_model="phone_call",
        language="en-US",
        speech_timeout="auto",
        num_digits=1
    ) as g:
        g.say(session['order_message'] +
              " If correct, say yes or press 1. If you need changes, say no or press 2.")
    
    return Response(str(response), mimetype='text/xml')


@order_bp.route('/confirm_order_from_initial', methods=['POST'])
def confirm_order_from_initial():
    """Handle confirmation of the initial order"""
    # Get user response
    user_resp = (request.form.get('SpeechResult', '') or "").lower()
    dtmf_input = request.form.get('Digits', '')
    log_info(f"Order confirmation: Speech='{user_resp}', DTMF='{dtmf_input}'")
    
    # Interpret response
    interpreted = None
    if dtmf_input:
        interpreted = dtmf_yes_no(dtmf_input)
    else:
        if user_said_yes(user_resp):
            interpreted = "yes"
        elif user_said_no(user_resp):
            interpreted = "no"
    
    # Get order data from session
    order_items = json.loads(session.get('order_items_json', '[]'))
    order_id = session.get('order_id', '') or str(uuid.uuid4())
    session['order_id'] = order_id
    sender = session.get('sender', '')
    caller_name = session.get('caller_name', 'Valued Customer')
    
    # Create voice response
    response = VoiceResponse()
    log_info(f"User confirmation interpreted as: {interpreted}")
    
    # Handle "yes" - process the order
    if interpreted == "yes":
        # Check for newly snoozed items
        from app.utils.snooze_validator import validate_items_availability
        menu_data = load_menu_data(force_refresh=True)
        
        # Deep check for snoozed items
        available_items = validate_items_availability(order_items)
        unavailable_items = [item["name"] for item in order_items if item not in available_items]
        
        if unavailable_items:
            logger.info(f"Items unavailable at order confirmation: {unavailable_items}")
            with response.gather(
                input='speech dtmf',
                action='/handle_newly_snoozed_in_checkout',
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout="auto",
                num_digits=1
            ) as g:
                g.say("Sorry, the following item(s) are now unavailable: " +
                      ", ".join(unavailable_items) + ". Press 1 to remove them, 2 to cancel.")
            return Response(str(response), mimetype='text/xml')
            
        # Check cooldown
        if not can_process_action(sender, 'order_food', 60):
            response.say(
                "You're placing orders too quickly. Please wait a moment and try again.")
            return Response(str(response), mimetype='text/xml')
        
        # Save to database
        try:
            text_msg = session.get('order_message', '')
            new_order = Order(id=order_id, sender=sender,
                              caller_name=caller_name, message=text_msg)
            db.session.add(new_order)
            if not commit_with_retry(db.session):
                raise Exception("Commit failed")
            log_info(f"Order {order_id} saved successfully.")
        except Exception as e:
            db.session.rollback()
            response.say(
                "Sorry, we encountered a database issue. Please try again later.")
            return Response(str(response), mimetype='text/xml')

        # Get total price
        total_price = session.get('total_price', 0.0)

        # Build and send to Deliverect
        try:
            # Import the validation function to ensure all items have reference handlers
            from app.utils.order_utils import prepare_order_for_deliverect
            
            # Validate order items before building order 
            validated_items = prepare_order_for_deliverect(order_items)
            
            # Check if we still have valid items after validation
            if not validated_items:
                log_info("No valid items with reference handlers in order, cannot submit to Deliverect")
                # Don't fail here since we still want to save the order in our system
            else:
                # Build the order with validated items
                deliverect_payload = build_deliverect_order(
                    sender=sender, 
                    caller_name=caller_name, 
                    order_items=validated_items, 
                    total_price=total_price, 
                    order_id=order_id
                )
                
                response_deliv = requests.post(
                    DELIVERECT_API_URL, 
                    json=deliverect_payload, 
                    headers=get_deliverect_headers(),
                    timeout=10
                )
                
                if response_deliv.status_code != 200:
                    log_info(f"Deliverect API error: Status {response_deliv.status_code}, Response: {response_deliv.text}")
                else:
                    log_info(f"Deliverect order successfully submitted: {response_deliv.text}")
        except Exception as e:
            log_info(f"Error sending order to Deliverect: {str(e)}")

        # Send SMS confirmation (offload to Celery)
        import tasks
        tasks.send_confirmation_sms_task.delay(
            order_id, 
            session.get('order_message', ''), 
            sender, 
            caller_name, 
            session.get('bill_amount', 0), 
            order_items
        )
        
        # Calculate prep time and respond
        time_taken = DEFAULT_PREP_TIME_BASE + (PREP_TIME_PER_ITEM * len(order_items))
        response.say(
            f"Great! Your order is confirmed and will be ready in about {time_taken} minutes. A confirmation text with payment options will be sent to your phone. You can also text 'status' to this number anytime to check your order status. Thank you!")
        response.hangup()

    # Handle "no" - go to modification
    elif interpreted == "no":
        session['modification_in_progress'] = True
        with response.gather(
            input='speech',
            action='/new_modify_order',
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto"
        ) as g:
            g.say("OK, please describe how you'd like your order changed.")
    
    # Handle unclear response
    else:
        with response.gather(
            input='speech dtmf',
            action='/confirm_order_from_initial',
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto",
            num_digits=1
        ) as g:
            g.say(
                "I didn't catch that. Say yes or press 1 if correct, or no or press 2 to modify.")
    
    return Response(str(response), mimetype='text/xml')


@order_bp.route('/new_modify_order', methods=['POST'])
def new_modify_order():
    """Handle order modifications"""
    # Get user's modification request
    user_resp = request.form.get('SpeechResult', '').strip()
    log_info(f"User requested order modification: {user_resp}")
    current_order_items = json.loads(session.get('order_items_json', '[]'))
    
    # Use agent to interpret modifications
    modifications = get_order_modifications(user_resp, current_order_items)
    
    # Create response
    response = VoiceResponse()
    
    # If no valid modifications, ask again
    if not modifications or ("additions" not in modifications and "removals" not in modifications):
        with response.gather(
            input='speech',
            action='/new_modify_order',
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto"
        ) as g:
            g.say(
                "I didn't understand your modifications. Please clearly state what you'd like to add or remove.")
        return Response(str(response), mimetype='text/xml')
    
    # Apply modifications
    updated_items = apply_modifications(current_order_items, modifications)
    
    # Update session
    session['order_items_json'] = json.dumps(updated_items)
    calculate_bill_amount(updated_items)
    session['bill_amount'] = int(session.get('total_price', 0) * 100)
    order_description = build_order_description(updated_items)
    log_info(f"Order updated after modification: {updated_items}")
    
    # Confirm updated order
    confirmation_message = (
        f"Your order is now:\n{order_description}\nTotal: ${session.get('total_price', 0):.2f}. "
        "If correct, say yes or press 1. If you need changes, say no or press 2."
    )
    with response.gather(
        input='speech dtmf',
        action='/confirm_order_after_modification',
        enhanced=True,
        speech_model="phone_call",
        language="en-US",
        speech_timeout="auto",
        num_digits=1
    ) as g:
        g.say(confirmation_message)
    
    return Response(str(response), mimetype='text/xml')


def apply_modifications(current_order, modifications):
    """Apply modifications to an order, handling both old and new formats"""
    # Extract additions and removals from modifications
    additions = modifications.get("additions", [])
    removals = modifications.get("removals", [])
    
    # Create a dictionary of current order items by name (case-insensitive)
    current_order_by_name = {item["name"].lower(): item for item in current_order}
    
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
            # Use the dictionary format
            item_name = removal["name"].lower()
            quantity = removal["quantity"]
        
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
                    "modifier": []
                }
            else:
                # Check if the item exists in the menu before adding
                menu_item = find_menu_item_by_name(item_name)
                if menu_item:
                    # Found in menu, use proper data including reference handler
                    addition = {
                        "name": menu_item.get("name"),
                        "price": menu_item.get("price", 0),
                        "reference_handler": menu_item.get("reference_handler", ""),
                        "quantity": quantity,
                        "modifier": []
                    }
                else:
                    # Not found in menu, create basic structure but tell the user
                    logger.warning(f"[ORDER-MODIFY] Item not found in menu: {item_name}")
                    # This item will fail validation later and be removed
                    addition = {
                        "name": item_name.title(), 
                        "quantity": quantity,
                        "modifier": []
                    }
        
        # Use the dictionary format
        item_name = addition.get("name", "").lower()
        quantity = addition.get("quantity", 1)
        
        # If item already exists, update it
        if item_name in current_order_by_name:
            current_order_by_name[item_name]["quantity"] += quantity
            # Update modifiers if provided
            if "modifier" in addition:
                current_order_by_name[item_name]["modifier"] = addition.get("modifier", [])
        else:
            # Add new item
            current_order_by_name[item_name] = addition
    
    # Return the updated order as a list
    return list(current_order_by_name.values())


@order_bp.route('/confirm_order_after_modification', methods=['POST'])
def confirm_order_after_modification():
    """Handle confirmation after order modifications"""
    # Get user response
    user_resp = (request.form.get('SpeechResult', '') or "").strip().lower()
    dtmf_input = request.form.get('Digits', '')
    log_info(f"Final confirmation after modification: Speech='{user_resp}', DTMF='{dtmf_input}'")
    
    # Interpret response
    interpreted = None
    if dtmf_input:
        interpreted = dtmf_yes_no(dtmf_input)
    else:
        if user_said_yes(user_resp):
            interpreted = "yes"
        elif user_said_no(user_resp):
            interpreted = "no"
    
    # Get order data
    order_items = json.loads(session.get('order_items_json', '[]'))
    order_id = session.get('order_id', '') or str(uuid.uuid4())
    session['order_id'] = order_id
    sender = session.get('sender', '')
    caller_name = session.get('caller_name', 'Valued Customer')
    
    # Create response
    response = VoiceResponse()
    log_info(f"User final decision: {interpreted}")
    
    # Handle "yes" - process the order
    if interpreted == "yes":
        # Check for newly snoozed items using comprehensive validator
        from app.utils.snooze_validator import validate_items_availability
        menu_data = load_menu_data(force_refresh=True)
        
        # Deep check for snoozed items
        available_items = validate_items_availability(order_items)
        unavailable_items = [item["name"] for item in order_items if item not in available_items]
        
        if unavailable_items:
            logger.info(f"Items unavailable at final confirmation: {unavailable_items}")
            with response.gather(
                input='speech dtmf',
                action='/handle_newly_snoozed_in_checkout',
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout="auto",
                num_digits=1
            ) as g:
                g.say("Sorry, the following item(s) are now unavailable: " +
                      ", ".join(unavailable_items) + ". Press 1 to remove them, 2 to cancel.")
            return Response(str(response), mimetype='text/xml')
        
        # Check cooldown
        if not can_process_action(sender, 'order_food', 60):
            response.say(
                "You're placing orders too quickly. Please wait and try again.")
            return Response(str(response), mimetype='text/xml')
        
        # Save to database
        try:
            text_msg = session.get('order_message', '')
            new_order = Order(id=order_id, sender=sender,
                              caller_name=caller_name, message=text_msg)
            db.session.add(new_order)
            if not commit_with_retry(db.session):
                raise Exception("Commit failed")
            log_info(f"Order {order_id} saved successfully.")
        except Exception as e:
            db.session.rollback()
            response.say(
                "Sorry, we encountered a database issue. Please try again later.")
            return Response(str(response), mimetype='text/xml')
        
        # Send to Deliverect and SMS confirmation
        try:
            # Import the validation function to ensure all items have reference handlers
            from app.utils.order_utils import prepare_order_for_deliverect
            
            # Validate order items before building order 
            validated_items = prepare_order_for_deliverect(order_items)
            
            # Check if we still have valid items after validation
            if not validated_items:
                log_info("No valid items with reference handlers in order, cannot submit to Deliverect")
                # Don't fail here since we still want to save the order in our system
            else:
                # Build and send the order 
                deliverect_payload = build_deliverect_order(
                    sender=sender, 
                    caller_name=caller_name, 
                    order_items=validated_items, 
                    total_price=session.get('total_price', 0.0), 
                    order_id=order_id
                )
                
                response_deliv = requests.post(
                    DELIVERECT_API_URL, 
                    json=deliverect_payload, 
                    headers=get_deliverect_headers(),
                    timeout=10
                )
                
                if response_deliv.status_code != 200:
                    log_info(f"Deliverect API error: Status {response_deliv.status_code}, Response: {response_deliv.text}")
                else:
                    log_info(f"Deliverect order successfully submitted: {response_deliv.text}")
        except Exception as e:
            log_info(f"Error sending order to Deliverect: {str(e)}")
            
        # Always send SMS confirmation regardless of Deliverect status
        import tasks
        tasks.send_confirmation_sms_task.delay(
            order_id, 
            session.get('order_message', ''), 
            sender, 
            caller_name, 
            session.get('bill_amount', 0), 
            order_items
        )
        
        # Calculate prep time
        time_taken = DEFAULT_PREP_TIME_BASE + (PREP_TIME_PER_ITEM * len(order_items))
        
        # Clear the modification flag
        session.pop('modification_in_progress', None)
        
        # Confirm order
        response.say(
            f"Great! Your order is confirmed and will be ready in about {time_taken} minutes. A confirmation text with payment options will be sent to your phone. You can also text 'status' to this number anytime to check your order status. Thank you for choosing Red Bar Sushi! Goodbye.")
        response.hangup()
    
    # Handle "no" - go back to modification
    elif interpreted == "no":
        with response.gather(
            input='speech',
            action='/new_modify_order',
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto"
        ) as g:
            g.say(
                "What else would you like to change? Please describe the final order you want.")
    
    # Handle unclear response
    else:
        with response.gather(
            input='speech dtmf',
            action='/confirm_order_after_modification',
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto",
            num_digits=1
        ) as g:
            g.say(
                "I didn't catch that. Say 'yes' or press 1 if correct, 'no' or press 2 to modify again.")
    
    return Response(str(response), mimetype='text/xml')


@order_bp.route('/handle_newly_snoozed_in_checkout', methods=['POST'])
def handle_newly_snoozed_in_checkout():
    """Handle the case where items become unavailable during checkout"""
    # Get user response
    user_resp = request.form.get('SpeechResult', '')
    dtmf_input = request.form.get('Digits', '')
    
    # Create response
    response = VoiceResponse()
    
    # Get order items
    order_items = json.loads(session.get('order_items_json', '[]'))
    
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
    snoozed_items_str = ", ".join(unavailable_items) if unavailable_items else "Some items"
    
    # Handle "yes" - remove items and continue
    if dtmf_input == '1' or user_said_yes(user_resp):
        logger.info(f"Customer chose to remove unavailable items and continue")
        
        # Remove unavailable items using validator results
        updated_items = available_items
        logger.info(f"Removed {len(order_items) - len(updated_items)} items from order")
        
        # If order is now empty, cancel
        if not updated_items:
            response.say(f"All items in your order including {snoozed_items_str} are now unavailable. We apologize for the inconvenience. Goodbye.")
            response.hangup()
            return Response(str(response), mimetype='text/xml')
        
        # Update session with modified order
        session['order_items_json'] = json.dumps(updated_items)
        calculate_bill_amount(updated_items)
        session['bill_amount'] = int(session.get('total_price', 0) * 100)
        order_description = build_order_description(updated_items)
        session['order_message'] = f"{order_description}\nYour total is ${session.get('total_price', 0):.2f}."
        
        # Confirm updated order
        with response.gather(
            input='speech dtmf',
            action='/confirm_order_after_modification',
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto",
            num_digits=1
        ) as g:
            g.say(f"We removed {snoozed_items_str}. Your updated order is: {session['order_message']} If correct, say yes or press 1. If you need changes, say no or press 2.")
    
    # Handle "no" - cancel order
    else:
        response.say(f"We're sorry that {snoozed_items_str} is unavailable. Your order has been cancelled. Goodbye.")
        response.hangup()
    
    return Response(str(response), mimetype='text/xml')


@order_bp.route('/order_status', methods=['POST'])
def order_status():
    """Handle order status updates from Deliverect"""
    # Get request data
    data = request.get_json() or {}
    status = data.get("status")
    order_id = data.get("channelOrderId")
    code = data.get("code")
    
    # Validate required parameters
    if not order_id:
        return jsonify({"error": "Missing channelOrderId parameter"}), 400
    if not status:
        return jsonify({"error": "Missing status parameter"}), 400
    
    # Log failed orders
    if status == "FAILED" or code == 120:
        log_info(f"Order {order_id} failed with code={code} or status={status}.")
    
    # Update order in database
    try:
        order_record = db.session.query(Order).filter_by(id=order_id).first()
        if not order_record:
            return jsonify({"error": "Order not found"}), 404
        
        order_record.status = status
        if not commit_with_retry(db.session):
            return jsonify({"error": "Database error"}), 500
        
        # Create a more user-friendly status message
        friendly_status = {
            "NEW": "received and is being processed",
            "ACCEPTED": "accepted and being prepared",
            "PREPARING": "now being prepared in the kitchen",
            "READY": "ready for pickup",
            "COMPLETED": "completed. Thank you for your order!",
            "FAILED": "could not be processed. Please call us",
            "REJECTED": "could not be processed. Please call us",
            "CANCELLED": "cancelled"
        }.get(status, f"updated to: {status}")
        
        # Send status update to customer with user-friendly message
        status_message = f"Your order ({order_id}) is {friendly_status}"
        from tasks import send_order_status_update_task
        send_order_status_update_task.delay(order_id, status_message)
        
        return jsonify({"success": True}), 200
    except Exception as e:
        log_info(f"Error processing order status update: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@order_bp.route('/sms', methods=['POST'])
def handle_sms():
    """Handle incoming SMS messages for order status inquiries"""
    # Get the message sent
    message_body = request.values.get('Body', '').strip().lower()
    from_number = request.values.get('From', '')
    
    # Create a response
    resp = MessagingResponse()
    
    # Handle status requests
    if 'status' in message_body:
        try:
            # Find the most recent order for this number
            recent_order = db.session.query(Order).filter_by(
                sender=from_number
            ).order_by(Order.timestamp.desc()).first()
            
            if recent_order:
                # Get status and create friendly message
                order_status = recent_order.status or "NEW"
                
                friendly_status = {
                    "NEW": "received and is being processed",
                    "ACCEPTED": "accepted and being prepared",
                    "PREPARING": "now being prepared in the kitchen",
                    "READY": "ready for pickup",
                    "COMPLETED": "completed. Thank you for your order!",
                    "FAILED": "could not be processed. Please call us",
                    "REJECTED": "could not be processed. Please call us",
                    "CANCELLED": "cancelled"
                }.get(order_status, order_status)
                
                # Create a brief but informative message
                order_id = recent_order.id
                status_message = f"Your order ({order_id[:8]}...) is {friendly_status}"
                resp.message(status_message)
            else:
                resp.message("We couldn't find any recent orders for your number. Please call us for assistance.")
        except Exception as e:
            log_info(f"Error processing SMS status request: {str(e)}")
            resp.message("Sorry, we encountered an error processing your request. Please call us for assistance.")
    # Handle help or other inquiries    
    elif 'help' in message_body:
        resp.message("Text 'status' to check your order status. For other assistance, please call us.")
    else:
        resp.message("Thanks for your message! Text 'status' to check your order status or 'help' for assistance.")
    
    return Response(str(resp), mimetype='text/xml')

@order_bp.route('/register', methods=['POST'])
def register_channel_route():
    """Register or update channel status with Deliverect"""
    # Get request data
    data = request.get_json() or {}
    status = data.get("status")
    
    # Validate required parameters
    if not status:
        return jsonify({"error": "Missing status parameter"}), 400
    
    # Update channel status
    global channel_status
    if status == "register":
        channel_status = 0
        log_info("Channel registered with Deliverect")
    elif status == "active":
        channel_status = 1
        log_info("Channel activated with Deliverect")
    elif status == "inactive":
        channel_status = 2
        log_info("Channel deactivated with Deliverect")
    else:
        return jsonify({"error": f"Invalid status: {status}"}), 400
    
    # Get base URL from configuration instead of hardcoding
    from app.config import BASE_URL
    base_url = BASE_URL
    
    # Return webhook URLs - keeping original paths for compatibility
    response_body = {
        "statusUpdateURL": f"{base_url}/order_status",
        "menuUpdateURL": f"{base_url}/menu_update",
        "snoozeUnsnoozeURL": f"{base_url}/snoozeUnsnooze",
        "busyModeURL": f"{base_url}/busy_mode",
        "updatePrepTimeURL": f"{base_url}/updatePrepTime",
        "courierUpdateURL": f"{base_url}/courierUpdate"
    }
    return jsonify(response_body), 200
