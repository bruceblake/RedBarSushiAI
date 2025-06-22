"""
Comprehensive E2E tests for the complete RedBarSushi voice ordering system.
Tests all major flows, edge cases, and system integration.
"""
import pytest
import asyncio
import json
import websockets
from typing import Dict, Any, List
import httpx
from datetime import datetime
import os

BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8080")
WS_BASE_URL = BASE_URL.replace("http://", "ws://").replace("https://", "wss://")


class VoiceTestClient:
    """Enhanced test client for voice interactions."""
    
    def __init__(self, call_sid: str):
        self.call_sid = call_sid
        self.websocket = None
        self.messages: List[Dict[str, Any]] = []
        self.transcript_history: List[str] = []
        
    async def connect(self):
        """Connect to ConversationRelay WebSocket."""
        ws_url = f"{WS_BASE_URL}/api/conversation-relay"
        self.websocket = await websockets.connect(ws_url)
        
    async def disconnect(self):
        """Disconnect from WebSocket."""
        if self.websocket:
            await self.websocket.close()
            
    async def setup_call(self):
        """Send initial setup message."""
        setup_msg = {
            "type": "setup",
            "sessionId": f"session_{self.call_sid}",
            "callSid": self.call_sid,
            "from": "+15551234567",
            "to": "+17036467799",
            "callStatus": "in-progress"
        }
        await self.websocket.send(json.dumps(setup_msg))
        
    async def send_voice_input(self, text: str):
        """Send voice input and get response."""
        self.transcript_history.append(text)
        prompt_msg = {
            "type": "prompt",
            "voicePrompt": text,
            "lang": "en-US",
            "last": True
        }
        await self.websocket.send(json.dumps(prompt_msg))
        
        # Wait for and return response
        response = await self.get_response()
        return response
        
    async def get_response(self, timeout: float = 30.0):
        """Get AI response with timeout."""
        try:
            msg = await asyncio.wait_for(self.websocket.recv(), timeout=timeout)
            data = json.loads(msg)
            self.messages.append(data)
            
            if data.get("type") == "text":
                return data.get("token", "")
            return None
        except asyncio.TimeoutError:
            return None


class TestCompleteSystemComprehensive:
    """Comprehensive E2E tests for the complete system."""
    
    @pytest.mark.asyncio
    async def test_successful_pickup_order_complete_flow(self):
        """Test a complete successful pickup order from start to finish."""
        client = VoiceTestClient("CAtest_pickup_complete")
        
        try:
            await client.connect()
            await client.setup_call()
            
            # Step 1: Greeting
            greeting = await client.get_response()
            assert greeting is not None
            assert "welcome" in greeting.lower()
            assert "name" in greeting.lower()
            
            # Step 2: Provide name
            response = await client.send_voice_input("Hi, my name is Michael Chen")
            assert "michael" in response.lower() or "chen" in response.lower()
            assert "help" in response.lower()
            
            # Step 3: Start order
            response = await client.send_voice_input("I'd like to place an order for pickup")
            assert any(word in response.lower() for word in ["what", "order", "like"])
            
            # Step 4: Order items with quantities
            response = await client.send_voice_input(
                "I'll have three California rolls, two spicy tuna rolls, and one order of edamame"
            )
            assert "california" in response.lower()
            assert "spicy tuna" in response.lower()
            assert "edamame" in response.lower()
            
            # Verify quantities mentioned
            assert any(str(num) in response for num in ["3", "three", "2", "two", "1", "one"])
            
            # Step 5: Complete order
            response = await client.send_voice_input("That's all for my order")
            assert any(word in response.lower() for word in ["confirm", "total", "correct"])
            
            # Step 6: Confirm order
            response = await client.send_voice_input("Yes, that looks correct")
            assert any(word in response.lower() for word in ["order", "submitted", "ready", "minutes"])
            
            # Step 7: Provide pickup time
            response = await client.send_voice_input("I'll pick it up in 30 minutes")
            assert any(word in response.lower() for word in ["great", "see you", "ready", "confirmed"])
            
        finally:
            await client.disconnect()
    
    @pytest.mark.asyncio
    async def test_menu_inquiry_and_recommendations(self):
        """Test menu inquiries and recommendation flow."""
        client = VoiceTestClient("CAtest_menu_inquiry")
        
        try:
            await client.connect()
            await client.setup_call()
            
            # Get greeting and provide name
            await client.get_response()
            await client.send_voice_input("My name is Lisa")
            
            # Ask about menu
            response = await client.send_voice_input("What kind of sushi do you have?")
            assert any(word in response.lower() for word in ["california", "spicy", "salmon", "roll"])
            
            # Ask for recommendations
            response = await client.send_voice_input("What do you recommend?")
            assert any(word in response.lower() for word in ["popular", "recommend", "try", "delicious"])
            
            # Order based on recommendation
            response = await client.send_voice_input("I'll try the California roll then")
            assert "california" in response.lower()
            
        finally:
            await client.disconnect()
    
    @pytest.mark.asyncio
    async def test_order_modification_flow(self):
        """Test modifying an order before confirmation."""
        client = VoiceTestClient("CAtest_modification")
        
        try:
            await client.connect()
            await client.setup_call()
            
            # Quick setup
            await client.get_response()
            await client.send_voice_input("Sarah Johnson")
            await client.send_voice_input("I want to order")
            
            # Initial order
            await client.send_voice_input("Two California rolls")
            
            # Add more items
            response = await client.send_voice_input("Actually, add a spicy tuna roll too")
            assert "spicy tuna" in response.lower()
            
            # Check cart
            response = await client.send_voice_input("What's in my order so far?")
            assert "california" in response.lower()
            assert "spicy tuna" in response.lower()
            
            # Complete order
            await client.send_voice_input("That's everything")
            
        finally:
            await client.disconnect()
    
    @pytest.mark.asyncio
    async def test_error_recovery_scenarios(self):
        """Test various error recovery scenarios."""
        client = VoiceTestClient("CAtest_errors")
        
        try:
            await client.connect()
            await client.setup_call()
            
            # Greeting
            await client.get_response()
            
            # Test unclear name
            response = await client.send_voice_input("Mmm hmm")
            assert any(word in response.lower() for word in ["sorry", "name", "repeat", "didn't"])
            
            # Provide clear name
            await client.send_voice_input("My name is Robert")
            
            # Test ordering non-existent item
            await client.send_voice_input("I want to order")
            response = await client.send_voice_input("I'll have the unicorn roll")
            assert any(word in response.lower() for word in ["sorry", "don't have", "not available", "menu"])
            
            # Order valid item
            response = await client.send_voice_input("How about California roll instead")
            assert "california" in response.lower()
            
        finally:
            await client.disconnect()
    
    @pytest.mark.asyncio
    async def test_conversation_interruption_handling(self):
        """Test handling of conversation interruptions."""
        client = VoiceTestClient("CAtest_interruption")
        
        try:
            await client.connect()
            await client.setup_call()
            
            # Start conversation
            await client.get_response()
            await client.send_voice_input("James here")
            
            # Simulate interruption with new topic
            response = await client.send_voice_input("Actually, what are your hours?")
            # System should handle topic change gracefully
            assert response is not None
            
            # Return to ordering
            response = await client.send_voice_input("Ok, I'd like to place an order")
            assert any(word in response.lower() for word in ["order", "what", "help"])
            
        finally:
            await client.disconnect()
    
    @pytest.mark.asyncio
    async def test_complex_order_with_dietary_restrictions(self):
        """Test handling complex orders with dietary restrictions."""
        client = VoiceTestClient("CAtest_dietary")
        
        try:
            await client.connect()
            await client.setup_call()
            
            # Setup
            await client.get_response()
            await client.send_voice_input("Amy Wong")
            
            # Ask about dietary options
            response = await client.send_voice_input("Do you have vegetarian options?")
            assert response is not None
            
            # Order with restrictions
            await client.send_voice_input("I'd like to order some vegetarian sushi")
            response = await client.send_voice_input("I'll have two avocado rolls and one cucumber roll")
            
            # Verify order understood
            await client.send_voice_input("That's all")
            
        finally:
            await client.disconnect()
    
    @pytest.mark.asyncio
    async def test_system_performance_under_load(self):
        """Test system performance with multiple concurrent connections."""
        clients = []
        results = []
        
        async def process_order(index: int):
            """Process a single order."""
            client = VoiceTestClient(f"CAtest_perf_{index}")
            try:
                await client.connect()
                await client.setup_call()
                
                start_time = datetime.now()
                
                # Quick order flow
                await client.get_response()  # Greeting
                await client.send_voice_input(f"Customer {index}")
                await client.send_voice_input("I want two California rolls")
                await client.send_voice_input("That's all")
                await client.send_voice_input("Yes confirm")
                
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                return {"index": index, "duration": duration, "success": True}
                
            except Exception as e:
                return {"index": index, "error": str(e), "success": False}
            finally:
                await client.disconnect()
        
        # Run 5 concurrent orders
        tasks = [process_order(i) for i in range(5)]
        results = await asyncio.gather(*tasks)
        
        # Verify all succeeded
        successful = [r for r in results if r["success"]]
        assert len(successful) >= 4  # At least 80% success rate
        
        # Check performance
        avg_duration = sum(r["duration"] for r in successful) / len(successful)
        assert avg_duration < 60  # Should complete within 60 seconds
    
    @pytest.mark.asyncio
    async def test_full_api_integration(self):
        """Test integration with all API endpoints."""
        async with httpx.AsyncClient() as http_client:
            # Test health check
            response = await http_client.get(f"{BASE_URL}/health")
            assert response.status_code == 200
            
            # Test menu endpoints
            response = await http_client.get(f"{BASE_URL}/api/menu/items")
            assert response.status_code == 200
            menu_items = response.json()
            assert len(menu_items) > 0
            
            # Test voice webhook
            response = await http_client.post(
                f"{BASE_URL}/voice/webhook",
                data={"CallSid": "CAtest_api", "From": "+15551234567"}
            )
            assert response.status_code == 200
            assert "<ConversationRelay" in response.text