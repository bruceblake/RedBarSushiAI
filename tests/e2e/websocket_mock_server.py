"""
Mock WebSocket server for E2E testing.

This module provides a mock WebSocket server that simulates the RedBarSushiAI
system for testing purposes.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Set, Optional
import websockets
from websockets.server import WebSocketServerProtocol
from datetime import datetime

logger = logging.getLogger(__name__)


class MockConversationHandler:
    """Handles mock conversations for testing."""
    
    def __init__(self):
        """Initialize the mock handler."""
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.responses = self._load_mock_responses()
    
    def _load_mock_responses(self) -> Dict[str, str]:
        """Load predefined mock responses."""
        return {
            # Greetings
            "hi": "Welcome to Red Bar Sushi! May I have your name please?",
            "hello": "Welcome to Red Bar Sushi! May I have your name please?",
            
            # Menu queries
            "menu": "We have California Roll ($12.95), Spicy Tuna Roll ($14.95), and Vegetable Roll ($12.95).",
            "vegetarian": "Our vegetarian options include the Vegetable Roll ($12.95) and Edamame ($5.95).",
            "price": "Our prices range from $5.95 for appetizers to $18.95 for specialty rolls.",
            
            # Ordering
            "order": "I'll help you place an order. What would you like?",
            "california": "I've added California Roll to your order.",
            "spicy tuna": "I've added Spicy Tuna Roll to your order.",
            "edamame": "I've added Edamame to your order.",
            
            # Order completion
            "that's all": "Let me confirm your order. Is everything correct?",
            "done": "Let me confirm your order. Is everything correct?",
            "confirm": "Great! Your order has been placed.",
            "yes": "Great! Your order has been placed.",
            
            # Global commands
            "repeat": "[Repeating last message]",
            "start over": "Let's start fresh. Welcome to Red Bar Sushi!",
            "go back": "Going back to the previous step.",
            "help": "I can help you place an order, answer menu questions, or connect you with staff.",
            
            # Error handling
            "lobster": "I'm sorry, we don't have lobster roll on our menu. Would you like to see what we have?",
            "...": "I didn't catch that. Could you please repeat?",
            "": "I didn't hear anything. Are you still there?"
        }
    
    def get_session(self, session_id: str) -> Dict[str, Any]:
        """Get or create session."""
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "id": session_id,
                "state": "GREETING",
                "context": {
                    "cart": [],
                    "conversation_history": []
                },
                "created_at": datetime.now()
            }
        return self.sessions[session_id]
    
    def process_message(self, session_id: str, message: str) -> Dict[str, Any]:
        """Process a user message and return response."""
        session = self.get_session(session_id)
        
        # Add to conversation history
        session["context"]["conversation_history"].append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat()
        })
        
        # Get response based on message content
        response_text = self._get_response(message.lower(), session)
        
        # Update state based on message
        new_state = self._update_state(message.lower(), session["state"])
        session["state"] = new_state
        
        # Determine agent
        agent = self._get_agent_for_state(new_state)
        
        # Add response to history
        session["context"]["conversation_history"].append({
            "role": "assistant",
            "content": response_text,
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            "type": "response",
            "text": response_text,
            "state": new_state,
            "agent": agent,
            "context": session["context"]
        }
    
    def _get_response(self, message: str, session: Dict[str, Any]) -> str:
        """Get appropriate response for message."""
        # Check for exact matches first
        for key, response in self.responses.items():
            if key in message:
                # Special handling for repeat command
                if key == "repeat" and session["context"]["conversation_history"]:
                    # Find last assistant message
                    for msg in reversed(session["context"]["conversation_history"]):
                        if msg["role"] == "assistant":
                            return msg["content"]
                return response
        
        # Handle name provision
        if session["state"] == "GREETING" and len(message.split()) <= 3:
            return f"Nice to meet you! How can I help you today?"
        
        # Handle order items
        if session["state"] == "ORDERING":
            if any(item in message for item in ["roll", "sushi", "sashimi"]):
                return "I've added that to your order. Anything else?"
            elif "no" in message or "nothing" in message:
                return "Let me confirm your order. Is everything correct?"
        
        # Default response
        return "I can help you with your order. What would you like?"
    
    def _update_state(self, message: str, current_state: str) -> str:
        """Update conversation state based on message."""
        # State transition logic
        if current_state == "GREETING":
            if any(word in message for word in ["order", "menu", "food"]):
                return "ORDERING"
            elif len(message.split()) <= 3:  # Likely a name
                return "MAIN_MENU"
        
        elif current_state == "MAIN_MENU":
            if "order" in message:
                return "ORDERING"
            elif any(word in message for word in ["menu", "what", "price"]):
                return "MAIN_MENU"  # Stay in menu
        
        elif current_state == "ORDERING":
            if any(word in message for word in ["done", "that's all", "complete"]):
                return "VALIDATION"
            elif "cancel" in message:
                return "CANCELLATION_PENDING"
        
        elif current_state == "VALIDATION":
            if any(word in message for word in ["yes", "confirm", "correct"]):
                return "CONFIRMATION"
            elif "no" in message or "change" in message:
                return "ORDERING"
        
        elif current_state == "CONFIRMATION":
            return "COMPLETED"
        
        # Global commands
        if "start over" in message:
            return "GREETING"
        elif "go back" in message and current_state == "ORDERING":
            return "MAIN_MENU"
        
        return current_state
    
    def _get_agent_for_state(self, state: str) -> str:
        """Get appropriate agent for state."""
        state_agent_map = {
            "GREETING": "frontline",
            "MAIN_MENU": "frontline",
            "ORDERING": "cart",
            "VALIDATION": "guardrail",
            "CONFIRMATION": "frontline",
            "FULFILLMENT": "fulfillment",
            "CANCELLATION_PENDING": "cart",
            "COMPLETED": "frontline",
            "ERROR": "frontline"
        }
        return state_agent_map.get(state, "frontline")


class MockWebSocketServer:
    """Mock WebSocket server for E2E testing."""
    
    def __init__(self, host: str = "localhost", port: int = 8765):
        """Initialize the mock server."""
        self.host = host
        self.port = port
        self.handler = MockConversationHandler()
        self.clients: Set[WebSocketServerProtocol] = set()
        self.server = None
    
    async def handle_client(self, websocket: WebSocketServerProtocol, path: str):
        """Handle a WebSocket client connection."""
        # Extract session ID from path
        session_id = path.strip("/").split("/")[-1] or "default"
        logger.info(f"Client connected with session ID: {session_id}")
        
        self.clients.add(websocket)
        
        try:
            # Send initial greeting
            greeting = self.handler.process_message(session_id, "")
            await websocket.send(json.dumps(greeting))
            
            # Handle messages
            async for message in websocket:
                try:
                    data = json.loads(message)
                    
                    if data.get("type") == "user_message":
                        # Process user message
                        response = self.handler.process_message(
                            session_id,
                            data.get("text", "")
                        )
                        
                        # Simulate processing delay
                        await asyncio.sleep(0.5)
                        
                        # Send response
                        await websocket.send(json.dumps(response))
                    
                    elif data.get("type") == "init":
                        # Handle initialization
                        context = data.get("context", {})
                        session = self.handler.get_session(session_id)
                        session["context"].update(context)
                        
                        await websocket.send(json.dumps({
                            "type": "init_ack",
                            "session_id": session_id
                        }))
                    
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON received: {message}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": str(e)
                    }))
        
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client disconnected: {session_id}")
        finally:
            self.clients.remove(websocket)
    
    async def start(self):
        """Start the mock server."""
        self.server = await websockets.serve(
            self.handle_client,
            self.host,
            self.port
        )
        logger.info(f"Mock WebSocket server started on ws://{self.host}:{self.port}")
    
    def stop(self):
        """Stop the mock server."""
        if self.server:
            self.server.close()
            logger.info("Mock WebSocket server stopped")
    
    async def wait_closed(self):
        """Wait for server to close."""
        if self.server:
            await self.server.wait_closed()


async def start_mock_server(host: str = "localhost", port: int = 8765) -> MockWebSocketServer:
    """Start a mock WebSocket server for testing."""
    server = MockWebSocketServer(host, port)
    await server.start()
    return server


if __name__ == "__main__":
    # Run mock server standalone
    async def main():
        logging.basicConfig(level=logging.INFO)
        server = await start_mock_server()
        
        try:
            # Keep server running
            await asyncio.Future()
        except KeyboardInterrupt:
            logger.info("Shutting down mock server...")
            server.stop()
            await server.wait_closed()
    
    asyncio.run(main())