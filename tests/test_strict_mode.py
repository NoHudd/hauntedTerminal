"""The suite runs strict (tests/conftest.py): a failure the game would only log
fails the test instead. These pin that the switches are really on."""
from __future__ import annotations

import pytest

from engine.api import GameSession
from src.events import Event, EventBus, EventType
from src.viewmodels.view_builder import ViewBuilder


def _explode(event: Event) -> None:
    raise RuntimeError("listener bug")


def test_a_listener_that_raises_fails_the_emit() -> None:
    bus = EventBus()
    bus.subscribe(EventType.UI_READY, _explode)
    with pytest.raises(RuntimeError, match="listener bug"):
        bus.emit_event(EventType.UI_READY, {}, "test")


def test_the_game_itself_logs_and_continues() -> None:
    bus = EventBus(strict=False)
    heard: list[Event] = []
    bus.subscribe(EventType.UI_READY, _explode)
    bus.subscribe(EventType.UI_READY, heard.append)
    bus.emit_event(EventType.UI_READY, {}, "test")
    assert len(heard) == 1


def test_a_session_bus_is_strict() -> None:
    session = GameSession()
    try:
        assert session.bus.strict is True
    finally:
        session.close()


def test_a_failed_view_build_raises() -> None:
    with pytest.raises(AttributeError):
        ViewBuilder.build_room_view(object(), "home_grove")
