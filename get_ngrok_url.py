#!/usr/bin/env python3
"""
Get the current ngrok public URL and show Twilio webhook configuration.
"""

import requests
import json
import sys

def get_ngrok_url():
    """Get the current ngrok public HTTPS URL."""
    try:
        # Query ngrok API
        response = requests.get('http://localhost:4040/api/tunnels')
        data = response.json()
        
        # Find HTTPS tunnel
        tunnels = data.get('tunnels', [])
        https_tunnel = next((t for t in tunnels if t.get('proto') == 'https'), None)
        
        if https_tunnel:
            public_url = https_tunnel['public_url']
            return public_url
        else:
            print("❌ No HTTPS tunnel found")
            print("Make sure ngrok is running: docker-compose -f docker-compose.dev.yml up -d")
            return None
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to ngrok")
        print("Make sure ngrok is running: docker-compose -f docker-compose.dev.yml up -d")
        return None
    except Exception as e:
        print(f"❌ Error getting ngrok URL: {e}")
        return None

def main():
    """Main function."""
    print("🔍 Getting ngrok URL...\n")
    
    public_url = get_ngrok_url()
    
    if public_url:
        webhook_url = f"{public_url}/voice/webhook"
        
        print("✅ ngrok is running!\n")
        print(f"📡 Public URL: {public_url}")
        print(f"📞 Twilio Webhook URL: {webhook_url}")
        print("\n" + "="*60)
        print("📋 COPY THIS TO TWILIO:")
        print("="*60)
        print(f"\n{webhook_url}\n")
        print("="*60)
        print("\n📱 Configure in Twilio Console:")
        print("1. Go to: https://console.twilio.com/us1/develop/phone-numbers/manage/incoming")
        print("2. Click on your phone number")
        print("3. In 'Voice Configuration' section:")
        print("   - Configure with: Webhooks, TwiML Bins, Functions, Studio, or Proxy")
        print("   - A call comes in: Webhook")
        print(f"   - URL: {webhook_url}")
        print("   - HTTP Method: POST")
        print("4. Click 'Save configuration'\n")
        
        # Try to copy to clipboard if pyperclip is available
        try:
            import pyperclip
            pyperclip.copy(webhook_url)
            print("✅ Webhook URL copied to clipboard!")
        except ImportError:
            print("💡 Tip: Install pyperclip to auto-copy: pip install pyperclip")
        
        return 0
    else:
        return 1

if __name__ == "__main__":
    sys.exit(main())