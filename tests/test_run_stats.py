"""Run stats: kill/item counters + save round-trip."""
from engine.api import GameSession


def test_take_increments_items_found():
    s = GameSession()
    s.new_game("t", "guardian")
    s.world.item_locations["health_packet"] = s.player.current_room
    before = s.player.run_stats["items_found"]
    s.submit("take health_packet")
    assert s.player.run_stats["items_found"] == before + 1
    s.close()


def test_kill_increments_kills():
    from src.events import EventType, event_bus
    s = GameSession()
    s.new_game("t", "guardian")
    world = s.world
    room_id, enemy_id = next(
        ((rid, world.get_enemies_in_room(rid)[0])
         for rid in world.rooms if world.get_enemies_in_room(rid)),
        (None, None),
    )
    assert enemy_id, "expected some room with an enemy"
    s.player.current_room = room_id
    before = s.player.run_stats["kills"]
    event_bus.emit_event(EventType.ENEMY_DEFEATED, {"enemy_id": enemy_id}, "test")
    assert s.player.run_stats["kills"] == before + 1
    s.close()


def test_run_stats_save_round_trip():
    from src.player import Player
    p = Player(name="t", player_class="guardian")
    p.run_stats["kills"] = 7
    data = p.to_dict()
    assert data["runStats"]["kills"] == 7
    p2 = Player.from_dict(data)
    assert p2.run_stats == p.run_stats


def test_old_save_without_runstats_loads():
    from src.player import Player
    p = Player(name="t", player_class="guardian")
    data = p.to_dict()
    del data["runStats"]
    p2 = Player.from_dict(data)
    assert p2.run_stats == {"kills": 0, "items_found": 0}
