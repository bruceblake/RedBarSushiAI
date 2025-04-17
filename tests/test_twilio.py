#\!/usr/bin/env python
import os
from app import twilio_client
from app.config import TWILIO_NUMBER

def test_twilio_auth():
    print("Testing Twilio authentication...")
    try:
        # Try to get account info
        accounts = twilio_client.api.accounts.list()
        print(f"Account status: {accounts[0].status}")
        print("✓ Successfully authenticated with Twilio")
        return True
    except Exception as e:
        print(f"✗ Twilio authentication error: {e}")
        return False

def test_send_sms(phone_number='+15555555555'):
    # Skip this test in pytest context
    import inspect
    if inspect.currentframe().f_back.f_globals.get('__name__') == 'pytest':
        import pytest
        pytest.skip("This test requires proper Twilio credentials and a real phone number")
    
    print(f"Testing SMS to {phone_number} from {TWILIO_NUMBER}...")
    try:
        # Send a test message
        message = twilio_client.messages.create(
            body="Test message from Red Bar Sushi AI",
            from_=TWILIO_NUMBER,
            to=phone_number
        )
        print(f"✓ Message sent! SID: {message.sid}, Status: {message.status}")
        return True
    except Exception as e:
        print(f"✗ SMS sending error: {e}")
        return False

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python test_twilio.py [phone_number]")
        sys.exit(1)
        
    phone_number = sys.argv[1]
    
    # Make sure phone number is in E.164 format
    if not phone_number.startswith('+'):
        phone_number = f"+{phone_number}"
        
    if test_twilio_auth():
        test_send_sms(phone_number)
