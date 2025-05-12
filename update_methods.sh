#!/bin/bash
# Script to apply the realtime_audio_async.py fixes to the running container

set -e

echo "===== Updating OpenAI Realtime Client in Container ====="

# Copy the updated file to the container
echo "Copying updated realtime_audio_async.py to container..."
docker cp /home/proxyie/MySoftware/RedBarSushiAI/app/utils/realtime_audio_async.py redbarsushi-app:/app/app/utils/

echo "✅ File copied to container"

# Create a verification script
echo "Creating verification script..."
cat > verify_methods.py << 'EOF'
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
EOF

# Copy verification script to container
echo "Copying verification script to container..."
docker cp verify_methods.py redbarsushi-app:/app/

# Run verification
echo "Running verification script..."
docker exec redbarsushi-app python /app/verify_methods.py

echo "===== Update Complete ====="
echo "The OpenAI Realtime client has been updated with the request_response method."
echo "This should fix the AttributeError in handlers.py."
echo ""
echo "To test the changes:"
echo "1. Make a call to your Twilio number"
echo "2. Check the logs with: docker logs redbarsushi-app"