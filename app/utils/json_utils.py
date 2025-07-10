"""
JSON utility functions for the RedBarSushiAI application.

This module provides safe JSON serialization functions that handle 
Decimal types and other non-standard JSON types.
"""

import json
from decimal import Decimal
from typing import Any


def safe_json_dumps(obj: Any, **kwargs) -> str:
    """
    JSON dumps with Decimal support.
    
    Args:
        obj: Object to serialize
        **kwargs: Additional arguments to pass to json.dumps
        
    Returns:
        JSON string representation of the object
    """
    def decimal_default(o):
        if isinstance(o, Decimal):
            return float(o)
        raise TypeError(f'Object of type {o.__class__.__name__} is not JSON serializable')
    
    return json.dumps(obj, default=decimal_default, **kwargs)


def safe_json_loads(json_str: str, **kwargs) -> Any:
    """
    JSON loads with error handling.
    
    Args:
        json_str: JSON string to parse
        **kwargs: Additional arguments to pass to json.loads
        
    Returns:
        Parsed object
    """
    return json.loads(json_str, **kwargs)