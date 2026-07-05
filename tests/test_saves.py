"""Save versioning + migration tests (rewrite Phase 4a).

Covers: round-trip save/load, the v2 camelCase envelope, migration of a legacy
v1 (no-version, snake-case) save, and from_dict tolerance of partial saves (the
old bracket access raised KeyError).
"""
from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

from engine.api import GameSession
from src.player import Player
from src.save import SAVE_VERSION, SaveManager


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

    mgr.save_game(session.player, session.world.get_state(), "s1.json")
    loaded = mgr.load_game("s1.json")

    assert loaded["version"] == SAVE_VERSION
    restored = Player.from_dict(loaded["player"])
    assert restored.name == "Saver"
    assert restored.player_class == "weaver"
    assert restored.current_room == session.player.current_room
    assert restored.max_health == session.player.max_health


def test_v2_envelope_is_camelcase(session: GameSession, tmp_path) -> None:
    mgr = SaveManager(save_dir=str(tmp_path))
    mgr.save_game(session.player, session.world.get_state(), "s.json")
    raw = json.loads((tmp_path / "s.json").read_text())
    assert raw["version"] == 2
    assert "savedAt" in raw and "saveDate" in raw
    assert "timestamp" not in raw and "save_date" not in raw


def test_legacy_v1_save_migrates(tmp_path) -> None:
    # A pre-versioning save: no "version", snake-case envelope keys.
    legacy = {
        "player": {"name": "Old", "player_class": "guardian", "current_room": "root"},
        "world": {},
        "timestamp": 123.0,
        "save_date": "2020-01-01 00:00:00",
    }
    (tmp_path / "old.json").write_text(json.dumps(legacy))

    mgr = SaveManager(save_dir=str(tmp_path))
    loaded = mgr.load_game("old.json")

    assert loaded["version"] == SAVE_VERSION
    assert loaded["saveDate"] == "2020-01-01 00:00:00"
    assert loaded["savedAt"] == 123.0
    assert "save_date" not in loaded and "timestamp" not in loaded
    # And the migrated payload still builds a player.
    assert Player.from_dict(loaded["player"]).name == "Old"


def test_from_dict_tolerates_partial_save() -> None:
    # Missing health/inventory/equipped_weapon must not KeyError.
    player = Player.from_dict({"name": "Partial", "player_class": "shaman"})
    assert player.name == "Partial"
    assert player.inventory == {}
    assert player.equipped_weapon is None
    assert player.max_health > 0


def test_get_save_files_reads_v2(session: GameSession, tmp_path) -> None:
    mgr = SaveManager(save_dir=str(tmp_path))
    mgr.save_game(session.player, session.world.get_state(), "s.json")
    files = mgr.get_save_files()
    assert len(files) == 1
    assert files[0]["player_name"] == "Saver"
    assert files[0]["date"] != "Unknown date"
