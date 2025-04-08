#!/usr/bin/env python
"""
Test script for verifying different realtime audio processors.
This will test all available implementations to help diagnose issues.
"""

import asyncio
import logging
import os
import sys

# Setup headless mode
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

async def main():
    """Test all available audio processors"""
    print("Testing all available audio processors...\n")
    
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
    for name, success in results.items():
        status = "✅ Working" if success else "❌ Failed"
        print(f"{name}: {status}")
    
    working_count = sum(1 for success in results.values() if success)
    print(f"\n{working_count}/{len(results)} implementations working")
    
    if results.get("Selected", False):
        print("\n✅ The selected implementation is working!")
    else:
        print("\n❌ The selected implementation is NOT working!")

if __name__ == "__main__":
    asyncio.run(main())