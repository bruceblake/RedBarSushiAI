# app/utils/deliverect/locations.py
"""
Location management module for the Deliverect API.

This module provides functions for location registration and management
for Deliverect integration.
"""

import json
import logging
from datetime import datetime
from app import db
from app.models.location import Location
from app.config import BASE_URL

logger = logging.getLogger(__name__)


def register_new_location(location_data):
    """
    Register a new location with Deliverect settings.
    
    Args:
        location_data (dict): Location data with Deliverect configuration
        
    Returns:
        tuple: (success, message, location_id)
            - success: Boolean indicating if registration was successful
            - message: Status message
            - location_id: ID of the registered location if successful
    """
    logger.info(f"Registering new location: {json.dumps(location_data)}")
    
    try:
        # Validate required fields
        required_fields = ["name", "deliverect_channel_name", "deliverect_channel_link_id"]
        missing_fields = [field for field in required_fields if field not in location_data]
        
        if missing_fields:
            error_msg = f"Missing required fields: {', '.join(missing_fields)}"
            logger.error(error_msg)
            return False, error_msg, None
        
        # Check if location with the same channel link ID already exists
        existing = Location.query.filter_by(
            deliverect_channel_link_id=location_data["deliverect_channel_link_id"]
        ).first()
        
        if existing:
            logger.warning(f"Location with channel link ID {location_data['deliverect_channel_link_id']} already exists")
            return False, "Location with this channel link ID already exists", None
        
        # Create the location
        location = Location(
            name=location_data["name"],
            deliverect_channel_name=location_data["deliverect_channel_name"],
            deliverect_channel_link_id=location_data["deliverect_channel_link_id"],
            webhook_base=location_data.get("webhook_base", BASE_URL),
            address=location_data.get("address", ""),
            phone=location_data.get("phone", ""),
            email=location_data.get("email", ""),
            is_active=location_data.get("is_active", True),
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # Add additional fields if provided
        for field in ["open_time", "close_time", "timezone", "status", "notes"]:
            if field in location_data:
                setattr(location, field, location_data[field])
        
        # Save to database
        db.session.add(location)
        db.session.commit()
        
        logger.info(f"Successfully registered location: {location.id}")
        return True, "Location registered successfully", location.id
        
    except Exception as e:
        logger.error(f"Error registering location: {str(e)}")
        return False, f"Error registering location: {str(e)}", None


def update_location_status(location_id, status):
    """
    Update a location's status.
    
    Args:
        location_id (int): The location ID
        status (str): The new status
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    logger.info(f"Updating location {location_id} status to '{status}'")
    
    try:
        # Get the location
        location = Location.query.filter_by(id=location_id).first()
        
        if not location:
            logger.error(f"Location not found with ID: {location_id}")
            return False
        
        # Update the status
        location.status = status
        location.updated_at = datetime.now()
        db.session.commit()
        
        logger.info(f"Location {location_id} status updated to '{status}'")
        return True
    except Exception as e:
        logger.error(f"Error updating location status: {e}")
        # No need to rollback when using direct SQL
        return False


def get_location_webhook_urls(location_id):
    """
    Get webhook URLs for a specific location.
    
    Args:
        location_id: The unique location identifier
    
    Returns:
        dict: Dictionary of webhook URLs matching Deliverect's expected format
    """
    try:
        logger.info(f"Generating webhook URLs for location {location_id} with BASE_URL: {BASE_URL}")
        
        location = Location.query.filter_by(id=location_id).first()
        if not location or not location.webhook_base:
            # For non-existent locations, use the regular endpoints without the location prefix
            # THIS IS THE STANDARD FORMAT EXPECTED BY DELIVERECT
            response = {
                "statusUpdateURL": f"{BASE_URL}/order_status",
                "menuUpdateURL": f"{BASE_URL}/menu_update",
                "snoozeUnsnoozeURL": f"{BASE_URL}/snoozeUnsnooze",
                "busyModeURL": f"{BASE_URL}/busy_mode",
                "updatePrepTimeURL": f"{BASE_URL}/updatePrepTime",
                "courierUpdateURL": f"{BASE_URL}/courierUpdate",
                "paymentUpdateURL": f"{BASE_URL}/payment_update",
            }
            logger.info(f"Generated standard webhook URLs: {json.dumps(response)}")
            return response
        else:
            # For existing locations, use the location-specific endpoints
            # NOTE: Some Deliverect implementations may not accept these prefixed URLs
            urls = {
                "statusUpdateURL": f"{BASE_URL}/location/{location_id}/order_status",
                "menuUpdateURL": f"{BASE_URL}/location/{location_id}/menu_update",
                "snoozeUnsnoozeURL": f"{BASE_URL}/location/{location_id}/snoozeUnsnooze",
                "busyModeURL": f"{BASE_URL}/location/{location_id}/busy_mode",
                "updatePrepTimeURL": f"{BASE_URL}/location/{location_id}/updatePrepTime",
                "courierUpdateURL": f"{BASE_URL}/location/{location_id}/courierUpdate",
                "paymentUpdateURL": f"{BASE_URL}/location/{location_id}/payment_update",
            }
            logger.info(f"Generated location-specific webhook URLs: {json.dumps(urls)}")
            return urls
    except Exception as e:
        logger.error(f"Error generating location webhook URLs: {e}")
        
        # Fall back to default URLs - most compatible option
        logger.info(f"Falling back to default webhook URLs with BASE_URL: {BASE_URL}")
        return {
            "statusUpdateURL": f"{BASE_URL}/order_status",
            "menuUpdateURL": f"{BASE_URL}/menu_update",
            "snoozeUnsnoozeURL": f"{BASE_URL}/snoozeUnsnooze",
            "busyModeURL": f"{BASE_URL}/busy_mode",
            "updatePrepTimeURL": f"{BASE_URL}/updatePrepTime",
            "courierUpdateURL": f"{BASE_URL}/courierUpdate",
            "paymentUpdateURL": f"{BASE_URL}/payment_update",
        }