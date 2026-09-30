"""Arriving in /proc: taught ps + kill, then ps, kill, fight, flag."""
from collections.abc import Iterator

import pytest

from engine.api import GameSession
from src.save import save_manager


@pytest.fixture
def s(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Iterator[GameSession]:
    monkeypatch.setattr(save_manager, "save_dir", str(tmp_path))
    session = GameSession()
    session.new_game("t", "shaman")
    session.player.tutorial_state["completed"] = True
    try:
        yield session
    finally:
        session.close()


def _out(s: GameSession, cmd: str) -> str:
    return "\n".join(str(x) for x in s.submit(cmd))


def test_first_rogue_from_lesson_to_flag(s: GameSession) -> None:
    h = s.engine.cmd_handler
    s.world.discover_room("proc_secrets")
    arrival = _out(s, "cd /proc")
    assert "kill 1337" in arrival
    assert "1337" in _out(s, "ps")
    _out(s, "kill 1337")
    out = ""
    while h.current_combat_session:
        out += _out(s, next(iter(h.current_combat_session.available_attacks)))
    assert s.world.flag_captured("proc_secrets")
    assert "FLAG{kill_ends_what_ps_finds}" in out
