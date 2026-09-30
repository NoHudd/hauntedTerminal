"""Suite-wide settings.

Each switch makes a hidden failure a test failure: the event bus normally
logs and swallows a listener's exception, ViewBuilder normally returns a
placeholder view when a build fails, and the engine's flow methods catch a
rejected state transition and fall back to the menu.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest

import src.save as save_mod
from engine.events import EventBus
from src.game_states import GameState
from src.state_manager import InvalidTransitionError, StateManager
from src.viewmodels.view_builder import ViewBuilder


@pytest.fixture(autouse=True)
def _fail_loudly(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest,
) -> Iterator[None]:
    monkeypatch.setattr(EventBus, "strict_by_default", True)
    monkeypatch.setattr(ViewBuilder, "raise_errors", True)

    # The engine's flow methods catch broad exceptions and fall back to the
    # menu, which would hide a rejected state transition. Record them all.
    rejected: list[str] = []
    set_state = StateManager.set_state

    def recording(self: StateManager, new_state: GameState, emit_event: bool = True) -> None:
        try:
            set_state(self, new_state, emit_event)
        except InvalidTransitionError as e:
            rejected.append(str(e))
            raise

    monkeypatch.setattr(StateManager, "set_state", recording)
    yield
    if request.node.get_closest_marker("rejects_transition") is None:
        assert rejected == [], f"state transitions the game should never make: {rejected}"


@pytest.fixture(autouse=True)
def _isolated_saves(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Every test saves into its own scratch dir with no run in progress. With
    one file per run (and no pool cap) test saves would otherwise pile up in
    the real saves/."""
    manager = save_mod.save_manager
    monkeypatch.setattr(manager, "save_dir", str(tmp_path_factory.mktemp("saves")))
    monkeypatch.setattr(manager, "active_run_id", None)
    monkeypatch.setattr(manager, "pending_replace", None)


@pytest.fixture
def mgr() -> save_mod.SaveManager:
    """The game's own save manager, already pointed at this test's scratch dir
    (so the engine, commands and autosaves all write where the test reads)."""
    return save_mod.save_manager


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every save gets a later timestamp, so newest-first order is exact."""
    ticks = iter(range(1000, 100000, 10))
    monkeypatch.setattr(save_mod, "_now", lambda: float(next(ticks)))
