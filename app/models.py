# app/models.py
from app import db

class Order(db.Model):
    __tablename__ = 'order'
    id = db.Column(db.String(36), primary_key=True)
    sender = db.Column(db.String(15), nullable=False)
    caller_name = db.Column(db.String(50), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(20), default='NEW')
    status_code = db.Column(db.Integer, nullable=True)  # Deliverect status code
    status_updated_at = db.Column(db.DateTime, nullable=True)  # When status last changed
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    location_id = db.Column(db.String(36), nullable=True)
    sms_sid = db.Column(db.String(50), nullable=True)
    sms_status = db.Column(db.String(20), nullable=True)
    sms_error_code = db.Column(db.Integer, nullable=True)
    sms_error_message = db.Column(db.String(255), nullable=True)
    # Delivery tracking fields
    delivery_status = db.Column(db.String(30), nullable=True)  # Delivery-specific status
    delivery_status_code = db.Column(db.Integer, nullable=True)  # Delivery status code
    courier_name = db.Column(db.String(50), nullable=True)  # Name of delivery courier
    courier_phone = db.Column(db.String(20), nullable=True)  # Phone of delivery courier
    estimated_delivery_time = db.Column(db.DateTime, nullable=True)  # Estimated delivery time

    def __repr__(self):
        return f"<Order {self.id} - {self.sender} - {self.caller_name} - {self.status}>"
        
    def get_status_display(self):
        """Returns a user-friendly status description based on the status code"""
        # POS statuses
        if self.status_code == 10:
            return "New - Received by restaurant"
        elif self.status_code == 20:
            return "Accepted - Order confirmed"
        elif self.status_code == 40:
            return "Printed - Ticket sent to kitchen"
        elif self.status_code == 50:
            return "Preparing - In preparation"
        elif self.status_code == 60:
            return "Prepared - Cooking completed"
        elif self.status_code == 70:
            return "Pickup Ready - Ready for collection"
        elif self.status_code == 90:
            return "Finalized - Order completed"
        elif self.status_code == 95:
            return "Auto-Finalized - Order handled"
        elif self.status_code == 110:
            return "Canceled - Order canceled"
        elif self.status_code == 120:
            return "Failed - Order failed"
            
        # Delivery statuses
        elif self.status_code == 76:
            return "Delivery Created - Looking for courier"
        elif self.status_code == 81:
            return "Delivery Confirmed - Courier assigned"
        elif self.status_code == 83:
            return "En Route to Pickup - Courier approaching restaurant"
        elif self.status_code == 85:
            return "Arrived at Pickup - Courier at restaurant"
        elif self.status_code == 87:
            return "En Route To Dropoff - Courier heading to you"
        elif self.status_code == 89:
            return "Arrived At Drop Off - Courier arrived at your location"
        elif self.status_code == 115:
            return "Delivery Canceled - Delivery was canceled"
            
        # System statuses
        elif self.status_code == 1:
            return "Parsed - Order received by system"
        elif self.status_code == 2:
            return "Received by POS - Order sent to restaurant"
        elif self.status_code == 25:
            return "Scheduled - Order awaiting scheduled time"
        
        # Default fallback
        return self.status or "Processing"

class Location(db.Model):
    __tablename__ = 'location'
    id = db.Column(db.String(36), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='inactive')  # registered, active, inactive
    webhook_base = db.Column(db.String(255), nullable=True)
    api_key = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    def __repr__(self):
        return f"<Location {self.id} - {self.name} - {self.status}>"