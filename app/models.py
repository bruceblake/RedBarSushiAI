# app/models.py
from app import db

class Order(db.Model):
    __tablename__ = 'order'
    id = db.Column(db.String(36), primary_key=True)
    sender = db.Column(db.String(15), nullable=False)
    caller_name = db.Column(db.String(50), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(20), default='NEW')
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    location_id = db.Column(db.String(36), nullable=True)
    sms_sid = db.Column(db.String(50), nullable=True)
    sms_status = db.Column(db.String(20), nullable=True)
    sms_error_code = db.Column(db.Integer, nullable=True)
    sms_error_message = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f"<Order {self.id} - {self.sender} - {self.caller_name} - {self.message}>"

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