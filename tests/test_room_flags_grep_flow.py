"""cat shows a grep log's wall but never captures; grep output captures;
NPCs give the room's clue while its flag is out there."""
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
    session.player.current_room = "mnt_forest"
    session.world.enemy_locations = {
        e: r for e, r in session.world.enemy_locations.items() if r != "mnt_forest"
    }
    try:
        yield session
    finally:
        session.close()


def _out(s: GameSession, cmd: str) -> str:
    return "\n".join(str(x) for x in s.submit(cmd))


def test_cat_of_a_log_prints_the_whole_wall(s: GameSession) -> None:
    out = _out(s, "cat lost_user_log")
    assert out.count("user:") >= 300
    assert not s.world.flag_captured("mnt_forest")
    assert "ECHO>" in out


def test_on_grep_captures_only_when_the_flag_line_matched(s: GameSession) -> None:
    flags = s.engine.cmd_handler.flags
    assert not flags.on_grep("lost_user_log", ["[03:00:01] user: ls"])
    assert flags.on_grep("lost_user_log", ["x FLAG{grep_finds_needles}"])
    assert s.world.flag_captured("mnt_forest")


def test_npc_gives_the_clue_until_the_flag_is_captured(s: GameSession) -> None:
    out = _out(s, "talk lost_user.dat")
    assert "so long now" in out
    s.world.mark_flag_captured("mnt_forest")
    assert "so long now" not in _out(s, "talk lost_user.dat")
