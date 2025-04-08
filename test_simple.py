#!/usr/bin/env python3
"""
Simple test script for verifying that the syntax is correct in realtime_audio.py
"""

import sys
import os
import logging

# Set up basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Make sure realtime_audio.py is in the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# First, try to import the file to check for any syntax errors
logger.info("Testing import of realtime_audio.py...")
try:
    from app.utils.realtime_audio import get_audio_processor
    logger.info("✅ Successfully imported get_audio_processor from realtime_audio.py")
except SyntaxError as e:
    logger.error(f"❌ Syntax error in realtime_audio.py: {e}")
    sys.exit(1)
except Exception as e:
    logger.error(f"Error importing realtime_audio.py: {e}")
    sys.exit(1)

# Try to initialize the RealtimeAudioProcessor class
logger.info("Testing RealtimeAudioProcessor class...")
try:
    from app.utils.realtime_audio import RealtimeAudioProcessor
    processor = RealtimeAudioProcessor()
    logger.info("✅ Successfully created RealtimeAudioProcessor instance")
except Exception as e:
    logger.error(f"Error creating RealtimeAudioProcessor: {e}")

# Try importing RealtimeClient if available
logger.info("Testing import of RealtimeClient from openai_realtime_client...")
try:
    import openai_realtime_client
    logger.info(f"openai_realtime_client contents: {dir(openai_realtime_client)}")
    
    try:
        from openai_realtime_client import RealtimeClient
        logger.info("✅ Successfully imported RealtimeClient")
    except ImportError:
        logger.warning("❌ Could not import RealtimeClient directly")
except ImportError:
    logger.warning("❌ openai_realtime_client module not available")

logger.info("All tests completed!")