"""
Granular Deliverect Webhook Endpoints for RedBarSushiAI.

This module provides webhook endpoints for handling granular changes
from Deliverect, including individual item price updates and status changes.
These webhooks enable precise cache invalidation instead of full menu refreshes.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database_async import get_db
from app.utils.enhanced_logging import get_logger
from app.services.cache_service import CacheService
from app.utils.menu_cache_enhanced import MenuCacheManager
from app.db.crud_menu_async import async_menu_db_store
from app.config import settings

logger = get_logger(__name__)

router = APIRouter(prefix="/api/deliverect", tags=["Deliverect Granular Webhooks"])


class PriceUpdateWebhook(BaseModel):
    """Model for price update webhook payload."""
    
    plu: str = Field(..., description="Product Lookup Unit identifier")
    old_price: float = Field(..., description="Previous price in cents")
    new_price: float = Field(..., description="New price in cents")
    currency: str = Field(default="USD", description="Currency code")
    location_id: str = Field(..., description="Deliverect location ID")
    channel_id: str = Field(..., description="Deliverect channel ID")
    updated_at: datetime = Field(..., description="Timestamp of price change")
    updated_by: Optional[str] = Field(None, description="User who made the change")


class ItemStatusUpdateWebhook(BaseModel):
    """Model for item status update webhook payload."""
    
    plu: str = Field(..., description="Product Lookup Unit identifier")
    old_status: str = Field(..., description="Previous status (AVAILABLE, UNAVAILABLE, SNOOZED)")
    new_status: str = Field(..., description="New status (AVAILABLE, UNAVAILABLE, SNOOZED)")
    location_id: str = Field(..., description="Deliverect location ID")
    channel_id: str = Field(..., description="Deliverect channel ID")
    updated_at: datetime = Field(..., description="Timestamp of status change")
    snooze_until: Optional[datetime] = Field(None, description="When snooze expires (if snoozed)")
    reason: Optional[str] = Field(None, description="Reason for status change")


class ModifierUpdateWebhook(BaseModel):
    """Model for modifier update webhook payload."""
    
    plu: str = Field(..., description="Product PLU that owns the modifier")
    modifier_plu: str = Field(..., description="Modifier PLU identifier")
    modifier_name: str = Field(..., description="Modifier name")
    old_price: Optional[float] = Field(None, description="Previous modifier price")
    new_price: Optional[float] = Field(None, description="New modifier price")
    old_status: Optional[str] = Field(None, description="Previous modifier status")
    new_status: Optional[str] = Field(None, description="New modifier status")
    location_id: str = Field(..., description="Deliverect location ID")
    updated_at: datetime = Field(..., description="Timestamp of change")


async def invalidate_item_cache(plu: str, operation: str) -> None:
    """
    Invalidate cache entries for a specific menu item.
    
    Args:
        plu: Product Lookup Unit identifier
        operation: Type of operation (price_update, status_change, etc.)
    """
    cache_service = CacheService()
    menu_cache = MenuCacheManager()
    
    # Specific cache keys to invalidate for this PLU
    cache_keys_to_invalidate = [
        f"menu:product:{plu}",
        f"menu:item:{plu}",
        f"item_plu:{plu}",
        f"variants:{plu}",
        f"menu:modifier:{plu}",
        f"menu:modifier_group:{plu}"
    ]
    
    # Invalidate specific keys
    for key in cache_keys_to_invalidate:
        await cache_service.delete(key, namespace="menu")
        logger.debug(f"Invalidated cache key: {key}")
    
    # Also invalidate any search results that might contain this item
    # Note: This is a broad invalidation but necessary for consistency
    await cache_service.clear_namespace("search")
    
    logger.info(f"Invalidated cache for PLU {plu} due to {operation}")


async def update_local_database_price(
    plu: str, 
    new_price: float, 
    db: AsyncSession
) -> bool:
    """
    Update the price in local database to stay in sync.
    
    Args:
        plu: Product Lookup Unit identifier
        new_price: New price in cents
        db: Database session
        
    Returns:
        True if update successful
    """
    try:
        # Convert cents to dollars for local storage
        price_in_dollars = new_price / 100.0
        
        # Update item price in local database
        from app.db.crud_menu_async import update_item_price
        success = await update_item_price(plu, price_in_dollars, db)
        
        if success:
            logger.info(f"Updated local database price for PLU {plu}: ${price_in_dollars:.2f}")
            return True
        else:
            logger.warning(f"Failed to update local database price for PLU {plu}")
            return False
            
    except Exception as e:
        logger.error(f"Error updating local database price for PLU {plu}: {e}")
        return False


async def update_local_database_status(
    plu: str, 
    new_status: str, 
    db: AsyncSession
) -> bool:
    """
    Update the availability status in local database.
    
    Args:
        plu: Product Lookup Unit identifier
        new_status: New status (AVAILABLE, UNAVAILABLE, SNOOZED)
        db: Database session
        
    Returns:
        True if update successful
    """
    try:
        # Map Deliverect status to local status
        local_status = new_status.lower() == "available"
        
        # Update item availability in local database
        from app.db.crud_menu_async import update_item_availability
        success = await update_item_availability(plu, local_status, db)
        
        if success:
            logger.info(f"Updated local database status for PLU {plu}: {local_status}")
            return True
        else:
            logger.warning(f"Failed to update local database status for PLU {plu}")
            return False
            
    except Exception as e:
        logger.error(f"Error updating local database status for PLU {plu}: {e}")
        return False


@router.post("/price_updated")
async def handle_price_update(
    webhook_data: PriceUpdateWebhook,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle individual item price update webhook from Deliverect.
    
    This endpoint receives notifications when a single menu item's price
    changes and performs targeted cache invalidation and database updates.
    
    Args:
        webhook_data: Price update information
        background_tasks: FastAPI background tasks
        request: HTTP request object
        db: Database session
        
    Returns:
        Success confirmation
    """
    logger.info(f"Received price update webhook for PLU {webhook_data.plu}")
    logger.info(f"Price change: ${webhook_data.old_price/100:.2f} -> ${webhook_data.new_price/100:.2f}")
    
    try:
        # Validate the webhook (in production, you'd verify signature)
        if not webhook_data.plu:
            raise HTTPException(status_code=400, detail="PLU is required")
        
        # Update local database in background
        background_tasks.add_task(
            update_local_database_price,
            webhook_data.plu,
            webhook_data.new_price,
            db
        )
        
        # Invalidate cache immediately
        background_tasks.add_task(
            invalidate_item_cache,
            webhook_data.plu,
            "price_update"
        )
        
        # Send alert for significant price changes
        price_change_percent = abs(webhook_data.new_price - webhook_data.old_price) / webhook_data.old_price
        if price_change_percent > 0.20:  # 20% price change
            from app.services.alerting import alerting_service, Alert, AlertType, AlertSeverity
            
            alert = Alert(
                alert_type=AlertType.MENU_CHANGE,
                severity=AlertSeverity.MEDIUM,
                title="Significant Price Change Detected",
                message=f"💰 PRICE ALERT: PLU {webhook_data.plu} price changed by {price_change_percent:.1%} "
                       f"(${webhook_data.old_price/100:.2f} → ${webhook_data.new_price/100:.2f})",
                timestamp=webhook_data.updated_at.timestamp(),
                metadata={
                    "plu": webhook_data.plu,
                    "old_price": webhook_data.old_price,
                    "new_price": webhook_data.new_price,
                    "change_percent": price_change_percent,
                    "location_id": webhook_data.location_id
                }
            )
            
            background_tasks.add_task(alerting_service.send_alert, alert)
        
        logger.info(f"Successfully processed price update for PLU {webhook_data.plu}")
        
        return {
            "success": True,
            "message": f"Price update processed for PLU {webhook_data.plu}",
            "plu": webhook_data.plu,
            "old_price": webhook_data.old_price / 100,
            "new_price": webhook_data.new_price / 100,
            "processed_at": datetime.utcnow()
        }
        
    except Exception as e:
        logger.error(f"Error processing price update webhook: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process price update: {str(e)}")


@router.post("/item_status_changed")
async def handle_item_status_change(
    webhook_data: ItemStatusUpdateWebhook,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle individual item status change webhook from Deliverect.
    
    This endpoint receives notifications when a menu item's availability
    status changes (available, unavailable, snoozed) and updates cache and database.
    
    Args:
        webhook_data: Status change information
        background_tasks: FastAPI background tasks
        request: HTTP request object
        db: Database session
        
    Returns:
        Success confirmation
    """
    logger.info(f"Received status change webhook for PLU {webhook_data.plu}")
    logger.info(f"Status change: {webhook_data.old_status} -> {webhook_data.new_status}")
    
    try:
        # Validate the webhook
        if not webhook_data.plu:
            raise HTTPException(status_code=400, detail="PLU is required")
        
        valid_statuses = ["AVAILABLE", "UNAVAILABLE", "SNOOZED"]
        if webhook_data.new_status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status: {webhook_data.new_status}")
        
        # Update local database in background
        background_tasks.add_task(
            update_local_database_status,
            webhook_data.plu,
            webhook_data.new_status,
            db
        )
        
        # Invalidate cache immediately
        background_tasks.add_task(
            invalidate_item_cache,
            webhook_data.plu,
            "status_change"
        )
        
        # Send alert for items going unavailable
        if webhook_data.new_status in ["UNAVAILABLE", "SNOOZED"]:
            from app.services.alerting import alerting_service, Alert, AlertType, AlertSeverity
            
            severity = AlertSeverity.LOW if webhook_data.new_status == "SNOOZED" else AlertSeverity.MEDIUM
            
            alert = Alert(
                alert_type=AlertType.MENU_CHANGE,
                severity=severity,
                title="Menu Item Unavailable",
                message=f"🚫 AVAILABILITY ALERT: PLU {webhook_data.plu} is now {webhook_data.new_status.lower()}. "
                       f"Reason: {webhook_data.reason or 'Not specified'}",
                timestamp=webhook_data.updated_at.timestamp(),
                metadata={
                    "plu": webhook_data.plu,
                    "old_status": webhook_data.old_status,
                    "new_status": webhook_data.new_status,
                    "reason": webhook_data.reason,
                    "snooze_until": webhook_data.snooze_until.isoformat() if webhook_data.snooze_until else None,
                    "location_id": webhook_data.location_id
                }
            )
            
            background_tasks.add_task(alerting_service.send_alert, alert)
        
        logger.info(f"Successfully processed status change for PLU {webhook_data.plu}")
        
        return {
            "success": True,
            "message": f"Status change processed for PLU {webhook_data.plu}",
            "plu": webhook_data.plu,
            "old_status": webhook_data.old_status,
            "new_status": webhook_data.new_status,
            "processed_at": datetime.utcnow()
        }
        
    except Exception as e:
        logger.error(f"Error processing status change webhook: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process status change: {str(e)}")


@router.post("/modifier_updated")
async def handle_modifier_update(
    webhook_data: ModifierUpdateWebhook,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle modifier update webhook from Deliverect.
    
    This endpoint receives notifications when modifiers (like size options,
    toppings, etc.) are updated and invalidates related cache entries.
    
    Args:
        webhook_data: Modifier update information
        background_tasks: FastAPI background tasks
        request: HTTP request object
        db: Database session
        
    Returns:
        Success confirmation
    """
    logger.info(f"Received modifier update webhook for PLU {webhook_data.plu}, modifier {webhook_data.modifier_plu}")
    
    try:
        # Invalidate cache for both the main item and modifier
        background_tasks.add_task(
            invalidate_item_cache,
            webhook_data.plu,
            "modifier_update"
        )
        
        # Also invalidate modifier-specific cache
        cache_service = CacheService()
        modifier_cache_keys = [
            f"menu:modifier:{webhook_data.modifier_plu}",
            f"modifier:{webhook_data.modifier_plu}"
        ]
        
        for key in modifier_cache_keys:
            background_tasks.add_task(cache_service.delete, key, "menu")
        
        logger.info(f"Successfully processed modifier update for PLU {webhook_data.plu}")
        
        return {
            "success": True,
            "message": f"Modifier update processed for PLU {webhook_data.plu}",
            "plu": webhook_data.plu,
            "modifier_plu": webhook_data.modifier_plu,
            "processed_at": datetime.utcnow()
        }
        
    except Exception as e:
        logger.error(f"Error processing modifier update webhook: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process modifier update: {str(e)}")


@router.get("/webhook_status")
async def get_webhook_status():
    """
    Get status of granular webhook endpoints.
    
    Returns:
        Status information about webhook processing capabilities
    """
    cache_service = CacheService()
    
    return {
        "webhook_endpoints": {
            "price_updated": "/api/deliverect/price_updated",
            "item_status_changed": "/api/deliverect/item_status_changed", 
            "modifier_updated": "/api/deliverect/modifier_updated"
        },
        "cache_invalidation": {
            "enabled": True,
            "granular_keys": True,
            "search_invalidation": True
        },
        "database_sync": {
            "enabled": True,
            "background_processing": True
        },
        "alerting": {
            "price_change_threshold": 0.20,  # 20%
            "status_change_alerts": True
        },
        "processed_at": datetime.utcnow()
    }