"""A player reaching /mnt is taught grep, reads the wall, then greps the flag."""
from collections.abc import Iterator

import pytest

from engine.api import GameSession
from src.save import save_manager


@pytest.fixture
def s(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Iterator[GameSession]:
    monkeypatch.setattr(save_manager, "save_dir", str(tmp_path))
    session = GameSession()
    session.new_game("t", "weaver")
    session.player.tutorial_state["completed"] = True
    session.world.enemy_locations = {
        e: r for e, r in session.world.enemy_locations.items() if r != "mnt_forest"
    }
    try:
        yield session
    finally:
        session.close()


def _out(s: GameSession, cmd: str) -> str:
    return "\n".join(str(x) for x in s.submit(cmd))


def test_first_grep_room_teaches_then_grep_captures(s: GameSession) -> None:
    arrival = _out(s, "cd /mnt")
    assert "grep FLAG lost_user_log" in arrival
    _out(s, "cat lost_user_log")
    assert not s.world.flag_captured("mnt_forest")
    out = _out(s, "grep FLAG lost_user_log")
    assert s.world.flag_captured("mnt_forest")
    assert "Flags 1/13" in out
