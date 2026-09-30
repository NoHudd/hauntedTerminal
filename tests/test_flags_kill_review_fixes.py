"""Checkpoint timing around fights: the finale never leaves an unwinnable
newest save, and fleeing after a capture still saves the flag."""
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
    try:
        yield session
    finally:
        session.close()


def test_beating_the_overlord_writes_no_unwinnable_save(s: GameSession, tmp_path) -> None:
    """The win must fire; no checkpoint may land between the kill and it, or
    loading the newest save puts the player in a won-less, finished world."""
    h = s.engine.cmd_handler
    s.player.current_room = "core"
    h.check_for_enemies()
    combat = h.current_combat_session
    assert combat is not None
    combat.enemy_health = 1
    s.submit(next(iter(combat.available_attacks)))
    assert h.flow.game_won
    assert not list(tmp_path.iterdir())


def test_fleeing_after_a_capture_still_saves_the_flag(s: GameSession, tmp_path) -> None:
    h = s.engine.cmd_handler
    s.player.current_room = "proc_secrets"
    s.player.previous_room = "root"
    s.submit("kill 1337")
    assert h.current_combat_session is not None
    h.flags.on_enemy_defeated("runaway_fork.bomb")  # captured mid-fight
    h.end_combat({"fled": True, "enemy_id": "runaway_fork.bomb"})
    assert len(list(tmp_path.iterdir())) == 1
