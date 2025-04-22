"""
Voice menu module. This module contains the routes for handling menu-related questions and interactions.
"""

import logging
import json
from flask import request, session, Response
from twilio.twiml.voice_response import VoiceResponse

# Import blueprint
from . import voice_bp

# Import helpers
from .voice_core import setup_gather_params, handle_silence

# Import agent utilities
from app.utils.agent_utils import OrderParsingAgent
from app.utils.menu_utils import load_menu_data, get_popular_menu_items

# Import menu handling utilities
from app.utils.menu_cache import get_cached_response

# Try to import optimized menu handler
try:
    from app.utils.opt_menu_handler import handle_menu_query
    OPTIMIZED_MENU_HANDLER = True
    logger.info("Using optimized menu handler with caching")
except ImportError:
    OPTIMIZED_MENU_HANDLER = False
    logger.warning("Optimized menu handler not available, using standard handler")

# Set up logger
logger = logging.getLogger(__name__)

@voice_bp.route("/handle_menu_questions", methods=["POST"])
def handle_menu_questions():
    """
    Process questions about the menu and provide information.
    
    This route:
    1. Processes natural language questions about the menu
    2. Uses AI to generate relevant responses about menu items
    3. Provides options for additional menu questions
    4. Offers a path to ordering or returning to the main menu
    """
    # Initialize TwiML response
    response = VoiceResponse()
    
    # Check if customer asked a question or if we need to prompt
    asked = request.args.get("asked", "true").lower() == "true"
    
    if not asked:
        # No question asked yet, prompt for one
        prompt = (
            "You can ask me about our menu items, prices, recommendations, or specials. "
            "What would you like to know about our menu?"
        )
        
        # Menu question hints
        hints = (
            "what's on the menu, popular items, recommendations, "
            "vegetarian options, gluten free, spicy rolls, "
            "price, how much is, do you have, special rolls"
        )
        
        # Set up gather for menu questions
        with response.gather(
            action="/handle_menu_questions?asked=true",
            input="dtmf speech",
            speech_model="phone_call",
            enhanced=True,
            speech_timeout=3,
            timeout=8,
            hints=hints,
        ) as g:
            g.say(prompt)
        
        # Fallback for no input - list popular items
        response.say("Let me tell you about some of our popular items.")
        
        # Get popular menu items
        popular_items = get_popular_menu_items(5)  # Get top 5 items
        
        if popular_items:
            response.say("Some of our most popular items include:")
            
            # List popular items with prices
            for item in popular_items:
                name = item.get("name", "")
                price = item.get("price", 0)
                price_text = f"${price:.2f}" if price else ""
                
                if name and price_text:
                    response.say(f"{name} for {price_text}.")
        
        # Offer to continue or return to main menu
        with response.gather(
            action="/handle_menu_follow_up",
            input="dtmf speech",
            speech_model="phone_call",
            enhanced=True,
            speech_timeout=2,
            timeout=5,
            hints="yes, no, main menu, order",
        ) as g:
            g.say("Would you like to ask another question about our menu?")
    else:
        # Process the customer's menu question
        spoken_query = request.form.get("SpeechResult", "")
        digits = request.form.get("Digits", "")
        
        # Log the query
        logger.info(f"Menu question - Speech: '{spoken_query}', DTMF: '{digits}'")
        
        # Handle digits as shortcut for common queries
        if digits:
            if digits == "1":  # Popular items
                spoken_query = "What are your most popular items?"
            elif digits == "2":  # Vegetarian options
                spoken_query = "What vegetarian options do you have?"
            elif digits == "3":  # Special rolls
                spoken_query = "What are your special rolls?"
            elif digits == "0":  # Return to main menu
                response.say("Returning to the main menu.")
                response.redirect("/main_menu")
                return Response(str(response), mimetype="text/xml")
            else:
                # Unknown digit command
                response.say("I didn't recognize that command. Let me help you with our menu.")
                response.redirect("/handle_menu_questions?asked=false")
                return Response(str(response), mimetype="text/xml")
        
        # Empty query handling
        if not spoken_query:
            # Handle as silence
            handle_silence(
                response,
                "What would you like to know about our menu?",
                "/handle_menu_questions?asked=true",
                retry_count=session.get("menu_silence_retry", 0),
                interaction_type="menu",
                fallback_url="/main_menu"
            )
            
            # Increment silence retry counter
            session["menu_silence_retry"] = session.get("menu_silence_retry", 0) + 1
            
            return Response(str(response), mimetype="text/xml")
        
        # Reset silence counter since we got input
        session["menu_silence_retry"] = 0
        
        # Check for commands to exit menu questions
        exit_phrases = ["exit", "quit", "main menu", "go back", "order", "place an order"]
        
        if any(phrase in spoken_query.lower() for phrase in exit_phrases):
            if "order" in spoken_query.lower() or "place an order" in spoken_query.lower():
                response.say("I'll help you place an order.")
                response.redirect("/greeting")  # Redirect to order system
            else:
                response.say("Returning to the main menu.")
                response.redirect("/main_menu")
            return Response(str(response), mimetype="text/xml")
        
        # Process the menu question
        # First check for cached response
        cached_response = get_cached_response(spoken_query)
        
        if cached_response:
            logger.info(f"Using cached response for query: {spoken_query}")
            menu_response = cached_response
        else:
            try:
                # Load the most recent menu data
                menu_data = load_menu_data(force_refresh=True)
                
                # Get agent to process menu question
                if OPTIMIZED_MENU_HANDLER:
                    # Use optimized handler
                    menu_response = handle_menu_query(spoken_query, menu_data)
                else:
                    # Use standard agent
                    agent = OrderParsingAgent()
                    menu_response = agent.menu_tool.answer_menu_question(spoken_query)
            except Exception as e:
                logger.error(f"Error processing menu question: {str(e)}")
                menu_response = "I'm sorry, I had trouble processing that menu question. Let me tell you about our popular items instead."
                
                # Fall back to listing popular items
                popular_items = get_popular_menu_items(3)
                
                if popular_items:
                    menu_response += " Some of our most popular items include: "
                    item_texts = []
                    
                    for item in popular_items:
                        name = item.get("name", "")
                        price = item.get("price", 0)
                        price_text = f"${price:.2f}" if price else ""
                        
                        if name and price_text:
                            item_texts.append(f"{name} for {price_text}")
                    
                    menu_response += ", ".join(item_texts) + "."
        
        # Speak the menu response
        response.say(menu_response)
        
        # Offer to continue or return to main menu
        with response.gather(
            action="/handle_menu_follow_up",
            input="dtmf speech",
            speech_model="phone_call",
            enhanced=True,
            speech_timeout=2,
            timeout=5,
            hints="yes, no, main menu, order",
        ) as g:
            g.say("Would you like to ask another question about our menu?")
    
    # Return the TwiML response
    return Response(str(response), mimetype="text/xml")

@voice_bp.route("/handle_menu_follow_up", methods=["POST"])
def handle_menu_follow_up():
    """
    Handle the follow-up after answering a menu question.
    
    This route:
    1. Processes whether the customer wants more menu information
    2. Redirects to either continue menu questions or go to main menu
    3. Provides an option to start ordering
    """
    # Initialize TwiML response
    response = VoiceResponse()
    
    # Get customer response
    spoken_resp = request.form.get("SpeechResult", "").lower()
    digits = request.form.get("Digits", "")
    
    # Log the response
    logger.info(f"Menu follow-up - Speech: '{spoken_resp}', DTMF: '{digits}'")
    
    # Process response
    continue_menu = False
    place_order = False
    
    # Check for affirmative responses to continue menu questions
    yes_phrases = ["yes", "yeah", "yep", "sure", "okay", "continue", "go ahead", "more questions"]
    if any(phrase in spoken_resp for phrase in yes_phrases) or digits == "1":
        continue_menu = True
    
    # Check for order intent
    order_phrases = ["order", "place an order", "start order", "i want to order", "order food"]
    if any(phrase in spoken_resp for phrase in order_phrases) or digits == "2":
        place_order = True
    
    # Redirect based on intent
    if place_order:
        response.say("Great! Let's start your order.")
        response.redirect("/greeting")  # Redirect to order system
    elif continue_menu:
        response.say("I'll help you with more menu information.")
        response.redirect("/handle_menu_questions?asked=false")
    else:
        # Default to returning to main menu
        response.say("Let's return to the main menu.")
        response.redirect("/main_menu")
    
    # Return the TwiML response
    return Response(str(response), mimetype="text/xml")