"""Armor mitigation: equip sets a capped mitigation fraction; take_damage applies it."""
from __future__ import annotations

import pytest

from src.player import ARMOR_DEFENSE_TO_PCT, ARMOR_MITIGATION_CAP, Player


def _guardian_with(item_id: str, defense: int) -> Player:
    p = Player("Tester", "guardian")
    p.add_to_inventory(item_id, {"type": "armor", "defense": defense})
    return p


def _expected_mitigation(defense: int) -> float:
    return min(ARMOR_MITIGATION_CAP, defense * ARMOR_DEFENSE_TO_PCT) / 100.0


def test_equip_armor_sets_mitigation_from_defense() -> None:
    p = _guardian_with("immutable_shield", 20)
    assert p.equip_armor("immutable_shield") is True
    assert p.equipped_armor == "immutable_shield"
    assert p.armor_mitigation == pytest.approx(_expected_mitigation(20))
    assert p.armor_mitigation > 0


def test_mitigation_is_capped() -> None:
    p = _guardian_with("overbuilt", 999)  # far beyond the cap
    p.equip_armor("overbuilt")
    assert p.armor_mitigation == pytest.approx(ARMOR_MITIGATION_CAP / 100.0)


def test_take_damage_applies_mitigation_with_floor() -> None:
    p = _guardian_with("immutable_shield", 20)
    p.equip_armor("immutable_shield")
    m = p.armor_mitigation
    before = p.health
    p.take_damage(20)
    assert before - p.health == max(1, round(20 * (1 - m)))
    # a tiny hit still costs at least 1
    hp = p.health
    p.take_damage(1)
    assert hp - p.health == 1


def test_unequipped_player_takes_full_damage() -> None:
    p = Player("Tester", "guardian")
    before = p.health
    p.take_damage(20)
    assert before - p.health == 20


from engine.api import GameSession  # noqa: E402


def test_equip_command_equips_armor() -> None:
    s = GameSession()
    s.new_game("Tester", "guardian")
    try:
        h = s.engine.cmd_handler
        armor_data = h.world.items["immutable_shield"]  # guardian-usable rare armor
        h.player.add_to_inventory("immutable_shield", dict(armor_data))
        s.submit("equip immutable_shield")
        assert h.player.equipped_armor == "immutable_shield"
        assert h.player.armor_mitigation > 0
    finally:
        s.close()


def test_sim_class_armor_is_obtainable_and_sorted() -> None:
    from sim.simulator import _class_armor
    guard = _class_armor("guardian")
    ids = [aid for aid, _ in guard]
    defenses = [d for _, d in guard]
    assert "immutable_shield" in ids                 # guardian rare tank piece
    assert "stack_guard_vest" not in ids             # weaver-only, excluded for guardian
    assert defenses == sorted(defenses)              # ascending by defense


def test_sim_equips_armor_and_gains_mitigation() -> None:
    from sim.simulator import _equip_for_stage
    p = Player("SimBot", "guardian")
    _equip_for_stage(p, "guardian", cleared=8, total=9)  # near the end of the gauntlet
    assert p.equipped_armor is not None
    assert p.armor_mitigation > 0
