#!/usr/bin/env python3
"""
Simple WebSocket client for testing connection to Render service.
This script attempts to connect to a WebSocket endpoint and prints diagnostics.
"""

import asyncio
import sys
import argparse
import websockets
from datetime import datetime
import ssl

def log(message):
    """Print log message with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

async def connect_websocket(url, message=None):
    """
    Connect to a WebSocket server and optionally send/receive messages.
    
    Args:
        url: WebSocket URL to connect to
        message: Optional message to send after connecting
    """
    log(f"Connecting to {url}...")
    try:
        # Create SSL context with certificate verification
        ssl_context = ssl.create_default_context()
        
        async with websockets.connect(url, ssl=ssl_context) as websocket:
            log("✅ Connection successful!")
            
            # Send initial message if provided
            if message:
                log(f"Sending message: {message}")
                await websocket.send(message)
                
                # Wait for response
                log("Waiting for response...")
                response = await websocket.recv()
                log(f"Received response: {response}")
            
            # Keep connection open for manual testing
            log("Connection established. Press Ctrl+C to exit.")
            while True:
                await asyncio.sleep(1)
                
    except websockets.exceptions.InvalidStatusCode as e:
        log(f"❌ Connection failed with invalid status code: {e}")
        log(f"Status code: {e.status_code}")
        return False
    except websockets.exceptions.InvalidHandshake as e:
        log(f"❌ Connection failed with invalid handshake: {e}")
        return False
    except websockets.exceptions.ConnectionClosed as e:
        log(f"❌ Connection closed unexpectedly: {e}")
        log(f"Code: {e.code}, Reason: {e.reason}")
        return False
    except Exception as e:
        log(f"❌ Connection failed: {e}")
        return False
    finally:
        log("Connection closed.")

def main():
    """Main function to handle command line arguments and run the connection test."""
    parser = argparse.ArgumentParser(description="Test WebSocket connection")
    parser.add_argument("url", help="WebSocket URL to connect to")
    parser.add_argument("--message", "-m", help="Optional message to send after connecting")
    parser.add_argument("--timeout", "-t", type=int, default=10, help="Connection timeout in seconds")
    args = parser.parse_args()
    
    try:
        # Run with a timeout
        asyncio.run(asyncio.wait_for(connect_websocket(args.url, args.message), args.timeout))
    except asyncio.TimeoutError:
        log(f"❌ Connection timed out after {args.timeout} seconds")
    except KeyboardInterrupt:
        log("Interrupted by user")
    except Exception as e:
        log(f"Error: {e}")

if __name__ == "__main__":
    main()