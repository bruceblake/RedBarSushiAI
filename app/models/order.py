"""
Order model for storing order data and contact requests.
"""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

# Import the SQLAlchemy 2.0 Base
from app.db_async import Base

# Define the TimestampMixin in SQLAlchemy 2.0 style
class TimestampMixin:
    """Mixin that adds created_at and updated_at timestamps."""
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Order(Base, TimestampMixin):
    """
    Order model for storing customer orders.
    """

    __tablename__ = "order"
    id = Column(String(36), primary_key=True)
    sender = Column(String(15), nullable=False)
    caller_name = Column(String(50), nullable=False)
    message = Column(String(500), nullable=False)
    status = Column(String(20), default="NEW")
    status_code = Column(Integer, nullable=True)  # Deliverect status code
    status_updated_at = Column(
        DateTime, nullable=True
    )  # When status last changed
    timestamp = Column(DateTime, default=func.current_timestamp())
    location_id = Column(String(36), nullable=True)
    sms_sid = Column(String(50), nullable=True)
    sms_status = Column(String(20), nullable=True)
    sms_error_code = Column(Integer, nullable=True)
    sms_error_message = Column(String(255), nullable=True)
    # Delivery tracking fields
    delivery_status = Column(
        String(30), nullable=True
    )  # Delivery-specific status
    delivery_status_code = Column(Integer, nullable=True)  # Delivery status code
    courier_name = Column(String(50), nullable=True)  # Name of delivery courier
    courier_phone = Column(String(20), nullable=True)  # Phone of delivery courier
    estimated_delivery_time = Column(
        DateTime, nullable=True
    )  # Estimated delivery time

    def __repr__(self):
        return f"<Order {self.id} - {self.sender} - {self.caller_name} - {self.status}>"

    def get_status_display(self):
        """Returns a user-friendly status description based on the status code"""
        # Check if status_code attribute exists (for backward compatibility)
        if not hasattr(self, "status_code") or self.status_code is None:
            # Fallback to traditional status mapping
            status_map = {
                "NEW": "Your order has been received and is being processed",
                "ACCEPTED": "Your order has been accepted and is being prepared",
                "PREPARING": "Your order is now being prepared in the kitchen",
                "READY": "Your order is ready for pickup! 🎉",
                "COMPLETED": "Your order has been completed. Thank you for your order! 🙏",
                "FAILED": "There was an issue with your order. Please call us at (833) 324-7207",
                "REJECTED": "We're sorry, but your order could not be processed. Please call us at (833) 324-7207",
                "CANCELLED": "Your order has been cancelled",
            }
            return status_map.get(
                self.status, self.status or "Your order is being processed"
            )

        # POS statuses - use more customer-friendly language
        if self.status_code == 10:
            return "Your order has been received by the restaurant"
        elif self.status_code == 20:
            return "Your order has been confirmed by the restaurant"
        elif self.status_code == 40:
            return "Your order has been sent to the kitchen"
        elif self.status_code == 50:
            return "Your order is now being prepared in the kitchen"
        elif self.status_code == 60:
            return "The preparation of your order has been completed"
        elif self.status_code == 70:
            return "Your order is ready for pickup! You can come to the restaurant now"
        elif self.status_code == 90:
            return "Your order has been completed. Thank you for ordering with us!"
        elif self.status_code == 95:
            return "Your order has been completed. Thank you for ordering with us!"
        elif self.status_code == 110:
            return "Your order has been canceled. Please call us at (833) 324-7207 if you didn't request this"
        elif self.status_code == 120:
            return "There was an issue with your order. Please call us at (833) 324-7207 for assistance"

        # Delivery statuses - more detailed for customer tracking
        elif self.status_code == 76:
            return "We're looking for a delivery courier for your order"
        elif self.status_code == 81:
            return "A courier has been assigned to deliver your order"
        elif self.status_code == 83:
            return "Your courier is on the way to the restaurant to pick up your order"
        elif self.status_code == 85:
            return "Your courier has arrived at the restaurant and is collecting your order"
        elif self.status_code == 87:
            return (
                "Your order is on the way to you! The courier has left the restaurant"
            )
        elif self.status_code == 89:
            return "Your courier has arrived at your location with your order"
        elif self.status_code == 115:
            return "The delivery for your order has been canceled. Please call us at (833) 324-7207"

        # System statuses - simplified for customers
        elif self.status_code == 1:
            return "Your order has been received by our system"
        elif self.status_code == 2:
            return "Your order has been sent to the restaurant"
        elif self.status_code == 25:
            return "Your order is scheduled and will be prepared at the requested time"

        # Default fallback - customer friendly
        return (
            "Your order is being processed"
            if not self.status
            else f"Your order status: {self.status}"
        )


class ContactRequest(Base, TimestampMixin):
    """
    Model for storing customer contact requests for callbacks or menu notifications.
    """
    __tablename__ = "contact_requests"
    
    id = Column(String(36), primary_key=True)
    customer_name = Column(String(255))
    customer_phone = Column(String(20))
    customer_email = Column(String(255))
    message = Column(String(500))
    request_type = Column(String(50))  # callback, menu_notification, etc.
    status = Column(String(50), default='pending')  # pending, completed, etc.
    timestamp = Column(DateTime, default=func.current_timestamp())
    
    def __repr__(self):
        return f"<ContactRequest {self.id}: {self.customer_name}, Type: {self.request_type}, Status: {self.status}>"
