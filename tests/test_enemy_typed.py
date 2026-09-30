"""Enemy templates are typed, and get_enemy hands combat a private typed copy."""
from __future__ import annotations

import glob
import os

import yaml

from engine.schema import Enemy


def test_load_enemy_data_returns_typed_models():
    from src.data_loader import load_enemy_data
    enemies = load_enemy_data()
    assert len(enemies) == 27
    for eid, e in enemies.items():
        assert isinstance(e, Enemy), (eid, type(e))
        assert e.health > 0


def test_get_enemy_returns_a_model_carrying_every_yaml_key():
    from engine.api import GameSession
    s = GameSession()
    try:
        s.new_game("Tester", "guardian")
        world = s.engine.cmd_handler.world
        path = sorted(glob.glob("data/enemies/*.yml"))[0]
        eid = os.path.basename(path)[:-4]
        raw = yaml.safe_load(open(path)) or {}
        got = world.get_enemy(eid)
        assert isinstance(got, Enemy)
        assert set(raw.keys()) <= set(got.model_dump(exclude_unset=True).keys())
    finally:
        s.close()


def test_get_enemy_never_hands_out_the_shared_template():
    from engine.api import GameSession
    s = GameSession()
    try:
        s.new_game("Tester", "guardian")
        world = s.engine.cmd_handler.world
        eid = next(iter(world.enemies))
        template_hp = world.enemies[eid].health
        copy = world.get_enemy(eid, "guardian")
        copy.health = 1
        copy.attack_patterns.append({"damage": 999})
        assert world.enemies[eid].health == template_hp
        assert {"damage": 999} not in world.enemies[eid].attack_patterns
    finally:
        s.close()
