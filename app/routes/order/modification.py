"""
Order modification routes for RedBarSushiAI.
This module provides the routes for modifying orders.
"""

import json
import logging
from flask import request, session, Response
from twilio.twiml.voice_response import VoiceResponse

from app.routes.order import order_bp
from app.utils.agent_utils import OrderParsingAgent, get_order_modifications
from app.utils.order_utils import build_order_description, calculate_bill_amount, validate_modifiers, mark_unavailable_items

# Configure logger
logger = logging.getLogger(__name__)

@order_bp.route("/new_modify_order", methods=["POST"])
def new_modify_order():
    """
    Process order modifications from the user.
    This route handles requests to modify an existing order.
    """
    # Get the speech result from the request
    user_resp = request.form.get("SpeechResult", "").strip()
    
    # Build the response object
    response = VoiceResponse()
    
    # Handle silence (no speech)
    if not user_resp:
        # Count silence retries
        silence_retry = session.get("modify_silence_retry", 0)
        session["modify_silence_retry"] = silence_retry + 1
        
        # If too many retries, send to fallback
        if silence_retry >= 2:
            logger.info("Multiple silence retries in modify, sending to fallback")
            response.redirect("/modification_silence_fallback")
            return Response(str(response), mimetype="text/xml")
        
        # Try again
        with response.gather(
            input="speech",
            action="/new_modify_order",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=5,
            timeout=7
        ) as g:
            g.say(
                "I didn't hear your changes. Please tell me what modifications you'd like to make to your order."
            )
        return Response(str(response), mimetype="text/xml")
    
    # Reset silence counter since we got a response
    session["modify_silence_retry"] = 0
    
    # Get the current order from session
    try:
        current_order = json.loads(session.get("order_items_json", "[]"))
        if not current_order:
            # If no order found, handle the error gracefully
            logger.error("No order found in session for modification")
            response.say("I'm sorry, I couldn't find your order details. Let's start over.")
            response.redirect("/take_order")
            return Response(str(response), mimetype="text/xml")
    except Exception as e:
        logger.error(f"Error loading order from session: {e}")
        response.say("I'm sorry, there was an error processing your order. Let's try again.")
        response.redirect("/take_order")
        return Response(str(response), mimetype="text/xml")
    
    # Get order modifications using the agent
    logger.info(f"Getting modifications for: '{user_resp}'")
    
    try:
        modifications = get_order_modifications(user_resp, current_order)
        logger.info(f"Modifications: {modifications}")
        
        # If no modifications were detected, ask again
        if not modifications.get("changes", []):
            # Count understanding retries
            understand_retry = session.get("modify_understand_retry", 0)
            session["modify_understand_retry"] = understand_retry + 1
            
            # If too many retries, send to fallback
            if understand_retry >= 2:
                logger.info("Multiple understanding retries in modify, sending to fallback")
                response.redirect("/modification_silence_fallback")
                return Response(str(response), mimetype="text/xml")
            
            # Try again with more guidance
            with response.gather(
                input="speech",
                action="/new_modify_order",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout=5,
                timeout=7
            ) as g:
                g.say(
                    "I couldn't understand what changes you want to make. You can say things like 'add a California roll' or 'remove the spicy tuna roll'. Please tell me your changes now."
                )
            return Response(str(response), mimetype="text/xml")
        
        # Reset understanding counter since we got meaningful modifications
        session["modify_understand_retry"] = 0
        
        # Apply the modifications to the current order
        updated_order = apply_modifications(current_order, modifications)
        logger.info(f"Updated order: {updated_order}")
        
        # Process and mark any unavailable items
        available_items, unavailable_items = mark_unavailable_items(updated_order)
        
        # Handle case where all items are unavailable
        if not available_items and unavailable_items:
            unavailable_names = [item.get("name", "").split(" (")[0] for item in unavailable_items]
            unavailable_text = ", ".join(unavailable_names)
            
            response.say(
                f"I'm sorry, all the items in your updated order ({unavailable_text}) are currently unavailable. Let's try a different order."
            )
            
            # Redirect to take a new order
            response.redirect("/take_order")
            return Response(str(response), mimetype="text/xml")
        
        # Include both available and unavailable items in the order
        # (unavailable items will be shown separately in the order description)
        updated_order = available_items + unavailable_items
        
        # Calculate total and prepare confirmation
        calculate_bill_amount(updated_order)
        order_description = build_order_description(updated_order)
        session["bill_amount"] = int(session.get("total_price", 0) * 100)
        session["order_items_json"] = json.dumps(updated_order)
        session["order_message"] = (
            f"Your updated order is: {order_description}\nYour new total is ${session.get('total_price', 0):.2f}."
        )
        
        # Ask for confirmation
        with response.gather(
            input="speech dtmf",
            action="/confirm_order_after_modification",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=5,
            timeout=7,
            num_digits=1
        ) as g:
            g.say(
                session["order_message"]
                + " If correct, say yes or press 1. If you need more changes, say no or press 2."
            )
        
        return Response(str(response), mimetype="text/xml")
        
    except Exception as e:
        logger.error(f"Error processing modifications: {e}")
        response.say("I'm sorry, there was an error processing your changes. Let's try again.")
        
        # Ask for modifications again
        with response.gather(
            input="speech",
            action="/new_modify_order",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=5,
            timeout=7
        ) as g:
            g.say("Please tell me what changes you'd like to make to your order.")
        
        return Response(str(response), mimetype="text/xml")

def apply_modifications(current_order, modifications):
    """
    Apply modifications to the current order.
    
    Args:
        current_order: Current order items
        modifications: Modification instructions
        
    Returns:
        Updated order items
    """
    # Make a copy of the current order to avoid modifying the original
    updated_order = current_order.copy()
    
    # Get the changes from the modifications
    changes = modifications.get("changes", [])
    
    # Process each change
    for change in changes:
        change_type = change.get("type")
        
        if change_type == "add":
            # Add new items to the order
            new_items = change.get("items", [])
            
            for new_item in new_items:
                # Check if the item is already in the order
                existing_items = [item for item in updated_order 
                                if item.get("name") == new_item.get("name")]
                
                if existing_items:
                    # Item already exists, update quantity
                    existing_item = existing_items[0]
                    existing_qty = existing_item.get("quantity", 1)
                    new_qty = new_item.get("quantity", 1)
                    existing_item["quantity"] = existing_qty + new_qty
                    logger.info(f"Updated quantity of {existing_item['name']} to {existing_item['quantity']}")
                else:
                    # Add the new item to the order
                    updated_order.append(new_item)
                    logger.info(f"Added new item: {new_item['name']}")
                
        elif change_type == "remove":
            # Remove items from the order
            items_to_remove = change.get("items", [])
            
            for item_to_remove in items_to_remove:
                remove_name = item_to_remove.get("name")
                remove_qty = item_to_remove.get("quantity", 1)
                
                # Find matching items in the order
                for i, item in enumerate(updated_order):
                    if item.get("name") == remove_name:
                        current_qty = item.get("quantity", 1)
                        
                        if current_qty <= remove_qty:
                            # Remove the entire item
                            updated_order.pop(i)
                            logger.info(f"Removed item: {remove_name}")
                            break
                        else:
                            # Reduce the quantity
                            item["quantity"] = current_qty - remove_qty
                            logger.info(f"Reduced quantity of {remove_name} to {item['quantity']}")
                            break
                
        elif change_type == "modify":
            # Modify items in the order
            item_name = change.get("item_name")
            modifiers_to_add = change.get("add_modifiers", [])
            modifiers_to_remove = change.get("remove_modifiers", [])
            
            # Find the item to modify
            for item in updated_order:
                if item.get("name") == item_name:
                    # Initialize modifiers list if it doesn't exist
                    if "modifier" not in item or not item["modifier"]:
                        item["modifier"] = []
                    
                    # Add new modifiers
                    for mod_to_add in modifiers_to_add:
                        # Check if modifier already exists
                        existing_mods = [m for m in item["modifier"] 
                                        if m.get("name") == mod_to_add.get("name")]
                        
                        if existing_mods:
                            # Update existing modifier
                            existing_mod = existing_mods[0]
                            existing_mod["quantity"] = existing_mod.get("quantity", 1) + mod_to_add.get("quantity", 1)
                        else:
                            # Add new modifier
                            item["modifier"].append(mod_to_add)
                    
                    # Remove modifiers
                    for mod_to_remove in modifiers_to_remove:
                        remove_name = mod_to_remove.get("name")
                        item["modifier"] = [m for m in item["modifier"] 
                                           if m.get("name") != remove_name]
                    
                    logger.info(f"Modified modifiers for {item_name}")
                    break
        
        elif change_type == "replace":
            # Replace the entire order
            replace_items = change.get("items", [])
            if replace_items:
                updated_order = replace_items
                logger.info(f"Replaced entire order with {len(replace_items)} items")
    
    # Make sure all items have a quantity
    for item in updated_order:
        if "quantity" not in item or not item["quantity"]:
            item["quantity"] = 1
        
        # Make sure all modifiers have a quantity
        if "modifier" in item and item["modifier"]:
            for mod in item["modifier"]:
                if "quantity" not in mod or not mod["quantity"]:
                    mod["quantity"] = 1
    
    return updated_order

@order_bp.route("/handle_modifier_suggestion", methods=["POST"])
def handle_modifier_suggestion():
    """
    Handle responses to modifier suggestions.
    """
    # Get the response
    user_resp = request.form.get("SpeechResult", "").strip()
    dtmf_digits = request.form.get("Digits", "").strip()
    
    # Get the current modifier item from session
    current_item = session.get("current_modifier_item", "")
    
    # Build the response
    response = VoiceResponse()
    
    # Get the order with updates
    try:
        order_items = json.loads(session.get("order_items_without_modifiers_json", "[]"))
        
        # If we have a response, try to parse modifier selections
        if user_resp:
            # Use an agent to parse the modifier choices
            agent = OrderParsingAgent()
            
            # Parse the modifier choices
            parsed_modifiers = agent.parse_modifier_choices(current_item, user_resp)
            logger.info(f"Parsed modifiers for {current_item}: {parsed_modifiers}")
            
            # Add the modifiers to the appropriate item
            for item in order_items:
                if item.get("name") == current_item:
                    # Initialize modifier list if not present
                    if "modifier" not in item:
                        item["modifier"] = []
                    
                    # Add the new modifiers
                    for mod in parsed_modifiers:
                        item["modifier"].append(mod)
                    
                    break
        
        # Check if there are more items needing modifiers
        remaining_items = json.loads(session.get("remaining_modifier_items", "[]"))
        
        if remaining_items:
            # Get the next item to modify
            next_item = remaining_items[0]
            next_item_name = next_item.get("name", "")
            
            # Update session
            session["current_modifier_item"] = next_item_name
            session["remaining_modifier_items"] = (
                json.dumps(remaining_items[1:])
                if len(remaining_items) > 1
                else "[]"
            )
            
            # Get modifier suggestions for the next item
            agent = OrderParsingAgent()
            modifier_prompt = agent.menu_tool.generate_modifier_prompt(next_item_name)
            
            # Store updated order
            session["order_items_without_modifiers_json"] = json.dumps(order_items)
            
            # Ask for modifiers for the next item
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
        
        # No more items need modifiers, continue with the order
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
            num_digits=1
        ) as g:
            g.say(
                session["order_message"]
                + " If correct, say yes or press 1. If you need changes, say no or press 2."
            )
        
        return Response(str(response), mimetype="text/xml")
        
    except Exception as e:
        logger.error(f"Error processing modifier suggestions: {e}")
        response.say("I'm sorry, there was an error processing your choices. Let's continue with your order.")
        
        # Skip to order confirmation
        response.redirect("/confirm_order_from_initial")
        return Response(str(response), mimetype="text/xml")

# Export all functions
__all__ = ['new_modify_order', 'apply_modifications', 'handle_modifier_suggestion']