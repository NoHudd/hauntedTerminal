"""Death -> game-over screen -> the r/n/q choice, through GameFlow."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from engine.api import GameSession
from engine.events import EventType
from src.game_states import GameState
from src.save import save_manager


@pytest.fixture
def session() -> Iterator[GameSession]:
    s = GameSession()
    s.new_game("D", "guardian")
    try:
        yield s
    finally:
        s.close()


def _die(s: GameSession) -> None:
    s.engine.cmd_handler.effects.execute_effect({"damage": 10_000})


def test_lethal_effect_enters_game_over_mode(session: GameSession) -> None:
    _die(session)
    assert session.engine.cmd_handler.flow.in_game_over_mode is True


def test_invalid_choice_reprompts_and_stays_on_the_screen(session: GameSession) -> None:
    _die(session)
    out = "\n".join(str(line) for line in session.submit("x"))
    assert "Invalid option" in out
    assert session.engine.cmd_handler.flow.in_game_over_mode is True


def test_main_menu_choice_returns_to_the_title(session: GameSession) -> None:
    seen: list[dict] = []
    session.bus.subscribe(EventType.GAME_OVER, lambda e: seen.append(e.data))
    _die(session)
    session.submit("m")
    assert session.state == GameState.MENU
    assert [data["reason"] for data in seen] == ["menu"]  # the UI shows the title
    assert save_manager.active_run_id is None  # the run is over


def test_quit_choice_asks_the_frontend_to_stop(session: GameSession) -> None:
    _die(session)
    session.submit("q")
    assert session.ui.quit_requested is True
