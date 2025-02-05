# app/routes/voice.py
from flask import Blueprint, request, session, Response
from twilio.twiml.voice_response import VoiceResponse
import logging

voice_bp = Blueprint('voice', __name__)
logger = logging.getLogger(__name__)


@voice_bp.route('/', methods=['GET', 'POST'])
def receive_call():
    call_sid = request.values.get('CallSid', 'unknown')
    sender = request.values.get('From', '')
    session['sender'] = sender
    session['order_message'] = ""
    session['bill_amount'] = 0
    session['total_price'] = 0
    session['modification_in_progress'] = False
    session['caller_name'] = "Valued Customer"
    session['ordering_in_progress'] = False
    session['initial_choice_made'] = False

    response = VoiceResponse()
    gather = response.gather(
        input='speech',
        action='/take_name',
        enhanced=True,
        speech_model="phone_call",
        language="en-US",
        speech_timeout="auto"
    )
    gather.say(
        "Hello! Thank you for calling Red Bar Sushi. May I have your name, please?")
    return Response(str(response), mimetype='text/xml')


@voice_bp.route('/take_name', methods=['POST'])
def take_name():
    caller_name = request.form.get('SpeechResult', '').strip()
    if caller_name:
        session['caller_name'] = caller_name
        menu_prompt = f"Thanks, {session['caller_name']}! Press or say 1 to order, 2 for menu questions, 3 for a real person."
    else:
        menu_prompt = "I didn't catch your name. Please say it clearly."
    response = VoiceResponse()
    with response.gather(
        input='speech dtmf',
        action='/main_menu',
        enhanced=True,
        speech_model="phone_call",
        language="en-US",
        speech_timeout="auto",
        num_digits=1
    ) as g:
        g.say(menu_prompt)
    return Response(str(response), mimetype='text/xml')


@voice_bp.route('/main_menu', methods=['POST'])
def main_menu():
    user_resp = (request.form.get('SpeechResult', '') or "").lower()
    dtmf_input = request.form.get('Digits', '')
    choice = None
    if dtmf_input == '1':
        choice = 'order'
    elif dtmf_input == '2':
        choice = 'ask_menu'
    elif dtmf_input == '3':
        choice = 'real_person'
    else:
        if "1" in user_resp:
            choice = 'order'
        elif "2" in user_resp:
            choice = 'ask_menu'
        elif "3" in user_resp:
            choice = 'real_person'
    response = VoiceResponse()
    # For simplicity, assume channel_status is active (1)
    channel_status = 1
    if choice == 'order' and channel_status == 1:
        session['ordering_in_progress'] = True
        with response.gather(
            input='speech',
            action='/take_order',
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto"
        ) as g:
            g.say("Please tell me what you would like to order.")
    elif choice == 'ask_menu':
        with response.gather(
            input='speech',
            action='/handle_menu_questions',
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto"
        ) as g:
            g.say(
                "You can ask for the menu, prices, descriptions, or say what you'd like to order.")
    elif choice == 'real_person':
        response.say("Please hold, transferring to a real person.")
        response.hangup()
    else:
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
                "I didn’t understand. Press 1 to order, 2 for menu questions, 3 for a real person.")
    return Response(str(response), mimetype='text/xml')
