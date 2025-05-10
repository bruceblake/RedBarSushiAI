#!/usr/bin/env python3
"""
Script to fix direct imports from app.config to use settings object.
This addresses the ImportError issues seen during Render deployment.
"""

import os
import re
import logging
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def find_files_with_direct_imports(directory):
    """Find all Python files with direct imports from app.config."""
    direct_import_pattern = re.compile(r'from\s+app\.config\s+import\s+(?!settings)([^,]+(?:,\s*[^,]+)*)')
    
    files_with_imports = {}
    
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        matches = direct_import_pattern.findall(content)
                        if matches:
                            # Extract all imported variable names
                            imported_vars = []
                            for match in matches:
                                imported_vars.extend([var.strip() for var in match.split(',')])
                            
                            if imported_vars:
                                files_with_imports[file_path] = imported_vars
                except Exception as e:
                    logger.error(f"Error reading {file_path}: {e}")
    
    return files_with_imports

def fix_imports(file_path, imported_vars):
    """Fix direct imports to use settings object."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace direct import with settings import
        for import_block in re.findall(r'from\s+app\.config\s+import\s+(?!settings)([^,]+(?:,\s*[^,]+)*)', content):
            old_import = f"from app.config import {import_block}"
            # Check if 'settings' is already imported
            if 'from app.config import settings' in content:
                # If yes, just remove the direct import
                content = content.replace(old_import, '')
            else:
                # If not, replace with settings import
                content = content.replace(old_import, 'from app.config import settings')
        
        # Replace direct variable usage with settings.variable
        for var in imported_vars:
            var = var.strip()
            # Use word boundary to avoid partial matches
            pattern = r'\b' + re.escape(var) + r'\b'
            # Only replace when it's used as a variable (not part of string, comment, etc.)
            content = re.sub(pattern, f'settings.{var}', content)
        
        # Write the modified content back to the file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"Fixed imports in {file_path}")
        return True
    except Exception as e:
        logger.error(f"Error fixing {file_path}: {e}")
        return False

def main():
    if len(sys.argv) > 1:
        app_dir = sys.argv[1]
    else:
        app_dir = 'app'
    
    logger.info(f"Scanning {app_dir} for direct imports from app.config...")
    files_with_imports = find_files_with_direct_imports(app_dir)
    
    if not files_with_imports:
        logger.info("No files with direct imports found.")
        return
    
    logger.info(f"Found {len(files_with_imports)} files with direct imports.")
    
    fixed_count = 0
    for file_path, imported_vars in files_with_imports.items():
        logger.info(f"Processing {file_path} ({', '.join(imported_vars)})")
        if fix_imports(file_path, imported_vars):
            fixed_count += 1
    
    logger.info(f"Fixed imports in {fixed_count} out of {len(files_with_imports)} files.")

if __name__ == "__main__":
    main()