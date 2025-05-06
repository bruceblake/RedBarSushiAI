#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test watcher script for RedBarSushiAI.

This script monitors specified directories for file changes and runs tests when changes are detected.
It supports running MCP-related tests, specific test categories (e.g., e2e, voice), or all tests.

Example usage:
    python scripts/watch_tests.py --mcp
    python scripts/watch_tests.py --category e2e
    python scripts/watch_tests.py --file tests/e2e/test_voice_flow.py
    python scripts/watch_tests.py --all
"""

import os
import sys
import time
import argparse
import subprocess
import json
from typing import Dict, List, Optional, Set, Tuple, Union
from datetime import datetime
from pathlib import Path

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import local MCP config if available (for MCP testing)
try:
    from tests.config.local_mcp_config import MCP_SERVER_URL, TestType
except ImportError:
    MCP_SERVER_URL = "http://localhost:4000/mcp"
    # Define fallback TestType if import fails
    class TestType:
        BASIC = "basic"
        DATABASE = "database"
        REDIS = "redis"
        MENU = "menu"
        ORDER = "order"
        ALL = "all"

# Configuration
DEFAULT_WATCH_DIRS = [
    "app/",
    "tests/",
    "mcp/",
]

# File patterns to ignore
IGNORE_PATTERNS = [
    "__pycache__/",
    ".pyc",
    ".pyo",
    ".swp",
    ".git/",
    ".pytest_cache/",
    "node_modules/",
    "venv/",
]

# ANSI color codes for terminal output
COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
}

def color_text(text: str, color: str) -> str:
    """Format text with ANSI color"""
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"

def get_file_times(dirs: List[str], ignore_patterns: List[str]) -> Dict[str, float]:
    """Get the modification times of all files in the given directories"""
    file_times = {}
    
    for directory in dirs:
        for root, _, files in os.walk(directory):
            # Skip directories that match ignore patterns
            if any(ignore in root for ignore in ignore_patterns):
                continue
                
            for file in files:
                # Skip files that match ignore patterns
                if any(ignore in file for ignore in ignore_patterns):
                    continue
                    
                file_path = os.path.join(root, file)
                try:
                    file_times[file_path] = os.path.getmtime(file_path)
                except (FileNotFoundError, PermissionError):
                    # Skip files that can't be accessed
                    pass
    
    return file_times

def print_header(text: str) -> None:
    """Print a formatted header"""
    terminal_width = os.get_terminal_size().columns
    padding = max(0, terminal_width - len(text) - 4)
    print("\n" + "=" * terminal_width)
    print(f"= {color_text(text, 'bold')} {' ' * padding}=")
    print("=" * terminal_width)

def run_tests(test_type: str, category: Optional[str] = None, file: Optional[str] = None) -> bool:
    """Run the specified tests and return True if all tests passed"""
    print_header(f"Running tests: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if test_type == "mcp":
        # Run MCP tests
        print(color_text("Running MCP tests...", "cyan"))
        command = ["python", "tests/mcp/test_local_mcp.py"]
        result = subprocess.run(command, capture_output=True, text=True)
        
        # Print output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(color_text(result.stderr, "red"))
            
        success = result.returncode == 0
        
    elif test_type == "category" and category:
        # Run tests by category (using pytest markers)
        print(color_text(f"Running {category} tests...", "cyan"))
        command = ["pytest", "-v", "-m", category]
        result = subprocess.run(command, capture_output=True, text=True)
        
        # Print output
        if result.stdout:
            print(result.stdout)
        if result.stderr and "No tests ran" not in result.stderr:
            print(color_text(result.stderr, "red"))
        
        success = result.returncode == 0
        
    elif test_type == "file" and file:
        # Run specific test file
        print(color_text(f"Running file: {file}", "cyan"))
        command = ["pytest", "-v", file]
        result = subprocess.run(command, capture_output=True, text=True)
        
        # Print output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(color_text(result.stderr, "red"))
            
        success = result.returncode == 0
        
    elif test_type == "all":
        # Run all tests
        print(color_text("Running all tests...", "cyan"))
        command = ["pytest", "-v"]
        result = subprocess.run(command, capture_output=True, text=True)
        
        # Print output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(color_text(result.stderr, "red"))
            
        success = result.returncode == 0
        
    else:
        print(color_text("Invalid test type or missing arguments", "red"))
        return False
    
    # Print result
    if success:
        print(color_text("✅ Tests passed!", "green"))
    else:
        print(color_text("❌ Tests failed!", "red"))
    
    return success

def call_mcp_method(method: str, params: Optional[Dict] = None) -> Dict:
    """Call a method on the MCP server using JSON-RPC"""
    import requests
    
    if params is None:
        params = {}
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(MCP_SERVER_URL, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": {"code": -1, "message": str(e)}}

def run_mcp_test(test_type: str = TestType.BASIC) -> bool:
    """Run a test through the MCP server"""
    print_header(f"Running MCP test: {test_type} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        response = call_mcp_method("tool/call", {
            "name": "run_test",
            "arguments": {
                "test_type": test_type
            }
        })
        
        if "result" in response and "content" in response["result"]:
            content = response["result"]["content"]
            for item in content:
                if item.get("type") == "text":
                    print(item["text"])
            
            success = response["result"].get("success", False)
            
            if success:
                print(color_text("✅ MCP test passed!", "green"))
            else:
                print(color_text("❌ MCP test failed!", "red"))
                
            return success
        else:
            print(color_text("Invalid response from MCP server", "red"))
            if "error" in response:
                print(color_text(f"Error: {response['error'].get('message', 'Unknown error')}", "red"))
            return False
            
    except Exception as e:
        print(color_text(f"Error running MCP test: {str(e)}", "red"))
        return False

def watch_for_changes(args: argparse.Namespace) -> None:
    """Watch for file changes and run tests when changes are detected"""
    dirs_to_watch = DEFAULT_WATCH_DIRS
    
    print_header("RedBarSushiAI Test Watcher")
    
    # Get initial file modification times
    file_times = get_file_times(dirs_to_watch, IGNORE_PATTERNS)
    
    print(color_text(f"Watching {len(file_times)} files in {len(dirs_to_watch)} directories", "cyan"))
    print(color_text("Press Ctrl+C to stop", "cyan"))
    
    # Run tests once at startup if requested
    if args.initial:
        if args.mcp:
            if args.mcp_test_type:
                run_mcp_test(args.mcp_test_type)
            else:
                run_tests("mcp")
        elif args.category:
            run_tests("category", args.category)
        elif args.file:
            run_tests("file", file=args.file)
        elif args.all:
            run_tests("all")
    
    try:
        while True:
            # Check for file changes
            new_file_times = get_file_times(dirs_to_watch, IGNORE_PATTERNS)
            
            # Check for modified, added, or removed files
            changed_files = []
            for file_path, mtime in new_file_times.items():
                if file_path not in file_times or mtime > file_times[file_path]:
                    changed_files.append(file_path)
            
            # Removed files
            for file_path in file_times:
                if file_path not in new_file_times:
                    changed_files.append(file_path)
            
            # If files changed, run tests
            if changed_files:
                changed_file_count = len(changed_files)
                if changed_file_count <= 5:  # Only list if not too many
                    print(color_text(f"Detected changes in {changed_file_count} files:", "yellow"))
                    for file_path in changed_files[:5]:
                        print(f"  - {file_path}")
                    if changed_file_count > 5:
                        print(f"  - ...and {changed_file_count - 5} more")
                else:
                    print(color_text(f"Detected changes in {changed_file_count} files", "yellow"))
                
                # Wait a short time to ensure all file operations complete
                time.sleep(0.5)
                
                # Run the appropriate tests
                if args.mcp:
                    if args.mcp_test_type:
                        run_mcp_test(args.mcp_test_type)
                    else:
                        run_tests("mcp")
                elif args.category:
                    run_tests("category", args.category)
                elif args.file:
                    run_tests("file", file=args.file)
                elif args.all:
                    run_tests("all")
                
                # Update file times
                file_times = new_file_times
            
            # Sleep before checking again
            time.sleep(args.interval)
            
    except KeyboardInterrupt:
        print_header("Test Watcher Stopped")
        sys.exit(0)

def main() -> None:
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Watch for file changes and run tests")
    
    test_group = parser.add_mutually_exclusive_group(required=True)
    test_group.add_argument("--mcp", action="store_true", help="Run MCP tests")
    test_group.add_argument("--category", type=str, help="Run tests by category (e.g., e2e, voice, menu)")
    test_group.add_argument("--file", type=str, help="Run a specific test file")
    test_group.add_argument("--all", action="store_true", help="Run all tests")
    
    parser.add_argument("--mcp-test-type", type=str, 
                      help=f"MCP test type to run. Options: {', '.join([getattr(TestType, attr) for attr in dir(TestType) if not attr.startswith('_')])}")
    parser.add_argument("--interval", type=float, default=1.0, 
                      help="Interval in seconds between file checks (default: 1.0)")
    parser.add_argument("--initial", action="store_true", 
                      help="Run tests immediately on startup")
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.mcp_test_type and not args.mcp:
        parser.error("--mcp-test-type can only be used with --mcp")
    
    # Start watching for file changes
    watch_for_changes(args)

if __name__ == "__main__":
    main()