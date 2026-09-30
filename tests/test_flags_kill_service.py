"""The rogue shows only while hidden; beating a flag enemy captures; the
checkpoint waits for victory."""
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


def test_rogue_process_is_listed_until_released(s: GameSession) -> None:
    flags = s.engine.cmd_handler.flags
    assert flags.rogue_process() == (1337, "runaway_fork")
    assert flags.release_rogue() == "runaway_fork.bomb"
    assert s.world.enemy_locations["runaway_fork.bomb"] == "proc_secrets"
    assert flags.rogue_process() is None


def test_no_rogue_line_while_it_is_already_out(s: GameSession) -> None:
    flags = s.engine.cmd_handler.flags
    flags.release_rogue()
    s.world.mark_enemy_as_fled("runaway_fork.bomb", "proc_secrets")
    assert flags.rogue_process() is None
    assert flags.release_rogue() is None


def test_defeating_the_flag_enemy_captures(s: GameSession) -> None:
    flags = s.engine.cmd_handler.flags
    assert flags.on_enemy_defeated("runaway_fork.bomb")
    assert s.world.flag_captured("proc_secrets")
    assert not flags.on_enemy_defeated("runaway_fork.bomb")


def test_defeat_capture_is_checkpointed_after_victory(s: GameSession, tmp_path) -> None:
    flags = s.engine.cmd_handler.flags
    flags.on_enemy_defeated("runaway_fork.bomb")
    assert not list(tmp_path.iterdir()), "no save mid-fight"
    flags.flush_checkpoint()
    assert len(list(tmp_path.iterdir())) == 1
    flags.flush_checkpoint()
    assert len(list(tmp_path.iterdir())) == 1


def test_boss_defeat_captures_via_on_kill(s: GameSession) -> None:
    s.player.current_room = "core"
    s.engine.cmd_handler.on_kill("daemon_overlord.sys")
    assert s.world.flag_captured("core")


def test_first_kill_room_teaches_kill(s: GameSession) -> None:
    s.player.current_room = "deprecated_dir"
    s.ui.clear_console()
    s.engine.cmd_handler.flags.on_room_entered("deprecated_dir")
    assert "kill 2048" in "\n".join(s.ui.drain())
