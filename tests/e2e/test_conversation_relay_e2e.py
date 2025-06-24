"""
E2E tests for Twilio ConversationRelay integration.

This module tests the complete flow through Twilio ConversationRelay,
simulating how Twilio sends webhook requests and WebSocket messages.
"""

import pytest
import asyncio
import json
import uuid
import httpx
import websockets
from typing import Dict, Any, Optional
from datetime import datetime
import os

# Get configuration from environment or use defaults
NGROK_URL = os.getenv("NGROK_URL", "https://fd17-149-22-84-153.ngrok-free.app")
USE_NGROK = os.getenv("USE_NGROK", "true").lower() == "true"
BASE_URL = NGROK_URL if USE_NGROK else "http://localhost:8000"


class ConversationRelayE2ETest:
    """E2E test for ConversationRelay integration."""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.ws_url = base_url.replace("https://", "wss://").replace("http://", "ws://")
        self.call_sid = f"CA{uuid.uuid4().hex[:24]}"
        self.session_id = f"session_{uuid.uuid4().hex[:8]}"
        
    async def test_twiml_generation(self) -> Dict[str, Any]:
        """Test TwiML generation endpoint."""
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'TwilioProxy/1.1',
        }
        
        # Add ngrok headers if needed
        if USE_NGROK:
            headers['ngrok-skip-browser-warning'] = 'true'
            
        # Twilio webhook data
        webhook_data = {
            'CallSid': self.call_sid,
            'AccountSid': 'ACtest1234567890',
            'From': '+15551234567',
            'To': '+17036467799',
            'CallStatus': 'ringing',
            'Direction': 'inbound',
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            print(f"📞 Testing TwiML generation at {self.base_url}/voice/")
            
            response = await client.post(
                f"{self.base_url}/voice/",
                data=webhook_data,
                headers=headers
            )
            
            result = {
                "status_code": response.status_code,
                "twiml": response.text if response.status_code == 200 else None,
                "error": response.text if response.status_code != 200 else None
            }
            
            if response.status_code == 200:
                # Verify TwiML structure
                twiml = response.text
                assert "<?xml" in twiml
                assert "<ConversationRelay" in twiml
                assert f"{self.ws_url}/api/conversation-relay" in twiml
                print(f"✅ TwiML generated successfully")
                
            return result
            
    async def test_conversation_relay_websocket(self) -> Dict[str, Any]:
        """Test ConversationRelay WebSocket connection."""
        ws_endpoint = f"{self.ws_url}/api/conversation-relay"
        
        # Add headers for ngrok if needed
        headers = {}
        if USE_NGROK:
            headers = {
                'User-Agent': 'TwilioProxy/1.1',
            }
            
        print(f"🌐 Connecting to WebSocket: {ws_endpoint}")
        
        try:
            async with websockets.connect(ws_endpoint, extra_headers=headers) as websocket:
                print(f"✅ WebSocket connected")
                
                # Send setup message (simulating Twilio)
                setup_message = {
                    "type": "setup",
                    "sessionId": self.session_id,
                    "callSid": self.call_sid,
                    "from": "+15551234567",
                    "to": "+17036467799",
                    "callStatus": "in-progress",
                    "welcomeGreeting": None  # Let the system send its own greeting
                }
                
                await websocket.send(json.dumps(setup_message))
                print(f"📤 Sent setup message")
                
                # Wait for any initial response
                responses = []
                try:
                    # Wait up to 5 seconds for initial greeting
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    response_data = json.loads(response)
                    responses.append(response_data)
                    print(f"📨 Received: {response_data}")
                    
                    # If we got a text response (greeting), acknowledge it
                    if response_data.get("type") == "text":
                        print(f"🗣️ System greeting: {response_data.get('text', '')[:100]}...")
                        
                except asyncio.TimeoutError:
                    print("⏱️ No initial greeting received (timeout)")
                    
                # Send a user prompt
                user_message = {
                    "type": "prompt",
                    "voicePrompt": "Hello, I would like to order some sushi",
                    "lang": "en-US",
                    "last": True
                }
                
                await websocket.send(json.dumps(user_message))
                print(f"💬 Sent user prompt: {user_message['voicePrompt']}")
                
                # Wait for response
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    response_data = json.loads(response)
                    responses.append(response_data)
                    
                    if response_data.get("type") == "text":
                        print(f"🤖 AI response: {response_data.get('text', '')[:200]}...")
                        
                except asyncio.TimeoutError:
                    print("⏱️ Response timeout")
                    
                # Send interrupt test
                interrupt_message = {
                    "type": "interrupt",
                    "reason": "speech",
                    "utteranceUntilInterrupt": "Welcome to Red Bar Sushi, how can I"
                }
                
                await websocket.send(json.dumps(interrupt_message))
                print(f"🛑 Sent interrupt message")
                
                # Close gracefully
                await websocket.close()
                
                return {
                    "connected": True,
                    "responses": responses,
                    "message_count": len(responses)
                }
                
        except Exception as e:
            print(f"❌ WebSocket error: {e}")
            return {
                "connected": False,
                "error": str(e),
                "responses": []
            }
            
    async def test_full_conversation_flow(self) -> Dict[str, Any]:
        """Test a complete conversation flow."""
        results = {
            "twiml_test": None,
            "websocket_test": None,
            "success": False
        }
        
        print("\n" + "="*60)
        print("🧪 STARTING CONVERSATIONRELAY E2E TEST")
        print(f"📍 Target: {self.base_url}")
        print(f"🔧 Using ngrok: {USE_NGROK}")
        print("="*60 + "\n")
        
        # Step 1: Test TwiML generation
        print("📋 Step 1: Testing TwiML generation...")
        results["twiml_test"] = await self.test_twiml_generation()
        
        # Step 2: Test WebSocket connection
        print("\n📋 Step 2: Testing ConversationRelay WebSocket...")
        results["websocket_test"] = await self.test_conversation_relay_websocket()
        
        # Determine overall success
        results["success"] = (
            results["twiml_test"] is not None and 
            results["twiml_test"].get("status_code") == 200 and
            results["websocket_test"] is not None and
            results["websocket_test"].get("connected", False)
        )
        
        # Summary
        print("\n" + "="*60)
        print("📊 TEST SUMMARY")
        print("="*60)
        print(f"✅ TwiML Generation: {'PASSED' if results['twiml_test'] and results['twiml_test'].get('status_code') == 200 else 'FAILED'}")
        print(f"✅ WebSocket Connection: {'PASSED' if results['websocket_test'] and results['websocket_test'].get('connected') else 'FAILED'}")
        print(f"✅ Overall Result: {'PASSED' if results['success'] else 'FAILED'}")
        print("="*60 + "\n")
        
        return results


# Test functions
@pytest.mark.asyncio
async def test_conversation_relay_e2e():
    """Run the complete ConversationRelay E2E test."""
    test = ConversationRelayE2ETest()
    results = await test.test_full_conversation_flow()
    
    assert results["success"], f"E2E test failed: {results}"
    

@pytest.mark.asyncio
async def test_conversation_relay_twiml_only():
    """Test only TwiML generation."""
    test = ConversationRelayE2ETest()
    result = await test.test_twiml_generation()
    
    assert result["status_code"] == 200, f"TwiML generation failed: {result}"
    

@pytest.mark.asyncio 
async def test_conversation_relay_websocket_only():
    """Test only WebSocket connection."""
    test = ConversationRelayE2ETest()
    result = await test.test_conversation_relay_websocket()
    
    assert result["connected"], f"WebSocket connection failed: {result}"


if __name__ == "__main__":
    # Run the test directly
    async def main():
        test = ConversationRelayE2ETest()
        await test.test_full_conversation_flow()
        
    asyncio.run(main())