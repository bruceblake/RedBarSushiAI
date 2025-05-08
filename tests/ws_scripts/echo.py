"""
WebSocket test script for testing the echo WebSocket endpoint.
This script sends a simple message and verifies that the server echoes it back.
"""

import json
import asyncio
from typing import Dict, Any

async def run(ws):
    """
    Run the echo test script with the provided WebSocket connection.
    
    Args:
        ws: A connected WebSocket client
        
    Returns:
        Dict containing the test results
    """
    # Test message
    test_message = "ping from WebSocket script"
    
    # Send the message
    await ws.send(test_message)
    
    # Receive the response
    response = await asyncio.wait_for(ws.recv(), timeout=5)
    
    # Return the results
    return {
        "sent": test_message,
        "received": response,
        "echo_match": test_message == response
    }