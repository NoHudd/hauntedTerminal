"""GameSession — the single entry point a frontend uses to drive the game.

A frontend (the Textual TUI, a test, a scripted playthrough) talks only to this
facade: start a game, submit a command string, read back the text the engine
produced. Input already flows through the synchronous event bus
(COMMAND_ENTERED), so ``submit`` emits that event and returns whatever the engine
rendered — captured by the HeadlessUI sink.

This makes the engine drivable with no Textual App. It does not yet sever the
domain->UI output coupling; it captures at the existing seam.
"""

from __future__ import annotations

from typing import Any

from src.events import EventType, event_bus
from src.game_engine import ImprovedGameEngine
from src.game_states import GameState
from src.state_manager import state_manager

from .headless import HeadlessUI


class GameSession:
    """Headless driver around ImprovedGameEngine."""

    def __init__(self) -> None:
        self.ui = HeadlessUI()
        self.engine = ImprovedGameEngine(ui=self.ui)

    # --- lifecycle ----------------------------------------------------------

    def new_game(self, name: str, player_class: str) -> list[str]:
        """Create a player and enter PLAYING. Returns startup output."""
        self.ui.clear_console()
        if not self.engine.create_player(name, player_class):
            raise RuntimeError(f"failed to create player (class={player_class!r})")
        self.engine.start_game()
        return self.ui.drain()

    # --- driving ------------------------------------------------------------

    def submit(self, command: str) -> list[str]:
        """Run one command through the engine; return the text it produced."""
        self.ui.clear_console()
        event_bus.emit_event(
            EventType.COMMAND_ENTERED,
            {"command": command, "game_state": state_manager.current_state},
            "GameSession",
        )
        return self.ui.drain()

    # --- read-only state accessors ------------------------------------------

    @property
    def player(self) -> Any:
        return self.engine.player

    @property
    def world(self) -> Any:
        return self.engine.world

    @property
    def state(self) -> GameState:
        return state_manager.current_state

    def close(self) -> None:
        self.engine._cleanup()
