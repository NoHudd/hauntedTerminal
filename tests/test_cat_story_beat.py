"""`cat` shows the file and nothing else — no room re-list, deferred or immediate.

The scene view shows who is in the room and the exits, so appending/replacing the
output with a full room listing after every cat was noise (and with append-mode
output it read as a glitchy wall). Story-beat messages must still appear.
"""
from __future__ import annotations

from engine.api import GameSession
from src.events import EventType, event_bus


def _count_delayed_refresh(fn):
    hits = {"n": 0}
    cb = lambda ev: hits.__setitem__("n", hits["n"] + 1)  # noqa: E731
    event_bus.subscribe(EventType.DELAYED_ROOM_REFRESH, cb)
    try:
        fn()
    finally:
        event_bus.unsubscribe(EventType.DELAYED_ROOM_REFRESH, cb)
    return hits["n"]


def test_story_beat_cat_shows_message_without_relist():
    s = GameSession()
    try:
        s.new_game("T", "guardian")
        h = s.engine.cmd_handler
        room = h.player.current_room
        h.world.add_item_to_room("system_err_log", room)  # story_flag: typo_discovered

        out_lines = []
        n = _count_delayed_refresh(lambda: out_lines.extend(s.submit("cat system_err_log")))
        joined = "".join(str(x) for x in out_lines)

        assert "Memory restored" in joined, "story beat message missing"
        assert n == 0, f"cat must not defer a room re-list anymore, got {n}"
        assert "Where you can go" not in joined, "cat must not append the room listing"
    finally:
        s.close()


def test_ordinary_cat_does_not_relist():
    s = GameSession()
    try:
        s.new_game("T", "guardian")
        # readme_txt_corrupt lives in home_grove and has no story_flag
        out = []
        n = _count_delayed_refresh(lambda: out.extend(s.submit("cat readme_txt_corrupt")))
        joined = "".join(str(x) for x in out)
        assert n == 0
        assert "Where you can go" not in joined, "cat must not append the room listing"
    finally:
        s.close()
