#!/usr/bin/env python3
"""
UI Interface Protocol

Defines the contract that all UI implementations must follow,
enabling better abstraction and testability.
"""

from typing import Protocol, Any

class UIProtocol(Protocol):
    """Protocol defining the UI interface contract."""
    
    def attach_bus(self, bus: Any, state_manager: Any) -> None:
        """Adopt the owning engine's EventBus and StateManager (called once,
        from the engine's constructor, before the engine subscribes)."""
        ...

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
    
    def clear_console(self) -> None:
        """Clear the output display."""
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