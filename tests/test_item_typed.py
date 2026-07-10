"""Items validate at load; get_item hands consumers a dict; placement/mutation intact."""
from __future__ import annotations

import pytest
import yaml


def test_get_item_returns_dict_matching_raw_yaml():
    from engine.api import GameSession
    s = GameSession()
    try:
        s.new_game("Tester", "guardian")
        world = s.engine.cmd_handler.world
        weapons = yaml.safe_load(open("data/items/weapons.yaml")) or {}
        iid = next(iter(weapons))
        got = world.get_item(iid)
        assert isinstance(got, dict)
        assert set(weapons[iid].keys()) <= set(got.keys())
        assert got.get("damage") == weapons[iid].get("damage")
    finally:
        s.close()


def test_loaders_validate_and_return_dicts():
    from src.data_loader import load_consumable_data, load_weapon_data
    w = load_weapon_data("segfault_shield")
    assert isinstance(w, dict) and isinstance(w.get("damage"), int)
    c = load_consumable_data("health_packet")
    assert isinstance(c, dict) and isinstance(c.get("combat_effects"), dict)


def test_bad_item_field_raises_at_validation():
    from pydantic import ValidationError

    from engine.schema import Item
    with pytest.raises(ValidationError):
        Item(id="x", name="X", type="weapon", damage="not-a-number")
