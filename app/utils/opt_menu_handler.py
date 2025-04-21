"""
Optimized menu handler with caching for faster responses.
This file provides caching for menu queries to improve performance.
"""

import time
import logging
import json
from typing import Dict, Any, Optional

import openai
from flask import session, request, Response
from twilio.twiml.voice_response import VoiceResponse

from app.utils.agent_utils import analyze_user_input, OrderParsingAgent
from app.utils.menu_utils import get_popular_menu_items

logger = logging.getLogger(__name__)

# Cache for menu questions to avoid redundant API calls
menu_questions_cache = {}
menu_questions_cache_duration = 300  # 5 minutes

# Cache for AI responses to avoid redundant API calls
ai_responses_cache = {}
ai_responses_cache_duration = 300  # 5 minutes

def handle_menu_query(user_input):
    """
    Optimized handler for menu questions with caching.
    
    Args:
        user_input: The user's input text
        
    Returns:
        Response: The Twilio response
    """
    # For performance tracking
    start_time = time.time()
    
    # Check for silence
    if not user_input:
        return None  # Let the main handler deal with silence
    
    # Check if we have a cached response for this query
    cleaned_input = user_input.strip().lower()
    current_time = time.time()
    
    # Check for cached complete response
    if cleaned_input in menu_questions_cache:
        cached_response, timestamp = menu_questions_cache[cleaned_input]
        if current_time - timestamp < menu_questions_cache_duration:
            logger.info(f"Using cached complete response for menu question: '{cleaned_input[:30]}...'")
            return cached_response
    
    # Use the agent-based analysis
    analysis_start = time.time()
    analysis = analyze_user_input(user_input)
    intent = analysis.get("intent", "other")
    logger.info(f"Analysis completed in {time.time() - analysis_start:.2f} seconds. Intent: {intent}")
    
    response = VoiceResponse()
    
    if intent == "order_food":
        # User decided to order instead of asking questions
        session["ordering_in_progress"] = True
        # Use a more direct approach for transitioning to ordering
        # Preload any useful context data for faster order processing
        session["menu_context_preloaded"] = True
            
        with response.gather(
            input="speech",
            action="/take_order",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=5,  # Reduced from 10 to 5 for better responsiveness
            timeout=7,  # Reduced from 12 to 7
        ) as g:
            g.say("I'll take your order now. Please tell me what you would like to order.")
    
    elif intent == "ask_menu":
        # Check for cached AI response
        ai_cache_key = f"ai:{cleaned_input}"
        ai_response = None
        
        if ai_cache_key in ai_responses_cache:
            cached_ai, timestamp = ai_responses_cache[ai_cache_key]
            if current_time - timestamp < ai_responses_cache_duration:
                logger.info(f"Using cached AI response for: '{cleaned_input[:30]}...'")
                ai_response = cached_ai
        
        if not ai_response:
            # Need to generate a new response
            # Get menu data based on the query
            search_results = []
            menu_query = user_input.strip()
            
            # Use the search_results from the analysis if available
            if "search_results" in analysis and analysis["search_results"]:
                search_results = analysis["search_results"]
            else:
                # Lightweight menu tool just for search 
                menu_tool = OrderParsingAgent().menu_tool
                search_results = menu_tool.search_menu(menu_query)
            
            # Format menu items for context - more efficiently
            menu_context = []
            if search_results.get("found"):
                for item in search_results.get("items", [])[:5]:  # Limit to 5 items
                    price_str = f"${item.get('price', 0):.2f}"
                    desc = item.get('description', '')[:50]  # Limit description length
                    menu_context.append(f"- {item.get('name')}: {price_str}. {desc}")
            else:
                # Get popular items if no specific match
                popular_items = get_popular_menu_items(5)  # Limit to 5 items
                if popular_items:
                    for item in popular_items:
                        price_str = f"${item.get('price', 0):.2f}"
                        desc = item.get('description', '')[:50]  # Limit description length
                        menu_context.append(f"- {item.get('name')}: {price_str}. {desc}")
            
            menu_context_text = "Here are relevant menu items:\n" + "\n".join(menu_context)
            
            # Create OpenAI client and send concise request with optimized parameters
            client = openai.OpenAI()
            system_msg = (
                "You are a helpful assistant for Red Bar Sushi restaurant. "
                "Answer the customer's question concisely using only the menu information provided. "
                "Keep your response brief and to the point. "
                "If you don't have the specific information, just say so simply."
            )
            
            ai_start = time.time()
            ai_result = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": f"Menu information:\n{menu_context_text}\n\nCustomer question: {user_input}"}
                ],
                temperature=0.1,  # Lower temperature for faster, more deterministic responses
                max_tokens=150    # Limit tokens for faster response
            )
            logger.info(f"AI request completed in {time.time() - ai_start:.2f} seconds")
            
            ai_response = ai_result.choices[0].message.content.strip()
            
            # Cache the AI response
            ai_responses_cache[ai_cache_key] = (ai_response, time.time())
            
            # Limit cache size to avoid memory issues
            if len(ai_responses_cache) > 100:
                # Remove oldest entries
                oldest_keys = sorted(ai_responses_cache.items(), 
                                  key=lambda x: x[1][1])[:30]
                for key, _ in oldest_keys:
                    ai_responses_cache.pop(key, None)
        
        # Say the AI response and offer to continue the conversation
        response.say(ai_response)
        
        # Add a gather to continue the conversation
        with response.gather(
            input="speech",
            action="/handle_menu_questions",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=5,  # Reduced from 10 to 5 for better responsiveness
            timeout=7,  # Reduced from 12 to 7
        ) as g:
            g.say("Is there anything else you'd like to know about our menu?")
    
    elif intent == "get_menu_item_price" or intent == "describe_menu_item":
        # Handle specific menu item queries
        # This part could also be further optimized with similar caching techniques
        # The general idea is the same as above
        item_name = ""
        if "menu_items" in analysis and analysis["menu_items"]:
            item_name = analysis["menu_items"][0]["name"]
        
        item_cache_key = f"{intent}:{item_name.lower()}"
        item_desc = None
        
        if item_cache_key in menu_questions_cache:
            cached_desc, timestamp = menu_questions_cache[item_cache_key]
            if current_time - timestamp < menu_questions_cache_duration:
                logger.info(f"Using cached item description for: '{item_name}'")
                item_desc = cached_desc
        
        if not item_desc:
            # Need to generate a new description
            menu_tool = OrderParsingAgent().menu_tool
            result = menu_tool.get_details(item_name)
            
            if result.get("found"):
                item = result.get("item", {})
                if item.get("available", True) and not item.get("snoozed", False):
                    item_desc = f"The {item.get('name')} costs ${item.get('price', 0):.2f}."
                    if intent == "describe_menu_item":
                        item_desc += f" {item.get('description', 'It is one of our popular items.')}"
                    
                    # Add modifier info if needed - simplified for performance
                    if result.get("modifiers") and intent == "describe_menu_item":
                        mod_groups = result.get("modifiers", [])
                        if mod_groups:
                            mod_info = " Available add-ons include: "
                            mod_list = []
                            for group in mod_groups[:1]:  # Just use the first group
                                for mod in group.get("modifiers", [])[:3]:  # Limit to 3 modifiers
                                    mod_name = mod.get("name", "")
                                    mod_price = mod.get("price", 0)
                                    if mod_price > 0:
                                        mod_list.append(f"{mod_name} (${mod_price:.2f})")
                                    else:
                                        mod_list.append(mod_name)
                            if mod_list:
                                item_desc += mod_info + ", ".join(mod_list) + "."
                else:
                    # Item exists but is unavailable
                    item_desc = f"I'm sorry, the {item.get('name')} is currently unavailable."
            else:
                # Try to suggest alternatives if item not found
                popular_items = get_popular_menu_items(2)  # Just 2 items for speed
                if popular_items:
                    items_text = ", ".join([f"{item['name']}" for item in popular_items])
                    item_desc = f"I couldn't find '{item_name}' on our menu. You might be interested in: {items_text}."
                else:
                    item_desc = f"I'm sorry, I couldn't find '{item_name}' on our menu."
            
            # Cache the generated description
            menu_questions_cache[item_cache_key] = (item_desc, time.time())
        
        with response.gather(
            input="speech",
            action="/handle_menu_questions",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=5,  # Changed from "auto" to 5 seconds for more predictable behavior
            timeout=7,  # Added fixed timeout instead of default
        ) as g:
            g.say(item_desc + " Is there anything else you'd like to know about our menu?")
    
    else:
        # Default response for other intents
        with response.gather(
            input="speech dtmf",
            action="/main_menu",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=5,  # Changed from "auto" to 5 seconds
            timeout=7,  # Added explicit timeout
            num_digits=1,
        ) as g:
            g.say(
                "I'm not sure I understood your question. "
                + "Press 1 to order, 2 to ask another menu question, or 3 to speak to a person."
            )
    
    # Cache the entire response for this user input
    menu_questions_cache[cleaned_input] = (response, time.time())
    
    # Limit cache size to avoid memory issues
    if len(menu_questions_cache) > 100:
        # Remove oldest entries
        oldest_keys = sorted(menu_questions_cache.items(), 
                          key=lambda x: x[1][1])[:30]
        for key, _ in oldest_keys:
            menu_questions_cache.pop(key, None)
    
    logger.info(f"Total menu question handling time: {time.time() - start_time:.2f} seconds")
    return response
