"""
OpenAI SDK compatibility layer.
This module provides compatibility between different versions of the OpenAI SDK.
"""

import logging
import importlib
import sys
from typing import Any, Dict, List, Optional, Union, Callable

logger = logging.getLogger(__name__)

# Check OpenAI SDK version to determine which imports to use
OPENAI_NEW_SDK = True

try:
    import openai
    from packaging import version
    
    # Check if openai.types exists (present in newer versions)
    if hasattr(openai, "__version__"):
        logger.info(f"Detected OpenAI SDK version: {openai.__version__}")
        if version.parse(openai.__version__) >= version.parse("1.0.0"):
            OPENAI_NEW_SDK = True
            logger.info("Using modern OpenAI SDK structure")
        else:
            OPENAI_NEW_SDK = False
            logger.info("Using legacy OpenAI SDK structure")
    else:
        # No version attribute, likely an older version
        OPENAI_NEW_SDK = False
        logger.info("OpenAI SDK version not detected, assuming legacy structure")
except (ImportError, AttributeError) as e:
    logger.warning(f"Error detecting OpenAI SDK version: {str(e)}")
    OPENAI_NEW_SDK = False

# Import the appropriate Tool and tool decorator
# If imports fail, provide fallback implementations
try:
    if OPENAI_NEW_SDK:
        # New SDK structure (1.0.0+)
        from openai.types.agent import Tool
        from openai import tool
    else:
        # Legacy SDK structure
        # First try the internal tool module
        try:
            from openai import tool
            # Create a Tool class to match the new SDK interface
            Tool = type('Tool', (), {'function': None, 'parameters': None, 'description': None})
        except ImportError:
            logger.warning("Could not import 'tool' from openai, using compatibility implementation")
            # Create our own compatible tool decorator
            def tool(*args, **kwargs):
                def decorator(func):
                    # Just return the function unchanged
                    return func
                if len(args) == 1 and callable(args[0]):
                    return decorator(args[0])
                return decorator
            
            # Create a Tool class to match the new SDK interface
            Tool = type('Tool', (), {'function': None, 'parameters': None, 'description': None})
except Exception as e:
    logger.error(f"Error importing OpenAI SDK Tool components: {str(e)}")
    logger.warning("Using fallback implementations for Tool and tool decorator")
    
    # Fallback implementations
    def tool(*args, **kwargs):
        def decorator(func):
            # Just return the function unchanged
            return func
        if len(args) == 1 and callable(args[0]):
            return decorator(args[0])
        return decorator
    
    # Create a Tool class to match the new SDK interface
    Tool = type('Tool', (), {'function': None, 'parameters': None, 'description': None})

# Export the right versions
__all__ = ['Tool', 'tool', 'OPENAI_NEW_SDK']