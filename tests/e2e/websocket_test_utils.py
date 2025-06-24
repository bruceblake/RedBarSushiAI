"""
WebSocket test utilities for E2E testing.

This module provides utilities for testing WebSocket connections
and simulating Twilio ConversationRelay messages.
"""

import asyncio
import json
import base64
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
import websockets
import pytest


class MockTwilioWebSocketClient:
    """Mock Twilio WebSocket client for testing voice interactions."""
    
    def __init__(self, url: str, call_sid: str = "test_call_123"):
        """
        Initialize the mock Twilio WebSocket client.
        
        Args:
            url: WebSocket URL to connect to
            call_sid: Mock call SID for testing
        """
        self.url = url
        self.call_sid = call_sid
        self.websocket = None
        self.connected = False
        self.stream_sid = None
        self.received_messages = []
        self.audio_buffer = bytearray()
        
    async def connect(self) -> None:
        """Connect to the WebSocket server."""
        self.websocket = await websockets.connect(self.url)
        self.connected = True
        
        # Send initial connected message
        await self.send_connected_message()
        
    async def disconnect(self) -> None:
        """Disconnect from the WebSocket server."""
        if self.websocket:
            await self.websocket.close()
            self.connected = False
            
    async def send_connected_message(self) -> None:
        """Send Twilio connected message."""
        message = {
            "event": "connected",
            "protocol": "Call",
            "version": "1.0.0"
        }
        await self.send_message(message)
        
    async def send_start_message(self, custom_parameters: Optional[Dict[str, Any]] = None) -> None:
        """Send Twilio start message with stream metadata."""
        self.stream_sid = f"stream_{self.call_sid}"
        
        message = {
            "event": "start",
            "sequenceNumber": "1",
            "start": {
                "streamSid": self.stream_sid,
                "accountSid": "ACtest1234567890",
                "callSid": self.call_sid,
                "tracks": ["inbound"],
                "customParameters": custom_parameters or {}
            }
        }
        await self.send_message(message)
        
    async def send_media_message(self, audio_data: bytes, timestamp: Optional[int] = None) -> None:
        """
        Send audio media message.
        
        Args:
            audio_data: Raw audio bytes (should be 8000Hz, 16-bit PCM, mono)
            timestamp: Optional timestamp for the audio
        """
        # Base64 encode the audio data
        encoded_audio = base64.b64encode(audio_data).decode('utf-8')
        
        message = {
            "event": "media",
            "sequenceNumber": str(len(self.received_messages) + 2),
            "media": {
                "track": "inbound",
                "chunk": str(len(self.received_messages)),
                "timestamp": str(timestamp or int(datetime.now().timestamp() * 1000)),
                "payload": encoded_audio
            },
            "streamSid": self.stream_sid
        }
        await self.send_message(message)
        
    async def send_text_as_audio(self, text: str) -> None:
        """
        Simulate sending text as if it were transcribed audio.
        
        This is a convenience method for testing that simulates
        the transcription process.
        """
        # In a real test, you would convert text to audio
        # For now, we'll send a mark message to simulate speech
        await self.send_mark_message(f"speech:{text}")
        
    async def send_mark_message(self, mark_name: str) -> None:
        """Send a mark message (used for synchronization)."""
        message = {
            "event": "mark",
            "sequenceNumber": str(len(self.received_messages) + 2),
            "mark": {
                "name": mark_name
            },
            "streamSid": self.stream_sid
        }
        await self.send_message(message)
        
    async def send_stop_message(self) -> None:
        """Send stop message to end the stream."""
        message = {
            "event": "stop",
            "sequenceNumber": str(len(self.received_messages) + 2),
            "stop": {
                "accountSid": "ACtest1234567890",
                "callSid": self.call_sid
            },
            "streamSid": self.stream_sid
        }
        await self.send_message(message)
        
    async def send_message(self, message: Dict[str, Any]) -> None:
        """Send a message through the WebSocket."""
        if not self.connected or not self.websocket:
            raise RuntimeError("WebSocket not connected")
            
        await self.websocket.send(json.dumps(message))
        
    async def receive_message(self, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """
        Receive a message from the WebSocket.
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            Parsed message or None if timeout
        """
        try:
            message_text = await asyncio.wait_for(
                self.websocket.recv(),
                timeout=timeout
            )
            message = json.loads(message_text)
            self.received_messages.append(message)
            
            # Handle media messages by accumulating audio
            if message.get("event") == "media":
                audio_data = base64.b64decode(message["media"]["payload"])
                self.audio_buffer.extend(audio_data)
                
            return message
        except asyncio.TimeoutError:
            return None
            
    async def receive_all_messages(self, max_messages: int = 10, timeout: float = 5.0) -> List[Dict[str, Any]]:
        """Receive multiple messages until timeout or max reached."""
        messages = []
        for _ in range(max_messages):
            msg = await self.receive_message(timeout=timeout)
            if msg is None:
                break
            messages.append(msg)
        return messages
        
    async def wait_for_message(
        self, 
        condition: Callable[[Dict[str, Any]], bool],
        timeout: float = 10.0
    ) -> Optional[Dict[str, Any]]:
        """
        Wait for a message matching a condition.
        
        Args:
            condition: Function that returns True for the desired message
            timeout: Maximum time to wait
            
        Returns:
            The matching message or None if timeout
        """
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            msg = await self.receive_message(timeout=1.0)
            if msg and condition(msg):
                return msg
                
        return None
        
    def get_audio_responses(self) -> bytes:
        """Get all received audio data as bytes."""
        return bytes(self.audio_buffer)
        
    def get_text_responses(self) -> List[str]:
        """Extract text responses from mark messages."""
        texts = []
        for msg in self.received_messages:
            if msg.get("event") == "mark":
                mark_name = msg.get("mark", {}).get("name", "")
                if mark_name.startswith("response:"):
                    texts.append(mark_name[9:])  # Remove "response:" prefix
        return texts


class ConversationSimulator:
    """Simulate a phone conversation for testing."""
    
    def __init__(self, websocket_url: str):
        """Initialize the conversation simulator."""
        self.client = MockTwilioWebSocketClient(websocket_url)
        self.conversation_history = []
        
    async def start_call(self, phone_number: str = "+14155551234") -> None:
        """Start a simulated phone call."""
        await self.client.connect()
        await self.client.send_start_message({
            "phone_number": phone_number,
            "test_mode": "true"
        })
        
    async def say(self, text: str) -> Dict[str, Any]:
        """
        Simulate user saying something and get the response.
        
        Args:
            text: What the user says
            
        Returns:
            The assistant's response
        """
        # Record user input
        self.conversation_history.append({
            "role": "user",
            "content": text,
            "timestamp": datetime.now().isoformat()
        })
        
        # Send the text (in real scenario, this would be audio)
        await self.client.send_text_as_audio(text)
        
        # Wait for response
        response = await self.client.wait_for_message(
            lambda msg: msg.get("event") == "mark" and 
                       msg.get("mark", {}).get("name", "").startswith("response:"),
            timeout=10.0
        )
        
        if response:
            response_text = response["mark"]["name"][9:]  # Remove "response:" prefix
            self.conversation_history.append({
                "role": "assistant",
                "content": response_text,
                "timestamp": datetime.now().isoformat()
            })
            return {"text": response_text, "raw_message": response}
        
        return {"text": None, "raw_message": None}
        
    async def end_call(self) -> None:
        """End the simulated phone call."""
        await self.client.send_stop_message()
        await self.client.disconnect()
        
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Get the full conversation history."""
        return self.conversation_history.copy()


# Test fixtures
@pytest.fixture
async def twilio_ws_client():
    """Fixture for Twilio WebSocket client."""
    client = MockTwilioWebSocketClient("ws://localhost:8000/ws/twilio-stream")
    yield client
    if client.connected:
        await client.disconnect()


@pytest.fixture
async def conversation_simulator():
    """Fixture for conversation simulator."""
    simulator = ConversationSimulator("ws://localhost:8000/ws/twilio-stream")
    yield simulator
    if simulator.client.connected:
        await simulator.end_call()