# app/routes/voice.py
from flask import Blueprint, request, session, Response
from twilio.twiml.voice_response import VoiceResponse
import logging

voice_bp = Blueprint('voice', __name__)
logger = logging.getLogger(__name__)


@voice_bp.route('/', methods=['GET', 'POST'])
def receive_call():
    # Set initial session variables
    session['sender'] = request.values.get('From', '')
    session['order_message'] = ""
    session['total_price'] = 0
    session['modification_in_progress'] = False
    session['caller_name'] = "Valued Customer"
    session['ordering_in_progress'] = False

    response = VoiceResponse()
    with response.gather(
        input='speech',
        action='/take_name',
        enhanced=True,
        speech_model="phone_call",
        language="en-US",
        speech_timeout="auto"
    ) as g:
        g.say("Hello! Thank you for calling Red Bar Sushi. May I have your name, please?")
    return Response(str(response), mimetype="text/xml")


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
    return Response(str(response), mimetype="text/xml")

