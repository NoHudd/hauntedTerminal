"""Save versioning and compatibility.

Covers: round-trip save/load, the versioned camelCase envelope, refusal of saves
written before the filesystem tree (they persist room_states from when the boss
room had no lock), and from_dict tolerance of partial saves.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from engine.api import GameSession
from src.player import Player
from src.save import SAVE_VERSION, IncompatibleSaveError, SaveManager


@pytest.fixture
def session() -> Iterator[GameSession]:
    s = GameSession()
    s.new_game("Saver", "weaver")
    try:
        yield s
    finally:
        s.close()


def test_save_round_trip(session: GameSession, tmp_path) -> None:
    mgr = SaveManager(save_dir=str(tmp_path))
    session.submit("cd root")  # make some state

    mgr.save_game(session.player, session.world.get_state())
    loaded = mgr.load_run(mgr.active_run_id)

    assert loaded["version"] == SAVE_VERSION
    restored = Player.from_dict(loaded["player"])
    assert restored.name == "Saver"
    assert restored.player_class == "weaver"
    assert restored.current_room == session.player.current_room
    assert restored.max_health == session.player.max_health


def test_envelope_is_versioned_and_camelcase(session: GameSession, tmp_path) -> None:
    mgr = SaveManager(save_dir=str(tmp_path))
    path = mgr.save_game(session.player, session.world.get_state())
    raw = json.loads(Path(path).read_text())
    assert raw["version"] == SAVE_VERSION
    assert "savedAt" in raw and "saveDate" in raw
    assert "timestamp" not in raw and "save_date" not in raw


def _legacy_save(version: int | None) -> dict:
    """A save from before the filesystem tree. v1 had no version field."""
    save = {
        "player": {"name": "Old", "player_class": "guardian", "current_room": "root"},
        "world": {"room_states": {"core": {"locked": False, "hidden": False}}},
    }
    if version is None:
        save.update(timestamp=123.0, save_date="2020-01-01 00:00:00")
    else:
        save.update(version=version, savedAt=123.0, saveDate="2020-01-01 00:00:00")
    return save


@pytest.mark.parametrize("version", [None, 1, 2])
def test_pre_tree_saves_are_refused(version, tmp_path) -> None:
    """v2 and older persist room_states from before /boot was locked. Loading one
    would reopen the boss room, so it is refused rather than half-migrated."""
    (tmp_path / "run_old00000.json").write_text(json.dumps(_legacy_save(version)))
    mgr = SaveManager(save_dir=str(tmp_path))

    with pytest.raises(IncompatibleSaveError):
        mgr.load_run("old00000")


def test_incompatible_saves_are_not_offered(tmp_path) -> None:
    """The load menu must not list a save that would then fail to load."""
    (tmp_path / "run_old00000.json").write_text(json.dumps(_legacy_save(2)))
    mgr = SaveManager(save_dir=str(tmp_path))

    assert mgr.list_runs() == []


def test_from_dict_tolerates_partial_save() -> None:
    # Missing health/inventory/equipped_weapon must not KeyError.
    player = Player.from_dict({"name": "Partial", "player_class": "shaman"})
    assert player.name == "Partial"
    assert player.inventory == {}
    assert player.equipped_weapon is None
    assert player.max_health > 0


@pytest.mark.parametrize("version", [3, 4])
def test_v4_saves_are_refused_and_hidden(version, tmp_path) -> None:
    """Saves from before room flags have no flag state; /boot's gate would
    strand them, so they are refused and not offered."""
    (tmp_path / "run_old00000.json").write_text(json.dumps(_legacy_save(version)))
    mgr = SaveManager(save_dir=str(tmp_path))
    with pytest.raises(IncompatibleSaveError, match="flag"):
        mgr.load_run("old00000")
    assert mgr.list_runs() == []
