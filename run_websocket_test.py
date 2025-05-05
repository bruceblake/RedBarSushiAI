#!/usr/bin/env python3
"""
Run a test Flask server with WebSocket routes to verify that the fix works.

This script sets up a minimal Flask app with Flask-Sock to test that
WebSocket routes are properly registered and accessible.
"""

from flask import Flask, render_template_string
from flask_sock import Sock
import logging
import json
import argparse
import time
import sys

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Flask app setup
app = Flask(__name__)
sock = Sock(app)

# Simple HTML template for testing WebSocket on the browser
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WebSocket Test</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        #log { border: 1px solid #ccc; padding: 10px; height: 300px; overflow-y: auto; }
        .message { margin-bottom: 5px; }
        .sent { color: blue; }
        .received { color: green; }
        .error { color: red; }
    </style>
</head>
<body>
    <h1>WebSocket Test</h1>
    <div>
        <button id="connect">Connect</button>
        <button id="disconnect" disabled>Disconnect</button>
    </div>
    <div style="margin-top: 10px;">
        <input type="text" id="message" placeholder="Type a message">
        <button id="send" disabled>Send</button>
    </div>
    <h3>Log:</h3>
    <div id="log"></div>

    <script>
        const connectBtn = document.getElementById('connect');
        const disconnectBtn = document.getElementById('disconnect');
        const sendBtn = document.getElementById('send');
        const messageInput = document.getElementById('message');
        const log = document.getElementById('log');
        
        let socket = null;
        
        function addLogMessage(message, type) {
            const div = document.createElement('div');
            div.className = `message ${type}`;
            div.textContent = message;
            log.appendChild(div);
            log.scrollTop = log.scrollHeight;
        }
        
        connectBtn.addEventListener('click', () => {
            // Create WebSocket connection
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const url = `${protocol}//${window.location.host}/ws/echo`;
            
            socket = new WebSocket(url);
            
            addLogMessage(`Connecting to ${url}...`, 'sent');
            
            socket.onopen = () => {
                addLogMessage('WebSocket connection established!', 'received');
                connectBtn.disabled = true;
                disconnectBtn.disabled = false;
                sendBtn.disabled = false;
            };
            
            socket.onmessage = (event) => {
                addLogMessage(`Received: ${event.data}`, 'received');
            };
            
            socket.onerror = (error) => {
                addLogMessage(`Error: ${error}`, 'error');
            };
            
            socket.onclose = (event) => {
                addLogMessage(`Connection closed. Code: ${event.code}, Reason: ${event.reason || 'No reason provided'}`, 'error');
                connectBtn.disabled = false;
                disconnectBtn.disabled = true;
                sendBtn.disabled = true;
                socket = null;
            };
        });
        
        disconnectBtn.addEventListener('click', () => {
            if (socket) {
                socket.close();
                addLogMessage('Disconnected', 'sent');
                connectBtn.disabled = false;
                disconnectBtn.disabled = true;
                sendBtn.disabled = true;
            }
        });
        
        sendBtn.addEventListener('click', () => {
            if (socket && messageInput.value) {
                socket.send(messageInput.value);
                addLogMessage(`Sent: ${messageInput.value}`, 'sent');
                messageInput.value = '';
            }
        });
        
        messageInput.addEventListener('keypress', (event) => {
            if (event.key === 'Enter' && !sendBtn.disabled) {
                sendBtn.click();
            }
        });
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    """Serve WebSocket test page."""
    return render_template_string(HTML_TEMPLATE)

@sock.route("/ws/echo")
def echo_socket(ws):
    """Echo WebSocket - responds with the same message it receives."""
    logger.info("WebSocket connection established to /ws/echo")
    
    try:
        while True:
            message = ws.receive()
            logger.info(f"Received message: {message}")
            
            # Echo the message back
            ws.send(f"You said: {message}")
            logger.info(f"Sent response for message: {message}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    
    logger.info("WebSocket connection closed")

@sock.route("/ws/debug")
def debug_socket(ws):
    """Debug WebSocket - provides connection information and echoes messages."""
    logger.info("WebSocket connection established to /ws/debug")
    
    # Send connection info
    try:
        info = {
            "status": "connected",
            "endpoint": "/ws/debug",
            "time": time.time(),
            "message": "WebSocket connection established successfully"
        }
        ws.send(json.dumps(info))
        logger.info("Sent connection info")
        
        # Echo loop
        while True:
            message = ws.receive()
            logger.info(f"Received message: {message}")
            
            # Parse JSON if possible
            try:
                data = json.loads(message)
                response = {
                    "echo": data,
                    "time": time.time(),
                    "type": "json_echo"
                }
                ws.send(json.dumps(response))
            except:
                # Not JSON, echo as string
                response = {
                    "echo": message,
                    "time": time.time(),
                    "type": "string_echo"
                }
                ws.send(json.dumps(response))
            
            logger.info(f"Sent response for message: {message}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    
    logger.info("WebSocket connection closed")

@sock.route("/ws/voice/media")
def media_socket(ws):
    """Simplified media WebSocket endpoint for testing."""
    logger.info("WebSocket connection established to /ws/voice/media")
    session_id = str(int(time.time()))
    
    try:
        # Send welcome message
        welcome = {
            "event": "message",
            "text": "Welcome to the test media WebSocket endpoint",
            "timestamp": time.time(),
            "session_id": session_id
        }
        ws.send(json.dumps(welcome))
        logger.info("Sent welcome message")
        
        # Process messages
        while True:
            message = ws.receive()
            logger.info(f"Received media message: {message[:100]}...")
            
            # Send acknowledgment
            ack = {
                "event": "ack",
                "timestamp": time.time(),
                "session_id": session_id
            }
            ws.send(json.dumps(ack))
            logger.info("Sent acknowledgment")
    except Exception as e:
        logger.error(f"Media WebSocket error: {e}")
    
    logger.info("Media WebSocket connection closed")

def main():
    """Run the Flask application."""
    parser = argparse.ArgumentParser(description="Run WebSocket test server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    
    args = parser.parse_args()
    
    logger.info(f"Starting WebSocket test server on {args.host}:{args.port}")
    logger.info("Available WebSocket endpoints:")
    logger.info("  - ws://<host>:<port>/ws/echo")
    logger.info("  - ws://<host>:<port>/ws/debug")
    logger.info("  - ws://<host>:<port>/ws/voice/media")
    logger.info("")
    logger.info("Open http://<host>:<port>/ in your browser to test the WebSocket connection")
    
    app.run(host=args.host, port=args.port, debug=args.debug)

if __name__ == "__main__":
    main()