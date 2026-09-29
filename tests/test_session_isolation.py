"""Two engines in one process do not hear each other.

Each engine owns its EventBus and StateManager, so a run that is never closed
cannot react to another run's events — the property the old process-wide bus
lacked, and the prerequisite for hosting more than one game per process.
"""
from __future__ import annotations

from engine.api import GameSession
from src.events import EventType
from src.game_states import GameState


def test_commands_in_one_session_do_not_reach_another() -> None:
    a, b = GameSession(), GameSession()
    try:
        a.new_game("A", "guardian")
        b.new_game("B", "weaver")

        heard_by_b: list[object] = []
        b.bus.subscribe(EventType.COMMAND_ENTERED, heard_by_b.append)

        b_room = b.player.current_room
        a.submit("cd /bin")

        assert heard_by_b == []
        assert b.player.current_room == b_room
    finally:
        a.close()
        b.close()


def test_state_changes_are_per_session() -> None:
    a, b = GameSession(), GameSession()
    try:
        a.new_game("A", "guardian")
        assert a.state == GameState.PLAYING
        assert b.state == GameState.MENU
    finally:
        a.close()
        b.close()


def test_an_unclosed_session_cannot_double_handle_the_next_ones_quit() -> None:
    leaked = GameSession()
    leaked.new_game("L", "guardian")

    s = GameSession()
    try:
        s.new_game("S", "guardian")
        s.submit("quit")
        s.submit("n")
        assert s.ui.quit_requested is True
        assert leaked.ui.quit_requested is False
    finally:
        s.close()
        leaked.close()
