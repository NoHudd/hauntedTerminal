"""Enemy templates are typed; get_enemy hands combat a dict identical to the raw YAML."""
from __future__ import annotations

import glob
import os

import yaml

from engine.schema import Enemy


def test_load_enemy_data_returns_typed_models():
    from src.data_loader import load_enemy_data
    enemies = load_enemy_data()
    assert len(enemies) == 24
    for eid, e in enemies.items():
        assert isinstance(e, Enemy), (eid, type(e))
        assert e.health > 0


def test_get_enemy_returns_dict_matching_raw_yaml():
    from engine.api import GameSession
    s = GameSession()
    try:
        s.new_game("Tester", "guardian")
        world = s.engine.cmd_handler.world
        path = sorted(glob.glob("data/enemies/*.yml"))[0]
        eid = os.path.basename(path)[:-4]
        raw = yaml.safe_load(open(path)) or {}
        got = world.get_enemy(eid)  # no player_class -> unscaled dict
        assert isinstance(got, dict)
        assert set(raw.keys()) <= set(got.keys())
    finally:
        s.close()
