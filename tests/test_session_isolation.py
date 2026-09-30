"""Two engines in one process do not hear each other.

Each engine owns its EventBus and StateManager, so a run that is never closed
cannot react to another run's events — the property the old process-wide bus
lacked, and the prerequisite for hosting more than one game per process.
"""
from __future__ import annotations

from engine.api import GameSession


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
