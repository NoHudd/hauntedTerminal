"""ps reveals the rogue; kill brings it out; errors teach PIDs."""
from collections.abc import Iterator

import pytest

from engine.api import GameSession
from src.save import save_manager


@pytest.fixture
def s(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Iterator[GameSession]:
    monkeypatch.setattr(save_manager, "save_dir", str(tmp_path))
    session = GameSession()
    session.new_game("t", "guardian")
    session.player.tutorial_state["completed"] = True
    session.player.current_room = "proc_secrets"
    try:
        yield session
    finally:
        session.close()


def _out(s: GameSession, cmd: str) -> str:
    return "\n".join(str(x) for x in s.submit(cmd))


def test_ps_shows_the_rogue_as_the_odd_one_out(s: GameSession) -> None:
    out = _out(s, "ps")
    assert "1337" in out and "runaway_fork" in out and "CPU" in out


def test_kill_brings_the_rogue_out_to_fight(s: GameSession) -> None:
    _out(s, "kill 1337")
    assert s.engine.cmd_handler.current_combat_session is not None


def test_beating_the_rogue_captures_and_saves(s: GameSession, tmp_path) -> None:
    h = s.engine.cmd_handler
    s.submit("kill 1337")
    while h.current_combat_session:
        s.submit(next(iter(h.current_combat_session.available_attacks)))
    assert s.world.flag_captured("proc_secrets")
    assert list(tmp_path.iterdir())


def test_ps_forgets_the_rogue_after_capture(s: GameSession) -> None:
    s.world.mark_flag_captured("proc_secrets")
    assert "1337" not in _out(s, "ps")


def test_system_pid_is_not_permitted(s: GameSession) -> None:
    out = _out(s, "kill 1")
    assert "Operation not permitted" in out and "odd one out" in out


def test_unknown_pid(s: GameSession) -> None:
    assert "No such process" in _out(s, "kill 9999")


def test_kill_usage_and_non_numbers(s: GameSession) -> None:
    assert "Usage: kill" in _out(s, "kill")
    assert "number" in _out(s, "kill runaway_fork")


def test_man_kill_exists(s: GameSession) -> None:
    assert "terminate a process" in _out(s, "man kill")
