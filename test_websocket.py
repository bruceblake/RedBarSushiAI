#!/usr/bin/env python3
# test_websocket.py - Test WebSocket functionality for RedBarSushiAI

import asyncio
import websockets
import json
import base64
import argparse
import os
import sys
import logging
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Default server URL
DEFAULT_SERVER = "http://localhost:8080"

async def test_capabilities(server_url):
    """Test the capabilities endpoint to see what features are available."""
    import requests
    
    capabilities_url = f"{server_url}/api/ws/capabilities"
    logger.info(f"Testing capabilities at {capabilities_url}")
    
    try:
        response = requests.get(capabilities_url)
        response.raise_for_status()
        capabilities = response.json()
        
        logger.info("Server Capabilities:")
        logger.info(f"- WebSockets available: {capabilities.get('websockets_available', False)}")
        logger.info(f"- Real-time STT: {capabilities.get('real_time_stt', False)}")
        logger.info(f"- Real-time TTS: {capabilities.get('real_time_tts', False)}")
        logger.info(f"- Conversation: {capabilities.get('conversation', False)}")
        logger.info(f"- Supported content types: {capabilities.get('supported_content_types', [])}")
        logger.info(f"- Supported voices: {capabilities.get('supported_voices', [])}")
        logger.info(f"- Endpoints: {capabilities.get('endpoints', {})}")
        
        return capabilities
    except Exception as e:
        logger.error(f"Error testing capabilities: {e}")
        return None

async def test_text_to_speech(server_url, text, voice="alloy"):
    """Test the text-to-speech WebSocket endpoint."""
    # Convert http:// to ws:// or https:// to wss://
    parsed_url = urlparse(server_url)
    ws_scheme = "wss" if parsed_url.scheme == "https" else "ws"
    ws_url = f"{ws_scheme}://{parsed_url.netloc}/api/ws/text-to-speech"
    
    logger.info(f"Testing text-to-speech at {ws_url}")
    logger.info(f"Text: '{text}'")
    logger.info(f"Voice: {voice}")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            # Wait for connection established message
            response = json.loads(await websocket.recv())
            logger.info(f"Server: {response}")
            
            # Send text to synthesize
            await websocket.send(json.dumps({
                "type": "text",
                "text": text,
                "voice": voice
            }))
            
            # Receive speech synthesis messages and audio
            chunks_received = 0
            audio_file = open("test_tts_output.mp3", "wb")
            
            try:
                while True:
                    message = await websocket.recv()
                    if isinstance(message, str):
                        # JSON message
                        data = json.loads(message)
                        logger.info(f"Server: {data}")
                        
                        if data.get("type") == "session_complete":
                            break
                    else:
                        # Binary audio data
                        chunks_received += 1
                        audio_file.write(message)
                        logger.info(f"Received audio chunk {chunks_received} ({len(message)} bytes)")
            finally:
                audio_file.close()
                
            # Send end signal
            await websocket.send(json.dumps({"type": "end"}))
            
            if chunks_received > 0:
                logger.info(f"Success! Audio saved to test_tts_output.mp3 ({chunks_received} chunks)")
                return True
            else:
                logger.error("No audio chunks received")
                return False
            
    except Exception as e:
        logger.error(f"Error testing text-to-speech: {e}")
        return False

async def test_conversation(server_url, text):
    """Test the conversation WebSocket endpoint with text input."""
    # Convert http:// to ws:// or https:// to wss://
    parsed_url = urlparse(server_url)
    ws_scheme = "wss" if parsed_url.scheme == "https" else "ws"
    ws_url = f"{ws_scheme}://{parsed_url.netloc}/api/ws/conversation"
    
    logger.info(f"Testing conversation at {ws_url}")
    logger.info(f"Text: '{text}'")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            # Wait for connection established message
            response = json.loads(await websocket.recv())
            logger.info(f"Server: {response}")
            
            # Send text message
            await websocket.send(json.dumps({
                "type": "text",
                "text": text
            }))
            
            # Receive conversation messages
            response_text = ""
            audio_chunks = 0
            
            try:
                while True:
                    message = await asyncio.wait_for(websocket.recv(), timeout=30)
                    if isinstance(message, str):
                        # JSON message
                        data = json.loads(message)
                        logger.info(f"Server: {data}")
                        
                        if data.get("type") == "message":
                            response_text += data.get("text", "")
                        elif data.get("type") == "message_complete":
                            logger.info(f"Complete response: {data.get('text', '')}")
                        elif data.get("type") == "session_complete":
                            break
                    else:
                        # Binary audio data
                        audio_chunks += 1
                        logger.info(f"Received audio chunk {audio_chunks} ({len(message)} bytes)")
                        
                        # Save first audio chunk for testing
                        if audio_chunks == 1:
                            with open("test_conversation_audio.mp3", "wb") as f:
                                f.write(message)
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for server response")
            
            # Send end signal
            await websocket.send(json.dumps({"type": "end"}))
            
            if response_text:
                logger.info(f"Success! Received response: {response_text}")
                return True
            else:
                logger.error("No response text received")
                return False
            
    except Exception as e:
        logger.error(f"Error testing conversation: {e}")
        return False

async def main():
    parser = argparse.ArgumentParser(description="Test WebSocket functionality for RedBarSushiAI")
    parser.add_argument("--server", default=DEFAULT_SERVER, help=f"Server URL (default: {DEFAULT_SERVER})")
    parser.add_argument("--test", choices=["capabilities", "tts", "conversation", "all"], default="all", 
                      help="Test to run (default: all)")
    parser.add_argument("--text", default="Hello, I'd like to order sushi please.", 
                      help="Text to use for testing")
    parser.add_argument("--voice", default="alloy", 
                      help="Voice to use for TTS testing")
    
    args = parser.parse_args()
    
    if args.test == "capabilities" or args.test == "all":
        await test_capabilities(args.server)
    
    if args.test == "tts" or args.test == "all":
        await test_text_to_speech(args.server, args.text, args.voice)
    
    if args.test == "conversation" or args.test == "all":
        await test_conversation(args.server, args.text)

if __name__ == "__main__":
    asyncio.run(main())