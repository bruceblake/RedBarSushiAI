"""Tests for external service mocks - Task 2.6."""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from datetime import datetime
import aiohttp
from typing import Dict, Any, List


class TestOpenAIMocks:
    """Test OpenAI API mocks for AI operations - Task 2.6.1."""
    
    @pytest.mark.asyncio
    async def test_openai_completion_mock(self):
        """Test mocking OpenAI completion API."""
        # Mock OpenAI response
        mock_response = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1677652288,
            "model": "gpt-4",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "I'd be happy to help you order sushi!"
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            }
        }
        
        # Mock the OpenAI client
        with patch('openai.AsyncOpenAI') as mock_openai_class:
            mock_client = AsyncMock()
            mock_openai_class.return_value = mock_client
            
            # Mock the chat completion create method
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            # Test using the mock
            import openai
            client = openai.AsyncOpenAI(api_key="test-key")
            response = await client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": "Hello"}]
            )
            
            assert response["choices"][0]["message"]["content"] == "I'd be happy to help you order sushi!"
    
    @pytest.mark.asyncio
    async def test_openai_function_calling_mock(self):
        """Test mocking OpenAI function calling."""
        # Mock response with function call
        mock_response = {
            "id": "chatcmpl-456",
            "object": "chat.completion",
            "created": 1677652288,
            "model": "gpt-4",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": None,
                    "function_call": {
                        "name": "add_to_cart",
                        "arguments": json.dumps({
                            "item_name": "Spicy Tuna Roll",
                            "quantity": 2
                        })
                    }
                },
                "finish_reason": "function_call"
            }]
        }
        
        with patch('openai.AsyncOpenAI') as mock_openai_class:
            mock_client = AsyncMock()
            mock_openai_class.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            # Test function calling
            import openai
            client = openai.AsyncOpenAI(api_key="test-key")
            response = await client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": "Add 2 spicy tuna rolls"}],
                functions=[{"name": "add_to_cart", "parameters": {}}]
            )
            
            function_call = response["choices"][0]["message"]["function_call"]
            assert function_call["name"] == "add_to_cart"
            args = json.loads(function_call["arguments"])
            assert args["item_name"] == "Spicy Tuna Roll"
            assert args["quantity"] == 2
    
    @pytest.mark.asyncio
    async def test_openai_error_scenarios(self):
        """Test OpenAI API error scenarios - Task 2.6.4."""
        with patch('openai.AsyncOpenAI') as mock_openai_class:
            mock_client = AsyncMock()
            mock_openai_class.return_value = mock_client
            
            # Test rate limit error
            from openai import RateLimitError
            mock_client.chat.completions.create = AsyncMock(
                side_effect=RateLimitError("Rate limit exceeded")
            )
            
            import openai
            client = openai.AsyncOpenAI(api_key="test-key")
            
            with pytest.raises(RateLimitError):
                await client.chat.completions.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": "Hello"}]
                )
    
    @pytest.mark.asyncio
    async def test_openai_streaming_mock(self):
        """Test mocking OpenAI streaming responses."""
        # Mock streaming chunks
        async def mock_stream():
            chunks = [
                {"choices": [{"delta": {"content": "I can "}}]},
                {"choices": [{"delta": {"content": "help "}}]},
                {"choices": [{"delta": {"content": "you!"}}]}
            ]
            for chunk in chunks:
                yield chunk
        
        with patch('openai.AsyncOpenAI') as mock_openai_class:
            mock_client = AsyncMock()
            mock_openai_class.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())
            
            # Test streaming
            import openai
            client = openai.AsyncOpenAI(api_key="test-key")
            stream = await client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": "Hello"}],
                stream=True
            )
            
            content = ""
            async for chunk in stream:
                if "content" in chunk["choices"][0]["delta"]:
                    content += chunk["choices"][0]["delta"]["content"]
            
            assert content == "I can help you!"


class TestTwilioMocks:
    """Test Twilio API mocks for voice operations - Task 2.6.2."""
    
    def test_twilio_client_mock(self):
        """Test mocking Twilio client creation."""
        with patch('twilio.rest.Client') as mock_twilio_class:
            mock_client = MagicMock()
            mock_twilio_class.return_value = mock_client
            
            # Mock call creation
            mock_call = MagicMock()
            mock_call.sid = "CA123456789"
            mock_call.status = "initiated"
            mock_client.calls.create.return_value = mock_call
            
            # Test call creation
            from twilio.rest import Client
            client = Client("test_sid", "test_token")
            call = client.calls.create(
                to="+1234567890",
                from_="+0987654321",
                url="https://example.com/twiml"
            )
            
            assert call.sid == "CA123456789"
            assert call.status == "initiated"
    
    def test_twilio_twiml_response_mock(self):
        """Test mocking TwiML response generation."""
        from twilio.twiml.voice_response import VoiceResponse
        
        # Create TwiML response
        response = VoiceResponse()
        response.say("Welcome to Red Bar Sushi!")
        response.gather(
            input="speech",
            action="/voice/process",
            speech_timeout="3"
        )
        
        # Convert to string and verify
        twiml_str = str(response)
        assert "<Say>Welcome to Red Bar Sushi!</Say>" in twiml_str
        assert "<Gather" in twiml_str
        assert 'input="speech"' in twiml_str
    
    @pytest.mark.asyncio
    async def test_twilio_webhook_validation_mock(self):
        """Test mocking Twilio webhook signature validation."""
        with patch('twilio.request_validator.RequestValidator') as mock_validator_class:
            mock_validator = MagicMock()
            mock_validator_class.return_value = mock_validator
            mock_validator.validate.return_value = True
            
            # Test validation
            from twilio.request_validator import RequestValidator
            validator = RequestValidator("auth_token")
            
            is_valid = validator.validate(
                "https://example.com/webhook",
                {"CallSid": "CA123"},
                "fake_signature"
            )
            
            assert is_valid is True
    
    def test_twilio_error_handling_mock(self):
        """Test Twilio error scenarios - Task 2.6.4."""
        with patch('twilio.rest.Client') as mock_twilio_class:
            mock_client = MagicMock()
            mock_twilio_class.return_value = mock_client
            
            # Mock Twilio exception
            from twilio.base.exceptions import TwilioRestException
            mock_client.calls.create.side_effect = TwilioRestException(
                status=400,
                uri="/Calls",
                msg="Invalid phone number"
            )
            
            # Test error handling
            from twilio.rest import Client
            client = Client("test_sid", "test_token")
            
            with pytest.raises(TwilioRestException) as exc_info:
                client.calls.create(
                    to="invalid",
                    from_="+0987654321",
                    url="https://example.com/twiml"
                )
            
            assert exc_info.value.status == 400
            assert "Invalid phone number" in str(exc_info.value)
    
    def test_twilio_status_callback_mock(self):
        """Test mocking Twilio status callbacks."""
        # Mock webhook data
        webhook_data = {
            "CallSid": "CA123456789",
            "CallStatus": "completed",
            "CallDuration": "45",
            "From": "+1234567890",
            "To": "+0987654321",
            "Timestamp": "2024-01-15T10:30:00Z"
        }
        
        # Test processing webhook
        assert webhook_data["CallStatus"] == "completed"
        assert int(webhook_data["CallDuration"]) == 45


class TestDeliverectMocks:
    """Test Deliverect API mocks for order submission - Task 2.6.3."""
    
    @pytest.mark.asyncio
    async def test_deliverect_auth_mock(self):
        """Test mocking Deliverect authentication."""
        mock_auth_response = {
            "access_token": "test_access_token_123",
            "token_type": "Bearer",
            "expires_in": 3600
        }
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            # Mock POST response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_auth_response)
            mock_session.post.return_value.__aenter__.return_value = mock_response
            
            # Test authentication
            async with aiohttp.ClientSession() as session:
                response = await session.post(
                    "https://api.deliverect.com/oauth/token",
                    json={
                        "client_id": "test_client",
                        "client_secret": "test_secret",
                        "grant_type": "client_credentials"
                    }
                )
                auth_data = await response.json()
            
            assert auth_data["access_token"] == "test_access_token_123"
            assert auth_data["expires_in"] == 3600
    
    @pytest.mark.asyncio
    async def test_deliverect_order_submission_mock(self):
        """Test mocking Deliverect order submission."""
        mock_order_response = {
            "orderId": "ORD-123456",
            "status": "ACCEPTED",
            "deliveryTime": "2024-01-15T18:30:00Z",
            "totalAmount": 2599,  # $25.99 in cents
            "items": [
                {
                    "productId": "PROD-001",
                    "name": "Spicy Tuna Roll",
                    "quantity": 2,
                    "price": 1299
                }
            ]
        }
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            # Mock POST response for order
            mock_response = AsyncMock()
            mock_response.status = 201
            mock_response.json = AsyncMock(return_value=mock_order_response)
            mock_session.post.return_value.__aenter__.return_value = mock_response
            
            # Test order submission
            order_data = {
                "customer": {
                    "name": "John Doe",
                    "phone": "+1234567890"
                },
                "items": [{"id": "PROD-001", "quantity": 2}],
                "deliveryType": "DELIVERY"
            }
            
            async with aiohttp.ClientSession() as session:
                response = await session.post(
                    "https://api.deliverect.com/orders",
                    json=order_data,
                    headers={"Authorization": "Bearer test_token"}
                )
                order_result = await response.json()
            
            assert order_result["orderId"] == "ORD-123456"
            assert order_result["status"] == "ACCEPTED"
            assert order_result["totalAmount"] == 2599
    
    @pytest.mark.asyncio
    async def test_deliverect_menu_sync_mock(self):
        """Test mocking Deliverect menu synchronization."""
        mock_menu_response = {
            "menu": {
                "id": "MENU-001",
                "name": "Main Menu",
                "categories": [
                    {
                        "id": "CAT-001",
                        "name": "Sushi Rolls",
                        "products": [
                            {
                                "id": "PROD-001",
                                "name": "Spicy Tuna Roll",
                                "price": 1299,
                                "available": True
                            }
                        ]
                    }
                ]
            }
        }
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            # Mock GET response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_menu_response)
            mock_session.get.return_value.__aenter__.return_value = mock_response
            
            # Test menu fetch
            async with aiohttp.ClientSession() as session:
                response = await session.get(
                    "https://api.deliverect.com/menus/MENU-001",
                    headers={"Authorization": "Bearer test_token"}
                )
                menu_data = await response.json()
            
            assert menu_data["menu"]["id"] == "MENU-001"
            assert len(menu_data["menu"]["categories"]) == 1
            assert menu_data["menu"]["categories"][0]["products"][0]["available"] is True
    
    @pytest.mark.asyncio
    async def test_deliverect_webhook_mock(self):
        """Test mocking Deliverect webhooks."""
        # Mock webhook payload
        webhook_payload = {
            "eventType": "ORDER_STATUS_UPDATE",
            "orderId": "ORD-123456",
            "status": "READY_FOR_PICKUP",
            "timestamp": "2024-01-15T18:25:00Z",
            "estimatedPickupTime": "2024-01-15T18:30:00Z"
        }
        
        # Test webhook processing
        assert webhook_payload["eventType"] == "ORDER_STATUS_UPDATE"
        assert webhook_payload["status"] == "READY_FOR_PICKUP"
        
        # Mock webhook validation
        with patch('hmac.compare_digest') as mock_compare:
            mock_compare.return_value = True
            
            import hmac
            is_valid = hmac.compare_digest("signature1", "signature2")
            assert is_valid is True
    
    @pytest.mark.asyncio
    async def test_deliverect_error_scenarios_mock(self):
        """Test Deliverect API error scenarios - Task 2.6.4."""
        # Test various error responses
        error_scenarios = [
            (400, {"error": "Invalid request", "message": "Missing required field: customer.phone"}),
            (401, {"error": "Unauthorized", "message": "Invalid or expired token"}),
            (404, {"error": "Not Found", "message": "Menu not found"}),
            (429, {"error": "Rate Limited", "message": "Too many requests"}),
            (500, {"error": "Internal Server Error", "message": "Service temporarily unavailable"})
        ]
        
        for status_code, error_response in error_scenarios:
            with patch('aiohttp.ClientSession') as mock_session_class:
                mock_session = AsyncMock()
                mock_session_class.return_value.__aenter__.return_value = mock_session
                
                # Mock error response
                mock_response = AsyncMock()
                mock_response.status = status_code
                mock_response.json = AsyncMock(return_value=error_response)
                mock_session.post.return_value.__aenter__.return_value = mock_response
                
                # Test error handling
                async with aiohttp.ClientSession() as session:
                    response = await session.post(
                        "https://api.deliverect.com/orders",
                        json={},
                        headers={"Authorization": "Bearer test_token"}
                    )
                    
                    assert response.status == status_code
                    error_data = await response.json()
                    assert "error" in error_data


class TestComprehensiveErrorScenarios:
    """Test comprehensive error scenarios for all services - Task 2.6.4."""
    
    @pytest.mark.asyncio
    async def test_network_timeout_scenarios(self):
        """Test network timeout handling."""
        # Mock timeout for different services
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            # Simulate timeout
            mock_session.post.side_effect = aiohttp.ClientTimeout
            
            with pytest.raises(aiohttp.ClientTimeout):
                async with aiohttp.ClientSession() as session:
                    await session.post("https://api.example.com/endpoint")
    
    @pytest.mark.asyncio
    async def test_connection_error_scenarios(self):
        """Test connection error handling."""
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            # Simulate connection error
            mock_session.get.side_effect = aiohttp.ClientConnectorError(
                connection_key=None,
                os_error=OSError("Connection refused")
            )
            
            with pytest.raises(aiohttp.ClientConnectorError):
                async with aiohttp.ClientSession() as session:
                    await session.get("https://api.example.com/data")
    
    @pytest.mark.asyncio
    async def test_retry_logic_mock(self):
        """Test retry logic for failed requests."""
        attempt_count = 0
        
        async def mock_request():
            nonlocal attempt_count
            attempt_count += 1
            
            if attempt_count < 3:
                raise aiohttp.ClientError("Temporary failure")
            
            # Success on third attempt
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"success": True})
            return mock_response
        
        # Test retry logic
        max_retries = 3
        for i in range(max_retries):
            try:
                response = await mock_request()
                break
            except aiohttp.ClientError:
                if i == max_retries - 1:
                    raise
                continue
        
        assert attempt_count == 3
        assert response.status == 200
    
    def test_circuit_breaker_mock(self):
        """Test circuit breaker pattern for service failures."""
        class MockCircuitBreaker:
            def __init__(self, failure_threshold=5, recovery_timeout=60):
                self.failure_count = 0
                self.failure_threshold = failure_threshold
                self.is_open = False
                self.last_failure_time = None
            
            def call(self, func, *args, **kwargs):
                if self.is_open:
                    raise Exception("Circuit breaker is open")
                
                try:
                    result = func(*args, **kwargs)
                    self.failure_count = 0  # Reset on success
                    return result
                except Exception as e:
                    self.failure_count += 1
                    if self.failure_count >= self.failure_threshold:
                        self.is_open = True
                        self.last_failure_time = datetime.now()
                    raise e
        
        # Test circuit breaker
        breaker = MockCircuitBreaker(failure_threshold=3)
        
        def failing_service():
            raise Exception("Service error")
        
        # Should fail 3 times then open circuit
        for i in range(3):
            with pytest.raises(Exception):
                breaker.call(failing_service)
        
        assert breaker.is_open is True
        
        # Further calls should fail immediately
        with pytest.raises(Exception, match="Circuit breaker is open"):
            breaker.call(failing_service)
    
    @pytest.mark.asyncio
    async def test_graceful_degradation_mock(self):
        """Test graceful degradation when services fail."""
        # Mock service availability
        services = {
            "openai": False,
            "twilio": True,
            "deliverect": False
        }
        
        async def check_service_health(service_name: str) -> bool:
            return services.get(service_name, False)
        
        # Test fallback behavior
        if not await check_service_health("openai"):
            # Fallback to rule-based responses
            fallback_response = "I'm currently unable to process AI requests, but I can still help you with basic orders."
            assert "unable to process AI" in fallback_response
        
        if await check_service_health("twilio"):
            # Twilio is available
            can_make_calls = True
            assert can_make_calls is True
        
        if not await check_service_health("deliverect"):
            # Store orders locally for later submission
            local_order_queue = []
            local_order_queue.append({"order_id": "LOCAL-001", "data": {}})
            assert len(local_order_queue) == 1


class TestMockIntegration:
    """Test integration of multiple service mocks."""
    
    @pytest.mark.asyncio
    async def test_full_order_flow_with_mocks(self):
        """Test complete order flow with all services mocked."""
        # Mock OpenAI for order understanding
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            # AI understands the order
            mock_client.chat.completions.create = AsyncMock(return_value={
                "choices": [{
                    "message": {
                        "function_call": {
                            "name": "add_to_cart",
                            "arguments": json.dumps({
                                "items": [
                                    {"name": "Spicy Tuna Roll", "quantity": 2},
                                    {"name": "Salmon Sashimi", "quantity": 1}
                                ]
                            })
                        }
                    }
                }]
            })
            
            # Mock Twilio for voice confirmation
            with patch('twilio.twiml.voice_response.VoiceResponse') as mock_twiml:
                mock_response = MagicMock()
                mock_twiml.return_value = mock_response
                
                # Mock Deliverect for order submission
                with patch('aiohttp.ClientSession') as mock_session:
                    mock_http = AsyncMock()
                    mock_session.return_value.__aenter__.return_value = mock_http
                    
                    # Mock successful order submission
                    mock_order_response = AsyncMock()
                    mock_order_response.status = 201
                    mock_order_response.json = AsyncMock(return_value={
                        "orderId": "ORD-789",
                        "status": "ACCEPTED",
                        "estimatedTime": "30 minutes"
                    })
                    mock_http.post.return_value.__aenter__.return_value = mock_order_response
                    
                    # Simulate the flow
                    # 1. AI processes order
                    import openai
                    ai_client = openai.AsyncOpenAI(api_key="test")
                    ai_response = await ai_client.chat.completions.create(
                        model="gpt-4",
                        messages=[{"role": "user", "content": "I want 2 spicy tuna rolls and 1 salmon sashimi"}]
                    )
                    
                    # 2. Generate voice confirmation
                    from twilio.twiml.voice_response import VoiceResponse
                    voice_response = VoiceResponse()
                    voice_response.say("Your order has been confirmed")
                    
                    # 3. Submit to Deliverect
                    async with aiohttp.ClientSession() as session:
                        order_response = await session.post(
                            "https://api.deliverect.com/orders",
                            json={"items": [], "customer": {}}
                        )
                        order_data = await order_response.json()
                    
                    # Verify the flow
                    assert order_data["orderId"] == "ORD-789"
                    assert order_data["status"] == "ACCEPTED"
    
    @pytest.mark.asyncio
    async def test_partial_service_failure_handling(self):
        """Test handling when some services fail."""
        # OpenAI works, Deliverect fails
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(return_value={
                "choices": [{"message": {"content": "Order understood"}}]
            })
            
            with patch('aiohttp.ClientSession') as mock_session:
                mock_http = AsyncMock()
                mock_session.return_value.__aenter__.return_value = mock_http
                
                # Deliverect fails
                mock_http.post.side_effect = aiohttp.ClientError("Service unavailable")
                
                # Test graceful handling
                order_saved_locally = False
                
                try:
                    async with aiohttp.ClientSession() as session:
                        await session.post("https://api.deliverect.com/orders")
                except aiohttp.ClientError:
                    # Save order locally
                    order_saved_locally = True
                
                assert order_saved_locally is True
    
    def test_mock_state_management(self):
        """Test managing mock states across tests."""
        # Create a mock state manager
        class MockStateManager:
            def __init__(self):
                self.states = {
                    "openai_available": True,
                    "twilio_available": True,
                    "deliverect_available": True,
                    "order_count": 0,
                    "error_count": 0
                }
            
            def set_service_availability(self, service: str, available: bool):
                self.states[f"{service}_available"] = available
            
            def increment_order_count(self):
                self.states["order_count"] += 1
            
            def increment_error_count(self):
                self.states["error_count"] += 1
            
            def reset(self):
                self.__init__()
        
        # Test state management
        state_manager = MockStateManager()
        
        # Simulate service failures
        state_manager.set_service_availability("openai", False)
        assert state_manager.states["openai_available"] is False
        
        # Track orders
        state_manager.increment_order_count()
        state_manager.increment_order_count()
        assert state_manager.states["order_count"] == 2
        
        # Reset for new test
        state_manager.reset()
        assert state_manager.states["order_count"] == 0
        assert state_manager.states["openai_available"] is True
    
    @pytest.mark.asyncio
    async def test_mock_data_consistency(self):
        """Test data consistency across mocked services."""
        # Shared order ID across services
        order_id = "ORD-CONSISTENT-123"
        
        # Mock all services to use consistent order ID
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(return_value={
                "choices": [{
                    "message": {
                        "content": f"Order {order_id} created"
                    }
                }]
            })
            
            with patch('twilio.rest.Client') as mock_twilio:
                mock_twilio_client = MagicMock()
                mock_twilio.return_value = mock_twilio_client
                mock_call = MagicMock()
                mock_call.sid = f"CA-{order_id}"
                mock_twilio_client.calls.create.return_value = mock_call
                
                with patch('aiohttp.ClientSession') as mock_session:
                    mock_http = AsyncMock()
                    mock_session.return_value.__aenter__.return_value = mock_http
                    
                    mock_response = AsyncMock()
                    mock_response.json = AsyncMock(return_value={"orderId": order_id})
                    mock_http.post.return_value.__aenter__.return_value = mock_response
                    
                    # Test consistency
                    import openai
                    from twilio.rest import Client
                    
                    # AI response includes order ID
                    ai_client = openai.AsyncOpenAI(api_key="test")
                    ai_response = await ai_client.chat.completions.create(
                        model="gpt-4",
                        messages=[]
                    )
                    assert order_id in ai_response["choices"][0]["message"]["content"]
                    
                    # Twilio call references same order
                    twilio_client = Client("sid", "token")
                    call = twilio_client.calls.create(
                        to="+1234567890",
                        from_="+0987654321",
                        url="https://example.com"
                    )
                    assert order_id in call.sid
                    
                    # Deliverect returns same order ID
                    async with aiohttp.ClientSession() as session:
                        response = await session.post("https://api.deliverect.com/orders")
                        data = await response.json()
                        assert data["orderId"] == order_id