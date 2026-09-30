"""Autosaves must not grow the saves/ directory without bound.

The game autosaves on story beats and checkpoints; the old timestamped pool
accumulated thousands of files (observed: 16k files -> 4 minutes per fuzz
test) until it was capped. With one slot per run, autosaves overwrite the
run's file, so a run is always exactly one file.
"""
import json
import os

from src.save import SaveManager


class _P:
    def to_dict(self):
        return {"name": "t"}


def test_many_autosaves_in_one_run_leave_one_file(tmp_path):
    d = str(tmp_path / "saves")
    m = SaveManager(save_dir=d)
    for _ in range(50):
        m.save_game(_P(), {})
    files = [f for f in os.listdir(d) if f.endswith(".json")]
    assert len(files) == 1


def test_saves_still_valid_json(tmp_path):
    d = str(tmp_path / "saves")
    m = SaveManager(save_dir=d)
    path = m.save_game(_P(), {"x": 1})
    data = json.load(open(path))
    assert data["player"] == {"name": "t"}
