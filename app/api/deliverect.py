"""
Deliverect integration endpoints.

This module handles the channel registration and webhook management
for Deliverect integration following their official API documentation.
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status, Request, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class ChannelRegistrationRequest(BaseModel):
    """Deliverect channel registration request model."""
    status: str = Field(..., description="register, active, or inactive")
    channelLocationId: str = Field(..., description="Unique ID of merchant in channel platform")
    channelLinkId: str = Field(..., description="Channel link ID from Deliverect")
    locationId: str = Field(..., description="Location ID from Deliverect")
    channelLinkName: str = Field(..., description="Channel name displayed in Deliverect")


class ChannelRegistrationResponse(BaseModel):
    """Response model for channel registration."""
    statusUpdateURL: str
    menuUpdateURL: str
    snoozeUnsnoozeURL: str
    busyModeURL: str
    updatePrepTimeURL: str
    courierUpdateURL: str
    paymentUpdateURL: str
    menuUrl: str


@router.post("/register", response_model=ChannelRegistrationResponse)
async def register_channel(
    request: ChannelRegistrationRequest,
    req: Request,
    db: AsyncSession = Depends(get_db)
) -> ChannelRegistrationResponse:
    """
    Handle Deliverect channel registration.
    
    This endpoint is called by Deliverect in three scenarios:
    - register: New store/location establishing connection
    - active: Store ready to receive orders
    - inactive: Store stopping order reception
    """
    try:
        logger.info(f"Received channel registration request: status={request.status}, "
                   f"channelLinkId={request.channelLinkId}, locationId={request.locationId}")
        
        # Get the base URL from the request
        # In production, this should come from settings or environment
        base_url = str(req.base_url).rstrip('/')
        
        # For development with ngrok or similar, check if we have a public URL configured
        if hasattr(settings, 'PUBLIC_WEBHOOK_URL') and settings.PUBLIC_WEBHOOK_URL:
            base_url = settings.PUBLIC_WEBHOOK_URL.rstrip('/')
        
        # Store the registration details in database if needed
        # TODO: Implement database storage for channel registrations
        
        if request.status == "register":
            logger.info(f"Registering new channel: {request.channelLinkName}")
            # TODO: Create channel record in database
            
        elif request.status == "active":
            logger.info(f"Activating channel: {request.channelLinkId}")
            # TODO: Update channel status to active
            
        elif request.status == "inactive":
            logger.info(f"Deactivating channel: {request.channelLinkId}")
            # TODO: Update channel status to inactive
            
        else:
            logger.warning(f"Unknown registration status: {request.status}")
        
        # Return the webhook URLs that Deliverect will use
        response = ChannelRegistrationResponse(
            statusUpdateURL=f"{base_url}/api/deliverect/order/status",
            menuUpdateURL=f"{base_url}/api/deliverect/menu/update",
            snoozeUnsnoozeURL=f"{base_url}/api/deliverect/menu/snooze",
            busyModeURL=f"{base_url}/api/deliverect/location/busy",
            updatePrepTimeURL=f"{base_url}/api/deliverect/location/preptime",
            courierUpdateURL=f"{base_url}/api/deliverect/order/courier",
            paymentUpdateURL=f"{base_url}/api/deliverect/order/payment",
            menuUrl=f"{base_url}"  # Store URL, can be customized
        )
        
        logger.info(f"Returning webhook URLs: {response.dict()}")
        
        return response
        
    except Exception as e:
        logger.error(f"Error during channel registration: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Channel registration failed: {str(e)}"
        )