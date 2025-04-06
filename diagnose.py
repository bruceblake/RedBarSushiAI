#!/usr/bin/env python3
"""
Diagnostic script for troubleshooting WebSocket and audio processing issues
"""

import os
import sys
import logging
import traceback
import importlib
import tempfile

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set environment variables
os.environ['PYNPUT_HEADLESS'] = '1'
os.environ['NO_X11'] = '1'
os.environ['HEADLESS'] = '1'
os.environ['DISPLAY'] = ':99'
os.environ['OPENAI_REALTIME_AVAILABLE'] = '1'

def check_system_info():
    """Check basic system information"""
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Platform: {sys.platform}")
    logger.info(f"Working directory: {os.getcwd()}")
    logger.info(f"Python executable: {sys.executable}")
    
    # Check environment variables
    env_vars = ['DISPLAY', 'PYNPUT_HEADLESS', 'NO_X11', 'HEADLESS', 'OPENAI_API_KEY', 'OPENAI_REALTIME_AVAILABLE']
    for var in env_vars:
        logger.info(f"Environment variable {var}: {'SET' if os.environ.get(var) else 'NOT SET'}")

def test_dependencies():
    """Test importing key dependencies"""
    dependencies = [
        'flask', 
        'flask_sock', 
        'openai', 
        'openai_realtime_client', 
        'websockets', 
        'python_socketio', 
        'gevent', 
        'eventlet'
    ]
    
    for dep in dependencies:
        try:
            module = importlib.import_module(dep.replace('_', '.'))
            version = getattr(module, '__version__', 'unknown')
            logger.info(f"✅ Successfully imported {dep} (version: {version})")
        except ImportError as e:
            logger.error(f"❌ Failed to import {dep}: {e}")
        except Exception as e:
            logger.error(f"❌ Error checking {dep}: {e}")

def test_openai_api():
    """Test OpenAI API connectivity"""
    try:
        import openai
        from openai import OpenAI
        
        logger.info(f"Using OpenAI Python package version: {openai.__version__}")
        
        # Test the API key
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            logger.error("❌ OPENAI_API_KEY environment variable is not set")
            return False
            
        # Initialize the client
        client = OpenAI(api_key=api_key)
        
        # Test a simple completion
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello, this is a test."}],
            max_tokens=5
        )
        
        # Check for successful response
        if response.choices and response.choices[0].message.content:
            logger.info(f"✅ OpenAI API test successful. Response: {response.choices[0].message.content}")
            return True
        else:
            logger.error("❌ OpenAI API test failed: No content in response")
            return False
            
    except Exception as e:
        logger.error(f"❌ OpenAI API test failed: {e}")
        logger.error(traceback.format_exc())
        return False

def test_realtime_client():
    """Test OpenAI Realtime client"""
    try:
        import openai_realtime_client
        from openai_realtime_client import Session
        
        logger.info(f"Using OpenAI Realtime client version: {openai_realtime_client.__version__}")
        
        # Test creating a session (without actually connecting)
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            logger.error("❌ OPENAI_API_KEY environment variable is not set")
            return False
            
        # Just check that the Session class is accessible
        logger.info("✅ OpenAI Realtime client Session class is accessible")
        return True
        
    except Exception as e:
        logger.error(f"❌ OpenAI Realtime client test failed: {e}")
        logger.error(traceback.format_exc())
        return False

def test_audio_processor():
    """Test the audio processor implementation"""
    try:
        # Try to import our audio processor
        from app.utils.realtime_audio import get_audio_processor
        
        # Get the processor instance
        processor = get_audio_processor()
        logger.info(f"✅ Successfully created audio processor: {type(processor).__name__}")
        
        # Check processor capabilities
        capabilities = {
            "process_audio": hasattr(processor, "process_audio"),
            "process_audio_stream": hasattr(processor, "process_audio_stream"),
            "generate_speech": hasattr(processor, "generate_speech"),
            "process_conversation": hasattr(processor, "process_conversation")
        }
        
        logger.info(f"Audio processor capabilities: {capabilities}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Audio processor test failed: {e}")
        logger.error(traceback.format_exc())
        return False

def test_filesystem():
    """Test filesystem access for temporary files (needed for audio processing)"""
    try:
        # Test creating a temporary file
        with tempfile.NamedTemporaryFile(suffix=".mp3") as temp_file:
            temp_file.write(b"test data")
            temp_file.flush()
            
            # Check that we can read from it
            with open(temp_file.name, "rb") as f:
                data = f.read()
                
            logger.info(f"✅ Successfully created and read temporary file with {len(data)} bytes")
        
        # Test directory permissions
        test_dirs = ["/tmp", "/app", "."]
        for test_dir in test_dirs:
            if os.path.exists(test_dir):
                writable = os.access(test_dir, os.W_OK)
                readable = os.access(test_dir, os.R_OK)
                logger.info(f"Directory {test_dir}: Readable={readable}, Writable={writable}")
            else:
                logger.info(f"Directory {test_dir} does not exist")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Filesystem test failed: {e}")
        logger.error(traceback.format_exc())
        return False

def run_all_tests():
    """Run all diagnostic tests"""
    logger.info("=" * 60)
    logger.info("Starting diagnostic tests")
    logger.info("=" * 60)
    
    # System info
    logger.info("\n[1] Checking system information...")
    check_system_info()
    
    # Dependencies
    logger.info("\n[2] Checking dependencies...")
    test_dependencies()
    
    # OpenAI API
    logger.info("\n[3] Testing OpenAI API...")
    test_openai_api()
    
    # Realtime client
    logger.info("\n[4] Testing OpenAI Realtime client...")
    test_realtime_client()
    
    # Audio processor
    logger.info("\n[5] Testing audio processor...")
    test_audio_processor()
    
    # Filesystem
    logger.info("\n[6] Testing filesystem access...")
    test_filesystem()
    
    logger.info("=" * 60)
    logger.info("Diagnostic tests complete")
    logger.info("=" * 60)

if __name__ == "__main__":
    run_all_tests()