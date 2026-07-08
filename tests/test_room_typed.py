"""Room templates are typed; get_room returns a live model; enemy removal persists."""
from __future__ import annotations

from engine.schema import Room


def test_load_room_data_returns_typed_models():
    from src.data_loader import load_room_data
    rooms = load_room_data()
    assert len(rooms) == 18
    for rid, r in rooms.items():
        assert isinstance(r, Room), (rid, type(r))
        assert r.name


def test_defeated_enemy_does_not_reappear():
    # get_enemies_in_room unions dynamic + template enemies; removal must mutate
    # the live template model so a cleared enemy stays gone.
    from engine.api import GameSession
    s = GameSession()
    try:
        s.new_game("Tester", "guardian")
        world = s.engine.cmd_handler.world
        room_id = next(
            (rid for rid in world.rooms if world.get_enemies_in_room(rid)), None
        )
        assert room_id, "expected some room with an enemy"
        eid = world.get_enemies_in_room(room_id)[0]
        world.remove_enemy_from_room(eid)
        assert eid not in world.get_enemies_in_room(room_id)
    finally:
        s.close()
