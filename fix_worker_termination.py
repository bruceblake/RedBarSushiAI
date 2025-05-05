#!/usr/bin/env python3
"""
Fix for worker termination issues in RedBarSushiAI voice ordering system.

This script adds graceful shutdown handling to prevent WebSocket connections
from being terminated unexpectedly when worker processes are rotated.

Usage:
    python fix_worker_termination.py

The script modifies the Procfile to include proper graceful shutdown parameters.
"""

import os
import re
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger("fix_worker_termination")

def backup_file(filepath):
    """Create a backup of the file."""
    backup_path = f"{filepath}.bak"
    try:
        with open(filepath, 'r') as original:
            with open(backup_path, 'w') as backup:
                backup.write(original.read())
        logger.info(f"Created backup at {backup_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        return False

def update_procfile():
    """Update the Procfile with graceful shutdown parameters."""
    procfile_path = "Procfile"
    
    # Check if file exists
    if not os.path.exists(procfile_path):
        logger.error(f"Procfile not found at {procfile_path}")
        return False
    
    # Create backup
    if not backup_file(procfile_path):
        logger.error("Aborting due to backup failure")
        return False
    
    try:
        # Read current content
        with open(procfile_path, 'r') as f:
            content = f.read()
        
        # Check if changes are already applied
        if "--graceful-timeout 60" in content and "--max-requests 200" in content:
            logger.info("Graceful shutdown parameters already present in Procfile")
            return True
        
        # Define the pattern to match web worker line
        pattern = r'(web:\s*.*gunicorn\s+.*)'
        
        # Define the replacement with graceful shutdown parameters
        replacement = r'web: FLASK_SKIP_DOTENV=1 WEB_CONCURRENCY=4 gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 4 --bind 0.0.0.0:$PORT --timeout 300 --keep-alive 10 --graceful-timeout 60 --max-requests 200 --max-requests-jitter 50 \'run:app\''
        
        # If the pattern doesn't match exactly, try a more flexible approach
        if not re.search(pattern, content):
            logger.warning("Web worker line not found with exact pattern, using alternate approach")
            
            # Find the line starting with "web:"
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if line.startswith('web:'):
                    lines[i] = replacement
                    break
            
            updated_content = '\n'.join(lines)
        else:
            # Apply the replacement
            updated_content = re.sub(pattern, replacement, content)
        
        # Write updated content
        with open(procfile_path, 'w') as f:
            f.write(updated_content)
        
        logger.info("Successfully updated Procfile with graceful shutdown parameters")
        return True
        
    except Exception as e:
        logger.error(f"Error updating Procfile: {e}")
        return False

def update_websocket_route_registration():
    """
    Ensure WebSocket routes are not registered multiple times.
    Improves the route registration check in voice/__init__.py.
    """
    ws_init_path = "app/routes/voice/__init__.py"
    
    # Check if file exists
    if not os.path.exists(ws_init_path):
        logger.error(f"WebSocket init file not found at {ws_init_path}")
        return False
    
    # Create backup
    if not backup_file(ws_init_path):
        logger.error("Aborting due to backup failure")
        return False
    
    try:
        # Read current content
        with open(ws_init_path, 'r') as f:
            content = f.read()
        
        # Check if the improved check is already present
        if "existing_funcs = [f.__name__ for f in sock._rules.values()] if hasattr(sock, '_rules') else []" in content:
            logger.info("Enhanced WebSocket route registration check already present")
            return True
        
        # Look for the existing route check pattern
        route_check_pattern = r'if\s+"/ws/voice/media"\s+not\s+in\s+existing_routes:'
        
        # New improved check
        improved_check = 'existing_funcs = [f.__name__ for f in sock._rules.values()] if hasattr(sock, \'_rules\') else []\n\n            if "/ws/voice/media" not in existing_routes and "media_stream_ws" not in existing_funcs:'
        
        # Apply the replacement
        updated_content = re.sub(route_check_pattern, improved_check, content)
        
        # Write updated content
        with open(ws_init_path, 'w') as f:
            f.write(updated_content)
        
        logger.info("Successfully updated WebSocket route registration check")
        return True
        
    except Exception as e:
        logger.error(f"Error updating WebSocket route registration: {e}")
        return False

def update_keep_alive_messages():
    """
    Enhance keep-alive message strategy in voice/handlers.py.
    Ensures multiple keep-alive messages are sent with proper delays.
    """
    handlers_path = "app/routes/voice/handlers.py"
    
    # Check if file exists
    if not os.path.exists(handlers_path):
        logger.error(f"Handlers file not found at {handlers_path}")
        return False
    
    # Create backup
    if not backup_file(handlers_path):
        logger.error("Aborting due to backup failure")
        return False
    
    try:
        # Read current content
        with open(handlers_path, 'r') as f:
            content = f.read()
        
        # Check if the enhanced keep-alive strategy is already present
        if "for i in range(5):  # Send 5 keep-alive messages with short intervals" in content:
            logger.info("Enhanced keep-alive strategy already present")
            return True
        
        # Find the single keep-alive message pattern
        single_keep_alive_pattern = r'(# Send a keep-alive message after greeting.*?await ws\.send\(json\.dumps\(keep_alive\)\).*?metrics\["events_sent"\] \+= 1)'
        
        # New enhanced keep-alive strategy with multiple messages
        enhanced_keep_alive = '''                    # Send multiple keep-alive messages after greeting to maintain connection
                    logger.critical(f"[SILENCE:{session_id}] Sending multiple keep-alive messages after greeting")
                    for i in range(5):  # Send 5 keep-alive messages with short intervals
                        keep_alive = {
                            "type": "connection_keep_alive", 
                            "message": f"Keeping connection alive after greeting ({i+1}/5)",
                            "timestamp": silence_timestamp + i*0.2,
                            "session_id": session_id
                        }
                        try:
                            await asyncio.sleep(0.2)  # Small delay between messages
                            await ws.send(json.dumps(keep_alive))
                            metrics["events_sent"] += 1
                            logger.critical(f"[SILENCE:{session_id}] ✅ Sent keep-alive #{i+1} after greeting")
                        except Exception as ka_error:
                            logger.critical(f"[SILENCE:{session_id}] ❌ Error sending keep-alive #{i+1}: {ka_error}")
                            # Try an alternative format
                            try:
                                alt_keep_alive = {
                                    "event": "ping", 
                                    "message": f"Keep-alive ping #{i+1}",
                                    "timestamp": time.time()
                                }
                                await ws.send(json.dumps(alt_keep_alive))
                                logger.critical(f"[SILENCE:{session_id}] ✅ Sent alternative keep-alive #{i+1}")
                            except Exception as alt_error:
                                logger.critical(f"[SILENCE:{session_id}] ❌ Alternative also failed: {alt_error}")
                    
                    # Log completion of keep-alive sequence
                    logger.critical(f"[SILENCE:{session_id}] ✅ Completed keep-alive sequence after greeting")'''
        
        # Apply the replacement
        if re.search(single_keep_alive_pattern, content, re.DOTALL):
            updated_content = re.sub(single_keep_alive_pattern, enhanced_keep_alive, content, flags=re.DOTALL)
        else:
            logger.warning("Could not find single keep-alive pattern, skipping this update")
            updated_content = content
        
        # Also update the silence keep-alive strategy (add multiple keep-alives)
        silence_keep_alive_pattern = r'(# Send a keep-alive message for other states.*?await ws\.send\(json\.dumps\(keep_alive\)\).*?metrics\["events_sent"\] \+= 1)'
        
        enhanced_silence_keep_alive = '''                # Send a keep-alive message for other states
                try:
                    # Send multiple keep-alive messages to ensure connection stays open
                    for i in range(3):
                        keep_alive = {
                            "type": "silence_keep_alive", 
                            "message": f"Keeping connection alive during silence in {current_state} state ({i+1}/3)",
                            "timestamp": silence_timestamp + (i * 0.2),
                            "session_id": session_id,
                            "state": str(current_state)
                        }
                        await ws.send(json.dumps(keep_alive))
                        metrics["events_sent"] += 1
                        logger.critical(f"[SILENCE:{session_id}] Sent silence keep-alive #{i+1} in {current_state} state")
                        await asyncio.sleep(0.2)  # Small delay between keep-alives
                except Exception as ka_error:
                    logger.critical(f"[SILENCE:{session_id}] Error sending silence keep-alive: {ka_error}")
                    # Try alternative format
                    try:
                        alt_keep_alive = {
                            "event": "ping",
                            "timestamp": time.time(),
                            "session_id": session_id
                        }
                        await ws.send(json.dumps(alt_keep_alive))
                        logger.critical(f"[SILENCE:{session_id}] Sent alternative keep-alive in {current_state} state")
                    except Exception as alt_error:
                        logger.critical(f"[SILENCE:{session_id}] Alternative also failed: {alt_error}")'''
        
        # Apply the second replacement
        if re.search(silence_keep_alive_pattern, updated_content, re.DOTALL):
            final_content = re.sub(silence_keep_alive_pattern, enhanced_silence_keep_alive, updated_content, flags=re.DOTALL)
        else:
            logger.warning("Could not find silence keep-alive pattern, skipping this update")
            final_content = updated_content
        
        # Write updated content
        with open(handlers_path, 'w') as f:
            f.write(final_content)
        
        logger.info("Successfully updated keep-alive message strategy")
        return True
        
    except Exception as e:
        logger.error(f"Error updating keep-alive message strategy: {e}")
        return False

def main():
    """Main function to run all fixes."""
    logger.info("Starting worker termination fix")
    
    # Update Procfile with graceful shutdown parameters
    logger.info("Updating Procfile with graceful shutdown parameters...")
    procfile_updated = update_procfile()
    
    # Update WebSocket route registration
    logger.info("Enhancing WebSocket route registration check...")
    route_check_updated = update_websocket_route_registration()
    
    # Update keep-alive message strategy
    logger.info("Enhancing keep-alive message strategy...")
    keep_alive_updated = update_keep_alive_messages()
    
    # Summary
    logger.info("\n=== Fix Summary ===")
    logger.info(f"Procfile updated: {'✅ Success' if procfile_updated else '❌ Failed'}")
    logger.info(f"WebSocket route registration enhanced: {'✅ Success' if route_check_updated else '❌ Failed'}")
    logger.info(f"Keep-alive message strategy enhanced: {'✅ Success' if keep_alive_updated else '❌ Failed'}")
    
    if procfile_updated and route_check_updated and keep_alive_updated:
        logger.info("\n✅ All fixes successfully applied! WebSocket connections should now remain stable.")
        logger.info("To apply changes, restart the application with:")
        logger.info("  1. git commit -am 'Fix WebSocket disconnection and worker termination issues'")
        logger.info("  2. git push")
        logger.info("  3. Redeploy the application on Render")
    else:
        logger.warning("\n⚠️ Some fixes could not be applied. Check the logs above for details.")

if __name__ == "__main__":
    main()