#!/usr/bin/env python3
"""
WebSocket Failure Mode Tester for RedBarSushiAI

This script tests various potential failure modes for WebSocket connections in the
RedBarSushiAI system. It simulates different scenarios that could cause disconnections
and validates that the implemented fixes address these issues.

Usage:
    python test_failure_modes.py [--url URL]
"""

import asyncio
import websockets
import json
import time
import argparse
import logging
import sys
import ssl
import uuid
import signal
import socket
import random
import traceback
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('failure_mode_tests.log')
    ]
)
logger = logging.getLogger("failure_mode_test")

# Connection statistics
connection_stats = {
    "tests_run": 0,
    "tests_passed": 0,
    "tests_failed": 0,
    "tests_skipped": 0
}

class FailureTest:
    """Base class for failure tests."""
    
    def __init__(self, name, description):
        """Initialize the test."""
        self.name = name
        self.description = description
        self.result = None
        self.error = None
        self.duration = None
    
    async def run(self, url):
        """Run the test."""
        logger.info(f"\n{'='*70}")
        logger.info(f"RUNNING TEST: {self.name}")
        logger.info(f"{self.description}")
        logger.info(f"{'-'*70}")
        
        start_time = time.time()
        
        try:
            self.result = await self._execute(url)
            self.duration = time.time() - start_time
            
            if self.result:
                logger.info(f"✅ PASSED: {self.name} ({self.duration:.2f}s)")
                connection_stats["tests_passed"] += 1
            else:
                logger.error(f"❌ FAILED: {self.name} ({self.duration:.2f}s)")
                logger.error(f"Reason: {self.error or 'Test condition not met'}")
                connection_stats["tests_failed"] += 1
        except Exception as e:
            self.duration = time.time() - start_time
            self.error = str(e)
            self.result = False
            logger.error(f"❌ ERROR: {self.name} - {e} ({self.duration:.2f}s)")
            logger.error(traceback.format_exc())
            connection_stats["tests_failed"] += 1
        
        connection_stats["tests_run"] += 1
        return self.result
    
    async def _execute(self, url):
        """Execute the test - to be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement this method")

class NetworkLatencyTest(FailureTest):
    """Test WebSocket behavior with network latency."""
    
    def __init__(self, latency_ms=500):
        """Initialize the test with the specified latency."""
        super().__init__(
            name=f"Network Latency ({latency_ms}ms)",
            description=f"Tests WebSocket behavior with {latency_ms}ms of network latency"
        )
        self.latency_ms = latency_ms
    
    async def _execute(self, url):
        """Execute the test."""
        ssl_context = None
        if url.startswith("wss://"):
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        
        try:
            # Connect with custom socket class that adds latency
            class LatencySocket(socket.socket):
                def send(self, data):
                    # Simulate latency
                    asyncio.get_event_loop().run_in_executor(
                        None, 
                        lambda: time.sleep(self.latency_ms / 1000)
                    )
                    return super().send(data)
                
                def recv(self, bufsize):
                    # Simulate latency
                    asyncio.get_event_loop().run_in_executor(
                        None, 
                        lambda: time.sleep(self.latency_ms / 1000)
                    )
                    return super().recv(bufsize)
            
            # Can't easily patch socket class, so we'll simulate latency another way
            async with websockets.connect(url, ssl=ssl_context) as ws:
                logger.info(f"✅ Connected to {url}")
                
                # Send initial message
                await ws.send(json.dumps({
                    "event": "start",
                    "streamSid": "MT" + "".join([str(i) for i in range(32)]),
                    "accountSid": "AC" + "".join([str(i) for i in range(32)]),
                    "callSid": "CA" + "".join([str(i) for i in range(32)]),
                    "tracks": ["inbound_track"]
                }))
                logger.info("✅ Sent start message")
                
                # Explicitly add latency to sends and receives
                greeting_received = False
                keep_alive_count = 0
                post_greeting_messages = 0
                greeting_time = None
                
                # Test for 20 seconds
                start_time = time.time()
                max_duration = 20  # seconds
                
                while time.time() - start_time < max_duration:
                    try:
                        # Simulate latency before receiving
                        await asyncio.sleep(self.latency_ms / 1000)
                        message = await asyncio.wait_for(ws.recv(), timeout=2.0)
                        
                        # Process message
                        try:
                            data = json.loads(message)
                            message_type = data.get("type") or data.get("event", "unknown")
                            
                            # Check for greeting
                            is_greeting = False
                            if "text" in data:
                                text = data.get("text", "").lower()
                                is_greeting = (
                                    data.get("is_greeting", False) or
                                    "welcome" in text or
                                    "how can i help" in text
                                )
                            
                            if is_greeting and not greeting_received:
                                greeting_received = True
                                greeting_time = time.time()
                                logger.info(f"✅ Received greeting: {data.get('text', '')}")
                                
                                # Simulate user response with latency
                                await asyncio.sleep(self.latency_ms / 1000)
                                await ws.send(json.dumps({
                                    "event": "user_input",
                                    "text": "I would like to order sushi",
                                    "timestamp": time.time()
                                }))
                            
                            # Track keep-alives
                            if message_type == "heartbeat" or message_type == "keep_alive" or "keep_alive" in message_type:
                                keep_alive_count += 1
                                logger.info(f"✅ Received keep-alive #{keep_alive_count}")
                            
                            # Track post-greeting messages
                            if greeting_received:
                                post_greeting_messages += 1
                        except:
                            # Not JSON, ignore
                            pass
                        
                        # Periodically send a message to simulate client activity
                        if random.random() < 0.2:  # 20% chance
                            await asyncio.sleep(self.latency_ms / 1000)
                            await ws.send(json.dumps({
                                "type": "ping",
                                "timestamp": time.time()
                            }))
                    
                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        logger.error(f"Error during test: {e}")
                        self.error = str(e)
                        return False
                
                # Test passes if we received a greeting and maintained connection after it
                if greeting_received and post_greeting_messages > 3:
                    logger.info(f"✅ Connection maintained with {self.latency_ms}ms latency")
                    logger.info(f"✅ Received {post_greeting_messages} messages after greeting")
                    return True
                elif greeting_received:
                    self.error = f"Received greeting but only {post_greeting_messages} messages afterward"
                    return False
                else:
                    self.error = "Did not receive greeting"
                    return False
        
        except Exception as e:
            self.error = str(e)
            return False

class PacketLossTest(FailureTest):
    """Test WebSocket behavior with packet loss."""
    
    def __init__(self, loss_rate=0.2):
        """Initialize the test with the specified packet loss rate."""
        super().__init__(
            name=f"Packet Loss ({int(loss_rate*100)}%)",
            description=f"Tests WebSocket behavior with {int(loss_rate*100)}% packet loss"
        )
        self.loss_rate = loss_rate
    
    async def _execute(self, url):
        """Execute the test."""
        ssl_context = None
        if url.startswith("wss://"):
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        
        try:
            # Connect normally (we'll simulate packet loss at the application level)
            async with websockets.connect(url, ssl=ssl_context) as ws:
                logger.info(f"✅ Connected to {url}")
                
                # Original send method
                original_send = ws.send
                
                # Override send method to simulate packet loss
                async def send_with_loss(message):
                    if random.random() >= self.loss_rate:
                        return await original_send(message)
                    else:
                        logger.info(f"⚠️ Simulated packet loss (outgoing)")
                        # Simulate successful send for the test
                        return None
                
                # Apply the override
                ws.send = send_with_loss
                
                # Send initial message
                await ws.send(json.dumps({
                    "event": "start",
                    "streamSid": "MT" + "".join([str(i) for i in range(32)]),
                    "accountSid": "AC" + "".join([str(i) for i in range(32)]),
                    "callSid": "CA" + "".join([str(i) for i in range(32)]),
                    "tracks": ["inbound_track"]
                }))
                logger.info("✅ Sent start message")
                
                # Tracking variables
                greeting_received = False
                keep_alive_count = 0
                post_greeting_messages = 0
                greeting_time = None
                
                # Test for 20 seconds
                start_time = time.time()
                max_duration = 20  # seconds
                
                while time.time() - start_time < max_duration:
                    try:
                        # Receive messages with simulated packet loss for receiving
                        if random.random() < self.loss_rate:
                            logger.info(f"⚠️ Simulated packet loss (incoming)")
                            await asyncio.sleep(0.5)  # Simulate waiting time
                            continue
                        
                        message = await asyncio.wait_for(ws.recv(), timeout=2.0)
                        
                        # Process message
                        try:
                            data = json.loads(message)
                            message_type = data.get("type") or data.get("event", "unknown")
                            
                            # Check for greeting
                            is_greeting = False
                            if "text" in data:
                                text = data.get("text", "").lower()
                                is_greeting = (
                                    data.get("is_greeting", False) or
                                    "welcome" in text or
                                    "how can i help" in text
                                )
                            
                            if is_greeting and not greeting_received:
                                greeting_received = True
                                greeting_time = time.time()
                                logger.info(f"✅ Received greeting: {data.get('text', '')}")
                                
                                # Simulate user response
                                await ws.send(json.dumps({
                                    "event": "user_input",
                                    "text": "I would like to order sushi",
                                    "timestamp": time.time()
                                }))
                            
                            # Track keep-alives
                            if message_type == "heartbeat" or message_type == "keep_alive" or "keep_alive" in message_type:
                                keep_alive_count += 1
                                logger.info(f"✅ Received keep-alive #{keep_alive_count}")
                            
                            # Track post-greeting messages
                            if greeting_received:
                                post_greeting_messages += 1
                        except:
                            # Not JSON, ignore
                            pass
                        
                        # Periodically send a message to simulate client activity
                        if random.random() < 0.2:  # 20% chance
                            await ws.send(json.dumps({
                                "type": "ping",
                                "timestamp": time.time()
                            }))
                    
                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        logger.error(f"Error during test: {e}")
                        self.error = str(e)
                        return False
                
                # Test passes if we received a greeting and maintained connection after it
                if greeting_received and post_greeting_messages > 3:
                    logger.info(f"✅ Connection maintained with {int(self.loss_rate*100)}% packet loss")
                    logger.info(f"✅ Received {post_greeting_messages} messages after greeting")
                    return True
                elif greeting_received:
                    self.error = f"Received greeting but only {post_greeting_messages} messages afterward"
                    return False
                else:
                    self.error = "Did not receive greeting"
                    return False
        
        except Exception as e:
            self.error = str(e)
            return False

class HighLoadTest(FailureTest):
    """Test WebSocket behavior under high load."""
    
    def __init__(self, connections=10):
        """Initialize the test with the specified number of concurrent connections."""
        super().__init__(
            name=f"High Load ({connections} connections)",
            description=f"Tests WebSocket behavior with {connections} concurrent connections"
        )
        self.connections = connections
    
    async def _execute(self, url):
        """Execute the test."""
        ssl_context = None
        if url.startswith("wss://"):
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        
        try:
            # Create multiple concurrent connections
            connection_tasks = []
            for i in range(self.connections):
                connection_tasks.append(self._test_single_connection(url, i, ssl_context))
            
            # Run all connections concurrently
            results = await asyncio.gather(*connection_tasks, return_exceptions=True)
            
            # Check results
            success_count = sum(1 for result in results if result is True)
            error_count = sum(1 for result in results if isinstance(result, Exception))
            
            logger.info(f"Results: {success_count} successful, {error_count} errors")
            
            # Test passes if at least 70% of connections were successful
            success_rate = success_count / self.connections
            if success_rate >= 0.7:
                logger.info(f"✅ {int(success_rate*100)}% of connections maintained under high load")
                return True
            else:
                self.error = f"Only {int(success_rate*100)}% of connections succeeded (need 70%)"
                return False
        
        except Exception as e:
            self.error = str(e)
            return False
    
    async def _test_single_connection(self, url, connection_index, ssl_context):
        """Test a single connection."""
        try:
            logger.info(f"Starting connection #{connection_index}")
            async with websockets.connect(url, ssl=ssl_context) as ws:
                logger.info(f"Connection #{connection_index} established")
                
                # Send initial message
                await ws.send(json.dumps({
                    "event": "start",
                    "streamSid": f"MT{connection_index}" + "".join([str(i) for i in range(30)]),
                    "accountSid": f"AC{connection_index}" + "".join([str(i) for i in range(30)]),
                    "callSid": f"CA{connection_index}" + "".join([str(i) for i in range(30)]),
                    "tracks": ["inbound_track"]
                }))
                
                # Tracking variables
                greeting_received = False
                message_count = 0
                start_time = time.time()
                max_duration = 15  # seconds
                
                # Add jitter to prevent synchronized behavior
                await asyncio.sleep(random.random() * 0.5)
                
                while time.time() - start_time < max_duration:
                    try:
                        message = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        message_count += 1
                        
                        # Check for greeting
                        try:
                            data = json.loads(message)
                            if "text" in data:
                                text = data.get("text", "").lower()
                                if "welcome" in text or data.get("is_greeting", False):
                                    greeting_received = True
                                    # Respond to greeting
                                    await ws.send(json.dumps({
                                        "event": "user_input",
                                        "text": f"Connection #{connection_index} responding to greeting",
                                        "timestamp": time.time()
                                    }))
                        except:
                            pass
                        
                        # Periodically send a message
                        if random.random() < 0.1:  # 10% chance
                            await ws.send(json.dumps({
                                "type": "ping",
                                "connection": connection_index,
                                "timestamp": time.time()
                            }))
                    
                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        logger.error(f"Connection #{connection_index} error: {e}")
                        return False
                
                # Success if we received messages and maintained connection
                if message_count > 5:
                    logger.info(f"Connection #{connection_index} succeeded with {message_count} messages")
                    return True
                else:
                    logger.error(f"Connection #{connection_index} failed with only {message_count} messages")
                    return False
        
        except Exception as e:
            logger.error(f"Connection #{connection_index} failed: {e}")
            return e

class LongPauseTest(FailureTest):
    """Test WebSocket behavior with long pauses in communication."""
    
    def __init__(self, pause_seconds=5):
        """Initialize the test with the specified pause duration."""
        super().__init__(
            name=f"Long Pause ({pause_seconds}s)",
            description=f"Tests WebSocket behavior with {pause_seconds}s pause in communication"
        )
        self.pause_seconds = pause_seconds
    
    async def _execute(self, url):
        """Execute the test."""
        ssl_context = None
        if url.startswith("wss://"):
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        
        try:
            # Connect normally
            async with websockets.connect(url, ssl=ssl_context) as ws:
                logger.info(f"✅ Connected to {url}")
                
                # Send initial message
                await ws.send(json.dumps({
                    "event": "start",
                    "streamSid": "MT" + "".join([str(i) for i in range(32)]),
                    "accountSid": "AC" + "".join([str(i) for i in range(32)]),
                    "callSid": "CA" + "".join([str(i) for i in range(32)]),
                    "tracks": ["inbound_track"]
                }))
                logger.info("✅ Sent start message")
                
                # Tracking variables
                greeting_received = False
                message_count = 0
                
                # Wait for greeting
                while not greeting_received:
                    try:
                        message = await asyncio.wait_for(ws.recv(), timeout=5.0)
                        message_count += 1
                        
                        try:
                            data = json.loads(message)
                            if "text" in data:
                                text = data.get("text", "").lower()
                                if "welcome" in text or data.get("is_greeting", False):
                                    greeting_received = True
                                    logger.info(f"✅ Received greeting: {data.get('text', '')}")
                        except:
                            pass
                    
                    except asyncio.TimeoutError:
                        logger.warning("Timeout waiting for greeting")
                        continue
                    except Exception as e:
                        logger.error(f"Error waiting for greeting: {e}")
                        self.error = str(e)
                        return False
                
                # Now that we've received the greeting, pause for the specified duration
                logger.info(f"Pausing for {self.pause_seconds}s after greeting...")
                await asyncio.sleep(self.pause_seconds)
                
                # After pause, send a message and see if we still get a response
                try:
                    logger.info("Sending message after pause...")
                    await ws.send(json.dumps({
                        "event": "user_input",
                        "text": "I would like to order sushi",
                        "timestamp": time.time()
                    }))
                    
                    # Wait for a response
                    post_pause_messages = 0
                    for _ in range(3):  # Try to receive up to 3 messages
                        try:
                            message = await asyncio.wait_for(ws.recv(), timeout=2.0)
                            post_pause_messages += 1
                            logger.info(f"✅ Received message after pause: {message[:100]}")
                        except asyncio.TimeoutError:
                            break
                        except Exception as e:
                            logger.error(f"Error receiving after pause: {e}")
                            break
                    
                    # Test passes if we received at least one message after the pause
                    if post_pause_messages > 0:
                        logger.info(f"✅ Connection maintained after {self.pause_seconds}s pause")
                        return True
                    else:
                        self.error = "No messages received after pause"
                        return False
                
                except Exception as e:
                    logger.error(f"Error sending after pause: {e}")
                    self.error = str(e)
                    return False
        
        except Exception as e:
            self.error = str(e)
            return False

class ReconnectionTest(FailureTest):
    """Test WebSocket reconnection behavior."""
    
    def __init__(self):
        """Initialize the test."""
        super().__init__(
            name="Reconnection Test",
            description="Tests WebSocket reconnection behavior after disconnection"
        )
    
    async def _execute(self, url):
        """Execute the test."""
        ssl_context = None
        if url.startswith("wss://"):
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        
        try:
            # First connection to establish session
            session_id = str(uuid.uuid4())[:12]
            logger.info(f"Establishing first connection with session ID: {session_id}")
            
            # Connect first time
            first_connection_ok = False
            try:
                async with websockets.connect(url, ssl=ssl_context) as ws:
                    logger.info("✅ First connection established")
                    
                    # Send start message with session ID
                    await ws.send(json.dumps({
                        "event": "start",
                        "streamSid": f"MT{session_id}",
                        "accountSid": f"AC{session_id}",
                        "callSid": f"CA{session_id}",
                        "session_id": session_id,
                        "tracks": ["inbound_track"]
                    }))
                    logger.info("✅ Sent start message")
                    
                    # Wait briefly to establish session
                    message_count = 0
                    for _ in range(3):
                        try:
                            message = await asyncio.wait_for(ws.recv(), timeout=1.0)
                            message_count += 1
                        except:
                            pass
                    
                    first_connection_ok = message_count > 0
                    logger.info(f"First connection received {message_count} messages")
            except Exception as e:
                logger.error(f"Error in first connection: {e}")
                self.error = f"First connection failed: {e}"
                return False
            
            if not first_connection_ok:
                self.error = "First connection did not receive any messages"
                return False
            
            # Wait briefly between connections
            logger.info("Waiting 2 seconds before reconnection...")
            await asyncio.sleep(2)
            
            # Reconnect
            logger.info(f"Attempting reconnection with session ID: {session_id}")
            try:
                async with websockets.connect(url, ssl=ssl_context) as ws:
                    logger.info("✅ Reconnection established")
                    
                    # Send start message with same session ID
                    await ws.send(json.dumps({
                        "event": "start",
                        "streamSid": f"MT{session_id}",
                        "accountSid": f"AC{session_id}",
                        "callSid": f"CA{session_id}",
                        "session_id": session_id,
                        "tracks": ["inbound_track"],
                        "is_reconnection": True
                    }))
                    logger.info("✅ Sent reconnection start message")
                    
                    # Wait for messages after reconnection
                    reconnect_messages = 0
                    greeting_received = False
                    post_greeting_messages = 0
                    
                    start_time = time.time()
                    max_duration = 15  # seconds
                    
                    while time.time() - start_time < max_duration:
                        try:
                            message = await asyncio.wait_for(ws.recv(), timeout=1.0)
                            reconnect_messages += 1
                            
                            # Process message
                            try:
                                data = json.loads(message)
                                if "text" in data:
                                    text = data.get("text", "").lower()
                                    if "welcome" in text or data.get("is_greeting", False):
                                        greeting_received = True
                                        logger.info(f"✅ Received greeting after reconnection")
                                        
                                        # Respond to greeting
                                        await ws.send(json.dumps({
                                            "event": "user_input",
                                            "text": "I need to finish my order",
                                            "timestamp": time.time(),
                                            "session_id": session_id
                                        }))
                                
                                # Count post-greeting messages
                                if greeting_received:
                                    post_greeting_messages += 1
                            except:
                                pass
                        
                        except asyncio.TimeoutError:
                            continue
                        except Exception as e:
                            logger.error(f"Error in reconnection: {e}")
                            self.error = f"Reconnection error: {e}"
                            return False
                    
                    # Test passes if:
                    # 1. We received any messages after reconnection
                    # 2. We received a greeting after reconnection
                    # 3. We received messages after the greeting
                    
                    logger.info(f"Reconnection received {reconnect_messages} messages")
                    logger.info(f"Greeting received: {greeting_received}")
                    logger.info(f"Post-greeting messages: {post_greeting_messages}")
                    
                    if reconnect_messages > 0 and greeting_received and post_greeting_messages > 0:
                        logger.info("✅ Successful reconnection with continuous communication")
                        return True
                    elif reconnect_messages > 0:
                        self.error = "Reconnection succeeded but greeting handling failed"
                        return False
                    else:
                        self.error = "No messages received after reconnection"
                        return False
            
            except Exception as e:
                logger.error(f"Error in reconnection: {e}")
                self.error = f"Reconnection failed: {e}"
                return False
        
        except Exception as e:
            self.error = str(e)
            return False

async def run_tests(url):
    """Run all failure mode tests."""
    logger.info(f"\n{'='*70}")
    logger.info(f"WebSocket Failure Mode Tests - {datetime.now().isoformat()}")
    logger.info(f"Target URL: {url}")
    logger.info(f"{'='*70}\n")
    
    # Define tests
    tests = [
        NetworkLatencyTest(latency_ms=200),
        NetworkLatencyTest(latency_ms=500),
        PacketLossTest(loss_rate=0.1),
        PacketLossTest(loss_rate=0.3),
        LongPauseTest(pause_seconds=5),
        LongPauseTest(pause_seconds=10),
        HighLoadTest(connections=5),
        ReconnectionTest()
    ]
    
    # Run tests
    for test in tests:
        await test.run(url)
        # Add a brief pause between tests
        await asyncio.sleep(2)
    
    # Print summary
    logger.info(f"\n{'='*70}")
    logger.info(f"TEST SUMMARY")
    logger.info(f"{'='*70}")
    logger.info(f"Tests Run:    {connection_stats['tests_run']}")
    logger.info(f"Tests Passed: {connection_stats['tests_passed']}")
    logger.info(f"Tests Failed: {connection_stats['tests_failed']}")
    logger.info(f"Tests Skipped: {connection_stats['tests_skipped']}")
    logger.info(f"Pass Rate:    {connection_stats['tests_passed'] / connection_stats['tests_run'] * 100:.1f}%")
    
    # Print detailed results
    logger.info(f"\n{'='*70}")
    logger.info(f"DETAILED RESULTS")
    logger.info(f"{'='*70}")
    for test in tests:
        status = "✅ PASSED" if test.result else "❌ FAILED"
        logger.info(f"{status}: {test.name} - {test.duration:.2f}s")
        if not test.result and test.error:
            logger.info(f"    Reason: {test.error}")
    
    # Overall success
    return connection_stats['tests_passed'] / connection_stats['tests_run'] >= 0.7

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="WebSocket Failure Mode Tester for RedBarSushiAI")
    parser.add_argument("--url", type=str, default="ws://localhost:5000/ws/voice/media",
                       help="WebSocket URL to test")
    parser.add_argument("--verbose", action="store_true",
                       help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        
    try:
        # Run the async tests
        success = asyncio.run(run_tests(args.url))
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Tests interrupted by user")
        sys.exit(130)  # Standard exit code for SIGINT
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()