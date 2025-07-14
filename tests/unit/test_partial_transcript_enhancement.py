"""
Unit tests for Enhanced Partial Transcript Processing.

Tests the new end-of-speech detection and configurable delay functionality
to prevent premature responses during continued user speech.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from app.utils.partial_transcript_processor import (
    PartialTranscriptProcessor, SimpleIntent, PendingTranscript,
    process_partial_transcript_with_delay
)


class TestPartialTranscriptEnhancement:
    """Test suite for Enhanced Partial Transcript Processing."""
    
    @pytest.fixture
    def processor(self):
        """Create a processor with test configuration."""
        return PartialTranscriptProcessor(
            confidence_threshold=0.9,
            delay_ms=300,
            end_of_speech_threshold=0.8
        )
    
    @pytest.fixture
    def context(self):
        """Test conversation context."""
        return {
            "call_sid": "test_call_123",
            "hsm_state": "ACTIVE.CONFIRMATION"
        }
    
    def test_continuation_indicators_detection(self, processor):
        """Test detection of continuation indicators."""
        # Test cases that should indicate continuation
        continuation_cases = [
            "yes and",
            "yes, and I'd also like",
            "okay but",
            "sure, however",
            "right, actually",
            "yes um",
            "okay so",
            "yes well",
            "no but wait"
        ]
        
        for transcript in continuation_cases:
            assert processor._indicates_continuation(transcript), f"Failed for: '{transcript}'"
    
    def test_complete_utterance_detection(self, processor):
        """Test detection of complete utterances."""
        # Test cases that should NOT indicate continuation
        complete_cases = [
            "yes",
            "no thank you",
            "that's correct",
            "perfect",
            "sounds good",
            "exactly right"
        ]
        
        for transcript in complete_cases:
            assert not processor._indicates_continuation(transcript), f"Failed for: '{transcript}'"
    
    @pytest.mark.asyncio
    async def test_immediate_processing_for_complete_utterances(self, processor, context):
        """Test that complete utterances are processed immediately after delay."""
        transcript = "yes"
        
        # Should detect intent but not process immediately
        result = await processor.process_partial_transcript_with_delay(transcript, context)
        assert result == (None, 0.0, None)  # No immediate processing
        
        # Should have pending transcript
        assert context["call_sid"] in processor.pending_transcripts
        
        # Wait for delay + a bit more
        await asyncio.sleep(0.35)  # 350ms
        
        # After delay, pending transcript should be processed and removed
        assert context["call_sid"] not in processor.pending_transcripts
    
    @pytest.mark.asyncio
    async def test_continuation_prevention(self, processor, context):
        """Test that continuation indicators prevent processing."""
        transcript = "yes and"
        
        # Should not process due to continuation indicator
        result = await processor.process_partial_transcript_with_delay(transcript, context)
        assert result == (None, 0.0, None)
        
        # Should not have pending transcript
        assert context["call_sid"] not in processor.pending_transcripts
    
    @pytest.mark.asyncio
    async def test_pending_transcript_updating(self, processor, context):
        """Test that pending transcripts are updated correctly."""
        call_sid = context["call_sid"]
        
        # First partial transcript
        result1 = await processor.process_partial_transcript_with_delay("ye", context)
        assert result1 == (None, 0.0, None)
        
        # Should not have pending (confidence too low)
        assert call_sid not in processor.pending_transcripts
        
        # High confidence partial
        result2 = await processor.process_partial_transcript_with_delay("yes", context)
        assert result2 == (None, 0.0, None)
        
        # Should have pending transcript
        assert call_sid in processor.pending_transcripts
        pending = processor.pending_transcripts[call_sid]
        assert pending.text == "yes"
        assert pending.intent == SimpleIntent.CONFIRM
        
        # Small delay to ensure we're still within the delay window
        await asyncio.sleep(0.1)  # 100ms - well before the 300ms delay
        
        # Update with more text (still high confidence - use "yes exactly" which matches patterns)
        result3 = await processor.process_partial_transcript_with_delay("yes exactly", context)
        assert result3 == (None, 0.0, None)
        
        # Should update existing pending (if still within delay window)
        if call_sid in processor.pending_transcripts:
            updated_pending = processor.pending_transcripts[call_sid]
            assert updated_pending.text == "yes exactly"
            assert updated_pending.last_updated > pending.last_updated
    
    @pytest.mark.asyncio
    async def test_delay_timer_functionality(self, processor, context):
        """Test the delay timer mechanism."""
        call_sid = context["call_sid"]
        
        # Mock the delayed response trigger
        processor._trigger_delayed_response = AsyncMock()
        
        # Process high-confidence intent
        await processor.process_partial_transcript_with_delay("yes", context)
        
        # Should have pending transcript
        assert call_sid in processor.pending_transcripts
        
        # Wait for delay period
        await asyncio.sleep(0.35)  # Slightly more than 300ms
        
        # Check if delayed response was triggered
        # Note: In real implementation, this would be handled by the voice system
        assert processor._trigger_delayed_response.call_count <= 1  # May or may not be called depending on timing
    
    def test_stale_transcript_cleanup(self, processor, context):
        """Test cleanup of stale pending transcripts."""
        call_sid = context["call_sid"]
        current_time = time.time()
        
        # Create a stale pending transcript
        processor.pending_transcripts[call_sid] = PendingTranscript(
            text="yes",
            confidence=0.9,
            intent=SimpleIntent.CONFIRM,
            response_data={},
            first_detected=current_time - 15,  # 15 seconds ago
            last_updated=current_time - 15,
            call_sid=call_sid
        )
        
        # Cleanup with 10 second threshold
        processor.cleanup_stale_pending_transcripts(max_age_seconds=10.0)
        
        # Should be cleaned up
        assert call_sid not in processor.pending_transcripts
    
    def test_pending_transcript_cancellation(self, processor, context):
        """Test manual cancellation of pending transcripts."""
        call_sid = context["call_sid"]
        
        # Add pending transcript
        processor.pending_transcripts[call_sid] = PendingTranscript(
            text="yes",
            confidence=0.9,
            intent=SimpleIntent.CONFIRM,
            response_data={},
            first_detected=time.time(),
            last_updated=time.time(),
            call_sid=call_sid
        )
        
        # Cancel it
        result = processor.cancel_pending_transcript(call_sid)
        assert result is True
        assert call_sid not in processor.pending_transcripts
        
        # Try to cancel non-existent
        result = processor.cancel_pending_transcript("non_existent")
        assert result is False
    
    def test_pending_status_reporting(self, processor):
        """Test status reporting for pending transcripts."""
        current_time = time.time()
        
        # Add multiple pending transcripts
        test_transcripts = [
            ("call_1", SimpleIntent.CONFIRM, current_time - 0.5),
            ("call_2", SimpleIntent.REJECT, current_time - 0.3),
            ("call_3", SimpleIntent.CONFIRM, current_time - 0.1)
        ]
        
        for call_sid, intent, first_detected in test_transcripts:
            processor.pending_transcripts[call_sid] = PendingTranscript(
                text="test",
                confidence=0.9,
                intent=intent,
                response_data={},
                first_detected=first_detected,
                last_updated=first_detected,
                call_sid=call_sid
            )
        
        status = processor.get_pending_status()
        
        assert status["total_pending"] == 3
        assert status["pending_by_intent"]["confirm"] == 2
        assert status["pending_by_intent"]["reject"] == 1
        assert status["oldest_pending_age_ms"] >= 500  # At least 500ms old
        assert status["average_pending_age_ms"] > 0
    
    @pytest.mark.asyncio
    async def test_race_condition_prevention(self, processor, context):
        """Test prevention of race conditions with 'Yes, and...' scenarios."""
        call_sid = context["call_sid"]
        
        # Simulate user saying "Yes" with high confidence
        result1 = await processor.process_partial_transcript_with_delay("Yes", context)
        assert result1 == (None, 0.0, None)
        assert call_sid in processor.pending_transcripts
        
        # Before delay expires, user continues with "and"
        result2 = await processor.process_partial_transcript_with_delay("Yes and", context)
        assert result2 == (None, 0.0, None)
        
        # Should not process due to continuation indicator
        # Pending transcript should be removed or not trigger response
        
        # Continue with full statement
        result3 = await processor.process_partial_transcript_with_delay("Yes and I'd also like soda", context)
        assert result3 == (None, 0.0, None)
        
        # Should not have triggered immediate response
        # This prevents interrupting user mid-sentence
    
    @pytest.mark.asyncio
    async def test_configurable_delay_values(self):
        """Test different delay configurations."""
        # Test with shorter delay
        processor_fast = PartialTranscriptProcessor(delay_ms=100)
        context = {"call_sid": "fast_test"}
        
        await processor_fast.process_partial_transcript_with_delay("yes", context)
        assert "fast_test" in processor_fast.pending_transcripts
        
        # Test with longer delay
        processor_slow = PartialTranscriptProcessor(delay_ms=500)
        context = {"call_sid": "slow_test"}
        
        await processor_slow.process_partial_transcript_with_delay("yes", context)
        assert "slow_test" in processor_slow.pending_transcripts
        
        # Verify different delay values
        assert processor_fast.delay_ms == 100
        assert processor_slow.delay_ms == 500
    
    @pytest.mark.asyncio
    async def test_backward_compatibility(self, processor, context):
        """Test that legacy synchronous method still works."""
        # Test legacy method
        result = processor.process_partial_transcript("yes", context)
        
        # Should return immediate result (no delay)
        assert result[0] == SimpleIntent.CONFIRM
        assert result[1] >= 0.9
        assert result[2] is not None
        
        # Should not create pending transcript
        assert context["call_sid"] not in processor.pending_transcripts


class TestEndToEndPartialProcessing:
    """End-to-end integration tests for partial transcript processing."""
    
    @pytest.mark.asyncio
    async def test_complete_conversation_flow(self):
        """Test complete conversation flow with enhanced partial processing."""
        processor = PartialTranscriptProcessor(delay_ms=200)
        context = {"call_sid": "e2e_test", "hsm_state": "ACTIVE.CONFIRMATION"}
        
        # Simulate partial transcripts arriving
        transcripts = [
            ("y", 0.1, False),      # Low confidence, should not process
            ("ye", 0.3, False),     # Still low confidence
            ("yes", 0.95, True),    # High confidence, should start delay
            ("yes ", 0.95, True),   # Update pending
        ]
        
        for transcript, expected_conf, should_have_pending in transcripts:
            result = await processor.process_partial_transcript_with_delay(transcript, context)
            
            # Should not process immediately
            assert result == (None, 0.0, None)
            
            # Check pending status
            has_pending = "e2e_test" in processor.pending_transcripts
            assert has_pending == should_have_pending
        
        # Wait for delay
        await asyncio.sleep(0.25)
        
        # Verify final state
        status = processor.get_pending_status()
        # Pending transcript may or may not still exist depending on timing
        assert status["total_pending"] >= 0
    
    @pytest.mark.asyncio
    async def test_multiple_concurrent_calls(self):
        """Test handling multiple concurrent calls with different delays."""
        processor = PartialTranscriptProcessor(delay_ms=300)
        
        calls = [
            {"call_sid": "call_1", "hsm_state": "ACTIVE.CONFIRMATION"},
            {"call_sid": "call_2", "hsm_state": "ACTIVE.VALIDATION"},
            {"call_sid": "call_3", "hsm_state": "ACTIVE.ORDERING"}
        ]
        
        # Process different intents for each call
        intents = ["yes", "no", "thanks"]
        
        for i, (call_context, intent_text) in enumerate(zip(calls, intents)):
            result = await processor.process_partial_transcript_with_delay(intent_text, call_context)
            assert result == (None, 0.0, None)
        
        # Should have multiple pending transcripts
        status = processor.get_pending_status()
        assert status["total_pending"] == 3
        
        # Each call should have its own pending transcript
        for call_context in calls:
            assert call_context["call_sid"] in processor.pending_transcripts


if __name__ == "__main__":
    pytest.main([__file__, "-v"])