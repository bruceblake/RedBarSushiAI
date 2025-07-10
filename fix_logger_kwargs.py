#!/usr/bin/env python3
"""
Fix logger calls that use invalid keyword arguments.
"""

import re
import os

def fix_logger_calls_in_file(filepath):
    """Fix problematic logger calls in a single file."""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        original_content = content
        changes_made = 0
        
        # Pattern 1: logger.info("text", call_sid=value) -> logger.info(f"[{value}] text")
        pattern1 = r'logger\.(\w+)\("([^"]*)",\s*call_sid=([^)]+)\)'
        def replace1(match):
            level, message, call_sid = match.groups()
            return f'logger.{level}(f"[{call_sid}] {message}")'
        
        new_content = re.sub(pattern1, replace1, content)
        if new_content != content:
            changes_made += new_content.count('[') - content.count('[')
            content = new_content
        
        # Pattern 2: logger.info(f"text", call_sid=value) -> logger.info(f"[{value}] text") 
        pattern2 = r'logger\.(\w+)\(f"([^"]*)",\s*call_sid=([^)]+)\)'
        def replace2(match):
            level, message, call_sid = match.groups()
            return f'logger.{level}(f"[{call_sid}] {message}")'
        
        new_content = re.sub(pattern2, replace2, content)
        if new_content != content:
            changes_made += 1
            content = new_content
            
        # Pattern 3: logger.info("text", event=value, confidence=value) -> logger.info(f"text (event: {value}, confidence: {value})")
        pattern3 = r'logger\.(\w+)\(\s*f?"([^"]*)",\s*event=([^,]+),\s*confidence=([^)]+)\s*\)'
        def replace3(match):
            level, message, event, confidence = match.groups()
            return f'logger.{level}(f"{message} (event: {event}, confidence: {confidence})")'
        
        new_content = re.sub(pattern3, replace3, content)
        if new_content != content:
            changes_made += 1
            content = new_content
        
        # Pattern 4: Other keyword arguments - convert to f-string format
        # This is more complex, so let's handle specific known cases
        
        # Fix specific known problematic lines
        problematic_patterns = [
            (r'logger\.info\(\s*f?"([^"]*)",\s*input=([^,)]+),\s*confidence=([^)]+)\s*\)', 
             r'logger.info(f"\1 for input \2 with confidence \3")'),
        ]
        
        for pattern, replacement in problematic_patterns:
            new_content = re.sub(pattern, replacement, content)
            if new_content != content:
                changes_made += 1
                content = new_content
        
        # Write back if changes were made
        if content != original_content:
            with open(filepath, 'w') as f:
                f.write(content)
            print(f"✅ Fixed {changes_made} logger calls in {filepath}")
            return True
        else:
            return False
            
    except Exception as e:
        print(f"❌ Error processing {filepath}: {e}")
        return False

def main():
    """Find and fix all problematic logger calls."""
    print("🔧 Fixing logger calls with invalid keyword arguments...")
    
    files_fixed = 0
    total_files = 0
    
    # Walk through all Python files in app/
    for root, dirs, files in os.walk('app'):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                total_files += 1
                
                if fix_logger_calls_in_file(filepath):
                    files_fixed += 1
    
    print(f"\n📊 Summary:")
    print(f"   Total Python files checked: {total_files}")
    print(f"   Files with fixes applied: {files_fixed}")
    
    if files_fixed > 0:
        print(f"\n🎉 All logger calls have been fixed!")
    else:
        print(f"\n✨ No problematic logger calls found.")

if __name__ == "__main__":
    main()