"""
Import tracking utility for RedBarSushiAI.
This module provides tools to track and log import attempts and successes.
"""

import sys
import logging
import time
import threading
import traceback
from functools import wraps
from typing import Dict, List, Set, Optional, Callable, Any, Tuple

# Configure logger
logger = logging.getLogger(__name__)

# Global registry of tracked modules
_tracked_modules: Dict[str, Dict[str, Any]] = {}
_import_attempts: Dict[str, List[Tuple[float, bool, Optional[str]]]] = {}
_import_lock = threading.RLock()
_initialized_modules: Set[str] = set()
_circular_imports_detected: Set[Tuple[str, str]] = set()

# Current import stack for detecting circular imports
_current_import_stack: List[str] = []


def track_import(module_name: str) -> Callable:
    """
    Decorator to track imports and initialization of modules.
    
    Args:
        module_name: Full name of the module being tracked
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            global _tracked_modules, _import_attempts, _current_import_stack
            
            # Record import attempt
            timestamp = time.time()
            
            with _import_lock:
                # Check for circular imports
                if module_name in _current_import_stack:
                    source_module = _current_import_stack[-1] if _current_import_stack else "unknown"
                    circular_path = " -> ".join(_current_import_stack + [module_name])
                    circular_import = (source_module, module_name)
                    
                    if circular_import not in _circular_imports_detected:
                        _circular_imports_detected.add(circular_import)
                        logger.warning(f"Circular import detected: {circular_path}")
                
                _current_import_stack.append(module_name)
                
                if module_name not in _import_attempts:
                    _import_attempts[module_name] = []
            
            success = False
            error_message = None
            
            try:
                # Call the original import or initialization function
                result = func(*args, **kwargs)
                success = True
                
                with _import_lock:
                    _tracked_modules[module_name] = {
                        "timestamp": timestamp,
                        "success": True,
                        "initialized": True
                    }
                    _initialized_modules.add(module_name)
                
                logger.info(f"Successfully imported and initialized module: {module_name}")
                return result
                
            except Exception as e:
                error_message = str(e)
                error_stack = traceback.format_exc()
                
                with _import_lock:
                    _tracked_modules[module_name] = {
                        "timestamp": timestamp,
                        "success": False,
                        "error": error_message,
                        "stack_trace": error_stack
                    }
                
                logger.error(f"Failed to import module {module_name}: {error_message}\n{error_stack}")
                raise
                
            finally:
                with _import_lock:
                    _import_attempts[module_name].append((timestamp, success, error_message))
                    
                    if _current_import_stack and _current_import_stack[-1] == module_name:
                        _current_import_stack.pop()
        
        return wrapper
    
    return decorator


def safe_import(module_name: str, retry: bool = False, max_retries: int = 3) -> Optional[Any]:
    """
    Safely import a module, with optional retry logic.
    
    Args:
        module_name: Name of the module to import
        retry: Whether to retry failed imports
        max_retries: Maximum number of retries
        
    Returns:
        The imported module or None if import failed
    """
    attempts = 0
    last_error = None
    
    while attempts <= max_retries:
        try:
            if '.' in module_name:
                # For submodules, import the parent first
                parts = module_name.split('.')
                # Import the parent module
                parent = __import__('.'.join(parts[:-1]), fromlist=[parts[-1]])
                # Then get the child attribute
                module = getattr(parent, parts[-1])
            else:
                # Simple import
                module = __import__(module_name)
            
            with _import_lock:
                timestamp = time.time()
                _tracked_modules[module_name] = {
                    "timestamp": timestamp,
                    "success": True,
                    "initialized": True
                }
                _initialized_modules.add(module_name)
                
                if module_name not in _import_attempts:
                    _import_attempts[module_name] = []
                _import_attempts[module_name].append((timestamp, True, None))
            
            logger.info(f"Successfully imported module: {module_name}")
            return module
            
        except ImportError as e:
            last_error = str(e)
            
            with _import_lock:
                timestamp = time.time()
                if module_name not in _import_attempts:
                    _import_attempts[module_name] = []
                _import_attempts[module_name].append((timestamp, False, last_error))
            
            if not retry or attempts >= max_retries:
                logger.warning(f"Failed to import module {module_name} (attempt {attempts+1}/{max_retries+1}): {last_error}")
                break
                
            # Wait before retrying (exponential backoff)
            time.sleep(0.1 * (2 ** attempts))
            attempts += 1
            
    # Final recording of failure if we've exhausted retries
    with _import_lock:
        _tracked_modules[module_name] = {
            "timestamp": time.time(),
            "success": False,
            "error": last_error,
            "attempts": attempts + 1
        }
    
    if retry and attempts > 0:
        logger.error(f"Failed to import module {module_name} after {attempts+1} attempts: {last_error}")
    
    return None


def mark_initialized(module_name: str) -> None:
    """
    Mark a module as successfully initialized.
    
    Args:
        module_name: Name of the module
    """
    with _import_lock:
        timestamp = time.time()
        _tracked_modules[module_name] = {
            "timestamp": timestamp,
            "success": True,
            "initialized": True
        }
        _initialized_modules.add(module_name)
        
        if module_name not in _import_attempts:
            _import_attempts[module_name] = []
        _import_attempts[module_name].append((timestamp, True, None))
    
    logger.info(f"Module marked as initialized: {module_name}")


def mark_initialization_failed(module_name: str, error: Exception) -> None:
    """
    Mark a module as failed to initialize.
    
    Args:
        module_name: Name of the module
        error: The exception that caused the failure
    """
    error_message = str(error)
    error_stack = traceback.format_exc()
    
    with _import_lock:
        timestamp = time.time()
        _tracked_modules[module_name] = {
            "timestamp": timestamp,
            "success": False,
            "initialized": False,
            "error": error_message,
            "stack_trace": error_stack
        }
        
        if module_name not in _import_attempts:
            _import_attempts[module_name] = []
        _import_attempts[module_name].append((timestamp, False, error_message))
    
    logger.error(f"Module initialization failed: {module_name} - {error_message}\n{error_stack}")


def get_import_status() -> Dict[str, Any]:
    """
    Get the current status of all tracked imports.
    
    Returns:
        Dictionary with import status information
    """
    with _import_lock:
        return {
            "tracked_modules": dict(_tracked_modules),
            "initialized_modules": list(_initialized_modules),
            "circular_imports": list(_circular_imports_detected),
            "import_attempts": dict(_import_attempts),
            "current_import_stack": list(_current_import_stack)
        }


def get_failed_imports() -> Dict[str, Dict[str, Any]]:
    """
    Get a list of all failed imports.
    
    Returns:
        Dictionary of failed modules and their error information
    """
    with _import_lock:
        return {
            name: info for name, info in _tracked_modules.items() 
            if not info.get("success", False)
        }


def get_circular_imports() -> List[Tuple[str, str]]:
    """
    Get a list of all detected circular imports.
    
    Returns:
        List of (source_module, target_module) pairs
    """
    with _import_lock:
        return list(_circular_imports_detected)


def install_import_tracker() -> None:
    """
    Install a global import hook to track all imports.
    Warning: This is an advanced feature that modifies Python's import system.
    """
    original_import = __builtins__['__import__']
    
    def import_hook(name, *args, **kwargs):
        timestamp = time.time()
        success = False
        error_message = None
        
        try:
            with _import_lock:
                if name not in _import_attempts:
                    _import_attempts[name] = []
                    
                # Check for circular imports
                if name in _current_import_stack:
                    source_module = _current_import_stack[-1] if _current_import_stack else "unknown"
                    circular_path = " -> ".join(_current_import_stack + [name])
                    circular_import = (source_module, name)
                    
                    if circular_import not in _circular_imports_detected:
                        _circular_imports_detected.add(circular_import)
                        logger.warning(f"Circular import detected via hook: {circular_path}")
                
                _current_import_stack.append(name)
            
            module = original_import(name, *args, **kwargs)
            success = True
            
            with _import_lock:
                _tracked_modules[name] = {
                    "timestamp": timestamp,
                    "success": True,
                    "initialized": True
                }
                
            return module
            
        except Exception as e:
            error_message = str(e)
            error_stack = traceback.format_exc()
            
            with _import_lock:
                _tracked_modules[name] = {
                    "timestamp": timestamp,
                    "success": False,
                    "error": error_message,
                    "stack_trace": error_stack
                }
            
            logger.debug(f"Import hook - failed to import {name}: {error_message}")
            raise
            
        finally:
            with _import_lock:
                _import_attempts[name].append((timestamp, success, error_message))
                
                if _current_import_stack and _current_import_stack[-1] == name:
                    _current_import_stack.pop()
    
    # Replace the built-in __import__ function
    __builtins__['__import__'] = import_hook
    logger.info("Installed global import tracker")


# Initialize logging for this module
def setup_import_logging():
    """Configure logging specifically for import tracking."""
    logger.setLevel(logging.DEBUG)
    
    # Create console handler if not already present
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        
        # Add the handler to the logger
        logger.addHandler(console_handler)
        
        # Also try to add a file handler for import debugging
        try:
            import_log_file = "import_debug.log"
            file_handler = logging.FileHandler(import_log_file)
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            logger.info(f"Import debug logging enabled to {import_log_file}")
        except Exception as e:
            logger.warning(f"Could not create file handler for import logging: {e}")

# Set up logging when this module is imported
setup_import_logging()