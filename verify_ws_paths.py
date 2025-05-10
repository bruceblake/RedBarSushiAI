#!/usr/bin/env python
"""
Script to verify that the WebSocket paths in the FastAPI route and TwiML generation match.
"""

import os
import sys
import re
from urllib.parse import urlparse

# ANSI color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"

def extract_twiml_ws_url_from_voice_py():
    """Extract the WebSocket URL pattern from app/api/voice.py."""
    try:
        with open("app/api/voice.py", "r") as f:
            content = f.read()
        
        # Look for the WebSocket URL construction
        pattern = r'ws_url\s*=\s*f"(.+?)"'
        match = re.search(pattern, content)
        
        if match:
            url_pattern = match.group(1)
            # Replace format string placeholders
            url_pattern = url_pattern.replace("{", "<").replace("}", ">")
            print(f"{CYAN}Found TwiML WebSocket URL pattern in voice.py: {url_pattern}{RESET}")
            return url_pattern
        
        print(f"{RED}Could not find WebSocket URL pattern in voice.py{RESET}")
        return None
    except Exception as e:
        print(f"{RED}Error reading voice.py: {str(e)}{RESET}")
        return None

def extract_fastapi_ws_route():
    """Extract the FastAPI WebSocket route from app/api/voice_async.py and __init__.py."""
    try:
        # Get the WebSocket route from voice_async.py
        with open("app/api/voice_async.py", "r") as f:
            content = f.read()
        
        route_pattern = r'@router\.websocket\(["\'](.+?)["\']'
        match = re.search(route_pattern, content)
        
        if not match:
            print(f"{RED}Could not find WebSocket route in app/api/voice_async.py{RESET}")
            return None
        
        ws_route = match.group(1)
        print(f"{CYAN}Found WebSocket route in voice_async.py: {ws_route}{RESET}")
        
        # Get the prefix from __init__.py
        with open("app/api/__init__.py", "r") as f:
            content = f.read()
        
        # Look for the line mounting voice_async_router
        prefix_pattern = r'api_router\.include_router\(voice_async_router,\s*prefix=["\'](.*?)["\']\)'
        match = re.search(prefix_pattern, content)
        
        if not match:
            print(f"{YELLOW}Warning: Could not find voice_async_router mount prefix in __init__.py{RESET}")
            prefix = ""
        else:
            prefix = match.group(1)
            print(f"{CYAN}Found prefix for voice_async_router in __init__.py: {prefix}{RESET}")
        
        # Combine prefix and route
        full_route = f"{prefix}{ws_route}"
        full_route = full_route.replace("{", "<").replace("}", ">")  # For comparison
        print(f"{CYAN}Resulting full FastAPI WebSocket route: {full_route}{RESET}")
        
        return full_route
    
    except Exception as e:
        print(f"{RED}Error extracting FastAPI WebSocket route: {str(e)}{RESET}")
        return None

def check_path_match(twiml_url, fastapi_route):
    """Check if the TwiML WebSocket URL and FastAPI route match."""
    if not twiml_url or not fastapi_route:
        print(f"{RED}Cannot compare routes: One or both routes not found{RESET}")
        return False
    
    # Extract path from TwiML URL (which could include scheme, host)
    # For the specific case where we have <ws_base_url> in the pattern
    if twiml_url.startswith("<ws_base_url>"):
        path = twiml_url[len("<ws_base_url>"):]
    else:
        url_parts = twiml_url.split("://", 1)
        if len(url_parts) > 1:
            # It has a scheme, extract just the path
            path = "/" + url_parts[1].split("/", 1)[1] if "/" in url_parts[1] else "/"
        else:
            # It's just a path
            path = twiml_url
    
    # Now compare the paths
    if path == fastapi_route:
        print(f"\n{GREEN}✓ SUCCESS: TwiML WebSocket URL path and FastAPI route MATCH!{RESET}")
        print(f"{GREEN}  - TwiML path:     {path}{RESET}")
        print(f"{GREEN}  - FastAPI route:  {fastapi_route}{RESET}")
        return True
    else:
        print(f"\n{RED}✗ ERROR: TwiML WebSocket URL path and FastAPI route DO NOT MATCH!{RESET}")
        print(f"{RED}  - TwiML path:     {path}{RESET}")
        print(f"{RED}  - FastAPI route:  {fastapi_route}{RESET}")
        
        # Suggestions
        print(f"\n{YELLOW}Suggestions to fix this mismatch:{RESET}")
        print(f"{YELLOW}1. Update the WebSocket URL in voice.py to:{RESET}")
        print(f'   ws_url = f"{{ws_base_url}}{fastapi_route}".replace("<", "{{").replace(">", "}}")')
        print(f"{YELLOW}2. Or update the FastAPI route setup to match the TwiML:{RESET}")
        print(f"   a. In app/api/voice_async.py: @router.websocket('{path.replace('<', '{').replace('>', '}')}')") 
        print(f"   b. In app/api/__init__.py: Mount voice_async_router at the correct prefix.")
        
        return False

def main():
    """Main function."""
    print(f"\n{CYAN}=== WebSocket Path Alignment Verification ==={RESET}\n")
    
    # Extract the WebSocket URL from voice.py
    twiml_ws_url = extract_twiml_ws_url_from_voice_py()
    
    # Extract the FastAPI WebSocket route
    fastapi_ws_route = extract_fastapi_ws_route()
    
    # Check if they match
    success = check_path_match(twiml_ws_url, fastapi_ws_route)
    
    # Exit with status code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()