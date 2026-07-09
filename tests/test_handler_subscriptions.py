"""Regression: a new CommandHandler must not leave a prior one subscribed.

Two live handlers made ROOM_ENTERED fire check_for_enemies twice (fight each enemy
twice) and ENEMY_DEFEATED fire _on_enemy_defeated twice (double loot + 'enemy not
found' warning). Creating a player must leave exactly one subscribed handler.
"""
from __future__ import annotations

from engine.headless import HeadlessUI
from src.events import EventType, event_bus
from src.game_engine import ImprovedGameEngine


def test_recreating_player_leaves_one_subscribed_handler():
    import src.command_handler as CH

    checks = {"n": 0}
    defeats = {"n": 0}
    orig_check = CH.CommandHandler.check_for_enemies
    orig_def = CH.CommandHandler._on_enemy_defeated
    CH.CommandHandler.check_for_enemies = lambda self: (checks.__setitem__("n", checks["n"] + 1), orig_check(self))[1]
    CH.CommandHandler._on_enemy_defeated = lambda self, ev: (defeats.__setitem__("n", defeats["n"] + 1), orig_def(self, ev))[1]
    try:
        eng = ImprovedGameEngine(ui=HeadlessUI())
        eng.create_player("A", "guardian")
        eng.create_player("B", "guardian")  # must clean up A's subscriptions
        eng.start_game()

        checks["n"] = 0
        event_bus.emit_event(EventType.ROOM_ENTERED, {}, "test")
        assert checks["n"] == 1, f"ROOM_ENTERED fired check_for_enemies {checks['n']}x (expected 1)"

        defeats["n"] = 0
        event_bus.emit_event(EventType.ENEMY_DEFEATED, {"enemy_id": "nope"}, "test")
        assert defeats["n"] == 1, f"ENEMY_DEFEATED fired _on_enemy_defeated {defeats['n']}x (expected 1)"
    finally:
        CH.CommandHandler.check_for_enemies = orig_check
        CH.CommandHandler._on_enemy_defeated = orig_def
