"""
Deliverect service with robust error handling and retry logic.

This service handles all Deliverect API interactions with proper
error recovery, retries, and circuit breaker pattern.
"""

import asyncio
import logging
import httpx
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

from app.config import settings
from app.models.order_async import Order
from app.models.location_async import Location
from app.utils.deliverect.auth import get_deliverect_access_token
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.utils.enhanced_logging import get_logger
from app.utils.http_utils import CorrelatedAsyncClient
from app.utils.correlation_id import get_correlation_id
from app.services.circuit_breaker import circuit_breakers, CircuitBreakerError
from app.services.http_pool import get_http_client

logger = get_logger(__name__)


class DeliverectService:
    """Service for interacting with Deliverect API with robust error handling."""
    
    def __init__(self):
        """Initialize the Deliverect service."""
        self.base_url = settings.DELIVERECT_BASE_URL
        self.max_retries = 3
        self.retry_delay = 2.0  # seconds
        self.timeout = 30.0  # seconds
    
    
    async def submit_order(self, order: Order, db: AsyncSession) -> Dict[str, Any]:
        """
        Submit an order to Deliverect with retry logic and error handling.
        
        Args:
            order: The order to submit
            db: Database session
            
        Returns:
            Dict with submission results
        """
        # Build order payload
        try:
            from app.utils.deliverect_async import build_deliverect_order
            
            order_data = {
                "order_type": 1 if order.order_type == "pickup" else 2,
                "customer": {
                    "name": order.customer_name or "Guest",
                    "phone_number": order.customer_phone,
                },
                "items": []
            }
            
            # Add items
            for item in order.items:
                order_data["items"].append({
                    "plu": item.menu_item_plu,
                    "name": item.name,
                    "price": float(item.price),
                    "quantity": item.quantity,
                    "modifiers": []  # TODO: Add modifier support
                })
            
            deliverect_payload = build_deliverect_order(order_data)
            
        except Exception as e:
            logger.error(f"Failed to build Deliverect order payload: {e}", order_id=order.id)
            return {
                "success": False,
                "error": f"Failed to prepare order: {str(e)}",
                "needs_manual_intervention": True
            }
        
        # Attempt submission with retries
        for attempt in range(self.max_retries):
            try:
                # Use circuit breaker for API call
                try:
                    success, response_data, status_code = await circuit_breakers.deliverect.async_call(
                        self._make_api_call,
                        deliverect_payload,
                        db
                    )
                except CircuitBreakerError:
                    logger.error(
                        "Circuit breaker is open - Deliverect API unavailable",
                        order_id=order.id
                    )
                    return {
                        "success": False,
                        "error": "POS system temporarily unavailable - circuit breaker open",
                        "needs_manual_intervention": True
                    }
                
                if success:
                    # Update order with Deliverect ID
                    if response_data.get("id"):
                        order.deliverect_channel_order_id = response_data["id"]
                        order.status = 20  # Accepted
                        await db.commit()
                    
                    return {
                        "success": True,
                        "deliverect_order_id": response_data.get("id"),
                        "response": response_data
                    }
                
                # Handle specific error cases
                if status_code == 401:
                    # Authentication failure - don't retry
                    logger.error("Authentication failed with Deliverect")
                    return {
                        "success": False,
                        "error": "Authentication failed with POS system",
                        "needs_manual_intervention": True
                    }
                
                # Log the failure
                logger.warning(f"Deliverect submission attempt {attempt + 1} failed: {response_data}")
                
            except httpx.TimeoutException:
                logger.error(f"Timeout on attempt {attempt + 1} submitting to Deliverect")
                    
            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
            
            # Wait before retry (except on last attempt)
            if attempt < self.max_retries - 1:
                await asyncio.sleep(self.retry_delay * (attempt + 1))
        
        # All retries failed
        return {
            "success": False,
            "error": "Failed to submit order after multiple attempts",
            "needs_manual_intervention": True,
            "retry_count": self.max_retries
        }
    
    async def _make_api_call(
        self, 
        payload: Dict[str, Any], 
        db: AsyncSession
    ) -> Tuple[bool, Dict[str, Any], Optional[int]]:
        """
        Make the actual API call to Deliverect.
        
        Returns:
            Tuple of (success, response_data, status_code)
        """
        # Get location details
        stmt = select(Location).limit(1)  # TODO: Support multiple locations
        result = await db.execute(stmt)
        location = result.scalar_one_or_none()
        
        if not location or not location.deliverect_channel_link_id:
            return False, {"error": "No location configured"}, None
        
        # Get access token
        token_response = get_deliverect_access_token(location.deliverect_channel_link_id)
        if not token_response["success"]:
            return False, {"error": "Failed to get access token"}, None
        
        # Build URL
        channel_name = location.deliverect_channel_name or settings.DELIVERECT_CHANNEL_NAME
        api_url = f"{self.base_url}/{channel_name}/order/{location.deliverect_channel_link_id}"
        
        # Make request using shared HTTP pool
        client = get_http_client('deliverect')
        response = await client.post(
            api_url,
            headers={
                "Authorization": f"Bearer {token_response['token']}",
                "Content-Type": "application/json"
            },
            json=payload
        )
        
        try:
            response_data = response.json()
        except:
            response_data = {"text": response.text}
        
        return response.status_code == 201, response_data, response.status_code