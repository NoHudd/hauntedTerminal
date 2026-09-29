#!/usr/bin/env python3
from __future__ import annotations

import logging

from src.game_states import GameState
from src.events import EventBus, EventType
from utils.debug_tools import debug_log

logger = logging.getLogger(__name__)


class StateManager:
    """Game-state machine for one engine; emits transitions on that engine's bus."""

    # Define valid state transitions for validation
    _valid_transitions: dict[GameState, list[GameState]] = {
        GameState.MENU: [GameState.WAITING_FOR_DIFFICULTY],
        GameState.WAITING_FOR_DIFFICULTY: [GameState.WAITING_FOR_CLASS, GameState.MENU],
        GameState.WAITING_FOR_CLASS: [GameState.PLAYING],
        GameState.TUTORIAL_NAME_INPUT: [GameState.WAITING_FOR_CLASS, GameState.PLAYING],
        GameState.PLAYING: [GameState.IN_COMBAT, GameState.GAME_OVER, GameState.MENU],
        GameState.IN_COMBAT: [GameState.PLAYING, GameState.GAME_OVER],
        GameState.GAME_OVER: [GameState.MENU],
    }

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._current_state: GameState = GameState.MENU
        debug_log("StateManager initialized")

    @property
    def current_state(self) -> GameState:
        """Get current game state."""
        return self._current_state

    def set_state(self, new_state: GameState, emit_event: bool = True) -> None:
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

        self._current_state = new_state

        debug_log(f"State transition: {old_state} -> {new_state}")

        if emit_event:
            self._bus.emit_event(
                EventType.UI_STATE_CHANGED,
                {"new_state": new_state, "old_state": old_state},
                "StateManager"
            )

    def enter_combat(self) -> None:
        """Enter combat state."""
        self.set_state(GameState.IN_COMBAT)

    def exit_combat(self) -> None:
        """Exit combat state."""
        self.set_state(GameState.PLAYING)

    def is_in_combat(self) -> bool:
        """Check if currently in combat."""
        return bool(self._current_state == GameState.IN_COMBAT)

    def is_in_game_over(self) -> bool:
        """Check if currently in game over state."""
        return bool(self._current_state == GameState.GAME_OVER)
