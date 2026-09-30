"""LOAD GAME and NEW GAME through the save picker, driven headless with the
same commands the picker screen sends: pick <id>, delete <id>, back."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

import src.save as save_mod
from engine.api import GameSession
from engine.events import EventType
from src.game_states import GameState
from src.save import SaveManager


@pytest.fixture
def mgr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SaveManager:
    m = SaveManager(save_dir=str(tmp_path))
    monkeypatch.setattr(save_mod, "save_manager", m)
    monkeypatch.setattr("src.game_engine.save_manager", m)
    ticks = iter(range(1000, 100000, 10))
    monkeypatch.setattr(save_mod, "_now", lambda: float(next(ticks)))
    return m


@pytest.fixture
def fresh() -> Iterator[GameSession]:
    s = GameSession()
    try:
        yield s
    finally:
        s.close()


def _make_run(mgr: SaveManager, name: str, cls: str) -> str:
    s = GameSession()
    try:
        s.new_game(name, cls)
        run_id = mgr.begin_run()
        mgr.save_game(s.player, s.world.get_state())
        return run_id
    finally:
        s.close()
        mgr.end_run()


def _picker_events(s: GameSession) -> list[dict[str, Any]]:
    seen: list[dict[str, Any]] = []
    s.bus.subscribe(EventType.SAVE_PICKER_REQUESTED, lambda e: seen.append(e.data))
    return seen


def _text(lines: list[Any]) -> str:
    return "\n".join(str(line) for line in lines)


def test_load_with_no_saves_says_so_and_goes_back(mgr, fresh) -> None:
    seen = _picker_events(fresh)
    out = _text(fresh.submit("2"))
    assert fresh.state == GameState.WAITING_FOR_SAVE
    assert "No saves available" in out
    assert seen[-1] == {"mode": "continue", "runs": [], "legacyCount": 0}

    out = _text(fresh.submit("back"))
    assert fresh.state == GameState.MENU
    assert "[title screen]" in out


def test_load_picks_the_chosen_run_not_the_newest(mgr, fresh) -> None:
    ada = _make_run(mgr, "Ada", "guardian")
    zed = _make_run(mgr, "Zed", "weaver")
    seen = _picker_events(fresh)

    fresh.submit("2")
    rows = seen[-1]["runs"]
    assert [row["runId"] for row in rows] == [zed, ada]
    assert rows[1]["playerName"] == "Ada" and rows[1]["roomPath"].startswith("/")
    assert set(rows[1]) == {
        "runId", "playerName", "playerClass", "difficulty", "level",
        "roomPath", "health", "maxHealth", "savedAt", "cleared",
    }

    fresh.submit(f"pick {ada}")
    assert fresh.state == GameState.PLAYING
    assert fresh.player.name == "Ada"
    assert mgr.active_run_id == ada


def test_delete_from_the_picker(mgr, fresh) -> None:
    ada = _make_run(mgr, "Ada", "guardian")
    seen = _picker_events(fresh)
    fresh.submit("2")
    fresh.submit(f"delete {ada}")
    assert fresh.state == GameState.WAITING_FOR_SAVE
    assert seen[-1]["runs"] == []
    assert mgr.list_runs() == []


def test_an_unknown_pick_keeps_the_picker_open(mgr, fresh) -> None:
    _make_run(mgr, "Ada", "guardian")
    fresh.submit("2")
    out = _text(fresh.submit("pick nope"))
    assert fresh.state == GameState.WAITING_FOR_SAVE
    assert "Invalid choice" in out


def test_new_game_with_free_slots_goes_straight_to_difficulty(mgr, fresh) -> None:
    fresh.submit("1")
    assert fresh.state == GameState.WAITING_FOR_DIFFICULTY
    assert mgr.active_run_id is not None
    assert mgr.list_runs() == []  # nothing is written until the first save


def test_new_game_when_full_replaces_the_chosen_run_on_first_save(
    mgr, fresh, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(save_mod, "MAX_RUNS", 2)
    ada = _make_run(mgr, "Ada", "guardian")
    zed = _make_run(mgr, "Zed", "weaver")
    seen = _picker_events(fresh)

    fresh.submit("1")
    assert fresh.state == GameState.WAITING_FOR_SAVE
    assert seen[-1]["mode"] == "replace"

    fresh.submit(f"pick {ada}")
    assert fresh.state == GameState.WAITING_FOR_DIFFICULTY
    assert {r.run_id for r in mgr.list_runs()} == {ada, zed}  # backing out loses nothing

    for command in ("2", "1", "Neo", "skip"):
        fresh.submit(command)
    assert fresh.state == GameState.PLAYING
    fresh.submit("save")
    assert {r.run_id for r in mgr.list_runs()} == {zed, mgr.active_run_id}


def test_the_replace_picker_has_no_delete(mgr, fresh, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(save_mod, "MAX_RUNS", 1)
    ada = _make_run(mgr, "Ada", "guardian")
    fresh.submit("1")
    assert fresh.state == GameState.WAITING_FOR_SAVE
    out = _text(fresh.submit(f"delete {ada}"))
    assert "Invalid choice" in out
    assert fresh.state == GameState.WAITING_FOR_SAVE
    assert [r.run_id for r in mgr.list_runs()] == [ada]
