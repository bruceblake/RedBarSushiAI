#!/usr/bin/env python3
"""
Test script for OpenAI Realtime client.
This script checks if the OpenAI Realtime client is correctly installed and can connect to X11.
"""

import os
import sys
import importlib.util
import subprocess

def print_header(text):
    """Print a header with decoration."""
    print("\n" + "=" * 80)
    print(f" {text} ".center(80, "="))
    print("=" * 80)

def print_success(text):
    """Print a success message."""
    print(f"✅ {text}")

def print_warning(text):
    """Print a warning message."""
    print(f"⚠️ {text}")

def print_error(text):
    """Print an error message."""
    print(f"❌ {text}")

def check_openai_realtime_installed():
    """Check if OpenAI Realtime client is installed."""
    spec = importlib.util.find_spec("openai_realtime_client")
    if spec is not None:
        try:
            import openai_realtime_client
            print_success(f"OpenAI Realtime client is installed (version: {getattr(openai_realtime_client, '__version__', 'unknown')})")
            return True
        except ImportError as e:
            print_error(f"OpenAI Realtime client is installed but could not be imported: {str(e)}")
            return False
    else:
        print_error("OpenAI Realtime client is not installed")
        
        # Try to install it
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "openai-realtime-client==0.1.0"], check=True)
            print_success("Successfully installed OpenAI Realtime client")
            return True
        except Exception as e:
            print_error(f"Failed to install OpenAI Realtime client: {str(e)}")
            return False

def check_x11_display():
    """Check if X11 display is working."""
    display = os.environ.get("DISPLAY")
    if display:
        print(f"DISPLAY environment variable is set to: {display}")
        try:
            result = subprocess.run(["xdpyinfo"], capture_output=True, text=True)
            if result.returncode == 0:
                print_success(f"X11 display {display} is working")
                return True
            else:
                print_error(f"X11 display {display} is not working: {result.stderr}")
                return False
        except FileNotFoundError:
            print_error("xdpyinfo command not found. X11 utilities may not be installed.")
            return False
    else:
        print_error("DISPLAY environment variable is not set")
        return False

def test_realtime_client_initialization():
    """Test if the OpenAI Realtime client can be initialized."""
    try:
        import openai_realtime_client
        
        print("Trying to initialize OpenAI Realtime client...")
        # Check environment variables
        print(f"DISPLAY: {os.environ.get('DISPLAY')}")
        print(f"PYNPUT_HEADLESS: {os.environ.get('PYNPUT_HEADLESS')}")
        print(f"NO_X11: {os.environ.get('NO_X11')}")
        print(f"HEADLESS: {os.environ.get('HEADLESS')}")
        print(f"OPENAI_REALTIME_NO_DISPLAY: {os.environ.get('OPENAI_REALTIME_NO_DISPLAY')}")
        
        # Initialize client
        class ConfigWithAudioOutput:
            def __init__(self):
                self.audio_output = "system"
        
        # Don't actually create a full client - just check if the imports work
        print("Checking that imports work...")
        from openai_realtime_client import OpenAIRealtime
        print_success("Imported OpenAIRealtime class")
        
        # Check if X11 is required for the current version
        import openai_realtime_client.x11
        print("X11 module exists in the client")
        
        if check_x11_display():
            print_success("X11 display is working and OpenAI Realtime client should work correctly")
        else:
            print_warning("X11 display is not working. OpenAI Realtime client will use direct WebSocket implementation.")
        
        # Check webrtc module
        import openai_realtime_client.webrtc
        print_success("WebRTC module exists in the client")
        
        return True
    except ImportError as e:
        print_error(f"Failed to import OpenAI Realtime client: {str(e)}")
        return False
    except Exception as e:
        print_error(f"Error testing OpenAI Realtime client initialization: {str(e)}")
        return False

def check_direct_websocket_implementation():
    """Check if a direct WebSocket implementation is available as fallback."""
    try:
        # Check if the direct WebSocket implementation modules are available
        print("Checking WebSocket dependencies...")
        
        module_checks = [
            ("websockets", "websockets", "8.1"),
            ("aiohttp", "aiohttp", "3.7.4"),
            ("socketio", "python-socketio", "5.0.4"),
            ("eventlet", "eventlet", "0.30.2")
        ]
        
        all_available = True
        for module_name, package_name, min_version in module_checks:
            spec = importlib.util.find_spec(module_name)
            if spec is not None:
                try:
                    module = importlib.import_module(module_name)
                    version = getattr(module, "__version__", "unknown")
                    print_success(f"{package_name} is installed (version: {version})")
                except ImportError as e:
                    print_error(f"{package_name} is installed but could not be imported: {str(e)}")
                    all_available = False
            else:
                print_error(f"{package_name} is not installed")
                all_available = False
                
                # Try to install it
                try:
                    subprocess.run([sys.executable, "-m", "pip", "install", f"{package_name}=={min_version}"], check=True)
                    print_success(f"Successfully installed {package_name}")
                except Exception as e:
                    print_error(f"Failed to install {package_name}: {str(e)}")
        
        if all_available:
            print_success("All WebSocket dependencies are available for direct WebSocket implementation")
        else:
            print_warning("Some WebSocket dependencies are missing. Direct WebSocket implementation may not work.")
        
        return all_available
    except Exception as e:
        print_error(f"Error checking WebSocket dependencies: {str(e)}")
        return False

def main():
    """Run all tests and report results."""
    print_header("OPENAI REALTIME CLIENT TEST")
    
    # Check if OpenAI Realtime client is installed
    client_installed = check_openai_realtime_installed()
    
    # Check if X11 display is working
    x11_working = check_x11_display()
    
    # Test if the OpenAI Realtime client can be initialized
    if client_installed:
        client_init = test_realtime_client_initialization()
    else:
        client_init = False
    
    # Check if a direct WebSocket implementation is available as fallback
    websocket_fallback = check_direct_websocket_implementation()
    
    # Report overall status
    print_header("TEST SUMMARY")
    
    if client_installed and (x11_working or websocket_fallback):
        if x11_working:
            print_success("OpenAI Realtime client is properly installed and X11 display is working")
        else:
            print_warning("OpenAI Realtime client is installed but X11 display is not working")
            print_warning("Direct WebSocket implementation will be used as fallback")
    elif client_installed and not x11_working and not websocket_fallback:
        print_error("OpenAI Realtime client is installed but X11 display is not working and WebSocket fallback is not available")
        print_error("Voice processing may not work correctly")
    else:
        print_error("OpenAI Realtime client is not properly set up")
        print_error("Voice processing will not work")

if __name__ == "__main__":
    main()