"""
Partial Transcript Processing for RedBarSushiAI.

This module implements high-confidence partial transcript processing
to reduce perceived latency for simple, common user intents.
"""

import re
import asyncio
import logging
import time
from typing import Dict, Any, Optional, Tuple, Set
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class SimpleIntent(Enum):
    """Simple intents that can be detected from partial transcripts."""
    CONFIRM = "confirm"           # "yes", "yeah", "that's right", "correct"
    REJECT = "reject"             # "no", "nope", "that's wrong", "not right"
    CANCEL = "cancel"             # "cancel", "stop", "never mind"
    REPEAT = "repeat"             # "repeat", "say that again", "what"
    HELP = "help"                 # "help", "I need help"
    CONTINUE = "continue"         # "continue", "go ahead", "next"
    THANK_YOU = "thank_you"       # "thank you", "thanks"

@dataclass
class PendingTranscript:
    """Track pending transcript for end-of-speech detection."""
    text: str
    confidence: float
    intent: SimpleIntent
    response_data: Dict[str, Any]
    first_detected: float
    last_updated: float
    call_sid: str

class PartialTranscriptProcessor:
    """
    Processes partial transcripts for high-confidence simple intents.
    
    This processor identifies common user responses that can be acted upon
    immediately without waiting for the final transcript, reducing latency
    and improving conversation flow.
    """
    
    def __init__(self, 
                 confidence_threshold: Optional[float] = None,
                 delay_ms: Optional[int] = None,
                 end_of_speech_threshold: Optional[float] = None):
        """
        Initialize the partial transcript processor.
        
        Args:
            confidence_threshold: Minimum confidence required to process partial transcript
            delay_ms: Delay in milliseconds before processing partial transcript
            end_of_speech_threshold: Confidence threshold for end-of-speech detection
        """
        from app.config import settings
        
        self.confidence_threshold = confidence_threshold or settings.PARTIAL_TRANSCRIPT_CONFIDENCE_THRESHOLD
        self.delay_ms = delay_ms or settings.PARTIAL_TRANSCRIPT_DELAY_MS
        self.end_of_speech_threshold = end_of_speech_threshold or settings.PARTIAL_TRANSCRIPT_END_OF_SPEECH_THRESHOLD
        
        # Track pending transcripts for end-of-speech detection
        self.pending_transcripts: Dict[str, PendingTranscript] = {}
        
        # Set of words that typically indicate continuation
        self.continuation_indicators: Set[str] = {
            "and", "also", "plus", "with", "but", "however", "actually", 
            "wait", "hold", "um", "uh", "er", "well", "so", "then"
        }
        
        # Define high-confidence patterns for each intent
        self.intent_patterns = {
            SimpleIntent.CONFIRM: [
                # Positive confirmations
                r'\b(yes|yeah|yep|yup|sure|okay|ok|right|correct|exactly|absolutely)\b',
                r'\b(that\'s right|that\'s correct|sounds good|looks good)\b',
                r'\b(perfect|great|good)\b'
            ],
            SimpleIntent.REJECT: [
                # Negative responses
                r'\b(no|nope|nah|not|wrong)\b',
                r'\b(that\'s wrong|that\'s not right|incorrect)\b',
                r'\b(I don\'t want|not that)\b'
            ],
            SimpleIntent.CANCEL: [
                # Cancellation requests
                r'\b(cancel|stop|quit|exit|never mind|forget it)\b',
                r'\b(I don\'t want to|cancel that|stop this)\b'
            ],
            SimpleIntent.REPEAT: [
                # Repeat requests
                r'\b(repeat|again|what|pardon|excuse me)\b',
                r'\b(say that again|can you repeat|didn\'t hear)\b',
                r'\b(what did you say|come again)\b'
            ],
            SimpleIntent.HELP: [
                # Help requests
                r'\b(help|assistance|support)\b',
                r'\b(I need help|can you help|help me)\b',
                r'\b(I don\'t understand|confused)\b'
            ],
            SimpleIntent.CONTINUE: [
                # Continue/proceed
                r'\b(continue|proceed|go ahead|next|keep going)\b',
                r'\b(that\'s all|I\'m done|finished)\b'
            ],
            SimpleIntent.THANK_YOU: [
                # Gratitude expressions
                r'\b(thank you|thanks|thank ya|appreciate)\b',
                r'\b(thanks a lot|thank you very much)\b'
            ]
        }
        
        # Compile patterns for better performance
        self.compiled_patterns = {}
        for intent, patterns in self.intent_patterns.items():
            self.compiled_patterns[intent] = [
                re.compile(pattern, re.IGNORECASE) for pattern in patterns
            ]
        
        logger.info(f"Partial transcript processor initialized with {self.confidence_threshold} confidence threshold, "
                   f"{self.delay_ms}ms delay, {self.end_of_speech_threshold} end-of-speech threshold")
    
    async def process_partial_transcript_with_delay(
        self, 
        transcript: str, 
        conversation_context: Dict[str, Any]
    ) -> Tuple[Optional[SimpleIntent], float, Optional[Dict[str, Any]]]:
        """
        Process a partial transcript with end-of-speech detection and configurable delay.
        
        This method implements sophisticated end-of-speech detection to prevent
        premature responses when users are still speaking (e.g., "Yes, and I'd also like...").
        
        Args:
            transcript: Partial transcript text
            conversation_context: Current conversation context
            
        Returns:
            Tuple of (detected_intent, confidence, response_data)
            Returns (None, 0.0, None) if no high-confidence intent detected or still speaking
        """
        if not transcript or len(transcript.strip()) < 2:
            return None, 0.0, None
        
        call_sid = conversation_context.get("call_sid", "unknown")
        current_time = time.time()
        
        # First, detect intent without processing
        intent, confidence, response_data = self._detect_intent_only(transcript, conversation_context)
        
        if intent is None or confidence < self.confidence_threshold:
            # Clean up any pending transcript for this call
            if call_sid in self.pending_transcripts:
                del self.pending_transcripts[call_sid]
            return None, 0.0, None
        
        # Check for end-of-speech indicators
        if self._indicates_continuation(transcript):
            logger.debug(f"Transcript indicates continuation, not processing: '{transcript}'")
            return None, 0.0, None
        
        # Handle pending transcript
        if call_sid in self.pending_transcripts:
            pending = self.pending_transcripts[call_sid]
            
            # Update existing pending transcript
            pending.text = transcript
            pending.confidence = confidence
            pending.response_data = response_data
            pending.last_updated = current_time
            
            # Check if enough time has passed since first detection
            time_since_first = (current_time - pending.first_detected) * 1000  # Convert to ms
            
            if time_since_first >= self.delay_ms:
                # Enough time has passed, process the intent
                logger.info(f"Processing delayed intent after {time_since_first:.0f}ms: {intent.value}")
                
                # Clean up pending transcript
                del self.pending_transcripts[call_sid]
                
                return intent, confidence, response_data
        else:
            # New high-confidence intent detected, start delay timer
            self.pending_transcripts[call_sid] = PendingTranscript(
                text=transcript,
                confidence=confidence,
                intent=intent,
                response_data=response_data,
                first_detected=current_time,
                last_updated=current_time,
                call_sid=call_sid
            )
            
            logger.debug(f"Started delay timer for intent {intent.value}, will process in {self.delay_ms}ms")
            
            # Schedule processing after delay
            asyncio.create_task(self._delayed_processing(call_sid))
        
        return None, 0.0, None
    
    async def _delayed_processing(self, call_sid: str):
        """Process pending transcript after delay if still valid."""
        await asyncio.sleep(self.delay_ms / 1000.0)  # Convert ms to seconds
        
        if call_sid in self.pending_transcripts:
            pending = self.pending_transcripts[call_sid]
            current_time = time.time()
            
            # Check if transcript is still recent (not updated for a while)
            time_since_update = (current_time - pending.last_updated) * 1000
            
            if time_since_update >= (self.delay_ms * 0.8):  # 80% of delay time
                logger.info(f"Auto-processing delayed intent: {pending.intent.value}")
                
                # This would trigger the response through callback mechanism
                # Implementation depends on the specific voice processing architecture
                await self._trigger_delayed_response(pending)
                
                # Clean up
                del self.pending_transcripts[call_sid]
    
    async def _trigger_delayed_response(self, pending: PendingTranscript):
        """Trigger a delayed response for a pending transcript."""
        # This is a placeholder for the actual response triggering mechanism
        # In practice, this would interface with the voice processing system
        logger.info(f"Triggering delayed response for {pending.intent.value}: {pending.response_data}")
    
    def _detect_intent_only(
        self, 
        transcript: str, 
        conversation_context: Dict[str, Any]
    ) -> Tuple[Optional[SimpleIntent], float, Optional[Dict[str, Any]]]:
        """
        Detect intent from transcript without processing/delay logic.
        
        Args:
            transcript: Partial transcript text
            conversation_context: Current conversation context
            
        Returns:
            Tuple of (detected_intent, confidence, response_data)
        """
        transcript_clean = transcript.strip().lower()
        logger.debug(f"Detecting intent in partial transcript: '{transcript_clean}'")
        
        # Check each intent pattern
        for intent, patterns in self.compiled_patterns.items():
            confidence = self._calculate_intent_confidence(transcript_clean, patterns)
            
            if confidence >= self.confidence_threshold:
                logger.debug(f"Intent detected: {intent.value} (confidence: {confidence:.2f})")
                
                # Generate appropriate response data
                response_data = self._generate_response_data(intent, conversation_context)
                
                return intent, confidence, response_data
        
        return None, 0.0, None
    
    def _indicates_continuation(self, transcript: str) -> bool:
        """
        Check if the transcript indicates the user is likely to continue speaking.
        
        Args:
            transcript: Transcript text to analyze
            
        Returns:
            True if transcript indicates continuation
        """
        transcript_lower = transcript.lower().strip()
        
        # Check for continuation indicators at the end
        words = transcript_lower.split()
        if not words:
            return False
        
        # Check if transcript ends with continuation indicators
        last_words = words[-2:] if len(words) >= 2 else words
        for word in last_words:
            if word in self.continuation_indicators:
                return True
        
        # Check for incomplete sentences (ending with comma, "and", etc.)
        if transcript_lower.endswith((',', ' and', ' also', ' plus', ' with', ' but')):
            return True
        
        # Check for pause fillers that typically indicate more speech
        pause_patterns = [
            r'\b(um|uh|er|ah|hmm|well)\s*$',
            r'\band\s*$',
            r'\bso\s*$',
            r'\bthen\s*$'
        ]
        
        for pattern in pause_patterns:
            if re.search(pattern, transcript_lower):
                return True
        
        return False
    
    def process_partial_transcript(
        self, 
        transcript: str, 
        conversation_context: Dict[str, Any]
    ) -> Tuple[Optional[SimpleIntent], float, Optional[Dict[str, Any]]]:
        """
        Legacy synchronous method for backward compatibility.
        
        This method provides immediate processing without delay for cases
        where end-of-speech detection is not needed.
        """
        return self._detect_intent_only(transcript, conversation_context)
    
    def _calculate_intent_confidence(self, transcript: str, patterns: list) -> float:
        """
        Calculate confidence score for an intent based on pattern matching.
        
        Args:
            transcript: Cleaned transcript text
            patterns: Compiled regex patterns for the intent
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        matches = 0
        total_patterns = len(patterns)
        
        for pattern in patterns:
            if pattern.search(transcript):
                matches += 1
        
        if matches == 0:
            return 0.0
        
        # Base confidence from pattern matching
        pattern_confidence = matches / total_patterns
        
        # Boost confidence for exact matches or very short transcripts
        # that match common responses
        if transcript in ['yes', 'no', 'okay', 'thanks', 'help', 'cancel']:
            pattern_confidence = min(1.0, pattern_confidence + 0.3)
        
        # Reduce confidence for very long transcripts (likely incomplete thoughts)
        if len(transcript) > 50:
            pattern_confidence *= 0.8
        
        return min(1.0, pattern_confidence)
    
    def _generate_response_data(
        self, 
        intent: SimpleIntent, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate response data for a detected intent.
        
        Args:
            intent: Detected simple intent
            context: Conversation context
            
        Returns:
            Response data structure
        """
        current_state = context.get("hsm_state", "unknown")
        
        response_data = {
            "intent": intent.value,
            "partial_processing": True,
            "requires_immediate_response": True
        }
        
        # State-specific response generation
        if intent == SimpleIntent.CONFIRM:
            if current_state in ["ACTIVE.CONFIRMATION", "ACTIVE.VALIDATION"]:
                response_data.update({
                    "action": "proceed_with_confirmation",
                    "response_text": "Perfect! Processing your order now.",
                    "triggers_state_transition": True
                })
            else:
                response_data.update({
                    "action": "acknowledge_confirmation",
                    "response_text": "Great!",
                    "triggers_state_transition": False
                })
        
        elif intent == SimpleIntent.REJECT:
            response_data.update({
                "action": "handle_rejection",
                "response_text": "No problem, let me help you with that.",
                "triggers_state_transition": True
            })
        
        elif intent == SimpleIntent.CANCEL:
            response_data.update({
                "action": "initiate_cancellation",
                "response_text": "I understand. Would you like to cancel your order?",
                "triggers_state_transition": True,
                "requires_confirmation": True
            })
        
        elif intent == SimpleIntent.REPEAT:
            response_data.update({
                "action": "repeat_last_message",
                "response_text": None,  # Will repeat previous message
                "triggers_state_transition": False
            })
        
        elif intent == SimpleIntent.HELP:
            response_data.update({
                "action": "provide_help",
                "response_text": "I'm here to help! What would you like to know?",
                "triggers_state_transition": False
            })
        
        elif intent == SimpleIntent.THANK_YOU:
            response_data.update({
                "action": "acknowledge_thanks",
                "response_text": "You're very welcome!",
                "triggers_state_transition": False
            })
        
        return response_data
    
    def should_process_partial(
        self, 
        transcript: str, 
        context: Dict[str, Any]
    ) -> bool:
        """
        Determine if a partial transcript should be processed.
        
        Args:
            transcript: Partial transcript text
            context: Conversation context
            
        Returns:
            True if transcript should be processed immediately
        """
        # Don't process very short or empty transcripts
        if not transcript or len(transcript.strip()) < 2:
            return False
        
        # Don't process if we're in a complex state requiring detailed input
        complex_states = [
            "ACTIVE.ORDERING.MENU_INQUIRY",
            "ACTIVE.ORDERING.ITEM_CUSTOMIZATION",
            "ACTIVE.GREETING"  # Name collection requires full input
        ]
        
        current_state = context.get("hsm_state")
        if current_state in complex_states:
            return False
        
        # Process if transcript looks complete for simple intents
        simple_complete_patterns = [
            r'^\s*(yes|no|okay|ok|thanks|help|cancel)\s*$',
            r'^\s*(that\'s right|that\'s wrong|never mind)\s*$'
        ]
        
        for pattern in simple_complete_patterns:
            if re.match(pattern, transcript.strip(), re.IGNORECASE):
                return True
        
        return False
    
    def cleanup_stale_pending_transcripts(self, max_age_seconds: float = 10.0):
        """
        Clean up pending transcripts that are too old.
        
        Args:
            max_age_seconds: Maximum age in seconds before cleaning up pending transcript
        """
        current_time = time.time()
        stale_calls = []
        
        for call_sid, pending in self.pending_transcripts.items():
            age = current_time - pending.first_detected
            if age > max_age_seconds:
                stale_calls.append(call_sid)
        
        for call_sid in stale_calls:
            logger.debug(f"Cleaning up stale pending transcript for call {call_sid}")
            del self.pending_transcripts[call_sid]
    
    def cancel_pending_transcript(self, call_sid: str) -> bool:
        """
        Cancel a pending transcript for a specific call.
        
        Args:
            call_sid: Call SID to cancel pending transcript for
            
        Returns:
            True if a pending transcript was cancelled, False otherwise
        """
        if call_sid in self.pending_transcripts:
            logger.debug(f"Cancelling pending transcript for call {call_sid}")
            del self.pending_transcripts[call_sid]
            return True
        return False
    
    def get_pending_status(self) -> Dict[str, Any]:
        """
        Get status of pending transcripts for monitoring.
        
        Returns:
            Status information about pending transcripts
        """
        current_time = time.time()
        
        status = {
            "total_pending": len(self.pending_transcripts),
            "pending_by_intent": {},
            "oldest_pending_age_ms": 0,
            "average_pending_age_ms": 0
        }
        
        if self.pending_transcripts:
            ages = []
            for pending in self.pending_transcripts.values():
                age_ms = (current_time - pending.first_detected) * 1000
                ages.append(age_ms)
                
                intent_name = pending.intent.value
                status["pending_by_intent"][intent_name] = status["pending_by_intent"].get(intent_name, 0) + 1
            
            status["oldest_pending_age_ms"] = max(ages)
            status["average_pending_age_ms"] = sum(ages) / len(ages)
        
        return status

# Global processor instance
_processor: Optional[PartialTranscriptProcessor] = None

def get_partial_processor() -> PartialTranscriptProcessor:
    """Get or create the global partial transcript processor."""
    global _processor
    if _processor is None:
        _processor = PartialTranscriptProcessor()
    return _processor

def process_partial_transcript(
    transcript: str, 
    context: Dict[str, Any]
) -> Tuple[Optional[SimpleIntent], float, Optional[Dict[str, Any]]]:
    """
    Process a partial transcript for high-confidence simple intents.
    
    Args:
        transcript: Partial transcript text
        context: Conversation context
        
    Returns:
        Tuple of (intent, confidence, response_data)
    """
    processor = get_partial_processor()
    return processor.process_partial_transcript(transcript, context)

async def process_partial_transcript_with_delay(
    transcript: str, 
    context: Dict[str, Any]
) -> Tuple[Optional[SimpleIntent], float, Optional[Dict[str, Any]]]:
    """
    Process a partial transcript with end-of-speech detection and configurable delay.
    
    Args:
        transcript: Partial transcript text
        context: Conversation context
        
    Returns:
        Tuple of (intent, confidence, response_data)
    """
    processor = get_partial_processor()
    return await processor.process_partial_transcript_with_delay(transcript, context)