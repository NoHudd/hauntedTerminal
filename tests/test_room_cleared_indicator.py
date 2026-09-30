"""GameWorld.is_room_cleared: derived from existing state, nothing new
persisted. A room with no enemies reads as cleared once visited; otherwise it
only reads as cleared once every enemy it ever had is
genuinely defeated — not just currently absent (a fled enemy is absent from
enemy_locations too, but respawns on the next ROOM_ENTERED, so it must not
read as cleared)."""
from engine.api import GameSession


def test_room_with_no_enemies_is_cleared_once_visited():
    """Nothing to fight, so visiting is what clears it: /proc read as never
    done even after the player had been there."""
    s = GameSession()
    try:
        s.new_game("t", "guardian")
        assert s.world.is_room_cleared("proc_secrets") is False
        s.world.set_room_visited("proc_secrets")
        assert s.world.is_room_cleared("proc_secrets") is True
    finally:
        s.close()


def test_walking_into_proc_marks_it_in_the_tree():
    s = GameSession()
    try:
        s.new_game("t", "guardian")
        s.player.tutorial_state["completed"] = True
        s.submit("cd /proc")
        s.submit("cd /")
        proc_line = next(
            line for line in "\n".join(str(x) for x in s.submit("tree")).splitlines()
            if "proc/" in line
        )
        assert "✓" in proc_line
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


def test_ls_marks_cleared_child_directory():
    """var_dungeon sits at /var, a child of /, and always declares
    enemy_tier: 2 (data/rooms/var_dungeon.yml) regardless of which specific
    tier-2 enemies the RNG rolls there — both facts are deterministic, so this
    test doesn't depend on run-to-run enemy placement."""
    s = GameSession()
    try:
        s.new_game("t", "guardian")
        s.world.mark_flag_captured("var_dungeon")
        for enemy_id in list(s.world.enemy_locations):
            if s.world.enemy_locations[enemy_id] == "var_dungeon":
                s.world.remove_enemy_from_room(enemy_id)
        assert s.world.is_room_cleared("var_dungeon") is True

        # The cleared marker rides the directory listing, so list the parent.
        s.player.current_room = "root"
        out = "\n".join(str(line) for line in s.submit("ls"))
        assert "var/" in out
        assert "✓" in out
    finally:
        s.close()


def test_tree_marks_cleared_room():
    """var_dungeon always declares enemy_tier: 2 (data/rooms/var_dungeon.yml)
    and is never hidden, so it always appears in the tree and always has
    enemies to clear, whichever tier-2 enemies the RNG rolls there."""
    s = GameSession()
    try:
        s.new_game("t", "guardian")
        s.world.set_room_visited("var_dungeon")
        s.world.mark_flag_captured("var_dungeon")
        for enemy_id in list(s.world.enemy_locations):
            if s.world.enemy_locations[enemy_id] == "var_dungeon":
                s.world.remove_enemy_from_room(enemy_id)
        assert s.world.is_room_cleared("var_dungeon") is True

        out = "\n".join(str(line) for line in s.submit("tree"))
        assert "var/" in out and "✓" in out
    finally:
        s.close()
