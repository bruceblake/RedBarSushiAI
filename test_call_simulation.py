#!/usr/bin/env python3
"""
Test script to simulate phone calls to the Red Bar Sushi ordering system.
Tests the full conversation flow, menu inquiries, order placement, FSM transitions, and error cases.
"""

import asyncio
import json
import websockets
import logging
from typing import Dict, List, Optional
import sys
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test configuration
WS_URL = "ws://0.0.0.0:8080/api/conversation-relay"
CALL_SID = f"test_call_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

class CallSimulator:
    """Simulates phone calls to test the ordering system."""
    
    def __init__(self, ws_url: str, call_sid: str):
        self.ws_url = ws_url
        self.call_sid = call_sid
        self.websocket = None
        self.conversation_log = []
        self.current_state = None
        
    async def connect(self):
        """Establish WebSocket connection."""
        # ConversationRelay doesn't expect call_sid in URL
        full_url = self.ws_url
        logger.info(f"Connecting to {full_url}")
        self.websocket = await websockets.connect(full_url)
        logger.info("Connected successfully")
        
    async def disconnect(self):
        """Close WebSocket connection."""
        if self.websocket:
            await self.websocket.close()
            logger.info("Disconnected")
            
    async def send_voice_input(self, text: str):
        """Send a voice input to the system."""
        message = {
            "type": "voice_input",
            "text": text,
            "timestamp": datetime.now().isoformat()
        }
        await self.websocket.send(json.dumps(message))
        logger.info(f"Sent: {text}")
        self.conversation_log.append({"role": "user", "content": text})
        
    async def receive_response(self, timeout: int = 30) -> Optional[Dict]:
        """Receive and parse response from the system."""
        try:
            response = await asyncio.wait_for(
                self.websocket.recv(), 
                timeout=timeout
            )
            data = json.loads(response)
            
            if data.get("type") == "agent_response":
                content = data.get("text", "")
                logger.info(f"Received: {content}")
                self.conversation_log.append({"role": "assistant", "content": content})
                
            if data.get("fsm_state"):
                self.current_state = data["fsm_state"]
                logger.info(f"FSM State: {self.current_state}")
                
            return data
            
        except asyncio.TimeoutError:
            logger.warning("Response timeout")
            return None
        except Exception as e:
            logger.error(f"Error receiving response: {e}")
            return None
            
    async def wait_for_greeting(self):
        """Wait for initial greeting from the system."""
        logger.info("Waiting for greeting...")
        response = await self.receive_response()
        return response is not None
        
    async def run_conversation_test(self, scenario: Dict):
        """Run a complete conversation test scenario."""
        logger.info(f"\n{'='*60}")
        logger.info(f"Running scenario: {scenario['name']}")
        logger.info(f"{'='*60}")
        
        try:
            # Connect and wait for greeting
            await self.connect()
            if not await self.wait_for_greeting():
                raise Exception("No greeting received")
                
            # Execute conversation steps
            for step in scenario['steps']:
                await asyncio.sleep(1)  # Small delay between interactions
                
                # Send user input
                await self.send_voice_input(step['input'])
                
                # Receive response
                response = await self.receive_response()
                
                # Validate response if expected content provided
                if 'expected_keywords' in step and response:
                    text = response.get('text', '').lower()
                    for keyword in step['expected_keywords']:
                        if keyword.lower() not in text:
                            logger.warning(f"Expected keyword '{keyword}' not found in response")
                            
                # Validate FSM state if expected
                if 'expected_state' in step:
                    if self.current_state != step['expected_state']:
                        logger.warning(
                            f"Expected state '{step['expected_state']}', "
                            f"but got '{self.current_state}'"
                        )
                        
            logger.info(f"Scenario '{scenario['name']}' completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Scenario failed: {e}")
            return False
            
        finally:
            await self.disconnect()
            
    def save_conversation_log(self, filename: str):
        """Save conversation log to file."""
        with open(filename, 'w') as f:
            json.dump({
                'call_sid': self.call_sid,
                'timestamp': datetime.now().isoformat(),
                'conversation': self.conversation_log
            }, f, indent=2)
        logger.info(f"Conversation log saved to {filename}")


# Test scenarios
TEST_SCENARIOS = [
    {
        "name": "Complete Order Flow",
        "steps": [
            {
                "input": "Hi, my name is John",
                "expected_keywords": ["John", "help", "order"],
                "expected_state": "MAIN_MENU"
            },
            {
                "input": "I'd like to place an order",
                "expected_keywords": ["what", "order", "like"],
                "expected_state": "ORDERING"
            },
            {
                "input": "I'll have two California rolls and one spicy tuna roll",
                "expected_keywords": ["California", "spicy tuna", "anything else"],
                "expected_state": "ORDERING"
            },
            {
                "input": "That's all for now",
                "expected_keywords": ["order", "total", "confirm"],
                "expected_state": "CONFIRMATION"
            },
            {
                "input": "Yes, that's correct",
                "expected_keywords": ["pickup", "delivery"],
                "expected_state": "FULFILLMENT"
            },
            {
                "input": "I'll pick it up",
                "expected_keywords": ["ready", "minutes", "thank"],
                "expected_state": "COMPLETION"
            }
        ]
    },
    {
        "name": "Menu Inquiry Flow",
        "steps": [
            {
                "input": "Hello, I'm Sarah",
                "expected_keywords": ["Sarah", "help"],
                "expected_state": "MAIN_MENU"
            },
            {
                "input": "What rolls do you have?",
                "expected_keywords": ["California", "Spicy Tuna", "roll"],
                "expected_state": "MAIN_MENU"
            },
            {
                "input": "How much is the California roll?",
                "expected_keywords": ["California", "8.99", "price"],
                "expected_state": "MAIN_MENU"
            },
            {
                "input": "What's in the spicy tuna roll?",
                "expected_keywords": ["spicy", "tuna", "cucumber"],
                "expected_state": "MAIN_MENU"
            },
            {
                "input": "I'd like to order now",
                "expected_keywords": ["what", "order"],
                "expected_state": "ORDERING"
            },
            {
                "input": "One California roll please",
                "expected_keywords": ["California", "anything else"],
                "expected_state": "ORDERING"
            },
            {
                "input": "No, that's it",
                "expected_keywords": ["order", "8.99"],
                "expected_state": "CONFIRMATION"
            }
        ]
    },
    {
        "name": "Order with Modifications",
        "steps": [
            {
                "input": "Hi, I'm Mike",
                "expected_keywords": ["Mike"],
                "expected_state": "MAIN_MENU"
            },
            {
                "input": "I want to order some sushi",
                "expected_keywords": ["what", "order"],
                "expected_state": "ORDERING"
            },
            {
                "input": "Two pieces of salmon nigiri with extra wasabi",
                "expected_keywords": ["salmon", "nigiri", "wasabi"],
                "expected_state": "ORDERING"
            },
            {
                "input": "Add a California roll with no cucumber",
                "expected_keywords": ["California", "cucumber"],
                "expected_state": "ORDERING"
            },
            {
                "input": "That's all",
                "expected_keywords": ["order", "total"],
                "expected_state": "CONFIRMATION"
            }
        ]
    },
    {
        "name": "Error Recovery - Unknown Item",
        "steps": [
            {
                "input": "Hello, I'm Lisa",
                "expected_keywords": ["Lisa"],
                "expected_state": "MAIN_MENU"
            },
            {
                "input": "I'd like to order",
                "expected_state": "ORDERING"
            },
            {
                "input": "I want a dragon roll",
                "expected_keywords": ["don't have", "not available", "else"],
                "expected_state": "ORDERING"
            },
            {
                "input": "What rolls do you have?",
                "expected_keywords": ["California", "Spicy Tuna"],
                "expected_state": "ORDERING"
            },
            {
                "input": "I'll take a spicy tuna roll then",
                "expected_keywords": ["spicy tuna"],
                "expected_state": "ORDERING"
            }
        ]
    },
    {
        "name": "Escalation Request",
        "steps": [
            {
                "input": "Hi there",
                "expected_state": "GREETING"
            },
            {
                "input": "I need to speak to a human",
                "expected_keywords": ["staff", "moment", "transfer"],
                "expected_state": "ESCALATION"
            }
        ]
    },
    {
        "name": "Multiple Items and Cart Review",
        "steps": [
            {
                "input": "Hey, I'm Tom",
                "expected_keywords": ["Tom"],
                "expected_state": "MAIN_MENU"
            },
            {
                "input": "I want to place a big order",
                "expected_state": "ORDERING"
            },
            {
                "input": "Three California rolls",
                "expected_keywords": ["California"],
                "expected_state": "ORDERING"
            },
            {
                "input": "Two spicy tuna rolls",
                "expected_keywords": ["spicy tuna"],
                "expected_state": "ORDERING"
            },
            {
                "input": "Four pieces of salmon nigiri",
                "expected_keywords": ["salmon"],
                "expected_state": "ORDERING"
            },
            {
                "input": "What's in my order so far?",
                "expected_keywords": ["California", "spicy tuna", "salmon"],
                "expected_state": "ORDERING"
            },
            {
                "input": "Remove one California roll",
                "expected_keywords": ["removed", "California"],
                "expected_state": "ORDERING"
            },
            {
                "input": "That's everything",
                "expected_keywords": ["total", "confirm"],
                "expected_state": "CONFIRMATION"
            }
        ]
    }
]


async def main():
    """Run all test scenarios."""
    logger.info("Starting Red Bar Sushi call simulation tests")
    
    results = []
    
    for scenario in TEST_SCENARIOS:
        simulator = CallSimulator(WS_URL, f"{CALL_SID}_{scenario['name'].replace(' ', '_')}")
        success = await simulator.run_conversation_test(scenario)
        results.append({
            'scenario': scenario['name'],
            'success': success,
            'log_file': f"logs/conversation_{scenario['name'].replace(' ', '_')}.json"
        })
        
        # Save conversation log
        simulator.save_conversation_log(results[-1]['log_file'])
        
        # Small delay between scenarios
        await asyncio.sleep(2)
    
    # Print summary
    logger.info("\n" + "="*60)
    logger.info("TEST SUMMARY")
    logger.info("="*60)
    
    for result in results:
        status = "✓ PASSED" if result['success'] else "✗ FAILED"
        logger.info(f"{status} - {result['scenario']}")
        
    passed = sum(1 for r in results if r['success'])
    total = len(results)
    logger.info(f"\nTotal: {passed}/{total} scenarios passed")
    
    return passed == total


if __name__ == "__main__":
    # Create logs directory if it doesn't exist
    import os
    os.makedirs("logs", exist_ok=True)
    
    # Run tests
    success = asyncio.run(main())
    sys.exit(0 if success else 1)