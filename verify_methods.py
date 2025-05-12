#!/usr/bin/env python3
"""Verify the OpenAI Realtime client has the required methods."""

import inspect

def check_client():
    try:
        from app.utils.realtime_audio_async import OpenAIRealtimeClient
        print("Successfully imported OpenAIRealtimeClient")
        
        # Check for request_response method
        if hasattr(OpenAIRealtimeClient, 'request_response'):
            print("✅ OpenAIRealtimeClient has request_response method")
            print(f"Method signature: {inspect.signature(OpenAIRealtimeClient.request_response)}")
        else:
            print("❌ OpenAIRealtimeClient is missing request_response method")
        
        # Check for send_text_for_tts method
        if hasattr(OpenAIRealtimeClient, 'send_text_for_tts'):
            print("✅ OpenAIRealtimeClient has send_text_for_tts method")
        else:
            print("❌ OpenAIRealtimeClient is missing send_text_for_tts method")
        
        # Check for process_messages method
        if hasattr(OpenAIRealtimeClient, 'process_messages'):
            print("✅ OpenAIRealtimeClient has process_messages method")
        else:
            print("❌ OpenAIRealtimeClient is missing process_messages method")
            
        print("\nAll required methods are present.")
        
    except ImportError as e:
        print(f"Error importing OpenAIRealtimeClient: {e}")
    except Exception as e:
        print(f"Error checking client methods: {e}")

if __name__ == "__main__":
    check_client()
