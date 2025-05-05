"""
Order checkout and processing routes for RedBarSushiAI.
This module provides the routes for order checkout and final processing.
"""

import json
import logging
import requests
import uuid
import time
import re
from datetime import datetime
from flask import request, session, Response, url_for, redirect, jsonify
from twilio.twiml.voice_response import VoiceResponse
from twilio.twiml.messaging_response import MessagingResponse

# Import blueprint reference directly to avoid circular imports
from app.routes.order.__init__ import order_bp
from app.utils.order_utils import mark_unavailable_items, build_order_description, validate_modifiers
from app.utils.deliverect import (
    build_deliverect_order, 
    get_deliverect_headers, 
    send_order_to_deliverect,
    generate_order_id
)
from app.utils.helpers import log_info, commit_with_retry
from app.config import DELIVERECT_API_URL, BASE_URL
from app import db, twilio_client
from app.models import Order

# Configure logger
logger = logging.getLogger(__name__)

# Try to import tasks module for status updates
try:
    from tasks import send_order_status_update_task
except ImportError:
    # Create a dummy task for testing
    def send_order_status_update_task(*args, **kwargs):
        logger.warning(
            "Could not import send_order_status_update_task from tasks module. Will try again when needed."
        )

@order_bp.route("/process_order_checkout", methods=["GET", "POST"])
def process_order_checkout():
    """
    Process the final order checkout.
    This route handles order submission to Deliverect and payment processing.
    """
    # Check if this is a retry
    is_retry = request.args.get("retry", "false").lower() == "true"
    
    # Build the response
    response = VoiceResponse()
    
    # Get the order from session
    try:
        order_items = json.loads(session.get("order_items_json", "[]"))
        
        # If no items in order, handle gracefully
        if not order_items:
            logger.error("No items in order for checkout")
            response.say("I'm sorry, your order appears to be empty. Let's try again.")
            response.redirect("/take_order")
            return Response(str(response), mimetype="text/xml")
        
        # If this is not a retry, check for newly unavailable items
        if not is_retry:
            # Check if any items have become unavailable since we last checked
            available_items, unavailable_items = mark_unavailable_items(order_items)
            
            # If items have changed, ask user what to do
            if unavailable_items and len(unavailable_items) > 0:
                unavailable_names = [item.get("name", "").split(" (")[0] for item in unavailable_items]
                unavailable_text = ", ".join(unavailable_names)
                
                response.say(
                    f"I'm sorry, but the following items are now unavailable: {unavailable_text}."
                )
                
                # If all items are unavailable, handle differently
                if not available_items:
                    response.say(
                        "Unfortunately, all items in your order are currently unavailable. Would you like to order something else?"
                    )
                    
                    with response.gather(
                        input="speech dtmf",
                        action="/handle_unavailable_order",
                        enhanced=True,
                        speech_model="phone_call",
                        language="en-US",
                        speech_timeout=5,
                        timeout=7,
                        num_digits=1
                    ) as g:
                        g.say(
                            "Press 1 to order something else, press 2 to hear our menu options, or press 3 to end the call."
                        )
                    
                    return Response(str(response), mimetype="text/xml")
                
                # Some items available, ask if they want to continue
                with response.gather(
                    input="speech dtmf",
                    action="/handle_newly_snoozed_in_checkout",
                    enhanced=True,
                    speech_model="phone_call",
                    language="en-US",
                    speech_timeout=5,
                    timeout=7,
                    num_digits=1
                ) as g:
                    g.say(
                        "Would you like to continue with just the available items? Say yes or press 1 to continue with available items only. Say no or press 2 to modify your order."
                    )
                
                return Response(str(response), mimetype="text/xml")
            
            # If we get here, all items are still available
            # Update the session with available items just to be safe
            session["order_items_json"] = json.dumps(available_items)
            order_items = available_items
        
        # Process the order for Deliverect
        call_sid = request.form.get("CallSid", request.args.get("CallSid", "unknown"))
        phone_number = request.form.get("From", request.args.get("From", "unknown"))
        
        # Clean the phone number (remove +)
        if phone_number.startswith("+"):
            phone_number = phone_number[1:]
        
        # Get customer name from session if available
        customer_name = session.get("customer_name", "Guest")
        
        # Prepare order data for Deliverect
        order_data = {
            "customer": {
                "name": customer_name,
                "phone_number": phone_number,
                "phoneNumber": phone_number,  # Both formats for compatibility
                "email": ""  # No email in voice flow
            },
            "items": order_items,
            "order_type": 1,  # Default to pickup
            "payment_type": 1,  # Default to cash
            "notes": "",
            "call_sid": call_sid
        }
        
        # Generate channel order ID
        channel_order_id, display_id = generate_order_id()
        
        # Add to order data
        order_data["channelOrderId"] = channel_order_id
        order_data["channelOrderDisplayId"] = display_id
        
        # Build the Deliverect order
        deliverect_order = build_deliverect_order(order_data)
        
        # Validate that the order has valid modifiers according to menu constraints
        validation_result = validate_modifiers(deliverect_order)
        
        if not validation_result["valid"]:
            logger.error(f"Order validation failed: {validation_result['message']}")
            
            # If validation failed due to missing required modifiers,
            # give the customer another chance to add them
            if validation_result.get("missing_required_modifiers", False):
                response.say(
                    "I'm sorry, but there are required options missing from your order."
                )
                response.redirect("/new_modify_order")
                return Response(str(response), mimetype="text/xml")
            
            # For other validation errors, offer to modify the order
            response.say(
                f"I'm sorry, but there's an issue with your order: {validation_result['message']}. Let's make some adjustments."
            )
            response.redirect("/new_modify_order")
            return Response(str(response), mimetype="text/xml")
        
        # Send the order to Deliverect
        logger.info(f"Sending order to Deliverect: {json.dumps(deliverect_order)}")
        
        # Track order in our database first
        order = Order(
            customer_phone=phone_number,
            customer_name=customer_name,
            order_type=order_data.get("order_type", 1),
            status=10,  # Initial status: received
            total_price=session.get("bill_amount", 0),
            placed_at=datetime.now(),
            deliverect_channel_order_id=channel_order_id
        )
        
        # Try to commit the order record
        try:
            db.session.add(order)
            commit_with_retry(db.session)
            logger.info(f"Saved order record with ID: {order.id}")
        except Exception as e:
            logger.error(f"Failed to save order record: {e}")
            # Continue anyway - we'll still try to send to Deliverect
        
        # Now send to Deliverect
        success, deliverect_response, status_code = send_order_to_deliverect(deliverect_order)
        
        if success:
            logger.info(f"Order submitted successfully to Deliverect: {deliverect_response}")
            
            # Send confirmation SMS to the customer
            try:
                # Update order status
                order.status = 20  # Accepted
                commit_with_retry(db.session)
                
                # Send confirmation SMS
                if send_order_status_update_task:
                    # If we have the Celery task, use it
                    send_order_status_update_task.delay(order.id)
                    logger.info(f"Queued status update notification for order {order.id}")
                else:
                    # Direct SMS send if Celery not available
                    try:
                        # Calculate estimated pickup time (20 minutes from now)
                        pickup_time = datetime.now()
                        pickup_time = pickup_time.replace(
                            minute=pickup_time.minute + 20,
                            second=0,
                            microsecond=0
                        )
                        
                        # Format pickup time
                        pickup_time_str = pickup_time.strftime("%I:%M %p")
                        
                        # Format message
                        message = (
                            f"Thank you for your order at Red Bar Sushi! "
                            f"Your order #{order.id} has been received and will be ready around {pickup_time_str}. "
                            f"Total: ${order.total_price/100:.2f}"
                        )
                        
                        # Send SMS
                        if twilio_client:
                            twilio_client.messages.create(
                                body=message,
                                from_="+18005551234",  # Use your Twilio phone number
                                to=f"+{phone_number}"
                            )
                            logger.info(f"Sent confirmation SMS to +{phone_number}")
                        else:
                            logger.error("Twilio client not available for SMS")
                    except Exception as e:
                        logger.error(f"Failed to send confirmation SMS: {e}")
            except Exception as e:
                logger.error(f"Error updating order status or sending SMS: {e}")
            
            # Tell the customer their order is successful
            response.say(
                "Great news! Your order has been successfully placed. You'll receive a text message confirmation shortly. "
                "Your order will be ready for pickup in approximately 20 minutes. Thank you for choosing Red Bar Sushi!"
            )
            
            # Redirect to order completion options
            response.redirect("/order_completion_options")
            return Response(str(response), mimetype="text/xml")
        else:
            # Order submission failed
            logger.error(f"Failed to submit order to Deliverect: {deliverect_response}")
            
            # Check if it's a validation error or system error
            error_message = "There was an issue processing your order through our system."
            
            if status_code == 400:
                # Validation error
                error_detail = "The order format was invalid."
            elif status_code == 401:
                # Authentication error
                error_detail = "There was an authentication error with the order system."
            elif status_code == 429:
                # Rate limiting
                error_detail = "The order system is currently experiencing high volume."
            elif status_code in [500, 502, 503, 504]:
                # Server error
                error_detail = "The order system is currently unavailable."
            else:
                # Unknown error
                error_detail = "An unexpected error occurred."
            
            # Tell customer about the error and offer options
            response.say(
                f"I'm sorry, but {error_message} {error_detail} "
                "Would you like to try again or speak with a team member?"
            )
            
            # Gather response for next steps
            with response.gather(
                input="speech dtmf",
                action="/handle_order_error",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout=5,
                timeout=7,
                num_digits=1
            ) as g:
                g.say(
                    "Say 'try again' or press 1 to retry, say 'team member' or press 2 to speak with a team member, or say 'cancel' or press 3 to cancel your order."
                )
                
            return Response(str(response), mimetype="text/xml")
            
    except Exception as e:
        logger.error(f"Error processing order checkout: {e}")
        response.say(
            "I'm sorry, but there was an unexpected error processing your order. "
            "Let me transfer you to a team member who can help."
        )
        response.dial("+18005551234")  # Replace with actual restaurant number
        return Response(str(response), mimetype="text/xml")

@order_bp.route("/handle_order_error", methods=["POST"])
def handle_order_error():
    """
    Handle different options after an order submission error.
    """
    # Get the response
    user_resp = request.form.get("SpeechResult", "").strip().lower()
    dtmf_digits = request.form.get("Digits", "").strip()
    
    # Build the response
    response = VoiceResponse()
    
    if dtmf_digits == "1" or "try" in user_resp or "again" in user_resp or "retry" in user_resp:
        # User wants to retry
        response.say("Let's try submitting your order again.")
        response.redirect("/process_order_checkout?retry=true")
    elif dtmf_digits == "2" or "team" in user_resp or "speak" in user_resp or "member" in user_resp:
        # User wants to speak with a team member
        response.say("I'll transfer you to a team member who can help process your order.")
        response.dial("+18005551234")  # Replace with actual restaurant number
    elif dtmf_digits == "3" or "cancel" in user_resp:
        # User wants to cancel
        response.say("I understand you'd like to cancel your order. Your order has been canceled. Thank you for calling Red Bar Sushi, and we hope to serve you soon!")
        response.hangup()
    else:
        # Unclear response, retry
        with response.gather(
            input="speech dtmf",
            action="/handle_order_error",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=5,
            timeout=7,
            num_digits=1
        ) as g:
            g.say(
                "I didn't understand your response. Say 'try again' or press 1 to retry, say 'team member' or press 2 to speak with a team member, or say 'cancel' or press 3 to cancel your order."
            )
    
    return Response(str(response), mimetype="text/xml")

@order_bp.route("/order_completion_options", methods=["POST"])
def order_completion_options():
    """
    Present options after order completion.
    """
    # Build the response
    response = VoiceResponse()
    
    # Give the customer options
    with response.gather(
        input="speech dtmf",
        action="/handle_completion_options",
        enhanced=True,
        speech_model="phone_call",
        language="en-US",
        speech_timeout=5,
        timeout=7,
        num_digits=1
    ) as g:
        g.say(
            "Is there anything else I can help you with? Say 'menu information' or press 1 to learn about our menu. "
            "Say 'specials' or press 2 to hear today's specials. "
            "Say 'goodbye' or press 3 to end the call."
        )
    
    return Response(str(response), mimetype="text/xml")

@order_bp.route("/handle_completion_options", methods=["POST"])
def handle_completion_options():
    """
    Handle options after order completion.
    """
    # Get the response
    user_resp = request.form.get("SpeechResult", "").strip().lower()
    dtmf_digits = request.form.get("Digits", "").strip()
    
    # Build the response
    response = VoiceResponse()
    
    if dtmf_digits == "1" or "menu" in user_resp:
        # User wants menu information
        response.say("I'd be happy to tell you about our menu.")
        response.redirect("/menu_info")
    elif dtmf_digits == "2" or "special" in user_resp:
        # User wants to hear specials
        response.say(
            "Today's specials include our Chef's Special Roll with fresh tuna, salmon, and yellowtail, "
            "topped with avocado and a special sauce. We also have a special discount on our Bento Box lunch special. "
            "Thank you for your interest, and we hope you enjoy your order!"
        )
        response.hangup()
    elif dtmf_digits == "3" or "goodbye" in user_resp or "end" in user_resp or "hang up" in user_resp:
        # User wants to end call
        response.say("Thank you for your order with Red Bar Sushi. We hope you enjoy your meal. Goodbye!")
        response.hangup()
    else:
        # Unclear response or no response
        response.say("Thank you for your order with Red Bar Sushi. We hope you enjoy your meal. Goodbye!")
        response.hangup()
    
    return Response(str(response), mimetype="text/xml")

# Export all functions
__all__ = [
    'process_order_checkout', 
    'handle_order_error', 
    'order_completion_options', 
    'handle_completion_options'
]