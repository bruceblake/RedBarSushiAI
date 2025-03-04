# app/utils/deliverect.py
import time
import requests
import logging
from app.config import DELIVERECT_CLIENT_ID, DELIVERECT_CLIENT_SECRET

logger = logging.getLogger(__name__)

deliverect_token = None
token_expiry = 0


def get_deliverect_token():
    token_url = "https://api.staging.deliverect.com/oauth/token"
    payload = {
        "grant_type": "token",
        "client_id": DELIVERECT_CLIENT_ID,
        "client_secret": DELIVERECT_CLIENT_SECRET,
        "audience": "https://api.staging.deliverect.com"
    }
    headers = {"Accept": "application/json",
               "Content-Type": "application/json"}
    try:
        logger.info("Fetching Deliverect token...")
        response = requests.post(token_url, json=payload, headers=headers)
        response.raise_for_status()
        token = response.json()
        logger.info("Deliverect token fetched successfully.")
        return token
    except Exception as e:
        logger.error(f"Error fetching Deliverect token: {e}")
        raise


def ensure_deliverect_token():
    global deliverect_token, token_expiry
    if time.time() >= token_expiry:
        logger.info("Deliverect token expired, refreshing...")
        deliverect_token = get_deliverect_token()
        token_expiry = time.time() + deliverect_token.get('expires_in', 3600)


def get_deliverect_headers():
    ensure_deliverect_token()
    return {
        "Authorization": f"Bearer {deliverect_token['access_token']}",
        "Content-Type": "application/json"
    }


def build_deliverect_order(sender, caller_name, order_items, total_price, order_id):
    """
    Build the order payload for the Deliverect API.

    Parameters:
      sender (str): The customer's phone number.
      caller_name (str): The customer's name.
      order_items (list): List of dictionaries for each ordered item.
      total_price (float): The total price (base) of the order.
      order_id (str): A unique identifier for the order.

    Returns:
      dict: The JSON payload ready to be sent to Deliverect.
    """
    # Define sales tax rate and calculate tax
    sales_tax = 0.06
    total_with_tax = total_price + (total_price * sales_tax)

    order_payload = {
        "orderId": str(order_id),
        "customer": {
            "name": caller_name,
            "phone": sender
        },
        "items": [],
        "total": int(round(total_price * 100)),  # Convert to cents with proper rounding
        "status": "NEW",
        "channelOrderId": str(order_id),
        "orderType": 1,
        "channelOrderDisplayId": str(order_id),
        "payment": {
            "amount": int(round(total_with_tax * 100)),  # Round properly
            "type": 0  # Assuming 0 means unpaid
        },
        "deliveryIsAsap": False,
        "orderIsAlreadyPaid": False,
        "decimalDigits": 2,
        "courier": "restaurant",
        "taxes": [
            {
                "name": "taxes",
                "total": int(round(total_price * sales_tax * 100))  # Round properly
            }
        ]
    }

    # Process each order item
    for item in order_items:
        del_item = {
            "name": item["name"],
            # Unique product identifier
            "plu": item.get("reference_handler", ""),
            "quantity": item.get("quantity", 1),
            "price": int(round(item.get("price", 0.0) * 100)),  # Round properly
            "subItems": []
        }
        # Process any modifiers for this item
        for mod in item.get("modifier", []):
            sub_item = {
                "name": mod.get("name", "").lower(),
                "plu": mod.get("plu", "UNKNOWN-PLU"),
                "quantity": mod.get("quantity", 1),
                "price": int(round(mod.get("price", 0.0) * 100))  # Round properly
            }
            del_item["subItems"].append(sub_item)
        order_payload["items"].append(del_item)

    return order_payload