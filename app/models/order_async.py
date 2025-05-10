"""
Async Order models for RedBarSushiAI.

This module provides SQLAlchemy 2.0 async models for orders.
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db_async import Base

# Define the TimestampMixin in SQLAlchemy 2.0 style
class TimestampMixin:
    """Mixin that adds created_at and updated_at timestamps."""
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

class Order(Base, TimestampMixin):
    """
    Order model for storing customer orders in SQLAlchemy 2.0 style.
    """
    __tablename__ = "orders"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    deliverect_channel_order_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    customer_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    customer_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    order_type: Mapped[str] = mapped_column(String(20), default="pickup")
    status: Mapped[int] = mapped_column(Integer, default=10)  # 10 = received
    total_price: Mapped[float] = mapped_column(Float, default=0.0)
    placed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    estimated_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    delivery_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationship to order items
    items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )

class OrderItem(Base, TimestampMixin):
    """
    OrderItem model for individual items in an order.
    """
    __tablename__ = "order_items"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id"), nullable=False)
    menu_item_plu: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationship to order and modifiers
    order: Mapped["Order"] = relationship("Order", back_populates="items")
    modifiers: Mapped[List["OrderItemModifier"]] = relationship(
        "OrderItemModifier", back_populates="order_item", cascade="all, delete-orphan"
    )

class OrderItemModifier(Base, TimestampMixin):
    """
    OrderItemModifier model for modifiers applied to order items.
    """
    __tablename__ = "order_item_modifiers"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_item_id: Mapped[str] = mapped_column(String(36), ForeignKey("order_items.id"), nullable=False)
    modifier_plu: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price_change: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Relationship to order item
    order_item: Mapped["OrderItem"] = relationship("OrderItem", back_populates="modifiers")