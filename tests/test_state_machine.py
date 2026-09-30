"""The engine owns the game mode. The transition table lists every change the
game makes and is enforced; the conftest guard also fails any test in which a
rejected transition was swallowed by a fallback."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

import src.save as save_mod
from engine.api import GameSession
from engine.events import EventBus, EventType
from src.game_states import GameState
from src.save import SaveManager
from src.state_manager import InvalidTransitionError, StateManager


@pytest.fixture
def fresh() -> Iterator[GameSession]:
    s = GameSession()
    try:
        yield s
    finally:
        s.close()


@pytest.mark.rejects_transition
def test_a_transition_the_game_never_makes_raises() -> None:
    sm = StateManager(EventBus())
    with pytest.raises(InvalidTransitionError):
        sm.set_state(GameState.IN_COMBAT)  # straight from the menu


def test_the_engine_ignores_a_mode_the_sender_claims(fresh: GameSession) -> None:
    fresh.new_game("Tess", "guardian")
    # "1" is New Game on the menu; in play it is just an unknown word.
    fresh.bus.emit_event(
        EventType.COMMAND_ENTERED, {"command": "1", "game_state": GameState.MENU}, "test"
    )
    assert fresh.state == GameState.PLAYING


def test_new_game_through_the_menu(fresh: GameSession) -> None:
    for command, state in (
        ("1", GameState.WAITING_FOR_DIFFICULTY),
        ("2", GameState.WAITING_FOR_CLASS),
        ("1", GameState.TUTORIAL_NAME_INPUT),
        ("Tess", GameState.TUTORIAL_NAME_INPUT),  # then the tutorial offer
        ("skip", GameState.PLAYING),
    ):
        fresh.submit(command)
        assert fresh.state == state, command


def test_f5_in_the_middle_of_a_fight(fresh: GameSession) -> None:
    fresh.new_game("Tess", "guardian")
    fresh.player.tutorial_state["completed"] = True
    fresh.world.spawn_tutorial_enemy("root")
    fresh.submit("cd root")
    assert fresh.state == GameState.IN_COMBAT
    fresh.engine.restart_game()
    assert fresh.state == GameState.MENU


def test_load_from_the_menu(
    fresh: GameSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    mgr = SaveManager(save_dir=str(tmp_path))
    monkeypatch.setattr(save_mod, "save_manager", mgr)
    monkeypatch.setattr("src.game_engine.save_manager", mgr)
    fresh.new_game("Tess", "guardian")
    mgr.save_game(fresh.player, fresh.world.get_state())
    run_id = mgr.active_run_id
    fresh.engine.restart_game()

    fresh.submit("2")
    assert fresh.state == GameState.WAITING_FOR_SAVE
    fresh.submit(f"pick {run_id}")
    assert fresh.state == GameState.PLAYING
    assert fresh.player.name == "Tess"


def test_f5_ends_the_run(fresh: GameSession) -> None:
    from src.save import save_manager
    fresh.new_game("Tess", "guardian")
    fresh.submit("save")
    assert save_manager.active_run_id is not None
    fresh.engine.restart_game()
    assert save_manager.active_run_id is None
