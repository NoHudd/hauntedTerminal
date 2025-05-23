#!/usr/bin/env python3
import sys
from dev_config import DEBUG_MODE

def debug_log(message):
    """
    Print a debug message to the console if DEBUG_MODE is enabled.
    
    Args:
        message (str): The debug message to print
    """
    if DEBUG_MODE:
        # Print to stderr to avoid interfering with normal game output
        print(f"[DEBUG] {message}", file=sys.stderr) 