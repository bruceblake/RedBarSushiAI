# app/routes/voice.py
from flask import Blueprint, request, session, Response, jsonify
from twilio.twiml.voice_response import VoiceResponse
import logging

# Try to import from the original module first 
try:
    from app.utils.agent_utils import analyze_user_input, get_order_modifications, OrderParsingAgent
    logger = logging.getLogger(__name__)
    logger.info("Successfully imported OpenAI agent utilities")
except ImportError:
    # If that fails, use our simplified implementation
    from app.utils.agent_utils_simple import analyze_user_input, get_order_modifications, OrderParsingAgent
    logger = logging.getLogger(__name__)
    logger.warning("Using simplified agent utilities (OpenAI not available)")

voice_bp = Blueprint('voice', __name__)
logger = logging.getLogger(__name__)

# Import channel_status from order.py
from app.routes.order import channel_status


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
        if "1" in user_resp or "order" in user_resp:
            choice = 'order'
        elif "2" in user_resp or "menu" in user_resp or "question" in user_resp:
            choice = 'ask_menu'
        elif "3" in user_resp or "person" in user_resp or "human" in user_resp:
            choice = 'real_person'
    
    response = VoiceResponse()
    
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
                "I didn't understand. Press 1 to order, 2 for menu questions, 3 for a real person.")
    return Response(str(response), mimetype='text/xml')


@voice_bp.route('/handle_menu_questions', methods=['POST'])
def handle_menu_questions():
    """Handle menu-related questions from the caller."""
    user_input = request.form.get('SpeechResult', '').lower()
    
    # Use the new agent-based analysis
    analysis = analyze_user_input(user_input)
    intent = analysis.get('intent', 'other')
    
    response = VoiceResponse()
    
    if intent == 'order_food':
        # User decided to order instead of asking questions
        session['ordering_in_progress'] = True
        with response.gather(
            input='speech',
            action='/take_order',
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto"
        ) as g:
            g.say("I'll take your order now. Please tell me what you would like to order.")
    elif intent == 'ask_menu':
        # Generic menu information
        with response.gather(
            input='speech',
            action='/handle_menu_questions',
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto"
        ) as g:
            g.say("Our menu features a variety of sushi rolls, nigiri, sashimi, and traditional Japanese dishes. " +
                  "We have special rolls like California Roll, Spicy Tuna Roll, Dragon Roll, and more. " +
                  "Would you like to know about specific items or would you like to place an order now?")
    elif intent == 'get_menu_item_price' or intent == 'describe_menu_item':
        # Look up the specific item using agent
        agent = OrderParsingAgent()
        item_name = ""
        if 'menu_items' in analysis and analysis['menu_items']:
            item_name = analysis['menu_items'][0]['name']
        
        # Get item details from menu
        result = agent.menu_tool.get_details(item_name)
        
        if result.get("found"):
            item = result.get("item", {})
            description = f"The {item.get('name')} costs ${item.get('price', 0):.2f}."
            if intent == 'describe_menu_item':
                description += f" {item.get('description', 'It is one of our popular items.')}"
        else:
            description = "I'm sorry, I couldn't find that item on our menu."
            
        with response.gather(
            input='speech',
            action='/handle_menu_questions',
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto"
        ) as g:
            g.say(description + " Is there anything else you'd like to know about our menu?")
    else:
        # Default response for other intents
        with response.gather(
            input='speech dtmf',
            action='/main_menu',
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto",
            num_digits=1
        ) as g:
            g.say("I'm not sure I understood your question. " +
                  "Press 1 to order, 2 to ask another menu question, or 3 to speak to a person.")
    
    return Response(str(response), mimetype='text/xml')


@voice_bp.route('/api/analyze', methods=['POST'])
def analyze():
    """
    API endpoint to analyze user input using our AI agent.
    """
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({"error": "Missing 'text' field in request"}), 400
            
        text = data['text']
        agent = OrderParsingAgent()
        order = agent.parse_order(text)
        
        return jsonify(order), 200
    except Exception as e:
        logger.error(f"Error in analyze API: {e}")
        return jsonify({"error": str(e)}), 500


@voice_bp.route('/api/modify', methods=['POST'])
def modify():
    """
    API endpoint to modify an existing order based on user input.
    """
    try:
        data = request.get_json()
        if not data or 'text' not in data or 'current_order' not in data:
            return jsonify({"error": "Missing required fields in request"}), 400
            
        text = data['text']
        current_order = data['current_order']
        
        modifications = get_order_modifications(text, current_order['items'])
        
        return jsonify(modifications), 200
    except Exception as e:
        logger.error(f"Error in modify API: {e}")
        return jsonify({"error": str(e)}), 500
        

@voice_bp.route('/healthcheck', methods=['GET'])
def healthcheck():
    """
    Simple health check endpoint for the voice service.
    """
    return jsonify({"status": "ok", "service": "voice"}), 200