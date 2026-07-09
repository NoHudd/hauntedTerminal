#!/usr/bin/env python3
import logging
from src.game_states import GameState
from src.events import event_bus, EventType
from utils.debug_tools import debug_log

logger = logging.getLogger(__name__)


class StateManager:
    """Centralized singleton for game state management."""

    _instance = None

    # Define valid state transitions for validation
    _valid_transitions = {
        GameState.MENU: [GameState.WAITING_FOR_DIFFICULTY, GameState.WAITING_FOR_NAME, GameState.LOADING, GameState.EXIT],
        GameState.WAITING_FOR_DIFFICULTY: [GameState.WAITING_FOR_CLASS, GameState.MENU],
        GameState.WAITING_FOR_NAME: [GameState.WAITING_FOR_CLASS, GameState.TUTORIAL_NAME_INPUT],
        GameState.WAITING_FOR_CLASS: [GameState.PLAYING],
        GameState.TUTORIAL_NAME_INPUT: [GameState.WAITING_FOR_CLASS, GameState.PLAYING],
        GameState.PLAYING: [GameState.IN_COMBAT, GameState.SAVING, GameState.PAUSED, GameState.GAME_OVER, GameState.MENU, GameState.EXIT],
        GameState.IN_COMBAT: [GameState.PLAYING, GameState.GAME_OVER],
        GameState.GAME_OVER: [GameState.MENU, GameState.EXIT],
        GameState.LOADING: [GameState.PLAYING, GameState.MENU],
        GameState.SAVING: [GameState.PLAYING],
        GameState.PAUSED: [GameState.PLAYING, GameState.MENU],
        GameState.EXIT: []  # Terminal state
    }

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

        # Validate state transition (warn but allow for flexibility)
        valid_next_states = self._valid_transitions.get(old_state, [])
        if valid_next_states and new_state not in valid_next_states:
            logger.warning(
                f"Potentially invalid state transition: {old_state} -> {new_state}. "
                f"Expected one of: {valid_next_states}"
            )
            debug_log(f"WARNING: Unexpected state transition: {old_state} -> {new_state}")

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

    # Additional convenience methods for state checking

    def is_playing(self) -> bool:
        """Check if currently in playing state."""
        return self._current_state == GameState.PLAYING

    def is_in_menu(self) -> bool:
        """Check if currently in menu state."""
        return self._current_state == GameState.MENU

    def is_in_game_over(self) -> bool:
        """Check if currently in game over state."""
        return self._current_state == GameState.GAME_OVER

    def is_waiting_for_input(self) -> bool:
        """Check if waiting for user input (name, class, tutorial)."""
        return self._current_state in [
            GameState.WAITING_FOR_NAME,
            GameState.WAITING_FOR_CLASS,
            GameState.TUTORIAL_NAME_INPUT
        ]

    def can_accept_commands(self) -> bool:
        """Check if game can accept player commands."""
        return self._current_state in [GameState.PLAYING, GameState.IN_COMBAT]


# Singleton instance
state_manager = StateManager()
