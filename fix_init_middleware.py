#!/usr/bin/env python3
"""
This script fixes the WebSocket WSGI middleware issue in app/__init__.py.

The issue:
- The line 'app.wsgi_app = sock.websocket(app.wsgi_app)' was added to app/__init__.py
- Flask-Sock does not have a 'websocket' method, causing an AttributeError
- This error prevents the application from starting properly

The fix:
- Remove the problematic line from app/__init__.py
- This allows the application to start without errors
"""

import os
import re
import sys

# Define the file to be fixed
INIT_FILE = 'app/__init__.py'

def remove_middleware_line():
    """
    Remove the problematic WSGI middleware line from app/__init__.py.
    """
    # Check if the file exists
    if not os.path.exists(INIT_FILE):
        print(f"Error: {INIT_FILE} does not exist")
        return False
    
    # Read the file content
    with open(INIT_FILE, 'r') as f:
        content = f.read()
        lines = content.split('\n')
    
    # Check if the problematic line exists
    middleware_line = "app.wsgi_app = sock.websocket(app.wsgi_app)"
    if middleware_line not in content:
        print(f"The problematic line '{middleware_line}' was not found in {INIT_FILE}")
        print("The file may have already been fixed or might be a different version.")
        return True
    
    # Create a backup of the original file
    backup_file = f"{INIT_FILE}.bak"
    with open(backup_file, 'w') as f:
        f.write(content)
    print(f"Created backup of original file at {backup_file}")
    
    # Remove the problematic line and add a comment
    fixed_content = []
    for line in lines:
        if line.strip() == middleware_line:
            fixed_content.append("    # Removed problematic line: sock.websocket() method doesn't exist in Flask-Sock")
            print(f"Found and removed the problematic line at {INIT_FILE}:{lines.index(line) + 1}")
        else:
            fixed_content.append(line)
    
    # Write the fixed content back to the file
    with open(INIT_FILE, 'w') as f:
        f.write('\n'.join(fixed_content))
    
    print(f"Successfully fixed {INIT_FILE}")
    return True

if __name__ == "__main__":
    print("Fixing WebSocket WSGI middleware issue in app/__init__.py...")
    
    if remove_middleware_line():
        print("\nNext steps:")
        print("1. Commit the changes: git add app/__init__.py && git commit -m 'Fix WebSocket WSGI middleware'")
        print("2. Push the changes to staging: git push origin staging")
        print("3. Verify the application starts correctly in the staging environment")
        sys.exit(0)
    else:
        print("\nFailed to fix the issue. Please check the errors above.")
        sys.exit(1)