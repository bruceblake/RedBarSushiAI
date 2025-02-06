# app/routes/order.py

from app.models import Order
from app import db
from app.utils.helpers import log_info, commit_with_retry
from app.utils.menu_utils import load_menu_data, is_item_snoozed_timebased
from app.utils.order_utils import (
    analyog_info(f"Received modificationsze_user_input,
                 user_said_yes,
                 user_said_no,
                 dtmf_yes_no, from AI: {modifications}")
    except Exception as e:
        log_info(f"Modification AI error:
                 build_order_description, {e}")
        modifications={}

    if not modifications or ("additions" not in modifications and "removals" not in modifications):
        response=VoiceResponse()
        with response.gather(
            input='speech',
            action='/new_modify_order',
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto"
    ) as g:  order_dict[key]["quantity"] +=
    g.say("I didn't understand your modifications. Please say clearly what you would like to add or remove from your order.")
        return Response(str(response), mimetype='text/xml')

    updated_order=apply_modifications(current_order_items, modifications)
    session['order_items_json']=json.dumps(updated_order)
    calculate_bill_amount(updated_order)
    session['bill_amount']=int(session['total_price'] * 100)
    order_description=build_order_description(updated_order)
    log_info(f"Order updated after modification add_qty
             order_dict[key]["modifier"]=updated_mods
             order_dict[key]["price"]=base_price
             else:
             new_item={
                 "name": add_name,
                 "reference_handler": matched_item.get("reference_handler", "") if matched_item else "",
                 "quantity": add_qty,
                 "price": base_price,
                 "modifier": updated_mods
             }
             order_dict[key]=new_item
             return list(order_dict.values())

             @ order_bp.route('/confirm_order_after_modification', methods=['POST'])
             def confirm_order_after_modification():
             user_resp=(request.form.get('SpeechResult', '')
                        or "").strip().lower()
             dtmf_input=request.form.get('Digits', '')
             log_info(
                 f"Final confirmation after modification: Speech='{user_resp}', DTMF='{dtmf_input}'")
             interpreted=None
             if dtmf_input:
             yes_n raise Exception("Failed to commit after several retries")
             log_info(f"Order {order_id} saved successfully.")
             except Exception as e:
             db.session.rollback()
             response.say(
                 "Sorry, we encountered a database issue. Please try again.")
             return Response(str(response), mimetype='text/xml')
             from tasks import send_confirmation_sms_task
             send_confirmation_sms_task.delay(order_id, session.get(
                 'order_message', ''), sender, caller_name, session.get('bill_amount', 0), order_items)
             time_taken=20 + (1 * len(order_items))
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

             @ order_bp.route('/order_status', methods=['POST'])
             def order_status():
             data=request.get_json() or {}
             status=data.get("status")
             order_id=data.get("channelOrderId")
             code=data.get("code")
             if status == "FAILED" or code == 120:
             log_info(
                 f"Order {order_id} failed with code=120 or status=FAILED.")
             order_record=db.session.query(
                 Order).filter_by(id=order_id).first()
             if not order_record:
             import json
             import uuid
             import time
             import datetime
             import threading
             import logging
             from collections import defaultdict
             from flask import Blueprint, request, session, Response, jsonify
             from twilis[0].message.content.strip()
             modifications=json.loads(reply)
             lo.twiml.voice_response import VoiceResponse

             # Import helper functions from order_utils (complete versions)
             return jsonify({"error": "Order not found"}), 404
             status_message=f"Your order ({order_id}) status is now: {status}"
             from tasks import send_order_status_update_task
             send_order_status_update_task.delay(order_id, status_message)
             return jsonify({"success": True}), 200

             @ order_bp.route('/register', methods=['POST'])
             def register_channel_route():
             data=request.get_json() or {}
             status=data.get("status")
             global channel_status
             if status == "register":
             channel_status=0
             elif status == "active":
             channel_status=1
             elif status == "inactive":
             channel_status=2
             response_body={
                 "statusUpdateURL": "https://pegasus.pythonanywhere.com/order_status",
                 "menuUpdateURL": "https://pegasus.pythonanywhere.com/menu_update",
                 "snoozeUnsnoozeURL": "https://pegasus.pythonanywhere.com/snoozeUnsnooze",
                 "busyModeURL": "https://pegasus.pythonanywhere.com/busy_mode",
                 "updatePrepTimeURL": "https://pegasus.pythonanywhere.com/updatePrepTime",
                 "courierUpdateURL": "https://pegasus.pythonanywhere.com/courierUpdate"
             }
             return jsonify(response_body), 200o=dtmf_yes_no(dtmf_input)
             if yes_no == "yes":
             interpreted="yes"
             elif yes_no == "no":
             interpreted="no"
             else:
             if user_said_yes(user_resp):
             interpreted="yes"
             elif user_said_no(user_resp):
             interpreted="no"
             order_items=json.loads(session.get('order_items_json', '[]'))
             order_id=session.get('order_id', '') or str(uuid.uuid4())
             session['order_id']=order_id
             sender=session.get('sender', '')
             caller_name=session.get('caller_name', 'Valued Customer')
             response=VoiceResponse()
             log_info(f"User final decision: {interpreted}")
             if interpreted == "yes":
             newly_snoozed=[it["name"]
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
             text_msg=session.get('order_message', '')
             new_order=Order(
                 id=order_id,
                 sender=sender,
                 caller_name=caller_name,
                 message=text_msg
             )
             db.session.add(new_order)
             if not commit_with_retry(db.session):: {updated_order}")
    response=VoiceResponse()
    confirmation_message=(
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

    def apply_modifications(current_order, modifications):
    order_dict={}
    for item in current_order:
        key=item["name"].lower()
        order_dict[key]=item
    for removal in modifications.get("removals", []):
        rem_name=removal.get("name", "").lower()
        rem_qty=removal.get("quantity", 1)
        if rem_name in order_dict:
            order_dict[rem_name]["quantity"] -= rem_qty
            if order_dict[rem_name]["quantity"] <= 0:
                del order_dict[rem_name]
    for addition in modifications.get("additions", []):
        add_name=addition.get("name", "")
        add_qty=addition.get("quantity", 1)
        add_mods=addition.get("modifier", [])
        key=add_name.lower()
        matched_item, _=find_menu_item(add_name)
        base_price=matched_item.get("price", 0.0) if matched_item else 0.0
        updated_mods=[]
        for mod in add_mods:
            mod_name=mod.get("name", "").lower()
            mod_qty=mod.get("quantity", 1)
            updated_mods.append({
                "name": mod_name,
                "quantity": mod_qty,
                "price": 0.0  # Replace with actual price lookup if available
            })
        if key in order_dict:

    calculate_bill_amount,
    find_menu_item,
    find_menu_item_any_status
)

# Import models and DB instance from our application package

order_bp = Blueprint('order', __name__)
logger = logging.getLogger(__name__)

# Global variables (you might want to persist these elsewhere in production)
channel_status = 1  # 0: registered, 1: active, 2: inactive
BUSY_MODE_ACTIVE = False
recent_actions = defaultdict(
    lambda: {'timestamp': 0, 'lock': threading.Lock()})


def can_process_action(sender, action_key, cooldown=30):
    current_time = time.time()
    with recent_actions[sender]['lock']:
        last_time = recent_actions[sender].get(action_key, 0)
        if current_time - last_time > cooldown:
            recent_actions[sender][action_key] = current_time
            return True
        else:
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

    # Get the user input from Twilio's SpeechResult
    user_resp = request.form.get('SpeechResult', '').strip()
    # Analyze the user input using the full analyze_user_input function
    analysis = analyze_user_input(user_resp)
    intent = analysis.get('intent', 'other')

    if intent != 'order_food' or not analysis.get('menu_items'):
        log_info(
            f"order_food: {intent}, menu_items: {analysis.get('menu_items')}")
        reply = "I’m sorry, I couldn’t understand that request."
        with response.gather(
            input='speech',
            action='/take_order',
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto",
            timeout=3
        ) as g:
            g.say(reply)
        return Response(str(response), mimetype='text/xml')

    order_items = []
    for item_entity in analysis['menu_items']:
        item_name = item_entity.get("name", "")
        matched_item, dist = find_menu_item_any_status(item_name)
        if not matched_item:
            reply = f"Sorry, we don’t have {item_name} on our menu."
            response.say(reply)
            response.hangup()
            return Response(str(response), mimetype='text/xml')
        if not matched_item.get("available", False):
            reply = f"Sorry, {matched_item['name']} is not available right now. Goodbye!"
            response.say(reply)
            response.hangup()
            return Response(str(response), mimetype='text/xml')
        quantity = item_entity.get("quantity", 1)
        order_items.append({
            "name": item_name,
            "reference_handler": matched_item.get("reference_handler", ""),
            "modifier": [],  # For simplicity, we assume no modifiers unless provided
            "quantity": quantity,
            "price": matched_item.get("price", 0.0)
        })

    calculate_bill_amount(order_items)
    order_description = build_order_description(order_items)
    # Generate a unique order ID if not already in session
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


@order_bp.route('/confirm_fuzzy_items', methods=['POST'])
def confirm_fuzzy_items():
    user_resp = (request.form.get('SpeechResult', '') or "").lower()
    dtmf_input = request.form.get('Digits', '')
    interpreted = None
    if dtmf_input == '1':
        interpreted = "yes"
    elif dtmf_input == '2':
        interpreted = "no"
    else:
        if user_said_yes(user_resp):
            interpreted = "yes"
        elif user_said_no(user_resp):
            interpreted = "no"
    response = VoiceResponse()
    order_items = json.loads(session.get('order_items_json', '[]'))
    if interpreted == "yes":
        with response.gather(
            input='speech dtmf',
            action='/confirm_order_from_initial',
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto",
            num_digits=1
        ) as g:
            g.say(session.get('order_message', ''))
        return Response(str(response), mimetype='text/xml')
    elif interpreted == "no":
        with response.gather(
            input='speech',
            action='/take_order',
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto"
        ) as g:
            g.say("Okay, let's try again. Please tell me your order.")
        return Response(str(response), mimetype='text/xml')
    else:
        with response.gather(
            input='speech dtmf',
            action='/confirm_fuzzy_items',
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto",
            num_digits=1
        ) as g:
            g.say("I didn’t understand. Say yes or press 1, or no or press 2.")
        return Response(str(response), mimetype='text/xml')


@order_bp.route('/confirm_order_from_initial', methods=['POST'])
def confirm_order_from_initial():
    user_resp = (request.form.get('SpeechResult', '') or "").lower()
    dtmf_input = request.form.get('Digits', '')
    log_info(f"Order confirmation: Speech='{user_resp}', DTMF='{dtmf_input}'")
    interpreted = None
    if dtmf_input:
        yes_no = dtmf_yes_no(dtmf_input)
        if yes_no == "yes":
            interpreted = "yes"
        elif yes_no == "no":
            interpreted = "no"
    else:
        if user_said_yes(user_resp):
            interpreted = "yes"
        elif user_said_no(user_resp):
            interpreted = "no"
    order_items = json.loads(session.get('order_items_json', '[]'))
    # Use an existing order ID or generate a new one
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
            new_order = Order(
                id=order_id,
                sender=sender,
                caller_name=caller_name,
                message=text_msg
            )
            db.session.add(new_order)
            if not commit_with_retry(db.session):
                raise Exception("Failed to commit after several retries")
            log_info(f"Order {order_id} inserted successfully.")
        except Exception as e:
            db.session.rollback()
            response.say(
                "Sorry, we encountered a database issue. Please try again.")
            return Response(str(response), mimetype='text/xml')
        # Enqueue the confirmation SMS task
        from tasks import send_confirmation_sms_task
        send_confirmation_sms_task.delay(order_id, session.get(
            'order_message', ''), sender, caller_name, session.get('bill_amount', 0), order_items)
        time_taken = 20 + (1 * len(order_items))
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
            g.say("I didn’t catch that. Yes or 1 if correct, or no or 2 to modify.")
    return Response(str(response), mimetype='text/xml')


@order_bp.route('/handle_newly_snoozed_in_checkout', methods=['POST'])
def handle_newly_snoozed_in_checkout():
    user_resp = (request.form.get('SpeechResult', '') or "").lower()
    dtmf_input = request.form.get('Digits', '')
    interpreted = None
    if dtmf_input == '1':
        interpreted = "remove"
    elif dtmf_input == '2':
        interpreted = "cancel"
    else:
        if user_said_yes(user_resp):
            interpreted = "remove"
        elif user_said_no(user_resp):
            interpreted = "cancel"
    response = VoiceResponse()
    order_items = json.loads(session.get('order_items_json', '[]'))
    if interpreted == "remove":
        filtered_items = [
            it for it in order_items if not is_item_snoozed_timebased(it)]
        removed_names = [it["name"]
                         for it in order_items if is_item_snoozed_timebased(it)]
        session['order_items_json'] = json.dumps(filtered_items)
        calculate_bill_amount(filtered_items)
        new_desc = build_order_description(filtered_items)
        if not filtered_items:
            with response.gather(
                input='speech dtmf',
                action='/main_menu',
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout="auto",
                num_digits=1
            ) as g:
                g.say(
                    "All items removed. Press 1 to order again, 2 for menu, 3 for a real person.")
            return Response(str(response), mimetype='text/xml')
        else:
            removal_msg = f"We removed {', '.join(removed_names)}. Now your order is: {new_desc} Total: ${session['total_price']:.2f}. If correct, say yes or press 1; else no or press 2."
            with response.gather(
                input='speech dtmf',
                action='/confirm_order_from_initial',
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout="auto",
                num_digits=1
            ) as g:
                g.say(removal_msg)
            return Response(str(response), mimetype='text/xml')
    elif interpreted == "cancel":
        response.say("Okay, canceling your order. Goodbye!")
        response.hangup()
        return Response(str(response), mimetype='text/xml')
    else:
        with response.gather(
            input='speech dtmf',
            action='/handle_newly_snoozed_in_checkout',
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto",
            num_digits=1
        ) as g:
            g.say("I didn’t understand. Press 1 to remove them, 2 to cancel.")
        return Response(str(response), mimetype='text/xml')


@order_bp.route('/new_modify_order', methods=['POST'])
def new_modify_order():
    user_resp = request.form.get('SpeechResult', '').strip()
    log_info(f"User requested order modification: {user_resp}")
    current_order_items = json.loads(session.get('order_items_json', '[]'))
    modification_prompt = (
        "You are an assistant that modifies restaurant orders. "
        "The current order is:\n" + json.dumps(current_order_items, indent=2) +
        "\nThe customer says: \"" + user_resp + "\".\n"
        "Please output a JSON object with two fields: 'additions' and 'removals'. Each should be a list of items. "
        "For each item include 'name', 'quantity', and if applicable, a list 'modifier' (with each modifier having 'name' and 'quantity').\n"
        "Example:\n"
        '{\n'
        '  "additions": [\n'
        '     {"name": "Chicken Sate", "quantity": 1, "modifier": [{"name": "White Rice", "quantity": 1, "price": 2}], "price": 2}\n'
        '  ],\n'
        '  "removals": [\n'
        '     {"name": "Takoyaki", "quantity": 1}\n'
        '  ]\n'
        '}\n'
        "Only output valid JSON."
    )
    # Use OpenAI to generate modifications (full version)
    try:
        import openai
        from app.config import OPENAI_API_KEY
        openai.api_key = OPENAI_API_KEY
        messages = [{"role": "system", "content": modification_prompt}]
        response_ai = openai.chat.completions.create(
            model="gpt-4",
            messages=messages,
            max_tokens=300,
            temperature=0.0
        )
        reply = response_ai.choices[0].message.content.strip()
        modifications = json.loads(reply)
        log_info(f"Received modifications from AI: {modifications}")
    except Exception as e:
        log_info(f"Modification AI error: {e}")
        modifications = {}

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
            g.say("I didn't understand your modifications. Please say clearly what you would like to add or remove from your order.")
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


def apply_modifications(current_order, modifications):
    order_dict = {}
    for item in current_order:
        key = item["name"].lower()
        order_dict[key] = item
    for removal in modifications.get("removals", []):
        rem_name = removal.get("name", "").lower()
        rem_qty = removal.get("quantity", 1)
        if rem_name in order_dict:
            order_dict[rem_name]["quantity"] -= rem_qty
            if order_dict[rem_name]["quantity"] <= 0:
                del order_dict[rem_name]
    for addition in modifications.get("additions", []):
        add_name = addition.get("name", "")
        add_qty = addition.get("quantity", 1)
        add_mods = addition.get("modifier", [])
        key = add_name.lower()
        matched_item, _ = find_menu_item(add_name)
        base_price = matched_item.get("price", 0.0) if matched_item else 0.0
        updated_mods = []
        for mod in add_mods:
            mod_name = mod.get("name", "").lower()
            mod_qty = mod.get("quantity", 1)
            updated_mods.append({
                "name": mod_name,
                "quantity": mod_qty,
                "price": 0.0  # Replace with actual price lookup if available
            })
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
        yes_no = dtmf_yes_no(dtmf_input)
        if yes_no == "yes":
            interpreted = "yes"
        elif yes_no == "no":
            interpreted = "no"
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
            new_order = Order(
                id=order_id,
                sender=sender,
                caller_name=caller_name,
                message=text_msg
            )
            db.session.add(new_order)
            if not commit_with_retry(db.session):
                raise Exception("Failed to commit after several retries")
            log_info(f"Order {order_id} saved successfully.")
        except Exception as e:
            db.session.rollback()
            response.say(
                "Sorry, we encountered a database issue. Please try again.")
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
    data = request.get_json() or {}
    status = data.get("status")
    order_id = data.get("channelOrderId")
    code = data.get("code")
    if status == "FAILED" or code == 120:
        log_info(f"Order {order_id} failed with code=120 or status=FAILED.")
    order_record = db.session.query(Order).filter_by(id=order_id).first()
    if not order_record:
        return jsonify({"error": "Order not found"}), 404
    status_message = f"Your order ({order_id}) status is now: {status}"
    from tasks import send_order_status_update_task
    send_order_status_update_task.delay(order_id, status_message)
    return jsonify({"success": True}), 200


@order_bp.route('/register', methods=['POST'])
def register_channel_route():
    data = request.get_json() or {}
    status = data.get("status")
    global channel_status
    if status == "register":
        channel_status = 0
    elif status == "active":
        channel_status = 1
    elif status == "inactive":
        channel_status = 2
    response_body = {
        "statusUpdateURL": "https://pegasus.pythonanywhere.com/order_status",
        "menuUpdateURL": "https://pegasus.pythonanywhere.com/menu_update",
        "snoozeUnsnoozeURL": "https://pegasus.pythonanywhere.com/snoozeUnsnooze",
        "busyModeURL": "https://pegasus.pythonanywhere.com/busy_mode",
        "updatePrepTimeURL": "https://pegasus.pythonanywhere.com/updatePrepTime",
        "courierUpdateURL": "https://pegasus.pythonanywhere.com/courierUpdate"
    }
    return jsonify(response_body), 200
