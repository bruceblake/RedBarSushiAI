#!/usr/bin/env python3
"""OpenAI API key verification script."""

import os
import sys
import json
import time
import asyncio
import traceback
from datetime import datetime
import websockets
from websockets.exceptions import ConnectionClosed, ConnectionClosedError

def print_header(text):
    print(f"\n{'=' * 50}")
    print(f"  {text}")
    print(f"{'=' * 50}")

def get_openai_api_key():
    """Get OpenAI API key from environment."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    
    if not api_key:
        print("❌ OPENAI_API_KEY environment variable not set!")
        return None
    
    # Check if it has proper format (starts with sk-)
    if not api_key.startswith("sk-"):
        print(f"⚠️ Warning: API key does not start with 'sk-', which is unusual")
    
    return api_key

async def test_openai_connection(api_key):
    """Test connection to OpenAI API."""
    print_header("Testing OpenAI API Connection")
    
    if not api_key:
        print("❌ Cannot test connection: No API key provided")
        return False
    
    # Endpoint for testing
    url = "wss://api.openai.com/v1/realtime"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "OpenAI-Beta": "realtime=v1",
        "Content-Type": "application/json"
    }
    
    print(f"Connecting to {url}...")
    print(f"Using API key: {api_key[:4]}...{api_key[-4:]} (length: {len(api_key)})")
    
    try:
        # Connect to WebSocket
        start_time = time.time()
        websocket = await websockets.connect(url, extra_headers=headers)
        connect_time = time.time() - start_time
        print(f"✅ Connection successful! (took {connect_time:.2f}s)")
        
        # Configure session
        print("Configuring session...")
        session_config = {
            "type": "session.update",
            "session": {
                "model": "gpt-4o-realtime-preview-2024-10-01",
                "modalities": ["text"],
                "sample_rate_hz": 8000
            }
        }
        
        await websocket.send(json.dumps(session_config))
        print("Session configuration sent")
        
        # Wait for response
        print("Waiting for response...")
        response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
        response_data = json.loads(response)
        
        print(f"Response received: {json.dumps(response_data, indent=2)}")
        
        # Check if response indicates success
        if response_data.get("type") == "session.update" and response_data.get("status") == "success":
            print("✅ Session configuration successful!")
        else:
            print(f"⚠️ Unexpected response format")
        
        # Close connection
        await websocket.close()
        print("✅ OpenAI API connection test passed!")
        return True
    
    except websockets.exceptions.InvalidStatusCode as e:
        status_code = getattr(e, 'status_code', 'unknown')
        print(f"❌ Connection failed with HTTP status {status_code}: {str(e)}")
        
        if status_code == 401:
            print(f"❌ Authentication error (401): Invalid API key")
        elif status_code == 403:
            print(f"❌ Authorization error (403): Account does not have access to the Realtime API")
        elif status_code == 429:
            print(f"❌ Rate limit error (429): Too many requests or quota exceeded")
        
        return False
    
    except (ConnectionClosed, ConnectionClosedError) as e:
        print(f"❌ WebSocket connection closed: code={e.code}, reason={e.reason}")
        return False
    
    except asyncio.TimeoutError:
        print("❌ Timeout waiting for response from OpenAI API")
        return False
    
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        print(traceback.format_exc())
        return False

async def main():
    print_header("OpenAI API Key Verification")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Get API key
    api_key = get_openai_api_key()
    
    if not api_key:
        print("\n❌ No OpenAI API key available for testing.")
        return 1
    
    # Test API connection
    connection_success = await test_openai_connection(api_key)
    
    # Print summary
    print_header("Test Results Summary")
    print(f"API key present: {'✅' if api_key else '❌'}")
    print(f"API connection: {'✅' if connection_success else '❌'}")
    
    if connection_success:
        print("\n✅ All OpenAI API tests passed successfully!")
        return 0
    else:
        print("\n❌ OpenAI API tests failed. See details above.")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
