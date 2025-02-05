# app/__init__.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import stripe
from twilio.rest import Client
import logging
from app.config import *
import os

# Initialize SQLAlchemy
db = SQLAlchemy()

# Initialize Twilio client and Stripe
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
stripe.api_key = STRIPE_API_KEY

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS
    app.secret_key = APP_SECRET_KEY

    # Initialize the database
    db.init_app(app)

    # Register Blueprints for routes
    from app.routes.voice import voice_bp
    from app.routes.menu import menu_bp
    from app.routes.order import order_bp

    app.register_blueprint(voice_bp)
    app.register_blueprint(menu_bp)
    app.register_blueprint(order_bp)

    # Configure logging
    logging.basicConfig(
        filename='progress.log',
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    return app
