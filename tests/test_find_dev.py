"""`find /dev -name null` must not name /dev while its door is still hidden
behind the Sudo Privileges Badge; once revealed, it points at the real path."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from engine.api import GameSession


@pytest.fixture
def s() -> Iterator[GameSession]:
    session = GameSession()
    session.new_game("t", "guardian")
    session.player.tutorial_state["completed"] = True
    session.player.current_room = "bin_armory"
    session.world.enemy_locations = {
        e: r for e, r in session.world.enemy_locations.items() if r != "bin_armory"
    }
    try:
        yield session
    finally:
        session.close()


def _find(s: GameSession) -> str:
    return "\n".join(str(x) for x in s.submit("find /dev -name null"))


def test_hidden_dev_is_not_found(s: GameSession) -> None:
    out = _find(s)
    assert "No such file" in out
    assert "Found" not in out and "cd " not in out


def test_revealed_dev_is_found_with_its_real_path(s: GameSession) -> None:
    s.world.reveal_doors("sudo_privileges_badge")
    out = _find(s)
    assert "Found" in out and "cd /dev" in out
    assert "dev_null_void" not in out


def test_revealed_dev_is_found_from_anywhere(s: GameSession) -> None:
    s.world.reveal_doors("sudo_privileges_badge")
    s.player.current_room = "root"
    assert "Found" in _find(s)
