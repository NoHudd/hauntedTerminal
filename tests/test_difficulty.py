"""Difficulty-mode tests (difficulty-sim Part A).

Modes scale enemy HP/damage and XP; multipliers come from data/difficulty.yaml.
"""
from __future__ import annotations

import pytest

from src import difficulty


@pytest.fixture(autouse=True)
def _reset_mode():
    difficulty.load()
    difficulty.set_mode("medium")
    yield
    difficulty.set_mode("medium")


def test_medium_is_neutral() -> None:
    difficulty.set_mode("medium")
    e = difficulty.scale_enemy({"health": 100, "damage": 10})
    assert e["health"] == 100 and e["damage"] == 10
    assert difficulty.scale_xp(50) == 50


def test_easy_weakens_enemies_and_boosts_xp() -> None:
    difficulty.set_mode("easy")
    e = difficulty.scale_enemy({"health": 100, "damage": 10})
    assert e["health"] < 100 and e["damage"] < 10
    assert difficulty.scale_xp(50) > 50


def test_hard_strengthens_enemies_and_cuts_xp() -> None:
    difficulty.set_mode("hard")
    e = difficulty.scale_enemy({"health": 100, "damage": 10})
    assert e["health"] > 100 and e["damage"] > 10
    assert difficulty.scale_xp(50) < 50


def test_scale_enemy_does_not_mutate_input() -> None:
    difficulty.set_mode("hard")
    original = {"health": 100, "damage": 10}
    difficulty.scale_enemy(original)
    assert original == {"health": 100, "damage": 10}


def test_get_enemy_applies_difficulty() -> None:
    from engine.api import GameSession

    s = GameSession()
    try:
        s.new_game("T", "guardian")
        eid = next(iter(s.world.enemies))
        difficulty.set_mode("easy")
        easy = s.world.get_enemy(eid, "guardian")["health"]
        difficulty.set_mode("hard")
        hard = s.world.get_enemy(eid, "guardian")["health"]
        assert hard > easy
    finally:
        difficulty.set_mode("medium")
        s.close()


def test_invalid_mode_falls_back_to_medium() -> None:
    difficulty.set_mode("nonsense")
    assert difficulty.current_mode() == "medium"
