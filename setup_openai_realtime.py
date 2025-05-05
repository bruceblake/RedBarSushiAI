#!/usr/bin/env python
"""
Set up and configure OpenAI Realtime client for RedBarSushiAI.
Handles both X11 and headless modes and ensures proper configuration.
"""

import os
import sys
import logging
import subprocess
import importlib.util

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger("openai_setup")

def check_openai_realtime():
    """Check if OpenAI Realtime client is installed and working."""
    try:
        # Check if the module is installed
        spec = importlib.util.find_spec("openai_realtime_client")
        if spec is None:
            logger.warning("OpenAI Realtime client is not installed")
            return False
        
        # Try to import the module
        import openai_realtime_client
        
        # Check version if available
        try:
            version = openai_realtime_client.__version__
            logger.info(f"OpenAI Realtime client version: {version}")
        except AttributeError:
            logger.warning("OpenAI Realtime client is installed but version information is not available")
        
        # Check if X11 is required and available
        x11_setup_success = os.environ.get("X11_SETUP_SUCCESS") == "true"
        if x11_setup_success:
            logger.info("X11 setup is successful, using X11 mode")
        else:
            logger.info("X11 setup not successful, using headless mode")
        
        # All checks passed
        logger.info("✅ OpenAI Realtime client is installed and configured")
        return True
    except ImportError as e:
        logger.error(f"Failed to import OpenAI Realtime client: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Error checking OpenAI Realtime client: {str(e)}")
        return False

def install_openai_realtime():
    """Install or upgrade OpenAI Realtime client."""
    try:
        # Install or upgrade with pip
        cmd = [sys.executable, "-m", "pip", "install", "--no-cache-dir", "--upgrade", "openai-realtime-client==0.1.0"]
        logger.info(f"Running command: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            check=True
        )
        
        # Check if installation was successful
        if result.returncode == 0:
            logger.info("✅ Successfully installed/upgraded OpenAI Realtime client")
            # Verify the installation
            if importlib.util.find_spec("openai_realtime_client") is not None:
                logger.info("✅ Verified OpenAI Realtime client installation")
                return True
            else:
                logger.error("❌ Failed to verify OpenAI Realtime client installation")
                return False
        else:
            logger.error(f"❌ Installation command failed with return code {result.returncode}")
            logger.error(f"Error output: {result.stderr.decode('utf-8')}")
            return False
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Failed to install OpenAI Realtime client: {str(e)}")
        logger.error(f"Error output: {e.stderr.decode('utf-8') if e.stderr else 'No error output'}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error during installation: {str(e)}")
        return False

def setup_openai_sdk():
    """Set up and configure OpenAI SDK."""
    try:
        # Check if OpenAI API key is set
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        if not openai_api_key:
            logger.warning("OPENAI_API_KEY environment variable is not set")
        else:
            # Partially mask API key for logging (show only first 4 chars)
            masked_key = openai_api_key[:4] + "..." + openai_api_key[-4:] if len(openai_api_key) > 8 else "***"
            logger.info(f"OPENAI_API_KEY is set: {masked_key}")
        
        # Install standard OpenAI SDK
        cmd = [sys.executable, "-m", "pip", "install", "--no-cache-dir", "--upgrade", "openai==1.77.0"]
        result = subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            check=True
        )
        
        if result.returncode == 0:
            logger.info("✅ Successfully installed/upgraded OpenAI SDK")
        else:
            logger.warning(f"OpenAI SDK installation command returned code {result.returncode}")
        
        # Check if OpenAI is importable
        try:
            import openai
            logger.info(f"OpenAI SDK version: {openai.__version__}")
            return True
        except ImportError as e:
            logger.error(f"Failed to import OpenAI SDK: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error checking OpenAI SDK: {str(e)}")
            return False
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Failed to install OpenAI SDK: {str(e)}")
        logger.error(f"Error output: {e.stderr.decode('utf-8') if e.stderr else 'No error output'}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error during OpenAI SDK setup: {str(e)}")
        return False

def configure_fallback_implementation():
    """Configure the fallback WebSocket implementation for environments without X11."""
    try:
        # Install required packages for WebSocket implementation
        packages = [
            "websockets==13.1",
            "aiohttp==3.11.13",
            "python-socketio==5.8.0",
            "eventlet==0.33.3"
        ]
        
        for package in packages:
            cmd = [sys.executable, "-m", "pip", "install", "--no-cache-dir", package]
            result = subprocess.run(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                check=True
            )
            
            if result.returncode == 0:
                logger.info(f"✅ Successfully installed {package}")
            else:
                logger.warning(f"Installation of {package} returned code {result.returncode}")
        
        # Set environment variable to use direct WebSocket implementation
        os.environ["USE_DIRECT_WEBSOCKET"] = "true"
        logger.info("✅ Configured fallback WebSocket implementation")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Failed to install fallback implementation package: {str(e)}")
        logger.error(f"Error output: {e.stderr.decode('utf-8') if e.stderr else 'No error output'}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error during fallback configuration: {str(e)}")
        return False

def main():
    """Main function to set up OpenAI Realtime client."""
    logger.info("Starting OpenAI Realtime client setup")
    
    # Set up OpenAI SDK first
    logger.info("Setting up OpenAI SDK...")
    openai_sdk_success = setup_openai_sdk()
    
    # Check if OpenAI Realtime client is already installed and working
    logger.info("Checking OpenAI Realtime client...")
    realtime_ready = check_openai_realtime()
    
    if not realtime_ready:
        logger.info("Installing/upgrading OpenAI Realtime client...")
        install_success = install_openai_realtime()
        
        if install_success:
            # Check again after installation
            realtime_ready = check_openai_realtime()
        else:
            logger.warning("Failed to install OpenAI Realtime client, will use fallback implementation")
    
    # Configure fallback implementation regardless (it's a good safety net)
    logger.info("Setting up fallback WebSocket implementation...")
    fallback_success = configure_fallback_implementation()
    
    # Final status
    if realtime_ready:
        logger.info("✅ OpenAI Realtime client is ready to use")
    elif fallback_success:
        logger.info("⚠️ Using fallback WebSocket implementation (OpenAI Realtime client setup failed)")
    else:
        logger.error("❌ Both OpenAI Realtime client and fallback implementation setup failed")
        return False
    
    logger.info("OpenAI Realtime client setup completed")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)