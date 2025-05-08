"""
WebSocket test script for testing the greeting flow.
This script simulates a client sending audio data to the WebSocket endpoint
and receiving the agent's greeting response.
"""

import json
import base64
import asyncio
import pathlib
from typing import Dict, List, Any

async def run(ws):
    """
    Run the greeting test script with the provided WebSocket connection.
    
    Args:
        ws: A connected WebSocket client
        
    Returns:
        Dict containing the test results
    """
    # Define the test call data
    call_sid = "TEST-CA-12345"
    
    # Pretend to be a media stream from Twilio
    await ws.send(json.dumps({
        "event": "start",
        "start": {
            "streamSid": call_sid,
            "accountSid": "TEST-AC-12345",
            "callSid": call_sid,
            "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}
        }
    }))
    
    # Wait for connection acknowledgment
    response = await asyncio.wait_for(ws.recv(), timeout=5)
    
    # Send several chunks of blank audio to allow the system to initiate greeting
    for _ in range(5):
        # Empty audio frames (silence)
        chunk = base64.b64encode(b'\x7f' * 160).decode()
        
        await ws.send(json.dumps({
            "event": "media",
            "media": {
                "payload": chunk,
                "streamSid": call_sid,
                "timestamp": "2023-05-04T15:30:00Z"
            }
        }))
        
        # Small delay to simulate real timing
        await asyncio.sleep(0.02)
    
    # Collect all responses with a timeout
    responses = []
    audio_frames = []
    transcripts = []
    
    # Try to receive responses for 5 seconds or until stop event
    timeout_time = asyncio.get_event_loop().time() + 5
    while asyncio.get_event_loop().time() < timeout_time:
        try:
            # Set a short timeout for each receive to allow us to check the total timeout
            response = await asyncio.wait_for(ws.recv(), timeout=0.5)
            response_data = json.loads(response)
            responses.append(response_data)
            
            # Extract audio and transcript data
            if "audio" in response_data:
                audio_frames.append(response_data["audio"])
            if "transcript" in response_data:
                transcripts.append(response_data["transcript"])
                
            # If we received a complete greeting, we can exit early
            if any(item.get("final", False) for item in transcripts):
                break
        except asyncio.TimeoutError:
            # Short timeout is expected, continue trying
            continue
    
    # Send stop event to clean up
    await ws.send(json.dumps({
        "event": "stop",
        "stop": {
            "streamSid": call_sid
        }
    }))
    
    # Summarize the results
    greeting_text = ""
    for transcript in transcripts:
        if transcript.get("text"):
            greeting_text += transcript.get("text", "") + " "
    
    return {
        "call_sid": call_sid,
        "greeting": greeting_text.strip(),
        "responses_received": len(responses),
        "audio_frames": len(audio_frames),
        "transcripts": transcripts
    }