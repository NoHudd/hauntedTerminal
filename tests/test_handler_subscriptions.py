"""Regression: a new CommandHandler must not leave a prior one subscribed.

Two live handlers used to fight each enemy twice and roll loot twice. Game rules
no longer hang off events (arrival, kills and combat outcomes are direct calls),
so the only handler-owned listeners left are the tutorial's; recreating the
player must leave exactly one of each, all belonging to the current handler.
"""
from __future__ import annotations

from collections import Counter

from engine.headless import HeadlessUI
from src.command_handler import CommandHandler
from src.events import EventType
from src.game_engine import ImprovedGameEngine
from src.tutorial_coach import TutorialCoach


def _handler_listeners(eng: ImprovedGameEngine) -> list[tuple[EventType, object]]:
    return [
        (event_type, getattr(cb, "__self__", None))
        for event_type, callbacks in eng.bus._listeners.items()
        for cb in callbacks
        if isinstance(getattr(cb, "__self__", None), (CommandHandler, TutorialCoach))
    ]


def test_recreating_player_leaves_one_subscribed_handler() -> None:
    eng = ImprovedGameEngine(ui=HeadlessUI())
    try:
        eng.create_player("A", "guardian")
        first = eng.cmd_handler
        eng.create_player("B", "guardian")  # must clean up A's subscriptions
        eng.start_game()

        listeners = _handler_listeners(eng)
        owners = {id(owner) for _, owner in listeners}
        assert id(first) not in owners and id(first.tutorial) not in owners
        assert all(n == 1 for n in Counter(et for et, _ in listeners).values()), listeners
    finally:
        eng._cleanup()


def test_a_kill_event_alone_changes_nothing() -> None:
    """ENEMY_DEFEATED is a UI notification: loot and removal run from on_kill."""
    eng = ImprovedGameEngine(ui=HeadlessUI())
    try:
        eng.create_player("A", "guardian")
        eng.start_game()
        world = eng.world
        room_id, enemy_id = next(
            (rid, world.get_enemies_in_room(rid)[0])
            for rid in world.rooms if world.get_enemies_in_room(rid)
        )
        eng.bus.emit_event(EventType.ENEMY_DEFEATED, {"enemy_id": enemy_id}, "test")
        assert enemy_id in world.get_enemies_in_room(room_id)
        assert enemy_id not in eng.cmd_handler.loot.awarded
    finally:
        eng._cleanup()
