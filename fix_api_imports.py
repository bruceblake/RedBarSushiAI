#!/usr/bin/env python3
"""
Script to fix API model imports in RedBarSushiAI.
This addresses issues with TwimlParameter and VoiceResponse imports.
"""

import os
import logging
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_voice_async_imports():
    """Fix imports in app/api/voice_async.py."""
    voice_async_path = os.path.join('app', 'api', 'voice_async.py')
    
    if not os.path.exists(voice_async_path):
        logger.error(f"Could not find {voice_async_path}")
        return False
    
    try:
        # Read the file
        with open(voice_async_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if the problematic import exists
        if "from app.models.api import TwimlParameter" in content:
            # Replace the import
            content = content.replace(
                "from app.models.api import TwimlParameter", 
                "from app.utils.twilio_twiml import TwimlParameter"
            )
            logger.info("Fixed TwimlParameter import in voice_async.py")
        
        # Check if VoiceResponse is imported from models.api without a corresponding import from twilio
        if "from app.models.api import VoiceResponse" in content and "from twilio.twiml.voice_response import VoiceResponse" not in content:
            # Replace with the correct import
            content = content.replace(
                "from app.models.api import VoiceResponse", 
                "from app.models.api import VoiceResponseModel as VoiceResponse\nfrom twilio.twiml.voice_response import VoiceResponse as TwilioVoiceResponse"
            )
            logger.info("Fixed VoiceResponse import in voice_async.py")
        
        # Handle the case where both are imported on the same line
        if "from app.models.api import TwimlParameter, VoiceResponse" in content:
            content = content.replace(
                "from app.models.api import TwimlParameter, VoiceResponse",
                "from app.utils.twilio_twiml import TwimlParameter\nfrom app.models.api import VoiceResponseModel as VoiceResponse\nfrom twilio.twiml.voice_response import VoiceResponse as TwilioVoiceResponse"
            )
            logger.info("Fixed combined TwimlParameter and VoiceResponse imports in voice_async.py")
        
        # Write the changes back
        with open(voice_async_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return True
    except Exception as e:
        logger.error(f"Error fixing voice_async.py: {e}")
        return False

def ensure_voice_response_model_exists():
    """Ensure VoiceResponseModel exists in app/models/api.py."""
    api_models_path = os.path.join('app', 'models', 'api.py')
    
    if not os.path.exists(api_models_path):
        logger.error(f"Could not find {api_models_path}")
        return False
    
    try:
        # Read the file
        with open(api_models_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if VoiceResponseModel already exists
        if "class VoiceResponseModel(BaseModel)" in content:
            logger.info("VoiceResponseModel already exists in api.py")
            return True
        
        # If it doesn't exist, add it at the end of the file
        voice_response_model = """
class VoiceResponseModel(BaseModel):
    """Model for voice response API in FastAPI routes."""
    
    say_text: Optional[str] = None
    play_url: Optional[str] = None
    hangup: bool = False
    redirect_url: Optional[str] = None
    gather_params: Optional[Dict[str, Any]] = None
"""
        
        # Find where to insert (after the last class definition)
        lines = content.splitlines()
        
        # Find the last class in the file
        last_class_idx = -1
        for i, line in enumerate(lines):
            if line.strip().startswith("class "):
                last_class_idx = i
        
        if last_class_idx == -1:
            # If no class was found, add at the end
            content += voice_response_model
        else:
            # Find the end of the last class (first empty line after class variables)
            class_end_idx = last_class_idx
            in_class = True
            while in_class and class_end_idx < len(lines) - 1:
                class_end_idx += 1
                line = lines[class_end_idx].strip()
                if not line or (not line.startswith(' ') and not line.startswith('\t')):
                    in_class = False
            
            # Insert after the class
            lines.insert(class_end_idx + 1, voice_response_model)
            content = '\n'.join(lines)
        
        # Write the changes back
        with open(api_models_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info("Added VoiceResponseModel to api.py")
        return True
    except Exception as e:
        logger.error(f"Error updating api.py: {e}")
        return False

def main():
    logger.info("Starting API import fixes...")
    
    # Ensure the VoiceResponseModel exists
    if not ensure_voice_response_model_exists():
        logger.error("Failed to ensure VoiceResponseModel exists")
        return False
    
    # Fix imports in voice_async.py
    if not fix_voice_async_imports():
        logger.error("Failed to fix imports in voice_async.py")
        return False
    
    logger.info("API import fixes completed successfully")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)