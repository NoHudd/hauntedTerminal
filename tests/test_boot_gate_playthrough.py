"""Holding 11 flags, the player walks into /boot; with 10 they are turned away."""
from collections.abc import Iterator

import pytest

from engine.api import GameSession


@pytest.fixture
def s() -> Iterator[GameSession]:
    session = GameSession()
    session.new_game("t", "guardian")
    session.player.tutorial_state["completed"] = True
    try:
        yield session
    finally:
        session.close()


def test_eleven_flags_open_boot(s: GameSession) -> None:
    rooms = [
        rid for rid, room in s.world.rooms.items()
        if room.flag is not None and not room.hidden and rid != "core"
    ]
    for rid in rooms[:10]:
        s.world.mark_flag_captured(rid)
    s.submit("cd /boot")
    assert s.player.current_room != "core"
    s.world.mark_flag_captured(rooms[10])
    s.submit("cd /boot")
    assert s.player.current_room == "core"
