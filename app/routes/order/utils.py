"""
Utility functions for order routes.
This module provides common utilities used across order routes.
"""

import os
import json
import time
import logging
import re
from datetime import datetime
from flask import session
from typing import List, Dict, Any, Optional, Tuple

from app.utils.order_utils import (
    build_order_description,
    calculate_bill_amount,
    dtmf_yes_no,
    user_said_yes,
    user_said_no,
    validate_modifiers,
)

# Configure logger
logger = logging.getLogger(__name__)

# Helper function to get recent log entries
def get_last_log_lines(num_lines=20) -> List[str]:
    """
    Get the last N lines from the log file.
    
    Args:
        num_lines: Number of lines to retrieve
        
    Returns:
        List of log lines
    """
    # Create an empty list for lines
    lines = []
    try:
        # First try reading from a standard log location
        log_paths = [
            "/app/progress.log",  # Docker container location
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                "progress.log",
            ),  # Project root
            "/var/log/app.log",  # Common Linux log location
            "app.log",  # Local directory
        ]

        # Try each possible log path
        for log_path in log_paths:
            if os.path.exists(log_path):
                with open(log_path, "r") as f:
                    # Read all lines and get the last N
                    all_lines = f.readlines()
                    lines = (
                        all_lines[-num_lines:]
                        if len(all_lines) >= num_lines
                        else all_lines
                    )
                break

        # If no log file found, try getting the log from the logging module's handlers
        if not lines:
            root_logger = logging.getLogger()
            for handler in root_logger.handlers:
                if hasattr(handler, "baseFilename"):
                    with open(handler.baseFilename, "r") as f:
                        all_lines = f.readlines()
                        lines = (
                            all_lines[-num_lines:]
                            if len(all_lines) >= num_lines
                            else all_lines
                        )
                    break
    except Exception as e:
        # If we can't read the log file, return an empty list
        logging.warning(f"Could not read log file: {e}")
        return []

    return lines

# Function to check if we can process an action (throttling/cooldown)
def can_process_action(sender: str, action_key: str, cooldown: int = 30) -> bool:
    """
    Check if an action can be processed based on cooldown/throttling.
    
    Args:
        sender: Identifier for who's performing the action
        action_key: The action being performed
        cooldown: Cooldown period in seconds
        
    Returns:
        True if action can be processed, False otherwise
    """
    # Create a composite key for this specific action
    key = f"{sender}:{action_key}"
    
    # Get the current time
    now = time.time()
    
    # Get the last time this action was performed
    last_time = session.get(f"last_action_{key}", 0)
    
    # Check if enough time has passed
    if now - last_time < cooldown:
        logger.info(f"Action {action_key} is on cooldown for {sender}")
        return False
    
    # Update the last action time
    session[f"last_action_{key}"] = now
    return True

# Export all functions
__all__ = ['get_last_log_lines', 'can_process_action']