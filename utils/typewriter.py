#!/usr/bin/env python3
"""
Typewriter Effect Utility for HFSE

Provides typewriter-style text animation that respects dev mode settings.
When DISABLE_ANIMATIONS is True, text appears instantly.
"""

import time
import asyncio
import os
from typing import Optional, Callable

# Get animation setting from environment
DISABLE_ANIMATIONS = os.environ.get("HFSE_DISABLE_ANIMATIONS", "False").lower() in ["true", "1", "yes"]

class TypewriterEffect:
    """Handles typewriter-style text display with animation controls."""
    
    def __init__(self, 
                 chars_per_second: float = 50.0,
                 pause_after_punctuation: float = 0.3,
                 pause_after_newline: float = 0.8):
        """
        Initialize typewriter effect.
        
        Args:
            chars_per_second: Base typing speed
            pause_after_punctuation: Extra pause after . ! ?
            pause_after_newline: Extra pause after newlines
        """
        self.chars_per_second = chars_per_second
        self.pause_after_punctuation = pause_after_punctuation
        self.pause_after_newline = pause_after_newline
        
    def get_char_delay(self, char: str, next_char: Optional[str] = None) -> float:
        """Calculate delay after typing a character."""
        if DISABLE_ANIMATIONS:
            return 0.0
            
        base_delay = 1.0 / self.chars_per_second
        
        # Add pauses for dramatic effect
        if char in '.!?':
            return base_delay + self.pause_after_punctuation
        elif char == '\n':
            return base_delay + self.pause_after_newline
        elif char in ',;:':
            return base_delay + 0.1
        else:
            return base_delay
    
    def type_text_sync(self, text: str, output_callback: Callable[[str], None]):
        """
        Type text with typewriter effect (synchronous).
        
        Args:
            text: Text to display
            output_callback: Function to call with each character update
        """
        if DISABLE_ANIMATIONS:
            # Instantly display full text in dev mode
            output_callback(text)
            return
            
        current_text = ""
        for i, char in enumerate(text):
            current_text += char
            output_callback(current_text)
            
            # Calculate delay for this character
            next_char = text[i + 1] if i + 1 < len(text) else None
            delay = self.get_char_delay(char, next_char)
            
            if delay > 0:
                time.sleep(delay)
    
    async def type_text_async(self, text: str, output_callback: Callable[[str], None]):
        """
        Type text with typewriter effect (asynchronous).
        
        Args:
            text: Text to display  
            output_callback: Function to call with each character update
        """
        if DISABLE_ANIMATIONS:
            # Instantly display full text in dev mode
            output_callback(text)
            return
            
        current_text = ""
        for i, char in enumerate(text):
            current_text += char
            output_callback(current_text)
            
            # Calculate delay for this character
            next_char = text[i + 1] if i + 1 < len(text) else None
            delay = self.get_char_delay(char, next_char)
            
            if delay > 0:
                await asyncio.sleep(delay)

# Pre-configured typewriter instances for different use cases
class TypewriterPresets:
    """Pre-configured typewriter effects for different contexts."""
    
    # Fast typing for normal dialogue
    DIALOGUE = TypewriterEffect(chars_per_second=60.0)
    
    # Slower, more dramatic for important story moments
    NARRATIVE = TypewriterEffect(
        chars_per_second=35.0, 
        pause_after_punctuation=0.5, 
        pause_after_newline=1.0
    )
    
    # Very slow for dramatic reveals
    DRAMATIC = TypewriterEffect(
        chars_per_second=20.0,
        pause_after_punctuation=0.8,
        pause_after_newline=1.5
    )
    
    # Fast for system messages
    SYSTEM = TypewriterEffect(chars_per_second=80.0)


def create_typewriter_output_func(ui_update_method):
    """
    Create an output callback function for typewriter effects.
    
    Args:
        ui_update_method: The UI update method to call
        
    Returns:
        Function that can be used as typewriter output callback
    """
    def output_callback(text: str):
        ui_update_method(text)
    return output_callback