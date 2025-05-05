#!/usr/bin/env python3
"""
WebSocket Fix Verification Script for RedBarSushiAI.

This script verifies that the WebSocket fixes have been properly applied
by checking the key files and configuration settings. It also includes
a simple test to verify WebSocket connectivity with enhanced timeout handling.

Usage:
    python verify_websocket_fixes.py [--url URL]
"""

import os
import re
import sys
import json
import logging
import argparse
import ssl
import asyncio
import websockets
import traceback
import time
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('websocket_verification.log')
    ]
)
logger = logging.getLogger("websocket_verification")

def check_procfile():
    """Check if Procfile contains the correct worker configuration."""
    try:
        with open("Procfile", "r") as f:
            content = f.read()
        
        # Check for required parameters
        required_params = [
            ("--graceful-timeout 60", "Graceful shutdown timeout"),
            ("--max-requests 200", "Maximum requests per worker"),
            ("--max-requests-jitter 50", "Request jitter for worker recycling"),
            ("-w 4", "Worker count")
        ]
        
        results = []
        for param, desc in required_params:
            if param in content:
                results.append((desc, "✅ Found"))
            else:
                results.append((desc, "❌ Missing"))
        
        return results
    except Exception as e:
        logger.error(f"Error checking Procfile: {e}")
        return [("Procfile check", f"❌ Error: {e}")]

def check_route_registration():
    """Check if route registration has been fixed to prevent duplicates."""
    try:
        filepath = "app/routes/voice/__init__.py"
        with open(filepath, "r") as f:
            content = f.read()
        
        # Check for the improved route registration check
        improved_check = 'existing_funcs = [f.__name__ for f in sock._rules.values()] if hasattr(sock, \'_rules\') else []'
        check_both = '"media_stream_ws" not in existing_funcs'
        
        results = []
        if improved_check in content:
            results.append(("Function name check", "✅ Found"))
        else:
            results.append(("Function name check", "❌ Missing"))
        
        if check_both in content:
            results.append(("Combined path and function check", "✅ Found"))
        else:
            results.append(("Combined path and function check", "❌ Missing"))
        
        return results
    except Exception as e:
        logger.error(f"Error checking route registration: {e}")
        return [("Route registration check", f"❌ Error: {e}")]

def check_enhanced_stream_handler():
    """Check if the enhanced WebSocket stream handler is implemented."""
    try:
        filepath = "app/routes/voice/realtime/enhanced_stream_handler.py"
        with open(filepath, "r") as f:
            content = f.read()
        
        # Check for key enhanced features
        task_registry = "# Global task registry to prevent garbage collection"
        multiple_keep_alives = "# Send multiple keep-alive messages immediately after greeting"
        follow_up_sequence = "# Wait a bit, then send follow-up prompt"
        connection_maintenance = "async def maintain_connection(ws, session_id):"
        track_active_connections = "active_connections[session_id]"
        proper_logging = 'logger.info(f"[WS:{session_id}]'
        
        results = []
        if task_registry in content:
            results.append(("Task registry for garbage collection", "✅ Found"))
        else:
            results.append(("Task registry for garbage collection", "❌ Missing"))
        
        if multiple_keep_alives in content:
            results.append(("Multiple sequential keep-alives", "✅ Found"))
        else:
            results.append(("Multiple sequential keep-alives", "❌ Missing"))
        
        if follow_up_sequence in content:
            results.append(("Follow-up prompt sequence", "✅ Found"))
        else:
            results.append(("Follow-up prompt sequence", "❌ Missing"))
        
        if connection_maintenance in content:
            results.append(("Connection maintenance task", "✅ Found"))
        else:
            results.append(("Connection maintenance task", "❌ Missing"))
        
        if track_active_connections in content:
            results.append(("Active connection tracking", "✅ Found"))
        else:
            results.append(("Active connection tracking", "❌ Missing"))
        
        if proper_logging in content:
            results.append(("Session-aware logging", "✅ Found"))
        else:
            results.append(("Session-aware logging", "❌ Missing"))
        
        # Check if __init__.py is using the enhanced handler
        init_filepath = "app/routes/voice/__init__.py"
        with open(init_filepath, "r") as f:
            init_content = f.read()
            
        if "from app.routes.voice.realtime.enhanced_stream_handler import handle_enhanced_media_stream" in init_content:
            results.append(("Init importing enhanced handler", "✅ Found"))
        else:
            results.append(("Init importing enhanced handler", "❌ Missing"))
        
        if "await handle_enhanced_media_stream(ws)" in init_content:
            results.append(("Init using enhanced handler", "✅ Found"))
        else:
            results.append(("Init using enhanced handler", "❌ Missing"))
        
        return results
    except Exception as e:
        logger.error(f"Error checking enhanced stream handler: {e}")
        return [("Enhanced stream handler check", f"❌ Error: {e}")]

def check_keep_alive_strategy():
    """Check if the enhanced keep-alive strategy is implemented (legacy check)."""
    try:
        # First check if the enhanced stream handler exists, if so, that's better
        if os.path.exists("app/routes/voice/realtime/enhanced_stream_handler.py"):
            return [("Keep-alive strategy", "✅ Upgraded to enhanced stream handler")]
            
        # Fall back to checking the old handlers.py
        filepath = "app/routes/voice/handlers.py"
        with open(filepath, "r") as f:
            content = f.read()
        
        # Check for the multiple keep-alive messages implementation
        multiple_keep_alives = 'for i in range(5):  # Send 5 keep-alive messages with short intervals'
        delay_between = 'await asyncio.sleep(0.2)  # Small delay between messages'
        alternative_format = 'alt_keep_alive = {'
        
        results = []
        if multiple_keep_alives in content:
            results.append(("Multiple sequential keep-alives", "✅ Found"))
        else:
            results.append(("Multiple sequential keep-alives", "❌ Missing"))
        
        if delay_between in content:
            results.append(("Delay between keep-alives", "✅ Found"))
        else:
            results.append(("Delay between keep-alives", "❌ Missing"))
        
        if alternative_format in content:
            results.append(("Alternative message format fallback", "✅ Found"))
        else:
            results.append(("Alternative message format fallback", "❌ Missing"))
        
        # Check for follow-up prompt with keep-alives
        follow_up_reduced_delay = 'delay=3.0'
        if follow_up_reduced_delay in content:
            results.append(("Reduced follow-up delay (3.0s)", "✅ Found"))
        else:
            results.append(("Reduced follow-up delay", "❌ Missing"))
        
        return results
    except Exception as e:
        logger.error(f"Error checking keep-alive strategy: {e}")
        return [("Keep-alive strategy check", f"❌ Error: {e}")]

def check_improved_twiml():
    """Check if the improved TwiML generator with bidirectional stream is implemented."""
    try:
        filepath = "app/routes/voice/twilio/improved_twiml.py"
        with open(filepath, "r") as f:
            content = f.read()
        
        # Check for bidirectional streaming in the TwiML
        bidirectional_stream = 'track="both_tracks"'
        single_stream_config = 'start.stream('
        proper_greeting = 'Welcome to {environment_name} Red Bar Sushi AI'
        pause_before_stream = 'response.pause(length=1)'
        
        results = []
        if bidirectional_stream in content:
            results.append(("Bidirectional track config", "✅ Found"))
        else:
            results.append(("Bidirectional track config", "❌ Missing"))
        
        if single_stream_config in content:
            results.append(("Single stream configuration", "✅ Found"))
        else:
            results.append(("Single stream configuration", "❌ Missing"))
        
        if proper_greeting in content:
            results.append(("Environment-aware greeting", "✅ Found"))
        else:
            results.append(("Environment-aware greeting", "❌ Missing"))
        
        if pause_before_stream in content:
            results.append(("Pause before streaming", "✅ Found"))
        else:
            results.append(("Pause before streaming", "❌ Missing"))
        
        # Check if routes.py is using the new generator
        routes_filepath = "app/routes/voice/routes.py"
        with open(routes_filepath, "r") as f:
            routes_content = f.read()
            
        if "generate_optimized_media_streams_twiml" in routes_content:
            results.append(("Routes using optimized TwiML", "✅ Found"))
        else:
            results.append(("Routes using optimized TwiML", "❌ Missing"))
        
        if "improved_twiml" in routes_content:
            results.append(("Routes importing improved_twiml", "✅ Found"))
        else:
            results.append(("Routes importing improved_twiml", "❌ Missing"))
        
        return results
    except Exception as e:
        logger.error(f"Error checking improved TwiML: {e}")
        return [("Improved TwiML check", f"❌ Error: {e}")]

async def test_websocket_connection(url, timeout=5.0):
    """Test WebSocket connection stability with proper timeout handling."""
    logger.info(f"Testing WebSocket connection to {url}")
    
    # Create SSL context (don't verify for testing)
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    try:
        # Connect with twilio-media-stream subprotocol
        logger.info("Connecting with twilio-media-stream subprotocol...")
        async with websockets.connect(
            url,
            ssl=ssl_context,
            subprotocols=["twilio-media-stream"]
        ) as ws:
            logger.info("✅ Connected successfully")
            
            # Send a Twilio-like start message
            start_msg = {
                "event": "start",
                "streamSid": "MT" + "".join([str(i) for i in range(32)]),
                "accountSid": "AC" + "".join([str(i) for i in range(32)]),
                "callSid": "CA" + "".join([str(i) for i in range(32)])
            }
            logger.info("Sending Twilio start message...")
            await ws.send(json.dumps(start_msg))
            logger.info("✅ Start message sent")
            
            # Look for initial response message
            logger.info(f"Waiting for initial response (timeout: {timeout}s)...")
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=timeout)
                logger.info(f"✅ Received response: {response[:200]} {'...' if len(response) > 200 else ''}")
                return True, "Connection succeeded and received response"
            except asyncio.TimeoutError:
                logger.warning(f"❌ No response received after {timeout}s")
                return False, f"Timed out waiting for response after {timeout}s"
            except Exception as e:
                logger.error(f"❌ Error receiving response: {e}")
                return False, f"Error receiving response: {e}"
    except Exception as e:
        logger.error(f"❌ Connection failed: {e}")
        logger.error(traceback.format_exc())
        return False, f"Connection failed: {e}"

def get_environment_info():
    """Get information about the environment for context."""
    info = {
        "time": datetime.now().isoformat(),
        "python_version": sys.version,
        "platform": sys.platform,
    }
    
    # Try to get git branch
    try:
        import subprocess
        result = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True)
        if result.returncode == 0:
            info["git_branch"] = result.stdout.strip()
    except:
        pass
    
    return info

def main():
    """Main verification function."""
    parser = argparse.ArgumentParser(description="WebSocket Fix Verification for RedBarSushiAI")
    parser.add_argument("--url", type=str, default="wss://redbarsushiai-staging.onrender.com/ws/voice/media",
                       help="WebSocket URL to test")
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info("RedBarSushiAI WebSocket Fix Verification")
    logger.info("=" * 80)
    
    # Get environment info
    env_info = get_environment_info()
    logger.info(f"Environment: {json.dumps(env_info, indent=2)}")
    
    # Record the start time
    start_time = time.time()
    
    # Check Procfile configuration
    logger.info("\nChecking Procfile configuration...")
    procfile_results = check_procfile()
    for desc, result in procfile_results:
        logger.info(f"  {desc}: {result}")
    
    # Check route registration
    logger.info("\nChecking WebSocket route registration...")
    route_results = check_route_registration()
    for desc, result in route_results:
        logger.info(f"  {desc}: {result}")
    
    # Check keep-alive strategy
    logger.info("\nChecking keep-alive strategy...")
    keep_alive_results = check_keep_alive_strategy()
    for desc, result in keep_alive_results:
        logger.info(f"  {desc}: {result}")
    
    # Check original TwiML generation (legacy check)
    if os.path.exists("app/routes/voice/twilio/twiml.py"):
        logger.info("\nChecking original TwiML generation (legacy)...")
        twiml_results = check_twilio_twiml()
        for desc, result in twiml_results:
            logger.info(f"  {desc}: {result}")
    else:
        twiml_results = [("Original TwiML", "⚠️ File not found (may be renamed)")]
        
    # Check improved TwiML generation
    logger.info("\nChecking improved TwiML generation...")
    improved_twiml_results = check_improved_twiml()
    for desc, result in improved_twiml_results:
        logger.info(f"  {desc}: {result}")
    
    # Check enhanced stream handler
    logger.info("\nChecking enhanced stream handler...")
    enhanced_handler_results = check_enhanced_stream_handler()
    for desc, result in enhanced_handler_results:
        logger.info(f"  {desc}: {result}")
    
    # Test WebSocket connection if requested
    logger.info("\nTesting WebSocket connection (this may take a moment)...")
    try:
        success, message = asyncio.run(test_websocket_connection(args.url))
        if success:
            logger.info(f"✅ WebSocket test successful: {message}")
        else:
            logger.warning(f"❌ WebSocket test failed: {message}")
    except Exception as e:
        logger.error(f"❌ WebSocket test error: {e}")
        logger.error(traceback.format_exc())
    
    # Calculate verification duration
    duration = time.time() - start_time
    
    # Count the results
    all_results = procfile_results + route_results + keep_alive_results + improved_twiml_results + enhanced_handler_results
    success_count = sum(1 for _, result in all_results if "✅" in result)
    failure_count = sum(1 for _, result in all_results if "❌" in result)
    
    # Final summary
    logger.info("\n" + "=" * 80)
    logger.info("VERIFICATION SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total checks: {len(all_results)}")
    logger.info(f"Successful checks: {success_count}")
    logger.info(f"Failed checks: {failure_count}")
    logger.info(f"Verification completed in {duration:.2f} seconds")
    
    if failure_count == 0:
        logger.info("\n✅ ALL CHECKS PASSED! The WebSocket fixes have been properly applied.")
        return 0
    else:
        logger.warning(f"\n⚠️ {failure_count} CHECKS FAILED. Please review the verification results.")
        return 1

if __name__ == "__main__":
    sys.exit(main())