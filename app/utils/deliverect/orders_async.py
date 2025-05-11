# app/utils/deliverect/orders_async.py
"""
Order management module for the Deliverect API (async version).

This module provides async functions for order creation, submission, and status tracking
through the Deliverect API.
"""

import json
import logging
import requests
import uuid
from datetime import datetime
from typing import Dict, Any, Tuple, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import db  # Keep for compatibility with synchronous code
from app.models import Location  # Import from models package to get the async version
from app.utils.deliverect.auth import get_deliverect_access_token

logger = logging.getLogger(__name__)


def build_deliverect_order(order_data, location_id=None):
    """
    Build an order payload in the format required by Deliverect.
    
    Args:
        order_data (dict): The order data from internal format
        location_id (int, optional): The location ID
        
    Returns:
        dict: The order data formatted for Deliverect
    """
    # Create a unique channel order ID (must be unique within 48 hours)
    # Format: RBS-TIMESTAMP-RANDOM
    channel_order_id = f"RBS-{int(datetime.now().timestamp())}-{uuid.uuid4().hex[:8].upper()}"
    
    # Create a display ID (shorter version for human readability)
    display_id = f"RBS-{int(datetime.now().timestamp())}"
    
    # Build the basic order structure
    deliverect_order = {
        "channelOrderId": channel_order_id,
        "channelOrderDisplayId": display_id,
        "orderType": order_data.get("order_type", 1),  # Default to pickup (1)
        "orderIsAlreadyPaid": False,  # Default to not paid, caller can override
        "decimalDigits": 2,
        "items": []
    }
    
    # Add customer info if available
    if "customer" in order_data:
        deliverect_order["customer"] = {
            "name": order_data["customer"].get("name", "Guest"),
            "phoneNumber": order_data["customer"].get("phone_number", ""),
            "email": order_data["customer"].get("email", "")
        }
    
    # Add delivery address if this is a delivery order
    if order_data.get("order_type") == 2 and "delivery_address" in order_data:
        deliverect_order["deliveryAddress"] = {
            "street": order_data["delivery_address"].get("street", ""),
            "postalCode": order_data["delivery_address"].get("postal_code", ""),
            "city": order_data["delivery_address"].get("city", ""),
            "state": order_data["delivery_address"].get("state", ""),
            "country": order_data["delivery_address"].get("country", ""),
            "extraAddressInfo": order_data["delivery_address"].get("extra_info", "")
        }
    
    # Process items
    if "items" in order_data:
        for item in order_data["items"]:
            deliverect_item = {
                "plu": item.get("plu", ""),
                "name": item.get("name", "Unknown Item"),
                "price": int(float(item.get("price", 0)) * 100),  # Convert to cents
                "quantity": item.get("quantity", 1),
                "subItems": []
            }
            
            # Process modifiers (subItems)
            if "modifiers" in item:
                for modifier in item["modifiers"]:
                    sub_item = {
                        "plu": modifier.get("plu", ""),
                        "name": modifier.get("name", "Unknown Modifier"),
                        "price": int(float(modifier.get("price_change", 0)) * 100),  # Convert to cents
                        "quantity": modifier.get("quantity", 1)
                    }
                    deliverect_item["subItems"].append(sub_item)
            
            deliverect_order["items"].append(deliverect_item)
    
    # Add payment information
    payment_amount = sum(
        item.get("price", 0) * item.get("quantity", 1) 
        for item in order_data.get("items", [])
    )
    
    # Convert to cents
    payment_amount_cents = int(payment_amount * 100)
    
    deliverect_order["payment"] = {
        "amount": payment_amount_cents,
        "type": order_data.get("payment_type", 1)  # Default to cash (1)
    }
    
    # Add estimated times if available
    if "estimated_time" in order_data:
        if order_data.get("order_type") == 1:  # Pickup
            deliverect_order["pickupTime"] = order_data["estimated_time"]
        elif order_data.get("order_type") == 2:  # Delivery
            deliverect_order["deliveryTime"] = order_data["estimated_time"]
    
    # Add notes if available
    if "notes" in order_data:
        deliverect_order["note"] = order_data["notes"]
    
    logger.info(f"Built Deliverect order: {json.dumps(deliverect_order)}")
    return deliverect_order


async def send_order_to_deliverect_async(order_data: Dict[str, Any], db: AsyncSession, location_id: Optional[str] = None) -> Tuple[bool, Dict[str, Any], Optional[int]]:
    """
    Send a prepared order to the Deliverect API (async version).
    
    Args:
        order_data (dict): The order data payload formatted according to Deliverect specifications
        db (AsyncSession): SQLAlchemy async database session
        location_id (str, optional): The location ID to use for the order. If not provided,
                                  the default location will be used
                                    
    Returns:
        tuple: (success, response_data, status_code)
            - success: Boolean indicating if the API call was successful
            - response_data: Data returned from the API or error message
            - status_code: HTTP status code or None if request failed
    """
    logger.info(f"Sending order to Deliverect: {json.dumps(order_data)}")
    
    try:
        # Get location details if location_id is provided
        channel_link_id = None
        channel_name = None
        
        if location_id:
            # Use SQLAlchemy 2.0 style select with async execution
            stmt = select(Location).where(Location.id == location_id)
            result = await db.execute(stmt)
            location = result.scalar_one_or_none()
            
            if location:
                channel_link_id = location.deliverect_channel_link_id
                channel_name = location.deliverect_channel_name
                logger.info(f"Using location {location_id} with channel link ID: {channel_link_id}")
            else:
                logger.error(f"Location not found with ID: {location_id}")
                return False, {"error": "Location not found"}, None
        else:
            # Get the first available location
            stmt = select(Location).limit(1)
            result = await db.execute(stmt)
            location = result.scalar_one_or_none()
            
            if location:
                channel_link_id = location.deliverect_channel_link_id
                channel_name = location.deliverect_channel_name
                logger.info(f"Using default location with channel link ID: {channel_link_id}")
            else:
                logger.error("No locations configured in the system")
                return False, {"error": "No locations configured"}, None
        
        # Ensure we have a channel name and link ID
        if not channel_name or not channel_link_id:
            logger.error("Missing channel name or channel link ID")
            return False, {"error": "Missing channel configuration"}, None
            
        # Get access token for the API call
        token_response = get_deliverect_access_token(channel_link_id)
        if not token_response["success"]:
            logger.error(f"Failed to get access token: {token_response['error']}")
            return False, {"error": f"Authentication failed: {token_response['error']}"}, None
            
        access_token = token_response["token"]
        
        # Build the API URL
        api_url = f"https://api.deliverect.com/{channel_name}/order/{channel_link_id}"
        
        # Set up the headers
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # Send the request to Deliverect
        logger.info(f"Sending order to Deliverect API: {api_url}")
        
        # Note: requests.post is still synchronous here
        # For fully async operation, this should be replaced with an async HTTP client like aiohttp or httpx
        response = requests.post(
            api_url,
            headers=headers,
            json=order_data,
            timeout=30  # 30 second timeout for order submission
        )
        
        status_code = response.status_code
        logger.info(f"Deliverect API response status: {status_code}")
        
        # Parse the response
        try:
            response_data = response.json()
        except ValueError:
            response_data = {"text": response.text}
        
        # Check if the request was successful (201 = Created)
        if status_code == 201:
            logger.info(f"Order successfully sent to Deliverect: {response_data}")
            return True, response_data, status_code
        else:
            logger.error(f"Failed to send order to Deliverect: {response_data}")
            return False, response_data, status_code
            
    except requests.RequestException as e:
        logger.error(f"Request error when sending order to Deliverect: {str(e)}")
        return False, {"error": f"Request failed: {str(e)}"}, None
    except Exception as e:
        logger.error(f"Unexpected error when sending order to Deliverect: {str(e)}")
        return False, {"error": f"Unexpected error: {str(e)}"}, None


async def get_order_status_async(channel_order_id: str, db: AsyncSession, location_id: Optional[str] = None) -> Tuple[bool, Dict[str, Any], Optional[int]]:
    """
    Get the status of an order from the Deliverect API (async version).
    
    Args:
        channel_order_id (str): The unique channel order ID used when the order was created
        db (AsyncSession): SQLAlchemy async database session
        location_id (str, optional): The location ID to use for the status check. 
                                   If not provided, the default location will be used
                                    
    Returns:
        tuple: (success, status_data, status_code)
            - success: Boolean indicating if the API call was successful
            - status_data: Data returned from the API or error message
            - status_code: HTTP status code or None if request failed
    """
    logger.info(f"Checking order status for channel order ID: {channel_order_id}")
    
    try:
        # Get location details if location_id is provided
        channel_link_id = None
        channel_name = None
        
        if location_id:
            # Use SQLAlchemy 2.0 style select with async execution
            stmt = select(Location).where(Location.id == location_id)
            result = await db.execute(stmt)
            location = result.scalar_one_or_none()
            
            if location:
                channel_link_id = location.deliverect_channel_link_id
                channel_name = location.deliverect_channel_name
                logger.info(f"Using location {location_id} with channel link ID: {channel_link_id}")
            else:
                logger.error(f"Location not found with ID: {location_id}")
                return False, {"error": "Location not found"}, None
        else:
            # Get the first available location
            stmt = select(Location).limit(1)
            result = await db.execute(stmt)
            location = result.scalar_one_or_none()
            
            if location:
                channel_link_id = location.deliverect_channel_link_id
                channel_name = location.deliverect_channel_name
                logger.info(f"Using default location with channel link ID: {channel_link_id}")
            else:
                logger.error("No locations configured in the system")
                return False, {"error": "No locations configured"}, None
        
        # Ensure we have a channel name and link ID
        if not channel_name or not channel_link_id:
            logger.error("Missing channel name or channel link ID")
            return False, {"error": "Missing channel configuration"}, None
            
        # Get access token for the API call
        token_response = get_deliverect_access_token(channel_link_id)
        if not token_response["success"]:
            logger.error(f"Failed to get access token: {token_response['error']}")
            return False, {"error": f"Authentication failed: {token_response['error']}"}, None
            
        access_token = token_response["token"]
        
        # Build the API URL
        api_url = f"https://api.deliverect.com/{channel_name}/order/{channel_link_id}/{channel_order_id}"
        
        # Set up the headers
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # Send the request to Deliverect
        logger.info(f"Checking order status from Deliverect API: {api_url}")
        
        # Note: requests.get is still synchronous here
        # For fully async operation, this should be replaced with an async HTTP client like aiohttp or httpx
        response = requests.get(
            api_url,
            headers=headers,
            timeout=15  # 15 second timeout for status check
        )
        
        status_code = response.status_code
        logger.info(f"Deliverect API response status: {status_code}")
        
        # Parse the response
        try:
            response_data = response.json()
        except ValueError:
            response_data = {"text": response.text}
        
        # Check if the request was successful (200 = OK)
        if status_code == 200:
            logger.info(f"Order status successfully retrieved from Deliverect: {response_data}")
            return True, response_data, status_code
        else:
            logger.error(f"Failed to get order status from Deliverect: {response_data}")
            return False, response_data, status_code
            
    except requests.RequestException as e:
        logger.error(f"Request error when checking order status from Deliverect: {str(e)}")
        return False, {"error": f"Request failed: {str(e)}"}, None
    except Exception as e:
        logger.error(f"Unexpected error when checking order status from Deliverect: {str(e)}")
        return False, {"error": f"Unexpected error: {str(e)}"}, None


def generate_order_id():
    """
    Generate a unique order ID for Deliverect.
    
    Returns:
        tuple: (channel_order_id, display_id)
            - channel_order_id: Unique order ID for Deliverect (must be unique within 48 hours)
            - display_id: Shorter version for human readability
    """
    # Create a unique channel order ID (must be unique within 48 hours)
    # Format: RBS-TIMESTAMP-RANDOM
    timestamp = int(datetime.now().timestamp())
    channel_order_id = f"RBS-{timestamp}-{uuid.uuid4().hex[:8].upper()}"
    
    # Create a display ID (shorter version for human readability)
    display_id = f"RBS-{timestamp}"
    
    return channel_order_id, display_id


async def process_order_status_update_async(webhook_data: Dict[str, Any], db: AsyncSession, location_id: Optional[str] = None) -> Tuple[bool, Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    Process an order status update webhook from Deliverect (async version).
    
    This function handles the webhook payload sent by Deliverect when an order's status changes.
    The webhook format follows the documentation at:
    https://developers.deliverect.com/reference/post-order-status-update
    
    Args:
        webhook_data (dict): The webhook payload from Deliverect
        db (AsyncSession): SQLAlchemy async database session
        location_id (str, optional): The location ID to associate with this update
                                    
    Returns:
        tuple: (success, response, order_info)
            - success: Boolean indicating if the webhook was processed successfully
            - response: Dictionary with message and status for response to Deliverect
            - order_info: Dictionary with extracted order information if successful
    """
    logger.info(f"Processing order status update webhook: {json.dumps(webhook_data)}")
    
    try:
        # Validate the webhook structure
        if not isinstance(webhook_data, dict):
            logger.error("Invalid webhook data format - not a dictionary")
            return False, {"message": "Invalid data format", "status": 400}, None
        
        # Check for required fields
        required_fields = ["channelOrderId", "status"]
        missing_fields = [field for field in required_fields if field not in webhook_data]
        
        if missing_fields:
            logger.error(f"Missing required fields in webhook: {missing_fields}")
            return False, {"message": f"Missing required fields: {', '.join(missing_fields)}", "status": 400}, None
        
        # Extract the key information
        channel_order_id = webhook_data["channelOrderId"]
        status = webhook_data["status"]
        
        logger.info(f"Order status update received - Channel Order ID: {channel_order_id}, Status: {status}")
        
        # Extract additional information if available
        order_info = {
            "channel_order_id": channel_order_id,
            "status": status,
            "timestamp": datetime.now().isoformat()
        }
        
        # Add any available additional fields
        additional_fields = [
            "rejectionReason", "orderReference", "estimatedDeliveryTime", 
            "estimatedPickupTime", "note", "actualDeliveryTime", 
            "actualPickupTime", "courierName", "courierPhone"
        ]
        
        for field in additional_fields:
            if field in webhook_data:
                # Convert camelCase to snake_case for our internal format
                snake_field = ''.join(['_' + c.lower() if c.isupper() else c for c in field]).lstrip('_')
                order_info[snake_field] = webhook_data[field]
        
        # Find the order in the database using SQLAlchemy 2.0 style select with async execution
        from app.models import Order
        
        stmt = select(Order).where(Order.deliverect_channel_order_id == channel_order_id)
        result = await db.execute(stmt)
        order = result.scalar_one_or_none()
        
        if not order:
            logger.warning(f"Order not found with channel order ID: {channel_order_id}")
            # We still return success because Deliverect expects a successful response,
            # even if we can't find the order in our system
            return True, {"message": "Acknowledged, but order not found in system", "status": 200}, order_info
        
        # Update the order status
        old_status = order.status
        order.status = status
        
        # Update any additional fields
        if "estimated_delivery_time" in order_info:
            try:
                order.estimated_time = datetime.fromisoformat(order_info["estimated_delivery_time"].replace('Z', '+00:00'))
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse estimated delivery time: {e}")
        
        if "estimated_pickup_time" in order_info and not "estimated_delivery_time" in order_info:
            try:
                order.estimated_time = datetime.fromisoformat(order_info["estimated_pickup_time"].replace('Z', '+00:00'))
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse estimated pickup time: {e}")
        
        if "note" in order_info:
            if order.notes:
                order.notes = f"{order.notes}\nUpdate: {order_info['note']}"
            else:
                order.notes = order_info["note"]
        
        # Save the changes
        order.updated_at = datetime.now()
        await db.commit()
        
        logger.info(f"Order status updated from {old_status} to {status} for order {channel_order_id}")
        
        # Trigger additional processing based on status change
        if old_status != status:
            # This would be a good place to trigger notifications or other actions
            # For example, sending SMS updates to the customer
            from app.tasks import send_status_update_notification
            # Async task to send notification
            send_status_update_notification.delay(order.id)
            
            logger.info(f"Triggered status update notification for order {channel_order_id}")
        
        return True, {"message": "Order status updated successfully", "status": 200}, order_info
        
    except Exception as e:
        logger.error(f"Error processing order status update webhook: {str(e)}")
        # We still return a 200 status to Deliverect to acknowledge receipt
        # This prevents them from retrying, which is usually preferred
        return False, {"message": "Webhook received, but processing failed", "status": 200}, None