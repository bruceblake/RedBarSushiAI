"""
Admin API endpoints for retrying failed POS submissions.

This module provides endpoints for restaurant staff to manually
retry orders that failed to submit to Deliverect.
"""

import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.db_async import get_db
from app.models.order_async import Order
from app.services.deliverect_service import DeliverectService
from app.auth.admin import require_admin_auth  # Assuming you have admin auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/pos", tags=["Admin - POS"])


@router.get("/failed-orders")
async def get_failed_pos_orders(
    db: AsyncSession = Depends(get_db),
    # admin: Dict = Depends(require_admin_auth)  # Uncomment when auth is implemented
) -> Dict[str, Any]:
    """
    Get list of orders that failed POS submission.
    
    Returns orders with status 'pending_pos_submission_failed' from the last 48 hours.
    """
    try:
        # Get failed orders from last 48 hours
        cutoff_time = datetime.now() - timedelta(hours=48)
        
        stmt = select(Order).where(
            and_(
                Order.status == "pending_pos_submission_failed",
                Order.created_at >= cutoff_time
            )
        ).order_by(Order.created_at.desc())
        
        result = await db.execute(stmt)
        orders = result.scalars().all()
        
        # Format response
        failed_orders = []
        for order in orders:
            failed_orders.append({
                "order_id": order.id,
                "customer_name": order.customer_name or "Unknown",
                "customer_phone": order.customer_phone,
                "order_type": order.order_type,
                "total_price": float(order.total_price) if order.total_price else 0,
                "created_at": order.created_at.isoformat(),
                "item_count": len(order.items) if order.items else 0
            })
        
        return {
            "success": True,
            "count": len(failed_orders),
            "orders": failed_orders
        }
        
    except Exception as e:
        logger.error(f"Error fetching failed POS orders: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch orders: {str(e)}"
        )


@router.post("/retry/{order_id}")
async def retry_pos_submission(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    # admin: Dict = Depends(require_admin_auth)  # Uncomment when auth is implemented
) -> Dict[str, Any]:
    """
    Manually retry submitting an order to POS.
    
    Args:
        order_id: The order ID to retry
        
    Returns:
        Result of the retry attempt
    """
    try:
        # Get the order
        stmt = select(Order).where(Order.id == order_id)
        result = await db.execute(stmt)
        order = result.scalar_one_or_none()
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order {order_id} not found"
            )
        
        # Check if already submitted
        if order.deliverect_channel_order_id:
            return {
                "success": True,
                "message": "Order already has a Deliverect ID",
                "deliverect_order_id": order.deliverect_channel_order_id,
                "already_submitted": True
            }
        
        # Retry submission
        service = DeliverectService()
        result = await service.submit_order(order, db)
        
        if result["success"]:
            logger.info(f"Successfully retried order {order_id} submission")
            
            return {
                "success": True,
                "message": "Order successfully submitted to POS",
                "order_id": order_id,
                "deliverect_order_id": result.get("deliverect_order_id"),
                "submitted_at": datetime.now().isoformat()
            }
        else:
            logger.error(f"Retry failed for order {order_id}: {result}")
            
            return {
                "success": False,
                "message": "Failed to submit order to POS",
                "order_id": order_id,
                "error": result.get("error", "Unknown error"),
                "needs_manual_intervention": result.get("needs_manual_intervention", True)
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrying POS submission for order {order_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retry order submission: {str(e)}"
        )


@router.post("/retry-all-failed")
async def retry_all_failed_orders(
    db: AsyncSession = Depends(get_db),
    # admin: Dict = Depends(require_admin_auth)  # Uncomment when auth is implemented
) -> Dict[str, Any]:
    """
    Retry all failed POS submissions from the last 48 hours.
    
    Returns:
        Summary of retry attempts
    """
    try:
        # Get failed orders from last 48 hours
        cutoff_time = datetime.now() - timedelta(hours=48)
        
        stmt = select(Order).where(
            and_(
                Order.status == "pending_pos_submission_failed",
                Order.created_at >= cutoff_time,
                Order.deliverect_channel_order_id.is_(None)
            )
        )
        
        result = await db.execute(stmt)
        orders = result.scalars().all()
        
        if not orders:
            return {
                "success": True,
                "message": "No failed orders to retry",
                "total_orders": 0,
                "successful_retries": 0,
                "failed_retries": 0
            }
        
        # Retry each order
        service = DeliverectService()
        successful_retries = 0
        failed_retries = 0
        retry_results = []
        
        for order in orders:
            try:
                result = await service.submit_order(order, db)
                
                if result["success"]:
                    successful_retries += 1
                    retry_results.append({
                        "order_id": order.id,
                        "success": True,
                        "deliverect_order_id": result.get("deliverect_order_id")
                    })
                else:
                    failed_retries += 1
                    retry_results.append({
                        "order_id": order.id,
                        "success": False,
                        "error": result.get("error", "Unknown error")
                    })
                    
            except Exception as e:
                failed_retries += 1
                retry_results.append({
                    "order_id": order.id,
                    "success": False,
                    "error": str(e)
                })
                logger.error(f"Error retrying order {order.id}: {e}")
        
        return {
            "success": True,
            "message": f"Retry completed for {len(orders)} orders",
            "total_orders": len(orders),
            "successful_retries": successful_retries,
            "failed_retries": failed_retries,
            "details": retry_results
        }
        
    except Exception as e:
        logger.error(f"Error in bulk retry of POS submissions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retry orders: {str(e)}"
        )