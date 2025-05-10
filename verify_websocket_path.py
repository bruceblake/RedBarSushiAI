#!/usr/bin/env python
"""
Verify the WebSocket path used in the TwiML matches the FastAPI WebSocket route.
"""

import os
import sys
import re
import subprocess
from urllib.parse import urlparse

# Colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def find_websocket_route_pattern():
    """Find the WebSocket route pattern in voice_async.py."""
    try:
        with open("app/api/voice_async.py", "r") as f:
            content = f.read()
            
        # Pattern to match the router.websocket decorator
        route_pattern = r'@router\.websocket\(["\'](.+?)["\']\)'
        matches = re.findall(route_pattern, content)
        
        if matches:
            return matches[0]
        
        print(f"{RED}ERROR: Could not find WebSocket route in app/api/voice_async.py{RESET}")
        return None
    except Exception as e:
        print(f"{RED}ERROR: Failed to read voice_async.py: {str(e)}{RESET}")
        return None

def find_twiml_url_pattern():
    """Find how the WebSocket URL is constructed in the TwiML generation."""
    try:
        with open("app/api/voice_async.py", "r") as f:
            content = f.read()
            
        # Pattern to match the websocket_url assignment
        url_pattern = r'websocket_url\s*=\s*f["\'](.+?)["\']\s*'
        matches = re.findall(url_pattern, content)
        
        if matches:
            # Return the pattern with format placeholders replaced
            return matches[0].replace("{", "[").replace("}", "]")
        
        print(f"{RED}ERROR: Could not find websocket_url pattern in app/api/voice_async.py{RESET}")
        return None
    except Exception as e:
        print(f"{RED}ERROR: Failed to read voice_async.py for TwiML URL: {str(e)}{RESET}")
        return None

def do_paths_match(route_pattern, url_pattern):
    """Check if the WebSocket route pattern matches the TwiML URL pattern."""
    if not route_pattern or not url_pattern:
        return False
    
    # Extract only the path portion
    url_parts = url_pattern.split('://')
    if len(url_parts) > 1:
        url_path = '/' + url_parts[1].split('/', 1)[1]
    else:
        url_path = url_pattern
    
    # Replace variables with placeholders for comparison
    route_normalized = route_pattern.replace("{call_sid}", "[call_sid]")
    url_normalized = url_path.replace("[call_sid]", "[call_sid]")
    
    match = route_normalized == url_normalized
    
    if match:
        print(f"{GREEN}✓ MATCH: WebSocket route '{route_pattern}' matches TwiML URL path '{url_path}'{RESET}")
    else:
        print(f"{RED}✗ MISMATCH: WebSocket route '{route_pattern}' does NOT match TwiML URL path '{url_path}'{RESET}")
        # Suggest a fix
        print(f"{YELLOW}Suggestion: Update one of these to match the other.")
        print(f"If the FastAPI route is correct, update the websocket_url in TwiML generation to:")
        print(f"websocket_url = f\"{{ws_scheme}}://{{host}}{route_pattern.replace('{call_sid}', '{call_sid}')}\"")
        print(f"Current websocket_url format: {url_pattern}{RESET}")
    
    return match
    
def main():
    print("=== WebSocket Path Consistency Check ===\n")
    
    # Find the WebSocket route pattern in voice_async.py
    route_pattern = find_websocket_route_pattern()
    print(f"WebSocket route pattern from FastAPI: {route_pattern}")
    
    # Find the TwiML URL pattern in the TwiML generation
    url_pattern = find_twiml_url_pattern()
    print(f"WebSocket URL pattern in TwiML: {url_pattern}\n")
    
    # Check if they match
    success = do_paths_match(route_pattern, url_pattern)
    
    print("\nWebSocket path consistency check complete!")
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()