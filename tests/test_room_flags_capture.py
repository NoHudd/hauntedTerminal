"""Reading a room's flag file captures its flag once: XP, a checkpoint, counts."""
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
    session.player.current_room = "root"
    try:
        yield session
    finally:
        session.close()


def _out(s: GameSession, cmd: str) -> str:
    return "\n".join(str(x) for x in s.submit(cmd))


def test_reading_the_flag_file_captures_it(s: GameSession, tmp_path) -> None:
    cycles = s.player.harvesting_cycles
    level = s.player.level
    out = _out(s, "cat motd")
    assert s.world.flag_captured("root")
    assert "FLAG{cat_reads_files}" in out and "Flags 1/" in out
    assert (s.player.level, s.player.harvesting_cycles) != (level, cycles)
    assert list(tmp_path.iterdir()), "capture should write a checkpoint save"


def test_second_read_is_a_no_op(s: GameSession, tmp_path) -> None:
    s.submit("cat motd")
    saves = set(tmp_path.iterdir())
    cycles = s.player.harvesting_cycles
    out = _out(s, "cat motd")
    assert "Flag captured" not in out
    assert s.player.harvesting_cycles == cycles
    assert set(tmp_path.iterdir()) == saves


def test_other_files_do_not_capture(s: GameSession) -> None:
    s.player.current_room = "home_grove"
    s.submit("cat readme_txt_corrupt")
    assert not s.world.flag_captured("home_grove")


def test_story_file_flag_restores_memory_and_saves_once(s: GameSession, tmp_path) -> None:
    s.player.current_room = "home_grove"
    out = _out(s, "cat .bash_profile")
    assert "Memory restored" in out and "Flag captured" in out
    assert s.world.flag_captured("home_grove")
    assert len(list(tmp_path.iterdir())) == 1


def test_counts_split_main_and_secret(s: GameSession) -> None:
    flags = s.engine.cmd_handler.flags
    assert flags.counts() == (0, 5, 0, 2)
    s.submit("cat motd")
    assert flags.counts() == (1, 5, 0, 2)
    assert flags.summary() == "Flags 1/5 · Secrets 0/2"
