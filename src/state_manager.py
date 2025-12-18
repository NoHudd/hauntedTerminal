#!/usr/bin/env python3
from src.game_states import GameState
from src.events import event_bus, EventType
from utils.debug_tools import debug_log

class StateManager:
    """Centralized singleton for game state management."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._current_state = GameState.MENU
        self._previous_state = None
        self._combat_context = None  # Track combat-specific state
        self._initialized = True
        debug_log("StateManager initialized")

    @property
    def current_state(self):
        """Get current game state."""
        return self._current_state

    def set_state(self, new_state, emit_event=True):
        """
        Set game state with validation.

        Args:
            new_state: The new GameState
            emit_event: Whether to emit UI_STATE_CHANGED event
        """
        if new_state == self._current_state:
            debug_log(f"State already {new_state}, skipping")
            return

        old_state = self._current_state
        self._previous_state = old_state
        self._current_state = new_state

        debug_log(f"State transition: {old_state} -> {new_state}")

        if emit_event:
            event_bus.emit_event(
                EventType.UI_STATE_CHANGED,
                {"new_state": new_state, "old_state": old_state},
                "StateManager"
            )

    def enter_combat(self, combat_context=None):
        """Enter combat state with optional context."""
        self._combat_context = combat_context
        self.set_state(GameState.IN_COMBAT)

    def exit_combat(self):
        """Exit combat state."""
        self._combat_context = None
        self.set_state(GameState.PLAYING)

    def is_in_combat(self):
        """Check if currently in combat."""
        return self._current_state == GameState.IN_COMBAT

    def get_combat_context(self):
        """Get combat context (enemy queue, etc)."""
        return self._combat_context

# Singleton instance
state_manager = StateManager()
