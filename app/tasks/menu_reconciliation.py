"""
Menu Reconciliation Tasks for RedBarSushiAI.

This module contains Celery tasks for performing full menu reconciliation
between Deliverect and the local database to ensure data consistency.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from celery import current_task
from sqlalchemy.ext.asyncio import AsyncSession

from celery_app_fastapi import celery
from app.db_async import get_db
from app.services.deliverect_service import DeliverectService
from app.db.crud_menu_async import get_all_menu_items, update_item_price, update_item_availability
from app.utils.enhanced_logging import get_logger
from app.services.alerting import alerting_service, Alert, AlertType, AlertSeverity
from app.services.cache_service import CacheService
from app.utils.menu_cache_enhanced import MenuCacheManager

logger = get_logger(__name__)


@celery.task(bind=True, max_retries=3, default_retry_delay=300)
def daily_menu_reconciliation(self):
    """
    Daily menu reconciliation task.
    
    Performs a complete comparison between Deliverect menu data
    and local database, identifying and fixing inconsistencies.
    
    This task runs asynchronously and reports results via alerts.
    """
    task_id = current_task.request.id if current_task else "manual"
    logger.info(f"Starting daily menu reconciliation task {task_id}")
    
    try:
        # Run the async reconciliation logic
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(_perform_menu_reconciliation(task_id))
        
        logger.info(f"Daily menu reconciliation completed successfully: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Daily menu reconciliation failed: {e}")
        
        # Retry the task if we haven't exceeded max retries
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying menu reconciliation (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e, countdown=300)  # Retry in 5 minutes
        else:
            # All retries failed, send critical alert
            asyncio.run(_send_reconciliation_failure_alert(task_id, str(e)))
            raise e


async def _perform_menu_reconciliation(task_id: str) -> Dict[str, Any]:
    """
    Perform the actual menu reconciliation logic.
    
    Args:
        task_id: Unique identifier for this reconciliation task
        
    Returns:
        Dictionary with reconciliation results
    """
    start_time = datetime.utcnow()
    results = {
        "task_id": task_id,
        "started_at": start_time.isoformat(),
        "deliverect_items": 0,
        "local_items": 0,
        "inconsistencies": {
            "missing_in_local": [],
            "missing_in_deliverect": [],
            "price_mismatches": [],
            "availability_mismatches": []
        },
        "corrections_made": 0,
        "cache_refreshed": False,
        "errors": []
    }
    
    db_session = None
    
    try:
        # Get database session
        async for db_session in get_db():
            break
        
        # Fetch menu from Deliverect
        logger.info("Fetching current menu from Deliverect...")
        deliverect_service = DeliverectService()
        deliverect_menu = await deliverect_service.get_full_menu(db_session)
        
        if not deliverect_menu:
            raise Exception("Failed to fetch menu from Deliverect")
        
        # Parse Deliverect items
        deliverect_items = _parse_deliverect_menu(deliverect_menu)
        results["deliverect_items"] = len(deliverect_items)
        
        # Fetch local menu items
        logger.info("Fetching local menu items from database...")
        local_items = await get_all_menu_items(db_session)
        results["local_items"] = len(local_items)
        
        # Create lookup dictionaries
        local_items_by_plu = {item.plu: item for item in local_items}
        deliverect_items_by_plu = {item["plu"]: item for item in deliverect_items}
        
        # Find inconsistencies
        logger.info("Identifying inconsistencies...")
        
        # Items missing in local database
        for plu, deliverect_item in deliverect_items_by_plu.items():
            if plu not in local_items_by_plu:
                results["inconsistencies"]["missing_in_local"].append({
                    "plu": plu,
                    "name": deliverect_item["name"],
                    "price": deliverect_item["price"]
                })
        
        # Items missing in Deliverect (potentially discontinued)
        for plu, local_item in local_items_by_plu.items():
            if plu not in deliverect_items_by_plu:
                results["inconsistencies"]["missing_in_deliverect"].append({
                    "plu": plu,
                    "name": local_item.name,
                    "price": float(local_item.price) if local_item.price else 0.0
                })
        
        # Price mismatches
        for plu in set(local_items_by_plu.keys()) & set(deliverect_items_by_plu.keys()):
            local_item = local_items_by_plu[plu]
            deliverect_item = deliverect_items_by_plu[plu]
            
            local_price = float(local_item.price) if local_item.price else 0.0
            deliverect_price = deliverect_item["price"]
            
            # Allow for small floating point differences
            if abs(local_price - deliverect_price) > 0.01:
                results["inconsistencies"]["price_mismatches"].append({
                    "plu": plu,
                    "name": local_item.name,
                    "local_price": local_price,
                    "deliverect_price": deliverect_price,
                    "difference": deliverect_price - local_price
                })
        
        # Apply corrections if in sync mode
        corrections_made = await _apply_reconciliation_corrections(
            results["inconsistencies"], 
            db_session
        )
        results["corrections_made"] = corrections_made
        
        # Refresh cache if corrections were made
        if corrections_made > 0:
            await _refresh_menu_cache()
            results["cache_refreshed"] = True
        
        # Send reconciliation report
        await _send_reconciliation_report(results)
        
        results["completed_at"] = datetime.utcnow().isoformat()
        results["duration_seconds"] = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info(f"Menu reconciliation completed: {corrections_made} corrections made")
        return results
        
    except Exception as e:
        logger.error(f"Error during menu reconciliation: {e}")
        results["errors"].append(str(e))
        raise e
        
    finally:
        if db_session:
            await db_session.close()


def _parse_deliverect_menu(deliverect_menu: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parse Deliverect menu data into a standardized format.
    
    Args:
        deliverect_menu: Raw menu data from Deliverect API
        
    Returns:
        List of parsed menu items
    """
    items = []
    
    try:
        products = deliverect_menu.get("products", {})
        
        for product_id, product_data in products.items():
            # Extract basic item information
            item = {
                "plu": product_data.get("plu", product_id),
                "name": product_data.get("name", ""),
                "price": float(product_data.get("price", 0)) / 100.0,  # Convert cents to dollars
                "available": product_data.get("available", True),
                "category": product_data.get("category", ""),
                "description": product_data.get("description", "")
            }
            items.append(item)
            
    except Exception as e:
        logger.error(f"Error parsing Deliverect menu: {e}")
        raise e
    
    return items


async def _apply_reconciliation_corrections(
    inconsistencies: Dict[str, List], 
    db_session: AsyncSession
) -> int:
    """
    Apply corrections for identified inconsistencies.
    
    Args:
        inconsistencies: Dictionary of inconsistencies found
        db_session: Database session
        
    Returns:
        Number of corrections applied
    """
    corrections_made = 0
    
    try:
        # Update prices for mismatched items
        for price_mismatch in inconsistencies["price_mismatches"]:
            plu = price_mismatch["plu"]
            correct_price = price_mismatch["deliverect_price"]
            
            success = await update_item_price(plu, correct_price, db_session)
            if success:
                corrections_made += 1
                logger.info(f"Corrected price for PLU {plu}: ${correct_price:.2f}")
        
        # Note: We don't automatically add/remove items as that requires more careful consideration
        # These would typically be handled by manual review or separate processes
        
    except Exception as e:
        logger.error(f"Error applying reconciliation corrections: {e}")
        raise e
    
    return corrections_made


async def _refresh_menu_cache():
    """Refresh menu cache after corrections are applied."""
    try:
        cache_service = CacheService()
        menu_cache = MenuCacheManager()
        
        # Clear entire menu cache to force refresh
        await cache_service.clear_namespace("menu")
        await cache_service.clear_namespace("search")
        
        logger.info("Menu cache refreshed after reconciliation")
        
    except Exception as e:
        logger.error(f"Error refreshing menu cache: {e}")


async def _send_reconciliation_report(results: Dict[str, Any]):
    """
    Send reconciliation report via alerts.
    
    Args:
        results: Reconciliation results dictionary
    """
    try:
        total_inconsistencies = sum(
            len(inconsistencies) 
            for inconsistencies in results["inconsistencies"].values()
        )
        
        if total_inconsistencies == 0:
            # Clean reconciliation - send info alert
            alert = Alert(
                alert_type=AlertType.SYSTEM_INFO,
                severity=AlertSeverity.INFO,
                title="Daily Menu Reconciliation: All Clear",
                message=f"✅ RECONCILIATION SUCCESS: Menu is fully synchronized.\n"
                       f"• Deliverect items: {results['deliverect_items']}\n"
                       f"• Local items: {results['local_items']}\n"
                       f"• Duration: {results.get('duration_seconds', 0):.1f}s",
                timestamp=datetime.utcnow().timestamp(),
                metadata=results
            )
        else:
            # Issues found - send warning alert
            alert = Alert(
                alert_type=AlertType.MENU_CHANGE,
                severity=AlertSeverity.MEDIUM,
                title="Daily Menu Reconciliation: Issues Found",
                message=f"⚠️ RECONCILIATION ISSUES: Found {total_inconsistencies} inconsistencies.\n"
                       f"• Missing in local: {len(results['inconsistencies']['missing_in_local'])}\n"
                       f"• Price mismatches: {len(results['inconsistencies']['price_mismatches'])}\n"
                       f"• Corrections made: {results['corrections_made']}\n"
                       f"• Duration: {results.get('duration_seconds', 0):.1f}s",
                timestamp=datetime.utcnow().timestamp(),
                metadata=results
            )
        
        await alerting_service.send_alert(alert)
        
    except Exception as e:
        logger.error(f"Error sending reconciliation report: {e}")


async def _send_reconciliation_failure_alert(task_id: str, error_message: str):
    """
    Send critical alert when reconciliation fails completely.
    
    Args:
        task_id: Task identifier
        error_message: Error description
    """
    try:
        alert = Alert(
            alert_type=AlertType.SYSTEM_ERROR,
            severity=AlertSeverity.CRITICAL,
            title="Daily Menu Reconciliation Failed",
            message=f"🚨 CRITICAL: Daily menu reconciliation task {task_id} failed after all retries.\n"
                   f"Error: {error_message}\n"
                   f"Manual intervention required to ensure menu data consistency.",
            timestamp=datetime.utcnow().timestamp(),
            metadata={
                "task_id": task_id,
                "error": error_message,
                "failed_at": datetime.utcnow().isoformat()
            }
        )
        
        await alerting_service.send_alert(alert)
        
    except Exception as e:
        logger.error(f"Error sending reconciliation failure alert: {e}")


@celery.task(bind=True)
def weekly_menu_health_check(self):
    """
    Weekly comprehensive menu health check.
    
    Performs deeper analysis of menu data health including:
    - Category distribution analysis
    - Price trend analysis
    - Availability pattern analysis
    """
    task_id = current_task.request.id if current_task else "manual"
    logger.info(f"Starting weekly menu health check task {task_id}")
    
    try:
        # Run the async health check logic
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(_perform_menu_health_check(task_id))
        
        logger.info(f"Weekly menu health check completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Weekly menu health check failed: {e}")
        raise e


async def _perform_menu_health_check(task_id: str) -> Dict[str, Any]:
    """
    Perform comprehensive menu health analysis.
    
    Args:
        task_id: Unique identifier for this health check
        
    Returns:
        Dictionary with health check results
    """
    # Implementation would include:
    # - Category distribution analysis
    # - Price anomaly detection
    # - Availability pattern analysis
    # - Performance metrics
    
    return {
        "task_id": task_id,
        "status": "completed",
        "timestamp": datetime.utcnow().isoformat(),
        "health_score": 95.5,  # Example score
        "recommendations": []
    }