#!/usr/bin/env python3
"""
UI Interface Protocol

Defines the contract that all UI implementations must follow,
enabling better abstraction and testability.
"""

from abc import ABC, abstractmethod
from typing import Protocol, Any, Optional

class UIProtocol(Protocol):
    """Protocol defining the UI interface contract."""
    
    def run(self) -> None:
        """Start the UI main loop."""
        ...
    
    def shutdown(self) -> None:
        """Clean shutdown of UI resources."""
        ...
    
    def update_output(self, content: str) -> None:
        """Update the main output display. content may be a markup string or a
        Rich renderable (e.g. rich.text.Text)."""
        ...

    def append_output(self, content: str) -> None:
        """Append content to the current output display."""
        ...

    def display_message(self, message: str) -> None:
        """Show a one-off message (used by the engine for prompts/notices)."""
        ...

    def update_output_renderable(self, renderable) -> None:
        """Push a Rich renderable (Panel/Table/Group) straight to the output."""
        ...
    
    def update_inventory(self, content: str) -> None:
        """Update the inventory panel."""
        ...
    
    def update_stats(self, content: str) -> None:
        """Update the stats panel."""
        ...
    
    def update_exits(self, exits: list) -> None:
        """Update the exits panel."""
        ...
    
    def update_player_name(self, name: str) -> None:
        """Update the player name display."""
        ...
    
    def clear_console(self) -> None:
        """Clear the output display."""
        ...
    
    def display_game_over(self) -> None:
        """Show the game over screen."""
        ...
    
    def save_current_game(self) -> None:
        """Handle game saving UI feedback."""
        ...

class GameEngineProtocol(Protocol):
    """Protocol defining what the UI can access from GameEngine."""
    
    @property
    def player(self) -> Optional[Any]:
        """Get the current player."""
        ...
    
    @property
    def world(self) -> Optional[Any]:
        """Get the game world."""
        ...
    
    @property
    def game_state(self) -> str:
        """Get the current game state."""
        ...
    
    def load_game_data(self) -> None:
        """Load game data."""
        ...
    
    def initialize_special_items(self, player_class: str) -> None:
        """Initialize class-specific items."""
        ...

class UIError(Exception):
    """Base exception for UI-related errors."""
    pass

class UIInitializationError(UIError):
    """Raised when UI fails to initialize."""
    pass

class UIStateError(UIError):
    """Raised when UI is in an invalid state."""
    pass