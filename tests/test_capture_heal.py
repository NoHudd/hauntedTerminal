"""Capturing a flag restores the player to full HP, and says so."""
from __future__ import annotations

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


def test_capture_refills_hp(s: GameSession) -> None:
    s.player.health = 7
    out = "\n".join(str(x) for x in s.submit("grep FLAG lost_user_log"))
    assert s.world.flag_captured("mnt_forest")
    assert s.player.health == s.player.max_health
    assert f"+{s.player.max_health - 7} HP" in out and "fully restored" in out


def test_capture_at_full_hp_says_nothing_about_healing(s: GameSession) -> None:
    out = "\n".join(str(x) for x in s.submit("grep FLAG lost_user_log"))
    assert s.world.flag_captured("mnt_forest")
    assert "fully restored" not in out
