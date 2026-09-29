#!/usr/bin/env python3
from __future__ import annotations

import logging

from src.game_states import GameState
from src.events import EventBus, EventType
from utils.debug_tools import debug_log

logger = logging.getLogger(__name__)


class InvalidTransitionError(RuntimeError):
    """A state change the transition table does not allow: a bug in the flow."""


class StateManager:
    """Game-state machine for one engine; emits transitions on that engine's bus."""

    # Every transition the game makes, and no others. MENU -> PLAYING is Load
    # Game; the -> MENU edges out of setup and play are F5 (restart) and the
    # error fallbacks; PLAYING -> MENU is also "new game" after a win.
    _valid_transitions: dict[GameState, list[GameState]] = {
        GameState.MENU: [GameState.WAITING_FOR_DIFFICULTY, GameState.PLAYING],
        GameState.WAITING_FOR_DIFFICULTY: [GameState.WAITING_FOR_CLASS, GameState.MENU],
        GameState.WAITING_FOR_CLASS: [GameState.TUTORIAL_NAME_INPUT, GameState.MENU],
        GameState.TUTORIAL_NAME_INPUT: [GameState.PLAYING, GameState.MENU],
        GameState.PLAYING: [GameState.IN_COMBAT, GameState.MENU],
        GameState.IN_COMBAT: [GameState.PLAYING, GameState.GAME_OVER, GameState.MENU],
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

        if new_state not in self._valid_transitions.get(old_state, []):
            raise InvalidTransitionError(
                f"{old_state} -> {new_state} is not a transition the game makes; "
                f"from {old_state} it goes to {self._valid_transitions.get(old_state, [])}"
            )

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
