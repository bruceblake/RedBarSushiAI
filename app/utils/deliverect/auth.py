# app/utils/deliverect/auth.py
"""
Authentication module for the Deliverect API.

This module provides functions for authenticating with the Deliverect API,
obtaining and managing access tokens.
"""

import time
import requests
import logging
from app.config import DELIVERECT_CLIENT_ID, DELIVERECT_CLIENT_SECRET

logger = logging.getLogger(__name__)

# Store tokens by location for multi-location support
deliverect_tokens = {}
token_expiries = {}


def get_deliverect_access_token(channel_link_id):
    """
    Get an access token for the Deliverect API. 
    Will retrieve from cache if valid, or get a new one if expired.
    
    Args:
        channel_link_id (str): The channel link ID to use for the token
        
    Returns:
        dict: Result with token info
            - success: Boolean indicating if token retrieval was successful
            - token: The access token if successful
            - error: Error message if not successful
    """
    # Check if we have a valid cached token for this location
    current_time = int(time.time())
    
    if (
        channel_link_id in deliverect_tokens
        and channel_link_id in token_expiries
        and token_expiries[channel_link_id] > current_time
    ):
        # We have a valid cached token
        logger.debug(f"Using cached Deliverect token for channel link {channel_link_id}")
        return {
            "success": True,
            "token": deliverect_tokens[channel_link_id]
        }
    
    # No valid cached token, need to get a new one
    logger.info(f"Getting new Deliverect access token for channel link {channel_link_id}")
    
    try:
        # Get the credentials for authentication
        client_id = DELIVERECT_CLIENT_ID
        client_secret = DELIVERECT_CLIENT_SECRET
        
        if not client_id or not client_secret:
            logger.error("Missing Deliverect API credentials")
            return {
                "success": False,
                "error": "Missing API credentials"
            }
        
        # Build the token request
        auth_url = "https://identity.deliverect.com/connect/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "menu.manage orders.create orders.manage channels.manage channels.read items.manage items.read"
        }
        
        # Make the authentication request
        response = requests.post(
            auth_url,
            headers=headers,
            data=data,
            timeout=10  # 10 second timeout for authentication
        )
        
        # Check if the request was successful
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get("access_token")
            expires_in = token_data.get("expires_in", 3600)  # Default to 1 hour if not specified
            
            if not access_token:
                logger.error("No access token in response")
                return {
                    "success": False,
                    "error": "No access token in response"
                }
            
            # Cache the token with expiry time (subtract 60 seconds for safety)
            deliverect_tokens[channel_link_id] = access_token
            token_expiries[channel_link_id] = current_time + expires_in - 60
            
            logger.info(f"Successfully obtained new Deliverect access token for channel link {channel_link_id}")
            return {
                "success": True,
                "token": access_token
            }
        else:
            error_msg = f"Failed to get access token: {response.status_code} - {response.text}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
    
    except requests.RequestException as e:
        error_msg = f"Request exception when getting Deliverect token: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }
    except Exception as e:
        error_msg = f"Unexpected error when getting Deliverect token: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }


def get_deliverect_headers(channel_link_id):
    """
    Get the necessary headers for Deliverect API requests, including authentication.
    
    Args:
        channel_link_id (str): The channel link ID to use for the token
        
    Returns:
        dict: Headers for Deliverect API requests or None if authentication fails
    """
    # Get an access token
    token_response = get_deliverect_access_token(channel_link_id)
    
    if not token_response.get("success"):
        logger.error(f"Failed to get headers: {token_response.get('error')}")
        return None
    
    # Construct and return the headers
    return {
        "Authorization": f"Bearer {token_response['token']}",
        "Content-Type": "application/json"
    }