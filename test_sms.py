#!/usr/bin/env python
"""
Test script for verifying SMS notifications.
This will send a test SMS to verify your Twilio integration is working properly.
"""

import os
import sys
import logging
import argparse
from app import create_app, twilio_client
from app.models import Order
from app import db
from twilio.base.exceptions import TwilioRestException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get Twilio phone number from environment or config
try:
    from app.config import TWILIO_NUMBER
except ImportError:
    TWILIO_NUMBER = os.environ.get('TWILIO_NUMBER')

def send_test_sms(phone_number, app):
    """Send a test SMS to verify Twilio functionality"""
    try:
        # Validate phone number format
        if not phone_number.startswith('+'):
            phone_number = f"+{phone_number}"
            
        # Log attempt
        logger.info(f"Attempting to send test SMS to {phone_number}")
        
        # Create the message
        message = twilio_client.messages.create(
            body="Hello from Red Bar Sushi AI! This is a test message to verify SMS notifications are working.",
            from_=TWILIO_NUMBER,
            to=phone_number,
            status_callback=f"{os.environ.get('BASE_URL', 'https://redbarsushiai.onrender.com')}/sms_status_callback"
        )
        
        logger.info(f"Message sent successfully! SID: {message.sid}")
        logger.info(f"Status: {message.status}")
        
        # Store the message SID in the database for tracking
        with app.app_context():
            try:
                # Create a placeholder order for testing
                test_order = Order(
                    id=f"test-{message.sid[:8]}",
                    sender=phone_number,
                    caller_name="SMS Test",
                    message="Test SMS message",
                    sms_sid=message.sid,
                    sms_status=message.status
                )
                db.session.add(test_order)
                db.session.commit()
                logger.info(f"Created test order record with ID: {test_order.id}")
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error creating test order: {e}")
        
        return True, message.sid
        
    except TwilioRestException as e:
        logger.error(f"Twilio error: {e.msg}")
        logger.error(f"Error code: {e.code}")
        logger.error(f"More info: {e.details if hasattr(e, 'details') else 'No details available'}")
        return False, str(e)
        
    except Exception as e:
        logger.error(f"General error: {e}")
        return False, str(e)

def verify_twilio_config():
    """Check if Twilio is properly configured"""
    required_vars = ['TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'TWILIO_NUMBER']
    
    missing_vars = []
    for var in required_vars:
        if not os.environ.get(var):
            try:
                # Try to get from config
                import app.config
                if not hasattr(app.config, var):
                    missing_vars.append(var)
            except (ImportError, AttributeError):
                missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing required Twilio configuration: {', '.join(missing_vars)}")
        return False
    
    return True

def main():
    """Run the SMS test with command line arguments"""
    parser = argparse.ArgumentParser(description='Test Twilio SMS functionality')
    parser.add_argument('phone_number', help='Phone number to send test SMS (with or without country code)')
    parser.add_argument('--check-config', action='store_true', help='Only check Twilio configuration without sending')
    args = parser.parse_args()
    
    # Create app context
    app = create_app()
    
    # Check Twilio configuration
    if not verify_twilio_config():
        logger.error("Twilio is not properly configured. Please check your environment variables.")
        
        # Print troubleshooting information
        print("\nTroubleshooting steps:")
        print("1. Check your Twilio account SID and auth token")
        print("2. Verify your Twilio phone number is active")
        print("3. Make sure the BASE_URL environment variable is set correctly")
        return False
        
    # Exit if only checking config
    if args.check_config:
        logger.info("Twilio configuration looks good!")
        return True
    
    # Send test SMS
    success, result = send_test_sms(args.phone_number, app)
    
    if success:
        print(f"✅ Message sent successfully! SID: {result}")
        print("Check your phone for the message and monitor the app logs for status callbacks")
        return True
    else:
        print(f"❌ Failed to send SMS: {result}")
        
        # Provide troubleshooting information
        print("\nTroubleshooting steps:")
        print("1. Check your Twilio account SID and auth token")
        print("2. Verify your Twilio phone number is active")
        print("3. Make sure the recipient number is in a valid format (+1XXXXXXXXXX)")
        print("4. Check if your Twilio account has sufficient credits")
        print("5. Verify your BASE_URL environment variable is set correctly")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)