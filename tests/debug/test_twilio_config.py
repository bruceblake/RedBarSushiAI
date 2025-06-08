"""
Debug Twilio configuration and webhook setup.
"""

import os
import httpx
import asyncio


async def test_ngrok_webhook():
    """Test if ngrok URL is accessible and webhook is configured correctly."""
    ngrok_url = "https://fd17-149-22-84-153.ngrok-free.app"
    
    print(f"🔍 Testing ngrok URL: {ngrok_url}")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test health endpoint
            response = await client.get(f"{ngrok_url}/healthcheck")
            print(f"✅ Health check: {response.status_code}")
            
            # Test voice webhook
            test_data = {
                "CallSid": "CAtest123",
                "From": "+15551234567",
                "To": "+15559876543",
                "CallStatus": "ringing"
            }
            
            response = await client.post(
                f"{ngrok_url}/voice/",
                data=test_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            print(f"✅ Voice webhook: {response.status_code}")
            if response.status_code == 200:
                print(f"📝 TwiML response: {response.text[:200]}...")
            else:
                print(f"❌ Error response: {response.text}")
                
    except Exception as e:
        print(f"❌ ngrok URL not accessible: {e}")


def check_twilio_config():
    """Check Twilio configuration."""
    print("\n🔧 TWILIO CONFIGURATION CHECK")
    print("=" * 50)
    
    account_sid = os.getenv('TWILIO_ACCOUNT_SID', 'NOT_SET')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN', 'NOT_SET')
    phone_number = os.getenv('TWILIO_PHONE_NUMBER', 'NOT_SET')
    
    print(f"Account SID: {account_sid}")
    print(f"Auth Token: {'SET' if auth_token != 'NOT_SET' else 'NOT_SET'}")
    print(f"Phone Number: {phone_number}")
    
    if account_sid.startswith('ACxxxxxxxx'):
        print("❌ PROBLEM: Twilio Account SID is placeholder!")
        print("   You need to set your real Twilio Account SID")
        
    if auth_token.startswith('your-auth'):
        print("❌ PROBLEM: Twilio Auth Token is placeholder!")
        print("   You need to set your real Twilio Auth Token")
        
    if phone_number == '+1234567890':
        print("❌ PROBLEM: Twilio Phone Number is placeholder!")
        print("   You need to set your real Twilio phone number")


def check_webhook_url():
    """Check webhook URL configuration."""
    print("\n🌐 WEBHOOK URL CHECK")
    print("=" * 50)
    
    base_url = os.getenv('BASE_URL', 'NOT_SET')
    print(f"BASE_URL env var: {base_url}")
    
    expected_webhook = "https://fd17-149-22-84-153.ngrok-free.app/voice/"
    print(f"Expected webhook URL: {expected_webhook}")
    
    print("\n📋 TWILIO CONSOLE CHECKLIST:")
    print("1. Go to Twilio Console → Phone Numbers")
    print("2. Click on your phone number")
    print("3. Set webhook URL to: https://fd17-149-22-84-153.ngrok-free.app/voice/")
    print("4. Set HTTP method to: POST")
    print("5. Save configuration")


async def main():
    """Run all diagnostics."""
    print("🚨 DIAGNOSING PHONE CALL ISSUES")
    print("=" * 50)
    
    check_twilio_config()
    check_webhook_url()
    await test_ngrok_webhook()
    
    print("\n🔍 COMMON ISSUES AND SOLUTIONS:")
    print("=" * 50)
    print("1. ❌ Twilio credentials are placeholders")
    print("   → Set real TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER")
    
    print("\n2. ❌ Webhook URL not configured in Twilio Console")
    print("   → Set webhook to: https://fd17-149-22-84-153.ngrok-free.app/voice/")
    
    print("\n3. ❌ ngrok tunnel expired/changed")
    print("   → Get new ngrok URL and update Twilio webhook")
    
    print("\n4. ❌ App not running on ngrok URL")
    print("   → Make sure your app is running and ngrok is forwarding")
    
    print("\n5. ❌ Firewall/network issues")
    print("   → Check if ngrok URL is accessible from internet")


if __name__ == "__main__":
    asyncio.run(main())