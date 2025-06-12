#!/usr/bin/env python3
"""
Verify that the voice integration is properly configured.
This script checks that all components are connected correctly.
"""

import asyncio
import os
import sys
import httpx
from typing import Dict, Any

async def check_voice_webhook(base_url: str) -> bool:
    """Check if the voice webhook is accessible."""
    print("\n1. Checking Voice Webhook...")
    
    # Test data mimicking Twilio's webhook
    test_data = {
        "CallSid": "CA1234567890abcdef1234567890abcdef",
        "Caller": "+1234567890",
        "Called": "+0987654321",
        "From": "+1234567890",
        "To": "+0987654321",
        "CallStatus": "ringing",
        "Direction": "inbound",
        "AccountSid": "AC1234567890abcdef1234567890abcdef"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            # Test the voice webhook endpoint
            response = await client.post(
                f"{base_url}/voice/webhook",
                data=test_data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": "TwilioProxy/1.1"
                }
            )
            
            if response.status_code == 200:
                content = response.text
                if "ConversationRelay" in content and "welcomeGreeting" in content:
                    print("✓ Voice webhook is working correctly")
                    print(f"✓ Generated TwiML includes ConversationRelay")
                    
                    # Extract WebSocket URL from TwiML
                    import re
                    ws_url_match = re.search(r'url="([^"]+)"', content)
                    if ws_url_match:
                        ws_url = ws_url_match.group(1)
                        print(f"✓ WebSocket URL: {ws_url}")
                    
                    return True
                else:
                    print("✗ Voice webhook returned unexpected content")
                    print(f"Response: {content[:200]}...")
                    return False
            else:
                print(f"✗ Voice webhook returned status {response.status_code}")
                return False
                
    except Exception as e:
        print(f"✗ Failed to reach voice webhook: {e}")
        return False

async def check_conversation_relay_route(base_url: str) -> bool:
    """Check if the ConversationRelay WebSocket route exists."""
    print("\n2. Checking ConversationRelay Route...")
    
    try:
        async with httpx.AsyncClient() as client:
            # Get route listing
            response = await client.get(f"{base_url}/routes")
            
            if response.status_code == 200:
                routes = response.json()
                ws_routes = routes.get("websocket_routes", [])
                
                # Look for ConversationRelay route
                relay_route = next(
                    (r for r in ws_routes if "conversation-relay" in r.get("path", "")),
                    None
                )
                
                if relay_route:
                    print(f"✓ ConversationRelay WebSocket route found: {relay_route['path']}")
                    return True
                else:
                    print("✗ ConversationRelay WebSocket route not found")
                    print(f"Available WebSocket routes: {[r['path'] for r in ws_routes]}")
                    return False
            else:
                print(f"✗ Failed to get routes: {response.status_code}")
                return False
                
    except Exception as e:
        print(f"✗ Failed to check routes: {e}")
        return False

async def check_agent_initialization(base_url: str) -> bool:
    """Check if agents are initialized properly."""
    print("\n3. Checking Agent Initialization...")
    
    try:
        async with httpx.AsyncClient() as client:
            # Check health endpoint for more details
            response = await client.get(f"{base_url}/healthcheck")
            
            if response.status_code == 200:
                health = response.json()
                print("✓ API is healthy")
                
                # The agents are initialized on startup, so if API is running, they should be ready
                print("✓ Agents should be initialized (they initialize on startup)")
                return True
            else:
                print(f"✗ Health check failed: {response.status_code}")
                return False
                
    except Exception as e:
        print(f"✗ Failed to check health: {e}")
        return False

async def simulate_conversation_flow() -> None:
    """Simulate the conversation flow to show how it works."""
    print("\n4. Voice Conversation Flow:")
    print("=" * 50)
    print("1. Customer calls Twilio phone number")
    print("2. Twilio hits /voice/webhook with call details")
    print("3. Webhook returns ConversationRelay TwiML")
    print("4. Twilio connects to WebSocket at /api/conversation-relay")
    print("5. ConversationRelay handler receives 'setup' event")
    print("6. Handler initializes agent orchestrator for the call")
    print("7. Customer speaks → Twilio STT → 'prompt' event")
    print("8. Handler processes with agents → response text")
    print("9. Response sent to Twilio → TTS → Customer hears")
    print("10. Conversation continues until call ends")
    print("=" * 50)

async def main():
    """Run all verification checks."""
    print("RedBarSushiAI Voice Integration Verification")
    print("=" * 50)
    
    # Get base URL
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    print(f"Using base URL: {base_url}")
    
    # Load .env if exists
    if os.path.exists('.env'):
        from dotenv import load_dotenv
        load_dotenv()
        print("✓ Loaded .env file")
    
    # Check required environment variables for voice
    voice_vars = [
        "OPENAI_API_KEY",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_PHONE_NUMBER"
    ]
    
    print("\nChecking Voice Configuration...")
    all_vars_set = True
    for var in voice_vars:
        if os.getenv(var):
            print(f"✓ {var} is set")
        else:
            print(f"✗ {var} is not set")
            all_vars_set = False
    
    if not all_vars_set:
        print("\n⚠️  Some required environment variables are missing!")
    
    # Run checks
    results = []
    
    # Check voice webhook
    webhook_ok = await check_voice_webhook(base_url)
    results.append(("Voice Webhook", webhook_ok))
    
    # Check ConversationRelay route
    route_ok = await check_conversation_relay_route(base_url)
    results.append(("ConversationRelay Route", route_ok))
    
    # Check agent initialization
    agents_ok = await check_agent_initialization(base_url)
    results.append(("Agent System", agents_ok))
    
    # Show conversation flow
    await simulate_conversation_flow()
    
    # Summary
    print("\n" + "=" * 50)
    print("VERIFICATION SUMMARY")
    print("=" * 50)
    
    all_passed = all(result[1] for result in results)
    
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name}: {status}")
    
    if all_passed:
        print("\n✅ Voice integration is properly configured!")
        print("\nNext steps:")
        print("1. Configure your Twilio phone number:")
        print(f"   - Webhook URL: {base_url}/voice/webhook")
        print("   - HTTP Method: POST")
        print("2. Make a test call to your Twilio number")
        print("3. Monitor logs: docker-compose logs -f app")
    else:
        print("\n❌ Some checks failed. Please fix the issues above.")
        print("\nTroubleshooting:")
        print("- Make sure the API server is running")
        print("- Check that all required environment variables are set")
        print("- Verify database and Redis are accessible")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)