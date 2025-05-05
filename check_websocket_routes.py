#!/usr/bin/env python3
"""
Diagnose WebSocket route registration issues in the RedBarSushiAI project.

This script inspects the Flask-Sock route decorators in the codebase and checks
if they are correctly formatted according to Flask-Sock's syntax.
"""

import os
import re
import argparse
import sys

def check_file_for_websocket_routes(file_path):
    """
    Check a file for WebSocket route decorators and return any issues found.
    
    Args:
        file_path: Path to the Python file to check
        
    Returns:
        List of issues found (empty if no issues)
    """
    issues = []
    
    # Check if the file exists
    if not os.path.exists(file_path):
        issues.append(f"File not found: {file_path}")
        return issues
    
    # Read the file content
    with open(file_path, 'r') as f:
        content = f.read()
        lines = content.split('\n')
    
    # Check for incorrect @sock.route syntax
    line_num = 0
    for line in lines:
        line_num += 1
        if '@sock.route' in line and 'websocket=True' in line:
            issues.append(f"{file_path}:{line_num} - Incorrect WebSocket route syntax: {line.strip()}")
    
    # Check for incorrect WSGI middleware
    middleware_pattern = r'app\.wsgi_app\s*=\s*sock\.websocket\(app\.wsgi_app\)'
    if re.search(middleware_pattern, content):
        # Find the line number
        for i, line in enumerate(lines):
            if 'app.wsgi_app = sock.websocket(app.wsgi_app)' in line:
                issues.append(f"{file_path}:{i+1} - Incorrect WSGI middleware: {line.strip()}")
    
    return issues

def check_all_python_files(directory='.'):
    """
    Check all Python files in a directory for WebSocket route issues.
    
    Args:
        directory: Root directory to start the search
        
    Returns:
        Dictionary mapping file paths to lists of issues
    """
    all_issues = {}
    
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                issues = check_file_for_websocket_routes(file_path)
                if issues:
                    all_issues[file_path] = issues
    
    return all_issues

def fix_websocket_route_issues(file_path, backup=True):
    """
    Fix WebSocket route issues in a file.
    
    Args:
        file_path: Path to the Python file to fix
        backup: Whether to create a backup of the original file
        
    Returns:
        Dictionary with fix results
    """
    result = {
        "file": file_path,
        "backed_up": False,
        "fixed_routes": 0,
        "fixed_middleware": False,
        "issues": []
    }
    
    # Check if the file exists
    if not os.path.exists(file_path):
        result["issues"].append(f"File not found: {file_path}")
        return result
    
    # Read the file content
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Create backup if requested
    if backup:
        backup_path = f"{file_path}.bak"
        with open(backup_path, 'w') as f:
            f.write(content)
        result["backed_up"] = True
    
    # Fix @sock.route syntax
    websocket_pattern = r'@sock\.route\(([^)]+), websocket=True\)'
    matches = re.findall(websocket_pattern, content)
    result["fixed_routes"] = len(matches)
    
    if matches:
        fixed_content = re.sub(
            websocket_pattern, 
            r'@sock.route(\1)', 
            content
        )
        content = fixed_content
    
    # Fix WSGI middleware
    middleware_pattern = r'app\.wsgi_app\s*=\s*sock\.websocket\(app\.wsgi_app\)'
    if re.search(middleware_pattern, content):
        fixed_content = re.sub(
            middleware_pattern,
            r'# Removed incorrect WSGI middleware - Flask-Sock does not have a websocket() method',
            content
        )
        content = fixed_content
        result["fixed_middleware"] = True
    
    # Write the fixed content back to the file
    with open(file_path, 'w') as f:
        f.write(content)
    
    return result

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Check and fix WebSocket route issues")
    parser.add_argument("--fix", action="store_true", help="Fix issues found")
    parser.add_argument("--no-backup", action="store_true", help="Don't create backups when fixing")
    parser.add_argument("--file", help="Specific file to check/fix")
    
    args = parser.parse_args()
    
    if args.file:
        # Check a specific file
        issues = check_file_for_websocket_routes(args.file)
        
        if not issues:
            print(f"✅ No WebSocket route issues found in {args.file}")
            return 0
        
        print(f"Found {len(issues)} WebSocket route issues in {args.file}:")
        for issue in issues:
            print(f"  - {issue}")
        
        if args.fix:
            print(f"\nFixing issues in {args.file}...")
            result = fix_websocket_route_issues(args.file, not args.no_backup)
            
            if result["backed_up"]:
                print(f"  Created backup: {args.file}.bak")
            
            print(f"  Fixed {result['fixed_routes']} WebSocket route decorators")
            if result["fixed_middleware"]:
                print(f"  Fixed incorrect WSGI middleware")
            
            if not result["issues"]:
                print(f"✅ Successfully fixed all issues in {args.file}")
            else:
                print(f"❌ Some issues could not be fixed:")
                for issue in result["issues"]:
                    print(f"  - {issue}")
        
    else:
        # Check all Python files
        print("Checking all Python files for WebSocket route issues...")
        all_issues = check_all_python_files()
        
        if not all_issues:
            print("✅ No WebSocket route issues found in any files")
            return 0
        
        total_issues = sum(len(issues) for issues in all_issues.values())
        print(f"Found {total_issues} WebSocket route issues in {len(all_issues)} files:")
        
        for file_path, issues in all_issues.items():
            print(f"\n{file_path}:")
            for issue in issues:
                print(f"  - {issue}")
        
        if args.fix:
            print("\nFixing issues...")
            for file_path in all_issues:
                print(f"\nFixing {file_path}...")
                result = fix_websocket_route_issues(file_path, not args.no_backup)
                
                if result["backed_up"]:
                    print(f"  Created backup: {file_path}.bak")
                
                print(f"  Fixed {result['fixed_routes']} WebSocket route decorators")
                if result["fixed_middleware"]:
                    print(f"  Fixed incorrect WSGI middleware")
                
                if result["issues"]:
                    print(f"  Some issues could not be fixed:")
                    for issue in result["issues"]:
                        print(f"    - {issue}")
            
            print("\n✅ Fixes applied successfully!")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())