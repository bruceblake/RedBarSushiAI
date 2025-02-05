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
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
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
