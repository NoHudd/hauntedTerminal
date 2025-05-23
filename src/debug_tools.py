#!/usr/bin/env python3
import os
import time
import inspect
from datetime import datetime

# Debug configuration
DEBUG_MODE = os.environ.get("HFSE_DEBUG", "False").lower() in ["true", "1", "yes"]
DEBUG_LOG_FILE = os.environ.get("HFSE_DEBUG_LOG", "debug.log")
DEBUG_CATEGORIES = {
    "command": True,        # Command processing
    "item": True,           # Item interactions
    "combat": True,         # Combat events
    "room": True,           # Room navigation
    "player": True,         # Player state changes
    "status": True,         # Status effects
    "npc": True,            # NPC interactions
    "system": True,         # System events
    "world": True,          # World state changes
}

# Allow enabling specific debug categories via environment variables
for category in DEBUG_CATEGORIES.keys():
    env_var = f"HFSE_DEBUG_{category.upper()}"
    if os.environ.get(env_var, "").lower() in ["true", "1", "yes"]:
        DEBUG_CATEGORIES[category] = True
    elif os.environ.get(env_var, "").lower() in ["false", "0", "no"]:
        DEBUG_CATEGORIES[category] = False

def debug_log(message, category="system"):
    """
    Log a debug message to the debug log file and console if DEBUG_MODE is True.
    
    Args:
        message (str): The message to log
        category (str): The category of the log message (command, item, combat, etc.)
    """
    if not DEBUG_MODE:
        return
    
    # Skip logging if the category is disabled
    if category in DEBUG_CATEGORIES and not DEBUG_CATEGORIES[category]:
        return
    
    # Get caller information
    frame = inspect.currentframe().f_back
    filename = os.path.basename(frame.f_code.co_filename)
    line_number = frame.f_lineno
    function_name = frame.f_code.co_name
    
    # Format the time
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    
    # Format the log message
    log_message = f"[{timestamp}] [{category.upper()}] [{filename}:{function_name}:{line_number}] {message}"
    
    # Print to console
    print(log_message)
    
    # Write to log file
    try:
        with open(DEBUG_LOG_FILE, "a") as f:
            f.write(log_message + "\n")
    except Exception as e:
        print(f"Error writing to debug log file: {e}")

def start_timer(label=""):
    """
    Start a timer for performance debugging.
    
    Args:
        label (str): A label for this timer
        
    Returns:
        tuple: (start_time, label) to be passed to end_timer
    """
    return (time.time(), label)

def end_timer(timer_info, category="system"):
    """
    End a timer and log the elapsed time.
    
    Args:
        timer_info (tuple): The tuple returned by start_timer
        category (str): The category for the log message
    """
    start_time, label = timer_info
    elapsed = time.time() - start_time
    debug_log(f"{label} took {elapsed:.4f} seconds", category)
    return elapsed

def dump_object(obj, category="system"):
    """
    Dump all attributes of an object to the debug log.
    
    Args:
        obj: The object to dump
        category (str): The category for the log message
    """
    if not DEBUG_MODE:
        return
    
    debug_log(f"Dumping object: {obj.__class__.__name__}", category)
    for attr_name in dir(obj):
        # Skip private attributes and methods
        if attr_name.startswith("_"):
            continue
        
        try:
            attr_value = getattr(obj, attr_name)
            # Skip methods and functions
            if callable(attr_value):
                continue
                
            debug_log(f"  {attr_name} = {attr_value}", category)
        except Exception as e:
            debug_log(f"  Error getting {attr_name}: {e}", category)

def trace_function(func):
    """
    Decorator to trace function calls, arguments, and return values.
    
    Args:
        func: The function to decorate
        
    Returns:
        The decorated function
    """
    def wrapper(*args, **kwargs):
        if not DEBUG_MODE:
            return func(*args, **kwargs)
        
        # Get function info
        func_name = func.__name__
        module_name = func.__module__
        
        # Format arguments
        args_str = ", ".join([repr(arg) for arg in args])
        kwargs_str = ", ".join([f"{k}={repr(v)}" for k, v in kwargs.items()])
        all_args = ", ".join(filter(None, [args_str, kwargs_str]))
        
        # Log function entry
        debug_log(f"ENTER: {module_name}.{func_name}({all_args})", "system")
        
        # Start timer
        timer = start_timer(f"Function {func_name}")
        
        # Call the function
        try:
            result = func(*args, **kwargs)
            # Log function exit
            end_timer(timer, "system")
            debug_log(f"EXIT: {module_name}.{func_name} -> {repr(result)}", "system")
            return result
        except Exception as e:
            # Log exception
            end_timer(timer, "system")
            debug_log(f"EXCEPTION in {module_name}.{func_name}: {e}", "system")
            raise
    
    return wrapper

def enable_debug_mode():
    """Enable debug mode programmatically"""
    global DEBUG_MODE
    DEBUG_MODE = True
    debug_log("Debug mode enabled programmatically")

def disable_debug_mode():
    """Disable debug mode programmatically"""
    global DEBUG_MODE
    DEBUG_MODE = False
    debug_log("Debug mode disabled")

def set_debug_category(category, enabled=True):
    """
    Enable or disable a specific debug category.
    
    Args:
        category (str): The category to enable/disable
        enabled (bool): True to enable, False to disable
    """
    if category in DEBUG_CATEGORIES:
        DEBUG_CATEGORIES[category] = enabled
        debug_log(f"Debug category '{category}' {'enabled' if enabled else 'disabled'}")
    else:
        debug_log(f"Unknown debug category: {category}")

# Log that debug_tools has been loaded
if DEBUG_MODE:
    debug_log("Debug tools loaded")
    for category, enabled in DEBUG_CATEGORIES.items():
        debug_log(f"Debug category '{category}' is {'enabled' if enabled else 'disabled'}") 