"""Regression: restarting must not leave the old run's handlers on the bus.

The event bus is a process-wide singleton, so a CommandHandler that is dropped
without unsubscribing keeps reacting to events with its dead player and world.
The symptom is doubled work: a dead run's tutorial reacting to the next run's
fights alongside the live one.
"""
from __future__ import annotations

import pytest

from engine.api import GameSession
from engine.events import EventType

# Events a CommandHandler subscribes to. Exactly one handler may be listening on
# each of these at a time, however many times the game has been restarted.
HANDLER_EVENTS = [
    EventType.COMBAT_ENDED,
    EventType.COMBAT_ACTION_RESULT,
]


def _counts(bus) -> dict[EventType, int]:
    return {e: len(bus._listeners.get(e, [])) for e in HANDLER_EVENTS}


@pytest.fixture
def session():
    s = GameSession()
    try:
        yield s
    finally:
        s.close()


def test_f5_restart_then_new_game_leaves_no_duplicate_handlers(session) -> None:
    session.new_game("First", "guardian")
    baseline = _counts(session.bus)

    session.engine.restart_game()      # the F5 path
    session.new_game("Second", "weaver")

    assert _counts(session.bus) == baseline, (
        "restart leaked the previous CommandHandler's subscriptions — "
        "enemies will be fought twice and loot rolled twice"
    )


def test_repeated_new_games_do_not_accumulate_handlers(session) -> None:
    session.new_game("One", "guardian")
    baseline = _counts(session.bus)

    for name, klass in (("Two", "weaver"), ("Three", "shaman"), ("Four", "guardian")):
        session.engine.restart_game()
        session.new_game(name, klass)

    assert _counts(session.bus) == baseline
