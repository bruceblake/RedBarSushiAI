"""
Async CRUD operations for order-related models.

This module provides asynchronous create, read, update, and delete operations
for orders and order items.
"""

import logging
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import uuid

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order_async import Order, OrderItem, OrderItemModifier, ContactRequest

logger = logging.getLogger(__name__)

# Order CRUD operations
async def create_order(
    db: AsyncSession,
    order_data: Dict[str, Any]
) -> Order:
    """
    Create a new order.
    
    Args:
        db: Database session
        order_data: Order data dictionary
        
    Returns:
        Created Order object
    """
    order = Order(
        id=order_data.get('id', str(uuid.uuid4())),
        deliverect_channel_order_id=order_data.get('deliverect_channel_order_id'),
        customer_phone=order_data['customer_phone'],
        customer_name=order_data.get('customer_name'),
        order_type=order_data.get('order_type', 'pickup'),
        status=order_data.get('status', 10),
        total_price=order_data.get('total_price', 0.0),
        placed_at=order_data.get('placed_at', datetime.utcnow()),
        estimated_time=order_data.get('estimated_time'),
        delivery_address=order_data.get('delivery_address')
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order

async def get_order(
    db: AsyncSession,
    order_id: str,
    include_items: bool = True
) -> Optional[Order]:
    """
    Get an order by ID.
    
    Args:
        db: Database session
        order_id: Order ID
        include_items: Whether to include order items
        
    Returns:
        Order object or None if not found
    """
    query = select(Order).where(Order.id == order_id)
    
    if include_items:
        query = query.options(
            selectinload(Order.items).selectinload(OrderItem.modifiers)
        )
    
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def get_order_by_deliverect_id(
    db: AsyncSession,
    deliverect_channel_order_id: str,
    include_items: bool = True
) -> Optional[Order]:
    """
    Get an order by Deliverect channel order ID.
    
    Args:
        db: Database session
        deliverect_channel_order_id: Deliverect channel order ID
        include_items: Whether to include order items
        
    Returns:
        Order object or None if not found
    """
    query = select(Order).where(Order.deliverect_channel_order_id == deliverect_channel_order_id)
    
    if include_items:
        query = query.options(
            selectinload(Order.items).selectinload(OrderItem.modifiers)
        )
    
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def get_orders_by_phone(
    db: AsyncSession,
    customer_phone: str,
    limit: int = 10,
    include_items: bool = False
) -> List[Order]:
    """
    Get orders by customer phone number.
    
    Args:
        db: Database session
        customer_phone: Customer phone number
        limit: Maximum number of orders to return
        include_items: Whether to include order items
        
    Returns:
        List of Order objects
    """
    query = (
        select(Order)
        .where(Order.customer_phone == customer_phone)
        .order_by(Order.placed_at.desc())
        .limit(limit)
    )
    
    if include_items:
        query = query.options(
            selectinload(Order.items).selectinload(OrderItem.modifiers)
        )
    
    result = await db.execute(query)
    return result.scalars().all()

async def update_order_status(
    db: AsyncSession,
    order_id: str,
    status: int,
    estimated_time: Optional[datetime] = None
) -> Optional[Order]:
    """
    Update order status and optionally estimated time.
    
    Args:
        db: Database session
        order_id: Order ID
        status: New status code
        estimated_time: Optional new estimated time
        
    Returns:
        Updated Order object or None if not found
    """
    # First check if order exists
    order = await get_order(db, order_id, include_items=False)
    if not order:
        logger.warning(f"Order {order_id} not found for status update")
        return None
    
    # Update the order
    update_data = {"status": status, "updated_at": datetime.utcnow()}
    if estimated_time is not None:
        update_data["estimated_time"] = estimated_time
    
    stmt = (
        update(Order)
        .where(Order.id == order_id)
        .values(**update_data)
    )
    
    await db.execute(stmt)
    await db.commit()
    
    # Return updated order
    return await get_order(db, order_id, include_items=True)

async def update_order(
    db: AsyncSession,
    order_id: str,
    order_data: Dict[str, Any]
) -> Optional[Order]:
    """
    Update an order with provided data.
    
    Args:
        db: Database session
        order_id: Order ID
        order_data: Dictionary of fields to update
        
    Returns:
        Updated Order object or None if not found
    """
    # First check if order exists
    order = await get_order(db, order_id, include_items=False)
    if not order:
        logger.warning(f"Order {order_id} not found for update")
        return None
    
    # Add updated_at timestamp
    order_data["updated_at"] = datetime.utcnow()
    
    stmt = (
        update(Order)
        .where(Order.id == order_id)
        .values(**order_data)
    )
    
    await db.execute(stmt)
    await db.commit()
    
    # Return updated order
    return await get_order(db, order_id, include_items=True)

async def delete_order(
    db: AsyncSession,
    order_id: str
) -> bool:
    """
    Delete an order and all related items.
    
    Args:
        db: Database session
        order_id: Order ID
        
    Returns:
        True if deleted, False if not found
    """
    # Check if order exists
    order = await get_order(db, order_id, include_items=False)
    if not order:
        return False
    
    # Delete the order (cascade will handle items and modifiers)
    stmt = delete(Order).where(Order.id == order_id)
    await db.execute(stmt)
    await db.commit()
    
    return True

# Order Item CRUD operations
async def create_order_item(
    db: AsyncSession,
    order_id: str,
    item_data: Dict[str, Any]
) -> Optional[OrderItem]:
    """
    Create a new order item.
    
    Args:
        db: Database session
        order_id: Order ID
        item_data: Order item data
        
    Returns:
        Created OrderItem object or None if order not found
    """
    # Verify order exists
    order = await get_order(db, order_id, include_items=False)
    if not order:
        logger.warning(f"Order {order_id} not found for item creation")
        return None
    
    item = OrderItem(
        id=item_data.get('id', str(uuid.uuid4())),
        order_id=order_id,
        menu_item_plu=item_data['menu_item_plu'],
        name=item_data['name'],
        quantity=item_data.get('quantity', 1),
        price=item_data.get('price', 0.0),
        note=item_data.get('note')
    )
    
    db.add(item)
    await db.commit()
    await db.refresh(item)
    
    return item

async def update_order_item(
    db: AsyncSession,
    item_id: str,
    item_data: Dict[str, Any]
) -> Optional[OrderItem]:
    """
    Update an order item.
    
    Args:
        db: Database session
        item_id: Order item ID
        item_data: Fields to update
        
    Returns:
        Updated OrderItem object or None if not found
    """
    # Check if item exists
    query = select(OrderItem).where(OrderItem.id == item_id)
    result = await db.execute(query)
    item = result.scalar_one_or_none()
    
    if not item:
        logger.warning(f"Order item {item_id} not found for update")
        return None
    
    # Update fields
    for key, value in item_data.items():
        if hasattr(item, key):
            setattr(item, key, value)
    
    item.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(item)
    
    return item

async def delete_order_item(
    db: AsyncSession,
    item_id: str
) -> bool:
    """
    Delete an order item.
    
    Args:
        db: Database session
        item_id: Order item ID
        
    Returns:
        True if deleted, False if not found
    """
    stmt = delete(OrderItem).where(OrderItem.id == item_id)
    result = await db.execute(stmt)
    await db.commit()
    
    return result.rowcount > 0

# Contact Request CRUD operations
async def create_contact_request(
    db: AsyncSession,
    request_data: Dict[str, Any]
) -> ContactRequest:
    """
    Create a new contact request.
    
    Args:
        db: Database session
        request_data: Contact request data
        
    Returns:
        Created ContactRequest object
    """
    contact_request = ContactRequest(
        id=request_data.get('id', str(uuid.uuid4())),
        customer_name=request_data.get('customer_name'),
        customer_phone=request_data.get('customer_phone'),
        customer_email=request_data.get('customer_email'),
        message=request_data.get('message'),
        request_type=request_data['request_type'],
        status=request_data.get('status', 'pending'),
        call_sid=request_data.get('call_sid')
    )
    
    db.add(contact_request)
    await db.commit()
    await db.refresh(contact_request)
    
    return contact_request

async def get_contact_requests(
    db: AsyncSession,
    status: Optional[str] = None,
    request_type: Optional[str] = None,
    limit: int = 100
) -> List[ContactRequest]:
    """
    Get contact requests with optional filtering.
    
    Args:
        db: Database session
        status: Optional status filter
        request_type: Optional request type filter
        limit: Maximum number of results
        
    Returns:
        List of ContactRequest objects
    """
    query = select(ContactRequest).order_by(ContactRequest.created_at.desc()).limit(limit)
    
    if status:
        query = query.where(ContactRequest.status == status)
    
    if request_type:
        query = query.where(ContactRequest.request_type == request_type)
    
    result = await db.execute(query)
    return result.scalars().all()

async def update_contact_request_status(
    db: AsyncSession,
    request_id: str,
    status: str
) -> Optional[ContactRequest]:
    """
    Update contact request status.
    
    Args:
        db: Database session
        request_id: Contact request ID
        status: New status
        
    Returns:
        Updated ContactRequest object or None if not found
    """
    stmt = (
        update(ContactRequest)
        .where(ContactRequest.id == request_id)
        .values(status=status, updated_at=datetime.utcnow())
    )
    
    result = await db.execute(stmt)
    await db.commit()
    
    if result.rowcount == 0:
        return None
    
    # Get and return updated request
    query = select(ContactRequest).where(ContactRequest.id == request_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_order_by_channel_id(
    db: AsyncSession,
    channel_order_id: str
) -> Optional[Order]:
    """
    Get order by Deliverect channel order ID.
    
    Args:
        db: Database session
        channel_order_id: Channel order ID
        
    Returns:
        Order object or None if not found
    """
    try:
        stmt = select(Order).where(Order.deliverect_channel_order_id == channel_order_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Error getting order by channel ID {channel_order_id}: {e}")
        return None


async def update_order_deliverect_status(
    db: AsyncSession,
    order_id: str,
    deliverect_order_id: str,
    status: int,
    timestamp: str,
    receipt_id: Optional[str] = None,
    reason: Optional[str] = None
) -> bool:
    """
    Update order status from Deliverect webhook.
    
    Args:
        db: Database session
        order_id: Deliverect order ID
        deliverect_order_id: Deliverect order ID
        status: Status code
        timestamp: Status timestamp
        receipt_id: POS receipt ID
        reason: Reason for status change
        
    Returns:
        True if successful, False otherwise
    """
    try:
        stmt = (
            update(Order)
            .where(Order.deliverect_channel_order_id == order_id)
            .values(
                status=status,
                deliverect_order_id=deliverect_order_id,
                last_status_update=datetime.fromisoformat(timestamp.replace('Z', '+00:00')),
                pos_receipt_id=receipt_id,
                status_reason=reason
            )
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0
    except Exception as e:
        logger.error(f"Error updating order Deliverect status: {e}")
        await db.rollback()
        return False


async def update_order_courier_info(
    db: AsyncSession,
    channel_order_id: str,
    courier_data: Dict[str, Any]
) -> bool:
    """
    Update order courier information.
    
    Args:
        db: Database session
        channel_order_id: Channel order ID
        courier_data: Courier information
        
    Returns:
        True if successful, False otherwise
    """
    try:
        stmt = (
            update(Order)
            .where(Order.deliverect_channel_order_id == channel_order_id)
            .values(courier_info=courier_data)
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0
    except Exception as e:
        logger.error(f"Error updating order courier info: {e}")
        await db.rollback()
        return False


async def update_order_payment_info(
    db: AsyncSession,
    channel_order_id: str,
    payment_data: Dict[str, Any]
) -> bool:
    """
    Update order payment information.
    
    Args:
        db: Database session
        channel_order_id: Channel order ID
        payment_data: Payment information
        
    Returns:
        True if successful, False otherwise
    """
    try:
        stmt = (
            update(Order)
            .where(Order.deliverect_channel_order_id == channel_order_id)
            .values(payment_info=payment_data)
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0
    except Exception as e:
        logger.error(f"Error updating order payment info: {e}")
        await db.rollback()
        return False