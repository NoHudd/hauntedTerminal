"""`cat` shows the file and nothing else — no room re-list.

The scene view shows who is in the room and the exits, so appending/replacing the
output with a full room listing after every cat was noise (and with append-mode
output it read as a glitchy wall). Story-beat messages must still appear.
"""
from __future__ import annotations

from engine.api import GameSession


def test_story_beat_cat_shows_message_without_relist():
    s = GameSession()
    try:
        s.new_game("T", "guardian")
        h = s.engine.cmd_handler
        room = h.player.current_room
        h.world.add_item_to_room("system_err_log", room)  # story_flag: typo_discovered

        joined = "".join(str(x) for x in s.submit("cat system_err_log"))

        assert "Memory restored" in joined, "story beat message missing"
        assert "Where you can go" not in joined, "cat must not append the room listing"
    finally:
        s.close()


def test_ordinary_cat_does_not_relist():
    s = GameSession()
    try:
        s.new_game("T", "guardian")
        # readme_txt_corrupt lives in home_grove and has no story_flag
        joined = "".join(str(x) for x in s.submit("cat readme_txt_corrupt"))
        assert "Where you can go" not in joined, "cat must not append the room listing"
    finally:
        s.close()
