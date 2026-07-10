"""A key that unlocks a hidden room must also reveal it.

opt_mage_tower is hidden+locked (key_required: opt_key). The hidden check used
to fire before the key logic, so a mage HOLDING the key was told the path
doesn't exist.
"""
from engine.api import GameSession


def test_opt_key_reveals_and_unlocks_mage_tower():
    s = GameSession()
    try:
        s.new_game("t", "weaver")
        h = s.engine.cmd_handler
        key = s.world.get_item("opt_key")
        h.player.add_to_inventory("opt_key", dict(key))
        # stand adjacent: the tower is an exit of usr_lib_arcane
        entry = next(
            rid for rid, room in s.world.rooms.items()
            if "opt_mage_tower" in getattr(room, "exits", [])
        )
        h.player.current_room = entry

        out = "\n".join(str(x) for x in s.submit("cd /opt"))

        assert "doesn't appear to exist" not in out, out
        assert h.player.current_room == "opt_mage_tower", out
    finally:
        s.close()
