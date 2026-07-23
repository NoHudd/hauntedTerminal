"""GameWorld.is_room_cleared: derived from existing state, nothing new
persisted. A room only reads as cleared once every enemy it ever had is
genuinely defeated — not just currently absent (a fled enemy is absent from
enemy_locations too, but respawns on the next ROOM_ENTERED, so it must not
read as cleared)."""
from engine.api import GameSession


def test_room_with_no_enemies_never_shown_as_cleared():
    s = GameSession()
    try:
        s.new_game("t", "guardian")
        # home_grove has no enemies declared at all (tutorial safe room).
        assert s.world.is_room_cleared("home_grove") is False
    finally:
        s.close()


def test_room_with_enemies_present_is_not_cleared():
    s = GameSession()
    try:
        s.new_game("t", "guardian")
        enemy_id = next(iter(s.world.enemy_locations))
        room_id = s.world.enemy_locations[enemy_id]
        assert s.world.is_room_cleared(room_id) is False
    finally:
        s.close()


def test_room_with_all_enemies_defeated_is_cleared():
    s = GameSession()
    try:
        s.new_game("t", "guardian")
        enemy_id = next(iter(s.world.enemy_locations))
        room_id = s.world.enemy_locations[enemy_id]
        assert s.world.is_room_cleared(room_id) is False
        s.world.remove_enemy_from_room(enemy_id)
        assert s.world.is_room_cleared(room_id) is True
    finally:
        s.close()


def test_fled_enemy_room_is_not_cleared_until_respawn_and_redefeat():
    s = GameSession()
    try:
        s.new_game("t", "guardian")
        enemy_id = next(iter(s.world.enemy_locations))
        room_id = s.world.enemy_locations[enemy_id]
        s.world.mark_enemy_as_fled(enemy_id, room_id)
        # Fled — enemy is gone from enemy_locations, but it will respawn.
        assert enemy_id not in s.world.enemy_locations
        assert s.world.is_room_cleared(room_id) is False

        s.world.respawn_fled_enemies(room_id)
        assert enemy_id in s.world.enemy_locations
        assert s.world.is_room_cleared(room_id) is False

        s.world.remove_enemy_from_room(enemy_id)
        assert s.world.is_room_cleared(room_id) is True
    finally:
        s.close()


def test_ls_marks_cleared_exit_in_where_you_can_go():
    """home_grove -> var_dungeon is a static exit relationship (data/rooms/
    home_grove.yml), and var_dungeon always declares enemy_tier: 2 (data/
    rooms/var_dungeon.yml) regardless of which specific tier-2 enemies the
    RNG rolls there — both facts are deterministic, so this test doesn't
    depend on run-to-run enemy placement."""
    s = GameSession()
    try:
        s.new_game("t", "guardian")
        s.player.current_room = "home_grove"
        for enemy_id in list(s.world.enemy_locations):
            if s.world.enemy_locations[enemy_id] == "var_dungeon":
                s.world.remove_enemy_from_room(enemy_id)
        assert s.world.is_room_cleared("var_dungeon") is True

        out = "\n".join(s.submit("ls"))
        assert "cd /var ✓" in out
    finally:
        s.close()


def test_map_marks_cleared_visited_room():
    """var_dungeon (not var_dungeon's enemies specifically) is picked
    deterministically, same reasoning as test_ls_marks_cleared_exit_in_where_
    you_can_go: it always declares enemy_tier: 2 and is never hidden, so the
    map line has no other status indicator that could sit between the room
    id and the cleared marker (a hidden room's own '❓' would, and did, when
    this test first used a randomly-selected room)."""
    s = GameSession()
    try:
        s.new_game("t", "guardian")
        s.world.set_room_visited("var_dungeon")
        for enemy_id in list(s.world.enemy_locations):
            if s.world.enemy_locations[enemy_id] == "var_dungeon":
                s.world.remove_enemy_from_room(enemy_id)
        assert s.world.is_room_cleared("var_dungeon") is True

        out = "\n".join(s.submit("map"))
        assert "var_dungeon ✓" in out
    finally:
        s.close()
