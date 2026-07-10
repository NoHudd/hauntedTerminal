"""Autosave cap: the save pool must not grow without bound.

The game autosaves on every room move; without a cap the saves/ directory
accumulates thousands of files and every save/list operation slows to a crawl
(observed: 16k files -> 4 minutes per fuzz test).
"""
import json
import os

from src.save import MAX_SAVE_FILES, SaveManager


class _P:
    def to_dict(self):
        return {"name": "t"}


def _fill(manager, save_dir, n):
    for i in range(n):
        manager.save_game(_P(), {}, save_name=f"save_{i:05d}.json")


def test_save_pool_is_capped(tmp_path):
    d = str(tmp_path / "saves")
    m = SaveManager(save_dir=d)
    _fill(m, d, MAX_SAVE_FILES + 25)
    files = [f for f in os.listdir(d) if f.endswith(".json")]
    assert len(files) == MAX_SAVE_FILES


def test_cap_keeps_the_newest(tmp_path):
    d = str(tmp_path / "saves")
    m = SaveManager(save_dir=d)
    _fill(m, d, MAX_SAVE_FILES + 5)
    files = sorted(f for f in os.listdir(d) if f.endswith(".json"))
    # oldest 5 pruned, newest MAX kept
    assert files[0] == f"save_{5:05d}.json"
    assert files[-1] == f"save_{MAX_SAVE_FILES + 4:05d}.json"


def test_saves_still_valid_json(tmp_path):
    d = str(tmp_path / "saves")
    m = SaveManager(save_dir=d)
    path = m.save_game(_P(), {"x": 1})
    data = json.load(open(path))
    assert data["player"] == {"name": "t"}
