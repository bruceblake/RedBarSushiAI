#!/usr/bin/env python3
"""
Test script for ConversationRelay WebSocket endpoint.
Simulates Twilio ConversationRelay messages to test the ordering system.
"""

import asyncio
import json
import logging
import websockets
from datetime import datetime
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# WebSocket URL for ConversationRelay
WS_URL = "ws://0.0.0.0:8080/api/conversation-relay"

class ConversationRelayTester:
    """Test ConversationRelay interactions."""
    
    def __init__(self):
        self.websocket = None
        self.call_sid = f"CA{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.session_id = f"sess_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.conversation_log = []
        
    async def connect(self):
        """Connect to the WebSocket endpoint."""
        logger.info(f"Connecting to {WS_URL}")
        self.websocket = await websockets.connect(WS_URL)
        logger.info("Connected successfully")
        
        # Send setup event
        setup_message = {
            "type": "setup",
            "sessionId": self.session_id,
            "callSid": self.call_sid,
            "from": "+14155551234",
            "to": "+14155555678",
            "callStatus": "in-progress"
        }
        await self.websocket.send(json.dumps(setup_message))
        logger.info(f"Sent setup message for call {self.call_sid}")
        
    async def send_prompt(self, text: str, is_last: bool = True):
        """Send a voice prompt (simulating Twilio STT)."""
        message = {
            "type": "prompt",
            "voicePrompt": text,
            "lang": "en-US",
            "last": is_last
        }
        await self.websocket.send(json.dumps(message))
        logger.info(f"USER: {text}")
        self.conversation_log.append({"role": "user", "content": text})
        
    async def receive_messages(self, timeout: int = 10) -> List[Dict]:
        """Receive all messages until timeout."""
        messages = []
        try:
            while True:
                response = await asyncio.wait_for(
                    self.websocket.recv(),
                    timeout=timeout
                )
                data = json.loads(response)
                messages.append(data)
                
                # Log text responses
                if data.get("type") == "text":
                    text = data.get("text", "")
                    logger.info(f"AGENT: {text}")
                    self.conversation_log.append({"role": "agent", "content": text})
                    
        except asyncio.TimeoutError:
            pass
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Connection closed")
            
        return messages
        
    async def run_scenario(self, scenario: Dict):
        """Run a test scenario."""
        logger.info(f"\n{'='*60}")
        logger.info(f"Scenario: {scenario['name']}")
        logger.info(f"{'='*60}")
        
        try:
            # Connect and setup
            await self.connect()
            
            # Wait for any initial messages
            await self.receive_messages(timeout=2)
            
            # Execute conversation steps
            for step in scenario['steps']:
                # Send user input
                await self.send_prompt(step['input'])
                
                # Receive response
                messages = await self.receive_messages(timeout=step.get('timeout', 5))
                
                # Optional: Check for expected responses
                if 'expected' in step:
                    found = False
                    for msg in messages:
                        if msg.get('type') == 'text' and step['expected'].lower() in msg.get('text', '').lower():
                            found = True
                            break
                    if found:
                        logger.info(f"✓ Found expected response: '{step['expected']}'")
                    else:
                        logger.warning(f"✗ Expected response not found: '{step['expected']}'")
                
                # Delay between interactions
                await asyncio.sleep(1)
                
            # Send completion
            await self.websocket.send(json.dumps({"type": "complete"}))
            logger.info("Sent completion signal")
            
            return True
            
        except Exception as e:
            logger.error(f"Scenario failed: {e}")
            return False
            
        finally:
            if self.websocket:
                await self.websocket.close()
                
    def save_conversation_log(self, filename: str):
        """Save conversation log to file."""
        with open(filename, 'w') as f:
            json.dump({
                "call_sid": self.call_sid,
                "timestamp": datetime.now().isoformat(),
                "conversation": self.conversation_log
            }, f, indent=2)
        logger.info(f"Conversation saved to {filename}")

# Test scenarios
SCENARIOS = [
    {
        "name": "Simple Order - California Roll",
        "steps": [
            {
                "input": "Hi, I'd like to order a California Roll please",
                "expected": "California Roll",
                "timeout": 5
            },
            {
                "input": "Yes, that's all",
                "expected": "confirm",
                "timeout": 5
            },
            {
                "input": "Yes, I'll pick it up",
                "expected": "pickup",
                "timeout": 5
            },
            {
                "input": "John Smith",
                "timeout": 5
            }
        ]
    },
    {
        "name": "Menu Inquiry",
        "steps": [
            {
                "input": "What sushi rolls do you have?",
                "expected": "roll",
                "timeout": 5
            },
            {
                "input": "How much is the Spicy Tuna Roll?",
                "expected": "14",
                "timeout": 5
            },
            {
                "input": "I'll take one Spicy Tuna Roll",
                "expected": "Spicy Tuna",
                "timeout": 5
            },
            {
                "input": "That's it",
                "timeout": 5
            }
        ]
    },
    {
        "name": "Order with Modifications",
        "steps": [
            {
                "input": "I want a California Roll with extra avocado",
                "expected": "California Roll",
                "timeout": 5
            },
            {
                "input": "Yes, add the extra avocado",
                "expected": "avocado",
                "timeout": 5
            },
            {
                "input": "No, that's all",
                "timeout": 5
            },
            {
                "input": "I'll pick it up in 20 minutes",
                "timeout": 5
            }
        ]
    },
    {
        "name": "Multiple Items",
        "steps": [
            {
                "input": "I'd like to order 2 California Rolls and 3 pieces of Salmon Nigiri",
                "expected": "California",
                "timeout": 8
            },
            {
                "input": "Can you repeat my order?",
                "expected": "2",
                "timeout": 5
            },
            {
                "input": "Yes, that's correct",
                "timeout": 5
            },
            {
                "input": "Pickup please",
                "timeout": 5
            }
        ]
    },
    {
        "name": "Unknown Item Recovery",
        "steps": [
            {
                "input": "I want a dragon roll",
                "expected": "don't have",
                "timeout": 5
            },
            {
                "input": "What rolls do you have then?",
                "expected": "California",
                "timeout": 5
            },
            {
                "input": "I'll have the California Roll",
                "expected": "California",
                "timeout": 5
            }
        ]
    }
]

async def main():
    """Run all test scenarios."""
    logger.info("Starting ConversationRelay tests")
    results = []
    
    for scenario in SCENARIOS:
        tester = ConversationRelayTester()
        success = await tester.run_scenario(scenario)
        results.append((scenario['name'], success))
        
        # Save conversation log
        filename = f"conversation_{scenario['name'].replace(' ', '_')}.json"
        tester.save_conversation_log(filename)
        
        # Wait between scenarios
        await asyncio.sleep(2)
    
    # Print summary
    logger.info(f"\n{'='*60}")
    logger.info("TEST SUMMARY")
    logger.info(f"{'='*60}")
    
    passed = sum(1 for _, success in results if success)
    for name, success in results:
        status = "✓ PASSED" if success else "✗ FAILED"
        logger.info(f"{status} - {name}")
    
    logger.info(f"\nTotal: {passed}/{len(results)} scenarios passed")

if __name__ == "__main__":
    asyncio.run(main())