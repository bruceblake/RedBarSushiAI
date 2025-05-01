"""
JSON utility functions for handling JSON data.
"""

import json
import logging
import os
import shutil

logger = logging.getLogger(__name__)

def safe_load_json(file_path, default=None):
    """
    Safely load JSON from a file, with fallback and backup mechanisms.
    
    Args:
        file_path: Path to the JSON file
        default: Default value to return if loading fails
        
    Returns:
        The loaded JSON data, or the default value if loading fails
    """
    if not os.path.exists(file_path):
        logger.error(f"JSON file not found: {file_path}")
        return default
        
    # Create a backup before trying to load
    try:
        backup_path = f"{file_path}.bak"
        shutil.copy2(file_path, backup_path)
        logger.info(f"Created backup of JSON file at {backup_path}")
    except Exception as e:
        logger.warning(f"Failed to create backup of JSON file: {e}")
    
    # Try to load the file
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        return data
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON file {file_path}: {e}")
        
        # Try to repair the JSON file
        try:
            logger.info(f"Attempting to repair JSON file {file_path}")
            with open(file_path, 'r') as f:
                content = f.read()
                
            # Some basic repair strategies
            # 1. Check for missing closing braces
            open_braces = content.count('{')
            close_braces = content.count('}')
            if open_braces > close_braces:
                content += '}' * (open_braces - close_braces)
                
            # 2. Check for missing closing brackets
            open_brackets = content.count('[')
            close_brackets = content.count(']')
            if open_brackets > close_brackets:
                content += ']' * (open_brackets - close_brackets)
                
            # Try to parse the repaired content
            data = json.loads(content)
            
            # If successful, save the repaired content
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
                
            logger.info(f"Successfully repaired JSON file {file_path}")
            return data
        except Exception as repair_e:
            logger.error(f"Failed to repair JSON file: {repair_e}")
            
            # Try to restore from backup
            try:
                if os.path.exists(backup_path):
                    logger.info(f"Restoring from backup: {backup_path}")
                    with open(backup_path, 'r') as f:
                        data = json.load(f)
                    return data
            except Exception as restore_e:
                logger.error(f"Failed to restore from backup: {restore_e}")
        
        # If all else fails, return the default
        return default
    except Exception as e:
        logger.error(f"Error loading JSON file {file_path}: {e}")
        return default
        
def safe_write_json(file_path, data):
    """
    Safely write JSON data to a file.
    
    Args:
        file_path: Path to the JSON file
        data: Data to write
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Create parent directory if it doesn't exist
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # Create a backup of the existing file if it exists
    if os.path.exists(file_path):
        try:
            backup_path = f"{file_path}.bak"
            shutil.copy2(file_path, backup_path)
        except Exception as e:
            logger.warning(f"Failed to create backup of JSON file: {e}")
    
    # Write to a temporary file first
    temp_path = f"{file_path}.tmp"
    try:
        with open(temp_path, 'w') as f:
            json.dump(data, f, indent=2)
            
        # Verify that the file was written correctly
        with open(temp_path, 'r') as f:
            json.load(f)
            
        # Move the temporary file to the target path
        os.replace(temp_path, file_path)
        return True
    except Exception as e:
        logger.error(f"Error writing JSON file {file_path}: {e}")
        # Clean up temporary file if it exists
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
        return False