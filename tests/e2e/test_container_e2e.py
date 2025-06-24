"""
E2E tests designed to run inside the Docker container.

This module tests the complete flow using internal container networking.
"""

import pytest
import asyncio
import json
import httpx
import websockets
from typing import Dict, Any


class ContainerE2ETest:
    """E2E test for running inside Docker container."""
    
    def __init__(self):
        # Use internal container URLs
        self.base_url = "http://localhost:8080"
        self.ws_url = "ws://localhost:8080"
        
    async def test_api_health(self) -> Dict[str, Any]:
        """Test API health endpoints."""
        async with httpx.AsyncClient() as client:
            # Test health check
            response = await client.get(f"{self.base_url}/healthcheck")
            assert response.status_code == 200
            health_data = response.json()
            assert health_data["status"] == "ok"
            
            # Test API routes
            response = await client.get(f"{self.base_url}/api/debug-routes")
            assert response.status_code == 200
            routes_data = response.json()
            
            return {
                "health": health_data,
                "routes_count": routes_data.get("count", 0)
            }
            
    async def test_twiml_generation(self) -> Dict[str, Any]:
        """Test TwiML generation."""
        webhook_data = {
            'CallSid': 'CAtest123456789',
            'From': '+15551234567',
            'To': '+17036467799',
            'CallStatus': 'ringing',
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/voice/",
                data=webhook_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            assert response.status_code == 200
            twiml = response.text
            
            # Verify TwiML structure
            assert "<?xml" in twiml
            assert "<ConversationRelay" in twiml
            assert "welcomeGreeting" in twiml
            
            return {
                "status_code": response.status_code,
                "has_conversation_relay": "<ConversationRelay" in twiml,
                "has_websocket_url": "/api/conversation-relay" in twiml
            }
            
    async def test_websocket_connection(self) -> Dict[str, Any]:
        """Test WebSocket connection to ConversationRelay."""
        ws_endpoint = f"{self.ws_url}/api/conversation-relay"
        
        try:
            async with websockets.connect(ws_endpoint) as websocket:
                # Send setup message
                setup_message = {
                    "type": "setup",
                    "sessionId": "test_session",
                    "callSid": "CAtest123",
                    "from": "+15551234567",
                    "to": "+17036467799",
                    "callStatus": "in-progress"
                }
                
                await websocket.send(json.dumps(setup_message))
                
                # Wait for any response
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    response_data = json.loads(response)
                    
                    # Send a test prompt
                    prompt_message = {
                        "type": "prompt",
                        "voicePrompt": "Hello",
                        "lang": "en-US",
                        "last": True
                    }
                    
                    await websocket.send(json.dumps(prompt_message))
                    
                    # Wait for AI response
                    ai_response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    ai_data = json.loads(ai_response)
                    
                    await websocket.close()
                    
                    return {
                        "connected": True,
                        "setup_response": response_data,
                        "ai_response": ai_data,
                        "success": True
                    }
                    
                except asyncio.TimeoutError:
                    return {
                        "connected": True,
                        "setup_response": None,
                        "ai_response": None,
                        "success": False,
                        "error": "Response timeout"
                    }
                    
        except Exception as e:
            return {
                "connected": False,
                "error": str(e),
                "success": False
            }
            
    async def test_menu_endpoints(self) -> Dict[str, Any]:
        """Test menu API endpoints."""
        async with httpx.AsyncClient() as client:
            # Test menu categories
            response = await client.get(f"{self.base_url}/menu/categories")
            assert response.status_code == 200
            categories = response.json()
            
            # Test menu items
            response = await client.get(f"{self.base_url}/menu/items")
            assert response.status_code == 200
            items = response.json()
            
            return {
                "categories_count": len(categories),
                "items_count": len(items),
                "has_menu_data": len(items) > 0
            }
            
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all E2E tests."""
        print("\n" + "="*60)
        print("🧪 CONTAINER E2E TEST SUITE")
        print("="*60 + "\n")
        
        results = {}
        
        # Test 1: API Health
        print("1️⃣ Testing API Health...")
        try:
            results["api_health"] = await self.test_api_health()
            print(f"✅ API Health: PASSED")
            print(f"   - Status: {results['api_health']['health']['status']}")
            print(f"   - Routes: {results['api_health']['routes_count']}")
        except Exception as e:
            results["api_health"] = {"error": str(e)}
            print(f"❌ API Health: FAILED - {e}")
            
        # Test 2: TwiML Generation
        print("\n2️⃣ Testing TwiML Generation...")
        try:
            results["twiml"] = await self.test_twiml_generation()
            print(f"✅ TwiML Generation: PASSED")
            print(f"   - Has ConversationRelay: {results['twiml']['has_conversation_relay']}")
            print(f"   - Has WebSocket URL: {results['twiml']['has_websocket_url']}")
        except Exception as e:
            results["twiml"] = {"error": str(e)}
            print(f"❌ TwiML Generation: FAILED - {e}")
            
        # Test 3: WebSocket Connection
        print("\n3️⃣ Testing WebSocket Connection...")
        try:
            results["websocket"] = await self.test_websocket_connection()
            if results["websocket"]["success"]:
                print(f"✅ WebSocket: PASSED")
                print(f"   - Connected: {results['websocket']['connected']}")
                if results["websocket"].get("ai_response"):
                    ai_text = results["websocket"]["ai_response"].get("text", "")[:100]
                    print(f"   - AI Response: {ai_text}...")
            else:
                print(f"⚠️ WebSocket: PARTIAL")
                print(f"   - Connected: {results['websocket']['connected']}")
                print(f"   - Error: {results['websocket'].get('error', 'Unknown')}")
        except Exception as e:
            results["websocket"] = {"error": str(e), "success": False}
            print(f"❌ WebSocket: FAILED - {e}")
            
        # Test 4: Menu Endpoints
        print("\n4️⃣ Testing Menu Endpoints...")
        try:
            results["menu"] = await self.test_menu_endpoints()
            print(f"✅ Menu Endpoints: PASSED")
            print(f"   - Categories: {results['menu']['categories_count']}")
            print(f"   - Items: {results['menu']['items_count']}")
        except Exception as e:
            results["menu"] = {"error": str(e)}
            print(f"❌ Menu Endpoints: FAILED - {e}")
            
        # Summary
        print("\n" + "="*60)
        print("📊 TEST SUMMARY")
        print("="*60)
        
        passed = sum(1 for r in results.values() if isinstance(r, dict) and "error" not in r)
        total = len(results)
        
        print(f"✅ Passed: {passed}/{total}")
        print(f"❌ Failed: {total - passed}/{total}")
        print(f"📈 Success Rate: {(passed/total)*100:.1f}%")
        print("="*60 + "\n")
        
        results["summary"] = {
            "passed": passed,
            "failed": total - passed,
            "total": total,
            "success_rate": passed / total
        }
        
        return results


# Pytest functions
@pytest.mark.asyncio
async def test_container_e2e_suite():
    """Run the complete container E2E test suite."""
    test = ContainerE2ETest()
    results = await test.run_all_tests()
    
    assert results["summary"]["success_rate"] >= 0.75, f"Too many tests failed: {results['summary']}"
    

@pytest.mark.asyncio
async def test_container_api_health():
    """Test API health only."""
    test = ContainerE2ETest()
    result = await test.test_api_health()
    
    assert "error" not in result, f"API health check failed: {result}"
    

@pytest.mark.asyncio
async def test_container_twiml():
    """Test TwiML generation only."""
    test = ContainerE2ETest()
    result = await test.test_twiml_generation()
    
    assert result["has_conversation_relay"], "TwiML missing ConversationRelay element"
    assert result["has_websocket_url"], "TwiML missing WebSocket URL"


if __name__ == "__main__":
    # Run directly
    async def main():
        test = ContainerE2ETest()
        await test.run_all_tests()
        
    asyncio.run(main())