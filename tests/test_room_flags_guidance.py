"""Beginners are taught once, can ask for a hint, and get nudged when stuck."""
from collections.abc import Iterator

import pytest

from engine.api import GameSession
from src.flags import STUCK_AFTER
from src.save import save_manager


@pytest.fixture
def s(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Iterator[GameSession]:
    monkeypatch.setattr(save_manager, "save_dir", str(tmp_path))
    session = GameSession()
    session.new_game("t", "guardian")
    session.player.tutorial_state["completed"] = True
    try:
        yield session
    finally:
        session.close()


def _out(s: GameSession, cmd: str) -> str:
    return "\n".join(str(x) for x in s.submit(cmd))


def test_first_visit_to_a_teaching_room_gets_the_lesson_once(s: GameSession) -> None:
    first = _out(s, "cd /")
    assert "ECHO>" in first and "cat motd" in first
    s.submit("cd /home")
    again = _out(s, "cd /")
    assert "cat motd" not in again


def test_hint_escalates_from_nudge_to_exact_command(s: GameSession) -> None:
    s.player.current_room = "bin_armory"
    s.world.enemy_locations = {
        e: r for e, r in s.world.enemy_locations.items() if r != "bin_armory"
    }
    first = _out(s, "hint")
    second = _out(s, "hint")
    assert "cat .ancient_manual_man" not in first
    assert "cat .ancient_manual_man" in second


def test_hint_where_there_is_nothing_to_find(s: GameSession) -> None:
    s.player.current_room = "proc_secrets"
    assert "No flag" in _out(s, "hint")
    s.player.current_room = "root"
    s.submit("cat motd")
    assert "already captured" in _out(s, "hint")


def test_idle_commands_bring_a_nudge_once(s: GameSession) -> None:
    s.player.current_room = "root"
    outs = [_out(s, "pwd") for _ in range(STUCK_AFTER)]
    assert "ECHO>" in outs[-1] and "hint" in outs[-1]
    assert all("ECHO>" not in o for o in outs[:-1])
    assert "ECHO>" not in _out(s, "pwd")


def test_no_guidance_while_the_tutorial_runs(s: GameSession) -> None:
    s.player.tutorial_state["completed"] = False
    out = _out(s, "cd /")
    s.player.current_room = "root"
    idle = [_out(s, "pwd") for _ in range(STUCK_AFTER)]
    assert "cat motd" not in out
    assert all("hint" not in o for o in idle)


def test_combat_commands_do_not_count_as_idle(s: GameSession) -> None:
    flags = s.engine.cmd_handler.flags
    s.player.current_room = "root"
    for _ in range(STUCK_AFTER):
        flags.after_command(in_combat=True)
    assert flags._idle == 0
