"""
Integration tests for streaming response functionality.
"""

import pytest
import pytest_asyncio
import asyncio
from unittest.mock import AsyncMock, patch
from typing import List, Tuple

from app.utils.agent_orchestration_async import AsyncAgentOrchestrator
from app.agents.base_async import BaseAsyncAgent
from app.utils.streaming import StreamingChunker, ChunkType
from app.fsm.core import ConversationState


class TestStreamingIntegration:
    """Test streaming response integration across the system."""
    
    @pytest_asyncio.fixture
    async def streaming_orchestrator(self, test_db, mock_redis, mock_openai_client):
        """Create orchestrator with streaming support."""
        orchestrator = AsyncAgentOrchestrator()
        
        # Mock initialization
        with patch('app.utils.agent_orchestration_async.async_agent_factory') as mock_factory:
            mock_voice_system = AsyncMock(spec=BaseAsyncAgent)
            mock_voice_system.specialist_agents = {}
            mock_factory.create_voice_agent_system.return_value = mock_voice_system
            
            # Create mock agents with streaming support
            mock_agents = {}
            for agent_type in ['frontline', 'cart', 'menu', 'guardrail', 'fulfillment', 'escalation']:
                agent = AsyncMock(spec=BaseAsyncAgent)
                agent.name = agent_type
                agent.supports_streaming = True
                mock_agents[agent_type] = agent
            
            async def get_agent_side_effect(agent_type, **kwargs):
                return mock_agents.get(agent_type)
            
            mock_factory.get_agent.side_effect = get_agent_side_effect
            
            await orchestrator.initialize(db=test_db)
            
            # Store mock agents for test access
            orchestrator._mock_agents = mock_agents
        
        return orchestrator
    
    @pytest.mark.asyncio
    async def test_streaming_response_flow(self, streaming_orchestrator):
        """Test complete streaming response flow."""
        orchestrator = streaming_orchestrator
        
        # Create session
        session_id = "test_stream_001"
        await orchestrator.create_session(session_id)
        
        # Collected chunks
        chunks: List[Tuple[str, bool]] = []
        
        async def chunk_callback(chunk: str, is_final: bool):
            chunks.append((chunk, is_final))
        
        # Mock agent streaming response
        async def mock_streaming_process(transcript, context, stream_callback=None):
            if stream_callback:
                # Simulate streaming chunks
                await stream_callback("Welcome to ", False)
                await asyncio.sleep(0.01)  # Simulate processing
                await stream_callback("Red Bar Sushi. ", False)
                await asyncio.sleep(0.01)
                await stream_callback("How can I help you today?", True)
            
            return {
                "text": "Welcome to Red Bar Sushi. How can I help you today?",
                "agent": "frontline",
                "handled": True,
                "streamed": True
            }
        
        # Set up mock agent
        orchestrator.frontline_agent.process = mock_streaming_process
        
        # Mock intent detection
        with patch('app.utils.agent_orchestration_async.intent_detector') as mock_detector:
            mock_detector.detect_intent = AsyncMock(return_value=None)
            
            # Process with streaming
            response = await orchestrator.process(
                session_id,
                "Hello",
                stream_callback=chunk_callback
            )
        
        # Verify streaming occurred
        assert len(chunks) == 3
        assert chunks[0] == ("Welcome to ", False)
        assert chunks[1] == ("Red Bar Sushi. ", False)
        assert chunks[2] == ("How can I help you today?", True)
        assert response["streamed"] is True
    
    @pytest.mark.asyncio
    async def test_streaming_with_sentence_boundaries(self, streaming_orchestrator):
        """Test streaming respects sentence boundaries."""
        orchestrator = streaming_orchestrator
        session_id = "test_stream_002"
        await orchestrator.create_session(session_id)
        
        chunks = []
        
        async def chunk_callback(chunk: str, is_final: bool):
            chunks.append(chunk)
        
        # Mock agent with longer response
        async def mock_long_response(transcript, context, stream_callback=None):
            full_text = (
                "I can help you with that. "
                "We have several sushi rolls available. "
                "The California Roll is $12.95. "
                "Would you like to order one?"
            )
            
            if stream_callback:
                # Use streaming chunker
                chunker = StreamingChunker()
                async for chunk, chunk_type in chunker.chunk_text(full_text):
                    is_final = chunk_type == ChunkType.FINAL
                    await stream_callback(chunk, is_final)
            
            return {
                "text": full_text,
                "agent": "menu",
                "handled": True,
                "streamed": True
            }
        
        # Set up in menu query state
        session = orchestrator.sessions[session_id]
        session["fsm"].current_state = ConversationState.MENU_QUERY_SUBSTATE
        
        # Mock menu agent
        if hasattr(orchestrator, 'menu_agent'):
            orchestrator.menu_agent.process = mock_long_response
        
        with patch('app.utils.agent_orchestration_async.intent_detector') as mock_detector:
            mock_detector.detect_intent = AsyncMock(return_value=None)
            
            response = await orchestrator.process(
                session_id,
                "What rolls do you have?",
                stream_callback=chunk_callback
            )
        
        # Verify sentence-based chunking
        assert len(chunks) > 0
        # Each chunk should end with punctuation (except possibly the last)
        for i, chunk in enumerate(chunks[:-1]):
            assert chunk.rstrip().endswith(('.', '!', '?'))
    
    @pytest.mark.asyncio
    async def test_streaming_error_handling(self, streaming_orchestrator):
        """Test streaming handles errors gracefully."""
        orchestrator = streaming_orchestrator
        session_id = "test_stream_003"
        await orchestrator.create_session(session_id)
        
        chunks = []
        error_occurred = False
        
        async def chunk_callback(chunk: str, is_final: bool):
            chunks.append((chunk, is_final))
        
        # Mock agent that errors during streaming
        async def mock_error_response(transcript, context, stream_callback=None):
            if stream_callback:
                await stream_callback("Starting to process", False)
                # Simulate error mid-stream
                raise Exception("Streaming error")
        
        orchestrator.frontline_agent.process = mock_error_response
        
        with patch('app.utils.agent_orchestration_async.intent_detector') as mock_detector:
            mock_detector.detect_intent = AsyncMock(return_value=None)
            
            try:
                response = await orchestrator.process(
                    session_id,
                    "Test error",
                    stream_callback=chunk_callback
                )
            except Exception:
                error_occurred = True
        
        # Should handle error gracefully
        assert len(chunks) >= 1  # At least got the first chunk
        assert chunks[0] == ("Starting to process", False)
    
    @pytest.mark.asyncio
    async def test_streaming_with_function_calls(self, streaming_orchestrator):
        """Test streaming with agents that use function calls."""
        orchestrator = streaming_orchestrator
        session_id = "test_stream_004"
        await orchestrator.create_session(session_id)
        
        # Set up in ordering state
        session = orchestrator.sessions[session_id]
        session["fsm"].current_state = ConversationState.ORDERING
        session["context"]["cart"] = []
        
        chunks = []
        
        async def chunk_callback(chunk: str, is_final: bool):
            chunks.append(chunk)
        
        # Mock cart agent with function call then streaming
        async def mock_cart_process(transcript, context, stream_callback=None):
            # Simulate function call processing
            context["cart"].append({
                "name": "California Roll",
                "quantity": 2,
                "price": 12.95
            })
            
            # Then stream response
            response_text = "I've added 2 California Rolls to your order. Your total is $25.90."
            
            if stream_callback:
                chunker = StreamingChunker()
                async for chunk, chunk_type in chunker.chunk_text(response_text):
                    is_final = chunk_type == ChunkType.FINAL
                    await stream_callback(chunk, is_final)
            
            return {
                "text": response_text,
                "agent": "cart",
                "handled": True,
                "streamed": True,
                "cart": context["cart"]
            }
        
        orchestrator.cart_agent.process = mock_cart_process
        
        with patch('app.utils.agent_orchestration_async.intent_detector') as mock_detector:
            mock_detector.detect_intent = AsyncMock(return_value=None)
            
            response = await orchestrator.process(
                session_id,
                "Add 2 California rolls",
                stream_callback=chunk_callback
            )
        
        # Verify function executed and streaming occurred
        assert len(session["context"]["cart"]) == 1
        assert len(chunks) > 0
        assert "California Rolls" in "".join(chunks)
        assert "$25.90" in "".join(chunks)
    
    @pytest.mark.asyncio
    async def test_non_streaming_agent_fallback(self, streaming_orchestrator):
        """Test handling of non-streaming agents."""
        orchestrator = streaming_orchestrator
        session_id = "test_stream_005"
        await orchestrator.create_session(session_id)
        
        chunks = []
        
        async def chunk_callback(chunk: str, is_final: bool):
            chunks.append((chunk, is_final))
        
        # Mock agent without streaming support
        async def mock_non_streaming(transcript, context, stream_callback=None):
            # Ignore stream_callback - don't stream
            return {
                "text": "This response is not streamed.",
                "agent": "guardrail",
                "handled": True,
                "streamed": False
            }
        
        # Set up in validation state
        session = orchestrator.sessions[session_id]
        session["fsm"].current_state = ConversationState.VALIDATION
        
        orchestrator.guardrail_agent.process = mock_non_streaming
        orchestrator.guardrail_agent.supports_streaming = False
        
        with patch('app.utils.agent_orchestration_async.intent_detector') as mock_detector:
            mock_detector.detect_intent = AsyncMock(return_value=None)
            
            response = await orchestrator.process(
                session_id,
                "Validate my order",
                stream_callback=chunk_callback
            )
        
        # Should get complete response at once
        assert len(chunks) == 1
        assert chunks[0] == ("This response is not streamed.", True)
        assert response["streamed"] is False
    
    @pytest.mark.asyncio
    async def test_streaming_performance(self, streaming_orchestrator):
        """Test streaming improves perceived latency."""
        orchestrator = streaming_orchestrator
        session_id = "test_stream_006"
        await orchestrator.create_session(session_id)
        
        first_chunk_time = None
        complete_time = None
        chunks_received = 0
        
        async def timing_callback(chunk: str, is_final: bool):
            nonlocal first_chunk_time, complete_time, chunks_received
            
            if chunks_received == 0:
                first_chunk_time = asyncio.get_event_loop().time()
            
            chunks_received += 1
            
            if is_final:
                complete_time = asyncio.get_event_loop().time()
        
        # Mock agent with delayed response
        async def mock_delayed_response(transcript, context, stream_callback=None):
            start_time = asyncio.get_event_loop().time()
            
            if stream_callback:
                # Stream first chunk quickly
                await asyncio.sleep(0.1)  # 100ms to first chunk
                await stream_callback("Starting your order. ", False)
                
                # Simulate processing
                await asyncio.sleep(0.3)  # 300ms more processing
                await stream_callback("I've found the items. ", False)
                
                await asyncio.sleep(0.1)  # 100ms more
                await stream_callback("Your total is $45.90.", True)
            else:
                # Without streaming, wait full time
                await asyncio.sleep(0.5)
            
            return {
                "text": "Starting your order. I've found the items. Your total is $45.90.",
                "agent": "cart",
                "handled": True,
                "streamed": bool(stream_callback)
            }
        
        orchestrator.cart_agent.process = mock_delayed_response
        
        # Test with streaming
        start_time = asyncio.get_event_loop().time()
        
        with patch('app.utils.agent_orchestration_async.intent_detector') as mock_detector:
            mock_detector.detect_intent = AsyncMock(return_value=None)
            
            response = await orchestrator.process(
                session_id,
                "Process my order",
                stream_callback=timing_callback
            )
        
        # Calculate timings
        time_to_first_chunk = first_chunk_time - start_time
        total_time = complete_time - start_time
        
        # Verify streaming improved perceived latency
        assert chunks_received == 3
        assert time_to_first_chunk < 0.2  # First chunk within 200ms
        assert total_time > 0.4  # Total time still includes all processing
        assert response["streamed"] is True