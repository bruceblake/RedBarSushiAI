"""
AI-driven global command detection and handling utilities.

This module provides functionality for detecting and handling global commands
that work across all conversation states using AI intelligence instead of hardcoded patterns.
"""

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
    """AI-driven global command detection for restaurant interactions."""
    
    def __init__(self):
        """Initialize the AI-driven global command detector."""
        pass
    
    async def detect_command(self, input_text: str) -> Tuple[GlobalCommand, float]:
        """
        Use AI to detect global commands in user input.
        
        Args:
            input_text: The user's input text
            
        Returns:
            Tuple of (command_type, confidence_score)
        """
        if not input_text:
            return GlobalCommand.NONE, 0.0
        
        try:
            from openai import AsyncOpenAI
            from app.config import settings
            
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a global command detector for restaurant phone ordering.

Analyze the user's input and determine if they're requesting a global system action.

Return ONLY a JSON object with:
{"command": "COMMAND_NAME", "confidence": 0.0-1.0}

Available commands:
- REPEAT: Asking to repeat/clarify what was just said
- START_OVER: Wanting to restart the entire order/conversation
- GO_BACK: Wanting to undo or return to previous step
- HELP: Asking for help or options
- CANCEL: Wanting to cancel/end the call/order
- NONE: Regular ordering conversation (not a global command)

Examples:
- "Can you repeat that?" → {"command": "REPEAT", "confidence": 0.95}
- "Let's start over" → {"command": "START_OVER", "confidence": 0.9}
- "I want food" → {"command": "NONE", "confidence": 0.0}
- "Cancel everything" → {"command": "CANCEL", "confidence": 0.95}
- "What are my options?" → {"command": "HELP", "confidence": 0.85}
- "Go back" → {"command": "GO_BACK", "confidence": 0.9}"""
                    },
                    {
                        "role": "user",
                        "content": input_text
                    }
                ],
                temperature=0.1,
                max_tokens=50
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Parse JSON response
            import json
            result = json.loads(result_text)
            
            command_str = result.get("command", "NONE")
            confidence = result.get("confidence", 0.0)
            
            # Convert string to GlobalCommand enum
            try:
                command = GlobalCommand(command_str)
            except ValueError:
                command = GlobalCommand.NONE
                confidence = 0.0
            
            if command != GlobalCommand.NONE:
                logger.info(f"AI detected global command: '{command.value}' (confidence: {confidence:.2f}) from input: '{input_text}'")
            
            return command, confidence
            
        except Exception as e:
            logger.error(f"Error in AI global command detection: {e}")
            # Conservative fallback - if AI fails, assume no global command
            return GlobalCommand.NONE, 0.0


class GlobalCommandContext:
    """AI-driven context for global command execution."""
    
    def __init__(self):
        """Initialize the global command context."""
        self.last_response = None
        self.last_response_time = None
    
    def update_last_response(self, response_text: str, timestamp: float):
        """Update the last response for potential REPEAT commands."""
        self.last_response = response_text
        self.last_response_time = timestamp
    
    async def execute_command(
        self, 
        command: GlobalCommand, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a global command using AI intelligence.
        
        Args:
            command: The global command to execute
            context: Current conversation context
            
        Returns:
            Dictionary with execution result and AI-generated response
        """
        try:
            from openai import AsyncOpenAI
            from app.config import settings
            
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            
            # Build context-aware prompt for command execution
            command_prompts = {
                GlobalCommand.REPEAT: "Generate a response that repeats the last system message in a natural way",
                GlobalCommand.START_OVER: "Generate a response that restarts the ordering conversation from the beginning",
                GlobalCommand.GO_BACK: "Generate a response that takes the customer back to the previous step",
                GlobalCommand.HELP: "Generate a helpful response that explains available options to the customer",
                GlobalCommand.CANCEL: "Generate a polite response that confirms order cancellation and offers alternatives"
            }
            
            if command not in command_prompts:
                return {"success": False, "message": "Unknown command"}
            
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are handling a global command for a restaurant ordering system.

Command: {command.value}
Task: {command_prompts[command]}

Context: {context}

Generate a natural, helpful response that appropriately handles this command.
Keep responses concise and friendly."""
                    },
                    {
                        "role": "user",
                        "content": f"Execute {command.value} command"
                    }
                ],
                temperature=0.3,
                max_tokens=150
            )
            
            response_text = response.choices[0].message.content.strip()
            
            return {
                "success": True,
                "command": command.value,
                "message": response_text,
                "action": self._get_command_action(command)
            }
            
        except Exception as e:
            logger.error(f"Error executing global command {command}: {e}")
            return {
                "success": False,
                "command": command.value,
                "message": "I'm sorry, I had trouble processing that request. Please try again.",
                "error": str(e)
            }
    
    def _get_command_action(self, command: GlobalCommand) -> str:
        """Get the system action for a command."""
        action_map = {
            GlobalCommand.REPEAT: "repeat_last_message",
            GlobalCommand.START_OVER: "restart_conversation",
            GlobalCommand.GO_BACK: "go_to_previous_step",
            GlobalCommand.HELP: "show_help_options", 
            GlobalCommand.CANCEL: "cancel_order"
        }
        return action_map.get(command, "none")


# Singleton instances for backward compatibility
global_command_detector = GlobalCommandDetector()
global_command_context = GlobalCommandContext()