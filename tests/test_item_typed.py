"""Items validate at load, and every consumer gets a private typed copy."""
from __future__ import annotations

import pytest
import yaml

from engine.schema import Item


def test_get_item_returns_a_model_carrying_every_yaml_key():
    from engine.api import GameSession
    s = GameSession()
    try:
        s.new_game("Tester", "guardian")
        world = s.engine.cmd_handler.world
        weapons = yaml.safe_load(open("data/items/weapons.yaml")) or {}
        iid = next(iter(weapons))
        got = world.get_item(iid)
        assert isinstance(got, Item)
        assert set(weapons[iid].keys()) <= set(got.model_dump(exclude_unset=True).keys())
        assert got.damage == weapons[iid].get("damage")
    finally:
        s.close()


def test_get_item_never_hands_out_the_shared_template():
    from engine.api import GameSession
    s = GameSession()
    try:
        s.new_game("Tester", "guardian")
        world = s.engine.cmd_handler.world
        copy = world.get_item("health_packet")
        copy.tags.append("tampered")
        assert "tampered" not in world.items["health_packet"].tags
    finally:
        s.close()


def test_load_item_returns_typed_copies():
    from src.data_loader import load_item
    w = load_item("segfault_shield")
    assert isinstance(w, Item) and w.damage > 0
    c = load_item("health_packet")
    assert isinstance(c, Item) and "player_heal" in c.combat_effects
    assert load_item("health_packet") is not c
    assert load_item("no_such_item") is None


def test_inventory_round_trips_through_the_save_dict():
    from src.player import Player
    p = Player("Tester", "guardian")
    before = p.to_dict()["inventory"]
    restored = Player.from_dict(p.to_dict())
    assert all(isinstance(i, Item) for i in restored.inventory.values())
    assert restored.to_dict()["inventory"] == before


def test_bad_item_field_raises_at_validation():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Item(id="x", name="X", type="weapon", damage="not-a-number")
