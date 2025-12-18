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
    WAITING_FOR_NAME = "waiting_for_name"
    WAITING_FOR_CLASS = "waiting_for_class"
    TUTORIAL_NAME_INPUT = "tutorial_name_input"
    PLAYING = "playing"  
    IN_COMBAT = "in_combat"
    GAME_OVER = "game_over"
    EXIT = "exit"
    LOADING = "loading"
    SAVING = "saving"
    PAUSED = "paused"
    
    def __str__(self) -> str:
        return self.value

class UIState(Enum):
    """Enumeration of UI states."""
    
    INITIALIZING = auto()
    READY = auto()
    ERROR = auto()
    SHUTTING_DOWN = auto()

class PlayerState(Enum):
    """Enumeration of player states."""
    
    ALIVE = auto()
    DEAD = auto()
    IN_COMBAT = auto()
    EXPLORING = auto()
    IN_DIALOGUE = auto()

# Default states
DEFAULT_GAME_STATE = GameState.MENU
DEFAULT_ROOM = "home_grove"