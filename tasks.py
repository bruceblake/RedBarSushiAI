# tasks.py
import logging
import stripe
import requests
import os
import gc
import time
import resource
from app import db, twilio_client, create_app
from app.models import Order
from app.utils.helpers import log_info, commit_with_retry
import app.config as config

# Import celery instance after it's fully defined
from celery_app import celery

# Memory profiling decorator for tasks
def memory_profiler(func):
    def wrapper(*args, **kwargs):
        # Only profile if debug is enabled
        if not os.environ.get('CELERY_PROFILE_MEMORY', 'false').lower() == 'true':
            return func(*args, **kwargs)
            
        task_name = func.__name__
        start_time = time.time()
        
        # Get initial memory usage
        gc.collect()  # Collect garbage before measurement
        start_memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        logging.info(f"[MEMORY] {task_name} starting - Current memory: {start_memory/1024:.2f}MB")
        
        # Execute the task
        result = func(*args, **kwargs)
        
        # Get final memory usage
        gc.collect()  # Collect garbage after task
        end_memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        memory_diff = end_memory - start_memory
        end_time = time.time()
        
        logging.info(f"[MEMORY] {task_name} completed in {end_time-start_time:.2f}s - "
                   f"Final memory: {end_memory/1024:.2f}MB, "
                   f"Diff: {memory_diff/1024:.2f}MB")
        
        return result
    return wrapper

# Use regular SMS number, not WhatsApp
TWILIO_PHONE_NUMBER = config.TWILIO_NUMBER
# Owner phone number without WhatsApp prefix for regular SMS
OWNER_PHONE_NUMBER = '+17032972632'

@celery.task(name="tasks.sync_menu_references")
@memory_profiler
def sync_menu_references():
    """
    Periodic task to ensure menu reference handlers and prices are synchronized
    across all locations.
    
    This task ensures that all menu items have consistent reference handlers
    and prices, keeping the menu data in a valid state.
    """
    app = create_app()
    with app.app_context():
        from app.utils.menu_utils import sync_reference_handlers
        
        logging.info("Starting menu reference synchronization task")
        
        # Get all location IDs
        try:
            from app.models import Location
            
            locations = db.session.query(Location).all()
            location_ids = [loc.id for loc in locations]
            
            # First sync the default menu
            stats = sync_reference_handlers()
            logging.info(f"Default menu sync stats: {stats}")
            
            # Then sync each location-specific menu
            for loc_id in location_ids:
                loc_stats = sync_reference_handlers(target_location_id=loc_id)
                logging.info(f"Location {loc_id} menu sync stats: {loc_stats}")
                
            return True
        except Exception as e:
            logging.error(f"Error during menu sync: {e}")
            return False

@celery.task(name="tasks.send_confirmation_sms_task", bind=True, max_retries=3)
@memory_profiler
def send_confirmation_sms_task(self, order_id, order_message, sender, caller_name, bill_amount, order_items, location_id=None):
    try:
        app = create_app()
        with app.app_context():
            # Create a nicely formatted message
            base_message = order_message.strip()
            
            # Add location to the message if provided
            location_prefix = ""
            location_name = "Red Bar Sushi"  # Default name
            if location_id:
                # Get location name from database if available
                try:
                    from app.models import Location
                    location = db.session.query(Location).filter_by(id=location_id).first()
                    if location:
                        location_name = location.name
                        location_prefix = f" at our {location_name}"
                    else:
                        location_prefix = f" at our {location_id} location"
                except Exception as e:
                    logging.info(f"Error getting location name: {e}")
                    location_prefix = f" at our {location_id} location"
                    
            # Extract order items and total
            order_items_text = ""
            total_text = ""
            
            lines = base_message.split('\n')
            for line in lines:
                if line.startswith('- '):  # This is an item line
                    order_items_text += line + "\n"
                elif "total" in line.lower():  # This is the total line
                    total_text = line
                    
            # Create a more attractive, structured message with emojis and improved formatting
            text_msg = f"""🍣 RED BAR SUSHI ORDER CONFIRMATION 🍣

Thank you for ordering{location_prefix}!

📋 YOUR ORDER:
{order_items_text}
{total_text}

🆔 Order ID: {order_id[:8]}
"""

            # Add estimated pickup time with emoji
            prep_time = 20 + (len(order_items) * 2)  # Base time + time per item
            current_time = time.strftime("%I:%M %p")  # Get current time in 12hr format
            pickup_time = f"⏱️ Estimated pickup time: {prep_time} minutes (around {time.strftime('%I:%M %p', time.localtime(time.time() + prep_time*60))})"
            text_msg += f"\n{pickup_time}"
            text_msg += f"\n🕒 Order placed at: {current_time}"
            
            # Add restaurant location and phone
            text_msg += f"\n\n📍 {location_name}"
            text_msg += "\n📞 (703) 297-2632"  # Restaurant phone
            
            # Create payment link with better description
            try:
                product_id = config.STRIPE_PRODUCT_ID
                stripe_amnt = int(bill_amount)
                price = stripe.Price.create(currency="usd", unit_amount=stripe_amnt, product=product_id)
                payment_link = stripe.PaymentLink.create(line_items=[{'price': price.id, 'quantity': 1}])
                text_msg += f"\n\n💳 PAY NOW: {payment_link.url}"
                text_msg += "\nSecurely pay online with credit card"
            except Exception as e:
                logging.info(f"Stripe link error: {e}")
                text_msg += "\n\n💵 Please pay when you pick up your order."
                
            # Add instructions for status checks with better formatting
            text_msg += "\n\n📱 SMS COMMANDS:"
            text_msg += "\n• Reply 'status' to check your order status"
            text_msg += "\n• Reply 'help' for more options"
            
            # Send SMS to customer with improved error handling and retries
            try:
                # Normalize phone number format
                normalized_sender = sender
                if not normalized_sender.startswith('+'):
                    normalized_sender = f"+{normalized_sender}"
                
                # Log the attempt
                logging.info(f"Sending confirmation SMS to {normalized_sender}")
                
                # Send the message
                message = twilio_client.messages.create(
                    body=text_msg,
                    from_=TWILIO_PHONE_NUMBER,
                    to=normalized_sender,
                    status_callback=f"{os.environ.get('BASE_URL', 'https://redbarsushiai.onrender.com')}/sms_status_callback"
                )
                
                # Log success with SID for tracking
                logging.info(f"SMS confirmation sent successfully! SID: {message.sid}")
                
                # Store the message SID in the database for tracking
                try:
                    order = db.session.get(Order, order_id)
                    if order:
                        order.sms_sid = message.sid
                        order.sms_status = "sent"
                        db.session.commit()
                except Exception as db_err:
                    logging.error(f"Error updating order with SMS SID: {db_err}")
                
            except Exception as e:
                logging.error(f"SMS error: {e}")
                # Try a second approach if the first fails
                try:
                    logging.info("Trying alternative SMS approach...")
                    # Remove any formatting from the phone number
                    plain_number = ''.join(filter(lambda x: x.isdigit(), sender))
                    if len(plain_number) == 10:  # US number without country code
                        plain_number = f"+1{plain_number}"
                    elif len(plain_number) > 10:  # Might already have country code
                        plain_number = f"+{plain_number}"
                        
                    message = twilio_client.messages.create(
                        body=text_msg,
                        from_=TWILIO_PHONE_NUMBER,
                        to=plain_number,
                        status_callback=f"{os.environ.get('BASE_URL', 'https://redbarsushiai.onrender.com')}/sms_status_callback"
                    )
                    logging.info(f"Alternative SMS approach successful! SID: {message.sid}")
                except Exception as alt_e:
                    logging.error(f"Alternative SMS approach also failed: {alt_e}")
            
            # Send SMS notification to owner (not WhatsApp)
            try:
                # Include location in owner notification
                owner_msg = text_msg
                if location_id and "location" not in owner_msg:
                    owner_msg = f"New order from{location_prefix}:\n{owner_msg}"
                    
                # Use regular SMS for owner notification
                twilio_client.messages.create(
                    body=owner_msg,
                    from_=TWILIO_PHONE_NUMBER,
                    to=OWNER_PHONE_NUMBER,
                    status_callback=f"{os.environ.get('BASE_URL', 'https://redbarsushiai.onrender.com')}/sms_status_callback"
                )
                logging.info(f"Owner notification SMS sent to {OWNER_PHONE_NUMBER}")
            except Exception as e:
                logging.info(f"Owner notification SMS error: {e}")
            
            # Update order in database (should already exist but update message)
            try:
                order = db.session.get(Order, order_id)
                if order:
                    # Update existing order
                    order.message = text_msg
                    if location_id and not order.location_id:
                        order.location_id = location_id
                else:
                    # Create new order if not found
                    new_order = Order(
                        id=order_id,
                        sender=sender,
                        caller_name=caller_name,
                        message=text_msg,
                        location_id=location_id
                    )
                    db.session.add(new_order)
                    
                if not commit_with_retry(db.session):
                    raise Exception("Failed to commit after several retries")
            except Exception as e:
                db.session.rollback()
                logging.info(f"DB save error: {e}")
                
            return f"Confirmation SMS sent for order {order_id}"
    except Exception as e:
        logging.error(f"Error in send_confirmation_sms_task: {e}")
        # Retry the task with exponential backoff
        retry_in = 2 ** self.request.retries
        self.retry(exc=e, countdown=retry_in)

@celery.task(name="tasks.send_order_status_update_task", bind=True, max_retries=3)
@memory_profiler
def send_order_status_update_task(self, order_id, status_message, location_id=None):
    try:
        app = create_app()
        with app.app_context():
            order = db.session.get(Order, order_id)
            if not order:
                logging.info(f"Order {order_id} not found for status update.")
                return f"Order {order_id} not found."
            
            # Extract original status from the message (if available)
            order_status = None
            for status in ["NEW", "ACCEPTED", "PREPARING", "READY", "COMPLETED", "FAILED", "REJECTED", "CANCELLED"]:
                if status in status_message:
                    order_status = status
                    break
            
            # Set location_id from order if not provided
            if not location_id and order.location_id:
                location_id = order.location_id
            
            # Get location name
            location_name = "Red Bar Sushi"
            if location_id:
                try:
                    from app.models import Location
                    location = db.session.query(Location).filter_by(id=location_id).first()
                    if location:
                        location_name = location.name
                except Exception as e:
                    logging.info(f"Error getting location name: {e}")
            
            # Create a beautifully formatted status update message
            friendly_status = {
                "NEW": "received and is being processed",
                "ACCEPTED": "accepted and being prepared",
                "PREPARING": "now being prepared in the kitchen",
                "READY": "ready for pickup! 🎉",
                "COMPLETED": "completed. Thank you for your order! 🙏",
                "FAILED": "could not be processed. Please call us",
                "REJECTED": "could not be processed. Please call us",
                "CANCELLED": "cancelled"
            }.get(order_status, "updated")
            
            # Extract order items from the stored message
            order_items = "your order"
            if order.message and "\n-" in order.message:
                try:
                    items_section = order.message.split("YOUR ORDER:")[1].split("\n\n")[0] if "YOUR ORDER:" in order.message else ""
                    if items_section:
                        order_items = items_section.strip()
                except:
                    pass
            
            # Format order time
            order_time = order.timestamp.strftime("%I:%M %p") if order.timestamp else "recently"
            
            # Create a nicely formatted status message
            formatted_status = f"""🍣 RED BAR SUSHI STATUS UPDATE 🍣

🆔 Order #{order_id[:8]}
📍 {location_name}
🕒 Placed at: {order_time}

{order_items}

📋 STATUS: {order_status if order_status else "UPDATED"}
Your order is {friendly_status}"""

            # Add special instructions based on status
            if order_status == "READY":
                formatted_status += "\n\n⏱️ Your order is ready for pickup now!"
                formatted_status += f"\n📍 Please pick up at: {location_name}"
                formatted_status += "\n📞 Call (703) 297-2632 if you need assistance"
            elif order_status == "PREPARING":
                # Estimate remaining time
                prep_time = 20 + (len(order.message.split("\n- ")) * 2)  # Estimate based on line count
                time_elapsed = (time.time() - order.timestamp.timestamp()) / 60 if order.timestamp else 0
                time_remaining = max(1, prep_time - time_elapsed)
                formatted_status += f"\n\n⏱️ Estimated to be ready in: {int(time_remaining)} minutes"
            elif order_status in ["FAILED", "REJECTED"]:
                formatted_status += "\n\n⚠️ Please call us at (703) 297-2632 regarding your order"
            
            # Add reminder for SMS commands
            formatted_status += "\n\n📱 Reply 'status' for the latest updates"
            formatted_status += "\n📱 Reply 'help' for more options"
            
            # Send SMS to customer
            try:
                message = twilio_client.messages.create(
                    body=formatted_status,
                    from_=TWILIO_PHONE_NUMBER,
                    to=order.sender,
                    status_callback=f"{os.environ.get('BASE_URL', 'https://redbarsushiai.onrender.com')}/sms_status_callback"
                )
                
                # Store the message SID in the database for tracking
                try:
                    order.sms_sid = message.sid
                    order.sms_status = "sent"
                    # Also update the order status if we know it
                    if order_status:
                        order.status = order_status
                    db.session.commit()
                    logging.info(f"Updated order {order_id} with SMS SID: {message.sid} and status: {order_status if order_status else 'unchanged'}")
                except Exception as db_err:
                    logging.error(f"Error updating order with SMS SID: {db_err}")
            except Exception as e:
                logging.info(f"Status SMS error: {e}")
                # Try alternative formatting for the phone number
                try:
                    logging.info("Trying alternative SMS approach for status update...")
                    # Remove any formatting from the phone number
                    plain_number = ''.join(filter(lambda x: x.isdigit(), order.sender))
                    if len(plain_number) == 10:  # US number without country code
                        plain_number = f"+1{plain_number}"
                    elif len(plain_number) > 10:  # Might already have country code
                        plain_number = f"+{plain_number}"
                        
                    message = twilio_client.messages.create(
                        body=formatted_status,
                        from_=TWILIO_PHONE_NUMBER,
                        to=plain_number,
                        status_callback=f"{os.environ.get('BASE_URL', 'https://redbarsushiai.onrender.com')}/sms_status_callback"
                    )
                    logging.info(f"Alternative SMS approach for status update successful! SID: {message.sid}")
                except Exception as alt_e:
                    logging.error(f"Alternative SMS approach for status update also failed: {alt_e}")

            # Send SMS notification to owner (not WhatsApp)
            try:
                # Add customer info for owner message
                owner_formatted_status = formatted_status + f"\n\nCustomer: {order.sender}"
                if order.caller_name:
                    owner_formatted_status += f" ({order.caller_name})"
                
                # Use regular SMS for owner notification
                twilio_client.messages.create(
                    body=owner_formatted_status,
                    from_=TWILIO_PHONE_NUMBER,
                    to=OWNER_PHONE_NUMBER,
                    status_callback=f"{os.environ.get('BASE_URL', 'https://redbarsushiai.onrender.com')}/sms_status_callback"
                )
                logging.info(f"Owner status notification SMS sent to {OWNER_PHONE_NUMBER}")
            except Exception as e:
                logging.info(f"Owner status notification SMS error: {e}")
                
            # Handle failed orders for reporting
            if order_status in ["FAILED", "CANCELLED", "REJECTED"]:
                try:
                    # Update order status in database
                    order.status = order_status
                    db.session.commit()
                    
                    # Additional logic for reporting failed orders could go here
                    logging.info(f"Order {order_id} marked as {order.status}")
                except Exception as e:
                    logging.info(f"Error updating failed order status: {e}")
                    
            return f"Order status update SMS sent for order {order_id}"
    except Exception as e:
        logging.error(f"Error in send_order_status_update_task: {e}")
        # Retry the task with exponential backoff
        retry_in = 2 ** self.request.retries
        self.retry(exc=e, countdown=retry_in)
