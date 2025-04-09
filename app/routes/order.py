import requests
import json
import uuid
import time
import threading
import logging
import re
import traceback
from collections import defaultdict
from datetime import datetime
from flask import Blueprint, request, session, Response, jsonify
from twilio.twiml.voice_response import VoiceResponse
from app.config import DELIVERECT_API_URL, BASE_URL
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
from app import db, twilio_client
from app.models import Order
from app.config import TWILIO_NUMBER as TWILIO_PHONE_NUMBER

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
            "We're currently busy and not accepting new orders right now. Please call back later.")
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
    
    # Check if the user was silent or speech wasn't captured
    if not user_resp:
        # Track silence retries for this specific part of the flow
        order_silence_retry = session.get('order_silence_retry', 0)
        session['order_silence_retry'] = order_silence_retry + 1
        
        response = VoiceResponse()
        
        # Change the message based on how many retries
        if order_silence_retry >= 2:
            # After multiple tries, give more detailed guidance
            with response.gather(
                input='speech dtmf',
                action='/take_order',
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout="auto",
                timeout=10  # Give even more time for the third try
            ) as g:
                g.say(
                    "I'm having trouble hearing you. Speak clearly and tell me what sushi items you'd like to order. For example, say 'two California rolls and one spicy tuna roll'. Or press any key to return to the main menu.")
            
            # Add a fallback to main menu after gathering
            response.redirect('/main_menu_fallback')
        else:
            # Normal or first retry prompt
            with response.gather(
                input='speech',
                action='/take_order',
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout="auto",
                timeout=8  # Give more time for the user to think and speak
            ) as g:
                g.say(
                    "I'm waiting for your order. Please tell me what sushi items you'd like to order. For example, you can say 'I'd like two California rolls and one spicy tuna roll'.")
        return Response(str(response), mimetype='text/xml')
    
    # Use the agent to analyze the order
    analysis = analyze_user_input(user_resp)
    intent = analysis.get('intent', 'other')
    
    # Build the voice response
    response = VoiceResponse()
    
    # If we couldn't understand the order, ask again
    if intent != 'order_food' or not analysis.get('menu_items'):
        # Track understanding retries separately from silence
        understand_retry = session.get('understand_retry', 0)
        session['understand_retry'] = understand_retry + 1
        
        # Reset silence counter since we got some speech
        session['order_silence_retry'] = 0
        
        # Change approach based on retry count
        if understand_retry >= 2:
            # After multiple failed attempts, offer more options
            with response.gather(
                input='speech dtmf',
                action='/understanding_fallback',
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout="auto",
                num_digits=1,
                timeout=8  # More time
            ) as g:
                g.say(
                    "I'm having trouble understanding your order. You can try again by speaking clearly, press 1 to hear our popular menu items, or press 2 to return to the main menu.")
        else:
            # First retry with better guidance
            with response.gather(
                input='speech',
                action='/take_order',
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout="auto",
                timeout=8  # More time for the retry
            ) as g:
                g.say(
                    "I'm sorry, I couldn't understand your order. Please tell me again what items you'd like to order from our menu. For example, you can say 'I'd like a California roll and a spicy tuna roll'.")
        return Response(str(response), mimetype='text/xml')

    # Get the menu items from the analysis
    order_items = analysis.get('menu_items', [])
    
    # Process and mark any unavailable items
    from app.utils.order_utils import mark_unavailable_items
    available_items, unavailable_items = mark_unavailable_items(order_items)
    
    # Handle case where all items are unavailable
    if not available_items and unavailable_items:
        unavailable_names = [item.get("name").split(" (")[0] for item in unavailable_items]
        unavailable_text = ", ".join(unavailable_names)
        
        response.say(
            f"I'm sorry, the item(s) you requested ({unavailable_text}) are currently unavailable. Would you like to order something else?")
        # Gather a new response instead of hanging up
        with response.gather(
            input='speech',
            action='/take_order',
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto"
        ) as g:
            g.say("Please tell me what else you would like to order.")
        return Response(str(response), mimetype='text/xml')
    
    # Include both available and unavailable items in the order
    # (unavailable items will be shown separately in the order description)
    order_items = available_items + unavailable_items

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

        # Send SMS confirmation
        import tasks
        try:
            log_info(f"Attempting to send SMS confirmation task directly for order {order_id}")
            # Call task directly for now until Redis/Celery is properly setup
            tasks.send_confirmation_sms_task(
                order_id, 
                session.get('order_message', ''), 
                sender, 
                caller_name, 
                session.get('bill_amount', 0), 
                order_items
            )
            log_info(f"SMS confirmation task executed successfully for order {order_id}")
        except Exception as task_error:
            log_info(f"Error sending SMS confirmation: {task_error}")
            # Fall back to direct SMS sending
            try:
                # Send a simpler message directly
                order_msg = session.get('order_message', '')
                simple_msg = f"Thank you for your order! Your order ID is {order_id[:8]}. A confirmation will be sent shortly."
                twilio_client.messages.create(
                    body=simple_msg,
                    from_=TWILIO_PHONE_NUMBER,
                    to=sender
                )
                log_info(f"Sent simple order confirmation directly via SMS to {sender}")
            except Exception as sms_error:
                log_info(f"Error sending direct SMS confirmation: {sms_error}")
        
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
        # Track confirmation retries
        confirm_retry_count = session.get('confirm_retry_count', 0)
        session['confirm_retry_count'] = confirm_retry_count + 1
        
        if confirm_retry_count >= 2:
            # After multiple unclear responses, give simpler options
            with response.gather(
                input='dtmf',
                action='/confirm_order_from_initial',
                timeout=10,
                num_digits=1
            ) as g:
                g.say(
                    "Please use your keypad. Press 1 to confirm your order, or press 2 to modify it.")
        else:
            # Normal retry
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
    
    # Check if the user was silent or speech wasn't captured
    if not user_resp:
        # Track silence retries for modifications
        modify_silence_retry = session.get('modify_silence_retry', 0)
        session['modify_silence_retry'] = modify_silence_retry + 1
        
        response = VoiceResponse()
        
        # Change the message based on how many retries
        if modify_silence_retry >= 2:
            # After multiple tries, give more detailed guidance or fallback
            with response.gather(
                input='speech dtmf',
                action='/modification_silence_fallback',
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout="auto",
                num_digits=1,
                timeout=10  # Give even more time
            ) as g:
                g.say(
                    "I'm having trouble hearing your modifications. You can say something like 'add one spicy tuna roll' or 'remove the California roll'. Or press 1 to keep your order as is, or 2 to cancel.")
        else:
            # Normal or first retry prompt
            with response.gather(
                input='speech',
                action='/new_modify_order',
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout="auto",
                timeout=8  # Give more time
            ) as g:
                g.say(
                    "I'm waiting to hear your modifications. For example, you can say 'add one spicy tuna roll' or 'remove the California roll'.")
        return Response(str(response), mimetype='text/xml')
        
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
            speech_timeout="auto",
            timeout=6  # More time for the retry
        ) as g:
            g.say(
                "I didn't understand your modifications. Please clearly state what you'd like to add or remove from your order.")
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
    """Apply modifications to an order, handling all possible formats"""
    # Extract additions and removals from modifications
    additions = modifications.get("additions", [])
    removals = modifications.get("removals", [])
    
    # Ensure all removals have a "name" field
    for removal in removals:
        if isinstance(removal, dict):
            if "item" in removal and "name" not in removal:
                removal["name"] = removal["item"]
                logger.info(f"[ORDER-FIX] Copying 'item' to 'name' field in removal: {removal}")
    
    # Ensure all additions have a "name" field
    for addition in additions:
        if isinstance(addition, dict):
            if "item" in addition and "name" not in addition:
                addition["name"] = addition["item"]
                logger.info(f"[ORDER-FIX] Copying 'item' to 'name' field in addition: {addition}")
    
    # Create a dictionary of current order items by name (case-insensitive)
    current_order_by_name = {item["name"].lower(): item for item in current_order}
    
    # Detailed logging for debugging
    logger.info(f"[ORDER-MODIFY] Processing modifications: {json.dumps(modifications)}")
    logger.info(f"[ORDER-MODIFY] Current order: {json.dumps(current_order)}")
    logger.info(f"[ORDER-MODIFY] Processed additions: {json.dumps(additions)}")
    logger.info(f"[ORDER-MODIFY] Processed removals: {json.dumps(removals)}")
    
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
                    logger.warning(f"[ORDER-MODIFY] Skipping removal with no item name: {removal}")
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
                    logger.warning(f"[ORDER-MODIFY] Skipping addition with no item name: {addition}")
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
                if "reference_handler" not in addition or not addition["reference_handler"]:
                    addition["reference_handler"] = menu_item.get("reference_handler", "")
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
        try:
            log_info(f"Attempting to send SMS confirmation task directly for order {order_id}")
            # Call task directly for now until Redis/Celery is properly setup
            tasks.send_confirmation_sms_task(
                order_id, 
                session.get('order_message', ''), 
                sender, 
                caller_name, 
                session.get('bill_amount', 0), 
                order_items
            )
            log_info(f"SMS confirmation task executed successfully for order {order_id}")
        except Exception as task_error:
            log_info(f"Error sending SMS confirmation: {task_error}")
            # Fall back to direct SMS sending
            try:
                # Send a simpler message directly
                order_msg = session.get('order_message', '')
                simple_msg = f"Thank you for your order! Your order ID is {order_id[:8]}. A confirmation will be sent shortly."
                twilio_client.messages.create(
                    body=simple_msg,
                    from_=TWILIO_PHONE_NUMBER,
                    to=sender
                )
                log_info(f"Sent simple order confirmation directly via SMS to {sender}")
            except Exception as sms_error:
                log_info(f"Error sending direct SMS confirmation: {sms_error}")
        
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
        # Track final confirmation retries
        final_confirm_retry = session.get('final_confirm_retry', 0)
        session['final_confirm_retry'] = final_confirm_retry + 1
        
        if final_confirm_retry >= 2:
            # After multiple unclear responses, give simpler options and longer timeout
            with response.gather(
                input='dtmf',
                action='/confirm_order_after_modification',
                timeout=12,
                num_digits=1
            ) as g:
                g.say(
                    "Please use your keypad. Press 1 to confirm your order, or press 2 to modify it again.")
        else:
            # Normal retry
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


@order_bp.route('/understanding_fallback', methods=['POST'])
def understanding_fallback():
    """Handle fallbacks for when we can't understand the order after multiple tries."""
    # Get user response
    user_resp = (request.form.get('SpeechResult', '') or "").lower()
    dtmf_input = request.form.get('Digits', '')
    
    # Create response
    response = VoiceResponse()
    
    # If they pressed 1, give them popular menu suggestions
    if dtmf_input == '1' or "menu" in user_resp or "popular" in user_resp:
        # Reset understanding retry counter
        session['understand_retry'] = 0
        with response.gather(
            input='speech',
            action='/take_order',
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto",
            timeout=8  # Give more time
        ) as g:
            g.say(
                "Our most popular items are California Roll, Spicy Tuna Roll, Dragon Roll, and Rainbow Roll. " +
                "Please tell me what you would like to order.")
    # If they pressed 2 or want to go back, return to main menu
    elif dtmf_input == '2' or "back" in user_resp or "main" in user_resp:
        # Reset session variables for ordering
        session['understand_retry'] = 0
        session['order_silence_retry'] = 0
        response.redirect('/main_menu_fallback')
        return Response(str(response), mimetype='text/xml')
    # Otherwise try again with their speech input (if they provided any)
    elif user_resp:
        # Their response might be an order attempt, so pass it to take_order
        response.redirect('/take_order')
        return Response(str(response), mimetype='text/xml')
    else:
        # No input provided, return to main menu as fallback
        response.redirect('/main_menu_fallback')
        return Response(str(response), mimetype='text/xml')
    
    return Response(str(response), mimetype='text/xml')


@order_bp.route('/modification_silence_fallback', methods=['POST'])
def modification_silence_fallback():
    """Handle fallbacks for when we can't hear modification requests after multiple tries."""
    # Get user response
    user_resp = (request.form.get('SpeechResult', '') or "").lower()
    dtmf_input = request.form.get('Digits', '')
    
    # Create response
    response = VoiceResponse()
    
    # If they pressed 1 or said to keep order, confirm as is
    if dtmf_input == '1' or "keep" in user_resp or "as is" in user_resp:
        # Reset modification silence counter
        session['modify_silence_retry'] = 0
        
        # Redirect to confirmation
        response.redirect('/confirm_order_after_modification')
        return Response(str(response), mimetype='text/xml')
    # If they pressed 2 or said to cancel, go back to main menu
    elif dtmf_input == '2' or "cancel" in user_resp:
        # Reset session variables for ordering
        session['modify_silence_retry'] = 0
        session['modification_in_progress'] = False
        response.redirect('/main_menu_fallback')
        return Response(str(response), mimetype='text/xml')
    # Otherwise try again with their speech input (if they provided any)
    elif user_resp:
        # Their response might be a modification attempt, so pass it to new_modify_order
        response.redirect('/new_modify_order')
        return Response(str(response), mimetype='text/xml')
    else:
        # No input provided, just confirm the current order as is
        response.redirect('/confirm_order_after_modification')
        return Response(str(response), mimetype='text/xml')
    
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
    log_info(f"Received status update: order={order_id}, status={status}, code={status_code}")
    log_info(f"Full Deliverect payload: {json.dumps(data)}")
    
    # Validate required parameters
    if not order_id:
        return jsonify({"error": "Missing channelOrderId parameter"}), 400
    if not status and not status_code:
        return jsonify({"error": "Missing status or code parameter"}), 400
    
    # Log failed orders with enhanced details
    if status == "FAILED" or status_code == 120:
        error_reason = data.get("errorReason", "Unknown error")
        log_info(f"Order {order_id} failed with code={status_code}, status={status}, reason: {error_reason}")
    
    # Update order in database with comprehensive status information
    try:
        # First try to get the order
        try:
            order_record = db.session.query(Order).filter_by(id=order_id).first()
        except Exception as db_err:
            # If we get a column does not exist error, it means we haven't migrated the database yet
            if "column order.status_code does not exist" in str(db_err):
                log_info("Database schema needs migration. Using legacy query without new columns.")
                # Use a simpler query that doesn't reference the new columns
                sql = text("SELECT id, sender, caller_name, message, status, timestamp, location_id, "
                           "sms_sid, sms_status, sms_error_code, sms_error_message "
                           "FROM \"order\" WHERE id = :order_id LIMIT 1")
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
        previous_code = getattr(order_record, 'status_code', None)
        
        # Update status field that should always exist
        order_record.status = status
        
        # Check if new columns are available in the database 
        try:
            # Try to update new columns - if they don't exist in db, these will be ignored
            if hasattr(order_record, 'status_code'):
                order_record.status_code = status_code
            if hasattr(order_record, 'status_updated_at'):
                order_record.status_updated_at = datetime.now()
            
            # Handle delivery specific information if columns exist
            if status_code in [76, 81, 83, 85, 87, 89]:
                # This is a delivery status
                if hasattr(order_record, 'delivery_status'):
                    order_record.delivery_status = status
                if hasattr(order_record, 'delivery_status_code'):
                    order_record.delivery_status_code = status_code
                
                # Store courier information if provided and columns exist
                if courier_name and hasattr(order_record, 'courier_name'):
                    order_record.courier_name = courier_name
                if courier_phone and hasattr(order_record, 'courier_phone'):
                    order_record.courier_phone = courier_phone
                
                # Parse and store ETA if provided and column exists
                if eta and hasattr(order_record, 'estimated_delivery_time'):
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
                log_info("Full update failed, trying simplified update with just status.")
                sql = text("UPDATE \"order\" SET status = :status WHERE id = :order_id")
                db.session.execute(sql, {"status": status, "order_id": order_id})
                db.session.commit()
        except Exception as commit_err:
            log_info(f"Error committing changes: {commit_err}")
            # Try the most basic update possible
            try:
                sql = text("UPDATE \"order\" SET status = :status WHERE id = :order_id")
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
            20,   # Accepted - Order confirmed
            50,   # Preparing - In preparation
            70,   # Pickup Ready - Ready for collection
            76,   # Delivery Created - Looking for courier
            83,   # En Route to Pickup - Courier approaching
            87,   # En Route To Dropoff - Courier heading to customer
            89,   # Arrived At Drop Off - Courier at customer location
            90,   # Finalized/Delivered - Order completed
            110,  # Canceled - Order canceled
            120   # Failed - Order failed
        ]
        
        # Notify on first status update, status code changes, or major status changes
        if previous_status != status or previous_code != status_code or status_code in major_status_changes:
            should_notify = True
        
        # Special handling for delivery events - always notify
        if status_code in [76, 81, 83, 85, 87, 89]:
            should_notify = True
            
        # Don't notify for system-only statuses unless configured
        if status_code in [1, 2, 3, 4, 5, 6, 7]:
            should_notify = False  # System internal statuses, no customer notification needed
            
        # Create a detailed status message with courier info if applicable
        if should_notify:
            # Generate simple status message for compatibility or friendly message if columns exist
            try:
                # First try to use the advanced status description
                friendly_status = order_record.get_status_display()
                status_message = f"Your order ({order_id[:8]}) status: {friendly_status}"
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
                    eta_time = datetime.fromtimestamp(int(eta) / 1000).strftime("%I:%M %p")
                    status_message += f"\nEstimated delivery/pickup time: {eta_time}"
                except Exception as eta_err:
                    log_info(f"Error formatting ETA: {eta_err}")
            elif hasattr(order_record, 'estimated_delivery_time') and order_record.estimated_delivery_time:
                try:
                    eta_time = order_record.estimated_delivery_time.strftime("%I:%M %p")
                    status_message += f"\nEstimated delivery/pickup time: {eta_time}"
                except Exception as eta_err:
                    log_info(f"Error formatting stored ETA: {eta_err}")
            
            # Send status update to customer with enhanced information
            from tasks import send_order_status_update_task
            try:
                logging.info(f"Attempting to send status update task for order {order_id}")
                # Call the task directly for now until Redis/Celery is properly setup
                send_order_status_update_task(
                    order_id, 
                    status_message,
                    location_id=order_record.location_id
                )
                logging.info(f"Status update task executed successfully for order {order_id}")
            except Exception as task_error:
                logging.error(f"Error sending status update task: {task_error}")
                # Fall back to direct SMS sending if task execution fails
                try:
                    # Import necessary components
                    from app.models import Order
                    
                    # Get the order detail
                    order = db.session.get(Order, order_id)
                    if order and order.sender:
                        # Send SMS directly
                        twilio_client.messages.create(
                            body=status_message,
                            from_=TWILIO_PHONE_NUMBER,
                            to=order.sender
                        )
                        logging.info(f"Sent status update directly via SMS to {order.sender}")
                except Exception as sms_error:
                    logging.error(f"Error sending direct SMS: {sms_error}")
            
            log_info(f"Notification sent for order {order_id}: {status_message}")
        else:
            log_info(f"No notification sent for order {order_id} - internal status update only")
        
        return jsonify({"success": True}), 200
    except Exception as e:
        log_info(f"Error processing order status update: {str(e)}")
        log_info(traceback.format_exc())
        return jsonify({"error": "Internal server error"}), 500


@order_bp.route('/sms', methods=['POST'])
def handle_sms():
    """Handle incoming SMS messages for order status inquiries and other commands"""
    # Get the message sent
    message_body = request.values.get('Body', '').strip().lower()
    from_number = request.values.get('From', '')
    
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
    log_info(f"SMS COMMAND DEBUG - Keyword match: {any(keyword in message_body for keyword in ['help', 'command', 'info', 'option'])}")
    
    # Make sure we handle messages even if empty or malformed
    if not message_body:
        message_body = ""
        log_info("Received empty message body, treating as default welcome")
    
    # Handle different command types with flexible matching for user convenience
    # First, try exact match for common commands (for better reliability)
    command_type = message_body.strip().lower()
    
    if command_type == "status" or command_type == "order" or command_type == "check" or command_type == "stat" or any(keyword in message_body for keyword in ['status', 'stat', 'check', 'order']):
        try:
            # Find the most recent order for this number
            recent_order = db.session.query(Order).filter_by(
                sender=from_number
            ).order_by(Order.timestamp.desc()).first()
            
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
                        "CANCELLED": "cancelled"
                    }.get(order_status, order_status)
                
                # Extract order details for a more detailed response
                order_id = recent_order.id
                order_time = recent_order.timestamp.strftime("%I:%M %p") if recent_order.timestamp else "unknown time"
                
                # Extract order items from the stored message
                order_items = "your order"
                if recent_order.message and "\n-" in recent_order.message:
                    try:
                        items_section = recent_order.message.split("YOUR ORDER:")[1].split("\n\n")[0] if "YOUR ORDER:" in recent_order.message else ""
                        if items_section:
                            # Ensure consistent formatting with × for quantities
                            formatted_lines = []
                            for line in items_section.strip().split('\n'):
                                if line.startswith('- '):
                                    if ' × ' not in line and ' x ' not in line:
                                        parts = line.strip('- ').split(' ', 1)
                                        if len(parts) == 2 and parts[0].isdigit():
                                            quantity, name = parts
                                            line = f"- {quantity}× {name}"
                                formatted_lines.append(line)
                            order_items = '\n'.join(formatted_lines)
                    except:
                        # If we can't parse properly, just use the first line as fallback
                        order_items = recent_order.message.split("\n")[0] if recent_order.message else "your order"
                
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
                        location = db.session.query(Location).filter_by(id=recent_order.location_id).first()
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
                        eta_time = recent_order.estimated_delivery_time.strftime("%I:%M %p")
                        status_message += f"\n⏱️ Estimated delivery: {eta_time}"
                    
                    # Add delivery status-specific information
                    if recent_order.status_code == 83:
                        status_message += "\nYour courier is on the way to the restaurant"
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
                        prep_time = 20 + (len(recent_order.message.split("\n- ")) * 2)  # Estimate based on line count
                        time_elapsed = (time.time() - recent_order.timestamp.timestamp()) / 60 if recent_order.timestamp else 0
                        time_remaining = max(1, prep_time - time_elapsed)
                        status_message += f"\n\n⏱️ Estimated to be ready in: {int(time_remaining)} minutes"
                elif recent_order.status_code in [110, 120]:  # Failed/error states
                    status_message += "\n\n⚠️ Please call us at (833) 324-7207 regarding your order"
                
                # Add footer with help option
                status_message += "\n\n💬 Reply 'help' for more options"
                
                resp.message(status_message)
                log_info(f"Sent enhanced status update via SMS to {from_number}")
            else:
                resp.message("""⚠️ ORDER NOT FOUND

We couldn't find any recent orders for your number. 

• If you just placed an order, please wait a moment and try again
• If you're trying to place an order, please call us at (833) 324-7207

Reply 'menu' to see our menu options.""")
                log_info(f"No order found for {from_number}")
        except Exception as e:
            log_info(f"Error processing SMS status request: {str(e)}")
            resp.message("⚠️ Sorry, we encountered an error processing your request. Please call us at (833) 324-7207 for assistance.")
    
    # Handle help command - ensure we detect both exact and keyword matches
    elif command_type == "help" or "help" in message_body or any(keyword in message_body for keyword in ['command', 'info', 'option', '?']):
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
    elif command_type == "menu" or any(keyword in message_body for keyword in ['menu', 'food', 'eat', 'dish', 'price']):
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
    elif command_type == "hours" or any(keyword in message_body for keyword in ['hour', 'time', 'open', 'close']):
        resp.message("""🍣 RED BAR SUSHI HOURS 🍣

⏰ REGULAR HOURS:
Monday - Thursday: 11am - 9pm
Friday - Saturday: 11am - 10pm
Sunday: 12pm - 8pm

🔴 HAPPY HOUR:
Monday-Friday: 3pm - 6pm
$2 off all rolls and appetizers!

We look forward to serving you soon!
""")
        log_info(f"Sent hours info via SMS to {from_number}")
    
    # Handle location request
    elif command_type == "location" or any(keyword in message_body for keyword in ['location', 'address', 'where', 'map', 'direction']):
        resp.message("""🍣 RED BAR SUSHI LOCATION 🍣

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
""")
        log_info(f"Sent location info via SMS to {from_number}")
    
    # Handle contact request
    elif command_type == "contact" or any(keyword in message_body for keyword in ['contact', 'phone', 'call', 'reach']):
        resp.message("""🍣 RED BAR SUSHI CONTACT INFO 🍣

📞 PHONE: (833) 324-7207
📧 EMAIL: hello@redbarsushi.com
🌐 WEBSITE: redbarsushi.com
📱 SOCIAL: @RedBarSushi

For fastest response, please call us!
""")
        log_info(f"Sent contact info via SMS to {from_number}")
    
    # Handle specials request
    elif command_type == "specials" or any(keyword in message_body for keyword in ['special', 'deal', 'offer', 'discount', 'promotion']):
        # Get the current day of the week
        import datetime
        day_of_week = datetime.datetime.now().strftime('%A')
        
        # Create day-specific special
        day_special = {
            'Monday': "Maki Monday: 20% off all maki rolls!",
            'Tuesday': "Tuna Tuesday: $2 off tuna rolls!",
            'Wednesday': "Wasabi Wednesday: Free appetizer with $30+ order!",
            'Thursday': "Tempura Thursday: 15% off all tempura dishes!",
            'Friday': "Fusion Friday: Try our special fusion rolls!",
            'Saturday': "Sashimi Saturday: Premium sashimi platters 10% off!",
            'Sunday': "Sunday Special: Kids eat free with adult entrée!"
        }.get(day_of_week, "Daily special: 10% off your first order!")
        
        resp.message(f"""🍣 RED BAR SUSHI SPECIALS 🍣

✨ TODAY'S SPECIAL ({day_of_week}):
{day_special}

🔥 CURRENT PROMOTIONS:
• Buy 2 specialty rolls, get 1 regular roll free!
• Order online for 5% discount
• Happy Hour: 3-6pm daily with $2 off all rolls

📱 Show this message when ordering to redeem!
""")
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
    
    return Response(str(resp), mimetype='text/xml')

@order_bp.route('/register', methods=['POST'])
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
    channel_location_id = data.get("channelLocationId")
    channel_link_id = data.get("channelLinkId")
    location_id = data.get("locationId")
    channel_link_name = data.get("channelLinkName")
    
    # Update channel status
    global channel_status
    if status == "register":
        channel_status = 0
        log_info(f"Channel registered with Deliverect: {channel_link_name} (ID: {location_id})")
        
        # Save location details to database if we have a location ID
        if location_id and channel_link_name:
            try:
                from app.utils.deliverect import register_new_location
                webhook_base = BASE_URL
                success = register_new_location(
                    location_id=location_id,
                    location_name=channel_link_name,
                    webhook_base=webhook_base
                )
                if success:
                    log_info(f"Successfully registered location {location_id} in database")
                else:
                    log_info(f"Failed to register location {location_id} in database")
            except Exception as e:
                log_info(f"Error registering location: {e}")
        
    elif status == "active":
        channel_status = 1
        log_info(f"Channel activated with Deliverect: {channel_link_name} (ID: {location_id})")
        
        # Update location status if we have a location ID
        if location_id:
            try:
                from app.utils.deliverect import update_location_status
                update_location_status(location_id, "active")
            except Exception as e:
                log_info(f"Error updating location status: {e}")
                
    elif status == "inactive":
        channel_status = 2
        log_info(f"Channel deactivated with Deliverect: {channel_link_name} (ID: {location_id})")
        
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
        "paymentUpdateURL": f"{BASE_URL}/payment_update"
    }
    
    log_info(f"Registered webhooks with base URL: {BASE_URL}")
    log_info(f"Response: {json.dumps(response_body)}")
    return jsonify(response_body), 200

@order_bp.route('/sms_status_callback', methods=['POST'])
def sms_status_callback():
    """Handle SMS delivery status callbacks from Twilio"""
    # Extract data from the callback
    message_sid = request.values.get('MessageSid', '')
    message_status = request.values.get('MessageStatus', '')
    error_code = request.values.get('ErrorCode', None)
    error_message = request.values.get('ErrorMessage', None)
    to_number = request.values.get('To', '')
    
    log_info(f"SMS status callback received - SID: {message_sid}, Status: {message_status}, To: {to_number}")
    
    # If there's an error, log it with enhanced detail
    if error_code or error_message:
        log_info(f"SMS delivery error - Code: {error_code}, Message: {error_message}, To: {to_number}")
        
        # Auto-retry logic for failed messages (if error is recoverable)
        recoverable_errors = ['30001', '30002', '30003', '30004', '30005', '30006', '30007']
        if error_code in recoverable_errors and to_number:
            log_info(f"Queueing retry for recoverable error {error_code} to {to_number}")
            # This will be implemented if needed - would need a celery task
    
    # Find the order with this SMS SID
    try:
        try:
            # First try standard query
            order = db.session.query(Order).filter_by(sms_sid=message_sid).first()
        except Exception as db_err:
            # If we get a column does not exist error, it means we haven't migrated the database yet
            if "column order.status_code does not exist" in str(db_err):
                log_info("Database schema needs migration. Using legacy query for SMS status.")
                # Use a simpler query that doesn't reference the new columns
                sql = text("SELECT id, sender, caller_name, message, status, timestamp, location_id, "
                        "sms_sid, sms_status, sms_error_code, sms_error_message "
                        "FROM \"order\" WHERE sms_sid = :sms_sid LIMIT 1")
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
            if message_status == 'delivered':
                log_info(f"SMS successfully delivered to {to_number} for order {order.id}")
            elif message_status == 'undelivered' or message_status == 'failed':
                log_info(f"SMS delivery failed to {to_number} for order {order.id}: {error_code} - {error_message}")
                
            # Try to commit the changes - handle errors with simple SQL if needed
            try:
                if not commit_with_retry(db.session):
                    # If commit failed, try a simpler update with just the status
                    log_info("Full update failed, trying simplified SMS status update.")
                    sql = text("UPDATE \"order\" SET sms_status = :status WHERE id = :order_id")
                    db.session.execute(sql, {"status": message_status, "order_id": order.id})
                    db.session.commit()
            except Exception as commit_err:
                log_info(f"Error committing SMS status changes: {commit_err}")
                # Try the most basic update possible
                try:
                    sql = text("UPDATE \"order\" SET sms_status = :status WHERE id = :order_id")
                    db.session.execute(sql, {"status": message_status, "order_id": order.id})
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
                    recent_order = db.session.query(Order).filter_by(
                        sender=to_number
                    ).order_by(Order.timestamp.desc()).first()
                except Exception as db_err:
                    # If we get a column does not exist error, use direct SQL
                    if "column order.status_code does not exist" in str(db_err):
                        log_info("Using legacy query to find order by phone number.")
                        sql = text("SELECT id, sender, caller_name, message, status, timestamp, location_id, "
                                "sms_sid, sms_status, sms_error_code, sms_error_message "
                                "FROM \"order\" WHERE sender = :sender ORDER BY timestamp DESC LIMIT 1")
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
                        sql = text("UPDATE \"order\" SET sms_sid = :sms_sid, sms_status = :status WHERE id = :order_id")
                        params = {
                            "sms_sid": message_sid,
                            "status": message_status,
                            "order_id": recent_order.id
                        }
                        if error_code:
                            sql = text("UPDATE \"order\" SET sms_sid = :sms_sid, sms_status = :status, "
                                    "sms_error_code = :error_code WHERE id = :order_id")
                            params["error_code"] = error_code
                        if error_message:
                            sql = text("UPDATE \"order\" SET sms_sid = :sms_sid, sms_status = :status, "
                                    "sms_error_message = :error_message WHERE id = :order_id")
                            params["error_message"] = error_message
                        
                        db.session.execute(sql, params)
                        db.session.commit()
                        log_info(f"Updated SMS status for order {recent_order.id} using direct SQL")
                    except Exception as sql_err:
                        log_info(f"Error with direct SQL update for order by phone: {sql_err}")
                        return jsonify({"success": False, "error": "Database error"}), 500
                    
                    log_info(f"Updated SMS status for recent order {recent_order.id} (matched by phone number)")
                    return jsonify({"success": True}), 200
            
            log_info(f"No order found with SMS SID: {message_sid} or number: {to_number}")
            return jsonify({"success": False, "error": "Order not found"}), 404
    except Exception as e:
        db.session.rollback()
        log_info(f"Error processing SMS status callback: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@order_bp.route('/courierUpdate', methods=['POST'])
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
        "DELIVERY_CREATED": 76,               # Delivery partner doesn't have courier yet
        "DELIVERY_CONFIRMED": 81,             # Courier accepted the delivery job
        "EN_ROUTE_TO_PICKUP": 83,             # Courier approaching restaurant
        "ARRIVED_AT_PICKUP": 85,              # Courier at restaurant
        "EN_ROUTE_TO_DROPOFF": 87,            # Courier heading to customer
        "ARRIVED_AT_DROPOFF": 89,             # Courier at customer location
        "DELIVERED": 90,                      # Delivery completed successfully
        "DELIVERY_CANCELLED": 115             # Delivery canceled
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
        if status in ["EN_ROUTE_TO_PICKUP", "ARRIVED_AT_PICKUP", "EN_ROUTE_TO_DROPOFF", "ARRIVED_AT_DROPOFF"]:
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
            logging.info(f"Attempting to send courier status update task for order {order_id}")
            # Call task directly for now until Redis/Celery is properly setup
            send_order_status_update_task(
                order_id, 
                status_message,
                location_id=order_record.location_id
            )
            logging.info(f"Courier status update task executed successfully for order {order_id}")
        except Exception as task_error:
            logging.error(f"Error sending courier status update task: {task_error}")
            # Fall back to direct SMS sending
            try:
                if order_record.sender:
                    # Send SMS directly
                    twilio_client.messages.create(
                        body=status_message,
                        from_=TWILIO_PHONE_NUMBER,
                        to=order_record.sender
                    )
                    logging.info(f"Sent courier update directly via SMS to {order_record.sender}")
            except Exception as sms_error:
                logging.error(f"Error sending direct courier SMS: {sms_error}")
        
        log_info(f"Courier update processed for order {order_id}: {status}")
        return jsonify({"success": True}), 200
    except Exception as e:
        log_info(f"Error processing courier update: {str(e)}")
        log_info(traceback.format_exc())
        return jsonify({"error": "Internal server error"}), 500
        
@order_bp.route('/webhook-test', methods=['GET'])
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
            "render_env": os.environ.get('RENDER', 'false'),
            "render_service_id": os.environ.get('RENDER_SERVICE_ID', 'not set'),
            "disable_pythonanywhere_detection": os.environ.get('DISABLE_PYTHONANYWHERE_DETECTION', 'false')
        },
        "webhook_urls": {
            "statusUpdateURL": f"{BASE_URL}/order_status",
            "menuUpdateURL": f"{BASE_URL}/menu_update", 
            "snoozeUnsnoozeURL": f"{BASE_URL}/snoozeUnsnooze",
            "busyModeURL": f"{BASE_URL}/busy_mode",
            "updatePrepTimeURL": f"{BASE_URL}/updatePrepTime",
            "courierUpdateURL": f"{BASE_URL}/courierUpdate",
            "paymentUpdateURL": f"{BASE_URL}/payment_update",
            "smsCallbackURL": f"{BASE_URL}/sms_status_callback"
        }
    }
    
    # Check database connection
    try:
        from app.models import Location
        from app import db
        # Count registered locations
        location_count = db.session.query(Location).count()
        response["database"] = {
            "connection": "ok",
            "registered_locations": location_count
        }
    except Exception as e:
        response["database"] = {
            "connection": "error",
            "error": str(e)
        }
    
    log_info(f"Webhook test endpoint called - BASE_URL: {BASE_URL}")
    return jsonify(response)
