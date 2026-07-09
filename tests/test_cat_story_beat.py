"""A story-beat `cat` defers the room re-list (so the '✦ saved' message is readable);
an ordinary `cat` re-lists immediately as before.
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


def test_story_beat_cat_emits_delayed_refresh():
    s = GameSession()
    try:
        s.new_game("T", "guardian")
        h = s.engine.cmd_handler
        room = h.player.current_room
        h.world.add_item_to_room("system_err_log", room)  # story_flag: typo_discovered

        out_lines = []
        n = _count_delayed_refresh(lambda: out_lines.extend(s.submit("cat system_err_log")))

        assert "Memory restored" in "".join(out_lines), "story beat message missing"
        assert n == 1, f"story-beat cat should emit one DELAYED_ROOM_REFRESH, got {n}"
    finally:
        s.close()


def test_ordinary_cat_does_not_defer():
    s = GameSession()
    try:
        s.new_game("T", "guardian")
        # readme_txt_corrupt lives in home_grove and has no story_flag
        n = _count_delayed_refresh(lambda: s.submit("cat readme_txt_corrupt"))
        assert n == 0, "ordinary cat must not defer the re-list"
    finally:
        s.close()
