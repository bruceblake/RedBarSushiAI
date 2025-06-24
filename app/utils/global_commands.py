"""
Global command detection and handling utilities.

This module provides functionality for detecting and handling global commands
that work across all conversation states (e.g., "repeat that", "start over").
"""

import re
import logging
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum

from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)


class GlobalCommand(Enum):
    """Enumeration of global commands."""
    REPEAT = "REPEAT"
    START_OVER = "START_OVER"
    GO_BACK = "GO_BACK"
    HELP = "HELP"
    CANCEL = "CANCEL"
    NONE = "NONE"


class GlobalCommandDetector:
    """Detects global commands in user input."""
    
    # Command patterns mapped to their command type
    COMMAND_PATTERNS = {
        GlobalCommand.REPEAT: [
            r"\b(repeat|say)\s+(that|it)\s*(again)?\b",
            r"\bwhat\s+did\s+you\s+(just\s+)?say\b",
            r"\b(can|could)\s+you\s+(please\s+)?repeat\b",
            r"\b(say|tell)\s+(that|it)\s+(again|once\s+more)\b",
            r"\bpardon(\s+me)?\b",
            r"\bcome\s+again\b",
            r"\bone\s+more\s+time\b",
            r"\bdidn'?t\s+(quite\s+)?(catch|hear|get)\s+that\b"
        ],
        GlobalCommand.START_OVER: [
            r"\bstart\s+over\b",
            r"\b(begin|start)\s+(again|fresh|from\s+the\s+beginning)\b",
            r"\blet'?s\s+start\s+(over|fresh|again)\b",
            r"\breset\b",
            r"\b(restart|redo)\s+(the\s+)?(order|conversation)\b",
            r"\bscratch\s+that\s+start\s+over\b",
            r"\bcancel\s+everything\s+and\s+start\s+(over|again)\b"
        ],
        GlobalCommand.GO_BACK: [
            r"\bgo\s+back\b",
            r"\b(previous|last)\s+(step|screen|menu)\b",
            r"\bundo\s+(that|the\s+last)\b",
            r"\btake\s+me\s+back\b",
            r"\bback\s+up\b",
            r"\blet'?s\s+go\s+back\b",
            r"\breturn\s+to\s+(the\s+)?(previous|last)\b",
            r"\bchange\s+my\s+mind\b"
        ],
        GlobalCommand.HELP: [
            r"\bhelp\s*(me)?\b",
            r"\bwhat\s+can\s+(i|you)\s+do\b",
            r"\bi'?m\s+(confused|lost|stuck)\b",
            r"\bwhat\s+are\s+my\s+options\b",
            r"\bshow\s+me\s+(the\s+)?options\b",
            r"\bi\s+need\s+(help|assistance)\b",
            r"\bhow\s+do\s+i\b",
            r"\bwhat\s+do\s+i\s+do\s+(now|next)\b"
        ],
        GlobalCommand.CANCEL: [
            r"\bcancel\s*(everything|all|order)?\b",
            r"\bstop\s*(everything|the\s+order)?\b",
            r"\bend\s+(the\s+)?(call|conversation)\b",
            r"\bnevermind\b",
            r"\bforget\s+(it|everything|the\s+order)\b",
            r"\bi\s+don'?t\s+want\s+(to\s+order\s+)?anything\b",
            r"\bhang\s+up\b",
            r"\bgoodbye\b"
        ]
    }
    
    def __init__(self):
        """Initialize the global command detector."""
        # Compile regex patterns for efficiency
        self.compiled_patterns = {}
        for command, patterns in self.COMMAND_PATTERNS.items():
            self.compiled_patterns[command] = [
                re.compile(pattern, re.IGNORECASE) 
                for pattern in patterns
            ]
    
    def detect_command(self, input_text: str) -> Tuple[GlobalCommand, float]:
        """
        Detect if the input contains a global command.
        
        Args:
            input_text: The user's input text
            
        Returns:
            Tuple of (command_type, confidence_score)
        """
        if not input_text:
            return GlobalCommand.NONE, 0.0
        
        # Clean the input
        cleaned_input = input_text.strip().lower()
        
        # Check each command type
        for command, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(cleaned_input):
                    # Calculate confidence based on how much of the input matches
                    match = pattern.search(cleaned_input)
                    match_ratio = len(match.group()) / len(cleaned_input)
                    confidence = min(0.9 + (match_ratio * 0.1), 1.0)
                    
                    logger.info(
                        f"Detected global command: {command.value}",
                        input=input_text,
                        confidence=confidence
                    )
                    return command, confidence
        
        return GlobalCommand.NONE, 0.0
    
    def is_global_command(self, input_text: str, threshold: float = 0.8) -> bool:
        """
        Check if the input is a global command with sufficient confidence.
        
        Args:
            input_text: The user's input text
            threshold: Minimum confidence threshold
            
        Returns:
            True if a global command was detected above threshold
        """
        command, confidence = self.detect_command(input_text)
        return command != GlobalCommand.NONE and confidence >= threshold


class GlobalCommandContext:
    """Manages context needed for global command execution."""
    
    def __init__(self):
        """Initialize command context."""
        self.last_response: Optional[str] = None
        self.last_response_time: Optional[float] = None
        self.state_history: List[str] = []
        self.context_history: List[Dict[str, Any]] = []
        self.max_history_size = 10
    
    def update_last_response(self, response: str, timestamp: float):
        """Update the last response for repeat functionality."""
        self.last_response = response
        self.last_response_time = timestamp
    
    def push_state(self, state: str, context: Dict[str, Any]):
        """Push a state onto the history stack."""
        self.state_history.append(state)
        self.context_history.append(context.copy())
        
        # Limit history size
        if len(self.state_history) > self.max_history_size:
            self.state_history.pop(0)
            self.context_history.pop(0)
    
    def pop_state(self) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Pop the previous state from history."""
        if len(self.state_history) > 1:  # Keep at least one state
            # Remove current state
            self.state_history.pop()
            self.context_history.pop()
            
            # Return previous state
            return self.state_history[-1], self.context_history[-1]
        return None
    
    def clear_history(self):
        """Clear state history (for start over)."""
        self.state_history.clear()
        self.context_history.clear()
        self.last_response = None
        self.last_response_time = None


# Singleton instances
global_command_detector = GlobalCommandDetector()
global_command_context = GlobalCommandContext()