# app/utils/deliverect/locations_async.py
"""
Location management module for the Deliverect API (async version).

This module provides async functions for location registration and management
for Deliverect integration.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Location
from app.config import settings

logger = logging.getLogger(__name__)


async def register_new_location_async(db: AsyncSession, location_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Register a new location with Deliverect (async version).
    
    Args:
        db: AsyncSession for database access
        location_data: Dictionary containing location registration data
        
    Returns:
        Dict with registration results and status information
    """
    logger.info(f"Registering new location: {location_data.get('name')}")
    
    try:
        # Create a new location object
        location = Location(
            id=location_data.get('id') or str(uuid.uuid4()),
            name=location_data.get('name', 'New Location'),
            status='registered',
            webhook_base=location_data.get('webhook_base', ''),
            api_key=location_data.get('api_key', ''),
        )
        
        # Add properties from location_data
        if hasattr(location, 'properties'):
            location.properties = {
                'deliverect_channel_link_id': location_data.get('channel_link_id', ''),
                'deliverect_channel_name': location_data.get('channel_name', 'redbarsushi'),
                'deliverect_account_id': location_data.get('account_id', ''),
                'registration_date': datetime.now().isoformat(),
            }
        
        # Add to database
        db.add(location)
        await db.commit()
        await db.refresh(location)
        
        logger.info(f"Location {location.name} registered successfully with ID: {location.id}")
        
        return {
            'success': True,
            'location_id': location.id,
            'message': f"Location {location.name} registered successfully"
        }
        
    except Exception as e:
        logger.error(f"Error registering location: {str(e)}")
        await db.rollback()
        return {
            'success': False,
            'message': f"Failed to register location: {str(e)}"
        }


async def update_location_status_async(db: AsyncSession, location_id: str, status: str) -> Dict[str, Any]:
    """
    Update the status of a location (async version).
    
    Args:
        db: AsyncSession for database access
        location_id: ID of the location to update
        status: New status value
        
    Returns:
        Dict with update results and status information
    """
    logger.info(f"Updating location {location_id} status to: {status}")
    
    try:
        # Find the location in the database
        stmt = select(Location).where(Location.id == location_id)
        result = await db.execute(stmt)
        location = result.scalar_one_or_none()
        
        if not location:
            logger.error(f"Location not found with ID: {location_id}")
            return {
                'success': False,
                'message': f"Location not found with ID: {location_id}"
            }
        
        # Update the status
        location.status = status
        location.updated_at = datetime.now()
        
        # Save changes
        await db.commit()
        
        logger.info(f"Location {location.name} status updated to {status}")
        
        return {
            'success': True,
            'location_id': location.id,
            'status': status,
            'message': f"Location {location.name} status updated to {status}"
        }
        
    except Exception as e:
        logger.error(f"Error updating location status: {str(e)}")
        await db.rollback()
        return {
            'success': False,
            'message': f"Failed to update location status: {str(e)}"
        }


async def get_location_webhook_urls_async(db: AsyncSession, location_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Get webhook URLs for all active locations (async version).
    
    Args:
        db: AsyncSession for database access
        location_id: Optional location ID to get webhooks for a specific location
        
    Returns:
        Dict with webhook URLs organized by location
    """
    logger.info("Getting webhook URLs for locations")
    
    try:
        # Query for locations
        stmt = select(Location)
        if location_id:
            stmt = stmt.where(Location.id == location_id)
        else:
            stmt = stmt.where(Location.status == 'active')
            
        result = await db.execute(stmt)
        locations = result.scalars().all()
        
        # Build webhook data
        webhook_data = {
            'webhook_urls': [],
            'count': 0
        }
        
        for location in locations:
            if location.webhook_base:
                # Standard webhook endpoints
                order_status_webhook = f"{location.webhook_base}/webhooks/deliverect/status"
                
                webhook_data['webhook_urls'].append({
                    'location_id': location.id,
                    'location_name': location.name,
                    'order_status_webhook': order_status_webhook
                })
        
        webhook_data['count'] = len(webhook_data['webhook_urls'])
        
        logger.info(f"Found {webhook_data['count']} webhook URLs")
        
        return webhook_data
        
    except Exception as e:
        logger.error(f"Error getting webhook URLs: {str(e)}")
        return {
            'webhook_urls': [],
            'count': 0,
            'error': str(e)
        }