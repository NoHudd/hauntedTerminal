#!/usr/bin/env python3
"""
Game State Constants

Defines all game states as constants to avoid magic strings
and provide better type safety.
"""

from enum import Enum, auto

class GameState(Enum):
    """Enumeration of all possible game states."""
    
    MENU = "menu"
    WAITING_FOR_CLASS = "waiting_for_class"
    WAITING_FOR_DIFFICULTY = "waiting_for_difficulty"
    WAITING_FOR_SAVE = "waiting_for_save"
    TUTORIAL_NAME_INPUT = "tutorial_name_input"
    PLAYING = "playing"  
    IN_COMBAT = "in_combat"
    GAME_OVER = "game_over"
    
    def __str__(self) -> str:
        return self.value

class UIState(Enum):
    """Enumeration of UI states."""
    
    INITIALIZING = auto()
    READY = auto()
    ERROR = auto()
    SHUTTING_DOWN = auto()

# Default states
DEFAULT_GAME_STATE = GameState.MENU
DEFAULT_ROOM = "home_grove"