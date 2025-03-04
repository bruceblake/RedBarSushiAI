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

    def __repr__(self):
        return f"<Order {self.id} - {self.sender} - {self.caller_name} - {self.message}>"