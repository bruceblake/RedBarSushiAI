# tasks.py
import logging
import stripe
import requests
from celery_app import celery, application
from app import db, twilio_client
from app.models import Order
from app.utils.helpers import log_info, commit_with_retry
import app.config as config

TWILIO_PHONE_NUMBER = config.TWILIO_NUMBER
OWNER_WHATSAPP_NUMBER = 'whatsapp:+17032972632'

@celery.task(name="tasks.send_confirmation_sms_task")
def send_confirmation_sms_task(order_id, order_message, sender, caller_name, bill_amount, order_items):
    with application.app_context():
        text_msg = order_message
        try:
            product_id = config.STRIPE_PRODUCT_ID
            stripe_amnt = int(bill_amount)
            price = stripe.Price.create(currency="usd", unit_amount=stripe_amnt, product=product_id)
            payment_link = stripe.PaymentLink.create(line_items=[{'price': price.id, 'quantity': 1}])
            text_msg += f"\nYou can pay here: {payment_link.url}"
        except Exception as e:
            logging.info(f"Stripe link error: {e}")
        try:
            twilio_client.messages.create(
                body=text_msg,
                from_=TWILIO_PHONE_NUMBER,
                to=sender
            )
        except Exception as e:
            logging.info(f"SMS error: {e}")
        try:
            from_whatsapp_number = 'whatsapp:+14155238886'
            twilio_client.messages.create(
                body=text_msg,
                from_=from_whatsapp_number,
                to=OWNER_WHATSAPP_NUMBER
            )
        except Exception as e:
            logging.info(f"WhatsApp error: {e}")
        try:
            new_order = Order(
                id=order_id,
                sender=sender,
                caller_name=caller_name,
                message=text_msg
            )
            db.session.add(new_order)
            if not commit_with_retry(db.session):
                raise Exception("Failed to commit after several retries")
        except Exception as e:
            db.session.rollback()
            logging.info(f"DB save error: {e}")
        return f"Confirmation SMS sent for order {order_id}"

@celery.task(name="tasks.send_order_status_update_task")
def send_order_status_update_task(order_id, status_message):
    with application.app_context():
        order = db.session.get(Order, order_id)
        if not order:
            logging.info(f"Order {order_id} not found for status update.")
            return f"Order {order_id} not found."
        try:
            twilio_client.messages.create(
                body=status_message,
                from_=TWILIO_PHONE_NUMBER,
                to=order.sender
            )
        except Exception as e:
            logging.info(f"Status SMS error: {e}")

        try:
            from_whatsapp_number = 'whatsapp:+14155238886'
            twilio_client.messages.create(
                body=status_message,
                from_=from_whatsapp_number,
                to=OWNER_WHATSAPP_NUMBER
            )
        except Exception as e:
            logging.info(f"WhatsApp error: {e}")
        return f"Order status update SMS sent for order {order_id}"
