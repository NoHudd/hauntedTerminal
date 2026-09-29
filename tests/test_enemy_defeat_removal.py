"""Regression: defeating an enemy must remove it from the room.

CommandHandler.on_kill awards drops then removes the enemy. If the drop-award reads
the typed Enemy model with .get() it raises before removal, the enemy stays, and
combat re-triggers on it (fight each enemy twice).
"""
from __future__ import annotations

from engine.api import GameSession


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

        h.on_kill(enemy_id)

        assert enemy_id not in world.get_enemies_in_room(room_id), (
            f"{enemy_id} still present after on_kill — drop-award crashed before removal"
        )
    finally:
        s.close()
