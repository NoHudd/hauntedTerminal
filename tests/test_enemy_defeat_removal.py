"""Regression: defeating an enemy must remove it from the room.

_on_enemy_defeated awards drops then removes the enemy. If the drop-award reads the
typed Enemy model with .get() it raises, the event callback aborts before removal,
the enemy stays, and combat re-triggers on it (fight each enemy twice).
"""
from __future__ import annotations

from engine.api import GameSession
from src.events import EventType, event_bus


def test_defeating_enemy_removes_it_from_room():
    s = GameSession()
    try:
        s.new_game("T", "guardian")
        h = s.engine.cmd_handler
        world = h.world
        # find a room that has an enemy, and put the player there
        room_id, enemy_id = next(
            ((rid, world.get_enemies_in_room(rid)[0])
             for rid in world.rooms if world.get_enemies_in_room(rid)),
            (None, None),
        )
        assert room_id and enemy_id, "expected some room with an enemy"
        h.player.current_room = room_id

        event_bus.emit_event(EventType.ENEMY_DEFEATED, {"enemy_id": enemy_id}, "test")

        assert enemy_id not in world.get_enemies_in_room(room_id), (
            f"{enemy_id} still present after ENEMY_DEFEATED — drop-award crashed before removal"
        )
    finally:
        s.close()
