#!/usr/bin/env python3
"""
Common error handling utilities to reduce code duplication.
"""

import logging
import functools
from typing import Optional, Callable, Any

logger = logging.getLogger(__name__)

def safe_execute(operation_name: str, default_return: Any = None, 
                 reraise: Optional[type] = None, ui_message: str = None):
    """
    Decorator for standardized error handling.
    
    Args:
        operation_name: Description of what operation is being performed
        default_return: What to return on error (default: None)
        reraise: Exception type to reraise (e.g., GameEngineError)
        ui_message: Optional message to show to user via UI
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in {operation_name}: {e}")
                
                # If we have a UI reference and message, show it to user
                if ui_message and len(args) > 0 and hasattr(args[0], 'ui'):
                    try:
                        args[0].ui.update_output(f"Error: {ui_message}")
                    except:
                        pass  # Don't fail if UI update fails
                
                # Re-raise as specified exception type
                if reraise:
                    raise reraise(f"Failed to {operation_name.lower()}: {e}")
                
                return default_return
                
        return wrapper
    return decorator

def log_and_continue(operation_name: str, default_return: Any = None):
    """
    Decorator that logs errors but continues execution.
    Useful for non-critical operations.
    """
    return safe_execute(operation_name, default_return=default_return)

def log_and_reraise(operation_name: str, exception_type: type):
    """
    Decorator that logs errors and reraises as a specific exception type.
    Useful for critical operations.
    """
    return safe_execute(operation_name, reraise=exception_type)

def with_error_context(context_msg: str):
    """
    Context manager for error handling in blocks of code.
    """
    class ErrorContext:
        def __enter__(self):
            return self
            
        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type:
                logger.error(f"Error in {context_msg}: {exc_val}")
            return False  # Don't suppress exceptions
    
    return ErrorContext()