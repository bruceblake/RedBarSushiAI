# app/routes/order.py

import json
import uuid
import time
import threading
import logging
import requests
from collections import defaultdict
from flask import Blueprint, request, session, Response, jsonify
from twilio.twiml.voice_response import VoiceResponse
from app.config import DELIVERECT_CLIENT_ID, DELIVERECT_CLIENT_SECRET, BASE_URL, DELIVERECT_API_URL
from app.utils.deliverect import build_deliverect_order, get_deliverect_headers
from app.utils.order_utils import (
    analyze_user_input,
    user_said_yes,
    user_said_no,
    dtmf_yes_no,
    build_order_description,
    calculate_bill_amount,
    find_menu_item,
    find_menu_item_any_status
)
from app.utils.menu_utils import load_menu_data, is_item_snoozed_timebased
from app.utils.helpers import log_info, commit_with_retry
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
    current_time = time.time()
    with recent_actions[sender]['lock']:
        last_time = recent_actions[sender].get(action_key, 0)
        if current_time - last_time > cooldown:
            recent_actions[sender][action_key] = current_time
            return True
        return False


@order_bp.route('/take_order', methods=['POST'])
def take_order():
    if BUSY_MODE_ACTIVE:
        response = VoiceResponse()
        response.say(
            "We're currently busy and not accepting new orders right now. Goodbye!")
        response.hangup()
        return Response(str(response), mimetype='text/xml')

    data = load_menu_data()
    available_items = [it for it in data.get(
        "items", []) if it.get("available")]
    response = VoiceResponse()
    if not available_items:
        response.say(
            "I'm sorry, our menu is currently unavailable. Please try again later.")
        response.hangup()
        return Response(str(response), mimetype='text/xml')

    user_resp = request.form.get('SpeechResult', '').strip()
    # Consider offloading this asynchronously in production
    analysis = analyze_user_input(user_resp)
    intent = analysis.get('intent', 'other')
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
                "I’m sorry, I couldn’t understand that request. Please repeat your order.")
        return Response(str(response), mimetype='text/xml')

    order_items = []
    for item_entity in analysis['menu_items']:
        item_name = item_entity.get("name", "")
        matched_item, _ = find_menu_item_any_status(item_name)
        if not matched_item:
            response.say(f"Sorry, we don’t have {item_name} on our menu.")
            response.hangup()
            return Response(str(response), mimetype='text/xml')
        if not matched_item.get("available", False):
            response.say(
                f"Sorry, {matched_item['name']} is not available right now. Goodbye!")
            response.hangup()
            return Response(str(response), mimetype='text/xml')
        quantity = item_entity.get("quantity", 1)
        order_items.append({
            "name": item_name,
            "reference_handler": matched_item.get("reference_handler", ""),
            "modifier": item_entity.get("modifier", []),
            "quantity": quantity,
            "price": matched_item.get("price", 0.0)
        })

    calculate_bill_amount(order_items)
    order_description = build_order_description(order_items)
    order_id = str(uuid.uuid4())
    session['bill_amount'] = int(session['total_price'] * 100)
    session['order_items_json'] = json.dumps(order_items)
    session['order_message'] = f"{order_description}\nYour total is ${session['total_price']:.2f}."
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
    user_resp = (request.form.get('SpeechResult', '') or "").lower()
    dtmf_input = request.form.get('Digits', '')
    log_info(f"Order confirmation: Speech='{user_resp}', DTMF='{dtmf_input}'")
    interpreted = None
    if dtmf_input:
        result = dtmf_yes_no(dtmf_input)
        interpreted = result if result else None
    else:
        if user_said_yes(user_resp):
            interpreted = "yes"
        elif user_said_no(user_resp):
            interpreted = "no"
    order_items = json.loads(session.get('order_items_json', '[]'))
    order_id = session.get('order_id', '') or str(uuid.uuid4())
    session['order_id'] = order_id
    sender = session.get('sender', '')
    caller_name = session.get('caller_name', 'Valued Customer')
    response = VoiceResponse()
    log_info(f"User confirmation interpreted as: {interpreted}")
    if interpreted == "yes":
        if not can_process_action(sender, 'order_food', 60):
            response.say(
                "You're placing orders too quickly. Please wait a moment and try again.")
            return Response(str(response), mimetype='text/xml')
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

         # In app/routes/order.py, after order confirmation and before sending SMS confirmation
         # Assume total_price is stored in session['total_price'] (a float)
        total_price = session.get('total_price', 0.0)

        # Build the Deliverect payload
        deliverect_payload = build_deliverect_order(
            sender=sender, caller_name=caller_name, order_items=order_items, total_price=total_price, order_id=order_id)

        # Send the order to Deliverect
        try:
            deliverect_url = DELIVERECT_API_URL
            response_deliv = requests.post(
                deliverect_url, 
                json=deliverect_payload, 
                headers=get_deliverect_headers(),
                timeout=10
            )
            
            if response_deliv.status_code != 200:
                log_info(f"Deliverect API error: Status {response_deliv.status_code}, Response: {response_deliv.text}")
            else:
                log_info(f"Deliverect order successfully submitted: {response_deliv.text}")
        except requests.RequestException as e:
            log_info(f"Error sending order to Deliverect: {str(e)}")
            # Consider implementing a retry mechanism or fallback here

            # Offload SMS confirmation to Celery
        from tasks import send_confirmation_sms_task
        send_confirmation_sms_task.delay(order_id, session.get(
            'order_message', ''), sender, caller_name, session.get('bill_amount', 0), order_items)
        time_taken = DEFAULT_PREP_TIME_BASE + (PREP_TIME_PER_ITEM * len(order_items))
        response.say(
            f"Great! Your order is confirmed and will be ready in about {time_taken} minutes. A confirmation text will be sent. Thank you!")
        response.hangup()

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
                "I didn’t catch that. Say yes or press 1 if correct, or no or press 2 to modify.")
    return Response(str(response), mimetype='text/xml')


@order_bp.route('/new_modify_order', methods=['POST'])
def new_modify_order():
    user_resp = request.form.get('SpeechResult', '').strip()
    log_info(f"User requested order modification: {user_resp}")
    current_order_items = json.loads(session.get('order_items_json', '[]'))
    
    # Use AI to interpret order modifications
    modifications = get_order_modifications(user_resp, current_order_items)
    if not modifications or ("additions" not in modifications and "removals" not in modifications):
        response = VoiceResponse()
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
    updated_order = apply_modifications(current_order_items, modifications)
    session['order_items_json'] = json.dumps(updated_order)
    calculate_bill_amount(updated_order)
    session['bill_amount'] = int(session['total_price'] * 100)
    order_description = build_order_description(updated_order)
    log_info(f"Order updated after modification: {updated_order}")
    response = VoiceResponse()
    confirmation_message = (
        f"Your order is now:\n{order_description}\nTotal: ${session['total_price']:.2f}. "
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


def get_order_modifications(user_input, current_order_items):
    """Use AI to interpret order modifications from user speech"""
    modification_prompt = (
        "You are an assistant that modifies restaurant orders. The current order is:\n" +
        json.dumps(current_order_items, indent=2) +
        "\nThe customer says: \"" + user_input + "\".\n"
        "Output a JSON object with two keys: 'additions' and 'removals'. Each is a list of items with 'name', 'quantity', and optionally 'modifier' (with each modifier having 'name' and 'quantity')."
    )
    try:
        import openai
        from app.config import OPENAI_API_KEY
        openai.api_key = OPENAI_API_KEY
        messages = [{"role": "system", "content": modification_prompt}]
        response_ai = openai.chat.completions.create(
            model="gpt-4o-2024-11-20",
            messages=messages,
            max_tokens=300,
            temperature=0.0,
            timeout=15
        )
        reply = response_ai.choices[0].message.content.strip()
        modifications = json.loads(reply)
        log_info(f"Received modifications from AI: {modifications}")
        return modifications
    except Exception as e:
        log_info(f"Modification AI error: {e}")
        return {}

def apply_modifications(current_order, modifications):
    """Apply the modifications to the current order"""
    order_dict = {item["name"].lower(): item for item in current_order}
    
    # Process removals
    for removal in modifications.get("removals", []):
        rem_name = removal.get("name", "").lower()
        rem_qty = removal.get("quantity", 1)
        if rem_name in order_dict:
            order_dict[rem_name]["quantity"] -= rem_qty
            if order_dict[rem_name]["quantity"] <= 0:
                del order_dict[rem_name]
    
    # Process additions
    for addition in modifications.get("additions", []):
        add_name = addition.get("name", "")
        add_qty = addition.get("quantity", 1)
        add_mods = addition.get("modifier", [])
        key = add_name.lower()
        
        # Find the menu item
        matched_item, _ = find_menu_item(add_name)
        if not matched_item:
            log_info(f"Warning: Menu item '{add_name}' not found")
            continue
            
        base_price = matched_item.get("price", 0.0) if matched_item else 0.0
        updated_mods = [{"name": mod.get("name", "").lower(), "quantity": mod.get(
            "quantity", 1), "price": 0.0} for mod in add_mods]
            
        # Update existing item or add new one
        if key in order_dict:
            order_dict[key]["quantity"] += add_qty
            order_dict[key]["modifier"] = updated_mods
            order_dict[key]["price"] = base_price
        else:
            new_item = {
                "name": add_name,
                "reference_handler": matched_item.get("reference_handler", "") if matched_item else "",
                "quantity": add_qty,
                "price": base_price,
                "modifier": updated_mods
            }
            order_dict[key] = new_item
            
    return list(order_dict.values())


@order_bp.route('/confirm_order_after_modification', methods=['POST'])
def confirm_order_after_modification():
    user_resp = (request.form.get('SpeechResult', '') or "").strip().lower()
    dtmf_input = request.form.get('Digits', '')
    log_info(
        f"Final confirmation after modification: Speech='{user_resp}', DTMF='{dtmf_input}'")
    interpreted = None
    if dtmf_input:
        result = dtmf_yes_no(dtmf_input)
        interpreted = result if result else None
    else:
        if user_said_yes(user_resp):
            interpreted = "yes"
        elif user_said_no(user_resp):
            interpreted = "no"
    order_items = json.loads(session.get('order_items_json', '[]'))
    order_id = session.get('order_id', '') or str(uuid.uuid4())
    session['order_id'] = order_id
    sender = session.get('sender', '')
    caller_name = session.get('caller_name', 'Valued Customer')
    response = VoiceResponse()
    log_info(f"User final decision: {interpreted}")
    if interpreted == "yes":
        newly_snoozed = [it["name"]
                         for it in order_items if is_item_snoozed_timebased(it)]
        if newly_snoozed:
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
                      ", ".join(newly_snoozed) + ". Press 1 to remove them, 2 to cancel.")
            return Response(str(response), mimetype='text/xml')
        if not can_process_action(sender, 'order_food', 60):
            response.say(
                "You're placing orders too quickly. Please wait and try again.")
            return Response(str(response), mimetype='text/xml')
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
        from tasks import send_confirmation_sms_task
        send_confirmation_sms_task.delay(order_id, session.get(
            'order_message', ''), sender, caller_name, session.get('bill_amount', 0), order_items)
        time_taken = 20 + (1 * len(order_items))
        response.say(
            f"Great! Your order is confirmed and will be ready in about {time_taken} minutes. A confirmation text is on the way. Thank you for choosing Red Bar Sushi! Goodbye.")
        response.hangup()
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


@order_bp.route('/order_status', methods=['POST'])
def order_status():
    """Handle order status updates from Deliverect"""
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
        
    # Find the order in the database
    try:
        order_record = db.session.query(Order).filter_by(id=order_id).first()
        if not order_record:
            return jsonify({"error": "Order not found"}), 404
            
        # Update order status in database
        order_record.status = status
        if not commit_with_retry(db.session):
            return jsonify({"error": "Database error"}), 500
            
        # Send status update to customer
        status_message = f"Your order ({order_id}) status is now: {status}"
        from tasks import send_order_status_update_task
        send_order_status_update_task.delay(order_id, status_message)
        
        return jsonify({"success": True}), 200
    except Exception as e:
        log_info(f"Error processing order status update: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@order_bp.route('/register', methods=['POST'])
def register_channel_route():
    """Register or update channel status with Deliverect"""
    data = request.get_json() or {}
    status = data.get("status")
    
    if not status:
        return jsonify({"error": "Missing status parameter"}), 400
        
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
    base_url = BASE_URL or "https://yourdomain.com"
    
    response_body = {
        "statusUpdateURL": f"{base_url}/order_status",
        "menuUpdateURL": f"{base_url}/menu_update",
        "snoozeUnsnoozeURL": f"{base_url}/snoozeUnsnooze",
        "busyModeURL": f"{base_url}/busy_mode",
        "updatePrepTimeURL": f"{base_url}/updatePrepTime",
        "courierUpdateURL": f"{base_url}/courierUpdate"
    }
    return jsonify(response_body), 200

@order_bp.route('/handle_newly_snoozed_in_checkout', methods=['POST'])
def handle_newly_snoozed_in_checkout():
    """Handle the case where items become unavailable during checkout"""
    user_resp = request.form.get('SpeechResult', '')
    dtmf_input = request.form.get('Digits', '')
    
    response = VoiceResponse()
    
    # Check if user wants to remove unavailable items (1) or cancel (2)
    if dtmf_input == '1' or user_said_yes(user_resp):
        # Remove snoozed items from order
        order_items = json.loads(session.get('order_items_json', '[]'))
        updated_items = [item for item in order_items if not is_item_snoozed_timebased(item)]
        
        if not updated_items:
            response.say("All items in your order are now unavailable. We apologize for the inconvenience. Goodbye.")
            response.hangup()
            return Response(str(response), mimetype='text/xml')
            
        # Update the order
        session['order_items_json'] = json.dumps(updated_items)
        calculate_bill_amount(updated_items)
        session['bill_amount'] = int(session['total_price'] * 100)
        order_description = build_order_description(updated_items)
        session['order_message'] = f"{order_description}\nYour total is ${session['total_price']:.2f}."
        
        # Confirm the updated order
        with response.gather(
            input='speech dtmf',
            action='/confirm_order_after_modification',
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto",
            num_digits=1
        ) as g:
            g.say(f"Your updated order is: {session['order_message']} If correct, say yes or press 1. If you need changes, say no or press 2.")
    else:
        # Cancel the order
        response.say("We're sorry about that. Your order has been cancelled. Goodbye.")
        response.hangup()
        
    return Response(str(response), mimetype='text/xml')
