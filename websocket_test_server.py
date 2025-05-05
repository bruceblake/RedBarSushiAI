#!/usr/bin/env python3
"""
WebSocket Test Server for RedBarSushiAI

This script creates a minimal Flask application with WebSocket support to test
the WebSocket fixes implemented for RedBarSushiAI. It mimics the production
environment by including similar route registrations, keep-alive patterns,
and worker configurations.

Usage:
    python websocket_test_server.py
"""

import asyncio
import json
import logging
import os
import sys
import time
import traceback
import uuid
from flask import Flask, render_template_string, request
from flask_sock import Sock

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('websocket_test_server.log')
    ]
)
logger = logging.getLogger("websocket_test_server")

# Create Flask app
app = Flask(__name__)
sock = Sock(app)

# Track active connections
active_connections = {}
connection_count = 0

# Simple HTML page for testing
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>WebSocket Test</title>
    <style>
        body { font-family: sans-serif; margin: 0; padding: 20px; }
        #connection { padding: 10px; background: #f0f0f0; margin-bottom: 10px; }
        #status { font-weight: bold; }
        #messages { height: 400px; overflow-y: auto; border: 1px solid #ccc; padding: 10px; margin-bottom: 10px; }
        .message { margin-bottom: 5px; }
        .message.sent { color: blue; }
        .message.received { color: green; }
        .message.error { color: red; }
        .message.system { color: purple; }
        button { padding: 8px 16px; margin-right: 10px; }
        input { padding: 8px; width: 300px; }
    </style>
</head>
<body>
    <h1>WebSocket Test for RedBarSushiAI</h1>
    
    <div id="connection">
        Status: <span id="status">Disconnected</span>
        <button id="connect">Connect</button>
        <button id="disconnect" disabled>Disconnect</button>
    </div>
    
    <div id="actions">
        <button id="send-start" disabled>Send Twilio Start</button>
        <button id="send-media" disabled>Send Media Chunk</button>
        <button id="send-custom" disabled>Send Custom Message</button>
        <input id="custom-message" placeholder="Custom message...">
    </div>
    
    <h3>Messages</h3>
    <div id="messages"></div>
    
    <script>
        // Elements
        const status = document.getElementById('status');
        const connectBtn = document.getElementById('connect');
        const disconnectBtn = document.getElementById('disconnect');
        const sendStartBtn = document.getElementById('send-start');
        const sendMediaBtn = document.getElementById('send-media');
        const sendCustomBtn = document.getElementById('send-custom');
        const customMessage = document.getElementById('custom-message');
        const messages = document.getElementById('messages');
        
        // Connection variables
        let socket = null;
        const sessionId = Math.random().toString(36).substring(2, 10);
        
        // Add message to the log
        function addMessage(text, type) {
            const message = document.createElement('div');
            message.className = `message ${type}`;
            message.textContent = `${new Date().toISOString().substr(11, 8)} [${type}] ${text}`;
            messages.appendChild(message);
            messages.scrollTop = messages.scrollHeight;
        }
        
        // Connect to WebSocket
        connectBtn.addEventListener('click', () => {
            try {
                // Create WebSocket connection
                socket = new WebSocket('ws://' + window.location.host + '/ws/voice/media');
                
                // Connection opened
                socket.addEventListener('open', (event) => {
                    status.textContent = 'Connected';
                    connectBtn.disabled = true;
                    disconnectBtn.disabled = false;
                    sendStartBtn.disabled = false;
                    sendMediaBtn.disabled = false;
                    sendCustomBtn.disabled = false;
                    
                    addMessage('Connection established', 'system');
                });
                
                // Listen for messages
                socket.addEventListener('message', (event) => {
                    try {
                        // Try to parse as JSON
                        const data = JSON.parse(event.data);
                        addMessage(JSON.stringify(data, null, 2), 'received');
                    } catch (e) {
                        // Raw message
                        addMessage(event.data, 'received');
                    }
                });
                
                // Connection closed
                socket.addEventListener('close', (event) => {
                    status.textContent = `Disconnected (${event.code}: ${event.reason || 'No reason'})`;
                    connectBtn.disabled = false;
                    disconnectBtn.disabled = true;
                    sendStartBtn.disabled = true;
                    sendMediaBtn.disabled = true;
                    sendCustomBtn.disabled = true;
                    
                    addMessage(`Connection closed: ${event.code} - ${event.reason || 'No reason'}`, 'system');
                    socket = null;
                });
                
                // Connection error
                socket.addEventListener('error', (event) => {
                    addMessage('Connection error', 'error');
                    console.error('WebSocket error:', event);
                });
                
            } catch (error) {
                addMessage(`Error creating connection: ${error.message}`, 'error');
                console.error('Error:', error);
            }
        });
        
        // Disconnect
        disconnectBtn.addEventListener('click', () => {
            if (socket) {
                socket.close();
                status.textContent = 'Disconnected (user initiated)';
                connectBtn.disabled = false;
                disconnectBtn.disabled = true;
                sendStartBtn.disabled = true;
                sendMediaBtn.disabled = true;
                sendCustomBtn.disabled = true;
                
                addMessage('Connection closed by user', 'system');
                socket = null;
            }
        });
        
        // Send Twilio Start message
        sendStartBtn.addEventListener('click', () => {
            if (socket && socket.readyState === WebSocket.OPEN) {
                const startMsg = {
                    event: "start",
                    streamSid: "MT" + "12345678901234567890123456789012",
                    accountSid: "AC" + "12345678901234567890123456789012",
                    callSid: "CA" + "12345678901234567890123456789012",
                    tracks: ["inbound_track", "both_tracks"],
                    mediaFormat: {
                        encoding: "audio/x-mulaw",
                        sampleRate: 8000,
                        channels: 1
                    }
                };
                
                socket.send(JSON.stringify(startMsg));
                addMessage(JSON.stringify(startMsg), 'sent');
            }
        });
        
        // Send media chunk
        sendMediaBtn.addEventListener('click', () => {
            if (socket && socket.readyState === WebSocket.OPEN) {
                const mediaMsg = {
                    event: "media",
                    streamSid: "MT" + "12345678901234567890123456789012",
                    trackSid: "inbound_track",
                    chunk: {
                        timestamp: Date.now()
                    },
                    media: {
                        payload: "AAAAAAAAAAAAAAAAAAAAAA==", // Dummy audio data
                        track: "inbound_track"
                    }
                };
                
                socket.send(JSON.stringify(mediaMsg));
                addMessage("Sent media chunk", 'sent');
            }
        });
        
        // Send custom message
        sendCustomBtn.addEventListener('click', () => {
            if (socket && socket.readyState === WebSocket.OPEN) {
                const message = customMessage.value || '{"type": "ping", "timestamp": ' + Date.now() + '}';
                
                try {
                    // Try to parse as JSON
                    const data = JSON.parse(message);
                    socket.send(JSON.stringify(data));
                    addMessage(JSON.stringify(data), 'sent');
                } catch (e) {
                    // Send as raw text
                    socket.send(message);
                    addMessage(message, 'sent');
                }
                
                customMessage.value = '';
            }
        });
        
        // Also send custom message on Enter key
        customMessage.addEventListener('keyup', (event) => {
            if (event.key === 'Enter') {
                sendCustomBtn.click();
            }
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Render the test page."""
    return render_template_string(HTML_TEMPLATE)

def websocket_handler(func):
    """Decorator for WebSocket handler functions that adds logging and error handling."""
    async def wrapper(ws):
        # Generate a connection ID
        conn_id = str(uuid.uuid4())[:8]
        
        # Track connection
        global connection_count
        connection_count += 1
        active_connections[conn_id] = {
            'id': conn_id,
            'connected_at': time.time(),
            'messages_received': 0,
            'messages_sent': 0,
            'client_ip': request.remote_addr if request else 'unknown',
            'user_agent': request.headers.get('User-Agent', 'unknown') if request else 'unknown'
        }
        
        logger.info(f"[WS:{conn_id}] WebSocket connection established")
        logger.info(f"[WS:{conn_id}] Active connections: {len(active_connections)}")
        
        try:
            # Send a welcome message to establish the connection
            welcome_msg = json.dumps({
                "type": "connected", 
                "message": "WebSocket connection established",
                "timestamp": time.time(),
                "connection_id": conn_id
            })
            await ws.send(welcome_msg)
            active_connections[conn_id]['messages_sent'] += 1
            logger.info(f"[WS:{conn_id}] Sent welcome message")
            
            # Add a brief delay
            await asyncio.sleep(0.2)
            
            # Send a test heartbeat message
            heartbeat_msg = json.dumps({
                "type": "heartbeat", 
                "message": "Initial heartbeat to maintain connection",
                "timestamp": time.time(),
                "connection_id": conn_id
            })
            await ws.send(heartbeat_msg)
            active_connections[conn_id]['messages_sent'] += 1
            logger.info(f"[WS:{conn_id}] Sent initial heartbeat")
            
            # Start heartbeat task
            heartbeat_task = asyncio.create_task(send_heartbeats(ws, conn_id))
            
            # Wait a moment before proceeding
            await asyncio.sleep(0.2)
            
            # Execute the handler function
            return await func(ws, conn_id)
        except Exception as e:
            logger.error(f"[WS:{conn_id}] Error in WebSocket handler: {e}")
            logger.error(traceback.format_exc())
            
            # Try to send an error message
            try:
                error_message = {
                    'type': 'error',
                    'message': f"Internal error: {str(e)}",
                    'timestamp': time.time()
                }
                await ws.send(json.dumps(error_message))
                active_connections[conn_id]['messages_sent'] += 1
            except:
                pass
            
            raise
        finally:
            # Clean up connection tracking
            if conn_id in active_connections:
                connection_duration = time.time() - active_connections[conn_id]['connected_at']
                messages_received = active_connections[conn_id]['messages_received']
                messages_sent = active_connections[conn_id]['messages_sent']
                
                logger.info(f"[WS:{conn_id}] WebSocket connection closed")
                logger.info(f"[WS:{conn_id}] Connection duration: {connection_duration:.2f}s")
                logger.info(f"[WS:{conn_id}] Messages received: {messages_received}")
                logger.info(f"[WS:{conn_id}] Messages sent: {messages_sent}")
                
                del active_connections[conn_id]
                logger.info(f"[WS:{conn_id}] Remaining active connections: {len(active_connections)}")
    
    return wrapper

async def send_heartbeats(ws, conn_id, interval=5.0):
    """Send periodic heartbeat messages to keep the WebSocket connection alive."""
    heartbeat_count = 0
    
    try:
        while True:
            # Wait for the specified interval
            await asyncio.sleep(interval)
            
            # Increment counter
            heartbeat_count += 1
            
            # Send heartbeat message
            try:
                heartbeat_message = {
                    "type": "heartbeat",
                    "count": heartbeat_count,
                    "timestamp": time.time(),
                    "message": "Connection is alive"
                }
                await ws.send(json.dumps(heartbeat_message))
                
                if conn_id in active_connections:
                    active_connections[conn_id]['messages_sent'] += 1
                
                # Log the heartbeat (but not too frequently to avoid log flooding)
                if heartbeat_count % 5 == 0:
                    logger.debug(f"[WS:{conn_id}] Sent heartbeat #{heartbeat_count}")
            except Exception as e:
                logger.error(f"[WS:{conn_id}] Error sending heartbeat: {e}")
                break
    except asyncio.CancelledError:
        logger.info(f"[WS:{conn_id}] Heartbeat task cancelled after {heartbeat_count} heartbeats")
    except Exception as e:
        logger.error(f"[WS:{conn_id}] Error in heartbeat task: {e}")

async def handle_greeting(ws, conn_id):
    """Simulate the greeting and multiple keep-alive pattern."""
    logger.info(f"[WS:{conn_id}] Sending greeting sequence")
    
    try:
        # Send greeting
        greeting = {
            "event": "agent_response",
            "text": "Welcome to Red Bar Sushi! How can I help you today?",
            "timestamp": time.time(),
            "is_greeting": True
        }
        await ws.send(json.dumps(greeting))
        if conn_id in active_connections:
            active_connections[conn_id]['messages_sent'] += 1
        logger.info(f"[WS:{conn_id}] Sent greeting message")
        
        # Send multiple keep-alive messages after greeting 
        # This is the critical pattern that was fixed in the main code
        for i in range(5):
            keep_alive = {
                "type": "connection_keep_alive", 
                "message": f"Keeping connection alive after greeting ({i+1}/5)",
                "timestamp": time.time(),
                "connection_id": conn_id
            }
            await asyncio.sleep(0.2)  # Small delay between messages
            await ws.send(json.dumps(keep_alive))
            if conn_id in active_connections:
                active_connections[conn_id]['messages_sent'] += 1
            logger.info(f"[WS:{conn_id}] Sent keep-alive #{i+1} after greeting")
        
        logger.info(f"[WS:{conn_id}] Completed keep-alive sequence after greeting")
        
        # Add a longer delay before the follow-up prompt
        await asyncio.sleep(3.0)
        
        # Send follow-up prompt
        followup = {
            "event": "agent_response",
            "text": "I'm here to help with our menu or take your order. What can I do for you today?",
            "timestamp": time.time(),
            "is_followup": True
        }
        await ws.send(json.dumps(followup))
        if conn_id in active_connections:
            active_connections[conn_id]['messages_sent'] += 1
        logger.info(f"[WS:{conn_id}] Sent follow-up prompt")
        
    except Exception as e:
        logger.error(f"[WS:{conn_id}] Error sending greeting sequence: {e}")
        logger.error(traceback.format_exc())

@sock.route('/ws/voice/media')
@websocket_handler
async def media_stream_ws(ws, conn_id):
    """WebSocket handler for media stream messages."""
    greeting_sent = False
    greeting_task = None
    
    logger.info(f"[WS:{conn_id}] Media stream handler started")
    
    try:
        # Listen for messages
        while True:
            try:
                message = await ws.receive()
                
                if conn_id in active_connections:
                    active_connections[conn_id]['messages_received'] += 1
                
                # Try to parse as JSON
                try:
                    data = json.loads(message)
                    
                    # Process Twilio start message
                    if isinstance(data, dict) and data.get('event') == 'start':
                        logger.info(f"[WS:{conn_id}] Received Twilio start message")
                        call_sid = data.get('callSid', 'unknown')
                        logger.info(f"[WS:{conn_id}] Call SID: {call_sid}")
                        
                        # Schedule greeting after receiving start message
                        if not greeting_sent and not greeting_task:
                            greeting_task = asyncio.create_task(handle_greeting(ws, conn_id))
                            greeting_sent = True
                    
                    # Echo the message back with a timestamp
                    response = {
                        "type": "echo",
                        "original": data,
                        "timestamp": time.time(),
                        "connection_id": conn_id
                    }
                    await ws.send(json.dumps(response))
                    if conn_id in active_connections:
                        active_connections[conn_id]['messages_sent'] += 1
                    
                except json.JSONDecodeError:
                    # Not JSON, treat as plain text
                    logger.info(f"[WS:{conn_id}] Received text message: {message[:100]}")
                    
                    # Echo the message back
                    response = {
                        "type": "echo",
                        "text": message,
                        "timestamp": time.time(),
                        "connection_id": conn_id
                    }
                    await ws.send(json.dumps(response))
                    if conn_id in active_connections:
                        active_connections[conn_id]['messages_sent'] += 1
                    
                    # Schedule greeting if not sent yet (for text messages)
                    if message and not greeting_sent and not greeting_task:
                        greeting_task = asyncio.create_task(handle_greeting(ws, conn_id))
                        greeting_sent = True
            
            except Exception as e:
                logger.error(f"[WS:{conn_id}] Error receiving/processing message: {e}")
                logger.error(traceback.format_exc())
                break
    
    except Exception as e:
        logger.error(f"[WS:{conn_id}] Error in media stream handler: {e}")
        logger.error(traceback.format_exc())
    
    logger.info(f"[WS:{conn_id}] Media stream handler completed")

# Route to check active connections
@app.route('/connections')
def check_connections():
    """Return information about active connections."""
    return {
        "active_connections": len(active_connections),
        "total_connections": connection_count,
        "connections": list(active_connections.values())
    }

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting WebSocket test server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)