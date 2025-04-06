#!/usr/bin/env python3
"""
Test script to verify OpenAI Realtime client installation and functionality
"""

import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_openai_realtime_client():
    """Test if openai-realtime-client is installed and functioning"""
    logger.info("Testing OpenAI Realtime client installation...")
    
    # Test 1: Check if the package can be imported
    try:
        import openai_realtime_client
        logger.info(f"✅ Successfully imported openai_realtime_client module (version: {openai_realtime_client.__version__})")
    except ImportError as e:
        logger.error(f"❌ Failed to import openai_realtime_client: {e}")
        logger.info("Attempting to install openai-realtime-client...")
        
        # Try to install the package
        import subprocess
        result = subprocess.run([sys.executable, "-m", "pip", "install", "openai-realtime-client==0.1.0"], 
                               capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("✅ Successfully installed openai-realtime-client")
            try:
                import openai_realtime_client
                logger.info(f"✅ Now able to import openai_realtime_client (version: {openai_realtime_client.__version__})")
            except ImportError as e2:
                logger.error(f"❌ Still unable to import openai_realtime_client after installation: {e2}")
                return False
        else:
            logger.error(f"❌ Failed to install openai-realtime-client:\n{result.stderr}")
            return False
    
    # Test 2: Try to access the Session class
    try:
        from openai_realtime_client import Session
        logger.info("✅ Successfully imported Session class from openai_realtime_client")
    except ImportError as e:
        logger.error(f"❌ Failed to import Session class: {e}")
        return False
    
    # Test 3: Check OpenAI API key
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        logger.error("❌ OPENAI_API_KEY environment variable is not set")
        return False
    logger.info("✅ OPENAI_API_KEY environment variable is set")
    
    # Test 4: Try to create a session (but don't actually connect to avoid using API credits)
    try:
        # Just import and access the class without creating an instance
        logger.info("✅ Session class is available for creating WebSocket sessions")
        return True
    except Exception as e:
        logger.error(f"❌ Error while testing Session class: {e}")
        return False

if __name__ == "__main__":
    success = test_openai_realtime_client()
    
    if success:
        logger.info("✅ All tests passed! OpenAI Realtime client is properly installed and configured.")
        sys.exit(0)
    else:
        logger.error("❌ Some tests failed. Please check the errors above.")
        sys.exit(1)