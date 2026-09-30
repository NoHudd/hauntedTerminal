"""/boot opens with any 11 of the 12 main flags outside it."""
from collections.abc import Iterator

import pytest

from engine.api import GameSession


@pytest.fixture
def s() -> Iterator[GameSession]:
    session = GameSession()
    session.new_game("t", "guardian")
    try:
        yield session
    finally:
        session.close()


def _main_rooms_outside_boot(s: GameSession) -> list[str]:
    return [
        rid for rid, room in s.world.rooms.items()
        if room.flag is not None and not room.hidden and rid != "core"
    ]


def test_boot_is_no_longer_key_locked(s: GameSession) -> None:
    assert "master_key" not in s.world.items
    assert s.world.get_room("core").flags_required == 11


def test_ten_flags_are_not_enough_eleven_are(s: GameSession) -> None:
    rooms = _main_rooms_outside_boot(s)
    assert len(rooms) == 12
    for rid in rooms[:10]:
        s.world.mark_flag_captured(rid)
    allowed, denial = s.world.check_access("core", s.player)
    assert not allowed and denial["reason"] == "flags"
    assert (denial["flags_required"], denial["flags_have"]) == (11, 10)
    s.world.mark_flag_captured(rooms[10])
    assert s.world.check_access("core", s.player)[0]


def test_secrets_do_not_open_boot(s: GameSession) -> None:
    for rid, room in s.world.rooms.items():
        if room.flag is not None and room.hidden:
            s.world.mark_flag_captured(rid)
    assert not s.world.check_access("core", s.player)[0]


def test_boot_flag_is_not_counted_for_boot(s: GameSession) -> None:
    rooms = _main_rooms_outside_boot(s)
    for rid in rooms[:10]:
        s.world.mark_flag_captured(rid)
    s.world.mark_flag_captured("core")
    assert not s.world.check_access("core", s.player)[0]


def test_flag_counts_can_exclude_a_room(s: GameSession) -> None:
    s.world.mark_flag_captured("core")
    assert s.world.flag_counts()[:2] == (1, 13)
    assert s.world.flag_counts(exclude="core")[:2] == (0, 12)
