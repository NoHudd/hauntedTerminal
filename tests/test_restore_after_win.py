"""Post-win "r" (restore the most recent save) must give a fully working run.

It used to rebuild the command handler without its event subscriptions:
entering a room with an enemy started no fight, NPCs said nothing after
combat, and the tutorial went quiet. Both load paths now share one entry step.
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

import src.save as save_mod
from engine.api import GameSession
from engine.events import Event, EventType
from src.game_states import GameState
from src.game_world import TUTORIAL_ENEMY
from src.save import SaveManager


@pytest.fixture
def restored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[GameSession]:
    mgr = SaveManager(save_dir=str(tmp_path))
    monkeypatch.setattr(save_mod, "save_manager", mgr)
    monkeypatch.setattr("src.game_engine.save_manager", mgr)

    s = GameSession()
    s.new_game("Victor", "guardian")
    s.player.tutorial_state["completed"] = True
    mgr.save_game(s.player, s.world.get_state())
    try:
        yield s
    finally:
        s.close()


def _restore(s: GameSession) -> list[Event]:
    seen: list[Event] = []
    for et in (EventType.GAME_STARTED, EventType.ROOM_ENTERED):
        s.bus.subscribe(et, seen.append)
    s.engine.cmd_handler.flow.handle_game_over_input("r")
    s.ui.drain()
    return seen


def test_restore_announces_the_run_to_the_ui(restored: GameSession) -> None:
    seen = _restore(restored)
    assert [e.type for e in seen] == [EventType.GAME_STARTED, EventType.ROOM_ENTERED]
    assert restored.state == GameState.PLAYING


def test_entering_a_room_with_an_enemy_starts_a_fight_after_restore(
    restored: GameSession,
) -> None:
    _restore(restored)
    restored.world.spawn_tutorial_enemy("root")
    restored.submit("cd root")
    session = restored.engine.cmd_handler.current_combat_session
    assert session is not None and session.enemy_id == TUTORIAL_ENEMY


def test_a_failed_restore_falls_back_to_a_new_game(
    restored: GameSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken() -> dict:
        raise OSError("disk gone")

    monkeypatch.setattr(save_mod, "load_most_recent_save", broken)
    # The engine's own restore (GameFlow's "r" catches load errors itself first).
    restored.engine._restart_from_save()
    out = "\n".join(restored.ui.drain())
    assert "Failed to load save" in out
    assert restored.state == GameState.WAITING_FOR_DIFFICULTY


def test_the_tui_can_show_the_restore_failure() -> None:
    """The fallback reports through ui.display_message (a UIProtocol method)."""
    from src.ui.textual_ui import TextualGameUI

    assert callable(getattr(TextualGameUI, "display_message", None))
