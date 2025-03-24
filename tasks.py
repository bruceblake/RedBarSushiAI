# tasks.py
import logging
import stripe
import requests
from app import db, twilio_client, create_app
from app.models import Order
from app.utils.helpers import log_info, commit_with_retry
import app.config as config

# Import celery instance after it's fully defined
from celery_app import celery

TWILIO_PHONE_NUMBER = config.TWILIO_NUMBER
OWNER_WHATSAPP_NUMBER = 'whatsapp:+17032972632'

@celery.task(name="tasks.sync_menu_references")
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

@celery.task(name="tasks.send_confirmation_sms_task")
def send_confirmation_sms_task(order_id, order_message, sender, caller_name, bill_amount, order_items, location_id=None):
    app = create_app()
    with app.app_context():
        text_msg = order_message
        
        # Add location to the message if provided
        location_prefix = ""
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
        
        # Add location prefix to the message
        if location_prefix and "location" not in text_msg:
            text_msg = text_msg.replace("Your order is", f"Your order{location_prefix} is")
            text_msg = text_msg.replace("You ordered:", f"You ordered from{location_prefix}:")
        
        # Create payment link
        try:
            product_id = config.STRIPE_PRODUCT_ID
            stripe_amnt = int(bill_amount)
            price = stripe.Price.create(currency="usd", unit_amount=stripe_amnt, product=product_id)
            payment_link = stripe.PaymentLink.create(line_items=[{'price': price.id, 'quantity': 1}])
            text_msg += f"\nYou can pay here: {payment_link.url}"
        except Exception as e:
            logging.info(f"Stripe link error: {e}")
        
        # Send SMS to customer
        try:
            twilio_client.messages.create(
                body=text_msg,
                from_=TWILIO_PHONE_NUMBER,
                to=sender
            )
        except Exception as e:
            logging.info(f"SMS error: {e}")
        
        # Send WhatsApp notification to owner
        try:
            # Include location in owner notification
            owner_msg = text_msg
            if location_id and "location" not in owner_msg:
                owner_msg = f"New order from{location_prefix}:\n{owner_msg}"
                
            from_whatsapp_number = 'whatsapp:+14155238886'
            twilio_client.messages.create(
                body=owner_msg,
                from_=from_whatsapp_number,
                to=OWNER_WHATSAPP_NUMBER
            )
        except Exception as e:
            logging.info(f"WhatsApp error: {e}")
        
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

@celery.task(name="tasks.send_order_status_update_task")
def send_order_status_update_task(order_id, status_message, location_id=None):
    app = create_app()
    with app.app_context():
        order = db.session.get(Order, order_id)
        if not order:
            logging.info(f"Order {order_id} not found for status update.")
            return f"Order {order_id} not found."
        
        # Set location_id from order if not provided
        if not location_id and order.location_id:
            location_id = order.location_id
        
        # Add location to the message if not already included
        if location_id and "location" not in status_message:
            try:
                from app.models import Location
                location = db.session.query(Location).filter_by(id=location_id).first()
                if location:
                    location_name = location.name
                    status_message = status_message.replace(f"Your order ({order_id})", 
                                                         f"Your order ({order_id}) at our {location_name}")
                else:
                    status_message = status_message.replace(f"Your order ({order_id})", 
                                                         f"Your order ({order_id}) at our {location_id} location")
            except Exception as e:
                logging.info(f"Error getting location name: {e}")
        
        # Send SMS to customer
        try:
            twilio_client.messages.create(
                body=status_message,
                from_=TWILIO_PHONE_NUMBER,
                to=order.sender
            )
        except Exception as e:
            logging.info(f"Status SMS error: {e}")

        # Send WhatsApp notification to owner
        try:
            from_whatsapp_number = 'whatsapp:+14155238886'
            twilio_client.messages.create(
                body=status_message,
                from_=from_whatsapp_number,
                to=OWNER_WHATSAPP_NUMBER
            )
        except Exception as e:
            logging.info(f"WhatsApp error: {e}")
            
        # Handle failed orders for reporting
        if "FAILED" in status_message or "CANCELLED" in status_message:
            try:
                # Update order status in database
                order.status = "FAILED" if "FAILED" in status_message else "CANCELLED"
                db.session.commit()
                
                # Additional logic for reporting failed orders could go here
                logging.info(f"Order {order_id} marked as {order.status}")
            except Exception as e:
                logging.info(f"Error updating failed order status: {e}")
                
        return f"Order status update SMS sent for order {order_id}"
