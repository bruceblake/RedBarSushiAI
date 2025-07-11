"""
Deliverect service with robust error handling and retry logic.

This service handles all Deliverect API interactions with proper
error recovery, retries, and circuit breaker pattern.
Enhanced with menu fetching and caching capabilities.
"""

import asyncio
import logging
import httpx
import json
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timedelta

from app.config import settings
from app.models.order_async import Order
from app.models.location_async import Location
from app.models.deliverect_models import (
    DeliverectMenu, Product, Modifier, ModifierGroup, 
    MenuLookupResult, ItemAvailabilityStatus, MenuCacheMetadata
)
from app.utils.deliverect.auth import get_deliverect_access_token
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.utils.enhanced_logging import get_logger
from app.utils.http_utils import CorrelatedAsyncClient
from app.utils.correlation_id import get_correlation_id
from app.services.http_pool import get_http_client
from app.redis_async import redis_set, redis_get, get_redis

logger = get_logger(__name__)


class DeliverectService:
    """Service for interacting with Deliverect API with robust error handling."""
    
    def __init__(self):
        """Initialize the Deliverect service."""
        self.base_url = settings.DELIVERECT_BASE_URL
        self.max_retries = 3
        self.retry_delay = 2.0  # seconds
        self.timeout = 30.0  # seconds
        self.menu_cache_ttl = 3600  # 1 hour cache for menu data
    
    async def get_full_menu(self, db: AsyncSession) -> Optional[Dict[str, Any]]:
        """
        Fetch the complete menu from Deliverect API.
        
        Args:
            db: Database session for location lookup
            
        Returns:
            Dict containing the full menu JSON or None if failed
        """
        try:
            # Get location details
            stmt = select(Location).limit(1)  # Currently single location - multi-location is future feature
            result = await db.execute(stmt)
            location = result.scalar_one_or_none()
            
            if not location or not location.deliverect_channel_link_id:
                logger.error("No location configured for menu fetch")
                return None
            
            # Get access token
            token_response = get_deliverect_access_token(location.deliverect_channel_link_id)
            if not token_response["success"]:
                logger.error("Failed to get access token for menu fetch")
                return None
            
            # Build menu URL
            channel_name = location.deliverect_channel_name or settings.DELIVERECT_CHANNEL_NAME
            menu_url = f"{self.base_url}/{channel_name}/menu/{location.deliverect_channel_link_id}"
            
            # Make request using shared HTTP pool
            client = get_http_client('deliverect')
            response = await client.get(
                menu_url,
                headers={
                    "Authorization": f"Bearer {token_response['token']}",
                    "Content-Type": "application/json"
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                menu_data = response.json()
                logger.info(f"Successfully fetched menu with {len(menu_data.get('products', {}))} products")
                return menu_data
            else:
                logger.error(f"Failed to fetch menu: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching full menu: {e}")
            return None
    
    async def parse_and_cache_menu(self, db: AsyncSession) -> bool:
        """
        Fetch menu from Deliverect, parse into structured models, and cache in Redis.
        
        Args:
            db: Database session
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Fetch the raw menu data
            raw_menu = await self.get_full_menu(db)
            if not raw_menu:
                logger.error("Failed to fetch menu data")
                return False
            
            # Parse into structured models
            menu = DeliverectMenu()
            
            # Parse products
            for plu, product_data in raw_menu.get('products', {}).items():
                try:
                    product = Product(**product_data)
                    menu.products[plu] = product
                except Exception as e:
                    logger.warning(f"Failed to parse product {plu}: {e}")
            
            # Parse modifiers
            for plu, modifier_data in raw_menu.get('modifiers', {}).items():
                try:
                    modifier = Modifier(**modifier_data)
                    menu.modifiers[plu] = modifier
                except Exception as e:
                    logger.warning(f"Failed to parse modifier {plu}: {e}")
            
            # Parse modifier groups
            for plu, group_data in raw_menu.get('modifierGroups', {}).items():
                try:
                    group = ModifierGroup(**group_data)
                    menu.modifier_groups[plu] = group
                except Exception as e:
                    logger.warning(f"Failed to parse modifier group {plu}: {e}")
            
            # Handle snoozed products
            snoozed_plus = raw_menu.get('snoozedProducts', [])
            menu.snoozed_products = snoozed_plus
            
            # Mark snoozed items
            for plu in snoozed_plus:
                if plu in menu.products:
                    menu.products[plu].snoozed = True
                elif plu in menu.modifiers:
                    menu.modifiers[plu].snoozed = True
                elif plu in menu.modifier_groups:
                    menu.modifier_groups[plu].snoozed = True
            
            # Cache the structured data in Redis
            redis_client = await get_redis()
            
            # Cache individual products
            for plu, product in menu.products.items():
                await redis_set(
                    f"menu:product:{plu}", 
                    product.json(),
                    expire=self.menu_cache_ttl
                )
            
            # Cache individual modifiers
            for plu, modifier in menu.modifiers.items():
                await redis_set(
                    f"menu:modifier:{plu}",
                    modifier.json(),
                    expire=self.menu_cache_ttl
                )
            
            # Cache individual modifier groups
            for plu, group in menu.modifier_groups.items():
                await redis_set(
                    f"menu:modifier_group:{plu}",
                    group.json(),
                    expire=self.menu_cache_ttl
                )
            
            # Cache complete menu structure
            await redis_set(
                "menu:complete",
                menu.json(),
                expire=self.menu_cache_ttl
            )
            
            # Cache metadata
            metadata = MenuCacheMetadata(
                last_updated=datetime.now().isoformat(),
                cache_version="1.0",
                total_products=len(menu.products),
                total_modifiers=len(menu.modifiers),
                total_modifier_groups=len(menu.modifier_groups),
                snoozed_count=len(snoozed_plus)
            )
            await redis_set(
                "menu:metadata",
                metadata.json(),
                expire=self.menu_cache_ttl
            )
            
            logger.info(
                f"Successfully cached menu: {len(menu.products)} products, "
                f"{len(menu.modifiers)} modifiers, {len(menu.modifier_groups)} groups, "
                f"{len(snoozed_plus)} snoozed items"
            )
            return True
            
        except Exception as e:
            logger.error(f"Error parsing and caching menu: {e}")
            return False
    
    async def get_cached_product(self, plu: str) -> Optional[Product]:
        """
        Get a cached product by PLU.
        
        Args:
            plu: Product PLU code
            
        Returns:
            Product instance or None if not found
        """
        try:
            product_json = await redis_get(f"menu:product:{plu}")
            if product_json:
                return Product.parse_raw(product_json.decode('utf-8'))
        except Exception as e:
            logger.error(f"Error getting cached product {plu}: {e}")
        return None
    
    async def get_cached_modifier_group(self, plu: str) -> Optional[ModifierGroup]:
        """
        Get a cached modifier group by PLU.
        
        Args:
            plu: ModifierGroup PLU code
            
        Returns:
            ModifierGroup instance or None if not found
        """
        try:
            group_json = await redis_get(f"menu:modifier_group:{plu}")
            if group_json:
                return ModifierGroup.parse_raw(group_json.decode('utf-8'))
        except Exception as e:
            logger.error(f"Error getting cached modifier group {plu}: {e}")
        return None
    
    async def get_cached_modifier(self, plu: str) -> Optional[Modifier]:
        """
        Get a cached modifier by PLU.
        
        Args:
            plu: Modifier PLU code
            
        Returns:
            Modifier instance or None if not found
        """
        try:
            modifier_json = await redis_get(f"menu:modifier:{plu}")
            if modifier_json:
                return Modifier.parse_raw(modifier_json.decode('utf-8'))
        except Exception as e:
            logger.error(f"Error getting cached modifier {plu}: {e}")
        return None
    
    async def get_all_cached_products(self) -> List[Product]:
        """
        Get all cached products from Redis.
        
        Returns:
            List of Product instances
        """
        products = []
        try:
            redis_client = await get_redis()
            
            # Scan for all product keys
            async for key in redis_client.scan_iter(match="menu:product:*"):
                try:
                    product_json = await redis_client.get(key)
                    if product_json:
                        product = Product.parse_raw(product_json.decode('utf-8'))
                        products.append(product)
                except Exception as e:
                    logger.warning(f"Failed to parse cached product from key {key}: {e}")
                    
        except Exception as e:
            logger.error(f"Error getting all cached products: {e}")
            
        return products
    
    async def check_item_availability(self, plu: str) -> ItemAvailabilityStatus:
        """
        Check if an item is available (not snoozed).
        
        Args:
            plu: Item PLU code
            
        Returns:
            ItemAvailabilityStatus with availability information
        """
        try:
            # Try to get the product first
            product = await self.get_cached_product(plu)
            if product:
                return ItemAvailabilityStatus(
                    plu=plu,
                    name=product.name,
                    is_available=not product.snoozed,
                    snoozed=product.snoozed,
                    reason="Item is temporarily unavailable" if product.snoozed else None
                )
            
            # If not a product, check modifiers
            modifier = await self.get_cached_modifier(plu)
            if modifier:
                return ItemAvailabilityStatus(
                    plu=plu,
                    name=modifier.name,
                    is_available=not modifier.snoozed,
                    snoozed=modifier.snoozed,
                    reason="Option is temporarily unavailable" if modifier.snoozed else None
                )
            
            # Item not found
            return ItemAvailabilityStatus(
                plu=plu,
                name="Unknown Item",
                is_available=False,
                snoozed=False,
                reason="Item not found in menu"
            )
            
        except Exception as e:
            logger.error(f"Error checking availability for {plu}: {e}")
            return ItemAvailabilityStatus(
                plu=plu,
                name="Unknown Item",
                is_available=False,
                snoozed=False,
                reason=f"Error checking availability: {str(e)}"
            )
    
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
            
            # Add items with modifier support
            for item in order.items:
                # Extract modifiers from item
                modifiers = []
                if hasattr(item, 'modifiers') and item.modifiers:
                    for modifier in item.modifiers:
                        if hasattr(modifier, 'plu') and modifier.plu:
                            modifiers.append({
                                "plu": modifier.plu,
                                "name": modifier.name,
                                "price": float(modifier.price or 0),
                                "quantity": modifier.quantity or 1
                            })
                
                order_data["items"].append({
                    "plu": item.menu_item_plu,
                    "name": item.name,
                    "price": float(item.price),
                    "quantity": item.quantity,
                    "modifiers": modifiers
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
                # Make API call directly
                success, response_data, status_code = await self._make_api_call(
                    deliverect_payload,
                    db
                )
                
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
        stmt = select(Location).limit(1)  # Currently single location - multi-location is future feature
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


# Singleton instance for easy import and shared usage
deliverect_service = DeliverectService()