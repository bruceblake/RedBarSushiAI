#!/usr/bin/env python
"""
Test script for verifying different realtime audio processors.
This will test all available implementations to help diagnose issues.
"""

import asyncio
import logging
import os
import sys
import subprocess
import importlib

# Check if we want to force X11 mode for testing
USE_X11 = os.environ.get('USE_XVFB', 'false').lower() in ('true', 't', '1', 'yes', 'y')

if USE_X11:
    # X11 mode - try to set up a virtual display if needed
    print("Running in X11 mode to test OpenAI Realtime client with display server")
    
    # Keep the existing DISPLAY variable if it's set
    if 'DISPLAY' not in os.environ:
        # Try to set up Xvfb
        try:
            subprocess.run(['which', 'Xvfb'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print("Xvfb found, setting up virtual display")
            
            # Kill any existing Xvfb instances
            subprocess.run(['pkill', 'Xvfb'], stderr=subprocess.PIPE)
            
            # Start Xvfb
            subprocess.Popen(['Xvfb', ':99', '-screen', '0', '1024x768x24', '-ac'])
            os.environ['DISPLAY'] = ':99'
            
            # Wait for Xvfb to start
            import time
            time.sleep(2)
            
            # Test display
            try:
                subprocess.run(['xdpyinfo'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                print(f"✅ X display server running on {os.environ['DISPLAY']}")
                
                # Configure for X11
                os.environ['PYNPUT_HEADLESS'] = '0'
                os.environ['NO_X11'] = '0'
                os.environ['HEADLESS'] = '0'
                os.environ['OPENAI_REALTIME_NO_DISPLAY'] = '0'
            except subprocess.CalledProcessError:
                print("❌ Failed to connect to X display, falling back to headless mode")
                os.environ['PYNPUT_HEADLESS'] = '1'
                os.environ['NO_X11'] = '1'
                os.environ['HEADLESS'] = '1'
                os.environ['OPENAI_REALTIME_NO_DISPLAY'] = '1'
        except subprocess.CalledProcessError:
            print("❌ Xvfb not found, cannot set up virtual display")
            # Fall back to headless mode
            os.environ['PYNPUT_HEADLESS'] = '1'
            os.environ['NO_X11'] = '1'
            os.environ['HEADLESS'] = '1'
            os.environ['OPENAI_REALTIME_NO_DISPLAY'] = '1'
    else:
        print(f"Using existing X display: {os.environ['DISPLAY']}")
        # Configure for X11
        os.environ['PYNPUT_HEADLESS'] = '0'
        os.environ['NO_X11'] = '0'
        os.environ['HEADLESS'] = '0'
        os.environ['OPENAI_REALTIME_NO_DISPLAY'] = '0'
else:
    # Headless mode
    print("Running in headless mode")
    os.environ['PYNPUT_HEADLESS'] = '1'
    os.environ['NO_X11'] = '1'
    os.environ['HEADLESS'] = '1'
    os.environ['OPENAI_REALTIME_NO_DISPLAY'] = '1'
    
    # Remove DISPLAY to prevent X11 connection attempts
    if 'DISPLAY' in os.environ:
        del os.environ['DISPLAY']

# Configure logging 
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Make sure we can import from the app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_processor(processor_name, processor):
    """Test basic functionality of the given processor"""
    print(f"\n----- Testing {processor_name} -----")
    
    try:
        # Test text response generation
        print(f"Testing text response generation...")
        message = "Tell me about sushi in one sentence."
        response_complete = False
        async for response in processor.process_conversation(message):
            if response.get("type") == "message":
                print(f"Received token: {response.get('text')}", end='', flush=True)
            elif response.get("type") == "message_complete":
                print(f"\nComplete response: {response.get('text')}")
                response_complete = True
        
        assert response_complete, "Did not receive complete response"
        print("✅ Text response generation test passed")
        
        # Test speech generation (just make sure it doesn't error)
        print(f"Testing speech generation...")
        speech_received = False
        async for audio_chunk in processor.generate_speech("Hello, this is a test.", voice="alloy"):
            if audio_chunk and len(audio_chunk) > 0:
                print(f"Received audio chunk of size {len(audio_chunk)} bytes")
                speech_received = True
                break
        
        assert speech_received, "Did not receive any audio data"
        print("✅ Speech generation test passed")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing {processor_name}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_display_connection():
    """Test if there's a working X11 display connection."""
    display = os.environ.get('DISPLAY')
    print(f"\n=== Testing X11 Display Connection ===")
    print(f"DISPLAY environment variable: {display}")
    
    if not display:
        print("❌ No DISPLAY environment variable set")
        return False
    
    try:
        # Test with xdpyinfo
        subprocess.run(['xdpyinfo'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("✅ X11 display test succeeded with xdpyinfo")
        return True
    except Exception as e:
        print(f"❌ X11 display test failed with xdpyinfo: {e}")
    
    # If we're here, the xdpyinfo test failed
    print("❌ X11 display is not working")
    return False

async def main():
    """Test all available audio processors"""
    print("Testing all available audio processors...\n")
    
    # First, test the display connection if we're in X11 mode
    if USE_X11:
        display_works = test_display_connection()
        print(f"X11 Display Connection: {'✅ Working' if display_works else '❌ Not working'}")
    
    results = {}
    
    # Attempt to import and test the original OpenAI Realtime client
    try:
        print("\n=== Testing original OpenAI Realtime client ===")
        import app.utils.realtime_audio
        # Check if it's actually available
        if app.utils.realtime_audio.REALTIME_AVAILABLE:
            print("OpenAI Realtime client is available, testing...")
            from app.utils.realtime_audio import RealtimeAudioProcessor
            processor = RealtimeAudioProcessor()
            results["OpenAI Realtime client"] = await test_processor("OpenAI Realtime client", processor)
        else:
            print("❌ OpenAI Realtime client not available, skipping test")
            results["OpenAI Realtime client"] = False
    except Exception as e:
        print(f"❌ Error importing OpenAI Realtime client: {str(e)}")
        results["OpenAI Realtime client"] = False
    
    # Test the direct realtime implementation
    try:
        print("\n=== Testing Direct Realtime implementation ===")
        from app.utils.direct_realtime import DirectRealtimeAudioProcessor
        processor = DirectRealtimeAudioProcessor()
        results["Direct Realtime"] = await test_processor("Direct Realtime", processor)
    except Exception as e:
        print(f"❌ Error importing Direct Realtime implementation: {str(e)}")
        results["Direct Realtime"] = False
        
    # Test the headless implementation
    try:
        print("\n=== Testing Headless implementation ===")
        from app.utils.audio_fallback import get_headless_audio_processor
        processor = get_headless_audio_processor()
        results["Headless"] = await test_processor("Headless", processor)
    except Exception as e:
        print(f"❌ Error importing Headless implementation: {str(e)}")
        results["Headless"] = False
    
    # Test the basic implementation
    try:
        print("\n=== Testing Basic implementation ===")
        from app.utils.realtime_audio import BasicAudioProcessor
        processor = BasicAudioProcessor()
        results["Basic"] = await test_processor("Basic", processor)
    except Exception as e:
        print(f"❌ Error importing Basic implementation: {str(e)}")
        results["Basic"] = False
    
    # Test the selected implementation that would be used
    try:
        print("\n=== Testing Selected implementation ===")
        from app.utils.realtime_audio import get_audio_processor
        processor = get_audio_processor()
        processor_name = processor.__class__.__name__
        results["Selected"] = await test_processor(f"Selected ({processor_name})", processor)
    except Exception as e:
        print(f"❌ Error with selected implementation: {str(e)}")
        results["Selected"] = False
    
    # Print summary
    print("\n===== Summary =====")
    
    # Display X11 status if relevant
    if USE_X11:
        display_works = test_display_connection()
        display_status = "✅ Working" if display_works else "❌ Not working"
        print(f"X11 Display: {display_status}")
        
        if not display_works:
            print("⚠️ X11 Display is not working, which affects the OpenAI Realtime client")
            print("   You have two options:")
            print("   1. Fix X11 by setting USE_XVFB=true and ensuring xvfb is installed")
            print("   2. Use the Direct Realtime implementation instead (recommended)")
    
    # Show processor results
    for name, success in results.items():
        status = "✅ Working" if success else "❌ Failed"
        print(f"{name}: {status}")
    
    working_count = sum(1 for success in results.values() if success)
    print(f"\n{working_count}/{len(results)} implementations working")
    
    # Final verdict
    if results.get("Selected", False):
        print("\n✅ The selected implementation is working!")
        
        # Get the processor name
        try:
            from app.utils.realtime_audio import get_audio_processor
            processor = get_audio_processor()
            processor_name = processor.__class__.__name__
            print(f"Using: {processor_name}")
        except:
            pass
    else:
        print("\n❌ The selected implementation is NOT working!")
        print("Try running with USE_XVFB=true to use the X11 virtual display server")

if __name__ == "__main__":
    asyncio.run(main())