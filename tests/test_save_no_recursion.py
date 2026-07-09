"""Regression: save_game must not emit GAME_SAVED.

GAME_SAVED is the *request* event (_on_save_requested handles it by calling save_game).
When save_game also emitted GAME_SAVED as a 'completed' signal, one save request
re-fired the handler → infinite recursion → hundreds of save files.

This asserts save_game emits zero GAME_SAVED itself, which is leak-immune (it doesn't
depend on how many _on_save_requested handlers are subscribed to the singleton bus).
"""
from __future__ import annotations

from engine.api import GameSession
from src.events import EventType, event_bus


def test_save_game_does_not_emit_game_saved():
    s = GameSession()
    try:
        s.new_game("T", "guardian")
        from src.save import save_manager

        hits = {"n": 0}
        counter = lambda ev: hits.__setitem__("n", hits["n"] + 1)  # noqa: E731
        event_bus.subscribe(EventType.GAME_SAVED, counter)
        try:
            save_manager.save_game(s.player, s.world.get_state())
            assert hits["n"] == 0, "save_game must not emit GAME_SAVED (causes recursive save storm)"
        finally:
            event_bus.unsubscribe(EventType.GAME_SAVED, counter)
    finally:
        s.close()
