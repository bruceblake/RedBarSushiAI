"""
Voice controller for RedBarSushiAI using OpenAI Agents SDK.
This module provides the core voice controller for handling Twilio calls with OpenAI Agents SDK.
"""

import logging
import json
import time
import os
import traceback
from typing import Dict, Any, Optional, Tuple

from app.agents.factory import agent_factory
from app.utils.conversation_store_sdk import agents_conversation_store

logger = logging.getLogger(__name__)

class VoiceController:
    """Controller for handling voice interactions using Agents SDK."""
    
    def __init__(self):
        """Initialize the voice controller."""
        self.frontline_agent = None
        self.menu_agent = None
        self.initialize_agents()
    
    def initialize_agents(self):
        """Initialize all agents."""
        try:
            # Get the agents from the factory
            self.frontline_agent = agent_factory.get_frontline_agent()
            self.menu_agent = agent_factory.get_menu_agent()
            
            if self.frontline_agent and self.menu_agent:
                logger.info("Voice controller successfully initialized with agents")
            else:
                logger.error("Failed to initialize voice controller with agents")
        except Exception as e:
            logger.error(f"Error initializing voice controller: {str(e)}")
    
    def handle_call(self, call_sid: str, transcript: str) -> str:
        """
        Handle a voice call using Agents SDK.
        
        Args:
            call_sid: The Twilio call SID
            transcript: The transcribed speech input
            
        Returns:
            The agent's response text
        """
        if not self.frontline_agent:
            logger.error("Frontline Voice Agent not initialized")
            return "I'm sorry, our voice assistant is currently unavailable. Please try again later."
        
        # Process the input using the Frontline Voice Agent
        try:
            start_time = time.time()
            
            # Process the input
            response = self.frontline_agent.process_voice_input(call_sid, transcript)
            
            duration = time.time() - start_time
            logger.info(f"Processed voice input in {duration:.2f}s for call {call_sid}")
            
            return response
        except Exception as e:
            logger.error(f"Error processing voice input: {str(e)}")
            logger.error(traceback.format_exc())
            
            return "I'm sorry, but I'm having trouble processing your request. Please try again later."
    
    def handle_menu_question(self, call_sid: str, question: str) -> str:
        """
        Handle a menu question using the Menu Agent.
        
        Args:
            call_sid: The Twilio call SID
            question: The menu question
            
        Returns:
            The Menu Agent's response
        """
        if not self.menu_agent:
            logger.error("Menu Agent not initialized")
            return "I'm sorry, I don't have access to our menu information right now."
        
        # Process the question using the Menu Agent
        try:
            start_time = time.time()
            
            # Process the question
            response = self.menu_agent.process_menu_question(call_sid, question)
            
            duration = time.time() - start_time
            logger.info(f"Processed menu question in {duration:.2f}s for call {call_sid}")
            
            return response
        except Exception as e:
            logger.error(f"Error processing menu question: {str(e)}")
            logger.error(traceback.format_exc())
            
            return "I'm sorry, but I'm having trouble accessing our menu information right now."
    
    def get_call_state(self, call_sid: str) -> Dict[str, Any]:
        """
        Get the current state of a call.
        
        Args:
            call_sid: The Twilio call SID
            
        Returns:
            The current call state
        """
        return agents_conversation_store.get_call_state(call_sid)
    
    def process_realtime_audio(self, call_sid: str, audio_data: bytes) -> Tuple[str, bytes]:
        """
        Process realtime audio stream.
        
        Args:
            call_sid: The Twilio call SID
            audio_data: The audio data
            
        Returns:
            Tuple of (transcript, TTS audio)
        """
        # This is a placeholder that will be implemented in task #8
        # For now, just return a placeholder
        return (
            "Audio processing not yet implemented",
            b""
        )

# Singleton instance for easy import
voice_controller = VoiceController()