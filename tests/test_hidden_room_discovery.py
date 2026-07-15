"""`ls -a` discovering a hidden room must refresh the persistent room-view
sidebar immediately, not just print a one-shot confirmation line.

Bug: world state (room_states[id]["hidden"]) flips correctly on discovery,
but the sidebar/scene (built from ViewBuilder.build_room_view) is only
rebuilt on ROOM_ENTERED, which only fires from `cd`. So the newly revealed
exit never reaches the persistent UI until the player leaves and re-enters
the room — the one-line "Discovered hidden directory!" text is the only
place it ever showed, and the next command (right or wrong) immediately
overwrites that output panel. Looks like the room vanished.
"""
from __future__ import annotations

from engine.api import GameSession
from src.events import EventType, event_bus


def _capture_room_entered(fn):
    rooms = []
    cb = lambda ev: rooms.append(ev.data.get("room", {}))  # noqa: E731
    event_bus.subscribe(EventType.ROOM_ENTERED, cb)
    try:
        fn()
    finally:
        event_bus.unsubscribe(EventType.ROOM_ENTERED, cb)
    return rooms


def test_ls_a_discovery_refreshes_room_view():
    s = GameSession()
    try:
        s.new_game("t", "guardian")
        h = s.engine.cmd_handler
        h.player.current_room = "usr_share_games"
        # Clear enemies so ls -a isn't blocked by the combat gate.
        h.world.enemy_locations = {
            eid: rid for eid, rid in h.world.enemy_locations.items()
            if rid != "usr_share_games"
        }
        assert h.world.get_room_state("cowsay_secret")["hidden"] is True

        room_updates = _capture_room_entered(lambda: s.submit("ls -a"))

        assert h.world.get_room_state("cowsay_secret")["hidden"] is False
        assert room_updates, "discovering a hidden room must emit a room-view refresh"
        assert "/cowsay" in room_updates[-1].get("exits", []), room_updates[-1]
        # The player must NOT have moved — this is a refresh, not a navigation event.
        assert h.player.current_room == "usr_share_games"
    finally:
        s.close()


def test_ls_a_with_no_new_discovery_does_not_refresh():
    """Once already discovered, re-running ls -a finds nothing new to reveal
    and must not spam a room-view refresh."""
    s = GameSession()
    try:
        s.new_game("t", "guardian")
        h = s.engine.cmd_handler
        h.player.current_room = "usr_share_games"
        h.world.enemy_locations = {
            eid: rid for eid, rid in h.world.enemy_locations.items()
            if rid != "usr_share_games"
        }
        s.submit("ls -a")  # first discovery

        room_updates = _capture_room_entered(lambda: s.submit("ls -a"))

        assert room_updates == []
    finally:
        s.close()
