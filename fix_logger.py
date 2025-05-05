#!/usr/bin/env python
"""
Fix logger initialization issues in RedBarSushiAI application.
"""

import os
import sys
import re
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger("logger_fix")

def fix_app_init():
    """Fix logger initialization in app/__init__.py."""
    init_file = "/app/app/__init__.py"
    if not os.path.exists(init_file):
        # Try local path
        init_file = "app/__init__.py"
        if not os.path.exists(init_file):
            logger.error(f"Cannot find app/__init__.py file")
            return False
    
    try:
        # Read the file
        with open(init_file, "r") as f:
            content = f.read()
        
        # Look for the logger initialization issue
        if "logger.info(f\"Configuring voice handler: {VOICE_HANDLER}\")" in content:
            logger.info(f"Found logger issue in {init_file}")
            
            # Replace the problematic line with proper initialization
            new_content = content.replace(
                "logger.info(f\"Configuring voice handler: {VOICE_HANDLER}\")",
                "app_logger = logging.getLogger(__name__)\n    app_logger.info(f\"Configuring voice handler: {VOICE_HANDLER}\")"
            )
            
            # Update other logger references in that section
            new_content = new_content.replace("logger.info(\"Voice handler set to ORCHESTRATED", "app_logger.info(\"Voice handler set to ORCHESTRATED")
            new_content = new_content.replace("logger.info(\"Voice handler set to STANDARD", "app_logger.info(\"Voice handler set to STANDARD")
            
            # Write the fixed content
            with open(init_file, "w") as f:
                f.write(new_content)
            
            logger.info(f"✅ Successfully fixed logger initialization in {init_file}")
            return True
        else:
            logger.info(f"No logger issue found in {init_file} (already fixed or different version)")
            return True
    except Exception as e:
        logger.error(f"Error fixing logger initialization: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("Starting logger initialization fix")
    success = fix_app_init()
    logger.info(f"Logger fix {'completed successfully' if success else 'failed'}")
    sys.exit(0 if success else 1)