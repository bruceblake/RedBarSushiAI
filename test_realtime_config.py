#!/usr/bin/env python3
"""
Test script for verifying OpenAI Realtime client configuration.
This helps diagnose X11 and RealtimeClient class issues.
"""

import os
import sys
import traceback
import importlib
import logging
import json
from pprint import pprint
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def check_environment():
    """Check environment variables related to X11 and display"""
    env_vars = {
        "DISPLAY": os.environ.get("DISPLAY"),
        "PYNPUT_HEADLESS": os.environ.get("PYNPUT_HEADLESS"),
        "NO_X11": os.environ.get("NO_X11"),
        "HEADLESS": os.environ.get("HEADLESS"),
        "OPENAI_REALTIME_NO_DISPLAY": os.environ.get("OPENAI_REALTIME_NO_DISPLAY"),
        "X11_SETUP_SUCCESS": os.environ.get("X11_SETUP_SUCCESS"),
    }
    
    print("=== Environment Variables ===")
    status_ok = True
    for var, value in env_vars.items():
        if value is None:
            status = "❌ Not set"
            status_ok = False
        else:
            status = f"✅ {value}"
        print(f"{var}: {status}")
    
    # Check if X11 is properly configured
    x11_ok = False
    if env_vars["DISPLAY"] and env_vars["X11_SETUP_SUCCESS"] == "true":
        try:
            # Try to test the X display with xdpyinfo
            import subprocess
            result = subprocess.run(["xdpyinfo"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                print(f"✅ X11 display working on {env_vars['DISPLAY']}")
                x11_ok = True
            else:
                print(f"❌ X11 display not working: {result.stderr.decode('utf-8')}")
                status_ok = False
        except Exception as e:
            print(f"❌ Error testing X11 display: {e}")
            status_ok = False
    else:
        print("ℹ️ X11 not configured - will use headless mode")
        
    return status_ok, x11_ok

def test_imports():
    """Test importing openai_realtime_client and related classes"""
    print("\n=== Testing OpenAI Realtime Client Imports ===")
    
    import_results = {}
    
    # Try importing the openai_realtime_client module
    try:
        import openai_realtime_client
        print("✅ Successfully imported openai_realtime_client module")
        import_results["base_module"] = True
        
        # Get module contents
        module_contents = dir(openai_realtime_client)
        print(f"Module contents: {', '.join(module_contents)}")
        
        # Check for RealtimeClient class
        if "RealtimeClient" in module_contents:
            print("✅ RealtimeClient class found in module")
            import_results["RealtimeClient_in_module"] = True
            
            # Try importing RealtimeClient directly
            try:
                from openai_realtime_client import RealtimeClient
                print("✅ Successfully imported RealtimeClient class")
                import_results["import_RealtimeClient"] = True
                
                # Try examining RealtimeClient
                client_methods = [method for method in dir(RealtimeClient) if not method.startswith("_")]
                print(f"RealtimeClient methods: {', '.join(client_methods)}")
                
                # Try creating a dummy instance (without API key)
                try:
                    client = RealtimeClient(api_key="sk-test")
                    print(f"✅ Successfully created RealtimeClient instance: {client}")
                    import_results["create_RealtimeClient"] = True
                except Exception as client_error:
                    print(f"❌ Error creating RealtimeClient instance: {client_error}")
                    traceback.print_exc()
                    import_results["create_RealtimeClient"] = False
            except ImportError:
                print("❌ Failed to import RealtimeClient class")
                traceback.print_exc()
                import_results["import_RealtimeClient"] = False
        else:
            print("❌ RealtimeClient class not found in module")
            import_results["RealtimeClient_in_module"] = False
            
        # Check for deprecated Session class
        client_module_contents = []
        if "client" in module_contents:
            try:
                client_module = openai_realtime_client.client
                client_module_contents = dir(client_module)
                print(f"client submodule contents: {', '.join(client_module_contents)}")
                
                if "Session" in client_module_contents:
                    print("✅ Session class found in client submodule (legacy API)")
                    import_results["Session_in_client"] = True
                else:
                    print("ℹ️ Session class not found in client submodule (expected in newer API)")
                    import_results["Session_in_client"] = False
            except Exception as e:
                print(f"❌ Error inspecting client submodule: {e}")
                traceback.print_exc()
        else:
            print("❌ client submodule not found")
    except ImportError:
        print("❌ Failed to import openai_realtime_client module")
        traceback.print_exc()
        import_results["base_module"] = False
    
    # Print summary
    print("\n=== Import Test Summary ===")
    for test, result in import_results.items():
        status = "✅ Passed" if result else "❌ Failed"
        print(f"{test}: {status}")
    
    return import_results

def test_realtime_audio_module():
    """Test importing our realtime_audio.py module"""
    print("\n=== Testing our realtime_audio.py module ===")
    
    # Make sure we can import from the app directory
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    results = {}
    
    # Check if realtime_audio.py exists
    try:
        import app.utils.realtime_audio
        print("✅ Successfully imported realtime_audio module")
        results["import_module"] = True
        
        # Check REALTIME_AVAILABLE flag
        print(f"REALTIME_AVAILABLE: {app.utils.realtime_audio.REALTIME_AVAILABLE}")
        results["REALTIME_AVAILABLE"] = app.utils.realtime_audio.REALTIME_AVAILABLE
        
        # Check WebSocket backend availability
        print(f"WEBSOCKETS_AVAILABLE: {app.utils.realtime_audio.WEBSOCKETS_AVAILABLE}")
        print(f"AIOHTTP_AVAILABLE: {app.utils.realtime_audio.AIOHTTP_AVAILABLE}")
        results["websockets"] = app.utils.realtime_audio.WEBSOCKETS_AVAILABLE
        results["aiohttp"] = app.utils.realtime_audio.AIOHTTP_AVAILABLE
        
        # Try initializing the various processor classes
        try:
            from app.utils.realtime_audio import RealtimeAudioProcessor
            processor = RealtimeAudioProcessor()
            print("✅ Successfully created RealtimeAudioProcessor")
            results["RealtimeAudioProcessor"] = True
        except Exception as e:
            print(f"❌ Error creating RealtimeAudioProcessor: {e}")
            traceback.print_exc()
            results["RealtimeAudioProcessor"] = False
        
        try:
            from app.utils.direct_realtime import DirectRealtimeAudioProcessor
            processor = DirectRealtimeAudioProcessor()
            print("✅ Successfully created DirectRealtimeAudioProcessor")
            results["DirectRealtimeAudioProcessor"] = True
        except Exception as e:
            print(f"❌ Error creating DirectRealtimeAudioProcessor: {e}")
            traceback.print_exc()
            results["DirectRealtimeAudioProcessor"] = False
        
        try:
            from app.utils.realtime_audio import get_audio_processor
            processor = get_audio_processor()
            processor_type = type(processor).__name__
            print(f"✅ get_audio_processor returned {processor_type}")
            results["get_audio_processor"] = processor_type
        except Exception as e:
            print(f"❌ Error calling get_audio_processor: {e}")
            traceback.print_exc()
            results["get_audio_processor"] = False
    except Exception as e:
        print(f"❌ Error importing realtime_audio module: {e}")
        traceback.print_exc()
        results["import_module"] = False
    
    return results

def main():
    """Main test function"""
    print("========================================")
    print("OpenAI Realtime Client Configuration Test")
    print("========================================")
    print(f"Running tests at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python version: {sys.version}")
    print("----------------------------------------")
    
    # Check environment variables
    env_ok, x11_ok = check_environment()
    if not env_ok:
        print("\n⚠️ Environment variables not properly set")
    else:
        print("\n✅ Environment variables properly set")
        
    # Check imports
    import_results = test_imports()
    
    # Check our realtime module
    if import_results.get("base_module", False):
        print("\n✅ OpenAI Realtime client module found!")
        print("Testing our implementation...")
    else:
        print("\n⚠️ OpenAI Realtime client module not found!")
        print("Will test our implementation with fallbacks...")
    
    # Test our module
    module_results = test_realtime_audio_module()
    
    # Print final verdict
    print("\n========================================")
    print("Final Results")
    print("========================================")
    can_use_realtime = import_results.get("base_module", False) and import_results.get("import_RealtimeClient", False)
    has_working_implementation = module_results.get("get_audio_processor", False) != False
    
    if can_use_realtime and x11_ok:
        print("✅ BEST: OpenAI Realtime client is available with working X11 setup")
        print("    Both ORC with X11 and our custom implementation should work")
    elif can_use_realtime:
        print("✅ GOOD: OpenAI Realtime client is available but X11 is not properly set up")
        print("    Using RealtimeClient with newer API but X11 config might need improvement")
    elif has_working_implementation:
        print("✅ OK: Our custom implementation is available and working")
        print("    Using DirectRealtimeAudioProcessor or other fallbacks")
    else:
        print("❌ BAD: Neither OpenAI Realtime client nor our custom implementation is working")
        print("    You should troubleshoot the issues above to fix the audio processing")
    
    if module_results.get("get_audio_processor", False):
        print(f"\nSelected implementation: {module_results['get_audio_processor']}")
    
    print("\nRecommendations:")
    if not can_use_realtime:
        print("1. Install the OpenAI Realtime client: pip install openai-realtime-client")
    elif not x11_ok:
        print("1. Fix X11 setup by setting DISPLAY and ensuring Xvfb is running")
        print("   - In Docker: modify docker-entrypoint.sh")
        print("   - Locally: run 'Xvfb :99 &' and export DISPLAY=:99")
    else:
        print("1. Everything looks good! No action needed.")
        
    if not module_results.get("import_module", False):
        print("2. Check app/utils/realtime_audio.py for syntax errors")
    elif not has_working_implementation:
        print("2. Fix the implemention in app/utils/realtime_audio.py - check the errors above")
    
    print("\nUse this script regularly to diagnose issues with the OpenAI Realtime client setup.")

if __name__ == "__main__":
    main()