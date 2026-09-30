"""Saves from the old shared pool (save_<timestamp>.json) become run slots:
newest file per hero, every original moved to saves/legacy/, nothing deleted."""
from __future__ import annotations

import json
from pathlib import Path

from src.save import MAX_RUNS, SAVE_VERSION, SaveManager


def _v5(name: str, cls: str, diff: str, saved_at: float, room: str = "home_grove") -> dict:
    return {
        "version": 5,
        "player": {"name": name, "player_class": cls, "current_room": room,
                   "level": 1, "health": 10, "max_health": 10},
        "world": {}, "difficulty": diff,
        "savedAt": saved_at, "saveDate": "2026-09-01 00:00:00",
    }


def _put(folder: Path, name: str, data: dict | str) -> None:
    (folder / name).write_text(data if isinstance(data, str) else json.dumps(data))


def test_old_saves_become_one_slot_per_hero(tmp_path: Path) -> None:
    _put(tmp_path, "save_1.json", _v5("Ada", "guardian", "easy", 100, room="root"))
    _put(tmp_path, "save_2.json", _v5("Ada", "guardian", "easy", 300, room="var_dungeon"))
    _put(tmp_path, "save_3.json", _v5("Ada", "guardian", "hard", 200))
    _put(tmp_path, "save_4.json", _v5("Zed", "weaver", "easy", 250))

    runs = SaveManager(save_dir=str(tmp_path)).list_runs()

    assert [(r.player_name, r.difficulty) for r in runs] == [
        ("Ada", "easy"), ("Zed", "easy"), ("Ada", "hard"),
    ]
    assert runs[0].room_id == "var_dungeon"  # the newest file of its group
    raw = json.loads((tmp_path / f"run_{runs[0].run_id}.json").read_text())
    assert raw["version"] == SAVE_VERSION
    assert raw["createdAt"] == 100  # the group's oldest save
    assert raw["cleared"] is False


def test_every_old_file_moves_to_legacy_and_none_is_deleted(tmp_path: Path) -> None:
    for i in range(3):
        _put(tmp_path, f"save_{i}.json", _v5("Ada", "guardian", "easy", i))
    _put(tmp_path, "save_old.json", {"version": 4, "player": {"name": "Old"}})
    _put(tmp_path, "save_bad.json", "{nope")

    mgr = SaveManager(save_dir=str(tmp_path))
    assert len(mgr.list_runs()) == 1
    assert list(tmp_path.glob("save_*.json")) == []
    assert sorted(p.name for p in (tmp_path / "legacy").iterdir()) == [
        "save_0.json", "save_1.json", "save_2.json", "save_bad.json", "save_old.json",
    ]
    assert mgr.legacy_count() == 5


def test_migration_fills_only_free_slots(tmp_path: Path) -> None:
    for i in range(MAX_RUNS + 2):
        _put(tmp_path, f"save_{i}.json", _v5(f"Hero{i}", "guardian", "easy", i))
    runs = SaveManager(save_dir=str(tmp_path)).list_runs()
    assert len(runs) == MAX_RUNS
    assert runs[-1].player_name == "Hero2"  # the two oldest heroes stay in legacy/ only


def test_migration_runs_once(tmp_path: Path) -> None:
    _put(tmp_path, "save_1.json", _v5("Ada", "guardian", "easy", 1))
    mgr = SaveManager(save_dir=str(tmp_path))
    mgr.list_runs()
    mgr.list_runs()
    assert len(mgr.list_runs()) == 1


def test_a_migrated_slot_loads(tmp_path: Path) -> None:
    _put(tmp_path, "save_1.json", _v5("Ada", "guardian", "easy", 1))
    mgr = SaveManager(save_dir=str(tmp_path))
    run = mgr.list_runs()[0]
    loaded = mgr.load_run(run.run_id)
    assert loaded is not None and loaded["player"]["name"] == "Ada"


def test_no_legacy_folder_means_zero(tmp_path: Path) -> None:
    assert SaveManager(save_dir=str(tmp_path)).legacy_count() == 0
